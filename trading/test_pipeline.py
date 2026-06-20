"""Correctness tests for the trading pipeline (run without the model or network).

Run directly::

    python -m trading.test_pipeline

or with pytest::

    pytest trading/test_pipeline.py
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .backtest import BacktestConfig, run_walk_forward
from .data import _standardize, resolve_symbol
from .signals import SignalConfig, expected_return, position_from_forecast


def _synthetic_df(n: int = 1500, seed: int = 0) -> pd.DataFrame:
    """A noisy upward random walk with daily timestamps."""
    rng = np.random.default_rng(seed)
    ret = rng.normal(0.0005, 0.01, n)
    close = 100.0 * np.exp(np.cumsum(ret))
    idx = pd.date_range("2020-01-01", periods=n, freq="D")
    df = pd.DataFrame(
        {
            "open": close * (1 + rng.normal(0, 0.001, n)),
            "high": close * (1 + abs(rng.normal(0, 0.003, n))),
            "low": close * (1 - abs(rng.normal(0, 0.003, n))),
            "close": close,
            "volume": rng.uniform(1e3, 1e4, n),
        },
        index=idx,
    )
    df.index.name = "timestamps"
    return _standardize(df.reset_index())


def _oracle_predict_fn(df: pd.DataFrame, flip: bool = False):
    """Predictor that 'knows' the real future closes (engine wiring test only)."""
    series = df["close"]

    def predict_fn(ctx, x_ts, y_ts, pred_len):
        last = float(ctx["close"].iloc[-1])
        y_ts = pd.Series(y_ts)
        future = series.reindex(pd.DatetimeIndex(y_ts.values)).to_numpy(dtype=float)
        future = np.where(np.isnan(future), last, future)
        if flip:  # mirror the path around the last close
            future = 2 * last - future
        vals = future
        return pd.DataFrame(
            {"open": vals, "high": vals, "low": vals, "close": vals,
             "volume": 0.0, "amount": 0.0},
            index=pd.Index(y_ts.values, name="timestamps"),
        )

    return predict_fn


# --------------------------------------------------------------------------- #
def test_signal_modes():
    last = 100.0
    up = np.array([101, 102, 103, 104], dtype=float)
    down = np.array([99, 98, 97, 96], dtype=float)
    cfg = SignalConfig(mode="mean")
    assert expected_return(up, last, cfg) > 0
    assert expected_return(down, last, cfg) < 0
    assert position_from_forecast(up, last, cfg) == 1
    assert position_from_forecast(down, last, cfg) == -1
    # no-short -> short collapses to flat
    assert position_from_forecast(down, last, SignalConfig(allow_short=False)) == 0
    # threshold gates small moves to flat
    tiny = np.array([100.01] * 4)
    assert position_from_forecast(tiny, last, SignalConfig(long_threshold=0.01)) == 0
    for mode in ("mean", "endpoint", "slope"):
        assert expected_return(up, last, SignalConfig(mode=mode)) > 0
    print("✓ test_signal_modes")


def test_oracle_beats_antioracle():
    """A perfect-direction forecaster must beat buy&hold; the inverse must lose."""
    df = _synthetic_df()
    cfg = BacktestConfig(lookback=200, pred_len=5, cost=0.0, signal=SignalConfig(mode="mean"))

    good = run_walk_forward(df, _oracle_predict_fn(df), cfg, verbose=False)
    bad = run_walk_forward(df, _oracle_predict_fn(df, flip=True), cfg, verbose=False)

    gm, bm = good["metrics"], bad["metrics"]
    assert gm["total_return"] > gm["benchmark_return"], gm
    assert gm["sharpe"] > 1.0, gm
    assert gm["win_rate"] > 0.6, gm
    assert bm["total_return"] < gm["total_return"], bm
    print(f"✓ test_oracle_beats_antioracle (oracle={gm['total_return']:.2%} "
          f"sharpe={gm['sharpe']:.2f}, anti={bm['total_return']:.2%})")


def test_no_lookahead_alignment():
    """Position over a step is constant and set strictly after the decision bar."""
    df = _synthetic_df(800)
    cfg = BacktestConfig(lookback=100, pred_len=10, step=10, cost=0.0)
    res = run_walk_forward(df, _oracle_predict_fn(df), cfg, verbose=False)
    pos = res["frame"]["position"].to_numpy()
    # Bars before the first decision (index < lookback) must be flat.
    assert np.all(pos[: cfg.lookback] == 0.0)
    # Equity equals the compounded strategy returns (no double counting).
    fr = res["frame"]
    recomputed = float((1.0 + fr["strategy_return"]).prod())
    assert abs(recomputed - fr["equity"].iloc[-1]) < 1e-9
    print("✓ test_no_lookahead_alignment")


def test_cost_reduces_return():
    df = _synthetic_df()
    base = BacktestConfig(lookback=200, pred_len=5, cost=0.0)
    with_cost = BacktestConfig(lookback=200, pred_len=5, cost=0.001)
    r0 = run_walk_forward(df, _oracle_predict_fn(df), base, verbose=False)["metrics"]
    r1 = run_walk_forward(df, _oracle_predict_fn(df), with_cost, verbose=False)["metrics"]
    assert r1["total_return"] < r0["total_return"]
    print("✓ test_cost_reduces_return")


def test_resolve_symbol():
    assert resolve_symbol("btc") == "BTC-USD"
    assert resolve_symbol("GOLD") == "GC=F"
    assert resolve_symbol("eurusd") == "EURUSD=X"
    assert resolve_symbol("AAPL") == "AAPL"  # passthrough
    print("✓ test_resolve_symbol")


def test_bars_per_year_daily():
    df = _synthetic_df(400)
    res = run_walk_forward(df, _oracle_predict_fn(df),
                           BacktestConfig(lookback=100, pred_len=5), verbose=False)
    assert 360 <= res["metrics"]["bars_per_year"] <= 366
    print("✓ test_bars_per_year_daily")


def main():
    test_signal_modes()
    test_resolve_symbol()
    test_bars_per_year_daily()
    test_no_lookahead_alignment()
    test_cost_reduces_return()
    test_oracle_beats_antioracle()
    print("\nAll tests passed ✅")


if __name__ == "__main__":
    main()
