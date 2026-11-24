"""F3 (B) - gọi LLM để viết câu trả lời từ tài liệu tìm được.

Chỉ hàm generate() gọi LLM: muốn đổi nhà cung cấp (ví dụ Gemini) thì chỉ sửa file này.
"""
import ollama

LLM_MODEL = "qwen3:8b"

SYSTEM_PROMPT = (
    "Bạn là trợ lý phân loại rác tại Việt Nam, nói chuyện thân thiện. "
    "Chỉ dựa trên tài liệu được cung cấp. Trả lời 2-4 câu: nói rác thuộc nhóm nào, "
    "bỏ vào đâu, và các bước cần làm trước khi bỏ (nếu tài liệu có). "
    "Nếu tài liệu không có thông tin, nói rõ là hệ thống chưa có hướng dẫn cho loại rác này "
    "và gợi ý người dùng chụp ảnh để hệ thống nhận diện. Không tự bịa thông tin. "
    "Không mở đầu bằng lời chào. Trả lời bằng tiếng Việt."
)


def generate(question: str, docs: list[str]):
    """Gửi câu hỏi kèm tài liệu cho LLM, trả về dần từng mẩu chữ khi LLM viết ra."""
    stream = ollama.chat(
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": "Tài liệu:\n" + "\n\n".join(docs) + f"\n\nCâu hỏi: {question}"},
        ],
        think=False,
        options={"num_ctx": 2048, "temperature": 0},
        stream=True,
    )
    for chunk in stream:
        yield chunk.message.content