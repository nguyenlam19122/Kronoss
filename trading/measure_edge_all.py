"""Measure forecast *edge* across many instruments in one run (no trading).

Loads the predictor **once** and evaluates every file, so a single Kronos load
serves all symbols. Prints a side-by-side table of directional accuracy / IC so
you can see, at a glance, where (if anywhere) the model has predictive edge.

Examples
--------
Baseline sanity check (no model / no network)::

    python -m trading.measure_edge_all --csv *.csv --predictor momentum

Real Kronos edge across all your M30 files (needs weights; GPU recommended)::

    python -m trading.measure_edge_all --predictor kronos --model NeoQuasar/Kronos-small \
        --lookback 256 --pred-len 24 --signal-every 4 \
        --csv XAUUSD_M30.csv US30_M30.csv US500_M30.csv USTEC_M30.csv BTC_M30.csv
"""

from __future__ import annotations

import argparse

from .data import load_csv
from .diagnostics import EdgeConfig, measure_edge
from .signals import SignalConfig


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Batch edge measurement (directional accuracy / IC) across instruments.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--csv", nargs="+", required=True, help="One or more CSV files (MT5 auto-detected).")
    p.add_argument("--predictor", default="kronos", choices=["kronos", "persistence", "momentum"])
    p.add_argument("--model", default="NeoQuasar/Kronos-small")
    p.add_argument("--tokenizer", default="NeoQuasar/Kronos-Tokenizer-base")
    p.add_argument("--device", default=None)
    p.add_argument("--max-context", type=int, default=512)
    p.add_argument("--lookback", type=int, default=256)
    p.add_argument("--pred-len", type=int, default=24)
    p.add_argument("--signal-every", type=int, default=4)
    p.add_argument("--signal-mode", default="mean", choices=["mean", "endpoint", "slope"])
    p.add_argument("--horizon", type=int, default=None)
    p.add_argument("--ensemble", type=int, default=0, help="N stochastic forecasts (Kronos only).")
    p.add_argument("--last-n", type=int, default=None, help="Use only the last N bars per file.")
    return p


def _build_predict_fn(args, sig):
    if args.predictor in ("persistence", "momentum"):
        from .baselines import momentum_predict_fn, persistence_predict_fn
        return momentum_predict_fn() if args.predictor == "momentum" else persistence_predict_fn()
    from .predictor import (load_kronos_predictor, make_kronos_predict_fn,
                            make_kronos_ensemble_predict_fn)
    kp = load_kronos_predictor(args.model, args.tokenizer, args.device, args.max_context)
    if args.ensemble and args.ensemble > 1:
        return make_kronos_ensemble_predict_fn(kp, n_samples=args.ensemble, signal=sig)
    return make_kronos_predict_fn(kp)


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    sig = SignalConfig(mode=args.signal_mode, horizon=args.horizon)

    print(f"🧠 Loading predictor: {args.predictor}"
          + (f" (ensemble x{args.ensemble})" if args.ensemble else "") + " ...")
    predict_fn = _build_predict_fn(args, sig)

    cfg = EdgeConfig(lookback=args.lookback, pred_len=args.pred_len,
                     signal_every=args.signal_every, signal=sig)

    rows = []
    for path in args.csv:
        df = load_csv(path)
        if args.last_n:
            df = df.iloc[-args.last_n:]
        name = df.attrs.get("instrument", path).split("_")[0].split("-")[-1]
        print(f"\n📊 {name}  ({len(df)} bars)")
        try:
            r = measure_edge(df, predict_fn, cfg, verbose=True)
            rows.append((name, r))
        except Exception as e:  # keep going across files
            print(f"   ⚠️ skipped: {e}")

    # --- summary table ---
    print("\n" + "=" * 74)
    print("📋 EDGE SUMMARY  (accuracy > ~55% with small p = real edge)")
    print("=" * 74)
    print(f"  {'instrument':<12}{'samples':>8}{'accuracy':>10}{'p':>8}{'IC':>8}{'rankIC':>8}  verdict")
    for name, r in rows:
        if r.get("n_samples", 0) == 0:
            print(f"  {name:<12}{'0':>8}   (no forecasts)")
            continue
        acc = r["directional_accuracy"]
        verdict = ("✅ edge" if acc >= 0.55 else "🟡 nhẹ" if acc >= 0.52
                   else "⚪ ~random" if acc >= 0.48 else "🔴 ngược")
        print(f"  {name:<12}{r['n_samples']:>8}{acc:>9.2%}{r['accuracy_pvalue']:>8.3f}"
              f"{r['pearson_ic']:>8.3f}{r['rank_ic']:>8.3f}  {verdict}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
