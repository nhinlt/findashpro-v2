# pages/4_⚖️_Risk_Analytics.py — yêu cầu [5] Monte Carlo + yêu cầu [4] CAPM & APT (một mã)
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from core.portfolio import apt, build_factors, capm, security_market_line
from core.quantitative import (DRIFT_MODES, estimate_drift, log_returns,
                               mc_percentile_bands, mc_risk_metrics, run_monte_carlo)
from data.dnse_client import get_ohlcv
from ui.charts import apply_theme, create_fan_chart
from ui.components import (guard_data, guard_model, note, page_header,
                           setup_page, sidebar_assumptions, source_badge, ticker_selector)
from utils.config import (MARKET_INDEX, PRICE_UNIT, RISK_FREE_RATE, SIZE_INDEX)


def render_risk_analytics_page() -> None:
    setup_page("Risk Analytics", "⚖️")
    ticker = ticker_selector("risk")
    sidebar_assumptions()

    page_header(f"Phân tích rủi ro & định giá · {ticker}",
                "Mô phỏng Monte Carlo, mô hình CAPM một nhân tố và APT đa nhân tố")

    df, source = get_ohlcv(ticker, 730)
    guard_data(df, ticker, min_rows=61)
    source_badge(source)

    tab_mc, tab_capm, tab_apt = st.tabs(
        ["🎲 Monte Carlo", "📐 CAPM", "🧮 APT (đa nhân tố)"])

    # ==================================================================
    # MONTE CARLO
    # ==================================================================
    with tab_mc:
        c1, c2, c3, c4, c5 = st.columns(5)
        sims = c1.selectbox("Số kịch bản", [500, 1000, 5000, 10000], index=1)
        horizon = c2.selectbox("Khung dự phóng (phiên)", [21, 63, 126, 252], index=1)
        method = c3.selectbox("Mô hình", ["GBM", "Bootstrap"],
                              help="GBM giả định lợi suất log phân phối chuẩn. "
                                   "Bootstrap rút mẫu từ chính lịch sử nên giữ được đuôi dày.")
        drift_label = c4.selectbox("Giả định drift", list(DRIFT_MODES), index=1,
                                   help="Drift ước lượng từ lịch sử có sai số chuẩn rất "
                                        "lớn. Trung tính rủi ro là chuẩn mực khi đo rủi ro.")
        conf = c5.selectbox("Độ tin cậy VaR", [0.90, 0.95, 0.99], index=1,
                            format_func=lambda x: f"{x:.0%}")

        # ---- Bày ra độ tin cậy của chính tham số đầu vào ----
        est = estimate_drift(df["close"])
        d = st.columns(4)
        d[0].metric("μ ước lượng (năm)", f"{est['mu_annual']:+.2%}")
        d[1].metric("Sai số chuẩn của μ", f"±{est['se_annual']:.2%}")
        d[2].metric("t-statistic của μ", f"{est['tstat']:.2f}")
        d[3].metric("σ ước lượng (năm)", f"{est['sigma_annual']:.2%}")

        if not est["significant"]:
            note(f"<b>Drift lịch sử KHÔNG khác 0 về mặt thống kê</b> (t = {est['tstat']:.2f}, "
                 f"khoảng tin cậy 95%: [{est['ci_annual'][0]:+.1%}; {est['ci_annual'][1]:+.1%}]). "
                 f"Sai số chuẩn của μ bằng σ/√n; với {est['n_obs']:,} phiên nó thường lớn hơn "
                 f"chính giá trị ước lượng. Vì vậy khi <b>đo rủi ro</b>, nên dùng drift "
                 f"<b>trung tính rủi ro</b> (μ = rf) thay vì áp đặt một xu hướng mà dữ liệu "
                 f"không đủ sức khẳng định. Sửa drift = 0 thành drift lịch sử là đúng về cấu "
                 f"trúc, nhưng nói rõ độ tin cậy của tham số mới là làm đủ.")

        sim = guard_model(run_monte_carlo, df["close"], horizon, sims,
                          method, DRIFT_MODES[drift_label])
        if sim is not None:
            m = mc_risk_metrics(sim, conf)

            k = st.columns(5)
            k[0].metric(f"Giá hiện tại ({PRICE_UNIT})", f"{m['s0']:,.2f}")
            k[1].metric("Giá kỳ vọng", f"{m['expected']:,.2f}",
                        delta=f"{m['expected']/m['s0']-1:+.2%}")
            # VaR LÀ MỘT KHOẢN LỖ, không phải một mức giá.
            k[2].metric(f"VaR {conf:.0%} ({horizon} phiên)", f"-{m['var_amount']:,.2f}",
                        delta=f"-{m['var_pct']:.2%}", delta_color="inverse")
            k[3].metric(f"CVaR {conf:.0%}", f"-{m['cvar_amount']:,.2f}",
                        delta=f"-{m['cvar_pct']:.2%}", delta_color="inverse")
            k[4].metric("Xác suất lỗ", f"{m['prob_loss']:.1%}")

            note(f"<b>VaR đọc thế nào:</b> với độ tin cậy {conf:.0%} trong {horizon} phiên tới, "
                 f"khoản lỗ không vượt quá <b>{m['var_amount']:,.2f} {PRICE_UNIT}</b> "
                 f"({m['var_pct']:.2%} giá trị). CVaR là mức lỗ <i>trung bình</i> trong "
                 f"{100*(1-conf):.0f}% kịch bản xấu nhất, nên luôn lớn hơn VaR. "
                 f"VaR là một <b>khoản lỗ</b> — không phải một mức giá.")

            cA, cB = st.columns([1.4, 1])
            with cA:
                st.plotly_chart(
                    create_fan_chart(mc_percentile_bands(sim),
                                     f"Dải phân vị {sims:,} kịch bản — {method} · {drift_label}"),
                    use_container_width=True)
            with cB:
                end = sim.iloc[-1]
                fig = go.Figure(go.Histogram(x=end, nbinsx=60, marker_color="#ff9900",
                                             opacity=0.8))
                fig.add_vline(x=m["s0"], line_color="#8b949e", line_dash="dash",
                              annotation_text="Hôm nay")
                fig.add_vline(x=m["q_low"], line_color="#ef5350",
                              annotation_text=f"P{100*(1-conf):.0f}")
                fig.update_xaxes(title_text=f"Giá sau {horizon} phiên ({PRICE_UNIT})")
                st.plotly_chart(apply_theme(fig, 460, "Phân phối giá cuối kỳ"),
                                use_container_width=True)

            note("Mô phỏng dùng <b>seed cố định</b> nên chạy lại cho ra đúng con số cũ. "
                 "Bước mô phỏng là S<sub>t</sub> = S<sub>0</sub>·exp[Σ((μ−½σ²) + σZ)] — "
                 "số hạng <b>−½σ²</b> đến từ bổ đề Itô; thiếu nó thì kỳ vọng bị thổi lên "
                 "đúng hệ số exp(σ²T/2). Nếu tab Thống kê giá cho thấy Jarque–Bera bác bỏ "
                 "phân phối chuẩn, hãy đối chiếu kết quả GBM với <b>Bootstrap</b>.")

    # ==================================================================
    # CAPM
    # ==================================================================
    with tab_capm:
        mkt_df, _ = get_ohlcv(MARKET_INDEX, 730)
        if mkt_df.empty:
            st.warning(f"Không tải được chỉ số {MARKET_INDEX}.")
        else:
            res = guard_model(capm, log_returns(df["close"]), log_returns(mkt_df["close"]))
            if res is not None:
                k = st.columns(4)
                k[0].metric("Beta", f"{res['beta']:.3f}",
                            help=f"t = {res['beta_tstat']:.2f} · "
                                 f"KTC 95%: [{res['beta_ci'][0]:.2f}; {res['beta_ci'][1]:.2f}]")
                k[1].metric("Alpha (năm hóa)", f"{res['alpha_annual']:+.2%}",
                            help=f"t = {res['alpha_tstat']:.2f} · p = {res['alpha_pvalue']:.4f}")
                k[2].metric("R²", f"{res['r_squared']:.1%}")
                k[3].metric("Số quan sát", f"{res['n_obs']:,}")

                verdict = ("<b>khác 0 có ý nghĩa thống kê</b>" if res["alpha_significant"]
                           else "<b>KHÔNG khác 0 về mặt thống kê</b>")
                note(f"Alpha có p-value = {res['alpha_pvalue']:.4f}, tức {verdict} ở mức 5%. "
                     f"Đây là dòng bắt buộc phải có: một alpha dương nhưng t nhỏ thì không "
                     f"cho phép kết luận cổ phiếu tạo ra alpha.")

                st.markdown("##### CAPM dùng để định giá")
                k = st.columns(4)
                k[0].metric("Lãi suất phi rủi ro", f"{RISK_FREE_RATE:.2%}")
                k[1].metric("Phần bù thị trường", f"{res['market_premium']:+.2%}")
                k[2].metric("Lợi suất YÊU CẦU", f"{res['required_return']:+.2%}",
                            help="E(R) = Rf + β·[E(Rm) − Rf]")
                k[3].metric("Lợi suất thực tế", f"{res['actual_return']:+.2%}",
                            delta=f"{res['jensen_alpha']:+.2%} so với yêu cầu")

                cA, cB = st.columns(2)
                with cA:
                    d = res["data"]           # CHÍNH bộ dữ liệu đã hồi quy
                    fig = px.scatter(d, x="rm_ex", y="ri_ex", trendline="ols",
                                     opacity=0.55, trendline_color_override="#ff9900")
                    fig.update_xaxes(title_text=f"Excess return {MARKET_INDEX}")
                    fig.update_yaxes(title_text=f"Excess return {ticker}")
                    st.plotly_chart(apply_theme(fig, 420, "Đường đặc trưng chứng khoán"),
                                    use_container_width=True)
                    note("Biểu đồ vẽ trên <b>đúng bộ dữ liệu excess return đã dùng để hồi quy</b>, "
                         "nên hệ số chặn của đường trên hình khớp với Alpha in ở trên. Phiên bản "
                         "trước hồi quy trên excess return nhưng vẽ trên raw return, khiến hai "
                         "con số không khớp nhau.")
                with cB:
                    sml = security_market_line(max(2.0, res["beta"] * 1.3),
                                               res["market_premium"])
                    fig = go.Figure()
                    fig.add_trace(go.Scatter(x=sml["beta"], y=sml["required_return"],
                                             mode="lines", name="SML",
                                             line=dict(color="#26a69a", width=2)))
                    fig.add_trace(go.Scatter(x=[res["beta"]], y=[res["actual_return"]],
                                             mode="markers+text", name=ticker, text=[ticker],
                                             textposition="top center",
                                             marker=dict(size=15, color="#ff9900", symbol="star")))
                    fig.update_xaxes(title_text="Beta")
                    fig.update_yaxes(title_text="Lợi suất năm", tickformat=".0%")
                    st.plotly_chart(apply_theme(fig, 420, "Đường thị trường chứng khoán (SML)"),
                                    use_container_width=True)
                    pos = "TRÊN" if res["jensen_alpha"] > 0 else "DƯỚI"
                    note(f"Điểm {ticker} nằm <b>{pos}</b> đường SML: lợi suất thực tế "
                         f"{res['actual_return']:+.2%} so với mức yêu cầu "
                         f"{res['required_return']:+.2%} ứng với beta {res['beta']:.2f}.")

    # ==================================================================
    # APT
    # ==================================================================
    with tab_apt:
        st.markdown("##### Arbitrage Pricing Theory — Ross (1976)")
        st.latex(r"R_i - R_f = \alpha + \sum_{k} \beta_k F_k + \varepsilon")

        mkt_df, _ = get_ohlcv(MARKET_INDEX, 730)
        size_df, _ = get_ohlcv(SIZE_INDEX, 730)
        if mkt_df.empty:
            st.warning(f"Không tải được chỉ số {MARKET_INDEX}.")
        else:
            factors = build_factors(mkt_df["close"],
                                    size_df["close"] if not size_df.empty else None)
            res_apt = guard_model(apt, log_returns(df["close"]), factors)
            res_capm = guard_model(capm, log_returns(df["close"]), log_returns(mkt_df["close"]))

            if res_apt is not None:
                k = st.columns(4)
                k[0].metric("R²", f"{res_apt['r_squared']:.1%}")
                k[1].metric("R² hiệu chỉnh", f"{res_apt['adj_r_squared']:.1%}")
                k[2].metric("F-test p-value", f"{res_apt['f_pvalue']:.4f}")
                k[3].metric("Alpha (năm hóa)", f"{res_apt['alpha_annual']:+.2%}",
                            help=f"p = {res_apt['alpha_pvalue']:.4f}")

                st.dataframe(
                    res_apt["table"].style.format({
                        "Hệ số β": "{:.4f}", "Sai số chuẩn": "{:.4f}",
                        "t-statistic": "{:.2f}", "p-value": "{:.4f}"}),
                    use_container_width=True, hide_index=True)

                st.markdown("##### Vì sao đề bài yêu cầu cả CAPM lẫn APT")
                if res_capm is not None:
                    gain = res_apt["adj_r_squared"] - res_capm["r_squared"]
                    c = st.columns(3)
                    c[0].metric("CAPM — R²", f"{res_capm['r_squared']:.1%}")
                    c[1].metric("APT — R² hiệu chỉnh", f"{res_apt['adj_r_squared']:.1%}")
                    c[2].metric("Chênh lệch", f"{gain:+.1%}")
                    verdict = ("bổ sung được khả năng giải thích" if gain > 0.01
                               else "gần như không bổ sung thêm gì")
                    note(f"Với mã {ticker}, các nhân tố ngoài thị trường <b>{verdict}</b>. "
                         f"CAPM giả định chỉ có MỘT nguồn rủi ro hệ thống; APT cho phép nhiều "
                         f"nguồn. So sánh R² hiệu chỉnh (đã phạt số biến) chính là câu trả lời "
                         f"cho câu hỏi hai mô hình khác nhau ở đâu.")

                vif_bad = [f"{k_}={v:.1f}" for k_, v in res_apt["vif"].items() if v > 5]
                st.caption("Kiểm tra đa cộng tuyến (VIF): " +
                           ", ".join(f"{k_} = {v:.2f}" for k_, v in res_apt["vif"].items()) +
                           (f" — ⚠️ VIF > 5 ở {', '.join(vif_bad)}, hệ số kém ổn định."
                            if vif_bad else " — tất cả dưới 5, chấp nhận được."))

                with st.expander("Định nghĩa các nhân tố"):
                    st.markdown(
                        f"- **MKT** — lợi suất {MARKET_INDEX}, nhân tố thị trường\n"
                        f"- **SIZE** — {SIZE_INDEX} trừ {MARKET_INDEX}: chênh lệch giữa rổ vốn "
                        f"hóa lớn và toàn thị trường, proxy cho nhân tố quy mô (dấu ngược với "
                        f"SMB của Fama–French)\n"
                        f"- **MOM** — động lượng thị trường, trung bình 20 phiên của "
                        f"{MARKET_INDEX}, **đã dịch 1 phiên** để tránh look-ahead bias")


if __name__ == "__main__":
    render_risk_analytics_page()
