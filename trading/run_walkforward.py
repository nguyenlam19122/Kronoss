"""CLI: honest out-of-sample profit-factor via walk-forward optimisation.

Forecasts are cached once, then strategy parameters are grid-searched on past
segments and scored on the next (out-of-sample) segment. Run it for the model
AND for a random baseline — a real edge must beat random OOS PF.

Example::

    python -m trading.run_walkforward --csv trading/mydata/US30_M30.csv \
        --predictor kronos --model NeoQuasar/Kronos-small \
        --lookback 256 --pred-len 6 --signal-every 12 --n-folds 4
"""

from __future__ import annotations

import argparse

from .data import load_data
from .walkforward import (WFConfig, format_wf, precompute_signals,
                          run_param_grid, walk_forward)


def build_parser():
    p = argparse.ArgumentParser(description="Walk-forward out-of-sample profit factor.")
    p.add_argument("--csv"); p.add_argument("--symbol")
    p.add_argument("--predictor", default="kronos", choices=["kronos", "random"])
    p.add_argument("--model", default="NeoQuasar/Kronos-small")
    p.add_argument("--tokenizer", default="NeoQuasar/Kronos-Tokenizer-base")
    p.add_argument("--device", default=None)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--lookback", type=int, default=256)
    p.add_argument("--pred-len", type=int, default=6)
    p.add_argument("--signal-every", type=int, default=12)
    p.add_argument("--last-n", type=int, default=None)
    p.add_argument("--n-folds", type=int, default=4)
    p.add_argument("--risk-amount", type=float, default=25.0)
    p.add_argument("--slippage-points", type=float, default=5.0)
    p.add_argument("--max-leverage", type=float, default=30.0)
    p.add_argument("--name", default=None)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    df = load_data(symbol=args.symbol, csv=args.csv)
    if args.last_n:
        df = df.iloc[-args.last_n:]
    print(f"📥 {len(df)} bars | {df.index.min()} → {df.index.max()}")

    if args.predictor == "random":
        from .baselines import random_predict_fn
        predict_fn = random_predict_fn(seed=args.seed)
        print("🧠 Predictor: RANDOM baseline")
    else:
        from .predictor import load_kronos_predictor, make_kronos_predict_fn
        kp = load_kronos_predictor(args.model, args.tokenizer, args.device, max_context=512)
        predict_fn = make_kronos_predict_fn(kp)
        print(f"🧠 Predictor: kronos ({args.model})")

    wf = WFConfig(lookback=args.lookback, pred_len=args.pred_len, signal_every=args.signal_every,
                  n_folds=args.n_folds, risk_amount=args.risk_amount,
                  slippage_points=args.slippage_points, max_leverage=args.max_leverage)

    print("⏳ Precomputing forecasts (one model pass) ...")
    cache = precompute_signals(df, predict_fn, wf.lookback, wf.pred_len, wf.signal_every, verbose=True)
    print(f"   cached {len(cache)} decision points")
    print("🔎 Grid-searching strategy params over folds ...")
    trades = run_param_grid(df, cache, wf)
    result = walk_forward(trades, df, wf)

    name = args.name or args.predictor
    print("\n" + "=" * 60)
    print(f"📊 Walk-forward OOS profit factor — {name}")
    print("=" * 60)
    print(format_wf(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
