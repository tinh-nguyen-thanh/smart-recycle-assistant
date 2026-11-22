from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from datetime import datetime, timezone

DATABASE_URL = "sqlite:///./smart_recycle.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})


@event.listens_for(engine, "connect")
def _bat_khoa_ngoai(dbapi_conn, _record):
    dbapi_conn.execute("PRAGMA foreign_keys=ON") #SQLite mặc định tắt kiểm tra khóa ngoại


SessionLocal = sessionmaker(bind=engine, autoflush=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def utcnow():
    return datetime.now(timezone.utc)

