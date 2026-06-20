"""Event-driven trade simulator for Kronos signals (realistic backtest).

Unlike :mod:`trading.backtest` (a quick return-compounding sketch), this engine
models individual trades the way a discretionary/retail system actually runs:

* **Entry**   at the *next* bar's open after a signal (no look-ahead), paying
  spread + slippage.
* **Stop-loss / take-profit** sized from **ATR** so the same settings work on
  BTC, Gold and FX; SL/TP are checked *intrabar* using each bar's high/low.
* **Position sizing** by fixed risk per trade ("1R", e.g. $25): the position is
  scaled so a stop-out loses ~1R; a take-profit at ``rr`` × stop yields ~+rr R.
* **Costs** modelled explicitly and reported separately: per-bar **spread**
  (from the data when available), **slippage** and **commission**.
* **Accounting** in account currency (USD), starting from ``initial_capital``.

One position at a time. The model is only queried every ``signal_every`` bars
(while flat) to keep inference tractable on long intraday series.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Callable

import numpy as np
import pandas as pd

from .signals import SignalConfig, expected_return, position_from_forecast
from .sizing import SizingConfig, size_position

PredictFn = Callable[[pd.DataFrame, pd.Series, pd.Series, int], pd.DataFrame]


@dataclass
class TradeConfig:
    # --- signal / forecast ---
    lookback: int = 256
    pred_len: int = 24
    signal: SignalConfig = field(default_factory=SignalConfig)
    signal_every: int | None = None   # bars between model queries (default pred_len)

    # --- stop-loss / take-profit (ATR units) ---
    atr_period: int = 14
    sl_atr: float = 1.5               # stop distance = sl_atr * ATR  == 1R
    rr: float = 2.0                   # take-profit distance = rr * stop distance
    max_hold: int | None = None       # bars before time-exit (default pred_len)

    # --- sizing / account ---
    sizing: SizingConfig = field(default_factory=SizingConfig)
    initial_capital: float = 5000.0

    # --- costs (points are converted to price via the data's point size) ---
    use_data_spread: bool = True      # use the per-bar `spread` column if present
    spread_points: float = 0.0        # fallback fixed spread (points) if no column
    slippage_points: float = 0.0      # adverse slippage per side (points)
    commission_per_notional: float = 0.0  # fraction of notional, charged each side
    commission_per_trade: float = 0.0     # flat fee per round-trip (account ccy)


def average_true_range(df: pd.DataFrame, period: int) -> np.ndarray:
    """Causal ATR (Wilder-style simple mean of True Range)."""
    high, low, close = df["high"].to_numpy(), df["low"].to_numpy(), df["close"].to_numpy()
    prev_close = np.concatenate([[close[0]], close[:-1]])
    tr = np.maximum.reduce([high - low, np.abs(high - prev_close), np.abs(low - prev_close)])
    return pd.Series(tr).rolling(period, min_periods=1).mean().to_numpy()


def run_trade_sim(
    df: pd.DataFrame, predict_fn: PredictFn, cfg: TradeConfig, verbose: bool = True
) -> dict:
    """Run the event-driven backtest. Returns ``{frame, trades, equity, metrics}``."""
    if not isinstance(df.index, pd.DatetimeIndex):
        raise ValueError("df must have a DatetimeIndex (use trading.data loaders).")

    n = len(df)
    if n <= cfg.lookback + 2:
        raise ValueError(f"Not enough data: {n} bars, need > {cfg.lookback + 2}.")

    point = float(df.attrs.get("point", 1.0))
    o = df["open"].to_numpy(float)
    h = df["high"].to_numpy(float)
    low = df["low"].to_numpy(float)
    c = df["close"].to_numpy(float)
    has_spread = "spread" in df.columns
    spread_col = df["spread"].to_numpy(float) if has_spread else None
    atr = average_true_range(df, cfg.atr_period)

    signal_every = cfg.signal_every or cfg.pred_len
    max_hold = cfg.max_hold or cfg.pred_len
    slip = cfg.slippage_points * point

    def bar_spread(i: int) -> float:
        if cfg.use_data_spread and has_spread:
            return float(spread_col[i])
        return cfg.spread_points * point

    equity = cfg.initial_capital
    trades = []
    bars_in_market = 0
    next_free = cfg.lookback  # earliest bar index we may open a new trade

    decision_points = list(range(cfg.lookback, n - 1, signal_every))
    for k, t in enumerate(decision_points):
        if t < next_free:
            continue  # still inside a previously simulated trade

        ctx = df.iloc[t - cfg.lookback : t]
        x_ts = pd.Series(ctx.index)
        from .backtest import future_timestamps
        y_ts = future_timestamps(df.index, t - 1, cfg.pred_len)
        pred_df = predict_fn(ctx, x_ts, y_ts, cfg.pred_len)

        last_close = float(c[t - 1])
        pred_close = pred_df["close"].to_numpy()
        direction = position_from_forecast(pred_close, last_close, cfg.signal)
        if direction == 0:
            continue

        atr_entry = float(atr[t - 1])
        stop_dist = cfg.sl_atr * atr_entry
        if stop_dist <= 0:
            continue

        # --- entry at next bar open, paying half-spread + slippage adversely ---
        entry_spread = bar_spread(t)
        entry_raw = float(o[t])
        entry_price = entry_raw + direction * (entry_spread / 2 + slip)
        units, risk_dollars = size_position(equity, entry_price, stop_dist, cfg.sizing)
        if units <= 0:
            continue

        sl = entry_price - direction * stop_dist
        tp = entry_price + direction * cfg.rr * stop_dist

        # --- walk forward bar by bar; check SL before TP (conservative) ---
        exit_bar, exit_raw, reason = None, None, None
        end = min(t + max_hold, n)
        for j in range(t, end):
            if direction > 0:
                if low[j] <= sl:
                    exit_bar, exit_raw, reason = j, sl, "stop"
                    break
                if h[j] >= tp:
                    exit_bar, exit_raw, reason = j, tp, "target"
                    break
            else:
                if h[j] >= sl:
                    exit_bar, exit_raw, reason = j, sl, "stop"
                    break
                if low[j] <= tp:
                    exit_bar, exit_raw, reason = j, tp, "target"
                    break
        if exit_bar is None:
            exit_bar, exit_raw, reason = end - 1, float(c[end - 1]), "timeout"

        exit_spread = bar_spread(exit_bar)
        exit_price = exit_raw - direction * (exit_spread / 2 + slip)

        # --- P&L and explicit cost breakdown ---
        gross = units * (exit_raw - entry_raw) * direction
        spread_cost = units * (entry_spread / 2 + exit_spread / 2)
        slippage_cost = units * 2 * slip
        commission = (
            cfg.commission_per_notional * (units * entry_price + units * exit_price)
            + cfg.commission_per_trade
        )
        net = gross - spread_cost - slippage_cost - commission
        equity += net
        bars_in_market += exit_bar - t + 1

        trades.append(
            {
                "entry_time": df.index[t],
                "exit_time": df.index[exit_bar],
                "side": "long" if direction > 0 else "short",
                "bars_held": exit_bar - t + 1,
                "units": units,
                "notional": units * entry_price,
                "entry": entry_price,
                "stop": sl,
                "target": tp,
                "exit": exit_price,
                "reason": reason,
                "risk": risk_dollars,
                "gross_pnl": gross,
                "spread_cost": spread_cost,
                "slippage_cost": slippage_cost,
                "commission": commission,
                "net_pnl": net,
                "R_multiple": net / risk_dollars if risk_dollars > 0 else 0.0,
                "equity": equity,
            }
        )
        if verbose:
            print(
                f"  [{k + 1}/{len(decision_points)}] {df.index[t]} {trades[-1]['side']:5s} "
                f"{reason:7s} R={trades[-1]['R_multiple']:+.2f} net=${net:+.2f} eq=${equity:,.2f}",
                flush=True,
            )
        next_free = exit_bar + 1

    trades_df = pd.DataFrame(trades)
    test_bars = n - cfg.lookback
    metrics = _trade_metrics(trades_df, cfg.initial_capital, equity, df, cfg.lookback,
                             bars_in_market, test_bars)
    equity_curve = _equity_curve(trades_df, df, cfg)
    return {"trades": trades_df, "equity": equity_curve, "metrics": metrics, "frame": df}


def _equity_curve(trades_df: pd.DataFrame, df: pd.DataFrame, cfg: TradeConfig) -> pd.DataFrame:
    """Step equity at each trade close, plus a 1x buy & hold benchmark in $."""
    start_time = df.index[cfg.lookback]
    times = [start_time]
    eq = [cfg.initial_capital]
    if len(trades_df):
        times += list(trades_df["exit_time"])
        eq += list(trades_df["equity"])
    curve = pd.DataFrame({"equity": eq}, index=pd.DatetimeIndex(times, name="timestamps"))
    curve = curve[~curve.index.duplicated(keep="last")].sort_index()

    region = df.loc[start_time:]
    bh = cfg.initial_capital * region["close"] / float(region["close"].iloc[0])
    curve["benchmark"] = bh.reindex(curve.index, method="ffill")
    return curve


def _max_drawdown(equity: pd.Series) -> float:
    peak = equity.cummax()
    return float(((equity - peak) / peak).min()) if len(equity) else 0.0


def _trade_metrics(td, capital, equity, df, lookback, bars_in_market, test_bars) -> dict:
    start_time, end_time = df.index[lookback], df.index[-1]
    years = max((end_time - start_time).total_seconds() / (365.25 * 86400), 1e-9)
    net_profit = equity - capital
    total_return = net_profit / capital
    bh_return = float(df["close"].iloc[-1] / df["close"].iloc[lookback] - 1.0)

    base = {
        "initial_capital": round(capital, 2),
        "final_equity": round(equity, 2),
        "net_profit": round(net_profit, 2),
        "total_return": round(total_return, 4),
        "n_trades": int(len(td)),
        "buy_hold_return": round(bh_return, 4),
        "exposure": round(bars_in_market / test_bars, 4) if test_bars else 0.0,
    }
    if not len(td):
        return {**base, "win_rate": None, "profit_factor": None, "expectancy": None,
                "avg_R": None, "max_drawdown": 0.0, "cagr": None,
                "total_costs": 0.0, "spread_cost": 0.0, "slippage_cost": 0.0,
                "commission": 0.0}

    wins = td[td["net_pnl"] > 0]["net_pnl"]
    losses = td[td["net_pnl"] <= 0]["net_pnl"]
    gross_profit = float(wins.sum())
    gross_loss = float(-losses.sum())

    # Trade-based Sharpe: per-trade return on equity-before-trade, annualised by frequency.
    eq_before = td["equity"] - td["net_pnl"]
    leverage = (td["notional"] / eq_before).replace([np.inf, -np.inf], np.nan)
    tr_ret = (td["net_pnl"] / eq_before).replace([np.inf, -np.inf], np.nan).dropna()
    trades_per_year = len(td) / years
    sharpe = (
        float(tr_ret.mean() / tr_ret.std(ddof=0) * np.sqrt(trades_per_year))
        if tr_ret.std(ddof=0) > 0 else 0.0
    )

    spread_cost = float(td["spread_cost"].sum())
    slippage_cost = float(td["slippage_cost"].sum())
    commission = float(td["commission"].sum())
    return {
        **base,
        "win_rate": round(float((td["net_pnl"] > 0).mean()), 4),
        "profit_factor": round(gross_profit / gross_loss, 3) if gross_loss > 0 else None,
        "expectancy": round(float(td["net_pnl"].mean()), 2),
        "avg_R": round(float(td["R_multiple"].mean()), 3),
        "best_trade": round(float(td["net_pnl"].max()), 2),
        "worst_trade": round(float(td["net_pnl"].min()), 2),
        "avg_notional": round(float(td["notional"].mean()), 2),
        "avg_leverage": round(float(leverage.mean()), 2),
        "sharpe": round(sharpe, 3),
        "max_drawdown": round(_max_drawdown(td["equity"]), 4),
        "cagr": round(float((equity / capital) ** (1 / years) - 1), 4) if equity > 0 else None,
        "longs": int((td["side"] == "long").sum()),
        "shorts": int((td["side"] == "short").sum()),
        "stops": int((td["reason"] == "stop").sum()),
        "targets": int((td["reason"] == "target").sum()),
        "timeouts": int((td["reason"] == "timeout").sum()),
        "spread_cost": round(spread_cost, 2),
        "slippage_cost": round(slippage_cost, 2),
        "commission": round(commission, 2),
        "total_costs": round(spread_cost + slippage_cost + commission, 2),
    }


# --------------------------------------------------------------------------- #
# Reporting
# --------------------------------------------------------------------------- #
def plot_trade_results(result: dict, title: str, out_path: str) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    curve = result["equity"]
    drawdown = curve["equity"] / curve["equity"].cummax() - 1.0
    m = result["metrics"]

    fig, (ax1, ax2) = plt.subplots(
        2, 1, figsize=(12, 8), sharex=True, gridspec_kw={"height_ratios": [3, 1]}
    )
    ax1.plot(curve.index, curve["equity"], label="Kronos strategy", color="#1f77b4", lw=1.6)
    ax1.plot(curve.index, curve["benchmark"], label="Buy & hold (1x)",
             color="#ff7f0e", lw=1.2, alpha=0.8)
    ax1.axhline(m["initial_capital"], color="grey", ls="--", lw=0.8)
    ax1.set_ylabel("Equity ($)")
    ax1.set_title(title, fontsize=13, fontweight="bold")
    ax1.legend(loc="upper left")
    ax1.grid(True, alpha=0.3)

    wr = f"{m['win_rate']:.1%}" if m["win_rate"] is not None else "n/a"
    pf = f"{m['profit_factor']:.2f}" if m["profit_factor"] is not None else "n/a"
    txt = (
        f"Net profit: ${m['net_profit']:,.0f} ({m['total_return']:.1%})\n"
        f"Trades: {m['n_trades']}  Win: {wr}  PF: {pf}\n"
        f"Avg R: {m.get('avg_R', 'n/a')}  Sharpe: {m.get('sharpe', 'n/a')}\n"
        f"Max DD: {m['max_drawdown']:.1%}\n"
        f"Costs paid: ${m['total_costs']:,.0f}\n"
        f"Buy&hold: {m['buy_hold_return']:.1%}"
    )
    ax1.text(0.015, 0.97, txt, transform=ax1.transAxes, fontsize=9, va="top",
             bbox=dict(boxstyle="round,pad=0.4", facecolor="lightyellow", alpha=0.85))

    ax2.fill_between(drawdown.index, drawdown, 0, color="red", alpha=0.3)
    ax2.set_ylabel("Drawdown")
    ax2.grid(True, alpha=0.3)
    plt.tight_layout()
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def save_trade_results(result: dict, out_dir: str, name: str) -> dict:
    os.makedirs(out_dir, exist_ok=True)
    paths = {
        "metrics": os.path.join(out_dir, f"{name}_metrics.json"),
        "trades": os.path.join(out_dir, f"{name}_trades.csv"),
        "equity": os.path.join(out_dir, f"{name}_equity.csv"),
        "chart": os.path.join(out_dir, f"{name}_backtest.png"),
    }
    with open(paths["metrics"], "w") as fh:
        json.dump(result["metrics"], fh, indent=2, default=str)
    result["trades"].to_csv(paths["trades"], index=False)
    result["equity"].to_csv(paths["equity"])
    plot_trade_results(result, title=name, out_path=paths["chart"])
    return paths


def format_trade_metrics(m: dict) -> str:
    order = [
        ("initial_capital", "Initial capital", "$"),
        ("final_equity", "Final equity", "$"),
        ("net_profit", "Net profit", "$"),
        ("total_return", "Total return", "%"),
        ("cagr", "CAGR", "%"),
        ("max_drawdown", "Max drawdown", "%"),
        ("sharpe", "Sharpe (trade)", ""),
        ("n_trades", "Trades", ""),
        ("win_rate", "Win rate", "%"),
        ("profit_factor", "Profit factor", ""),
        ("expectancy", "Expectancy / trade", "$"),
        ("avg_R", "Avg R multiple", "R"),
        ("best_trade", "Best trade", "$"),
        ("worst_trade", "Worst trade", "$"),
        ("avg_notional", "Avg position size", "$"),
        ("avg_leverage", "Avg leverage", "x"),
        ("longs", "Longs", ""),
        ("shorts", "Shorts", ""),
        ("targets", "Hit target", ""),
        ("stops", "Hit stop", ""),
        ("timeouts", "Timed out", ""),
        ("exposure", "Exposure", "%"),
        ("spread_cost", "  ├ spread", "$"),
        ("slippage_cost", "  ├ slippage", "$"),
        ("commission", "  ├ commission", "$"),
        ("total_costs", "Total costs paid", "$"),
        ("buy_hold_return", "Buy & hold return", "%"),
    ]
    lines = []
    for key, label, unit in order:
        if key not in m:
            continue
        v = m[key]
        if v is None:
            lines.append(f"  {label:<22}: n/a")
        elif unit == "%":
            lines.append(f"  {label:<22}: {v:.2%}")
        elif unit == "$":
            lines.append(f"  {label:<22}: ${v:,.2f}")
        elif unit == "R":
            lines.append(f"  {label:<22}: {v:+.2f}R")
        elif unit == "x":
            lines.append(f"  {label:<22}: {v:.2f}x")
        else:
            lines.append(f"  {label:<22}: {v}")
    return "\n".join(lines)
