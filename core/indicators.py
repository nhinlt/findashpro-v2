# core/indicators.py
"""Chỉ báo kỹ thuật. RSI đã sửa về đúng phương pháp làm mượt của Wilder."""
from __future__ import annotations

import numpy as np
import pandas as pd


def calculate_sma(df: pd.DataFrame, window: int = 50, column: str = "close") -> pd.Series:
    """Trung bình động đơn giản."""
    return df[column].rolling(window=window).mean()


def calculate_ema(df: pd.DataFrame, window: int = 20, column: str = "close") -> pd.Series:
    """Trung bình động lũy thừa."""
    return df[column].ewm(span=window, adjust=False).mean()


def calculate_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """
    RSI theo ĐÚNG phương pháp Wilder (1978): làm mượt lũy thừa với alpha = 1/period.

    Bản cũ dùng rolling(14).mean() — tức trung bình động ĐƠN GIẢN — rồi vẫn gọi là RSI.
    Hai cách cho kết quả lệch rõ rệt trong 30-50 phiên đầu.
    """
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)

    avg_gain = gain.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()

    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    rsi = 100.0 - 100.0 / (1.0 + rs)
    # avg_loss == 0 nghĩa là chuỗi chỉ toàn phiên tăng -> RSI = 100 theo định nghĩa
    return rsi.where(avg_loss != 0, 100.0).where(avg_gain.notna())


def calculate_bollinger(close: pd.Series, window: int = 20, n_std: float = 2.0):
    """Dải Bollinger. Dùng ddof=1 vì đây là độ lệch chuẩn MẪU."""
    mid = close.rolling(window).mean()
    sd = close.rolling(window).std(ddof=1)
    return mid + n_std * sd, mid, mid - n_std * sd


def calculate_macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    """MACD, đường tín hiệu và histogram."""
    macd = (close.ewm(span=fast, adjust=False).mean()
            - close.ewm(span=slow, adjust=False).mean())
    sig = macd.ewm(span=signal, adjust=False).mean()
    return macd, sig, macd - sig
