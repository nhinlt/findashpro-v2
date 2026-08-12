# core/portfolio_opt.py
"""
Tối ưu hóa danh mục Mean-Variance và đo lường rủi ro VaR / CVaR.

Bốn lỗi đã sửa:
  1. risk_free_rate hardcode 0.04 trong khi pages/4 dùng 0.045 -> nay đọc từ utils.config
  2. "Efficient Frontier" thực chất là đám mây điểm ngẫu nhiên. Với 4 mã, trọng số
     sinh bằng np.random.random() rồi chuẩn hóa chỉ vượt 0.9 trong 0.025% số lần —
     nghĩa là trong 1500 điểm, kỳ vọng 0.4 lần chạm được đầu mút đường biên.
     Nay có hàm efficient_frontier() GIẢI BÀI TOÁN TỐI ƯU tại từng mức lợi suất mục tiêu.
  3. calculate_var_cvar trả NaN im lặng khi mẫu nhỏ: index = int(0.05*15) = 0 nên
     .iloc[:0].mean() = NaN, còn VaR biến thành mức lỗ cực đại chứ không phải phân vị 5%.
  4. minimize() trả res.x mà không kiểm tra res.success -> tối ưu thất bại vẫn vẽ đồ thị.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy import stats

from utils.config import RANDOM_SEED, RISK_FREE_RATE, TRADING_DAYS

MIN_OBS_VAR = 100


class PortfolioOptimizer:
    """Tất cả tham số lợi suất đầu vào là LOG return theo phiên."""

    # ---------------- Hiệu năng ----------------
    @staticmethod
    def calculate_performance(weights, mean_returns, cov_matrix,
                              risk_free_rate: float = RISK_FREE_RATE):
        w = np.asarray(weights, dtype=float)
        p_ret = float(np.dot(mean_returns, w) * TRADING_DAYS)
        p_std = float(np.sqrt(w @ (np.asarray(cov_matrix) * TRADING_DAYS) @ w))
        sharpe = (p_ret - risk_free_rate) / p_std if p_std > 1e-12 else np.nan
        return p_ret, p_std, sharpe

    # ---------------- Tối ưu ----------------
    @classmethod
    def _solve(cls, objective, n_assets, extra_constraints=(), max_weight: float = 1.0):
        cons = [{"type": "eq", "fun": lambda w: np.sum(w) - 1.0}, *extra_constraints]
        bounds = tuple((0.0, max_weight) for _ in range(n_assets))  # long-only: TTCK VN không bán khống
        res = minimize(objective, np.repeat(1.0 / n_assets, n_assets),
                       method="SLSQP", bounds=bounds, constraints=cons,
                       options={"maxiter": 500, "ftol": 1e-10})
        if not res.success:
            raise RuntimeError(f"Bộ tối ưu SLSQP không hội tụ: {res.message}")
        return res.x

    @classmethod
    def optimize_sharpe(cls, mean_returns, cov_matrix,
                        risk_free_rate: float = RISK_FREE_RATE,
                        max_weight: float = 1.0) -> np.ndarray:
        def neg_sharpe(w):
            return -cls.calculate_performance(w, mean_returns, cov_matrix, risk_free_rate)[2]
        return cls._solve(neg_sharpe, len(mean_returns), max_weight=max_weight)

    @classmethod
    def optimize_min_variance(cls, mean_returns, cov_matrix,
                              max_weight: float = 1.0) -> np.ndarray:
        cov = np.asarray(cov_matrix) * TRADING_DAYS
        return cls._solve(lambda w: float(w @ cov @ w), len(mean_returns), max_weight=max_weight)

    # ---------------- Đường biên hiệu quả THẬT ----------------
    @classmethod
    def efficient_frontier(cls, mean_returns, cov_matrix,
                           n_points: int = 40, max_weight: float = 1.0) -> pd.DataFrame:
        """
        Với MỖI mức lợi suất mục tiêu R*, giải:
            min  wᵀΣw   s.t.  Σw = 1,  wᵀμ = R*,  0 ≤ w ≤ max_weight

        Đây mới là đường biên hiệu quả. Rắc N bộ trọng số ngẫu nhiên chỉ cho ra một
        đám mây tụ quanh danh mục đều và gần như không bao giờ chạm hai đầu mút.
        """
        n = len(mean_returns)
        ann_mu = np.asarray(mean_returns) * TRADING_DAYS
        ann_cov = np.asarray(cov_matrix) * TRADING_DAYS

        lo = float(cls.calculate_performance(
            cls.optimize_min_variance(mean_returns, cov_matrix, max_weight),
            mean_returns, cov_matrix)[0])
        hi = float(ann_mu.max())
        if hi <= lo:
            hi = lo * 1.05 + 1e-6

        rows = []
        for target in np.linspace(lo, hi, n_points):
            cons = ({"type": "eq", "fun": lambda w, t=target: float(w @ ann_mu) - t},)
            try:
                w = cls._solve(lambda w: float(w @ ann_cov @ w), n, cons, max_weight)
            except RuntimeError:
                continue                              # bỏ điểm không hội tụ, không im lặng nuốt lỗi
            ret, std, sharpe = cls.calculate_performance(w, mean_returns, cov_matrix)
            rows.append({"ret": ret, "vol": std, "sharpe": sharpe, "weights": w})

        if not rows:
            raise RuntimeError("Không giải được điểm nào trên đường biên hiệu quả.")
        return pd.DataFrame(rows)

    @classmethod
    def random_portfolios(cls, mean_returns, cov_matrix, n: int = 1500,
                          seed: int | None = RANDOM_SEED) -> pd.DataFrame:
        """
        Đám mây danh mục ngẫu nhiên — GỌI ĐÚNG TÊN, chỉ để làm nền minh họa.
        Dùng Dirichlet để phủ không gian trọng số đều hơn np.random.random() chuẩn hóa,
        và có seed để đám mây không nhảy mỗi lần rerun.
        """
        rng = np.random.default_rng(seed)
        n_assets = len(mean_returns)
        w = rng.dirichlet(np.ones(n_assets) * 0.6, size=n)   # alpha<1: phủ cả vùng tập trung
        out = [cls.calculate_performance(wi, mean_returns, cov_matrix) for wi in w]
        return pd.DataFrame(out, columns=["ret", "vol", "sharpe"])

    # ---------------- VaR / CVaR ----------------
    @staticmethod
    def calculate_var_cvar(returns: pd.Series, confidence_level: float = 0.95,
                           capital: float = 100_000_000) -> dict:
        """
        VaR lịch sử + VaR tham số (chuẩn) để đối chiếu.

        Ba sửa lỗi:
          - np.percentile CÓ nội suy tuyến tính, chính xác hơn iloc[int((1-c)*n)]
          - đuôi để tính CVaR BAO GỒM chính điểm VaR (r <= VaR), bản cũ dùng
            .iloc[:index] nên vừa loại nhầm điểm VaR vừa trả NaN khi index = 0
          - CHẶN mẫu nhỏ bằng ValueError thay vì hiển thị một con số vô nghĩa
        """
        r = pd.Series(returns).dropna()
        n = len(r)
        alpha = 1 - confidence_level

        if n < MIN_OBS_VAR:
            raise ValueError(
                f"Chỉ có {n} quan sát. VaR lịch sử ở mức {confidence_level:.0%} cần "
                f"ít nhất {MIN_OBS_VAR} quan sát — hiện vùng đuôi chỉ có khoảng "
                f"{int(n * alpha)} điểm, không đủ để ước lượng."
            )

        var_ret = float(np.percentile(r, alpha * 100))
        tail = r[r <= var_ret]
        cvar_ret = float(tail.mean())

        # VaR tham số: giả định chuẩn. So sánh với VaR lịch sử cho thấy đuôi dày.
        z = stats.norm.ppf(alpha)
        var_param = float(r.mean() + z * r.std(ddof=1))

        return {
            "var_pct": -var_ret,
            "var_amount": -var_ret * capital,
            "cvar_pct": -cvar_ret,
            "cvar_amount": -cvar_ret * capital,
            "var_param_pct": -var_param,
            "n_obs": n,
            "n_tail": len(tail),
            "confidence": confidence_level,
        }

    @staticmethod
    def kupiec_test(returns: pd.Series, var_pct: float, confidence_level: float = 0.95) -> dict:
        """
        Kiểm định Kupiec (POF): số lần lỗ vượt VaR có đúng bằng kỳ vọng không?

        Cần thiết vì VaR ở bản cũ được tính trên CHÍNH chuỗi dữ liệu đã dùng để tối ưu
        trọng số — tức VaR in-sample, luôn lạc quan hơn thực tế một cách có hệ thống.
        """
        r = pd.Series(returns).dropna()
        n, p = len(r), 1 - confidence_level
        x = int((r < -var_pct).sum())
        if x == 0 or x == n:
            return {"n": n, "violations": x, "expected": n * p, "lr": np.nan, "pvalue": np.nan}
        pi = x / n
        lr = -2 * ((n - x) * np.log(1 - p) + x * np.log(p)
                   - (n - x) * np.log(1 - pi) - x * np.log(pi))
        return {"n": n, "violations": x, "expected": n * p,
                "lr": float(lr), "pvalue": float(1 - stats.chi2.cdf(lr, df=1))}
