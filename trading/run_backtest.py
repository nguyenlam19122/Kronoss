"""End-to-end CLI: fetch data -> Kronos forecast -> signal -> walk-forward backtest.

Examples
--------
Smoke-test the pipeline with a baseline (no model / no network needed)::

    python -m trading.run_backtest --csv finetune_csv/data/HK_ali_09988_kline_5min_all.csv \
        --predictor momentum --lookback 256 --pred-len 24

Real Kronos backtest on Bitcoin daily candles (needs weights + Yahoo access)::

    python -m trading.run_backtest --symbol btc --interval 1d --period 3y \
        --predictor kronos --model NeoQuasar/Kronos-small --pred-len 24 --sample-count 3

Other assets: ``--symbol gold``, ``--symbol eurusd``, ``--symbol AAPL`` ...
"""

from __future__ import annotations

import argparse
import os
import sys

from .backtest import BacktestConfig, format_metrics, run_walk_forward, save_results
from .data import load_data, resolve_symbol
from .signals import SignalConfig


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Kronos signal + walk-forward backtest for Forex / Gold / BTC / US stocks.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    src = p.add_argument_group("data source")
    src.add_argument("--symbol", help="Ticker or alias: btc, gold, eurusd, AAPL ...")
    src.add_argument("--csv", help="Local CSV instead of Yahoo Finance.")
    src.add_argument("--interval", default="1d", help="Candle size: 1d, 1h, 15m ...")
    src.add_argument("--start", help="Start date YYYY-MM-DD (yfinance).")
    src.add_argument("--end", help="End date YYYY-MM-DD (yfinance).")
    src.add_argument("--period", help="Relative range e.g. 3y, 60d (overrides start/end).")

    mdl = p.add_argument_group("predictor")
    mdl.add_argument("--predictor", default="kronos",
                     choices=["kronos", "persistence", "momentum"],
                     help="kronos = real model; others are baselines (no weights).")
    mdl.add_argument("--model", default="NeoQuasar/Kronos-small", help="HF id or local path.")
    mdl.add_argument("--tokenizer", default="NeoQuasar/Kronos-Tokenizer-base")
    mdl.add_argument("--device", default=None, help="cuda:0 | cpu | mps (auto if unset).")
    mdl.add_argument("--max-context", type=int, default=512)
    mdl.add_argument("--T", type=float, default=1.0, help="Sampling temperature.")
    mdl.add_argument("--top-p", type=float, default=0.9)
    mdl.add_argument("--top-k", type=int, default=0)
    mdl.add_argument("--sample-count", type=int, default=1,
                     help="Forecast paths to average (>=2 stabilises signals).")

    sig = p.add_argument_group("signal")
    sig.add_argument("--signal-mode", default="mean", choices=["mean", "endpoint", "slope"])
    sig.add_argument("--horizon", type=int, default=None,
                     help="Forecast bars used for the signal (default: all pred_len).")
    sig.add_argument("--long-threshold", type=float, default=0.0)
    sig.add_argument("--short-threshold", type=float, default=0.0)
    sig.add_argument("--no-short", action="store_true", help="Long/flat only.")

    bt = p.add_argument_group("backtest")
    bt.add_argument("--lookback", type=int, default=400, help="Context candles (<= max_context).")
    bt.add_argument("--pred-len", type=int, default=24, help="Candles forecast per step.")
    bt.add_argument("--step", type=int, default=None, help="Rebalance interval (default pred_len).")
    bt.add_argument("--cost", type=float, default=0.0005, help="Per-side cost fraction.")
    bt.add_argument("--rf", type=float, default=0.0, help="Annual risk-free rate.")
    bt.add_argument("--bars-per-year", type=float, default=None,
                    help="Annualisation factor (default: inferred from spacing).")

    out = p.add_argument_group("output")
    out.add_argument("--out-dir", default="trading/results")
    out.add_argument("--name", default=None, help="Run name (default derived from symbol).")
    out.add_argument("--quiet", action="store_true", help="Suppress per-step logging.")
    return p


def make_predict_fn(args):
    """Build the predict_fn for the chosen predictor."""
    if args.predictor == "persistence":
        from .baselines import persistence_predict_fn
        return persistence_predict_fn()
    if args.predictor == "momentum":
        from .baselines import momentum_predict_fn
        return momentum_predict_fn()

    # Real Kronos model.
    from .predictor import load_kronos_predictor, make_kronos_predict_fn
    predictor = load_kronos_predictor(
        model_name=args.model,
        tokenizer_name=args.tokenizer,
        device=args.device,
        max_context=args.max_context,
    )
    return make_kronos_predict_fn(
        predictor, T=args.T, top_p=args.top_p, top_k=args.top_k,
        sample_count=args.sample_count,
    )


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)

    if args.lookback > args.max_context:
        print(f"⚠️  lookback ({args.lookback}) > max_context ({args.max_context}); "
              f"the model will truncate context.", file=sys.stderr)

    # 1. Data
    label = args.symbol or args.csv or "data"
    print(f"📥 Loading data: {label} ...")
    df = load_data(
        symbol=args.symbol, csv=args.csv, start=args.start, end=args.end,
        period=args.period, interval=args.interval,
    )
    print(f"   {len(df)} bars, {df.index.min()} → {df.index.max()}")

    # 2. Predictor
    print(f"🧠 Predictor: {args.predictor}")
    predict_fn = make_predict_fn(args)

    # 3. Backtest
    cfg = BacktestConfig(
        lookback=args.lookback, pred_len=args.pred_len, step=args.step,
        cost=args.cost, rf_annual=args.rf, bars_per_year=args.bars_per_year,
        signal=SignalConfig(
            mode=args.signal_mode, horizon=args.horizon,
            long_threshold=args.long_threshold, short_threshold=args.short_threshold,
            allow_short=not args.no_short,
        ),
    )
    print("🚀 Running walk-forward backtest ...")
    result = run_walk_forward(df, predict_fn, cfg, verbose=not args.quiet)

    # 4. Report
    if args.name:
        name = args.name
    else:
        if args.symbol:
            base = resolve_symbol(args.symbol).replace("=", "").replace("/", "_")
        else:
            base = os.path.splitext(os.path.basename(args.csv))[0]
        name = f"{base}_{args.predictor}"
    print("\n" + "=" * 60)
    print(f"📊 Backtest report — {name}")
    print("=" * 60)
    print(format_metrics(result["metrics"]))

    paths = save_results(result, args.out_dir, name)
    print("\n💾 Saved:")
    for k, v in paths.items():
        print(f"   {k:<8}: {v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
