"""Xuất các lượt quét người dùng đã sửa nhãn thành bộ ảnh để huấn luyện lại mô hình (phần của C).

Đọc bảng scan_sessions trong backend/smart_recycle.db, lấy các bản ghi có corrected_material
khác material_code, rồi chép ảnh trong backend/uploads/ sang thư mục theo nhãn đúng:
    ai/data/feedback/giay/12_tu_nhua.jpg
    ai/data/feedback/feedback.csv        danh sách đầy đủ (id, AI đoán, nhãn đúng, ghi chú)

A gộp thư mục này vào tập train trên Colab rồi huấn luyện lại.

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
    args = ap.parse_args()

    db, uploads, out = Path(args.db), Path(args.uploads), Path(args.out)
    if not db.is_file():
        raise SystemExit(f"Không thấy CSDL: {db}")

    con = sqlite3.connect(db)
    cols = {r[1] for r in con.execute("PRAGMA table_info(scan_sessions)")}
    note_col = "note" if "note" in cols else "NULL"
    rows = con.execute(
        f"SELECT id, material_code, corrected_material, image_path, {note_col}, created_at "
        "FROM scan_sessions WHERE corrected_material IS NOT NULL AND corrected_material != material_code "
        "ORDER BY id"
    ).fetchall()
    con.close()

    out.mkdir(parents=True, exist_ok=True)
    pairs, copied, missing = Counter(), 0, []
    with open(out / "feedback.csv", "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh)
        w.writerow(["id", "ai_du_doan", "nhan_dung", "anh", "ghi_chu", "thoi_gian"])
        for sid, pred, true, image, note, created in rows:
            pairs[(pred, true)] += 1
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
            w.writerow([sid, pred, true, dest, note or "", created])

    print(f"{len(rows)} lượt sửa nhãn, đã chép {copied} ảnh vào {out}")
    for (pred, true), c in pairs.most_common():
        print(f"  AI đoán {pred} -> đúng là {true}: {c}")
    if missing:
        print("Không tìm thấy ảnh của các lượt:", ", ".join(map(str, missing)))


if __name__ == "__main__":
    main()
