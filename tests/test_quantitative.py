# tests/test_quantitative.py
"""
Test cho ba chỗ dễ sai nhất: Monte Carlo, VaR/CVaR và CAPM.

Bộ test cũ chỉ phủ SMA (40 dòng) — đúng cái đơn giản nhất, bỏ trống đúng ba chỗ
mà toàn bộ kết luận tài chính phụ thuộc vào.
"""
import os
import sys

import numpy as np
import pandas as pd
import pytest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.portfolio import capm                       # noqa: E402
from core.portfolio_opt import PortfolioOptimizer     # noqa: E402
from core.quantitative import (estimate_drift, mc_risk_metrics,  # noqa: E402
                                run_monte_carlo)
from utils.config import TRADING_DAYS                 # noqa: E402


@pytest.fixture
def price_series() -> pd.Series:
    """Chuỗi giá GBM đã biết trước tham số: mu = 20%/năm, sigma = 30%/năm."""
    rng = np.random.default_rng(1)
    n, mu, sig = 500, 0.20 / TRADING_DAYS, 0.30 / np.sqrt(TRADING_DAYS)
    steps = (mu - 0.5 * sig**2) + sig * rng.standard_normal(n)
    return pd.Series(100 * np.exp(np.cumsum(steps)))


# ---------------------------------------------------------------- Monte Carlo
def test_mc_path_starts_at_current_price(price_series):
    """Hàng 0 phải LÀ giá hiện tại. Bản cũ bắt đầu ở S0*(1+r1)."""
    sim = run_monte_carlo(price_series, 30, 200)
    assert sim.shape == (31, 200)
    assert np.allclose(sim.iloc[0], price_series.iloc[-1])


def test_mc_drift_is_applied(price_series):
    """
    Lỗi nặng nhất của bản cũ: drift bị ĐẶT BẰNG 0 nên E[S_T] luôn xấp xỉ giá hôm nay,
    bất kể mã nào và bất kể khung dự phóng.

    Kiểm tra đúng đắn là E[S_T] khớp công thức S₀·exp(μ̂·T) với μ̂ ước lượng được —
    KHÔNG phải "kỳ vọng luôn tăng". Với chuỗi này μ̂ âm, và mô hình phản ánh đúng
    điều đó thay vì áp đặt một xu hướng không có trong dữ liệu.
    """
    d = estimate_drift(price_series)
    sim = run_monte_carlo(price_series, 252, 20000, drift_mode="historical")
    ratio = sim.iloc[-1].mean() / price_series.iloc[-1]
    assert ratio == pytest.approx(np.exp(d["mu_annual"]), rel=0.03)


def test_mc_drift_modes_are_distinct(price_series):
    """Ba chế độ drift phải cho ba kỳ vọng khác nhau và đúng lý thuyết."""
    s0 = price_series.iloc[-1]
    exp_of = lambda mode: run_monte_carlo(
        price_series, 252, 20000, drift_mode=mode).iloc[-1].mean() / s0

    # Martingale: E[S_T] = S₀. Đây là chỗ số hạng −½σ² phải bù đúng độ lồi hàm mũ.
    assert exp_of("zero") == pytest.approx(1.0, abs=0.02)
    # Trung tính rủi ro: E[S_T] = S₀·exp(rf·T)
    assert exp_of("risk_neutral") == pytest.approx(np.exp(0.045), rel=0.03)


def test_drift_estimate_reports_its_own_uncertainty(price_series):
    """
    Sai số chuẩn của μ bằng σ/√n. Với 1–2 năm dữ liệu nó thường LỚN HƠN chính giá
    trị ước lượng, nên drift lịch sử gần như luôn không khác 0 về mặt thống kê.
    Báo cáo Monte Carlo mà không nói điều này là báo cáo thiếu.
    """
    d = estimate_drift(price_series)
    assert d["se_annual"] > 0
    assert d["ci_annual"][0] < d["mu_annual"] < d["ci_annual"][1]
    # np.bool_ không đồng nhất với bool của Python nên so sánh bằng ==, không dùng is
    assert d["significant"] == bool(abs(d["tstat"]) > 1.96)


