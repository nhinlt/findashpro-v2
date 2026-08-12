# data/mock_data.py
"""
Dữ liệu dự phòng khi API sập.

Endpoint services.entrade.com.vn/chart-api/v2 là API nội bộ, không có tài liệu
công khai và không cam kết ổn định. Nếu nó đổi hoặc chặn đúng hôm bảo vệ thì app
phải vẫn chạy được — với nhãn cảnh báo rõ ràng rằng đây là dữ liệu mô phỏng.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

# Neo tham số theo mã để cùng một mã luôn cho ra cùng một chuỗi (tái lập được)
_PROFILE: dict[str, tuple[float, float, float]] = {
    # ticker: (giá gốc, drift năm, biến động năm)
    "VCB": (62.0, 0.12, 0.24), "FPT": (118.0, 0.28, 0.30), "HPG": (26.0, 0.10, 0.35),
    "VNM": (64.0, 0.02, 0.22), "VIC": (42.0, -0.05, 0.42), "MWG": (58.0, 0.18, 0.38),
    "VNINDEX": (1265.0, 0.09, 0.16), "VN30": (1340.0, 0.10, 0.18),
}
_DEFAULT = (50.0, 0.08, 0.30)


def generate_ohlcv(ticker: str, days: int = 365, seed: int | None = None) -> pd.DataFrame:
    """Sinh chuỗi OHLCV giả lập theo GBM. Cột chữ thường, khớp với dnse_client."""
    ticker = ticker.upper()
    s0, mu, sigma = _PROFILE.get(ticker, _DEFAULT)
    if seed is None:
        seed = abs(hash(ticker)) % (2**31)      # cùng mã -> cùng chuỗi
    rng = np.random.default_rng(seed)

    n = max(int(days * 252 / 365), 30)          # ngày lịch -> phiên giao dịch
    dt = 1 / 252
    steps = (mu - 0.5 * sigma**2) * dt + sigma * np.sqrt(dt) * rng.standard_normal(n)
    close = s0 * np.exp(np.cumsum(steps))

    intraday = np.abs(rng.normal(0, 0.008, n))
    open_ = close * (1 + rng.normal(0, 0.004, n))
    high = np.maximum(open_, close) * (1 + intraday)
    low = np.minimum(open_, close) * (1 - intraday)
    volume = rng.lognormal(mean=14.2, sigma=0.55, size=n).round()

    idx = pd.bdate_range(end=pd.Timestamp.today().normalize(), periods=n, name="date")
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": volume},
        index=idx,
    ).round(2)
