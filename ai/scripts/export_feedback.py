"""Xuất các lượt quét người dùng đã sửa nhãn thành bộ ảnh để huấn luyện lại mô hình (phần của C).

Đọc bảng scan_sessions trong backend/smart_recycle.db, lấy các bản ghi có corrected_material
khác material_code, rồi chép ảnh trong backend/uploads/ sang thư mục theo nhãn đúng:
    ai/data/feedback/giay/12_tu_nhua.jpg
    ai/data/feedback/feedback.csv        danh sách đầy đủ (id, AI đoán, nhãn đúng, ghi chú)

Nhãn sửa chỉ là đề xuất: người dùng cũng có thể chọn sai. Trước khi gộp vào tập train,
nhóm xem từng ảnh và ghi "co" hoặc "khong" vào cột da_duyet của feedback.csv. Chỉ ảnh có
da_duyet = co mới được đưa vào tập train. Lượt AI đoán với độ tin cậy cao (mặc định từ 0,9)
mà vẫn bị sửa được đánh dấu "can_xem_ky" vì dễ là người dùng sửa nhầm hơn.

Chạy lại script nhiều lần được: kết quả duyệt đã ghi được giữ lại theo id.
    - Lượt đã duyệt, nhãn sửa không đổi: giữ nguyên da_duyet.
    - Lượt đã duyệt nhưng người dùng sửa sang nhãn khác: xóa da_duyet để duyệt lại.
    - Lượt không còn bị sửa (người dùng chọn lại đúng nhãn AI): bỏ khỏi danh sách.
Trước khi ghi đè, bản cũ được lưu thành feedback.bak.csv.

Chạy từ thư mục gốc repo:
    py ai/scripts/export_feedback.py
"""
import argparse
import csv
import re
import shutil
import sqlite3
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CSV_NAME = "feedback.csv"
COLUMNS = ["id", "ai_du_doan", "do_tin_cay_ai", "nhan_dung", "can_xem_ky", "da_duyet", "anh", "ghi_chu", "thoi_gian"]
# Ảnh do script này chép ra có tên "<id>_tu_<nhãn AI>.<đuôi>"
OWN_IMAGE = re.compile(r"^(\d+)_tu_[a-z_]+\.[A-Za-z0-9]+$")


def read_reviews(path: Path) -> dict:
    """Đọc kết quả duyệt cũ: {id: (nhan_dung, da_duyet)}.

    Chịu được file đã mở và lưu lại bằng Excel: Excel tiếng Việt có thể đổi dấu phân cách
    thành ";" và đổi bảng mã. Các cột cần đọc (id, nhan_dung, da_duyet) đều là chữ không dấu.
    """
    if not path.is_file():
        return {}
    text = path.read_bytes().decode("utf-8-sig", errors="replace")
    lines = text.splitlines()
    if not lines:
        return {}
    delim = ";" if lines[0].count(";") > lines[0].count(",") else ","
    reviews = {}
    for row in csv.DictReader(lines, delimiter=delim):
        sid = (row.get("id") or "").strip()
        if sid.isdigit():
            reviews[int(sid)] = ((row.get("nhan_dung") or "").strip(), (row.get("da_duyet") or "").strip())
    return reviews


