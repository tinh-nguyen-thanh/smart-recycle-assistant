from datetime import datetime

from sqlalchemy import String, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, utcnow


class ScanSession(Base):
    __tablename__ = "scan_sessions"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    scan_type: Mapped[str] = mapped_column(String(20), default="image")
    material_code: Mapped[str] = mapped_column(ForeignKey("materials.code"))
    confidence: Mapped[float]
    contents_state: Mapped[str | None] = mapped_column(String(20))
    image_path: Mapped[str | None] = mapped_column(String(255))
    corrected_material: Mapped[str | None] = mapped_column(ForeignKey("materials.code"))
    note: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow) 