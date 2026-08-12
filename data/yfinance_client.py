# data/yfinance_client.py
"""
Lớp truy cập dữ liệu cơ bản (Yahoo Finance).

Ba lỗi đã sửa:
  1. BỎ fillna(0.0) trên báo cáo tài chính. "API không trả dữ liệu" KHÁC "khoản mục
     bằng 0". Điền 0 cho Total Revenue khuyết sẽ biến doanh thu quý thành 0 và mọi
     biên lợi nhuận suy ra đều sai — đó là bịa dữ liệu một cách vô tình.
  2. BỎ hardcode f"{ticker}.VN". Bản cũ khiến app KHÔNG THỂ phân tích cổ phiếu thế
     giới, trong khi giao diện lại quảng cáo "luồng dữ liệu toàn cầu".
  3. Thêm cache. Bản cũ gọi yf.Ticker().info — API chậm nhất và dễ rate-limit nhất —
     trên MỌI lần rerun của Streamlit.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st
import yfinance as yf

from utils.logger import get_logger

log = get_logger("yfinance")

MARKETS = {"Việt Nam (HOSE/HNX)": ".VN", "Quốc tế (US/EU/…)": ""}


def to_symbol(ticker: str, suffix: str = ".VN") -> str:
    """VCB + '.VN' -> 'VCB.VN' ; AAPL + '' -> 'AAPL'."""
    return f"{ticker.strip().upper()}{suffix}"


def clean_yfinance_data(df: pd.DataFrame, is_financial_statement: bool = False) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()

    df = df.replace([np.inf, -np.inf], np.nan)

    if is_financial_statement:
        df = df.dropna(how="all")
        # KHÔNG fillna(0). NaN được giữ nguyên để người đọc THẤY ô trống và biết
        # đó là dữ liệu thiếu. Pandas/Plotly tự bỏ qua NaN khi tính và vẽ.
    return df


@st.cache_data(ttl=900, show_spinner=False)
def fetch_company_profile(ticker: str, suffix: str = ".VN") -> dict:
    """Hồ sơ doanh nghiệp cho trang Summary (yêu cầu [1])."""
    try:
        info = yf.Ticker(to_symbol(ticker, suffix)).info or {}
    except Exception as exc:                       # noqa: BLE001
        log.error("Lỗi profile %s: %s", ticker, exc)
        return {}

    return {
        "Tên công ty": info.get("longName") or info.get("shortName"),
        "Sàn niêm yết": info.get("exchange"),
        "Ngành": info.get("sector"),
        "Lĩnh vực": info.get("industry"),
        "Vốn hóa": info.get("marketCap"),
        "CP lưu hành": info.get("sharesOutstanding"),
        "Tiền tệ": info.get("currency"),
        "Website": info.get("website"),
        "Mô tả": info.get("longBusinessSummary"),
    }


@st.cache_data(ttl=900, show_spinner=False)
def fetch_financial_ratios(ticker: str, suffix: str = ".VN") -> pd.DataFrame:
    """
    Chỉ số định giá. Trả về DataFrame 2 cột (Chỉ số / Giá trị) đã ĐỊNH DẠNG SẴN,
    vì bản cũ hiển thị ROE dạng thập phân thô 0.2134 không có dấu %.
    """
    try:
        info = yf.Ticker(to_symbol(ticker, suffix)).info or {}
    except Exception as exc:                       # noqa: BLE001
        log.error("Lỗi ratios %s: %s", ticker, exc)
        return pd.DataFrame()

    cur = info.get("currency", "")
    raw = {
        "P/E (trailing)": (info.get("trailingPE"), "x"),
        "P/E (forward)": (info.get("forwardPE"), "x"),
        "P/B": (info.get("priceToBook"), "x"),
        "EPS (trailing)": (info.get("trailingEps"), cur),
        "ROE": (info.get("returnOnEquity"), "%"),
        "ROA": (info.get("returnOnAssets"), "%"),
        "Biên LN gộp": (info.get("grossMargins"), "%"),
        "Biên LN ròng": (info.get("profitMargins"), "%"),
        "Nợ / Vốn CSH": (info.get("debtToEquity"), "%"),
        "Tỷ suất cổ tức": (info.get("dividendYield"), "%"),
        "Beta (Yahoo)": (info.get("beta"), "x"),
        f"Vốn hóa ({cur})": (info.get("marketCap"), "tiền"),
    }

    rows = []
    for name, (val, unit) in raw.items():
        if val is None or (isinstance(val, float) and np.isnan(val)):
            shown = "—"                     # ô trống trung thực, KHÔNG phải số 0
        elif unit == "%":
            shown = f"{val:.2%}"
        elif unit == "tiền":
            shown = f"{val/1e9:,.0f} tỷ"
        elif unit == "x":
            shown = f"{val:,.2f}x"
        else:
            shown = f"{val:,.2f} {unit}".strip()
        rows.append({"Chỉ số": name, "Giá trị": shown, "_missing": shown == "—"})

    return pd.DataFrame(rows)


def coverage(df_ratios: pd.DataFrame) -> float:
    """Tỷ lệ trường bị thiếu — dùng để cảnh báo trung thực thay vì hiện bảng NaN im lặng."""
    if df_ratios.empty or "_missing" not in df_ratios.columns:
        return 1.0
    return float(df_ratios["_missing"].mean())


@st.cache_data(ttl=900, show_spinner=False)
def fetch_statement(ticker: str, kind: str = "income",
                    is_yearly: bool = False, suffix: str = ".VN") -> pd.DataFrame:
    """
    Báo cáo tài chính. Bản cũ chỉ có Income Statement; yêu cầu [3] cần đủ bộ.
    kind ∈ {"income", "balance", "cashflow"}
    """
    try:
        stock = yf.Ticker(to_symbol(ticker, suffix))
        table = {
            ("income", True): "financials", ("income", False): "quarterly_financials",
            ("balance", True): "balance_sheet", ("balance", False): "quarterly_balance_sheet",
            ("cashflow", True): "cashflow", ("cashflow", False): "quarterly_cashflow",
        }[(kind, is_yearly)]
        raw = getattr(stock, table)
    except Exception as exc:                       # noqa: BLE001
        log.error("Lỗi %s %s: %s", kind, ticker, exc)
        return pd.DataFrame()

    df = clean_yfinance_data(raw, is_financial_statement=True)
    if not df.empty:
        df.columns = [c.strftime("%Y-%m-%d") if hasattr(c, "strftime") else str(c)
                      for c in df.columns]
    return df


# Giữ tên hàm cũ để không phá vỡ mã đã import ở nơi khác
def fetch_income_statement(ticker: str, is_yearly: bool = False,
                           suffix: str = ".VN") -> pd.DataFrame:
    return fetch_statement(ticker, "income", is_yearly, suffix)
