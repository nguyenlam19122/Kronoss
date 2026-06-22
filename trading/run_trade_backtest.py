"""CLI for the realistic event-driven backtest (entry / SL / TP / R-sizing / costs).

Examples
--------
Baseline smoke test on a MetaTrader CSV (no model / no network)::

    python -m trading.run_trade_backtest --csv XAUUSDm_M5.csv \
        --predictor momentum --sl-atr 1.5 --rr 2 --risk-amount 25

Real Kronos run on your Gold M5 data (needs weights; GPU recommended)::

    python -m trading.run_trade_backtest --csv XAUUSDm_M5.csv \
        --predictor kronos --model NeoQuasar/Kronos-small \
        --lookback 256 --pred-len 24 --signal-every 12 \
        --sl-atr 1.5 --rr 2 --risk-amount 25 --initial-capital 5000 \
        --slippage-points 5 --commission-bps 0
"""

from __future__ import annotations

import argparse
import os

from .data import load_data, resolve_symbol
from .run_backtest import make_predict_fn  # reuse predictor builder
from .signals import SignalConfig
from .sizing import SizingConfig
from .trade_sim import TradeConfig, format_trade_metrics, run_trade_sim, save_trade_results


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Kronos event-driven backtest with SL/TP, R-based sizing and explicit costs.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    src = p.add_argument_group("data source")
    src.add_argument("--symbol", help="Ticker/alias for yfinance (btc, gold, eurusd, AAPL ...).")
    src.add_argument("--csv", help="Local CSV (auto-detects MetaTrader 5 exports).")
    src.add_argument("--interval", default="1d")
    src.add_argument("--start"); src.add_argument("--end"); src.add_argument("--period")

    mdl = p.add_argument_group("predictor")
    mdl.add_argument("--predictor", default="kronos",
                     choices=["kronos", "persistence", "momentum"])
    mdl.add_argument("--model", default="NeoQuasar/Kronos-small")
    mdl.add_argument("--tokenizer", default="NeoQuasar/Kronos-Tokenizer-base")
    mdl.add_argument("--device", default=None)
    mdl.add_argument("--max-context", type=int, default=512)
    mdl.add_argument("--T", type=float, default=1.0)
    mdl.add_argument("--top-p", type=float, default=0.9)
    mdl.add_argument("--top-k", type=int, default=0)
    mdl.add_argument("--sample-count", type=int, default=1)

    sig = p.add_argument_group("signal")
    sig.add_argument("--signal-mode", default="mean", choices=["mean", "endpoint", "slope"])
    sig.add_argument("--horizon", type=int, default=None)
    sig.add_argument("--long-threshold", type=float, default=0.0)
    sig.add_argument("--short-threshold", type=float, default=0.0)
    sig.add_argument("--no-short", action="store_true")
    sig.add_argument("--lookback", type=int, default=256)
    sig.add_argument("--pred-len", type=int, default=24)
    sig.add_argument("--signal-every", type=int, default=None,
                     help="Bars between model queries while flat (default pred_len).")

    risk = p.add_argument_group("stop-loss / take-profit")
    risk.add_argument("--atr-period", type=int, default=14)
    risk.add_argument("--sl-atr", type=float, default=1.5, help="Stop distance = sl_atr * ATR (= 1R).")
    risk.add_argument("--rr", type=float, default=2.0, help="Take-profit = rr * stop distance (<=0 disables TP).")
    risk.add_argument("--max-hold", type=int, default=None, help="Time-exit (bars; default pred_len).")
    risk.add_argument("--trail", action="store_true", help="Enable a trailing stop.")
    risk.add_argument("--trail-atr", type=float, default=1.5,
                      help="Trailing distance behind the favourable extreme (× ATR).")
    risk.add_argument("--trail-activate-r", type=float, default=1.0,
                      help="Start trailing only after +this many R in profit.")

    flt = p.add_argument_group("entry filters")
    flt.add_argument("--trend-filter", action="store_true",
                     help="Only trade in the direction of the EMA trend.")
    flt.add_argument("--trend-ema", type=int, default=200, help="EMA period for the trend filter.")
    flt.add_argument("--min-expected-r", type=float, default=0.0,
                     help="Forecast must predict at least this many R of move to trade.")
    flt.add_argument("--ensemble", type=int, default=0,
                     help="Run N stochastic forecasts per signal to estimate confidence (needs Kronos).")
    flt.add_argument("--min-confidence", type=float, default=0.0,
                     help="Skip trades when ensemble agreement < this (0..1; requires --ensemble).")

    diag = p.add_argument_group("diagnostics")
    diag.add_argument("--edge-only", action="store_true",
                      help="Measure forecast edge (accuracy / IC) instead of backtesting.")

    sz = p.add_argument_group("sizing / account")
    sz.add_argument("--risk-mode", default="fixed", choices=["fixed", "percent"])
    sz.add_argument("--risk-amount", type=float, default=25.0, help="1R in $ (fixed mode).")
    sz.add_argument("--risk-pct", type=float, default=0.005, help="1R as fraction of equity (percent mode).")
    sz.add_argument("--initial-capital", type=float, default=5000.0)
    sz.add_argument("--max-leverage", type=float, default=None)

    cost = p.add_argument_group("costs")
    cost.add_argument("--no-data-spread", action="store_true",
                      help="Ignore the per-bar spread column; use --spread-points instead.")
    cost.add_argument("--spread-points", type=float, default=0.0,
                      help="Fixed spread in points (used when no spread column / --no-data-spread).")
    cost.add_argument("--slippage-points", type=float, default=0.0,
                      help="Adverse slippage per side, in points.")
    cost.add_argument("--commission-bps", type=float, default=0.0,
                      help="Commission per side, in basis points of notional (1 bp = 0.01%).")
    cost.add_argument("--commission-per-trade", type=float, default=0.0,
                      help="Flat commission per round-trip ($).")

    out = p.add_argument_group("output")
    out.add_argument("--out-dir", default="trading/results")
    out.add_argument("--name", default=None)
    out.add_argument("--quiet", action="store_true")
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)

    label = args.symbol or args.csv or "data"
    print(f"📥 Loading data: {label} ...")
    df = load_data(symbol=args.symbol, csv=args.csv, start=args.start, end=args.end,
                   period=args.period, interval=args.interval)
    point = df.attrs.get("point", 1.0)
    has_spread = "spread" in df.columns
    print(f"   {len(df)} bars, {df.index.min()} → {df.index.max()} | point={point} | "
          f"per-bar spread: {'yes' if has_spread else 'no'}")

    sig_cfg = SignalConfig(mode=args.signal_mode, horizon=args.horizon,
                           long_threshold=args.long_threshold,
                           short_threshold=args.short_threshold, allow_short=not args.no_short)

    print(f"🧠 Predictor: {args.predictor}" + (f" (ensemble x{args.ensemble})" if args.ensemble else ""))
    if args.ensemble and args.predictor == "kronos":
        from .predictor import load_kronos_predictor, make_kronos_ensemble_predict_fn
        kp = load_kronos_predictor(args.model, args.tokenizer, args.device, args.max_context)
        predict_fn = make_kronos_ensemble_predict_fn(
            kp, n_samples=args.ensemble, T=args.T, top_p=args.top_p, top_k=args.top_k, signal=sig_cfg)
    else:
        predict_fn = make_predict_fn(args)

    # --- diagnostics: measure edge instead of trading ---
    if args.edge_only:
        from .diagnostics import EdgeConfig, measure_edge
        print("\n🔬 Measuring forecast edge (no trading) ...")
        print("=" * 60)
        measure_edge(df, predict_fn, EdgeConfig(
            lookback=args.lookback, pred_len=args.pred_len,
            signal_every=args.signal_every, signal=sig_cfg), verbose=True)
        return 0

    cfg = TradeConfig(
        lookback=args.lookback, pred_len=args.pred_len, signal_every=args.signal_every,
        signal=sig_cfg,
        atr_period=args.atr_period, sl_atr=args.sl_atr, rr=args.rr, max_hold=args.max_hold,
        trail=args.trail, trail_atr=args.trail_atr, trail_activate_r=args.trail_activate_r,
        trend_filter=args.trend_filter, trend_ema=args.trend_ema,
        min_confidence=args.min_confidence, min_expected_r=args.min_expected_r,
        sizing=SizingConfig(mode=args.risk_mode, risk_amount=args.risk_amount,
                            risk_pct=args.risk_pct, max_leverage=args.max_leverage),
        initial_capital=args.initial_capital,
        use_data_spread=not args.no_data_spread, spread_points=args.spread_points,
        slippage_points=args.slippage_points,
        commission_per_notional=args.commission_bps / 1e4,
        commission_per_trade=args.commission_per_trade,
    )

    print("🚀 Running event-driven backtest (entry/SL/TP/sizing/costs) ...")
    result = run_trade_sim(df, predict_fn, cfg, verbose=not args.quiet)

    if args.name:
        name = args.name
    elif args.symbol:
        name = f"{resolve_symbol(args.symbol).replace('=', '').replace('/', '_')}_{args.predictor}"
    else:
        name = f"{df.attrs.get('instrument', os.path.splitext(os.path.basename(args.csv))[0])}_{args.predictor}"

    print("\n" + "=" * 60)
    print(f"📊 Trade backtest report — {name}")
    print("=" * 60)
    print(format_trade_metrics(result["metrics"]))

    paths = save_trade_results(result, args.out_dir, name)
    print("\n💾 Saved:")
    for kk, vv in paths.items():
        print(f"   {kk:<8}: {vv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
