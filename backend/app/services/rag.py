"""F3 (B) - RAG: tìm mục tri thức gần nhất với câu hỏi chatbot.

Kho tri thức dùng chung với F2: backend/app/data/f2_knowledge.json (mỗi nhãn là một đoạn).
"""
from functools import lru_cache

import numpy as np
import ollama

from app.routers.guide import load_knowledge

# EMBED_MODEL = "qwen3-embedding:0.6b"
EMBED_MODEL = "bge-m3"


def build_chunks() -> list[dict]:
    """Mỗi nhãn rác thành một đoạn văn bản để tìm kiếm."""
    data = load_knowledge()
    chunks = []
    for label, item in data["labels"].items():
        group = data["groups"][item["group"]]
        guide = item["guide"]
        lines = [
            f"{item['name']} - nhóm {group['name']}.",
            f"Ví dụ: {', '.join(guide['examples'])}.",
            guide["summary"],
            "Các bước: " + " ".join(guide["steps"]),
            "Không nên: " + " ".join(guide["dont"]),
        ]
        if item["warning"]:
            lines.append(item["warning"])
        chunks.append({"label": label, "text": "\n".join(lines)})
    return chunks


def embed(texts: list[str]) -> np.ndarray:
    """Đổi văn bản thành vector, chuẩn hóa độ dài về 1 để tích vô hướng = cosine."""
    vectors = np.array(ollama.embed(model=EMBED_MODEL, input=texts).embeddings)
    return vectors / np.linalg.norm(vectors, axis=1, keepdims=True)


@lru_cache(maxsize=1)
def index():
    """Tính vector cho kho tri thức một lần rồi giữ trong bộ nhớ."""
    chunks = build_chunks()
    return chunks, embed([c["text"] for c in chunks])


def search(question: str, top_k: int = 2) -> list[dict]:
    """Trả về top_k đoạn gần câu hỏi nhất, kèm điểm cosine (càng gần 1 càng giống)."""
    chunks, vectors = index()
    scores = vectors @ embed([question])[0]
    best = np.argsort(scores)[::-1][:top_k]
    return [{**chunks[i], "score": float(scores[i])} for i in best]


if __name__ == "__main__":
    for q in [
        "Hộp pizza dính dầu mỡ có tái chế được không?",
        "Pin điện thoại hỏng bỏ ở đâu?",
        "vo lon bia bo dau",
        "Túi ni lông đựng đồ ăn",
        "Thuốc hết hạn sử dụng",
    ]:
        print(q)
        for hit in search(q):
            print(f"  {hit['score']:.3f}  {hit['label']}")