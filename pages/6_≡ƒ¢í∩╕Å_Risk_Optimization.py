# pages/6_🛡️_Risk_Optimization.py — yêu cầu [4]: tối ưu danh mục, đường biên hiệu quả, VaR
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from core.portfolio_opt import PortfolioOptimizer as Opt
from core.quantitative import log_returns
from data.dnse_client import get_ohlcv
from ui.charts import apply_theme
from ui.components import (guard_model, multi_ticker_selector, note, page_header,
                           period_selector, setup_page, sidebar_assumptions)


@st.cache_data(ttl=300, show_spinner=False)
def load_price_matrix(tickers: tuple[str, ...], days: int) -> tuple[pd.DataFrame, list[str]]:
    """
    Ghép ma trận giá đa mã.

    Bản cũ nổ AttributeError ngay tại df.columns.str.lower() khi một mã trả về
    DataFrame rỗng, vì columns của DataFrame rỗng là RangeIndex kiểu int.
    Nay bỏ qua mã lỗi và BÁO TÊN chúng ra thay vì làm sập cả trang.
    """
    series, failed = {}, []
    for t in tickers:
        df, src = get_ohlcv(t, days, allow_mock=False)
        if df.empty or len(df) < 30:
            failed.append(t)
        else:
            series[t] = df["close"]
    if not series:
        return pd.DataFrame(), failed
    # dropna trên GIÁ trước, rồi mới tính lợi suất — thứ tự này rất quan trọng
    return pd.DataFrame(series).dropna(), failed


