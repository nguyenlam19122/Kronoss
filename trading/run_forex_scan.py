"""Scan many FX pairs for a robust mean-reversion edge (anti-overfit test).

Pulls multiple currency pairs from Yahoo Finance (needs open internet — run on
GitHub Actions, not the sandboxed env), then for each pair runs an honest
holdout: pick the best mean-reversion config on the first 60% and report its
profit factor on the untouched last 40%. It also applies ONE fixed config to
every pair — if the same rule clears PF > 1.2 across several pairs, the edge is
robust rather than an EURUSD-specific curve-fit.
"""

from __future__ import annotations

import argparse

from .data import load_yfinance
from .gold_strategy import backtest_signal, bollinger_meanrev, rsi_meanrev
from .walkforward import _profit_factor


def _pf(df, sig, cost, min_trades=10):
    tr, _ = backtest_signal(df, sig, cost)
    return (_profit_factor(tr["net_pnl"]), len(tr)) if len(tr) >= min_trades else (None, len(tr))


def _reality(df, sig, cost):
    """Risk reality behind the PF: a no-stop long-only mean-reversion 'holds the
    dip' and can show a huge PF while sitting through a brutal open drawdown.
    Report %time-in-market, strategy return & max DD vs plain buy & hold."""
    tr, net = backtest_signal(df, sig, cost)
    pos = sig.reindex(df.index).shift(1).fillna(0.0)
    eq = (1 + net).cumprod()
    s_ret = float(eq.iloc[-1] - 1)
    s_dd = float((eq / eq.cummax() - 1).min())
    bh = df["close"] / float(df["close"].iloc[0])
    bh_ret = float(bh.iloc[-1] - 1)
    bh_dd = float((bh / bh.cummax() - 1).min())
    return {"time_in_mkt": float((pos != 0).mean()), "trades": len(tr),
            "strat_ret": s_ret, "strat_dd": s_dd, "bh_ret": bh_ret, "bh_dd": bh_dd}


def search_configs():
    cfgs = {}
    for n in (20, 30):
        for k in (1.5, 2.0, 2.5):
            cfgs[f"boll_{n}_{k}"] = lambda d, n=n, k=k: bollinger_meanrev(d, n, k, long_only=True)
    for p, lo in ((2, 5), (7, 15), (14, 25)):
        cfgs[f"rsi_{p}_{lo}"] = lambda d, p=p, lo=lo: rsi_meanrev(d, p, lo, 100 - lo, long_only=True)
    return cfgs


def holdout(df, cost, train_frac=0.6):
    """Pick best mean-reversion config on train; score on untouched test."""
    s = int(train_frac * len(df))
    tr, te = df.iloc[:s], df.iloc[s:]
    best = None
    for name, fn in search_configs().items():
        pf, n = _pf(tr, fn(tr), cost, 12)
        if pf and (best is None or pf > best[1]):
            best = (name, pf, fn)
    if best is None:
        return None
    test_pf, test_n = _pf(te, best[2](te), cost, 8)
    return {"picked": best[0], "train_pf": round(best[1], 2),
            "test_pf": round(test_pf, 2) if test_pf else None, "test_trades": test_n}


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Multi-pair FX mean-reversion robustness scan.")
    p.add_argument("--symbols", nargs="+",
                   default=["eurusd", "gbpusd", "audusd", "usdjpy", "usdchf", "usdcad", "nzdusd"])
    p.add_argument("--interval", default="1h")
    p.add_argument("--period", default="730d")
    p.add_argument("--cost-frac", type=float, default=7e-5, help="Per-side cost as a return (~1 pip).")
    p.add_argument("--fixed", default="boll_30_2.0", help="One config applied to every pair.")
    args = p.parse_args(argv)

    def fixed_sig(d):
        return bollinger_meanrev(d, 30, 2.0, long_only=True)

    print(f"Scan: {args.interval}, {args.period}, cost/side={args.cost_frac*100:.4f}%\n")
    print(f"  {'pair':<9}{'bars':>7}  {'A) holdout pick':<16}{'TRAIN':>7}{'TEST':>7}   "
          f"{'B) fixed '+args.fixed:<18}{'TEST_PF':>8}")
    n_pass_a = n_pass_b = n_ok = 0
    reality_rows = []
    for sym in args.symbols:
        try:
            df = load_yfinance(sym, period=args.period, interval=args.interval)
        except Exception as e:
            print(f"  {sym.upper():<9} ERROR: {str(e)[:60]}")
            continue
        n_ok += 1
        h = holdout(df, args.cost_frac)
        # fixed-config: honest = test-half PF (last 40%), no per-pair selection
        s = int(0.6 * len(df))
        te = df.iloc[s:]
        fx_pf, fx_n = _pf(te, fixed_sig(te), args.cost_frac, 8)
        reality_rows.append((sym.upper(), _reality(te, fixed_sig(te), args.cost_frac)))
        a_test = h["test_pf"] if h else None
        va = "✅" if a_test and a_test > 1.2 else ("🟡" if a_test and a_test > 1.0 else "🔴")
        vb = "✅" if fx_pf and fx_pf > 1.2 else ("🟡" if fx_pf and fx_pf > 1.0 else "🔴")
        if a_test and a_test > 1.2: n_pass_a += 1
        if fx_pf and fx_pf > 1.2: n_pass_b += 1
        pick = h["picked"] if h else "n/a"
        trp = h["train_pf"] if h else None
        print(f"  {sym.upper():<9}{len(df):>7}  {pick:<16}{str(trp):>7}{str(a_test):>6}{va} "
              f"  {'':<18}{str(round(fx_pf,2) if fx_pf else None):>6}{vb}")

    # Reality check: a giant no-stop long-only PF can just be "hold the bull
    # market" with a hidden open drawdown. Compare to plain buy & hold.
    if reality_rows:
        print(f"\n  REALITY CHECK — fixed {args.fixed}, test half (is the PF real edge or hidden beta?)")
        print(f"  {'pair':<9}{'%inMkt':>7}{'trades':>7}{'stratRet':>9}{'stratDD':>8}   "
              f"{'B&Hret':>8}{'B&HDD':>7}")
        for name, r in reality_rows:
            print(f"  {name:<9}{r['time_in_mkt']*100:>6.0f}%{r['trades']:>7}"
                  f"{r['strat_ret']*100:>8.0f}%{r['strat_dd']*100:>7.0f}%   "
                  f"{r['bh_ret']*100:>7.0f}%{r['bh_dd']*100:>6.0f}%")

    print(f"\n  (A) holdout-pick > 1.2 OOS : {n_pass_a}/{n_ok} pairs")
    print(f"  (B) fixed boll_30_2.0 > 1.2: {n_pass_b}/{n_ok} pairs  ← robustness (same rule, many pairs)")
    if n_pass_b >= max(2, n_ok // 2):
        print("  → Cùng 1 quy tắc đạt >1.2 trên nhiều cặp ⇒ edge BỀN, không phải overfit riêng EURUSD.")
    else:
        print("  → Quy tắc KHÔNG bền qua nhiều cặp ⇒ phần lớn là overfit / phụ thuộc cặp & giai đoạn.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
