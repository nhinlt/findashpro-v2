# core/llm_client.py
"""
Trợ lý AI (Groq).

Hai lỗi đã sửa:
  1. Comment ở pages/8 ghi "Gửi cho Gemini" trong khi client là Groq.
  2. Trợ lý KHÔNG được cấp bất kỳ dữ liệu nào về mã đang chọn — tiêu đề hiển thị
     mã cổ phiếu nhưng prompt gửi đi không kèm giá, chỉ số hay thống kê nào. Nay có
     tham số context để nhồi số liệu thật vào system prompt.
"""
from __future__ import annotations

import streamlit as st

from utils.logger import get_logger

log = get_logger("llm")

MODEL = "openai/gpt-oss-120b"

SYSTEM_PROMPT = """Bạn là chuyên gia phân tích định lượng (Quant Analyst) hỗ trợ sinh viên
làm đồ án Financial Dashboard về thị trường chứng khoán Việt Nam.

QUY ĐỊNH:
- Luôn trả lời bằng TIẾNG VIỆT. Chỉ giữ tiếng Anh cho thuật ngữ (Sharpe Ratio, CAPM, APT, VaR...).
- Ngắn gọn, có cấu trúc, dựa trên dữ liệu.
- Nếu số liệu trong phần NGỮ CẢNH dưới đây không đủ để trả lời, hãy nói thẳng là
  không đủ dữ liệu thay vì suy đoán.
- Không đưa ra khuyến nghị mua/bán cụ thể. Giải thích phương pháp và ý nghĩa con số.
"""


def build_context(ticker: str, snapshot: dict | None = None) -> str:
    """Đóng gói số liệu thật của mã đang chọn thành đoạn ngữ cảnh cho model."""
    if not snapshot:
        return f"NGỮ CẢNH: người dùng đang xem mã {ticker}. Chưa tải được số liệu."
    lines = [f"NGỮ CẢNH — số liệu thật của mã {ticker}:"]
    lines += [f"- {k}: {v}" for k, v in snapshot.items()]
    return "\n".join(lines)


def get_ai_response(messages: list, context: str = "") -> tuple[str, bool]:
    """
    Trả về (nội dung, thành công).

    Cờ `thành công` để trang UI KHÔNG lưu chuỗi lỗi vào lịch sử chat. Bản cũ lưu
    thông báo lỗi như một câu trả lời của assistant rồi gửi lại cho model ở lượt
    sau, làm bẩn ngữ cảnh hội thoại.
    """
    try:
        from groq import Groq
    except ImportError:
        return "Chưa cài thư viện `groq`. Chạy: pip install groq", False

    try:
        api_key = st.secrets["GROQ_API_KEY"]
    except Exception:                              # noqa: BLE001
        return ("Chưa cấu hình GROQ_API_KEY. Tạo file `.streamlit/secrets.toml` với nội dung:\n\n"
                '```toml\nGROQ_API_KEY = "gsk_..."\n```'), False

    payload = [{"role": "system", "content": SYSTEM_PROMPT + "\n\n" + context}]
    payload += [{"role": m["role"], "content": m["content"]} for m in messages]

    try:
        completion = Groq(api_key=api_key).chat.completions.create(
            messages=payload, model=MODEL, temperature=0.2, max_tokens=2048,
        )
        return completion.choices[0].message.content, True
    except Exception as exc:                       # noqa: BLE001
        log.error("Groq API: %s", exc)
        return f"Không gọi được Groq API: {exc}", False
