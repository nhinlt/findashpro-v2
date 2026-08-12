# core/quantitative.py
"""
Mô phỏng Monte Carlo (yêu cầu [5]) và thống kê mô tả một cổ phiếu (yêu cầu [3]).

Bản cũ có 6 lỗi trong 18 dòng:
  (a) drift = 0     -> E[S_T] luôn xấp xỉ giá hôm nay, bất kể mã, bất kể horizon
  (b) thiếu -0.5σ²  -> sai bổ đề Itô
  (c) cumprod(1+r)  -> trộn simple return với mô hình log-normal
  (d) np.std ddof=0 -> dùng công thức tổng thể cho dữ liệu mẫu
  (e) không seed    -> mỗi lần rerun ra số khác, không tái lập được
  (f) hàng đầu tiên -> đã là S0*(1+r1), đường mô phỏng không nối với giá hiện tại
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from utils.config import RANDOM_SEED, RISK_FREE_RATE, TRADING_DAYS

MIN_OBS_MC = 60
MIN_OBS_STATS = 30


def log_returns(close: pd.Series) -> pd.Series:
    """Quy ước LOG return dùng thống nhất toàn app (xem utils.config.RETURN_CONVENTION)."""
    return np.log(close / close.shift(1)).dropna()


# ---------------------------------------------------------------------------
# MONTE CARLO
# ---------------------------------------------------------------------------
def estimate_drift(close_prices: pd.Series) -> dict:
    """
    Ước lượng μ, σ VÀ ĐỘ TIN CẬY của chúng.

    Đây là hàm mà mọi báo cáo Monte Carlo phải có nhưng gần như luôn bị bỏ qua.
    Sai số chuẩn của μ bằng σ/√n. Với 1 năm dữ liệu và σ = 30%/năm, sai số chuẩn
    của μ năm hóa vào khoảng 30%/năm — tức LỚN HƠN chính giá trị ước lượng. Nói
    cách khác: drift lịch sử gần như luôn KHÔNG khác 0 về mặt thống kê.

    Đó là lý do bản này cho phép chọn drift thay vì áp đặt một con số.
    """
    r = log_returns(close_prices)
    n = len(r)
    mu = float(r.mean())
    sigma = float(r.std(ddof=1))
    se = sigma / np.sqrt(n)
    return {
        "mu_daily": mu,
        "sigma_daily": sigma,
        "mu_annual": mu * TRADING_DAYS,
        "sigma_annual": sigma * np.sqrt(TRADING_DAYS),
        "se_annual": se * TRADING_DAYS,
        "tstat": mu / se if se > 0 else np.nan,
        "ci_annual": ((mu - 1.96 * se) * TRADING_DAYS, (mu + 1.96 * se) * TRADING_DAYS),
        "significant": bool(abs(mu / se) > 1.96) if se > 0 else False,
        "n_obs": n,
    }


DRIFT_MODES = {
    "Ước lượng từ lịch sử": "historical",
    "Trung tính rủi ro (μ = rf)": "risk_neutral",
    "Martingale (E[S_T] = S₀)": "zero",
}


def run_monte_carlo(
    close_prices: pd.Series,
    time_horizon: int,
    simulations: int,
    method: str = "GBM",
    drift_mode: str = "historical",
    seed: int | None = RANDOM_SEED,
) -> pd.DataFrame:
    """
    Mô phỏng quỹ đạo giá.

    GBM (Black–Scholes):
        S_t = S_0 · exp( Σ [ (μ − ½σ²)Δt + σ√Δt · Z ] )

    Số hạng −½σ² đến từ bổ đề Itô: nếu dS = μS·dt + σS·dW thì
        d(ln S) = (μ − ½σ²)dt + σ·dW
    Bỏ nó đi thì E[S_T] bị thổi lên đúng hệ số exp(σ²T/2).

    drift_mode:
      historical   — μ = trung bình log return lịch sử. Không thiên lệch nhưng
                     NHIỄU cực lớn (xem estimate_drift).
      risk_neutral — μ = lãi suất phi rủi ro. Chuẩn mực khi định giá và đo rủi ro,
                     vì nó không đòi hỏi dự báo lợi suất kỳ vọng.
      zero         — drift sao cho E[S_T] = S₀. KHÁC với lỗi cũ: bản cũ đặt kỳ vọng
                     của SIMPLE return bằng 0 mà vẫn thiếu hiệu chỉnh Itô.

    Bootstrap: rút mẫu có hoàn lại từ chính chuỗi lợi suất lịch sử. Không giả định
    phân phối chuẩn nên giữ được đuôi dày và độ lệch thật của thị trường.

    Trả về DataFrame (time_horizon + 1) × simulations, HÀNG 0 = giá hiện tại.
    """
    r = log_returns(close_prices)
    if len(r) < MIN_OBS_MC:
        raise ValueError(
            f"Chỉ có {len(r)} quan sát. Cần ít nhất {MIN_OBS_MC} phiên để ước lượng "
            f"μ và σ một cách đáng tin cậy."
        )

    sigma = float(r.std(ddof=1))         # ddof=1: độ lệch chuẩn MẪU
    s0 = float(close_prices.iloc[-1])

    if drift_mode == "historical":
        mu = float(r.mean())
    elif drift_mode == "risk_neutral":
        mu = RISK_FREE_RATE / TRADING_DAYS
    elif drift_mode == "zero":
        # E[S_T] = S₀·exp(μT). Muốn kỳ vọng đứng yên thì μ = 0 — số hạng −½σ² trong
        # bước mô phỏng chính là thứ bù lại độ lồi của hàm mũ. Bản cũ đặt kỳ vọng của
        # SIMPLE return bằng 0 mà vẫn thiếu −½σ², nên sai ở cả hai chỗ cùng lúc.
        mu = 0.0
    else:
        raise ValueError(f"drift_mode không hợp lệ: {drift_mode!r}")

    rng = np.random.default_rng(seed)    # có seed -> kết quả tái lập được

    if method == "GBM":
        z = rng.standard_normal((time_horizon, simulations))
        steps = (mu - 0.5 * sigma**2) + sigma * z
    elif method == "Bootstrap":
        sample = rng.choice(r.to_numpy(), size=(time_horizon, simulations), replace=True)
        # Tái neo drift của mẫu bootstrap về drift đã chọn, giữ nguyên hình dạng đuôi
        steps = sample - float(r.mean()) + mu
    else:
        raise ValueError(f"method không hợp lệ: {method!r} (chọn 'GBM' hoặc 'Bootstrap')")

    # Vector hóa hoàn toàn: không còn vòng lặp Python gán từng cột DataFrame
    paths = s0 * np.exp(np.vstack([np.zeros(simulations), steps.cumsum(axis=0)]))
    return pd.DataFrame(paths)           # hàng 0 = S0, đường vẽ nối liền giá hiện tại


def mc_risk_metrics(sim: pd.DataFrame, confidence: float = 0.95) -> dict:
    """
    Chỉ số rủi ro từ kết quả mô phỏng.

    VaR LÀ MỘT KHOẢN LỖ, không phải một mức giá:
        VaR_95% = S_0 − Q_5%(S_T)
    Bản cũ hiển thị thẳng np.percentile(end_prices, 5) — tức phân vị GIÁ — và gắn
    nhãn "VaR 95%". Đó là sai định nghĩa, không phải sai tham số.
    """
    s0 = float(sim.iloc[0, 0])
    st_ = sim.iloc[-1].to_numpy()

    q = float(np.percentile(st_, (1 - confidence) * 100))
    tail = st_[st_ <= q]

    return {
        "s0": s0,
        "expected": float(st_.mean()),
        "median": float(np.median(st_)),
        "q_low": q,
        "q_high": float(np.percentile(st_, confidence * 100)),
        "var_amount": s0 - q,                       # KHOẢN LỖ (đơn vị giá)
        "var_pct": 1.0 - q / s0,                    # KHOẢN LỖ (%)
        "cvar_amount": s0 - float(tail.mean()),
        "cvar_pct": 1.0 - float(tail.mean()) / s0,
        "prob_loss": float((st_ < s0).mean()),
        "confidence": confidence,
        "n_sims": sim.shape[1],
        "horizon": sim.shape[0] - 1,
    }


def mc_percentile_bands(sim: pd.DataFrame,
                        levels: tuple[int, ...] = (5, 25, 50, 75, 95)) -> pd.DataFrame:
    """Dải phân vị theo thời gian — biểu đồ quạt đọc được hơn 100 đường chồng nhau."""
    return pd.DataFrame(
        {f"P{p}": np.percentile(sim.to_numpy(), p, axis=1) for p in levels},
        index=sim.index,
    )


# ---------------------------------------------------------------------------
# THỐNG KÊ MÔ TẢ (yêu cầu [3])
# ---------------------------------------------------------------------------
def describe_returns(close_prices: pd.Series) -> pd.DataFrame:
    """
    Bảng thống kê mô tả cho MỘT cổ phiếu.

    Hai dòng quan trọng nhất là Kurtosis và Jarque–Bera: chúng là bằng chứng
    ĐỊNH LƯỢNG cho biết giả định phân phối chuẩn của GBM có bị vi phạm hay không.
    """
    r = log_returns(close_prices)
    n = len(r)
    if n < MIN_OBS_STATS:
        raise ValueError(f"Chỉ có {n} quan sát — cần ít nhất {MIN_OBS_STATS} để thống kê.")

    ann_ret = float(r.mean()) * TRADING_DAYS
    ann_vol = float(r.std(ddof=1)) * np.sqrt(TRADING_DAYS)
    sharpe = (ann_ret - RISK_FREE_RATE) / ann_vol if ann_vol > 0 else np.nan

    skew = float(stats.skew(r))
    kurt = float(stats.kurtosis(r))                 # kurtosis THỪA (chuẩn = 0)
    _, jb_p = stats.jarque_bera(r)

    equity = np.exp(r.cumsum())
    mdd = float((equity / equity.cummax() - 1).min())

    var95 = float(np.percentile(r, 5))
    cvar95 = float(r[r <= var95].mean())

    normal_ok = "Không bác bỏ" if jb_p >= 0.05 else "BÁC BỎ (đuôi dày)"

    rows = [
        ("Số quan sát", f"{n:,}"),
        ("Lợi suất TB / phiên", f"{r.mean():.4%}"),
        ("Độ lệch chuẩn / phiên", f"{r.std(ddof=1):.4%}"),
        ("Lợi suất năm hóa", f"{ann_ret:.2%}"),
        ("Biến động năm hóa", f"{ann_vol:.2%}"),
        (f"Sharpe (rf = {RISK_FREE_RATE:.1%})", f"{sharpe:.3f}"),
        ("Skewness", f"{skew:.3f}"),
        ("Kurtosis thừa", f"{kurt:.3f}"),
        ("Jarque–Bera p-value", f"{jb_p:.4f}"),
        ("Giả định phân phối chuẩn", normal_ok),
        ("Max Drawdown", f"{mdd:.2%}"),
        ("VaR 95% lịch sử (1 phiên)", f"{-var95:.2%}"),
        ("CVaR 95% lịch sử (1 phiên)", f"{-cvar95:.2%}"),
    ]
    return pd.DataFrame(rows, columns=["Chỉ tiêu", "Giá trị"])
