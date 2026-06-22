"""Correctness tests for the event-driven trade simulator (no model/network).

Run::  python -m trading.test_trade_sim   (or: pytest trading/test_trade_sim.py)
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .signals import SignalConfig
from .sizing import SizingConfig, size_position
from .trade_sim import TradeConfig, run_trade_sim


def _base_df(n=100, lookback=50):
    """First `lookback` bars oscillate so ATR == 1.0; rest filled flat at 100."""
    idx = pd.date_range("2024-01-01", periods=n, freq="5min")
    o = np.full(n, 100.0)
    c = np.full(n, 100.0)
    high = np.full(n, 100.5)
    low = np.full(n, 99.5)
    df = pd.DataFrame({"open": o, "high": high, "low": low, "close": c,
                       "volume": 1.0, "amount": 100.0}, index=idx)
    df.index.name = "timestamps"
    df.attrs["point"] = 1.0
    return df


def _forced_predict_fn(direction):
    factor = 1.05 if direction > 0 else 0.95

    def predict_fn(ctx, x_ts, y_ts, pred_len):
        last = float(ctx["close"].iloc[-1])
        vals = np.full(pred_len, last * factor)
        return pd.DataFrame({"open": vals, "high": vals, "low": vals, "close": vals,
                             "volume": 0.0, "amount": 0.0},
                            index=pd.Index(pd.Series(y_ts).values, name="timestamps"))
    return predict_fn


def _cfg(**kw):
    base = dict(lookback=50, pred_len=24, signal_every=1000, atr_period=14,
                sl_atr=1.0, rr=2.0, initial_capital=5000.0,
                sizing=SizingConfig(mode="fixed", risk_amount=25.0),
                use_data_spread=False, signal=SignalConfig(mode="mean"))
    base.update(kw)
    return TradeConfig(**base)


def test_sizing_math():
    units, risk = size_position(5000, 100.0, 2.0, SizingConfig(mode="fixed", risk_amount=25))
    assert abs(units - 12.5) < 1e-9 and abs(risk - 25) < 1e-9
    units, risk = size_position(5000, 100.0, 2.0, SizingConfig(mode="percent", risk_pct=0.005))
    assert abs(risk - 25) < 1e-9  # 0.5% of 5000
    # leverage cap binds -> realised risk drops below nominal
    units, risk = size_position(5000, 100.0, 0.01,
                                SizingConfig(mode="fixed", risk_amount=25, max_leverage=2))
    assert abs(units - 100.0) < 1e-9 and risk < 25  # 2x*5000/100 = 100 units
    print("✓ test_sizing_math")


def test_target_hit_gives_plus_rr_R():
    df = _base_df()
    df.iloc[50, df.columns.get_loc("open")] = 100.0
    df.iloc[50, df.columns.get_loc("high")] = 103.0   # >= TP (102) -> +2R
    df.iloc[50, df.columns.get_loc("low")] = 100.0    # never touches SL (99)
    df.iloc[50, df.columns.get_loc("close")] = 102.0

    res = run_trade_sim(df, _forced_predict_fn(+1), _cfg(), verbose=False)
    t = res["trades"].iloc[0]
    assert t["reason"] == "target", t["reason"]
    assert abs(t["units"] - 25.0) < 1e-6          # risk 25 / stop 1.0
    assert abs(t["net_pnl"] - 50.0) < 1e-6        # +2R = +$50
    assert abs(t["R_multiple"] - 2.0) < 1e-6
    assert abs(res["metrics"]["final_equity"] - 5050.0) < 1e-6
    print("✓ test_target_hit_gives_plus_rr_R")


def test_stop_hit_loses_1R():
    df = _base_df()
    df.iloc[50, df.columns.get_loc("open")] = 100.0
    df.iloc[50, df.columns.get_loc("high")] = 100.5   # never reaches TP (102)
    df.iloc[50, df.columns.get_loc("low")] = 98.0     # <= SL (99) -> -1R
    df.iloc[50, df.columns.get_loc("close")] = 99.0

    res = run_trade_sim(df, _forced_predict_fn(+1), _cfg(), verbose=False)
    t = res["trades"].iloc[0]
    assert t["reason"] == "stop", t["reason"]
    assert abs(t["net_pnl"] + 25.0) < 1e-6         # -1R = -$25
    assert abs(t["R_multiple"] + 1.0) < 1e-6
    print("✓ test_stop_hit_loses_1R")


def test_short_target():
    df = _base_df()
    df.iloc[50, df.columns.get_loc("open")] = 100.0
    df.iloc[50, df.columns.get_loc("high")] = 100.0   # never hits short SL (101)
    df.iloc[50, df.columns.get_loc("low")] = 97.0     # <= short TP (98) -> +2R
    df.iloc[50, df.columns.get_loc("close")] = 98.0

    res = run_trade_sim(df, _forced_predict_fn(-1), _cfg(), verbose=False)
    t = res["trades"].iloc[0]
    assert t["side"] == "short" and t["reason"] == "target"
    assert abs(t["net_pnl"] - 50.0) < 1e-6
    print("✓ test_short_target")


def test_costs_reduce_pnl():
    def make(**kw):
        df = _base_df()
        df.iloc[50, df.columns.get_loc("high")] = 103.0
        df.iloc[50, df.columns.get_loc("low")] = 100.0
        df.iloc[50, df.columns.get_loc("close")] = 102.0
        return run_trade_sim(df, _forced_predict_fn(+1), _cfg(**kw), verbose=False)

    free = make()
    costly = make(spread_points=1.0, slippage_points=0.5, commission_per_trade=2.0)
    t = costly["trades"].iloc[0]
    assert costly["metrics"]["net_profit"] < free["metrics"]["net_profit"]
    assert t["spread_cost"] > 0 and t["slippage_cost"] > 0 and t["commission"] == 2.0
    assert costly["metrics"]["total_costs"] > 0
    print(f"✓ test_costs_reduce_pnl (free=${free['metrics']['net_profit']:.2f} "
          f"costly=${costly['metrics']['net_profit']:.2f})")


def test_timeout_exit():
    df = _base_df(n=120)  # flat after entry -> neither SL nor TP -> timeout
    res = run_trade_sim(df, _forced_predict_fn(+1), _cfg(), verbose=False)
    t = res["trades"].iloc[0]
    assert t["reason"] == "timeout"
    assert t["bars_held"] == 24  # max_hold == pred_len
    print("✓ test_timeout_exit")


def test_trailing_locks_profit():
    """Price spikes to +2R then pulls back; trailing stop should exit ~+1R."""
    df = _base_df()
    oc = df.columns.get_loc
    # bar 50: rise to 102 (extreme) -> after activation stop trails to 101
    df.iloc[50, oc("open")], df.iloc[50, oc("high")] = 100.0, 102.0
    df.iloc[50, oc("low")], df.iloc[50, oc("close")] = 100.0, 101.5
    # bar 51: pull back to 101 -> hits the trailing stop
    df.iloc[51, oc("open")], df.iloc[51, oc("high")] = 101.5, 101.5
    df.iloc[51, oc("low")], df.iloc[51, oc("close")] = 101.0, 101.0

    cfg = _cfg(rr=10.0, trail=True, trail_atr=1.0, trail_activate_r=1.0)  # TP far away
    res = run_trade_sim(df, _forced_predict_fn(+1), cfg, verbose=False)
    t = res["trades"].iloc[0]
    assert t["reason"] == "trail", t["reason"]
    assert abs(t["net_pnl"] - 25.0) < 1e-6   # locked +1R = +$25
    assert res["metrics"]["trails"] == 1
    print("✓ test_trailing_locks_profit")


def test_rr_zero_disables_tp():
    df = _base_df(n=120)
    df.iloc[50, df.columns.get_loc("high")] = 200.0  # would smash any TP
    res = run_trade_sim(df, _forced_predict_fn(+1), _cfg(rr=0.0), verbose=False)
    t = res["trades"].iloc[0]
    assert t["reason"] != "target" and t["target"] == ""
    print("✓ test_rr_zero_disables_tp")


def _trend_df(n=120, direction="down"):
    idx = pd.date_range("2024-01-01", periods=n, freq="5min")
    close = np.linspace(105, 100, n) if direction == "down" else np.linspace(100, 105, n)
    df = pd.DataFrame({"open": close, "high": close + 0.3, "low": close - 0.3,
                       "close": close, "volume": 1.0, "amount": 100.0}, index=idx)
    df.index.name = "timestamps"
    df.attrs["point"] = 1.0
    return df


def test_trend_filter_blocks_counter_trend():
    df = _trend_df(direction="down")  # price below its EMA
    # Long signal against a downtrend -> blocked
    blocked = run_trade_sim(df, _forced_predict_fn(+1),
                            _cfg(trend_filter=True, trend_ema=20), verbose=False)
    assert blocked["metrics"]["n_trades"] == 0
    assert blocked["metrics"]["filtered_breakdown"]["trend"] >= 1
    # Short signal with the downtrend -> allowed
    allowed = run_trade_sim(df, _forced_predict_fn(-1),
                            _cfg(trend_filter=True, trend_ema=20), verbose=False)
    assert allowed["metrics"]["n_trades"] >= 1
    print("✓ test_trend_filter_blocks_counter_trend")


def test_min_expected_r_filters_small_moves():
    def small_move(ctx, x_ts, y_ts, pred_len):
        last = float(ctx["close"].iloc[-1])
        vals = np.full(pred_len, last * (1 + 1e-4))  # ~0 predicted move
        return pd.DataFrame({"open": vals, "high": vals, "low": vals, "close": vals,
                             "volume": 0.0, "amount": 0.0},
                            index=pd.Index(pd.Series(y_ts).values, name="timestamps"))
    df = _base_df(n=120)
    res = run_trade_sim(df, small_move, _cfg(min_expected_r=2.0), verbose=False)
    assert res["metrics"]["n_trades"] == 0
    assert res["metrics"]["filtered_breakdown"]["magnitude"] >= 1
    print("✓ test_min_expected_r_filters_small_moves")


def test_confidence_filter():
    def conf_fn(confidence):
        base = _forced_predict_fn(+1)
        def fn(ctx, x_ts, y_ts, pred_len):
            out = base(ctx, x_ts, y_ts, pred_len)
            out.attrs["confidence"] = confidence
            return out
        return fn
    df = _base_df(n=120)
    low = run_trade_sim(df, conf_fn(0.4), _cfg(min_confidence=0.7), verbose=False)
    assert low["metrics"]["n_trades"] == 0
    assert low["metrics"]["filtered_breakdown"]["confidence"] >= 1
    high = run_trade_sim(df, conf_fn(0.9), _cfg(min_confidence=0.7), verbose=False)
    assert high["metrics"]["n_trades"] >= 1
    print("✓ test_confidence_filter")


def main():
    test_sizing_math()
    test_target_hit_gives_plus_rr_R()
    test_stop_hit_loses_1R()
    test_short_target()
    test_costs_reduce_pnl()
    test_timeout_exit()
    test_trailing_locks_profit()
    test_rr_zero_disables_tp()
    test_trend_filter_blocks_counter_trend()
    test_min_expected_r_filters_small_moves()
    test_confidence_filter()
    print("\nAll trade-sim tests passed ✅")


if __name__ == "__main__":
    main()
