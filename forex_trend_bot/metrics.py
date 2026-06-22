"""Các chỉ số hiệu năng tính từ đường vốn (equity) và danh sách lệnh."""
import numpy as np
import pandas as pd


def _bars_per_year(index: pd.DatetimeIndex) -> float:
    """Ước lượng số nến/năm từ khoảng thời gian thực (đã trừ cuối tuần/nghỉ lễ)."""
    if len(index) < 2:
        return 252.0
    span_days = (index[-1] - index[0]).total_seconds() / 86400.0
    if span_days <= 0:
        return 252.0
    years = span_days / 365.25
    return len(index) / years


def max_drawdown(equity: pd.Series) -> float:
    peak = equity.cummax()
    dd = (equity - peak) / peak
    return float(dd.min())


def compute(trades: pd.DataFrame, equity: pd.Series, initial_equity: float) -> dict:
    final_equity = float(equity.iloc[-1])
    total_return = final_equity / initial_equity - 1.0

    rets = equity.pct_change().dropna()
    bpy = _bars_per_year(equity.index)
    if rets.std() > 0:
        sharpe = float(rets.mean() / rets.std() * np.sqrt(bpy))
    else:
        sharpe = 0.0

    span_years = max((equity.index[-1] - equity.index[0]).days / 365.25, 1e-9)
    cagr = (final_equity / initial_equity) ** (1.0 / span_years) - 1.0 if final_equity > 0 else -1.0

    n_trades = int(len(trades))
    out = {
        "n_trades": n_trades,
        "total_return": total_return,
        "cagr": cagr,
        "sharpe": sharpe,
        "max_drawdown": max_drawdown(equity),
        "final_equity": final_equity,
    }

    if n_trades > 0:
        pnl = trades["pnl"]
        wins = pnl[pnl > 0]
        losses = pnl[pnl < 0]
        gross_win = float(wins.sum())
        gross_loss = float(-losses.sum())
        out.update({
            "win_rate": float((pnl > 0).mean()),
            "profit_factor": (gross_win / gross_loss) if gross_loss > 0 else float("inf"),
            "avg_R": float(trades["R"].mean()),       # kỳ vọng theo bội số rủi ro
            "expectancy": float(pnl.mean()),
            "avg_win": float(wins.mean()) if len(wins) else 0.0,
            "avg_loss": float(losses.mean()) if len(losses) else 0.0,
            "payoff_ratio": (float(wins.mean()) / abs(float(losses.mean())))
                            if len(wins) and len(losses) else float("inf"),
            "avg_bars_held": float(trades["bars_held"].mean()),
            "max_R": float(trades["R"].max()),
            "min_R": float(trades["R"].min()),
        })
    else:
        out.update({
            "win_rate": 0.0, "profit_factor": 0.0, "avg_R": 0.0, "expectancy": 0.0,
            "avg_win": 0.0, "avg_loss": 0.0, "payoff_ratio": 0.0, "avg_bars_held": 0.0,
            "max_R": 0.0, "min_R": 0.0,
        })
    return out


_PCT_KEYS = {"total_return", "cagr", "max_drawdown", "win_rate"}


def format_report(m: dict, title: str = "") -> str:
    lines = []
    if title:
        lines.append(title)
        lines.append("=" * len(title))
    label = {
        "n_trades": "Số lệnh", "total_return": "Tổng lợi nhuận", "cagr": "CAGR (năm)",
        "sharpe": "Sharpe", "max_drawdown": "Max Drawdown", "final_equity": "Vốn cuối",
        "win_rate": "Tỷ lệ thắng", "profit_factor": "Profit Factor", "avg_R": "Kỳ vọng (R)",
        "expectancy": "Kỳ vọng ($/lệnh)", "avg_win": "Lãi TB", "avg_loss": "Lỗ TB",
        "payoff_ratio": "Payoff (lãi/lỗ)", "avg_bars_held": "Số nến giữ TB",
        "max_R": "R lớn nhất", "min_R": "R nhỏ nhất",
    }
    for k in ["n_trades", "total_return", "cagr", "sharpe", "max_drawdown", "win_rate",
              "profit_factor", "avg_R", "expectancy", "payoff_ratio", "avg_bars_held",
              "max_R", "min_R", "final_equity"]:
        if k not in m:
            continue
        v = m[k]
        if k in _PCT_KEYS:
            lines.append(f"  {label[k]:<20}: {v:>10.2%}")
        elif k == "n_trades":
            lines.append(f"  {label[k]:<20}: {v:>10d}")
        elif k in ("final_equity", "expectancy", "avg_win", "avg_loss"):
            lines.append(f"  {label[k]:<20}: {v:>10,.2f}")
        else:
            lines.append(f"  {label[k]:<20}: {v:>10.2f}")
    return "\n".join(lines)
