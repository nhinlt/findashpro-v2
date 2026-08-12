# ui/charts.py
"""
Biểu đồ Plotly dùng chung.

Ba thay đổi:
  1. Khối lượng chuyển từ secondary_y (kèm mẹo range=[0, max*3]) sang subplot 2 hàng
     chia sẻ trục X. Trục khối lượng nay đọc được số thật thay vì bị ẩn nhãn.
  2. Cột khối lượng tô màu theo phiên tăng/giảm — thông tin miễn phí, bản cũ bỏ phí.
  3. MỘT template cho toàn app (utils.config.PLOTLY_TEMPLATE) — nay là nền trắng.
     Bản cũ ép plotly_dark
     ở trang 1, 2, 4 nhưng plotly_white ở trang 5, 6 nên nền nhấp nháy khi chuyển trang.
"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from utils.config import (ACCENT, ACCENT_DOWN, ACCENT_FILL_LIGHT, ACCENT_FILL_MID,
                          ACCENT_UP, FONT_SANS, FONT_MONO, GRID, MUTED,
                          PLOTLY_TEMPLATE, PRICE_UNIT)


def apply_theme(fig: go.Figure, height: int = 520, title: str = "") -> go.Figure:
    fig.update_layout(
        template=PLOTLY_TEMPLATE, height=height, title=title or None,
        margin=dict(l=10, r=10, t=45 if title else 20, b=10),
        hovermode="x unified", plot_bgcolor="#FFFFFF", paper_bgcolor="#FFFFFF",
        legend=dict(orientation="h", yanchor="bottom", y=1.01, xanchor="right", x=1,
                    font=dict(family=FONT_SANS, size=12)),
        font=dict(family=FONT_SANS, size=12, color="#16202C"),
        title_font=dict(family=FONT_SANS, size=15, color="#16202C"),
    )
    # Trục: nhãn số dùng mono cho thẳng cột, lưới nhạt để không át dữ liệu
    fig.update_xaxes(showgrid=True, gridcolor=GRID, gridwidth=1, zeroline=False,
                     linecolor=GRID, tickfont=dict(family=FONT_MONO, size=11, color=MUTED),
                     title_font=dict(family=FONT_SANS, size=12, color=MUTED))
    fig.update_yaxes(showgrid=True, gridcolor=GRID, gridwidth=1, zeroline=False,
                     linecolor=GRID, tickfont=dict(family=FONT_MONO, size=11, color=MUTED),
                     title_font=dict(family=FONT_SANS, size=12, color=MUTED))
    return fig


def create_price_volume_chart(df: pd.DataFrame, ticker: str,
                              plot_type: str = "Candle",
                              overlays: dict[str, pd.Series] | None = None) -> go.Figure:
    """Giá + khối lượng, hai hàng chia sẻ trục X. df dùng cột chữ thường."""
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                        vertical_spacing=0.04, row_heights=[0.74, 0.26])

    if plot_type == "Candle":
        fig.add_trace(go.Candlestick(
            x=df.index, open=df["open"], high=df["high"], low=df["low"], close=df["close"],
            name="Giá", increasing_line_color=ACCENT_UP, decreasing_line_color=ACCENT_DOWN,
        ), row=1, col=1)
    elif plot_type == "OHLC":
        fig.add_trace(go.Ohlc(
            x=df.index, open=df["open"], high=df["high"], low=df["low"], close=df["close"],
            name="Giá", increasing_line_color=ACCENT_UP, decreasing_line_color=ACCENT_DOWN,
        ), row=1, col=1)
    else:
        fig.add_trace(go.Scatter(x=df.index, y=df["close"], mode="lines",
                                 name="Đóng cửa", line=dict(color=ACCENT, width=1.6)),
                      row=1, col=1)

    for name, series in (overlays or {}).items():
        fig.add_trace(go.Scatter(x=df.index, y=series, mode="lines", name=name,
                                 line=dict(width=1.2)), row=1, col=1)

    colors = [ACCENT_UP if c >= o else ACCENT_DOWN
              for o, c in zip(df["open"], df["close"])]
    fig.add_trace(go.Bar(x=df.index, y=df["volume"], name="Khối lượng",
                         marker_color=colors, opacity=0.55), row=2, col=1)

    fig.update_xaxes(rangeslider_visible=False)
    fig.update_yaxes(title_text=f"Giá ({PRICE_UNIT})", row=1, col=1)
    fig.update_yaxes(title_text="KL", row=2, col=1)
    return apply_theme(fig, height=620, title=f"{ticker} — giá và khối lượng")


def create_fan_chart(bands: pd.DataFrame, title: str = "") -> go.Figure:
    """Biểu đồ quạt phân vị — đọc được hơn 100 đường mô phỏng chồng lên nhau."""
    fig = go.Figure()
    pairs = [("P5", "P95", ACCENT_FILL_LIGHT), ("P25", "P75", ACCENT_FILL_MID)]
    for lo, hi, fill in pairs:
        if lo in bands and hi in bands:
            fig.add_trace(go.Scatter(x=bands.index, y=bands[hi], line=dict(width=0),
                                     showlegend=False, hoverinfo="skip"))
            fig.add_trace(go.Scatter(x=bands.index, y=bands[lo], fill="tonexty",
                                     fillcolor=fill, line=dict(width=0),
                                     name=f"{lo}–{hi}"))
    if "P50" in bands:
        fig.add_trace(go.Scatter(x=bands.index, y=bands["P50"], name="Trung vị",
                                 line=dict(color=ACCENT, width=2)))
    fig.update_xaxes(title_text="Số phiên kể từ hôm nay")   # nhãn ĐÚNG với trục
    fig.update_yaxes(title_text=f"Giá ({PRICE_UNIT})")
    return apply_theme(fig, height=460, title=title)
