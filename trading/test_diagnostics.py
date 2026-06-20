"""Tests for the edge-measurement tool. Run: python -m trading.test_diagnostics"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .data import _standardize
from .diagnostics import EdgeConfig, measure_edge
from .signals import SignalConfig


def _synthetic_df(n=1500, seed=1):
    rng = np.random.default_rng(seed)
    close = 100.0 * np.exp(np.cumsum(rng.normal(0.0003, 0.01, n)))
    idx = pd.date_range("2021-01-01", periods=n, freq="h")
    df = pd.DataFrame({"open": close, "high": close * 1.002, "low": close * 0.998,
                       "close": close, "volume": 1.0}, index=idx)
    df.index.name = "timestamps"
    return _standardize(df.reset_index())


def _oracle(df, flip=False):
    series = df["close"]

    def fn(ctx, x_ts, y_ts, pred_len):
        last = float(ctx["close"].iloc[-1])
        y = pd.Series(y_ts)
        fut = series.reindex(pd.DatetimeIndex(y.values)).to_numpy(float)
        fut = np.where(np.isnan(fut), last, fut)
        if flip:
            fut = 2 * last - fut
        return pd.DataFrame({"open": fut, "high": fut, "low": fut, "close": fut,
                             "volume": 0.0, "amount": 0.0},
                            index=pd.Index(y.values, name="timestamps"))
    return fn


def _random(seed=0):
    rng = np.random.default_rng(seed)

    def fn(ctx, x_ts, y_ts, pred_len):
        last = float(ctx["close"].iloc[-1])
        vals = last * (1 + rng.normal(0, 0.01, pred_len))
        return pd.DataFrame({"open": vals, "high": vals, "low": vals, "close": vals,
                             "volume": 0.0, "amount": 0.0},
                            index=pd.Index(pd.Series(y_ts).values, name="timestamps"))
    return fn


def test_oracle_has_edge():
    df = _synthetic_df()
    cfg = EdgeConfig(lookback=200, pred_len=10, signal=SignalConfig(mode="mean"))
    r = measure_edge(df, _oracle(df), cfg, verbose=False)
    assert r["directional_accuracy"] > 0.8, r
    assert r["pearson_ic"] > 0.5 and r["rank_ic"] > 0.5, r
    assert r["accuracy_pvalue"] < 0.01, r
    print(f"✓ test_oracle_has_edge (acc={r['directional_accuracy']:.2%}, IC={r['pearson_ic']})")


def test_antioracle_negative_ic():
    df = _synthetic_df()
    cfg = EdgeConfig(lookback=200, pred_len=10)
    r = measure_edge(df, _oracle(df, flip=True), cfg, verbose=False)
    assert r["directional_accuracy"] < 0.2, r
    assert r["pearson_ic"] < -0.5, r
    print(f"✓ test_antioracle_negative_ic (acc={r['directional_accuracy']:.2%}, IC={r['pearson_ic']})")


def test_random_no_edge():
    df = _synthetic_df()
    cfg = EdgeConfig(lookback=200, pred_len=10)
    r = measure_edge(df, _random(), cfg, verbose=False)
    assert 0.4 < r["directional_accuracy"] < 0.6, r
    assert abs(r["pearson_ic"]) < 0.2, r
    assert r["accuracy_pvalue"] > 0.05, r  # not significantly different from coin flip
    print(f"✓ test_random_no_edge (acc={r['directional_accuracy']:.2%}, IC={r['pearson_ic']}, p={r['accuracy_pvalue']:.3f})")


def main():
    test_oracle_has_edge()
    test_antioracle_negative_ic()
    test_random_no_edge()
    print("\nAll diagnostics tests passed ✅")


if __name__ == "__main__":
    main()
