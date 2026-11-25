"""Xuất các lượt quét người dùng đã sửa nhãn thành bộ ảnh để huấn luyện lại mô hình (phần của C).

Đọc bảng scan_sessions trong backend/smart_recycle.db, lấy các bản ghi có corrected_material
khác material_code, rồi chép ảnh trong backend/uploads/ sang thư mục theo nhãn đúng:
    ai/data/feedback/giay/12_tu_nhua.jpg
    ai/data/feedback/feedback.csv        danh sách đầy đủ (id, AI đoán, nhãn đúng, ghi chú)

Nhãn sửa chỉ là đề xuất: người dùng cũng có thể chọn sai. Trước khi gộp vào tập train,
nhóm xem lại từng ảnh trong feedback.csv. Lượt AI đoán với độ tin cậy cao (mặc định từ 0,9)
mà vẫn bị sửa được đánh dấu "can_xem_ky" vì dễ là người dùng sửa nhầm hơn.

Chạy từ thư mục gốc repo:
    py ai/scripts/export_feedback.py
"""
import argparse
import csv
import shutil
import sqlite3
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


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
    pairs, copied, missing, suspect = Counter(), 0, [], 0
    with open(out / "feedback.csv", "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh)
        w.writerow(["id", "ai_du_doan", "do_tin_cay_ai", "nhan_dung", "can_xem_ky", "da_duyet", "anh", "ghi_chu", "thoi_gian"])
        for sid, pred, true, image, note, created, conf in rows:
            pairs[(pred, true)] += 1
            flag = conf is not None and conf >= args.nghi_ngo
            suspect += flag
            dest = ""
            src = uploads / image if image else None
            if src and src.is_file():
                (out / true).mkdir(exist_ok=True)
                dst = out / true / f"{sid}_tu_{pred}{src.suffix}"
                shutil.copy2(src, dst)
                dest = str(dst.relative_to(out))
                copied += 1
            else:
                missing.append(sid)
            # Cột da_duyet để trống: người duyệt ghi "co" hoặc "khong" sau khi xem ảnh
            w.writerow([sid, pred, f"{conf:.4f}" if conf is not None else "", true,
                        "co" if flag else "", "", dest, note or "", created])

    print(f"{len(rows)} lượt sửa nhãn, đã chép {copied} ảnh vào {out}")
    for (pred, true), c in pairs.most_common():
        print(f"  AI đoán {pred} -> đúng là {true}: {c}")
    if suspect:
        print(f"{suspect} lượt AI đoán với độ tin cậy từ {args.nghi_ngo:.0%} trở lên vẫn bị sửa: cần xem kỹ (cột can_xem_ky).")
    print("Nhãn sửa chỉ là đề xuất. Xem ảnh và điền cột da_duyet trong feedback.csv trước khi đưa vào tập train.")
    if missing:
        print("Không tìm thấy ảnh của các lượt:", ", ".join(map(str, missing)))


if __name__ == "__main__":
    main()
