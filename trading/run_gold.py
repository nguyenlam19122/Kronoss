"""Run and chart a trend-following gold strategy with honest stats.

Example::

    python -m trading.run_gold --csv trading/mydata/XAUUSD_M30.csv \
        --timeframe 4h --strategy ema --fast 50 --slow 200 --long-only
"""

from __future__ import annotations

import argparse
import os

import numpy as np
import pandas as pd

from .data import load_csv
from .gold_strategy import (backtest_signal, buy_hold_pf, default_cost_per_side,
                            donchian, ema_cross, momentum, resample_ohlcv, sma_cross)
from .walkforward import _profit_factor


def build_signal(df, args):
    lo = args.long_only
    if args.strategy == "ema":
        return ema_cross(df, args.fast, args.slow, long_only=lo)
    if args.strategy == "sma":
        return sma_cross(df, args.fast, args.slow, long_only=lo)
    if args.strategy == "donchian":
        return donchian(df, args.n, long_only=lo)
    if args.strategy == "momentum":
        return momentum(df, args.n, long_only=lo)
    raise ValueError(args.strategy)


def metrics(trades, net):
    eq = (1 + net).cumprod()
    dd = (eq / eq.cummax() - 1).min()
    r = trades["net_pnl"]
    return {
        "profit_factor": round(_profit_factor(r), 3),
        "trades": int(len(r)),
        "win_rate": round(float((r > 0).mean()), 4),
        "total_return": round(float(eq.iloc[-1] - 1), 4),
        "avg_win": round(float(r[r > 0].mean()), 4) if (r > 0).any() else None,
        "avg_loss": round(float(r[r <= 0].mean()), 4) if (r <= 0).any() else None,
        "max_drawdown": round(float(dd), 4),
        "pf_first_half": round(_profit_factor(r.iloc[: len(r) // 2]), 3),
        "pf_second_half": round(_profit_factor(r.iloc[len(r) // 2:]), 3),
    }


def plot(df, net, name, out_path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    eq = (1 + net).cumprod()
    bh = df["close"] / float(df["close"].iloc[0])
    fig, ax = plt.subplots(figsize=(12, 6))
    ax.plot(eq.index, eq, label=f"{name} (trend strategy)", color="#1f77b4", lw=1.6)
    ax.plot(bh.index, bh, label="Buy & hold gold", color="#ff7f0e", lw=1.2, alpha=0.8)
    ax.set_yscale("log")
    ax.set_ylabel("Growth of 1 (log)")
    ax.set_title(name, fontweight="bold")
    ax.legend(); ax.grid(True, alpha=0.3)
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    fig.savefig(out_path, dpi=150, bbox_inches="tight"); plt.close(fig)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Trend-following gold strategy backtest.")
    p.add_argument("--csv", required=True)
    p.add_argument("--timeframe", default="4h", help="Resample rule: 4h, 1D, 1h ...")
    p.add_argument("--strategy", default="ema", choices=["ema", "sma", "donchian", "momentum"])
    p.add_argument("--fast", type=int, default=50)
    p.add_argument("--slow", type=int, default=200)
    p.add_argument("--n", type=int, default=55)
    p.add_argument("--long-only", action="store_true")
    p.add_argument("--slippage-points", type=float, default=2.0)
    p.add_argument("--out-dir", default="trading/results")
    args = p.parse_args(argv)

    raw = load_csv(args.csv)
    df = resample_ohlcv(raw, args.timeframe)
    cost = default_cost_per_side(df, args.slippage_points)
    name = (f"XAUUSD_{args.timeframe}_{args.strategy}_{args.fast}_{args.slow}"
            + ("_LO" if args.long_only else ""))

    trades, net = backtest_signal(df, build_signal(df, args), cost)
    m = metrics(trades, net)

    print(f"📊 {name}  ({len(df)} {args.timeframe} bars, cost/side={cost*100:.4f}%)")
    print(f"   Buy & hold PF (ref): {buy_hold_pf(df):.2f}")
    print("=" * 50)
    for k, v in m.items():
        if "rate" in k or "return" in k or "drawdown" in k or k.startswith("avg"):
            print(f"  {k:<16}: {v:.2%}" if isinstance(v, float) else f"  {k:<16}: {v}")
        else:
            print(f"  {k:<16}: {v}")
    verdict = "✅ ĐẠT (PF>1.2 + cả 2 nửa >1.2)" if (
        m["profit_factor"] > 1.2 and m["pf_first_half"] > 1.2 and m["pf_second_half"] > 1.2
    ) else "🟡 chưa vững"
    print(f"  VERDICT         : {verdict}")

    os.makedirs(args.out_dir, exist_ok=True)
    chart = os.path.join(args.out_dir, f"{name}.png")
    plot(df, net, name, chart)
    trades.to_csv(os.path.join(args.out_dir, f"{name}_trades.csv"), index=False)
    print(f"\n💾 chart: {chart}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
