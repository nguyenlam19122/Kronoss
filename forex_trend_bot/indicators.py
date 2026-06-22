"""Chỉ báo kỹ thuật cho hệ thống trend-following.

Tất cả dùng smoothing kiểu Wilder (ewm alpha=1/period) cho ATR/ADX để khớp với
cách MetaTrader/MQL5 tính, giúp backtest Python và EA cho kết quả tương đồng.
"""
import numpy as np
import pandas as pd


def ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def true_range(high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    return tr


def atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    tr = true_range(high, low, close)
    return tr.ewm(alpha=1.0 / period, adjust=False).mean()  # Wilder smoothing


def adx(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14):
    """Trả về (adx, +DI, -DI)."""
    up_move = high.diff()
    down_move = -low.diff()

    plus_dm = pd.Series(np.where((up_move > down_move) & (up_move > 0), up_move, 0.0), index=high.index)
    minus_dm = pd.Series(np.where((down_move > up_move) & (down_move > 0), down_move, 0.0), index=high.index)

    tr = true_range(high, low, close)
    atr_ = tr.ewm(alpha=1.0 / period, adjust=False).mean()

    plus_di = 100.0 * plus_dm.ewm(alpha=1.0 / period, adjust=False).mean() / atr_
    minus_di = 100.0 * minus_dm.ewm(alpha=1.0 / period, adjust=False).mean() / atr_

    dx = 100.0 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    adx_ = dx.ewm(alpha=1.0 / period, adjust=False).mean()
    return adx_, plus_di, minus_di


def donchian(high: pd.Series, low: pd.Series, period: int = 20):
    """Kênh Donchian dùng cho tín hiệu breakout.

    Trả về (upper_prev, lower_prev) đã shift 1 -> chỉ gồm N nến TRƯỚC nến hiện tại,
    tránh nhìn trộm tương lai (lookahead) khi xét breakout tại nến đóng cửa.
    """
    upper_prev = high.rolling(period).max().shift(1)
    lower_prev = low.rolling(period).min().shift(1)
    return upper_prev, lower_prev
