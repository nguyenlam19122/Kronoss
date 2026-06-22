"""Chuẩn bị chỉ báo & tín hiệu cho chiến lược trend-following.

Logic:
  - Lọc trend : EMA_fast vs EMA_slow + ADX > ngưỡng  (chỉ chơi khi có xu hướng)
  - Vào lệnh  : breakout kênh Donchian theo chiều trend
  - Gồng lệnh : Chandelier trailing stop (xử lý trong backtest.py / EA)

Hàm prepare() chỉ gắn thêm cột chỉ báo. Việc tránh lookahead (dùng nến i-1 để
quyết định, khớp lệnh tại open nến i) được xử lý trong vòng lặp của backtest.
"""
import pandas as pd

from . import indicators as ind
from .config import StrategyParams


def prepare(df: pd.DataFrame, sp: StrategyParams) -> pd.DataFrame:
    out = df.copy()
    high, low, close = out["high"], out["low"], out["close"]

    out["ema_fast"] = ind.ema(close, sp.ema_fast)
    out["ema_slow"] = ind.ema(close, sp.ema_slow)
    out["adx"], out["plus_di"], out["minus_di"] = ind.adx(high, low, close, sp.adx_period)
    out["atr"] = ind.atr(high, low, close, sp.atr_period)

    out["dc_upper_prev"], out["dc_lower_prev"] = ind.donchian(high, low, sp.donchian_period)

    # Đỉnh/đáy cao nhất cho Chandelier trailing (gồm cả nến hiện tại;
    # backtest dùng giá trị của nến i-1 để đặt stop cho nến i -> không lookahead)
    out["chand_high"] = high.rolling(sp.chandelier_period).max()
    out["chand_low"] = low.rolling(sp.chandelier_period).min()

    # Chiều trend tại mỗi nến: 1 = up, -1 = down, 0 = không đủ điều kiện
    trend = pd.Series(0, index=out.index, dtype="int64")
    strong = out["adx"] >= sp.adx_min
    trend[(out["ema_fast"] > out["ema_slow"]) & strong] = 1
    trend[(out["ema_fast"] < out["ema_slow"]) & strong] = -1
    out["trend"] = trend

    return out
