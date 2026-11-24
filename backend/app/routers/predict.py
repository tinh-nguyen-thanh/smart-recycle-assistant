"""Router F1 (/predict) và F5 (/history) của A - bám theo docs/api.md và bảng scan_sessions của B."""
import io
import json
import uuid
from datetime import timezone
from functools import lru_cache
from pathlib import Path

import numpy as np
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from PIL import Image, UnidentifiedImageError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.scan import ScanSession
from app.models import User
from app.security import get_current_user, get_optional_user

try:
    from app.routers.guide import get_guide  # hàm của C: trả về (group, guide) theo nhãn
except ImportError:  # C chưa đẩy guide.py: dùng bản giả để thử, xóa khi có bản thật
    def get_guide(label):
        return {"id": "tam", "name": label}, {"name": label}

router = APIRouter()

# backend/app/routers/predict.py -> parents[3] là thư mục gốc của repo
ROOT = Path(__file__).resolve().parents[3]
MODEL_PATH = ROOT / "ai" / "models" / "smart_recycle_model.onnx"
LABELS_PATH = ROOT / "ai" / "models" / "labels.json"
UPLOAD_DIR = ROOT / "backend" / "uploads"  # trùng với thư mục mount /uploads trong main.py

IMG_SIZE = (224, 224)
MAX_BYTES = 8 * 1024 * 1024  # ảnh tối đa 8 MB


# ---------- Mô hình: nạp một lần duy nhất ----------
@lru_cache(maxsize=1)
def get_session():
    import onnxruntime as ort  # import muộn để server khởi động nhanh

    return ort.InferenceSession(str(MODEL_PATH), providers=["CPUExecutionProvider"])

@lru_cache(maxsize=1)
def get_labels():
    # Thứ tự lớp lấy từ labels.json, không ghi cứng trong code
    return json.loads(LABELS_PATH.read_text(encoding="utf-8"))


def classify(img: Image.Image):
    """Trả về (nhãn, độ tin cậy). Mô hình nhận ảnh 224x224, pixel 0-255, không cần chuẩn hóa thêm."""
    # BILINEAR cho đúng với lúc huấn luyện (Keras resize kiểu bilinear)
    arr = np.asarray(img.convert("RGB").resize(IMG_SIZE, Image.BILINEAR), dtype="float32")
    sess = get_session()
    input_name = sess.get_inputs()[0].name
    probs = sess.run(None, {input_name: arr[None, ...]})[0][0]
    idx = int(np.argmax(probs))
    return get_labels()[idx], float(probs[idx])


# ---------- POST /predict ----------
@router.post("/predict")
def predict(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
):
    # Dùng def (không phải async def) để FastAPI chạy trong thread riêng, không chặn server khi mô hình suy luận
    if not (file.content_type or "").startswith("image/"):
        raise HTTPException(status_code=400, detail="Tệp tải lên không phải ảnh")
    data = file.file.read()
    if len(data) > MAX_BYTES:
        raise HTTPException(status_code=400, detail="Ảnh quá lớn (tối đa 8 MB)")
    try:
        img = Image.open(io.BytesIO(data))
        img.load()
    except (UnidentifiedImageError, OSError):
        raise HTTPException(status_code=400, detail="Không đọc được ảnh")

    label, confidence = classify(img)

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    image_name = f"{uuid.uuid4().hex}.jpg"
    img.convert("RGB").save(UPLOAD_DIR / image_name, quality=90)

    scan = ScanSession(
        user_id=user.id if user else None,  
        scan_type="image",
        material_code=label,
        confidence=confidence,
        image_path=image_name,
    )
    db.add(scan)
    db.commit()
    db.refresh(scan)

    group, guide = get_guide(label)
    return {
        "id": scan.id,
        "label": label,
        "confidence": round(confidence, 4),
        "group": group,
        "guide": guide,
    }


# ---------- GET /history ----------
@router.get("/history")  
def history(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    rows = db.scalars(
        select(ScanSession)
        .where(ScanSession.user_id == user.id)
        .order_by(ScanSession.id.desc())
        .limit(limit)
        .offset(offset)
    ).all()

    items = []
    for r in rows:
        corrected = r.corrected_material is not None and r.corrected_material != r.material_code
        t = r.created_at
        if t.tzinfo is None:  # SQLite không lưu múi giờ, giá trị lưu là UTC
            t = t.replace(tzinfo=timezone.utc)
        item = {
            "id": r.id,
            # Theo api.md: label là nhãn cuối cùng (sau khi người dùng sửa), original là nhãn AI đoán
            "label": r.corrected_material if corrected else r.material_code,
            "confidence": r.confidence,
            "time": t.isoformat(timespec="seconds"),
            "image": f"/uploads/{r.image_path}" if r.image_path else None,
        }
        if corrected:
            item["corrected"] = True
            item["original"] = r.material_code
        items.append(item)
    return items