def render_risk_optimization_page() -> None:
    setup_page("Risk Optimization", "🛡️")
    page_header("Tối ưu hóa danh mục & kiểm thử rủi ro",
                "Mô hình Markowitz, đường biên hiệu quả giải bằng tối ưu, VaR/CVaR lịch sử")

    tickers = multi_ticker_selector("opt", "Rổ cổ phiếu")
    days = period_selector("opt", 730)
    capital = st.sidebar.number_input("Tổng vốn (VND)", value=500_000_000, step=50_000_000)
    max_w = st.sidebar.slider("Trần tỷ trọng mỗi mã", 0.2, 1.0, 0.4, 0.05,
                              help="Ràng buộc tập trung. 1.0 = không giới hạn.")
    sidebar_assumptions()

    prices, failed = load_price_matrix(tuple(tickers), days)
    if failed:
        st.warning(f"Bỏ qua các mã không lấy được dữ liệu: **{', '.join(failed)}**")
    if prices.empty or prices.shape[1] < 2:
        st.error("Cần ít nhất 2 mã có dữ liệu hợp lệ để tối ưu hóa.")
        st.stop()

    returns = prices.apply(log_returns).dropna()
    mean_ret, cov = returns.mean(), returns.cov()
    st.caption(f"{prices.shape[1]} mã · {len(returns):,} phiên giao nhau · "
               f"{prices.index[0]:%d/%m/%Y} → {prices.index[-1]:%d/%m/%Y}")

    # ---------------- Tối ưu ----------------
    w_sharpe = guard_model(Opt.optimize_sharpe, mean_ret, cov, max_weight=max_w)
    w_minvar = guard_model(Opt.optimize_min_variance, mean_ret, cov, max_weight=max_w)
    if w_sharpe is None or w_minvar is None:
        st.stop()

    r_s, v_s, sh_s = Opt.calculate_performance(w_sharpe, mean_ret, cov)
    r_m, v_m, sh_m = Opt.calculate_performance(w_minvar, mean_ret, cov)

    st.markdown("##### 1 · Tỷ trọng tối ưu")
    tbl = pd.DataFrame({
        "Mã": prices.columns,
        "Max Sharpe": [f"{w:.1%}" for w in w_sharpe],
        "Phương sai nhỏ nhất": [f"{w:.1%}" for w in w_minvar],
    })
    c1, c2 = st.columns([1, 1.5])
    with c1:
        st.dataframe(tbl, use_container_width=True, hide_index=True)
    with c2:
        k = st.columns(3)
        k[0].metric("Lợi suất kỳ vọng/năm", f"{r_s:+.2%}")
        k[1].metric("Biến động/năm", f"{v_s:.2%}")
        k[2].metric("Sharpe", f"{sh_s:.3f}")
        st.caption(f"Danh mục phương sai nhỏ nhất: lợi suất {r_m:+.2%}, "
                   f"biến động {v_m:.2%}, Sharpe {sh_m:.3f}")

    # ---------------- VaR ----------------
    st.markdown("##### 2 · Rủi ro danh mục Max Sharpe")
    port_ret = (returns * w_sharpe).sum(axis=1)
    var = guard_model(Opt.calculate_var_cvar, port_ret, 0.95, capital)
    if var is not None:
        k = st.columns(4)
        k[0].metric("VaR 95% (1 phiên)", f"-{var['var_amount']/1e6:,.2f} tr",
                    delta=f"-{var['var_pct']:.2%}", delta_color="inverse")
        k[1].metric("CVaR 95% (1 phiên)", f"-{var['cvar_amount']/1e6:,.2f} tr",
                    delta=f"-{var['cvar_pct']:.2%}", delta_color="inverse")
        k[2].metric("VaR tham số (chuẩn)", f"-{var['var_param_pct']:.2%}",
                    help="Giả định phân phối chuẩn. Chênh với VaR lịch sử cho thấy đuôi dày.")
        k[3].metric("Cỡ mẫu / vùng đuôi", f"{var['n_obs']:,} / {var['n_tail']}")

        kup = Opt.kupiec_test(port_ret, var["var_pct"], 0.95)
        pval = f"{kup['pvalue']:.4f}" if kup["pvalue"] == kup["pvalue"] else "không tính được"
        note(f"<b>VaR này là in-sample.</b> Trọng số được tối ưu trên chính chuỗi lợi suất "
             f"dùng để đo VaR, nên kết quả lạc quan hơn thực tế một cách có hệ thống. "
             f"Kiểm định Kupiec: {kup['violations']} lần vượt ngưỡng trên {kup['n']} phiên "
             f"(kỳ vọng {kup['expected']:.1f}), p-value = {pval}. "
             f"Muốn kết luận chắc chắn thì phải tách train/test.")

    # ---------------- Đường biên ----------------
    st.markdown("##### 3 · Đường biên hiệu quả")
    frontier = guard_model(Opt.efficient_frontier, mean_ret, cov, 40, max_w)
    cloud = Opt.random_portfolios(mean_ret, cov, 1500)

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=cloud["vol"], y=cloud["ret"], mode="markers",
                             name="Danh mục ngẫu nhiên",
                             marker=dict(size=4, opacity=0.35, color=cloud["sharpe"],
                                         colorscale="Viridis", showscale=True,
                                         colorbar=dict(title="Sharpe"))))
    if frontier is not None:
        fig.add_trace(go.Scatter(x=frontier["vol"], y=frontier["ret"], mode="lines",
                                 name="Đường biên hiệu quả",
                                 line=dict(color="#ff9900", width=3)))
    fig.add_trace(go.Scatter(x=[v_s], y=[r_s], mode="markers", name="Max Sharpe",
                             marker=dict(size=16, color="#ef5350", symbol="star")))
    fig.add_trace(go.Scatter(x=[v_m], y=[r_m], mode="markers", name="Phương sai nhỏ nhất",
                             marker=dict(size=13, color="#26a69a", symbol="diamond")))
    fig.update_xaxes(title_text="Biến động năm", tickformat=".1%")
    fig.update_yaxes(title_text="Lợi suất kỳ vọng năm", tickformat=".1%")
    st.plotly_chart(apply_theme(fig, 520), use_container_width=True)

    note("Đường cam là <b>đường biên hiệu quả thật</b>: với mỗi mức lợi suất mục tiêu, "
         "chương trình giải bài toán min wᵀΣw với ràng buộc Σw = 1 và wᵀμ = R*. "
         "Đám mây phía sau chỉ là <b>danh mục ngẫu nhiên</b> để làm nền — và đó chính xác "
         "là thứ bản cũ vẽ ra rồi gọi nhầm là Efficient Frontier. Với 4 mã, trọng số sinh "
         "bằng <code>np.random.random()</code> rồi chuẩn hóa chỉ vượt 0,9 trong <b>0,025%</b> "
         "số lần, nên trong 1.500 điểm gần như không bao giờ chạm được hai đầu mút.")


if __name__ == "__main__":
    render_risk_optimization_page()