def main():
    ap = argparse.ArgumentParser(description="Xuất ảnh người dùng đã sửa nhãn")
    ap.add_argument("--db", default=str(ROOT / "backend" / "smart_recycle.db"))
    ap.add_argument("--uploads", default=str(ROOT / "backend" / "uploads"))
    ap.add_argument("--out", default=str(ROOT / "ai" / "data" / "feedback"))
    ap.add_argument("--nghi-ngo", type=float, default=0.9,
                    help="độ tin cậy của AI từ mức này trở lên mà vẫn bị sửa thì đánh dấu cần xem kỹ")
    args = ap.parse_args()

    db, uploads, out = Path(args.db), Path(args.uploads), Path(args.out)
    if not db.is_file():
        raise SystemExit(f"Không thấy CSDL: {db}")

    con = sqlite3.connect(db)
    cols = {r[1] for r in con.execute("PRAGMA table_info(scan_sessions)")}
    note_col = "note" if "note" in cols else "NULL"
    rows = con.execute(
        f"SELECT id, material_code, corrected_material, image_path, {note_col}, created_at, confidence "
        "FROM scan_sessions WHERE corrected_material IS NOT NULL AND corrected_material != material_code "
        "ORDER BY confidence DESC, id"
    ).fetchall()
    con.close()

    out.mkdir(parents=True, exist_ok=True)
    csv_path = out / CSV_NAME
    old = read_reviews(csv_path)

    pairs, copied, missing, suspect = Counter(), 0, [], 0
    kept, reset = 0, []
    expected = set()
    records = []
    for sid, pred, true, image, note, created, conf in rows:
        pairs[(pred, true)] += 1
        flag = conf is not None and conf >= args.nghi_ngo
        suspect += flag

        # Giữ kết quả duyệt cũ nếu nhãn sửa vẫn như lúc duyệt
        review = ""
        if sid in old:
            old_true, old_review = old[sid]
            if old_review and old_true == true:
                review = old_review
                kept += 1
            elif old_review:
                reset.append(sid)

        dest = ""
        src = uploads / image if image else None
        if src and src.is_file():
            (out / true).mkdir(exist_ok=True)
            dst = out / true / f"{sid}_tu_{pred}{src.suffix}"
            shutil.copy2(src, dst)
            dest = str(dst.relative_to(out))
            expected.add(dst.resolve())
            copied += 1
        else:
            missing.append(sid)
        records.append([sid, pred, f"{conf:.4f}" if conf is not None else "", true,
                        "co" if flag else "", review, dest, note or "", created])

    dropped = sorted(set(old) - {r[0] for r in records})

    # Ghi ra file tạm rồi mới thay, để lỗi giữa chừng không làm mất file cũ
    tmp = out / (CSV_NAME + ".tmp")
    with open(tmp, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh)
        w.writerow(COLUMNS)
        w.writerows(records)
    try:
        if csv_path.is_file():
            shutil.copy2(csv_path, out / "feedback.bak.csv")
        tmp.replace(csv_path)
    except PermissionError:
        tmp.unlink(missing_ok=True)
        raise SystemExit(f"Không ghi được {csv_path}. Hãy đóng file này trong Excel rồi chạy lại.")

    # Dọn ảnh cũ do script chép ra mà không còn đúng (lượt bỏ sửa, hoặc đã sửa sang nhãn khác)
    removed = 0
    for f in out.glob("*/*"):
        if f.is_file() and OWN_IMAGE.match(f.name) and f.resolve() not in expected:
            f.unlink()
            removed += 1

    print(f"{len(rows)} lượt sửa nhãn, đã chép {copied} ảnh vào {out}")
    for (pred, true), c in pairs.most_common():
        print(f"  AI đoán {pred} -> đúng là {true}: {c}")
    if suspect:
        print(f"{suspect} lượt AI đoán với độ tin cậy từ {args.nghi_ngo:.0%} trở lên vẫn bị sửa: cần xem kỹ (cột can_xem_ky).")
    if old:
        print(f"Giữ lại kết quả duyệt của {kept} lượt từ lần xuất trước.")
    if reset:
        print("Các lượt đã đổi nhãn sửa sau khi duyệt, cần duyệt lại:", ", ".join(map(str, reset)))
    if dropped:
        print("Các lượt không còn bị sửa, đã bỏ khỏi danh sách:", ", ".join(map(str, dropped)))
    if removed:
        print(f"Đã xóa {removed} ảnh cũ không còn dùng.")
    print("Nhãn sửa chỉ là đề xuất. Xem ảnh và điền cột da_duyet (co/khong) trong feedback.csv; "
          "chỉ ảnh có da_duyet = co mới đưa vào tập train.")
    if missing:
        print("Không tìm thấy ảnh của các lượt:", ", ".join(map(str, missing)))


if __name__ == "__main__":
    main()
