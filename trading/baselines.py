"""Naive forecast baselines (no model, no network).

These are useful for two things:
1. Smoke-testing the whole pipeline (data -> signal -> backtest) without
   downloading Kronos weights.
2. Providing a reference: a Kronos strategy should beat these trivial rules to
   be worth anything.

Each factory returns a ``predict_fn`` with the backtest signature
``(ctx, x_ts, y_ts, pred_len) -> pred_df``.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def _frame(values: np.ndarray, ctx: pd.DataFrame, y_ts) -> pd.DataFrame:
    """Build a minimal forecast frame from predicted closes."""
    values = np.asarray(values, dtype=float)
    return pd.DataFrame(
        {
            "open": values,
            "high": values,
            "low": values,
            "close": values,
            "volume": float(ctx["volume"].iloc[-1]) if "volume" in ctx else 0.0,
            "amount": 0.0,
        },
        index=pd.Index(pd.Series(y_ts).values[: len(values)], name="timestamps"),
    )


def persistence_predict_fn():
    """Random-walk baseline: forecast = last close repeated (expected move ~0)."""

    def predict_fn(ctx, x_ts, y_ts, pred_len):
        last = float(ctx["close"].iloc[-1])
        return _frame(np.full(pred_len, last), ctx, y_ts)

    return predict_fn


def random_predict_fn(seed: int = 0):
    """Random-direction baseline: forecast points up or down at random.

    Used as a control in walk-forward PF: a real signal must beat this. If a
    random signal reaches the same out-of-sample PF, the "profit" comes from
    market drift + exit management, not from the model.
    """
    rng = np.random.default_rng(seed)

    def predict_fn(ctx, x_ts, y_ts, pred_len):
        last = float(ctx["close"].iloc[-1])
        move = rng.normal(0.0, 0.01)
        return _frame(np.full(pred_len, last * (1.0 + move)), ctx, y_ts)

    return predict_fn


def momentum_predict_fn(window: int = 20):
    """Trend-continuation baseline: extrapolate the recent average bar return."""

    def predict_fn(ctx, x_ts, y_ts, pred_len):
        close = ctx["close"].to_numpy(dtype=float)
        last = float(close[-1])
        w = min(window, len(close) - 1)
        avg_ret = np.mean(close[-w:] / close[-w - 1 : -1] - 1.0) if w >= 1 else 0.0
        steps = np.arange(1, pred_len + 1)
        return _frame(last * (1.0 + avg_ret) ** steps, ctx, y_ts)

    return predict_fn