def test_mc_is_reproducible(price_series):
    """Có seed thì hai lần chạy phải ra đúng một kết quả."""
    a = run_monte_carlo(price_series, 20, 100, seed=7)
    b = run_monte_carlo(price_series, 20, 100, seed=7)
    pd.testing.assert_frame_equal(a, b)


def test_mc_prices_never_negative(price_series):
    """Dạng exp() luôn dương. cumprod(1+r) của bản cũ về lý thuyết có thể đổi dấu."""
    assert (run_monte_carlo(price_series, 252, 500) > 0).all().all()


def test_mc_rejects_short_sample():
    with pytest.raises(ValueError, match="quan sát"):
        run_monte_carlo(pd.Series(np.linspace(10, 12, 20)), 30, 100)


def test_var_is_a_loss_not_a_price(price_series):
    """
    VaR phải là một KHOẢN LỖ. Bản cũ hiển thị np.percentile(giá, 5) — một mức giá —
    rồi gắn nhãn "VaR 95%".
    """
    m = mc_risk_metrics(run_monte_carlo(price_series, 60, 2000), 0.95)
    assert m["var_amount"] == pytest.approx(m["s0"] - m["q_low"])
    assert 0 < m["var_pct"] < 1
    assert m["cvar_amount"] > m["var_amount"], "CVaR phải nặng hơn VaR"


# ---------------------------------------------------------------- VaR / CVaR
def test_var_cvar_rejects_small_sample():
    """Bản cũ với n = 15 cho index = 0 -> CVaR = NaN mà app vẫn hiển thị."""
    with pytest.raises(ValueError, match="quan sát"):
        PortfolioOptimizer.calculate_var_cvar(pd.Series(np.random.randn(15) / 100))


def test_cvar_tail_includes_var_point():
    rng = np.random.default_rng(3)
    r = pd.Series(rng.normal(0, 0.02, 1000))
    out = PortfolioOptimizer.calculate_var_cvar(r, 0.95)
    assert out["n_tail"] >= 1
    assert not np.isnan(out["cvar_pct"])
    assert out["cvar_pct"] > out["var_pct"]


def test_efficient_frontier_is_monotone():
    """Đường biên thật: lợi suất mục tiêu tăng thì biến động tối thiểu không giảm."""
    rng = np.random.default_rng(5)
    rets = pd.DataFrame(rng.normal(0.0004, 0.015, (400, 4)), columns=list("ABCD"))
    ef = PortfolioOptimizer.efficient_frontier(rets.mean(), rets.cov(), n_points=15)
    assert len(ef) >= 5
    assert ef["vol"].iloc[-1] >= ef["vol"].min() - 1e-9
    assert np.allclose([w.sum() for w in ef["weights"]], 1.0)


# ---------------------------------------------------------------- CAPM
def test_capm_recovers_known_beta():
    """Dựng chuỗi có beta = 1.5 theo thiết kế và kiểm tra hồi quy tìm lại được."""
    rng = np.random.default_rng(11)
    n = 600
    rm = pd.Series(rng.normal(0.0004, 0.011, n))
    ri = 1.5 * rm + rng.normal(0, 0.004, n)
    out = capm(ri, rm)
    assert out["beta"] == pytest.approx(1.5, abs=0.08)
    assert "alpha_tstat" in out and "alpha_pvalue" in out   # bản cũ thiếu cả hai
    assert out["required_return"] == pytest.approx(
        out["market_premium"] * out["beta"] + 0.045, abs=1e-9)


def test_capm_handles_identical_series():
    """Chọn chính chỉ số làm mã phân tích: bản cũ tạo 2 cột trùng tên rồi vỡ OLS."""
    rng = np.random.default_rng(13)
    r = pd.Series(rng.normal(0.0003, 0.01, 300), name="VNINDEX")
    out = capm(r, r)
    assert out["beta"] == pytest.approx(1.0, abs=1e-6)
