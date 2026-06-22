"""Deeper honest check: does a strategy actually BEAT BUY & HOLD out-of-sample?

The reality check on US indices showed a giant profit factor can be hollow — a
no-stop long-only mean-reversion just rides a bull market and still loses to
plain buy & hold. So a PF > 1.2 is necessary but NOT sufficient. The real bar
is: out-of-sample (last 40%, never optimised on), does the strategy beat buy &
hold on return AND on risk-adjusted return (return / max drawdown)?

This runs locally on the user's MT5 CSVs (no network). Gold has 5+ years of
history so it is the asset that can be judged honestly here.
"""

from __future__ import annotations

import argparse

import numpy as np
import pandas as pd

from .data import load_csv
from .gold_strategy import (backtest_signal, bollinger_meanrev, default_cost_per_side,
                            ema_cross, resample_ohlcv, sma_cross)
from .walkforward import _profit_factor


def _equity(net: pd.Series):
    eq = (1 + net).cumprod()
    ret = float(eq.iloc[-1] - 1)
    dd = float((eq / eq.cummax() - 1).min())
    return ret, dd


def reality(df, sig, cost):
    """Strategy vs buy & hold on the SAME window (return, max DD, time in market)."""
    tr, net = backtest_signal(df, sig, cost)
    pos = sig.reindex(df.index).shift(1).fillna(0.0)
    s_ret, s_dd = _equity(net)
    bh = df["close"].pct_change().fillna(0.0)
    bh_ret, bh_dd = _equity(bh)
    pf = _profit_factor(tr["net_pnl"]) if len(tr) else 0.0
    # risk-adjusted = return per unit of max drawdown (higher is better)
    s_radj = s_ret / abs(s_dd) if s_dd < 0 else float("inf")
    bh_radj = bh_ret / abs(bh_dd) if bh_dd < 0 else float("inf")
    return {"pf": pf, "trades": len(tr), "mkt": float((pos != 0).mean()),
            "s_ret": s_ret, "s_dd": s_dd, "s_radj": s_radj,
            "bh_ret": bh_ret, "bh_dd": bh_dd, "bh_radj": bh_radj}


def signal_for(df, spec, lo=True):
    kind = spec[0]
    if kind == "ema":
        return ema_cross(df, spec[1], spec[2], long_only=lo)
    if kind == "sma":
        return sma_cross(df, spec[1], spec[2], long_only=lo)
    if kind == "boll":
        return bollinger_meanrev(df, spec[1], spec[2], long_only=lo)
    raise ValueError(spec)


def run_asset(csv, tf, spec, label, train_frac=0.6):
    raw = load_csv(csv)
    df = resample_ohlcv(raw, tf)
    cost = default_cost_per_side(df)
    s = int(train_frac * len(df))
    test = df.iloc[s:]
    full = reality(df, signal_for(df, spec), cost)
    oos = reality(test, signal_for(test, spec), cost)
    # honest verdict on the untouched test half
    beats_ret = oos["s_ret"] > oos["bh_ret"]
    beats_radj = oos["s_radj"] > oos["bh_radj"]
    verdict = ("✅ THẮNG B&H (cả lợi nhuận & rủi ro)" if beats_ret and beats_radj else
               "🟡 chỉ thắng rủi ro (đỡ sụt vốn, lời thấp hơn)" if beats_radj else
               "🔴 THUA buy & hold")
    return {"label": label, "tf": tf, "bars": len(df), "oos_bars": len(test),
            "full": full, "oos": oos, "verdict": verdict}


def _fmt(r):
    o, f = r["oos"], r["full"]
    return (
        f"\n=== {r['label']}  ({r['bars']} {r['tf']} bars) ===\n"
        f"  FULL : PF={f['pf']:.2f}  ret={f['s_ret']*100:+.0f}%  DD={f['s_dd']*100:.0f}%  "
        f"(B&H ret={f['bh_ret']*100:+.0f}% DD={f['bh_dd']*100:.0f}%)\n"
        f"  OOS  : PF={o['pf']:.2f}  trades={o['trades']}  inMkt={o['mkt']*100:.0f}%\n"
        f"         strat   ret={o['s_ret']*100:+.0f}%  DD={o['s_dd']*100:.0f}%  ret/DD={o['s_radj']:.2f}\n"
        f"         buy&hold ret={o['bh_ret']*100:+.0f}%  DD={o['bh_dd']*100:.0f}%  ret/DD={o['bh_radj']:.2f}\n"
        f"  VERDICT (OOS): {r['verdict']}"
    )


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Does the strategy beat buy & hold OOS?")
    p.add_argument("--data-dir", default="trading/mydata")
    args = p.parse_args(argv)
    d = args.data_dir

    tests = [
        # The claimed winner: gold trend-following on H4 / Daily
        (f"{d}/XAUUSD_M30.csv", "4h", ("ema", 50, 200), "GOLD H4 — EMA50/200 trend (LO)"),
        (f"{d}/XAUUSD_M30.csv", "1D", ("ema", 50, 200), "GOLD D1 — EMA50/200 trend (LO)"),
        # Contrast on the SAME asset: mean-reversion (should be weaker on a trender)
        (f"{d}/XAUUSD_M30.csv", "4h", ("boll", 30, 2.0), "GOLD H4 — Bollinger MR (LO)"),
        # Indices locally (~1y M30): trend vs MR, intraday
        (f"{d}/US30_M30.csv", "4h", ("ema", 50, 200), "US30 H4 — EMA50/200 trend (LO)"),
        (f"{d}/US30_M30.csv", "4h", ("boll", 30, 2.0), "US30 H4 — Bollinger MR (LO)"),
        (f"{d}/US500_M30.csv", "4h", ("boll", 30, 2.0), "US500 H4 — Bollinger MR (LO)"),
    ]
    print("Honest test — out-of-sample (last 40%, never optimised): beat buy & hold?")
    results = []
    for csv, tf, spec, label in tests:
        try:
            r = run_asset(csv, tf, spec, label)
            results.append(r)
            print(_fmt(r))
        except Exception as e:
            print(f"\n=== {label} ===\n  ERROR: {e}")

    wins = [r for r in results if r["verdict"].startswith("✅")]
    print("\n" + "=" * 60)
    print(f"Beat buy & hold OOS (cả lợi nhuận lẫn rủi ro): {len(wins)}/{len(results)}")
    for r in wins:
        print(f"  ✅ {r['label']}")
    print("→ Chỉ những cái ✅ mới là edge THẬT đáng đóng gói (PF cao mà thua B&H = vô nghĩa).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
