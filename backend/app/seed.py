import json
from pathlib import Path

from app.database import SessionLocal, Base, engine
from app.models import WasteGroup, Material

# Cùng file với routers/guide.py của C: một nguồn tri thức duy nhất
KNOWLEDGE = Path(__file__).resolve().parent / "data" / "f2_knowledge.json"


def seed():
    Base.metadata.create_all(bind=engine)
    data = json.loads(KNOWLEDGE.read_text(encoding="utf-8"))
    db = SessionLocal()
    try:
        for code, g in data["groups"].items():
            db.merge(WasteGroup(code=code, name=g["name"], color=g["color"]))
        db.flush()
        for code, m in data["labels"].items():
            db.merge(Material(code=code, name=m["name"], group_code=m["group"]))
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()
    print("Đã nạp dữ liệu mẫu")