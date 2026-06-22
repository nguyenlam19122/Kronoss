"""Diversified time-series momentum (managed-futures style) — the honest edge.

Single-asset trend-following gives only a modest, risk-reducing edge (our gold
H4 test: it lowers drawdown but does NOT beat buy & hold on return). The
well-documented way to turn that into a real risk-adjusted edge is
DIVERSIFICATION: run the same long/short trend rule across many uncorrelated
assets (equities, bonds, commodities, crypto) and combine them at equal risk.
The bad stretches don't line up, and going short earns "crisis alpha" when
buy & hold bleeds (2008, 2022). Reference: Moskowitz, Ooi & Pedersen (2012),
"Time Series Momentum"; AQR managed-futures research.

Honest test (needs yfinance -> run on GitHub Actions): pull ~15y daily for a
diversified basket, build a long/short trend portfolio at equal risk, and judge
it OUT-OF-SAMPLE (last 40%, never used to choose anything) against a risk-parity
buy & hold portfolio on return, drawdown and Sharpe.
"""

from __future__ import annotations

import argparse

import numpy as np
import pandas as pd

from .data import load_yfinance
from .gold_strategy import ema_cross

# A deliberately diversified basket: equities, intl/EM, bonds, commodities, crypto.
DEFAULT_BASKET = ["SPY", "QQQ", "EFA", "EEM", "TLT", "IEF", "GLD", "SLV", "USO", "DBC", "BTC-USD"]


def tsmom(df: pd.DataFrame, lookback: int = 252) -> pd.Series:
    """Classic time-series momentum: long if the past-`lookback` return > 0 else short."""
    past = df["close"] / df["close"].shift(lookback) - 1.0
    return pd.Series(np.where(past > 0, 1.0, -1.0), index=df.index).where(past.notna(), 0.0)


def strat_net(df: pd.DataFrame, sig: pd.Series, cost: float) -> pd.Series:
    """Daily net return of holding `sig` (no look-ahead) with turnover cost."""
    pos = sig.reindex(df.index).shift(1).fillna(0.0)
    ret = df["close"].pct_change().fillna(0.0)
    turn = pos.diff().abs().fillna(pos.abs())
    return pos * ret - turn * cost


def vol_scaled(net: pd.Series, target_daily: float = 0.01, win: int = 60) -> pd.Series:
    """Scale a return stream to ~constant volatility (causal: trailing vol only)."""
    vol = net.rolling(win).std().shift(1)
    w = (target_daily / vol).clip(upper=3.0).fillna(0.0)
    return w * net


