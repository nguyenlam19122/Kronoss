"""Walk-forward backtest engine for Kronos-based signals.

The engine is deliberately model-agnostic: it receives a ``predict_fn`` callable
and only ever reads the *direction* of the forecast, so it can be exercised with
the real :class:`KronosPredictor`, a naive baseline, or a synthetic stub in
tests. There is **no look-ahead**: the position held over bar ``j`` is decided
using only candles up to bar ``j-1``.

Walk-forward loop
-----------------
At each decision point ``t`` (standing at the close of bar ``t-1``):

1. context  = candles ``[t-lookback : t]``  (history only)
2. forecast = ``predict_fn(context, ...)``  -> ``pred_len`` future candles
3. position = sign of the forecast vs the last close (see :mod:`trading.signals`)
4. that position is applied to the *actual* close-to-close returns of the next
   ``step`` bars; transaction costs are charged on position changes.

``t`` then advances by ``step`` (default ``pred_len`` -> non-overlapping holds).

Assumptions / simplifications (documented on purpose):
    * Fills at the close; returns are close-to-close.
    * Costs modelled as a flat per-side fraction on turnover (covers commission
      + a slippage allowance). Intrabar fills and market impact are not modelled.
    * Annualisation factor is inferred from the median bar spacing.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, asdict
from typing import Callable

import numpy as np
import pandas as pd

from .signals import SignalConfig, expected_return, position_from_forecast

# predict_fn(context_df, x_timestamp, y_timestamp, pred_len) -> pred_df(open..amount)
PredictFn = Callable[[pd.DataFrame, pd.Series, pd.Series, int], pd.DataFrame]


@dataclass
class BacktestConfig:
    lookback: int = 400          # context candles fed to the model (<= max_context)
    pred_len: int = 24           # candles the model forecasts each step
    step: int | None = None      # rebalance interval in bars; None -> pred_len
    cost: float = 0.0005         # per-side cost (fraction) charged on turnover
    rf_annual: float = 0.0       # annual risk-free rate for Sharpe
    bars_per_year: float | None = None  # None -> infer from timestamp spacing
    signal: SignalConfig = field(default_factory=SignalConfig)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def infer_bars_per_year(index: pd.DatetimeIndex) -> float:
    """Infer the annualisation factor from the median spacing between bars."""
    if len(index) < 3:
        return 252.0
    delta = pd.Series(index).diff().median()
    if pd.isna(delta) or delta.total_seconds() <= 0:
        return 252.0
    return float(pd.Timedelta(days=365) / delta)


def future_timestamps(index: pd.DatetimeIndex, last_pos: int, n: int) -> pd.Series:
    """Build ``n`` future timestamps after position ``last_pos`` in ``index``.

    Uses real timestamps where they exist in ``index`` and extrapolates the
    median bar spacing beyond the available history.
    """
    avail = index[last_pos + 1 : last_pos + 1 + n]
    if len(avail) >= n:
        return pd.Series(avail[:n])
    step = pd.Series(index).diff().median()
    if pd.isna(step) or step.total_seconds() <= 0:
        step = pd.Timedelta(days=1)
    extra = [index[-1] + step * (i + 1) for i in range(n - len(avail))]
    return pd.Series(list(avail) + extra)


# --------------------------------------------------------------------------- #
# Engine
# --------------------------------------------------------------------------- #
def run_walk_forward(
    df: pd.DataFrame,
    predict_fn: PredictFn,
    cfg: BacktestConfig,
    verbose: bool = True,
) -> dict:
    """Run the walk-forward backtest and return results + metrics.

    Args:
        df: Standardized OHLCV DataFrame with a DatetimeIndex (see
            :mod:`trading.data`).
        predict_fn: Callable producing a forecast DataFrame (must contain a
            ``close`` column) from a context window.
        cfg: :class:`BacktestConfig`.

    Returns:
        dict with keys ``frame`` (per-bar DataFrame: price/return/position/
        equity/benchmark), ``trades`` (DataFrame of round-trips) and ``metrics``.
    """
    if not isinstance(df.index, pd.DatetimeIndex):
        raise ValueError("df must have a DatetimeIndex (use trading.data loaders).")

    step = cfg.step or cfg.pred_len
    n = len(df)
    if n <= cfg.lookback + 1:
        raise ValueError(
            f"Not enough data: have {n} bars, need > lookback+1 = {cfg.lookback + 1}."
        )

    close = df["close"].to_numpy(dtype=float)
    index = df.index
    bar_ret = np.zeros(n)
    bar_ret[1:] = close[1:] / close[:-1] - 1.0

    target = np.full(n, np.nan)   # target position effective for each bar's return
    exp_ret = np.full(n, np.nan)  # forecast expected return logged at decision bar

    # Walk forward. Decision at close of bar t-1 sets the position for bars
    # [t, t+step-1]; that position multiplies the realised return of those bars.
    decision_points = range(cfg.lookback, n, step)
    for k, t in enumerate(decision_points):
        ctx = df.iloc[t - cfg.lookback : t]
        x_ts = pd.Series(ctx.index)
        y_ts = future_timestamps(index, t - 1, cfg.pred_len)

        pred_df = predict_fn(ctx, x_ts, y_ts, cfg.pred_len)
        last_close = float(close[t - 1])
        pred_close = pred_df["close"].to_numpy()
        er = expected_return(pred_close, last_close, cfg.signal)
        pos = position_from_forecast(pred_close, last_close, cfg.signal)

        end = min(t + step, n)
        target[t:end] = pos
        exp_ret[t - 1] = er
        if verbose:
            print(
                f"  [{k + 1}/{len(decision_points)}] {index[t - 1].date()} "
                f"exp_ret={er:+.4f} -> pos={pos:+d}",
                flush=True,
            )

    # Bars before the first decision are flat.
    target = pd.Series(target, index=index).fillna(0.0)

    # Strategy return for bar j = position(j) * realised return(j) - cost on turnover.
    turnover = target.diff().abs().fillna(target.abs())
    cost_series = turnover * cfg.cost
    strat_ret = target * pd.Series(bar_ret, index=index) - cost_series

    bpy = cfg.bars_per_year or infer_bars_per_year(index)

    equity = (1.0 + strat_ret).cumprod()
    benchmark = (1.0 + pd.Series(bar_ret, index=index)).cumprod()

    frame = pd.DataFrame(
        {
            "close": close,
            "bar_return": bar_ret,
            "expected_return": exp_ret,
            "position": target.values,
            "turnover": turnover.values,
            "strategy_return": strat_ret.values,
            "equity": equity.values,
            "benchmark": benchmark.values,
        },
        index=index,
    )

    trades = _extract_trades(frame)
    metrics = _compute_metrics(frame, trades, bpy, cfg.rf_annual)
    metrics["bars_per_year"] = round(bpy, 2)
    metrics["n_bars"] = int(n)
    metrics["n_decisions"] = len(decision_points)
    return {"frame": frame, "trades": trades, "metrics": metrics}


def _extract_trades(frame: pd.DataFrame) -> pd.DataFrame:
    """Reconstruct round-trip trades from the position series."""
    pos = frame["position"].to_numpy()
    idx = frame.index
    rows = []
    i = 0
    n = len(pos)
    while i < n:
        if pos[i] == 0:
            i += 1
            continue
        side = pos[i]
        j = i
        while j < n and pos[j] == side:
            j += 1
        seg = frame.iloc[i:j]
        # Net return of the held leg, including costs charged within the segment.
        net = float((1.0 + seg["strategy_return"]).prod() - 1.0)
        rows.append(
            {
                "entry_time": idx[i],
                "exit_time": idx[j - 1],
                "side": "long" if side > 0 else "short",
                "bars_held": j - i,
                "entry_price": float(seg["close"].iloc[0]),
                "exit_price": float(seg["close"].iloc[-1]),
                "return": net,
            }
        )
        i = j
    return pd.DataFrame(rows)


def _max_drawdown(equity: pd.Series) -> float:
    peak = equity.cummax()
    return float(((equity - peak) / peak).min())


def _compute_metrics(
    frame: pd.DataFrame, trades: pd.DataFrame, bpy: float, rf_annual: float
) -> dict:
    r = frame["strategy_return"]
    bench = frame["bar_return"]
    n = len(r)
    years = n / bpy if bpy > 0 else np.nan

    total_return = float(frame["equity"].iloc[-1] - 1.0)
    bench_total = float(frame["benchmark"].iloc[-1] - 1.0)
    cagr = float(frame["equity"].iloc[-1] ** (1.0 / years) - 1.0) if years and years > 0 else np.nan

    vol = float(r.std(ddof=0) * np.sqrt(bpy))
    rf_per_bar = rf_annual / bpy
    excess = r - rf_per_bar
    sharpe = float(excess.mean() / r.std(ddof=0) * np.sqrt(bpy)) if r.std(ddof=0) > 0 else 0.0
    downside = r[r < 0].std(ddof=0)
    sortino = float(excess.mean() / downside * np.sqrt(bpy)) if downside and downside > 0 else 0.0

    max_dd = _max_drawdown(frame["equity"])
    calmar = float(cagr / abs(max_dd)) if max_dd < 0 and not np.isnan(cagr) else np.nan

    bench_sharpe = float(bench.mean() / bench.std(ddof=0) * np.sqrt(bpy)) if bench.std(ddof=0) > 0 else 0.0
    bench_max_dd = _max_drawdown(frame["benchmark"])

    wins = trades["return"] > 0 if len(trades) else pd.Series([], dtype=bool)
    return {
        "total_return": round(total_return, 4),
        "cagr": round(cagr, 4) if not np.isnan(cagr) else None,
        "annual_volatility": round(vol, 4),
        "sharpe": round(sharpe, 3),
        "sortino": round(sortino, 3),
        "max_drawdown": round(max_dd, 4),
        "calmar": round(calmar, 3) if not (isinstance(calmar, float) and np.isnan(calmar)) else None,
        "exposure": round(float((frame["position"] != 0).mean()), 4),
        "n_trades": int(len(trades)),
        "win_rate": round(float(wins.mean()), 4) if len(trades) else None,
        "avg_trade_return": round(float(trades["return"].mean()), 4) if len(trades) else None,
        "total_turnover": round(float(frame["turnover"].sum()), 3),
        "benchmark_return": round(bench_total, 4),
        "benchmark_sharpe": round(bench_sharpe, 3),
        "benchmark_max_drawdown": round(bench_max_dd, 4),
    }


# --------------------------------------------------------------------------- #
# Reporting
# --------------------------------------------------------------------------- #
def plot_results(result: dict, title: str, out_path: str) -> None:
    """Save an equity-vs-benchmark + drawdown chart to ``out_path``."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    frame = result["frame"]
    equity, bench = frame["equity"], frame["benchmark"]
    drawdown = equity / equity.cummax() - 1.0
    m = result["metrics"]

    fig, (ax1, ax2) = plt.subplots(
        2, 1, figsize=(12, 8), sharex=True, gridspec_kw={"height_ratios": [3, 1]}
    )
    ax1.plot(equity.index, equity, label="Kronos strategy", color="#1f77b4", lw=1.6)
    ax1.plot(bench.index, bench, label="Buy & hold", color="#ff7f0e", lw=1.3, alpha=0.8)
    ax1.axhline(1.0, color="grey", ls="--", lw=0.8)
    ax1.set_ylabel("Growth of 1.0")
    ax1.set_title(title, fontsize=13, fontweight="bold")
    ax1.legend(loc="upper left")
    ax1.grid(True, alpha=0.3)

    txt = (
        f"Total return: {m['total_return']:.2%}\n"
        f"CAGR: {('%.2f%%' % (m['cagr'] * 100)) if m['cagr'] is not None else 'n/a'}\n"
        f"Sharpe: {m['sharpe']:.2f}\n"
        f"Max DD: {m['max_drawdown']:.2%}\n"
        f"Win rate: {('%.1f%%' % (m['win_rate'] * 100)) if m['win_rate'] is not None else 'n/a'}\n"
        f"Trades: {m['n_trades']}\n"
        f"B&H: {m['benchmark_return']:.2%}"
    )
    ax1.text(
        0.015, 0.97, txt, transform=ax1.transAxes, fontsize=9, va="top",
        bbox=dict(boxstyle="round,pad=0.4", facecolor="lightyellow", alpha=0.85),
    )

    ax2.fill_between(drawdown.index, drawdown, 0, color="red", alpha=0.3)
    ax2.set_ylabel("Drawdown")
    ax2.grid(True, alpha=0.3)
    plt.tight_layout()

    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def save_results(result: dict, out_dir: str, name: str) -> dict:
    """Persist metrics (JSON), trades (CSV) and the per-bar frame (CSV)."""
    os.makedirs(out_dir, exist_ok=True)
    paths = {
        "metrics": os.path.join(out_dir, f"{name}_metrics.json"),
        "trades": os.path.join(out_dir, f"{name}_trades.csv"),
        "frame": os.path.join(out_dir, f"{name}_equity.csv"),
        "chart": os.path.join(out_dir, f"{name}_backtest.png"),
    }
    with open(paths["metrics"], "w") as fh:
        json.dump(result["metrics"], fh, indent=2, default=str)
    result["trades"].to_csv(paths["trades"], index=False)
    result["frame"].to_csv(paths["frame"])
    plot_results(result, title=name, out_path=paths["chart"])
    return paths


