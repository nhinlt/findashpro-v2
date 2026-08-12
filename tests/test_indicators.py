# tests/test_indicators.py
import os
import sys

import numpy as np
import pandas as pd
import pytest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.indicators import calculate_bollinger, calculate_ema, calculate_rsi, calculate_sma  # noqa: E402


def test_calculate_sma_correctness():
    """SMA phải là trung bình cộng trượt, và NaN cho tới khi đủ chu kỳ."""
    df = pd.DataFrame({"close": [10.0, 20.0, 30.0, 40.0, 50.0]})
    result = calculate_sma(df, window=3, column="close")

    assert np.isnan(result.iloc[0]), "Phiên 1 chưa đủ chu kỳ 3 -> phải là NaN"
    assert np.isnan(result.iloc[1]), "Phiên 2 chưa đủ chu kỳ 3 -> phải là NaN"
    assert result.iloc[2] == 20.0, "(10 + 20 + 30) / 3 = 20"
    assert result.iloc[4] == 40.0, "(30 + 40 + 50) / 3 = 40"


def test_calculate_sma_missing_column():
    """Thiếu cột được yêu cầu thì phải báo lỗi, không trả về im lặng."""
    with pytest.raises(KeyError):
        calculate_sma(pd.DataFrame({"open": [10, 20, 30]}))


def test_calculate_ema_reacts_faster_than_sma():
    """
    EMA đặt trọng số cao hơn cho dữ liệu mới nên phản ứng nhanh hơn NGAY SAU cú sốc.

    So sánh phải thực hiện ở phiên liền sau cú sốc: nếu để trôi đủ 5 phiên thì cửa sổ
    SMA đã chứa toàn giá mới và bằng đúng 20, trong khi EMA vẫn còn mang theo lịch sử.
    """
    df = pd.DataFrame({"close": [10.0] * 10 + [20.0]})
    ema = calculate_ema(df, window=5, column="close").iloc[-1]
    sma = calculate_sma(df, window=5, column="close").iloc[-1]
    assert ema > sma, f"EMA {ema:.3f} phải vượt SMA {sma:.3f} ngay sau cú sốc"


def test_rsi_bounded_and_extremes():
    """
    RSI theo Wilder phải nằm trong [0, 100]; chuỗi chỉ toàn phiên tăng -> RSI = 100.
    Bản cũ dùng rolling(14).mean() (trung bình động ĐƠN GIẢN) rồi vẫn gọi là RSI.
    """
    rising = pd.Series(np.arange(1, 61, dtype=float))
    rsi_up = calculate_rsi(rising, period=14).dropna()
    assert (rsi_up.between(0, 100)).all()
    assert rsi_up.iloc[-1] == pytest.approx(100.0)

    falling = pd.Series(np.arange(60, 0, -1, dtype=float))
    assert calculate_rsi(falling, period=14).dropna().iloc[-1] == pytest.approx(0.0, abs=1e-6)


def test_rsi_uses_wilder_smoothing():
    """Wilder (alpha = 1/14) phải cho kết quả KHÁC trung bình động đơn giản 14 kỳ."""
    rng = np.random.default_rng(0)
    close = pd.Series(100 * np.exp(np.cumsum(rng.normal(0, 0.015, 200))))

    wilder = calculate_rsi(close, 14)

    delta = close.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    simple = 100 - 100 / (1 + gain / loss.replace(0, np.nan))

    diff = (wilder - simple).dropna().abs()
    assert diff.max() > 1.0, "Hai phương pháp phải lệch nhau rõ rệt"


def test_bollinger_bands_ordering():
    """Dải trên >= dải giữa >= dải dưới, luôn luôn."""
    rng = np.random.default_rng(2)
    close = pd.Series(100 + np.cumsum(rng.normal(0, 1, 100)))
    up, mid, lo = calculate_bollinger(close, window=20, n_std=2.0)
    ok = up.notna()
    assert (up[ok] >= mid[ok]).all() and (mid[ok] >= lo[ok]).all()
