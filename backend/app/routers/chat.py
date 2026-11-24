"""Router F3 (/chat) của B - chatbot hỏi đáp phân loại rác (RAG).

Tìm đoạn tri thức gần nhất (services/rag.py), rồi nhờ LLM viết câu trả lời (services/llm.py).
Câu trả lời gửi dần dạng text (stream); nhãn tài liệu đã dùng nằm ở header X-Sources.
"""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, StringConstraints
from sqlalchemy.orm import Session

from app.database import SessionLocal, get_db
from app.models import ChatMessage, User
from app.security import get_optional_user
from app.services.llm import generate
from app.services.rag import search

router = APIRouter(prefix="/chat", tags=["F3 - Chatbot"])

MIN_SCORE = 0.5  # từ thử nghiệm bge-m3: câu không có trong tài liệu < 0.47, câu đúng >= 0.54
NO_ANSWER = "Hệ thống chưa có hướng dẫn cho loại rác này. Bạn hãy chụp ảnh để hệ thống nhận diện."


class ChatIn(BaseModel):
    message: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]


@router.post("")
def chat(
    body: ChatIn,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
):
    try:
        hits = [h for h in search(body.message) if h["score"] >= MIN_SCORE]
    except Exception:  # Ollama chưa chạy hoặc thiếu mô hình embedding
        raise HTTPException(503, "Chatbot tạm thời không hoạt động")

    user_id = user.id if user else None
    db.add(ChatMessage(user_id=user_id, role="user", content=body.message))
    db.commit()
    return StreamingResponse(
        stream_answer(body.message, hits, user_id),
        media_type="text/plain; charset=utf-8",
        headers={"X-Sources": ",".join(h["label"] for h in hits)},
    )


def stream_answer(question: str, hits: list[dict], user_id: int | None):
    """Gửi dần câu trả lời; gửi xong thì lưu cả câu vào chat_messages."""
    parts = []
    try:
        if not hits:
            parts.append(NO_ANSWER)  # không gọi LLM nên không thể bịa
            yield NO_ANSWER
        else:
            for piece in generate(question, [h["text"] for h in hits]):
                parts.append(piece)
                yield piece
    except Exception:
        if not parts:  # LLM lỗi trước khi viết chữ nào: gửi tài liệu tìm được thay vì báo lỗi
            fallback = "\n\n".join(h["text"] for h in hits)
            parts.append(fallback)
            yield fallback
    finally:
        # Phiên db của Depends có thể đã đóng khi đang stream, nên mở phiên mới để lưu
        with SessionLocal() as db:
            db.add(ChatMessage(user_id=user_id, role="assistant", content="".join(parts).strip()))
            db.commit()