"""Router F6 (/stats) của C - số liệu cho trang thống kê frontend/stats.html.

Đọc từ bảng scan_sessions (của B). Định dạng trả về theo docs/api.md.
Hiện thống kê toàn hệ thống; khi có đăng nhập sẽ lọc theo user_id.
"""
from collections import Counter
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.scan import ScanSession
from app.routers.guide import load_knowledge

router = APIRouter(tags=["F6 - Thống kê"])

# Ngày tính theo giờ Việt Nam (UTC+7). Dùng độ lệch cố định để Windows không cần cài tzdata.
VN_TZ = timezone(timedelta(hours=7))
DAYS = 7


def final_label(row):
    """Nhãn cuối cùng: nhãn người dùng sửa nếu có, ngược lại là nhãn AI đoán."""
    if row.corrected_material and row.corrected_material != row.material_code:
        return row.corrected_material
    return row.material_code


def compute_stats(rows, knowledge: dict, today):
    groups, labels = knowledge["groups"], knowledge["labels"]
    by_group = {k: 0 for k in groups}
    by_label = {k: 0 for k in labels}
    days = Counter()
    pairs = Counter()
    corrected = 0

    for r in rows:
        lb = final_label(r)
        by_label[lb] = by_label.get(lb, 0) + 1
        if lb in labels:
            by_group[labels[lb]["group"]] += 1
        t = r.created_at
        if t is not None:
            if t.tzinfo is None:  # SQLite không lưu múi giờ, giá trị lưu là UTC
                t = t.replace(tzinfo=timezone.utc)
            days[t.astimezone(VN_TZ).date()] += 1
        if lb != r.material_code:
            corrected += 1
            pairs[(r.material_code, lb)] += 1

    by_day = []
    for i in range(DAYS - 1, -1, -1):
        d = today - timedelta(days=i)
        by_day.append({"date": d.isoformat(), "count": days.get(d, 0)})

    corrections = [
        {"from": a, "to": b, "count": n}
        for (a, b), n in sorted(pairs.items(), key=lambda kv: (-kv[1], kv[0]))
    ]
    return {
        "total": len(rows),
        "by_group": by_group,
        "by_label": by_label,
        "corrected": corrected,
        "by_day": by_day,
        "corrections": corrections,
    }


@router.get("/stats")  # TODO: lọc theo user_id khi B xong đăng nhập
def stats(db: Session = Depends(get_db)):
    rows = db.scalars(select(ScanSession)).all()
    today = datetime.now(VN_TZ).date()
    return compute_stats(rows, load_knowledge(), today)
