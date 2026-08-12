# core/alpha_engine.py
"""
Động cơ tín hiệu Alpha và backtest.

Bản cũ giữ được hai điều đúng — signal.shift(1) chống look-ahead và có tính phí
giao dịch — nhưng vi phạm hai đặc thù của thị trường Việt Nam và đặt sai tên hai
chỉ số. Đã sửa:

  1. BÁN KHỐNG: np.clip(position, -1, 1) cho phép vị thế âm. TTCK Việt Nam KHÔNG
     có bán khống cổ phiếu. Nghiêm trọng nhất với Mean_Reversion_ZScore vì tín hiệu
     đối xứng quanh 0 -> khoảng một nửa hiệu suất đến từ giao dịch không thực hiện được.
  2. THANH TOÁN T+2: bản cũ đảo vị thế hằng ngày. Trên HOSE, cổ phiếu mua phiên T
     chỉ bán được từ T+2. Đường equity cũ là không khả thi về vận hành.
  3. "Sharpe Ratio" không trừ lãi suất phi rủi ro -> đó là Information Ratio so với
     tiền mặt 0%. Nay tính đúng Sharpe VÀ báo cáo riêng Information Ratio.
  4. "Tỷ lệ thắng" tính trên NGÀY chứ không trên LỆNH. Biến tên là active_trades
     nhưng nội dung là lợi suất theo ngày. Nay gộp thành lệnh thật.
  5. Comment "RSI đảo chiều" mâu thuẫn công thức (rsi-50)/50 vốn là THUẬN xu hướng.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from core.indicators import calculate_rsi
from utils.config import (ALLOW_SHORT, EXECUTION_LAG, RISK_FREE_RATE,
                          SETTLEMENT_LAG, TRADING_DAYS, TRANSACTION_COST)

SIGNALS = ["Momentum_RSI", "Mean_Reversion_ZScore", "Volume_Price_Trend", "Momentum_5D"]


class AlphaEngine:

    # ------------------------------------------------------------------
    @staticmethod
    def calculate_alpha_signal(df: pd.DataFrame, expression_type: str = "Momentum_RSI") -> pd.Series:
        """Sinh tín hiệu trong khoảng [-1, 1]. df cần cột: close, volume."""
        data = df.copy()

        if expression_type == "Momentum_RSI":
            # THUẬN xu hướng: RSI > 50 -> mua. (Bản cũ ghi comment "đảo chiều" là sai.)
            rsi = calculate_rsi(data["close"], period=14)
            signal = (rsi - 50.0) / 50.0

        elif expression_type == "Mean_Reversion_ZScore":
            # ĐẢO CHIỀU: giá lệch xa trung bình 20 phiên thì kỳ vọng quay về
            sma20 = data["close"].rolling(20).mean()
            std20 = data["close"].rolling(20).std(ddof=1)
            signal = -((data["close"] - sma20) / std20.replace(0, np.nan))

        elif expression_type == "Volume_Price_Trend":
            ret = data["close"].pct_change()
            vol_sma = data["volume"].rolling(20).mean()
            signal = ret * (data["volume"] / vol_sma.replace(0, np.nan))

        else:  # Momentum_5D
            signal = data["close"].pct_change(5) * 10

        return signal.clip(-1.0, 1.0).fillna(0.0)

    # ------------------------------------------------------------------
    @staticmethod
    def _apply_settlement(position: np.ndarray, lag: int) -> np.ndarray:
        """
        Ràng buộc T+2: sau khi TĂNG vị thế ở phiên i, không được giảm trong `lag`
        phiên kế tiếp vì cổ phiếu chưa về tài khoản.
        """
        if lag <= 0:
            return position
        pos = position.copy()
        last_buy = -(10**9)
        for i in range(1, len(pos)):
            if pos[i] > pos[i - 1]:
                last_buy = i
            elif pos[i] < pos[i - 1] and (i - last_buy) <= lag:
                pos[i] = pos[i - 1]          # chưa về hàng -> giữ nguyên
        return pos

    # ------------------------------------------------------------------
    @staticmethod
    def backtest_signal(
        df: pd.DataFrame,
        signal: pd.Series,
        initial_capital: float = 100_000_000.0,
        transaction_cost: float = TRANSACTION_COST,
        allow_short: bool = ALLOW_SHORT,
        execution_lag: int = EXECUTION_LAG,
        settlement_lag: int = SETTLEMENT_LAG,
    ) -> dict:
        """Backtest vector hóa, có phí, có ràng buộc vi cấu trúc thị trường VN."""
        if df.empty or len(df) < 30:
            raise ValueError(f"Chỉ có {len(df)} phiên — quá ít để backtest (cần ≥ 30).")

        data = df.copy()
        data["signal"] = signal.reindex(data.index).fillna(0.0)

        # shift(execution_lag): tín hiệu chốt hết phiên T, khớp lệnh phiên T+1.
        # Đây là điều bản cũ đã làm đúng và phải giữ lại.
        lower = -1.0 if allow_short else 0.0        # long-only cho thị trường VN
        pos = data["signal"].shift(execution_lag).fillna(0.0).clip(lower, 1.0).to_numpy()
        data["position"] = AlphaEngine._apply_settlement(pos, settlement_lag)

        data["turnover"] = data["position"].diff().abs().fillna(0.0)
        data["market_return"] = data["close"].pct_change().fillna(0.0)
        data["strategy_return"] = (data["position"] * data["market_return"]
                                   - data["turnover"] * transaction_cost)

        data["cum_market_return"] = (1 + data["market_return"]).cumprod()
        data["cum_strategy_return"] = (1 + data["strategy_return"]).cumprod()
        data["equity"] = initial_capital * data["cum_strategy_return"]

        n = len(data)
        total_return = float(data["cum_strategy_return"].iloc[-1] - 1)
        ann_return = (1 + total_return) ** (TRADING_DAYS / n) - 1

        daily = data["strategy_return"]
        std = float(daily.std(ddof=1))
        rf_d = RISK_FREE_RATE / TRADING_DAYS

        # Sharpe ĐÚNG: có trừ lãi suất phi rủi ro
        sharpe = ((daily.mean() - rf_d) / std) * np.sqrt(TRADING_DAYS) if std > 0 else 0.0
        # Information Ratio: cái mà bản cũ tính nhưng gọi nhầm là Sharpe
        info_ratio = (daily.mean() / std) * np.sqrt(TRADING_DAYS) if std > 0 else 0.0

        downside = daily[daily < 0].std(ddof=1)
        sortino = ((daily.mean() - rf_d) / downside) * np.sqrt(TRADING_DAYS) if downside > 0 else np.nan

        cum_max = data["equity"].cummax()
        max_drawdown = float(((data["equity"] - cum_max) / cum_max).min())

        # ---- Tỷ lệ thắng tính trên LỆNH, không phải trên NGÀY ----
        sign = np.sign(data["position"])
        block = (sign != sign.shift()).cumsum()
        mask = sign != 0
        if mask.any():
            trade_ret = (data.loc[mask, "strategy_return"]
                         .groupby(block[mask])
                         .apply(lambda s: float((1 + s).prod() - 1)))
            win_rate = float((trade_ret > 0).mean())
            n_trades = int(len(trade_ret))
            avg_hold = float(mask.sum() / n_trades) if n_trades else 0.0
        else:
            trade_ret, win_rate, n_trades, avg_hold = pd.Series(dtype=float), 0.0, 0, 0.0

        bh_return = float(data["cum_market_return"].iloc[-1] - 1)

        return {
            "data": data,
            "total_return": total_return,
            "ann_return": float(ann_return),
            "sharpe_ratio": float(sharpe),
            "information_ratio": float(info_ratio),
            "sortino_ratio": float(sortino) if sortino == sortino else np.nan,
            "max_drawdown": max_drawdown,
            "win_rate": win_rate,               # TRÊN LỆNH
            "n_trades": n_trades,
            "avg_holding_days": avg_hold,
            "trade_returns": trade_ret,
            "total_turnover": float(data["turnover"].sum()),
            "total_cost": float(data["turnover"].sum() * transaction_cost * initial_capital),
            "final_equity": float(data["equity"].iloc[-1]),
            "benchmark_return": bh_return,
            "excess_vs_benchmark": total_return - bh_return,
            "assumptions": {
                "allow_short": allow_short,
                "execution_lag": execution_lag,
                "settlement_lag": settlement_lag,
                "transaction_cost": transaction_cost,
            },
        }
