"""Honest walk-forward profit-factor evaluation.

The only PF worth anything is the **out-of-sample** PF: strategy parameters are
chosen on past data and judged on future data the optimiser never saw. This
module makes that cheap by separating the two costs:

1. **Forecasts** (expensive) are computed once with the model and cached.
2. **Strategy parameters** (cheap) are then grid-searched by replaying the
   event-driven backtest over the cached signals — no model calls.

Walk-forward (expanding window): the timeline of trades is split into segments
S1..Sk. For each step the best parameters on the *prior* segments (in-sample)
are applied to the *next* segment (out-of-sample). Concatenating the OOS
segments gives an honest PF, plus the in-sample-vs-OOS gap that exposes
overfitting.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass

import numpy as np
import pandas as pd

from .signals import SignalConfig
from .sizing import SizingConfig
from .trade_sim import TradeConfig, run_trade_sim


# --------------------------------------------------------------------------- #
# 1. Cache the model's forecasts once
# --------------------------------------------------------------------------- #
def precompute_signals(df, predict_fn, lookback, pred_len, signal_every, verbose=True) -> dict:
    """Run the model at every decision point and cache pred_close by timestamp."""
    from .backtest import future_timestamps
    n = len(df)
    cache = {}
    points = list(range(lookback, n - 1, signal_every))
    for k, t in enumerate(points):
        ctx = df.iloc[t - lookback : t]
        y_ts = future_timestamps(df.index, t - 1, pred_len)
        pred = predict_fn(ctx, pd.Series(ctx.index), y_ts, pred_len)
        cache[df.index[t - 1]] = pred["close"].to_numpy(dtype=float)
        if verbose and (k + 1) % 50 == 0:
            print(f"   precompute {k + 1}/{len(points)}", flush=True)
    return cache


def make_cached_predict_fn(cache: dict, pred_len: int):
    """A predict_fn that returns cached forecasts (no model calls)."""
    def predict_fn(ctx, x_ts, y_ts, pl):
        key = ctx.index[-1]
        vals = cache.get(key)
        if vals is None:                       # unseen point -> neutral (no trade)
            last = float(ctx["close"].iloc[-1])
            vals = np.full(pl, last)
        vals = vals[:pl]
        idx = pd.Index(pd.Series(y_ts).values[: len(vals)], name="timestamps")
        return pd.DataFrame({"open": vals, "high": vals, "low": vals, "close": vals,
                             "volume": 0.0, "amount": 0.0}, index=idx)
    return predict_fn


# --------------------------------------------------------------------------- #
# 2. Strategy parameter grid -> trades per combo (cheap replay)
# --------------------------------------------------------------------------- #
@dataclass
class WFConfig:
    lookback: int = 256
    pred_len: int = 6
    signal_every: int = 12
    initial_capital: float = 5000.0
    risk_amount: float = 25.0
    max_leverage: float | None = 30.0
    slippage_points: float = 5.0
    n_folds: int = 4
    min_trades_is: int = 12     # ignore param combos with too few in-sample trades


DEFAULT_GRID = {
    "sl_atr": [1.0, 1.5, 2.0],
    "rr": [1.5, 2.0, 3.0],
    "trail": [False, True],
    "threshold": [0.0, 0.0005, 0.0015],
}


def _profit_factor(net: pd.Series) -> float:
    gp = net[net > 0].sum()
    gl = -net[net < 0].sum()
    return float(gp / gl) if gl > 0 else (float("inf") if gp > 0 else 0.0)


def run_param_grid(df, cache, wf: WFConfig, grid=None, allow_short=True) -> dict:
    """Backtest every parameter combo over the full series with cached signals."""
    grid = grid or DEFAULT_GRID
    predict_fn = make_cached_predict_fn(cache, wf.pred_len)
    keys = list(grid)
    out = {}
    for values in itertools.product(*[grid[k] for k in keys]):
        params = dict(zip(keys, values))
        cfg = TradeConfig(
            lookback=wf.lookback, pred_len=wf.pred_len, signal_every=wf.signal_every,
            sl_atr=params["sl_atr"], rr=params["rr"], trail=params["trail"],
            trail_atr=params["sl_atr"], trail_activate_r=1.0,
            signal=SignalConfig(mode="mean", long_threshold=params["threshold"],
                                short_threshold=params["threshold"], allow_short=allow_short),
            sizing=SizingConfig(mode="fixed", risk_amount=wf.risk_amount, max_leverage=wf.max_leverage),
            initial_capital=wf.initial_capital, slippage_points=wf.slippage_points,
        )
        res = run_trade_sim(df, predict_fn, cfg, verbose=False)
        trades = res["trades"]
        if len(trades):
            out[tuple(sorted(params.items()))] = trades[["entry_time", "net_pnl"]].copy()
    return out


# --------------------------------------------------------------------------- #
# 3. Walk-forward: optimise on past segments, score on the next (OOS)
# --------------------------------------------------------------------------- #
def walk_forward(trades_by_combo: dict, df, wf: WFConfig) -> dict:
    """Return out-of-sample PF and the in-sample/OOS optimism gap."""
    if not trades_by_combo:
        return {"oos_profit_factor": None, "note": "no trades from any parameter set"}

    # segment the timeline into n_folds equal-time chunks
    t0, t1 = df.index[wf.lookback], df.index[-1]
    edges = pd.date_range(t0, t1, periods=wf.n_folds + 1)

    oos_parts, is_pfs, per_fold = [], [], []
    for f in range(1, wf.n_folds):                 # need >=1 prior segment to optimise
        is_end = edges[f]
        oos_start, oos_end = edges[f], edges[f + 1]

        best_combo, best_is_pf, best_is_n = None, -np.inf, 0
        for combo, tr in trades_by_combo.items():
            is_tr = tr[tr["entry_time"] < is_end]["net_pnl"]
            if len(is_tr) < wf.min_trades_is:
                continue
            pf = _profit_factor(is_tr)
            if pf > best_is_pf:
                best_is_pf, best_combo, best_is_n = pf, combo, len(is_tr)
        if best_combo is None:
            continue

        tr = trades_by_combo[best_combo]
        oos_tr = tr[(tr["entry_time"] >= oos_start) & (tr["entry_time"] < oos_end)]["net_pnl"]
        oos_parts.append(oos_tr)
        is_pfs.append(best_is_pf)
        params = dict(best_combo) if isinstance(best_combo, (tuple, list)) else best_combo
        per_fold.append({
            "fold": f, "oos_window": f"{oos_start.date()}→{oos_end.date()}",
            "params": params, "in_sample_pf": round(best_is_pf, 3),
            "in_sample_trades": best_is_n,
            "oos_trades": int(len(oos_tr)),
            "oos_pf": round(_profit_factor(oos_tr), 3) if len(oos_tr) else None,
            "oos_net": round(float(oos_tr.sum()), 2),
        })

    oos = pd.concat(oos_parts) if oos_parts else pd.Series(dtype=float)
    oos_pf = _profit_factor(oos) if len(oos) else None
    return {
        "oos_profit_factor": round(oos_pf, 3) if oos_pf is not None else None,
        "oos_trades": int(len(oos)),
        "oos_net_profit": round(float(oos.sum()), 2) if len(oos) else 0.0,
        "oos_win_rate": round(float((oos > 0).mean()), 4) if len(oos) else None,
        "mean_in_sample_pf": round(float(np.mean(is_pfs)), 3) if is_pfs else None,
        "optimism_gap": (round(float(np.mean(is_pfs)) - oos_pf, 3)
                         if is_pfs and oos_pf is not None else None),
        "per_fold": per_fold,
        "n_param_combos": len(trades_by_combo),
    }


def format_wf(r: dict) -> str:
    if r.get("oos_profit_factor") is None:
        return "  (no out-of-sample trades) " + r.get("note", "")
    pf = r["oos_profit_factor"]
    verdict = "✅ ĐẠT (>1.2)" if pf >= 1.2 else ("🟡 gần" if pf >= 1.0 else "🔴 lỗ (<1.0)")
    lines = [
        f"  Out-of-sample PF      : {pf}   → {verdict}",
        f"  OOS trades            : {r['oos_trades']}",
        f"  OOS net profit        : ${r['oos_net_profit']:,.2f}",
        f"  OOS win rate          : {r['oos_win_rate']:.1%}" if r["oos_win_rate"] is not None else "  OOS win rate          : n/a",
        f"  Mean in-sample PF     : {r['mean_in_sample_pf']}",
        f"  Optimism gap (IS−OOS) : {r['optimism_gap']}   (lớn = overfit nặng)",
        "  Per-fold:",
    ]
    for pf_ in r["per_fold"]:
        lines.append(f"    [{pf_['fold']}] {pf_['oos_window']}  IS_PF={pf_['in_sample_pf']} "
                     f"→ OOS_PF={pf_['oos_pf']} ({pf_['oos_trades']} trades)  {pf_['params']}")
    return "\n".join(lines)
