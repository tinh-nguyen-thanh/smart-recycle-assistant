"""Router F3 (/chat) của B - chatbot hỏi đáp phân loại rác (RAG).

Tìm đoạn tri thức gần nhất (services/rag.py), rồi nhờ LLM viết câu trả lời (services/llm.py).
"""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, StringConstraints
from sqlalchemy.orm import Session

from app.database import get_db
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

    if not hits:
        answer = NO_ANSWER  # không gọi LLM nên không thể bịa
    else:
        try:
            answer = generate(body.message, [h["text"] for h in hits])
        except Exception:  # LLM lỗi: vẫn trả tài liệu tìm được thay vì báo lỗi
            answer = "\n\n".join(h["text"] for h in hits)

    user_id = user.id if user else None
    db.add_all([
        ChatMessage(user_id=user_id, role="user", content=body.message),
        ChatMessage(user_id=user_id, role="assistant", content=answer),
    ])
    db.commit()
    return {"answer": answer, "sources": [h["label"] for h in hits]}