def _stats(net: pd.Series) -> dict:
    net = net.dropna()
    eq = (1 + net).cumprod()
    ret = float(eq.iloc[-1] - 1) if len(eq) else 0.0
    dd = float((eq / eq.cummax() - 1).min()) if len(eq) else 0.0
    sharpe = float(net.mean() / net.std() * np.sqrt(252)) if net.std() > 0 else 0.0
    return {"ret": ret, "dd": dd, "radj": ret / abs(dd) if dd < 0 else float("inf"),
            "sharpe": sharpe}


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Diversified trend portfolio vs buy & hold (OOS).")
    p.add_argument("--symbols", nargs="+", default=DEFAULT_BASKET)
    p.add_argument("--period", default="15y")
    p.add_argument("--cost", type=float, default=2e-4, help="Per-side cost as a return.")
    p.add_argument("--signal", default="ema", choices=["ema", "tsmom"])
    p.add_argument("--fast", type=int, default=50)
    p.add_argument("--slow", type=int, default=200)
    p.add_argument("--train-frac", type=float, default=0.6)
    args = p.parse_args(argv)

    def make_sig(df):
        return (ema_cross(df, args.fast, args.slow, long_only=False)
                if args.signal == "ema" else tsmom(df))

    print(f"Diversified trend portfolio — {args.signal} (fast={args.fast}, slow={args.slow}), "
          f"{args.period} daily, cost/side={args.cost*100:.3f}%\n")
    print(f"  Per-asset OUT-OF-SAMPLE (last {int((1-args.train_frac)*100)}%): trend vs buy & hold")
    print(f"  {'asset':<9}{'bars':>6}  {'strat ret':>10}{'stratDD':>8}{'s.ret/DD':>9}   "
          f"{'B&H ret':>8}{'B&HDD':>7}{'verdict':>10}")

    nets, bhs = {}, {}
    n_beat = 0
    for sym in args.symbols:
        try:
            df = load_yfinance(sym, period=args.period, interval="1d")
        except Exception as e:
            print(f"  {sym:<9} ERROR: {str(e)[:55]}")
            continue
        if len(df) < 400:
            print(f"  {sym:<9} (only {len(df)} bars — skipped)")
            continue
        net = strat_net(df, make_sig(df), args.cost)
        bh = df["close"].pct_change().fillna(0.0)
        nets[sym], bhs[sym] = net, bh
        s = int(args.train_frac * len(df))
        so, bo = _stats(net.iloc[s:]), _stats(bh.iloc[s:])
        beat = so["radj"] > bo["radj"]
        n_beat += int(beat)
        v = "✅beat" if beat else "🔴"
        print(f"  {sym:<9}{len(df):>6}  {so['ret']*100:>9.0f}%{so['dd']*100:>7.0f}%{so['radj']:>9.2f}   "
              f"{bo['ret']*100:>7.0f}%{bo['dd']*100:>6.0f}%{v:>10}")

    if len(nets) < 2:
        print("\n  Not enough assets loaded for a portfolio.")
        return 0

    # Combine at equal risk (vol-scaled), averaging over assets available each day.
    scaled = pd.DataFrame({s: vol_scaled(n) for s, n in nets.items()})
    port = scaled.mean(axis=1, skipna=True)
    # Risk-parity buy & hold benchmark: inverse-vol weighted long-only.
    bh_df = pd.DataFrame(bhs)
    inv_vol = 1.0 / bh_df.rolling(60).std().shift(1)
    w = inv_vol.div(inv_vol.sum(axis=1), axis=0)
    bh_port = (bh_df * w).sum(axis=1, skipna=True)

    common = port.dropna().index.intersection(bh_port.dropna().index)
    port, bh_port = port.loc[common], bh_port.loc[common]
    s = int(args.train_frac * len(port))
    P, B = _stats(port.iloc[s:]), _stats(bh_port.iloc[s:])
    spy_oos = _stats(bhs["SPY"].iloc[int(args.train_frac*len(bhs["SPY"])):]) if "SPY" in bhs else None

    print("\n" + "=" * 64)
    print(f"  PORTFOLIO — OUT-OF-SAMPLE (last {int((1-args.train_frac)*100)}%, {len(common)-s} days)")
    print(f"  {'':<22}{'return':>9}{'maxDD':>8}{'ret/DD':>8}{'Sharpe':>8}")
    print(f"  {'Diversified TREND':<22}{P['ret']*100:>8.0f}%{P['dd']*100:>7.0f}%{P['radj']:>8.2f}{P['sharpe']:>8.2f}")
    print(f"  {'Risk-parity BUY&HOLD':<22}{B['ret']*100:>8.0f}%{B['dd']*100:>7.0f}%{B['radj']:>8.2f}{B['sharpe']:>8.2f}")
    if spy_oos:
        print(f"  {'(ref) SPY buy & hold':<22}{spy_oos['ret']*100:>8.0f}%{spy_oos['dd']*100:>7.0f}%"
              f"{spy_oos['radj']:>8.2f}{spy_oos['sharpe']:>8.2f}")

    print()
    better_sharpe = P["sharpe"] > B["sharpe"]
    better_dd = abs(P["dd"]) < abs(B["dd"])
    if better_sharpe and better_dd:
        print("  ✅ Trend portfolio thắng buy & hold về RỦI RO (Sharpe cao hơn + sụt vốn ít hơn)")
        print("     ⇒ Edge BỀN, kiểu managed-futures: đa dạng hoá + long/short. Đáng đóng gói.")
    elif better_sharpe:
        print("  🟡 Sharpe cao hơn buy & hold nhưng sụt vốn không nhỏ hơn — edge yếu/khá.")
    else:
        print("  🔴 KHÔNG thắng buy & hold về Sharpe ⇒ ngay cả đa dạng hoá cũng không tạo edge ở đây.")
    print(f"\n  Per-asset trend beat B&H (ret/DD) OOS: {n_beat}/{len(nets)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
