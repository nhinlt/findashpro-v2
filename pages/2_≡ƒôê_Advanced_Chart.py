# pages/2_📈_Advanced_Chart.py — yêu cầu [2]: biến động giá/khối lượng, LẤY MẪU, dạng biểu đồ
import plotly.graph_objects as go
import streamlit as st

from core.indicators import calculate_bollinger, calculate_ema, calculate_rsi, calculate_sma
from data.dnse_client import SAMPLING, get_ohlcv, resample_ohlcv
from ui.charts import apply_theme, create_price_volume_chart
from ui.components import (guard_data, note, page_header, period_selector,
                           setup_page, sidebar_assumptions, source_badge, ticker_selector)


def render_advanced_chart() -> None:
    setup_page("Advanced Chart", "📈")
    ticker = ticker_selector("chart")
    days = period_selector("chart", 365)
    sidebar_assumptions()

    page_header(f"Biểu đồ kỹ thuật · {ticker}",
                "Đa khung lấy mẫu, ba dạng biểu đồ và các chỉ báo chồng lớp")

    with st.container(border=True):
        c1, c2, c3, c4 = st.columns(4)
        freq = c1.selectbox("Lấy mẫu", list(SAMPLING), index=0,
                            help="Dữ liệu ngày được gộp phía ứng dụng theo quy tắc OHLCV")
        plot_type = c2.selectbox("Dạng biểu đồ", ["Candle", "Line", "OHLC"])
        ma_window = c3.number_input("Chu kỳ MA", min_value=5, max_value=200, value=20, step=5)
        overlay_choice = c4.multiselect("Chỉ báo", ["SMA", "EMA", "Bollinger", "RSI"],
                                        default=["SMA"])

    with st.spinner(f"Đang tải dữ liệu {ticker}…"):
        df_daily, source = get_ohlcv(ticker, days)
    guard_data(df_daily, ticker, min_rows=2)
    source_badge(source)

    # Lấy mẫu TRƯỚC khi tính chỉ báo: MA 20 trên dữ liệu tuần là 20 TUẦN, không phải 20 ngày
    df = resample_ohlcv(df_daily, freq)
    unit = {"Ngày": "phiên", "Tuần": "tuần", "Tháng": "tháng", "Quý": "quý"}[freq]
    guard_data(df, ticker, min_rows=2)

    if len(df) < ma_window:
        note(f"Chu kỳ MA ({ma_window}) <b>lớn hơn số quan sát sau khi lấy mẫu</b> "
             f"({len(df)} {unit}). Đường trung bình sẽ rỗng — hãy giảm chu kỳ hoặc "
             f"nới rộng khoảng thời gian.")

    overlays = {}
    if "SMA" in overlay_choice:
        overlays[f"SMA {ma_window} {unit}"] = calculate_sma(df, ma_window, "close")
    if "EMA" in overlay_choice:
        overlays[f"EMA {ma_window} {unit}"] = calculate_ema(df, ma_window, "close")
    if "Bollinger" in overlay_choice:
        up, mid, lo = calculate_bollinger(df["close"], min(20, max(len(df) - 1, 2)))
        overlays["Bollinger trên"] = up
        overlays["Bollinger dưới"] = lo

    st.plotly_chart(create_price_volume_chart(df, ticker, plot_type, overlays),
                    use_container_width=True)

    if "RSI" in overlay_choice:
        st.markdown("##### RSI (14)")
        rsi = calculate_rsi(df["close"], 14)
        fig = go.Figure(go.Scatter(x=df.index, y=rsi, mode="lines", name="RSI",
                                   line=dict(color="#ff9900", width=1.5)))
        for lvl, txt in ((70, "Quá mua"), (30, "Quá bán")):
            fig.add_hline(y=lvl, line_dash="dot", line_color="#8b949e",
                          opacity=0.6, annotation_text=txt)
        fig.update_yaxes(range=[0, 100])
        st.plotly_chart(apply_theme(fig, 260), use_container_width=True)
        note("RSI tính theo phương pháp làm mượt lũy thừa của <b>Wilder (1978)</b> với "
             "alpha = 1/14. Bản trước dùng trung bình động đơn giản 14 kỳ rồi vẫn gọi là "
             "RSI — hai cách lệch nhau rõ rệt trong 30–50 kỳ đầu.")

    note(f"Đang hiển thị <b>{len(df):,} {unit}</b> gộp từ {len(df_daily):,} phiên. "
         f"Quy tắc gộp: open = phiên đầu kỳ, high/low = max/min cả kỳ, close = phiên cuối kỳ, "
         f"volume = <b>tổng</b>. Gộp phía ứng dụng thay vì gửi <code>resolution='1W'</code> "
         f"lên API vì endpoint không cam kết hỗ trợ khung tuần/tháng.")


if __name__ == "__main__":
    render_advanced_chart()
