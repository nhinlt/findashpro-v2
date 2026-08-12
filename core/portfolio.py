# core/portfolio.py
"""
Mô hình định giá tài sản: CAPM và APT (yêu cầu [4]), cùng các hàm dựng danh mục.

File này trước đây RỖNG (chỉ có một dòng comment) — trong khi APT là hạng mục
đề bài yêu cầu đích danh và không tồn tại một dòng nào trong repo.

Ba lỗi CAPM của bản cũ đã sửa:
  1. Không có t-statistic / p-value của alpha. Alpha = 0.000123 mà t = 0.3 thì
     KHÔNG khác 0 về mặt thống kê; kết luận "cổ phiếu tạo alpha" là sai.
  2. Alpha không năm hóa -> con số 6 chữ số thập phân vô nghĩa với người đọc.
  3. Metric hồi quy trên EXCESS return nhưng biểu đồ vẽ trên RAW return, nên hệ số
     chặn trên hình không bằng Alpha in ra. Nay hàm trả về chính bộ dữ liệu đã hồi
     quy ('data') để trang UI vẽ đúng thứ đã tính.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.stats.outliers_influence import variance_inflation_factor

from core.quantitative import log_returns
from utils.config import RISK_FREE_RATE, TRADING_DAYS, daily_rf

MIN_OBS = 60


def _align(y: pd.Series, x: pd.DataFrame | pd.Series) -> pd.DataFrame:
    """
    Ghép theo giao ngày giao dịch. rename('ri') là bắt buộc: nếu người dùng chọn
    chính VNINDEX làm mã phân tích thì hai Series trùng tên -> DataFrame có 2 cột
    cùng tên -> data['VNINDEX'] trả DataFrame chứ không phải Series -> OLS vỡ.
    """
    x = x.to_frame() if isinstance(x, pd.Series) else x
    return pd.concat([y.rename("ri"), x], axis=1, join="inner").dropna()


# ---------------------------------------------------------------------------
# CAPM
# ---------------------------------------------------------------------------
def capm(stock_ret: pd.Series, market_ret: pd.Series) -> dict:
    """
    CAPM đầy đủ:  R_i − R_f = α + β(R_m − R_f) + ε

    Và — điều bản cũ bỏ qua hoàn toàn — DÙNG β để định giá:
        E(R_i) = R_f + β · [E(R_m) − R_f]
    CAPM tồn tại để tính lợi suất YÊU CẦU, không phải để in ra một con số beta rồi thôi.
    """
    d = _align(stock_ret, market_ret.rename("rm"))
    if len(d) < MIN_OBS:
        raise ValueError(f"Chỉ có {len(d)} phiên giao nhau — cần ít nhất {MIN_OBS}.")

    rf_d = daily_rf()
    d = d.assign(ri_ex=d["ri"] - rf_d, rm_ex=d["rm"] - rf_d)

    model = sm.OLS(d["ri_ex"], sm.add_constant(d["rm_ex"])).fit()

    beta = float(model.params["rm_ex"])
    alpha_d = float(model.params["const"])
    market_premium = float(d["rm"].mean()) * TRADING_DAYS - RISK_FREE_RATE
    required = RISK_FREE_RATE + beta * market_premium
    actual = float(d["ri"].mean()) * TRADING_DAYS

    return {
        "beta": beta,
        "beta_tstat": float(model.tvalues["rm_ex"]),
        "beta_pvalue": float(model.pvalues["rm_ex"]),
        "beta_ci": tuple(model.conf_int().loc["rm_ex"]),
        "alpha_daily": alpha_d,
        "alpha_annual": alpha_d * TRADING_DAYS,           # năm hóa, đọc được
        "alpha_tstat": float(model.tvalues["const"]),     # BẮT BUỘC phải báo cáo
        "alpha_pvalue": float(model.pvalues["const"]),
        "alpha_significant": bool(model.pvalues["const"] < 0.05),
        "r_squared": float(model.rsquared),
        "market_premium": market_premium,
        "required_return": required,                      # CAPM dùng để ĐỊNH GIÁ
        "actual_return": actual,
        "jensen_alpha": actual - required,                # >0: vượt kỳ vọng CAPM
        "n_obs": len(d),
        "data": d,          # trang UI vẽ CHÍNH bộ này -> hình khớp số
        "model": model,
    }


def security_market_line(beta_max: float = 2.0, market_premium: float = 0.08) -> pd.DataFrame:
    """Đường SML: E(R) = Rf + β·MRP. Dùng để định vị cổ phiếu là đắt hay rẻ."""
    betas = np.linspace(0, beta_max, 50)
    return pd.DataFrame({"beta": betas, "required_return": RISK_FREE_RATE + betas * market_premium})


# ---------------------------------------------------------------------------
# APT
# ---------------------------------------------------------------------------
def build_factors(market_close: pd.Series, size_close: pd.Series | None = None) -> pd.DataFrame:
    """
    Dựng bộ nhân tố cho APT từ chính dữ liệu chỉ số mà dnse_client đã hỗ trợ sẵn
    (tham số is_index) — không cần thêm nguồn API mới trước ngày bảo vệ.

      MKT  : lợi suất VNINDEX, nhân tố thị trường
      SIZE : VN30 − VNINDEX, chênh lệch vốn hóa lớn so với toàn thị trường
             (proxy cho nhân tố quy mô; dấu ngược với SMB của Fama–French)
      MOM  : động lượng thị trường, trung bình 20 phiên của VNINDEX, ĐÃ shift(1)
             để tránh look-ahead bias
    """
    mkt = log_returns(market_close).rename("MKT")
    cols = {"MKT": mkt, "MOM": mkt.rolling(20).mean().shift(1).rename("MOM")}

    if size_close is not None and not size_close.empty:
        size = log_returns(size_close)
        cols["SIZE"] = (size - mkt).dropna().rename("SIZE")

    return pd.DataFrame(cols).dropna()


def apt(stock_ret: pd.Series, factors: pd.DataFrame) -> dict:
    """
    APT — Arbitrage Pricing Theory (Ross, 1976):

        R_i − R_f = α + Σ_k β_k · F_k + ε

    Khác CAPM ở chỗ không giả định tồn tại một danh mục thị trường duy nhất; lợi
    suất được giải thích bằng NHIỀU nguồn rủi ro hệ thống. So sánh Adjusted R² của
    APT với CAPM chính là cách trả lời "tại sao đề bài bắt làm cả hai".
    """
    d = _align(stock_ret, factors)
    if len(d) < MIN_OBS:
        raise ValueError(f"Chỉ có {len(d)} phiên giao nhau — cần ít nhất {MIN_OBS}.")

    names = list(factors.columns)
    y = d["ri"] - daily_rf()
    x = sm.add_constant(d[names])
    model = sm.OLS(y, x).fit()

    table = pd.DataFrame({
        "Nhân tố": ["Alpha"] + names,
        "Hệ số β": model.params.to_numpy(),
        "Sai số chuẩn": model.bse.to_numpy(),
        "t-statistic": model.tvalues.to_numpy(),
        "p-value": model.pvalues.to_numpy(),
        "Có ý nghĩa (5%)": ["Có" if p < 0.05 else "Không" for p in model.pvalues],
    })

    # VIF: kiểm tra đa cộng tuyến — câu hỏi kinh điển với mọi mô hình đa nhân tố
    xv = x.to_numpy()
    vif = {n: float(variance_inflation_factor(xv, i + 1)) for i, n in enumerate(names)}

    return {
        "table": table,
        "r_squared": float(model.rsquared),
        "adj_r_squared": float(model.rsquared_adj),
        "f_pvalue": float(model.f_pvalue),
        "alpha_annual": float(model.params["const"]) * TRADING_DAYS,
        "alpha_pvalue": float(model.pvalues["const"]),
        "vif": vif,
        "n_obs": len(d),
        "factors": names,
        "model": model,
    }


# ---------------------------------------------------------------------------
# DANH MỤC
# ---------------------------------------------------------------------------
def normalize_weights(weights: dict[str, float]) -> dict[str, float]:
    total = sum(weights.values())
    if total <= 0:
        raise ValueError("Tổng tỷ trọng phải lớn hơn 0.")
    return {k: v / total for k, v in weights.items()}


def portfolio_series(prices: pd.DataFrame, weights: dict[str, float],
                     capital: float) -> pd.DataFrame:
    """
    NAV danh mục theo phương pháp MUA VÀ NẮM GIỮ: phân bổ vốn theo tỷ trọng tại
    phiên đầu, mua số cổ phiếu tương ứng rồi giữ nguyên. Tỷ trọng sau đó TRÔI theo
    giá — đúng với thực tế, khác với giả định tái cân bằng hằng ngày.
    """
    w = normalize_weights({k: v for k, v in weights.items() if k in prices.columns})
    px = prices[list(w)].dropna()
    if px.empty:
        raise ValueError("Không có phiên nào mà tất cả các mã đều có giá.")

    shares = pd.Series({t: capital * wt / px[t].iloc[0] for t, wt in w.items()})
    positions = px.mul(shares, axis=1)
    nav = positions.sum(axis=1)

    return pd.DataFrame({
        "nav": nav,
        "pnl": nav - capital,
        "return_pct": nav / capital - 1.0,
    }).join(positions.add_prefix("pos_"))


def portfolio_returns(prices: pd.DataFrame, weights: dict[str, float]) -> pd.Series:
    """Chuỗi log return của danh mục — đầu vào cho CAPM/APT ở cấp danh mục."""
    nav = portfolio_series(prices, weights, capital=1.0)["nav"]
    return log_returns(nav).rename("PORTFOLIO")
