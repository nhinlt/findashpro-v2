# pages/1_📊_Summary.py — yêu cầu [1]: tóm tắt thông tin một cổ phiếu chọn từ danh sách
import plotly.graph_objects as go
import streamlit as st

from data.dnse_client import get_ohlcv
from data.yfinance_client import fetch_company_profile
from ui.charts import apply_theme
from ui.components import (guard_data, note, page_header, period_selector,
                           setup_page, sidebar_assumptions, source_badge, ticker_selector)
from utils.config import ACCENT, PRICE_UNIT


def render_summary_page() -> None:
    setup_page("Summary", "📊")
    ticker = ticker_selector("summary")
    days = period_selector("summary", 365)
    sidebar_assumptions()

    page_header(f"Tổng quan giao dịch · {ticker}",
                "Hồ sơ doanh nghiệp, biến động giá, thanh khoản và biên độ 52 tuần")

    with st.spinner(f"Đang tải dữ liệu {ticker}…"):
        df, source = get_ohlcv(ticker, days)
    guard_data(df, ticker, min_rows=2)          # chặn IndexError của iloc[-2]
    source_badge(source)

    # ---------------- KPI ----------------
    price, prev = float(df["close"].iloc[-1]), float(df["close"].iloc[-2])
    change = price - prev
    pct = change / prev * 100 if prev else 0.0

    win = df.tail(252)
    high52, low52 = float(win["high"].max()), float(win["low"].min())
    pos52 = (price - low52) / (high52 - low52) * 100 if high52 > low52 else 50.0

    vol = float(df["volume"].iloc[-1])
    avg20 = float(df["volume"].tail(20).mean())
    # avg20 == 0 (mã bị đình chỉ giao dịch) từng cho ra inf/nan hiển thị lên metric
    vol_delta = f"{(vol - avg20) / avg20 * 100:+.1f}% so với TB 20 phiên" if avg20 > 0 else "Chưa đủ dữ liệu"

    st.markdown("##### Chỉ số phiên gần nhất")
    with st.container(border=True):
        c = st.columns(5)
        c[0].metric(f"Giá đóng cửa ({PRICE_UNIT})", f"{price:,.2f}",
                    delta=f"{change:+,.2f} ({pct:+.2f}%)")
        c[1].metric("Khối lượng", f"{vol:,.0f}", delta=vol_delta)
        c[2].metric("Đỉnh 52 tuần", f"{high52:,.2f}")
        c[3].metric("Đáy 52 tuần", f"{low52:,.2f}")
        c[4].metric("Vị trí trong biên độ", f"{pos52:.0f}%",
                    help="0% = đáy 52 tuần, 100% = đỉnh 52 tuần")

    st.caption(f"Phiên gần nhất: {df.index[-1]:%d/%m/%Y} · {len(df):,} phiên trong khoảng đã chọn")

    # ---------------- Hồ sơ doanh nghiệp ----------------
    st.markdown("##### Hồ sơ doanh nghiệp")
    profile = fetch_company_profile(ticker)
    fields = {k: v for k, v in profile.items() if k != "Mô tả" and v}
    if fields:
        cols = st.columns(4)
        for i, (k, v) in enumerate(fields.items()):
            shown = f"{v:,.0f}" if isinstance(v, (int, float)) else str(v)
            cols[i % 4].markdown(f"**{k}**  \n{shown}")
        if profile.get("Mô tả"):
            with st.expander("Mô tả hoạt động kinh doanh"):
                st.write(profile["Mô tả"])
    else:
        note("Yahoo Finance <b>không trả về hồ sơ</b> cho mã này. Độ phủ dữ liệu cơ bản "
             "của Yahoo với cổ phiếu niêm yết tại Việt Nam rất hạn chế — đây là dữ liệu "
             "thiếu, không phải doanh nghiệp không tồn tại.")

    # ---------------- Diễn biến giá ----------------
    st.markdown("##### Diễn biến giá")
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df.index, y=df["close"], mode="lines", name="Đóng cửa",
                             line=dict(color=ACCENT, width=1.8), fill="tozeroy",
                             fillcolor="rgba(255,153,0,0.10)"))
    fig.add_hline(y=high52, line_dash="dot", line_color="#8b949e", opacity=0.6,
                  annotation_text="Đỉnh 52T")
    fig.add_hline(y=low52, line_dash="dot", line_color="#8b949e", opacity=0.6,
                  annotation_text="Đáy 52T")
    fig.update_yaxes(title_text=f"Giá ({PRICE_UNIT})")
    st.plotly_chart(apply_theme(fig, 420), use_container_width=True)


if __name__ == "__main__":
    render_summary_page()
