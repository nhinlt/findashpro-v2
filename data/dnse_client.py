# data/dnse_client.py
"""
Lớp truy cập dữ liệu giá (DNSE / entrade).

Ba thay đổi so với bản cũ:
  1. Chuẩn hóa TÊN CỘT VỀ CHỮ THƯỜNG ngay tại nguồn. Bản cũ trả 'Close' viết hoa
     rồi các trang 5, 6 tự gọi .str.lower() — và nổ AttributeError khi DataFrame rỗng.
  2. KHÔNG ffill() khối lượng. Khối lượng khuyết nghĩa là không giao dịch -> 0,
     không phải "bằng hôm qua". Nội suy thanh khoản là bịa dữ liệu.
  3. Thêm get_ohlcv(): hàm DUY NHẤT mà tầng UI được gọi. Có cache, có guard,
     luôn trả về DataFrame ĐÚNG SCHEMA (kể cả khi rỗng) nên không trang nào crash nữa.
"""
from __future__ import annotations

from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import requests
import streamlit as st

from data.mock_data import generate_ohlcv
from utils.config import is_index as _is_index
from utils.logger import get_logger

log = get_logger("dnse")

BASE_URL = "https://services.entrade.com.vn/chart-api/v2/ohlcs"
OHLCV = ["open", "high", "low", "close", "volume"]

# Quy tắc gộp nến — yêu cầu [2]: lấy mẫu theo ngày/tuần/tháng
_AGG = {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
SAMPLING = {"Ngày": None, "Tuần": "W-FRI", "Tháng": "ME", "Quý": "QE"}


def empty_ohlcv() -> pd.DataFrame:
    """DataFrame rỗng NHƯNG ĐÚNG SCHEMA. Đây là thứ chống crash cả app."""
    return pd.DataFrame(columns=OHLCV, index=pd.DatetimeIndex([], name="date"))


def clean_financial_data(df: pd.DataFrame) -> pd.DataFrame:
    """Vệ sinh dữ liệu giá. Mỗi bước dưới đây tương ứng một lỗi đã bị bắt."""
    if df.empty:
        return df

    df = df.replace([np.inf, -np.inf], np.nan)

    # Không có giá đóng cửa thì không tính được gì -> bỏ hàng
    if "close" in df.columns:
        df = df.dropna(subset=["close"])

    # Khối lượng khuyết = phiên không có giao dịch = 0. TUYỆT ĐỐI KHÔNG ffill.
    if "volume" in df.columns:
        df["volume"] = df["volume"].fillna(0.0)

    # OHL khuyết thì suy từ close (nến doji), vẫn tốt hơn là bỏ cả phiên
    for col in ("open", "high", "low"):
        if col in df.columns and "close" in df.columns:
            df[col] = df[col].fillna(df["close"])

    return df.sort_index()


def fetch_historical_data(
    ticker: str,
    start_timestamp: int,
    end_timestamp: int,
    resolution: str = "1D",
    is_index: bool | None = None,
) -> pd.DataFrame:
    """Gọi API thô. Trả về OHLCV chữ thường, index là DatetimeIndex tên 'date'."""
    ticker = ticker.strip().upper()
    if is_index is None:
        is_index = _is_index(ticker)

    url = f"{BASE_URL}/{'index' if is_index else 'stock'}"
    params = {
        "symbol": ticker,
        "from": start_timestamp,
        "to": end_timestamp,
        "resolution": resolution,
    }

    try:
        r = requests.get(url, params=params, timeout=10,
                         headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
        payload = r.json()

        if not payload or "t" not in payload or not payload["t"]:
            log.warning("API không trả dữ liệu cho %s", ticker)
            return empty_ohlcv()

        n = len(payload["t"])
        df = pd.DataFrame(
            {
                "date": pd.to_datetime(payload["t"], unit="s"),
                "open": payload.get("o", [np.nan] * n),
                "high": payload.get("h", [np.nan] * n),
                "low": payload.get("l", [np.nan] * n),
                "close": payload.get("c", [np.nan] * n),
                "volume": payload.get("v") or [0.0] * n,
            }
        )
        df["date"] = df["date"].dt.normalize()
        df = df.set_index("date")
        return clean_financial_data(df)

    except Exception as exc:                      # noqa: BLE001
        log.error("Lỗi lấy dữ liệu %s: %s", ticker, exc)
        return empty_ohlcv()


@st.cache_data(ttl=300, show_spinner=False)
def get_ohlcv(
    ticker: str,
    days: int = 365,
    resolution: str = "1D",
    min_rows: int = 2,
    allow_mock: bool = True,
) -> tuple[pd.DataFrame, str]:
    """
    Hàm DUY NHẤT mà tầng UI được phép gọi.

    Trả về (df, nguồn) với nguồn ∈ {"live", "mock", "empty"}.
    Luôn có đủ 5 cột OHLCV kể cả khi rỗng -> mọi phép .columns, ['close'] đều an toàn.
    """
    ticker = ticker.strip().upper()
    if not ticker:
        return empty_ohlcv(), "empty"

    end_ts = int(datetime.now().timestamp())
    start_ts = int((datetime.now() - timedelta(days=days)).timestamp())

    df = fetch_historical_data(ticker, start_ts, end_ts, resolution=resolution)

    if not df.empty and len(df) >= min_rows:
        return df, "live"

    if allow_mock:
        log.warning("Chuyển sang dữ liệu mô phỏng cho %s", ticker)
        return generate_ohlcv(ticker, days), "mock"

    return empty_ohlcv(), "empty"


def resample_ohlcv(df: pd.DataFrame, label: str) -> pd.DataFrame:
    """
    Lấy mẫu theo Ngày/Tuần/Tháng/Quý (yêu cầu [2]).

    Gộp phía client thay vì gửi resolution='1W' lên API, vì chart-api/v2 không cam kết
    hỗ trợ khung tuần/tháng. Gộp ở đây cũng cho phép kiểm soát minh bạch quy tắc OHLCV:
    open = giá mở cửa phiên ĐẦU kỳ, high/low = max/min cả kỳ, close = phiên CUỐI kỳ,
    volume = TỔNG (không phải trung bình).
    """
    rule = SAMPLING.get(label)
    if rule is None or df.empty:
        return df
    agg = {k: v for k, v in _AGG.items() if k in df.columns}
    return df.resample(rule).agg(agg).dropna(subset=["close"])