def format_metrics(metrics: dict) -> str:
    """Human-readable one-per-line metrics block for the console."""
    label = {
        "total_return": "Total return", "cagr": "CAGR",
        "annual_volatility": "Annual volatility", "sharpe": "Sharpe",
        "sortino": "Sortino", "max_drawdown": "Max drawdown", "calmar": "Calmar",
        "exposure": "Exposure", "n_trades": "Trades", "win_rate": "Win rate",
        "avg_trade_return": "Avg trade return", "total_turnover": "Total turnover",
        "benchmark_return": "Buy & hold return", "benchmark_sharpe": "Buy & hold Sharpe",
        "benchmark_max_drawdown": "Buy & hold max DD", "bars_per_year": "Bars/year",
        "n_bars": "Bars", "n_decisions": "Decisions",
    }
    pct = {
        "total_return", "cagr", "annual_volatility", "max_drawdown", "exposure",
        "win_rate", "avg_trade_return", "benchmark_return", "benchmark_max_drawdown",
    }
    lines = []
    for k, v in metrics.items():
        name = label.get(k, k)
        if v is None:
            lines.append(f"  {name:<22}: n/a")
        elif k in pct and isinstance(v, (int, float)):
            lines.append(f"  {name:<22}: {v:.2%}")
        else:
            lines.append(f"  {name:<22}: {v}")
    return "\n".join(lines)
