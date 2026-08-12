# pages/5_🧪_Alpha_Backtest.py — module mở rộng (ngoài 5 yêu cầu của đề)
import plotly.graph_objects as go
import streamlit as st

from core.alpha_engine import SIGNALS, AlphaEngine
from data.dnse_client import get_ohlcv
from ui.charts import apply_theme
from ui.components import (guard_data, guard_model, note, page_header, period_selector,
                           setup_page, sidebar_assumptions, source_badge, ticker_selector)
from utils.config import SETTLEMENT_LAG, TRANSACTION_COST


def render_alpha_page() -> None:
    setup_page("Alpha Backtest", "🧪")
    # Đọc mã từ session_state như MỌI trang khác. Bản cũ hardcode value="VNM" nên
    # người dùng đổi mã ở trang chủ sang đây vẫn thấy VNM.
    ticker = ticker_selector("alpha")
    days = period_selector("alpha", 730)
    sidebar_assumptions()

    page_header(f"Kiểm thử tín hiệu Alpha · {ticker}",
                "Backtest vector hóa, có phí giao dịch và ràng buộc vi cấu trúc thị trường Việt Nam")

    with st.container(border=True):
        c1, c2, c3, c4 = st.columns(4)
        choice = c1.selectbox("Tín hiệu", SIGNALS)
        capital = c2.number_input("Vốn ban đầu (VND)", value=100_000_000, step=10_000_000)
        cost = c3.number_input("Phí mỗi lượt (%)", value=TRANSACTION_COST * 100,
                               step=0.05, format="%.2f") / 100
        allow_short = c4.checkbox("Cho phép bán khống", value=False,
                                  help="TTCK Việt Nam không có bán khống cổ phiếu. "
                                       "Bật để so sánh học thuật, không phải để kết luận.")

    df, source = get_ohlcv(ticker, days)
    guard_data(df, ticker, min_rows=30)
    source_badge(source)

    signal = AlphaEngine.calculate_alpha_signal(df, choice)
    res = guard_model(AlphaEngine.backtest_signal, df, signal,
                      initial_capital=capital, transaction_cost=cost,
                      allow_short=allow_short)
    if res is None:
        return

    k = st.columns(5)
    k[0].metric("Tổng lợi nhuận", f"{res['total_return']:+.2%}",
                delta=f"{res['excess_vs_benchmark']:+.2%} so với mua & giữ")
    k[1].metric("Sharpe Ratio", f"{res['sharpe_ratio']:.2f}",
                help="ĐÃ trừ lãi suất phi rủi ro. Bản cũ không trừ nên con số đó thực "
                     "chất là Information Ratio.")
    k[2].metric("Max Drawdown", f"{res['max_drawdown']:.2%}")
    k[3].metric("Tỷ lệ thắng / LỆNH", f"{res['win_rate']:.1%}",
                help=f"{res['n_trades']} lệnh, giữ trung bình "
                     f"{res['avg_holding_days']:.1f} phiên/lệnh")
    k[4].metric("Tổng phí đã trả", f"{res['total_cost']/1e6:,.1f} tr")

    k = st.columns(4)
    k[0].metric("Lợi nhuận năm hóa", f"{res['ann_return']:+.2%}")
    k[1].metric("Information Ratio", f"{res['information_ratio']:.2f}")
    k[2].metric("Sortino Ratio", f"{res['sortino_ratio']:.2f}"
                if res["sortino_ratio"] == res["sortino_ratio"] else "—")
    k[3].metric("Tổng turnover", f"{res['total_turnover']:.1f}x")

    a = res["assumptions"]
    note(
        f"<b>Giả định đã áp dụng.</b> "
        f"Bán khống: <b>{'CÓ' if a['allow_short'] else 'KHÔNG'}</b> — thị trường Việt Nam "
        f"không cho bán khống cổ phiếu, và tín hiệu Mean-Reversion đối xứng quanh 0 nên nếu "
        f"bật, khoảng một nửa hiệu suất đến từ giao dịch không thực hiện được. "
        f"Độ trễ khớp lệnh: <b>T+{a['execution_lag']}</b> (tín hiệu chốt hết phiên T, khớp "
        f"phiên sau — chống look-ahead bias). "
        f"Thanh toán: <b>T+{a['settlement_lag']}</b> — sau khi mua, vị thế bị giữ tối thiểu "
        f"{a['settlement_lag']} phiên vì cổ phiếu chưa về tài khoản. "
        f"Phí: <b>{a['transaction_cost']:.2%}</b> mỗi lượt, tính trên turnover thực tế."
    )

    data = res["data"]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=data.index, y=data["equity"], name="Chiến lược",
                             line=dict(color="#26a69a", width=2)))
    fig.add_trace(go.Scatter(x=data.index, y=capital * data["cum_market_return"],
                             name="Mua và giữ", line=dict(color="#ff9900", dash="dash", width=1.6)))
    fig.update_yaxes(title_text="Giá trị tài sản (VND)")
    st.plotly_chart(apply_theme(fig, 460, "Đường cong tài sản"), use_container_width=True)

    c1, c2 = st.columns(2)
    with c1:
        eq = data["equity"]
        dd = (eq - eq.cummax()) / eq.cummax()
        fig = go.Figure(go.Scatter(x=data.index, y=dd, fill="tozeroy",
                                   line=dict(color="#ef5350", width=1)))
        fig.update_yaxes(title_text="Drawdown", tickformat=".0%")
        st.plotly_chart(apply_theme(fig, 300, "Mức sụt giảm từ đỉnh"), use_container_width=True)
    with c2:
        if len(res["trade_returns"]):
            fig = go.Figure(go.Histogram(x=res["trade_returns"], nbinsx=30,
                                         marker_color="#ff9900", opacity=0.8))
            fig.add_vline(x=0, line_color="#8b949e", line_dash="dash")
            fig.update_xaxes(title_text="Lợi nhuận mỗi lệnh", tickformat=".0%")
            st.plotly_chart(apply_theme(fig, 300, "Phân phối lợi nhuận theo LỆNH"),
                            use_container_width=True)
            note("Tỷ lệ thắng tính trên <b>lệnh</b> — mỗi lệnh là một chuỗi phiên liên tiếp "
                 "giữ cùng chiều vị thế. Bản cũ tính trên <b>ngày</b> nhưng vẫn đặt tên biến "
                 "là <code>active_trades</code> và gắn nhãn &quot;Tỷ lệ thắng&quot;.")

    st.caption("Backtest in-sample trên toàn bộ khoảng dữ liệu — chưa tách train/test, nên "
               "kết quả không phải bằng chứng về hiệu quả ngoài mẫu.")


if __name__ == "__main__":
    render_alpha_page()
