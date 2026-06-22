"""Measure whether a forecaster has predictive *edge* — independent of trading.

Before optimising stops, sizing or costs, the first question is: does the model
predict direction better than a coin flip? This module walks the data exactly
like the backtest (same lookback / pred_len / cadence, no look-ahead) but instead
of trading it compares each forecast against what actually happened and reports:

* **Directional accuracy** — % of forecasts whose sign matches the realised move
  (50% = no edge). With an approximate two-sided p-value vs 50%.
* **Information Coefficient (IC)** — Pearson corr between predicted and realised
  returns; **Rank IC** — Spearman (rank) version, more robust to outliers.
* **Accuracy by confidence** — accuracy within terciles of |predicted move|
  (does a bigger predicted move mean a more reliable one? — justifies filtering).
* **Edge decay by horizon** — accuracy 1 / half / full `pred_len` bars ahead.

Works with any ``predict_fn`` (real Kronos, ensemble, or a baseline/oracle stub).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .backtest import future_timestamps
from .signals import SignalConfig, expected_return


@dataclass
class EdgeConfig:
    lookback: int = 256
    pred_len: int = 24
    signal_every: int | None = None          # default pred_len
    signal: SignalConfig = field(default_factory=SignalConfig)
    horizons: list[int] | None = None         # extra endpoint horizons to profile


def _safe_corr(a: np.ndarray, b: np.ndarray) -> float:
    if len(a) < 3 or np.std(a) == 0 or np.std(b) == 0:
        return float("nan")
    return float(np.corrcoef(a, b)[0, 1])


def _accuracy_pvalue(accuracy: float, n: int) -> float:
    """Two-sided p-value for accuracy != 0.5 (normal approximation)."""
    if n <= 0:
        return float("nan")
    z = (accuracy - 0.5) / np.sqrt(0.25 / n)
    # two-sided tail of the standard normal via erfc
    from math import erfc, sqrt
    return float(erfc(abs(z) / sqrt(2)))


def measure_edge(df: pd.DataFrame, predict_fn, cfg: EdgeConfig, verbose: bool = True) -> dict:
    """Run forecasts over ``df`` and quantify predictive edge (no trading)."""
    if not isinstance(df.index, pd.DatetimeIndex):
        raise ValueError("df must have a DatetimeIndex (use trading.data loaders).")

    n = len(df)
    close = df["close"].to_numpy(float)
    step = cfg.signal_every or cfg.pred_len
    sig_h = cfg.signal.horizon or cfg.pred_len
    extra = cfg.horizons or sorted({1, max(1, cfg.pred_len // 2), cfg.pred_len})

    pred_rets, act_rets = [], []
    per_h = {h: {"pred": [], "act": []} for h in extra}

    points = range(cfg.lookback, n - 1, step)
    for t in points:
        # Need the realised price `sig_h` bars after the decision bar (t-1).
        if (t - 1) + sig_h > n - 1:
            break
        ctx = df.iloc[t - cfg.lookback : t]
        y_ts = future_timestamps(df.index, t - 1, cfg.pred_len)
        pred_df = predict_fn(ctx, pd.Series(ctx.index), y_ts, cfg.pred_len)
        pred_close = pred_df["close"].to_numpy(float)
        last = float(close[t - 1])
        if last <= 0:
            continue

        pred_rets.append(expected_return(pred_close, last, cfg.signal))
        act_rets.append(close[(t - 1) + sig_h] / last - 1.0)

        for h in extra:
            if h <= len(pred_close) and (t - 1) + h <= n - 1:
                per_h[h]["pred"].append(pred_close[h - 1] / last - 1.0)
                per_h[h]["act"].append(close[(t - 1) + h] / last - 1.0)

    pred = np.asarray(pred_rets)
    act = np.asarray(act_rets)
    nz = pred != 0
    n_eff = int(nz.sum())
    if n_eff == 0:
        return {"n_samples": 0, "note": "No non-zero forecasts."}

    correct = np.sign(pred[nz]) == np.sign(act[nz])
    accuracy = float(correct.mean())

    # accuracy within terciles of forecast magnitude (confidence)
    conf_acc = {}
    if n_eff >= 6:
        mag = np.abs(pred[nz])
        order = np.argsort(mag)
        thirds = np.array_split(order, 3)
        for label, idx in zip(("low", "mid", "high"), thirds):
            conf_acc[label] = round(float(correct[idx].mean()), 4) if len(idx) else None

    horizon_acc = {}
    for h in extra:
        p, a = np.asarray(per_h[h]["pred"]), np.asarray(per_h[h]["act"])
        m = p != 0
        horizon_acc[h] = round(float((np.sign(p[m]) == np.sign(a[m])).mean()), 4) if m.sum() else None

    result = {
        "n_samples": n_eff,
        "pred_horizon_bars": sig_h,
        "directional_accuracy": round(accuracy, 4),
        "accuracy_pvalue": round(_accuracy_pvalue(accuracy, n_eff), 5),
        "pearson_ic": round(_safe_corr(pred[nz], act[nz]), 4),
        "rank_ic": round(_safe_corr(pd.Series(pred[nz]).rank().to_numpy(),
                                    pd.Series(act[nz]).rank().to_numpy()), 4),
        "mean_actual_when_up": round(float(act[nz][pred[nz] > 0].mean()), 6) if (pred[nz] > 0).any() else None,
        "mean_actual_when_down": round(float(act[nz][pred[nz] < 0].mean()), 6) if (pred[nz] < 0).any() else None,
        "accuracy_by_confidence": conf_acc,
        "accuracy_by_horizon": horizon_acc,
    }
    if verbose:
        print(format_edge(result))
    return result


def format_edge(r: dict) -> str:
    if r.get("n_samples", 0) == 0:
        return "  (no forecasts) " + r.get("note", "")
    acc = r["directional_accuracy"]
    verdict = ("EDGE rõ" if acc >= 0.55 else "edge nhẹ" if acc >= 0.52 else
               "≈ ngẫu nhiên" if acc >= 0.48 else "NGƯỢC (đảo tín hiệu?)")
    lines = [
        f"  Samples              : {r['n_samples']}  (horizon {r['pred_horizon_bars']} bars)",
        f"  Directional accuracy : {acc:.2%}   p={r['accuracy_pvalue']:.4f}  → {verdict}",
        f"  Information Coef (IC) : {r['pearson_ic']}   Rank IC: {r['rank_ic']}",
        f"  Mean move | pred up  : {r['mean_actual_when_up']}",
        f"  Mean move | pred down: {r['mean_actual_when_down']}",
    ]
    if r["accuracy_by_confidence"]:
        c = r["accuracy_by_confidence"]
        lines.append(f"  Accuracy by |pred|   : low={c.get('low')}  mid={c.get('mid')}  high={c.get('high')}")
    if r["accuracy_by_horizon"]:
        hs = "  ".join(f"{h}b={v:.0%}" if v is not None else f"{h}b=n/a"
                       for h, v in r["accuracy_by_horizon"].items())
        lines.append(f"  Accuracy by horizon  : {hs}")
    return "\n".join(lines)
