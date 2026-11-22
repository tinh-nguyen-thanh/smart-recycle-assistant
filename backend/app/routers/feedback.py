"""Router F7 (/feedback) của C - lưu nhãn người dùng sửa khi bấm "Kết quả sai?".

Ghi vào cột corrected_material của bảng scan_sessions (của B).
Ghi chú (note) chỉ được lưu khi bảng đã có cột note; trước đó vẫn trả về nhưng không lưu.
"""
import json
from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.scan import ScanSession

router = APIRouter(tags=["F7 - Sửa nhãn"])

# backend/app/routers/feedback.py -> parents[3] là thư mục gốc của repo
LABELS_PATH = Path(__file__).resolve().parents[3] / "ai" / "models" / "labels.json"
HAS_NOTE = hasattr(ScanSession, "note")  # True khi B đã thêm cột note


@lru_cache(maxsize=1)
def valid_labels() -> frozenset:
    # Nhãn hợp lệ lấy từ labels.json của mô hình, không ghi cứng
    return frozenset(json.loads(LABELS_PATH.read_text(encoding="utf-8")))


class FeedbackIn(BaseModel):
    id: int
    label: str
    note: str | None = Field(default=None, max_length=200)


def apply_feedback(scan, label: str, note: str | None) -> dict:
    """Cập nhật bản ghi theo nhãn người dùng chọn và trả về kết quả theo docs/api.md."""
    note = (note or "").strip() or None
    corrected = label != scan.material_code
    # Chọn lại đúng nhãn AI đã đoán thì coi như bỏ sửa
    scan.corrected_material = label if corrected else None
    if not corrected:
        note = None
    if HAS_NOTE:
        scan.note = note
    result = {
        "id": scan.id,
        "original": scan.material_code,
        "label": label,
        "corrected": corrected,
    }
    if note:
        result["note"] = note
    return result


@router.post("/feedback")
def feedback(body: FeedbackIn, db: Session = Depends(get_db)):
    if body.label not in valid_labels():
        raise HTTPException(status_code=400, detail=f"Nhãn '{body.label}' không có trong labels.json")
    scan = db.get(ScanSession, body.id)
    if scan is None:
        raise HTTPException(status_code=404, detail=f"Không có lượt quét id={body.id}")
    result = apply_feedback(scan, body.label, body.note)
    db.commit()
    return result
