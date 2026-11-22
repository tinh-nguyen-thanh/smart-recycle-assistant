from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.database import Base, engine
import app.models  # noqa: F401 (nạp model để create_all thấy các bảng)
from app.routers import feedback, guide, predict

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Smart Recycle Assistant")

UPLOAD_DIR = Path(__file__).resolve().parents[1] / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")
app.include_router(predict.router)
app.include_router(guide.router)
app.include_router(feedback.router)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok"}
