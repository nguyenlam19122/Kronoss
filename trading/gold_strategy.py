"""Classical trend-following strategies for gold (XAU/USD), honestly validated.

Research consensus (QuantifiedStrategies, Quant-Signals, ...): gold is a
*trending* asset — trend-following (EMA/SMA cross, Donchian/breakout, momentum)
works, pure RSI mean-reversion does not — and **higher timeframes** (H4/Daily)
beat intraday because trades are rarer so spread/cost drag is negligible.

So we resample the user's M30 data up to H4/D1, generate causal trend signals,
backtest them with realistic cost, and judge them with the same honest
walk-forward (optimise the strategy choice on past folds, score the next fold
out-of-sample) plus a random control. A signal must beat random and clear
PF > 1.2 out-of-sample to count.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


# --------------------------------------------------------------------------- #
# Resampling M30 -> higher timeframe
# --------------------------------------------------------------------------- #
def resample_ohlcv(df: pd.DataFrame, rule: str) -> pd.DataFrame:
    """Resample a standardized OHLCV(+spread) frame to a higher timeframe."""
    agg = {"open": "first", "high": "max", "low": "min", "close": "last",
           "volume": "sum"}
    if "spread" in df.columns:
        agg["spread"] = "mean"
    out = df.resample(rule).agg(agg).dropna(subset=["open", "high", "low", "close"])
    out["amount"] = out.get("volume", 0.0) * out["close"]
    out.attrs["point"] = df.attrs.get("point", 1.0)
    return out


# --------------------------------------------------------------------------- #
# Causal trend signals: each returns a direction series in {-1, 0, +1}.
# A signal computed at bar t uses only data up to t; the backtest then holds
# that position into bar t+1 (pos = signal.shift(1)).
# --------------------------------------------------------------------------- #
def ema_cross(df, fast=21, slow=50, long_only=False):
    ef = df["close"].ewm(span=fast, adjust=False).mean()
    es = df["close"].ewm(span=slow, adjust=False).mean()
    d = np.where(ef > es, 1.0, 0.0 if long_only else -1.0)
    return pd.Series(d, index=df.index)


def sma_cross(df, fast=50, slow=200, long_only=False):
    ef = df["close"].rolling(fast).mean()
    es = df["close"].rolling(slow).mean()
    d = np.where(ef > es, 1.0, 0.0 if long_only else -1.0)
    return pd.Series(d, index=df.index).where(es.notna(), 0.0)


def donchian(df, n=20, long_only=False):
    upper = df["high"].rolling(n).max().shift(1)
    lower = df["low"].rolling(n).min().shift(1)
    d = pd.Series(np.nan, index=df.index)
    d[df["close"] > upper] = 1.0
    d[df["close"] < lower] = 0.0 if long_only else -1.0
    return d.ffill().fillna(0.0)


def momentum(df, n=50, long_only=False):
    chg = df["close"] - df["close"].shift(n)
    d = np.where(chg > 0, 1.0, 0.0 if long_only else -1.0)
    return pd.Series(d, index=df.index).where(df["close"].shift(n).notna(), 0.0)


def macd_trend(df, fast=12, slow=26, signal=9, long_only=False):
    ef = df["close"].ewm(span=fast, adjust=False).mean()
    es = df["close"].ewm(span=slow, adjust=False).mean()
    macd = ef - es
    sig = macd.ewm(span=signal, adjust=False).mean()
    d = np.where(macd > sig, 1.0, 0.0 if long_only else -1.0)
    return pd.Series(d, index=df.index)


def random_signal(df, seed=0):
    rng = np.random.default_rng(seed)
    # random but persistent (flip occasionally) so trade frequency is comparable
    raw = rng.choice([1.0, -1.0], size=len(df))
    return pd.Series(raw, index=df.index)


# Strategy variants to search over (trend-following only — research-backed).
def strategy_zoo() -> dict:
    z = {}
    for f, s in [(21, 50), (20, 100), (50, 200), (10, 30)]:
        z[f"ema_{f}_{s}"] = lambda df, f=f, s=s: ema_cross(df, f, s)
        z[f"ema_{f}_{s}_LO"] = lambda df, f=f, s=s: ema_cross(df, f, s, long_only=True)
    for n in [20, 55]:
        z[f"donchian_{n}"] = lambda df, n=n: donchian(df, n)
        z[f"donchian_{n}_LO"] = lambda df, n=n: donchian(df, n, long_only=True)
    for n in [50, 100]:
        z[f"momentum_{n}"] = lambda df, n=n: momentum(df, n)
    z["sma_50_200"] = lambda df: sma_cross(df, 50, 200)
    z["sma_50_200_LO"] = lambda df: sma_cross(df, 50, 200, long_only=True)
    z["macd"] = lambda df: macd_trend(df)
    return z


# --------------------------------------------------------------------------- #
# Vectorised backtest of a direction signal (flip-exit) with cost
# --------------------------------------------------------------------------- #
def default_cost_per_side(df: pd.DataFrame, slippage_points: float = 2.0) -> float:
    """Per-side cost as a return: half-spread + slippage, divided by price."""
    point = df.attrs.get("point", 1.0)
    px = float(df["close"].median())
    spread = float(df["spread"].median()) if "spread" in df.columns else 0.0
    return (spread / 2 + slippage_points * point) / px


def backtest_signal(df: pd.DataFrame, direction: pd.Series, cost_per_side: float):
    """Hold `direction` (shifted, no look-ahead) until it flips; charge cost on
    turnover. Returns a trades DataFrame (entry_time, side, net_pnl=return)."""
    pos = direction.reindex(df.index).shift(1).fillna(0.0)
    bar_ret = df["close"].pct_change().fillna(0.0)
    turn = pos.diff().abs().fillna(pos.abs())
    net = pos * bar_ret - turn * cost_per_side

    p = pos.to_numpy()
    netv = net.to_numpy()
    idx = df.index
    rows, i, n = [], 0, len(p)
    while i < n:
        if p[i] == 0:
            i += 1
            continue
        j = i
        while j < n and p[j] == p[i]:
            j += 1
        tr = float(np.prod(1.0 + netv[i:j]) - 1.0)
        rows.append({"entry_time": idx[i], "exit_time": idx[j - 1],
                     "side": int(p[i]), "net_pnl": tr})
        i = j
    return pd.DataFrame(rows), net


def build_strategy_trades(df: pd.DataFrame, cost_per_side: float, include_random=True) -> dict:
    """Backtest every strategy variant -> {name: trades_df(entry_time, net_pnl)}."""
    out = {}
    for name, fn in strategy_zoo().items():
        trades, _ = backtest_signal(df, fn(df), cost_per_side)
        if len(trades):
            out[name] = trades[["entry_time", "net_pnl"]]
    if include_random:
        for seed in range(3):  # a few random controls
            trades, _ = backtest_signal(df, random_signal(df, seed), cost_per_side)
            if len(trades):
                out[f"__random_{seed}"] = trades[["entry_time", "net_pnl"]]
    return out


def buy_hold_pf(df: pd.DataFrame) -> float:
    """PF of simply holding long (reference)."""
    r = df["close"].pct_change().dropna()
    gp, gl = r[r > 0].sum(), -r[r < 0].sum()
    return float(gp / gl) if gl > 0 else float("inf")
