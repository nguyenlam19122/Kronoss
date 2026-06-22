"""Rigorously validate the standout edge: trend-following on crypto (BTC/ETH).

The diversified-portfolio test flagged BTC trend as the one strategy that beats
buy & hold on BOTH return and risk out-of-sample (ret/DD 7.32). Crypto suits
trend-following: violent multi-month trends AND deep crashes, so a long/short
trend rule both rides rallies and goes short through bear markets ("crisis
alpha"). But one asset / one window is thin — so here we stress it honestly:

* a small grid of trend params (not one cherry-picked rule),
* walk-forward (choose the param on the past, score the next slice OOS),
* a RANDOM long/short control (the strategy must beat coin-flips),
* beat-buy & hold on return AND risk-adjusted,
* and the current live position so it is actually usable.

Needs yfinance -> run on GitHub Actions.
"""

from __future__ import annotations

import argparse

import numpy as np
import pandas as pd

from .data import load_yfinance
from .gold_strategy import ema_cross, random_signal
from .run_trend_portfolio import _stats, strat_net, tsmom

PARAMS = {
    "ema_20_100": lambda d: ema_cross(d, 20, 100, long_only=False),
    "ema_50_200": lambda d: ema_cross(d, 50, 200, long_only=False),
    "tsmom_100": lambda d: tsmom(d, 100),
    "tsmom_200": lambda d: tsmom(d, 200),
}


def walk_forward(df, cost, n_folds=5):
    """Expanding walk-forward over a single asset: pick the best-Sharpe param on
    all prior folds, score the next fold OOS, concatenate the OOS pieces."""
    nets = {name: strat_net(df, fn(df), cost) for name, fn in PARAMS.items()}
    edges = np.linspace(0, len(df), n_folds + 1).astype(int)
    oos_parts, picks = [], []
    for f in range(1, n_folds):
        is_sl = slice(0, edges[f])
        oos_sl = slice(edges[f], edges[f + 1])
        best, best_sh = None, -np.inf
        for name, net in nets.items():
            sh = _stats(net.iloc[is_sl])["sharpe"]
            if np.isfinite(sh) and sh > best_sh:
                best_sh, best = sh, name
        if best is None:
            continue
        oos_parts.append(nets[best].iloc[oos_sl])
        picks.append((f, best))
    oos = pd.concat(oos_parts) if oos_parts else pd.Series(dtype=float)
    return _stats(oos), picks, len(oos)


def random_control(df, cost, n=30):
    radjs, shps = [], []
    for seed in range(n):
        net = strat_net(df, random_signal(df, seed), cost)
        st = _stats(net)
        radjs.append(st["radj"] if np.isfinite(st["radj"]) else 0.0)
        shps.append(st["sharpe"])
    return float(np.median(radjs)), float(np.median(shps))


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Validate crypto trend-following honestly.")
    p.add_argument("--symbols", nargs="+", default=["BTC-USD", "ETH-USD"])
    p.add_argument("--period", default="max")
    p.add_argument("--cost", type=float, default=6e-4, help="Per-side cost (~6bp, crypto).")
    p.add_argument("--train-frac", type=float, default=0.6)
    args = p.parse_args(argv)

    for sym in args.symbols:
        print("\n" + "=" * 66)
        print(f"  {sym}  —  trend-following validation ({args.period} daily, "
              f"cost/side={args.cost*100:.3f}%)")
        print("=" * 66)
        try:
            df = load_yfinance(sym, period=args.period, interval="1d")
        except Exception as e:
            print(f"  ERROR: {e}")
            continue
        bh = df["close"].pct_change().fillna(0.0)
        s = int(args.train_frac * len(df))
        bh_oos = _stats(bh.iloc[s:])
        print(f"  {len(df)} bars.  Buy & hold OOS: ret={bh_oos['ret']*100:+.0f}%  "
              f"DD={bh_oos['dd']*100:.0f}%  ret/DD={bh_oos['radj']:.2f}  Sharpe={bh_oos['sharpe']:.2f}\n")

        print(f"  {'param':<12}{'fullPF·ret':>12}{'OOS ret':>9}{'OOS DD':>8}"
              f"{'ret/DD':>8}{'Sharpe':>8}{'live':>7}")
        for name, fn in PARAMS.items():
            net = strat_net(df, fn(df), args.cost)
            full, oos = _stats(net), _stats(net.iloc[s:])
            live = fn(df).iloc[-1]
            live_s = "LONG" if live > 0 else ("SHORT" if live < 0 else "flat")
            beat = "✅" if oos["radj"] > bh_oos["radj"] and oos["ret"] > bh_oos["ret"] else ""
            print(f"  {name:<12}{full['ret']*100:>11.0f}%{oos['ret']*100:>8.0f}%"
                  f"{oos['dd']*100:>7.0f}%{oos['radj']:>8.2f}{oos['sharpe']:>8.2f}{live_s:>7}{beat}")

        wf, picks, n_oos = walk_forward(df, args.cost)
        rnd_radj, rnd_sh = random_control(df, args.cost)
        print(f"\n  WALK-FORWARD (honest, {n_oos} OOS days): ret={wf['ret']*100:+.0f}%  "
              f"DD={wf['dd']*100:.0f}%  ret/DD={wf['radj']:.2f}  Sharpe={wf['sharpe']:.2f}")
        print(f"    folds picked: {', '.join(f'{f}:{n}' for f, n in picks)}")
        print(f"  RANDOM long/short control: median ret/DD={rnd_radj:.2f}  Sharpe={rnd_sh:.2f}")
        beats_rng = wf["sharpe"] > rnd_sh + 0.2 and wf["radj"] > rnd_radj
        beats_bh = wf["radj"] > bh_oos["radj"]
        if beats_rng and beats_bh:
            print("  ✅ Walk-forward THẮNG cả random LẪN buy & hold (risk-adjusted) ⇒ edge THẬT.")
        elif beats_rng:
            print("  🟡 Thắng random nhưng không vượt buy & hold ⇒ edge yếu / chỉ giảm rủi ro.")
        else:
            print("  🔴 Không vượt random ⇒ KHÔNG có edge bền (phần lớn là may rủi).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
