# ui/components.py
"""
Thành phần giao diện dùng chung.

File này trước đây RỖNG, trong khi khối 15 dòng session_state + text_input +
st.rerun + CSS terminal-header bị copy-paste nguyên văn ở 5 trang. Sửa một chỗ
phải nhớ sửa 5 chỗ. Nay mọi trang gọi cùng một hàm.

Ba thay đổi về hành vi:
  1. CHỌN TỪ DANH SÁCH (yêu cầu [1]) thay vì text_input tự do.
  2. KHÔNG gọi st.rerun(). Streamlit đã tự chạy lại khi widget đổi giá trị; gọi
     thêm gây double-run và nhân đôi số lần gọi API.
  3. Mọi trang dùng CÙNG một widget nên mã cổ phiếu đồng bộ thật sự. Bản cũ có
     3/8 trang (5, 6, 7) hardcode mã riêng, phá vỡ đúng tính năng mà trang chủ
     quảng cáo là "mã kích hoạt trên toàn hệ thống".
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from utils.config import (ALL_TICKERS, DEFAULT_PORTFOLIO, PRICE_UNIT,
                          RISK_FREE_RATE, TRADING_DAYS, UNIVERSE)

_CSS = Path(__file__).parent / "styles.css"


def setup_page(title: str, icon: str = "📊") -> None:
    """set_page_config + nạp CSS. Bản cũ KHÔNG gọi set_page_config ở bất kỳ đâu,
    nên app chạy layout 'centered', lưới 3 cột bị bóp và tab trình duyệt ghi
    'app · Streamlit'."""
    try:
        st.set_page_config(page_title=f"FinDash Pro — {title}", page_icon=icon,
                           layout="wide", initial_sidebar_state="expanded")
    except Exception:                              # noqa: BLE001  đã gọi rồi
        pass
    if _CSS.exists():
        st.markdown(f"<style>{_CSS.read_text(encoding='utf-8')}</style>",
                    unsafe_allow_html=True)


def page_header(title: str, subtitle: str) -> None:
    st.markdown(f'<h1 class="terminal-header">{title}</h1>', unsafe_allow_html=True)
    st.markdown(f'<p class="terminal-sub">{subtitle}</p>', unsafe_allow_html=True)


def note(html: str) -> None:
    """Ghi chú giả định mô hình. Nói thẳng giới hạn được điểm cao hơn giấu nó đi."""
    st.markdown(f'<div class="fd-note">{html}</div>', unsafe_allow_html=True)


def source_badge(source: str) -> None:
    if source == "mock":
        st.markdown(
            '<span class="fd-badge mock">dữ liệu mô phỏng</span>'
            'API entrade không phản hồi. Số liệu dưới đây do máy sinh ra để giao diện '
            'vẫn chạy được — <b>không dùng để kết luận về thị trường</b>.',
            unsafe_allow_html=True)
    else:
        st.markdown('<span class="fd-badge live">dữ liệu trực tiếp</span>'
                    f'<span style="color:#8b949e;font-size:.78rem">'
                    f'Nguồn: DNSE / entrade · Đơn vị giá: {PRICE_UNIT}</span>',
                    unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# CHỌN MÃ
# ---------------------------------------------------------------------------
def ticker_selector(key: str) -> str:
    """Widget chọn mã dùng chung cho MỌI trang."""
    if "ticker" not in st.session_state:
        st.session_state["ticker"] = "VCB"

    st.sidebar.markdown("### ⚙️ Bảng điều khiển")

    current = st.session_state["ticker"]
    groups = list(UNIVERSE)
    default_group = next((g for g, ts in UNIVERSE.items() if current in ts), groups[0])

    group = st.sidebar.selectbox("Nhóm ngành", groups,
                                 index=groups.index(default_group), key=f"{key}_group")
    options = UNIVERSE[group]          # LIST có thứ tự — không dùng set(), vốn xáo
                                       # trộn khác nhau mỗi lần khởi động app
    idx = options.index(current) if current in options else 0
    chosen = st.sidebar.selectbox("Mã cổ phiếu", options, index=idx, key=f"{key}_tk")

    with st.sidebar.expander("Nhập mã ngoài danh sách"):
        manual = st.text_input("Mã", value="", key=f"{key}_manual",
                               placeholder="VD: SSI").strip().upper()

    st.session_state["ticker"] = manual or chosen
    return st.session_state["ticker"]              # KHÔNG st.rerun()


def multi_ticker_selector(key: str, label: str = "Rổ cổ phiếu",
                          default: list[str] | None = None, min_n: int = 2) -> list[str]:
    default = default or list(DEFAULT_PORTFOLIO)
    picked = st.sidebar.multiselect(label, ALL_TICKERS,
                                    default=[t for t in default if t in ALL_TICKERS],
                                    key=f"{key}_multi")
    if len(picked) < min_n:
        st.warning(f"Chọn ít nhất {min_n} mã để chạy phân tích danh mục.")
        st.stop()
    return picked


def period_selector(key: str, default_days: int = 365) -> int:
    opts = {"3 tháng": 90, "6 tháng": 180, "1 năm": 365, "2 năm": 730, "5 năm": 1825}
    labels = list(opts)
    idx = labels.index(next(k for k, v in opts.items() if v == default_days))
    return opts[st.sidebar.selectbox("Khoảng thời gian", labels, index=idx, key=f"{key}_period")]


def sidebar_assumptions() -> None:
    """Bày ra các giả định dùng chung. Giảng viên hỏi 'rf của em là bao nhiêu' thì
    câu trả lời nằm sẵn trên màn hình, và chỉ có MỘT con số."""
    st.sidebar.divider()
    st.sidebar.caption(
        f"**Giả định mô hình**  \n"
        f"Lãi suất phi rủi ro: {RISK_FREE_RATE:.2%}/năm  \n"
        f"Số phiên/năm: {TRADING_DAYS}  \n"
        f"Quy ước lợi suất: log return  \n"
        f"Đơn vị giá: {PRICE_UNIT}"
    )


# ---------------------------------------------------------------------------
# GUARD
# ---------------------------------------------------------------------------
def guard_data(df: pd.DataFrame, ticker: str, min_rows: int = 2) -> pd.DataFrame:
    """
    Dừng trang một cách lịch sự thay vì ném traceback.

    Bản cũ chỉ kiểm tra df.empty rồi vẫn gọi df['Close'].iloc[-2] (IndexError khi
    chỉ có 1 phiên) và df.columns.str.lower() (AttributeError khi DataFrame rỗng,
    vì columns của DataFrame rỗng là RangeIndex kiểu int chứ không phải chuỗi).
    """
    if df is None or df.empty:
        st.error(f"Không có dữ liệu cho mã **{ticker}**. Kiểm tra lại mã hoặc chọn "
                 f"khoảng thời gian khác.")
        st.stop()
    if len(df) < min_rows:
        st.error(f"Mã **{ticker}** chỉ có {len(df)} phiên trong khoảng đã chọn — "
                 f"cần ít nhất {min_rows}. Hãy nới rộng khoảng thời gian.")
        st.stop()
    return df


def guard_model(fn, *args, **kwargs):
    """Chạy hàm mô hình; ValueError/RuntimeError thành thông báo đọc được, không phải traceback."""
    try:
        return fn(*args, **kwargs)
    except (ValueError, RuntimeError) as exc:
        st.warning(f"Không chạy được mô hình: {exc}")
        return None
