"""Turn a Kronos forecast into a discrete trading position.

Kronos predicts ``pred_len`` future candles. These helpers reduce a forecast to
a single expected return and then to a target position in ``{-1, 0, +1}``
(short / flat / long).

Signal modes (how the expected return is read from the forecast):

* ``"endpoint"`` -- return implied by the close at the ``horizon``-th predicted
  bar versus the last observed close.
* ``"mean"``     -- average of the predicted closes over the horizon versus the
  last observed close (more robust to single-bar noise). **Default.**
* ``"slope"``    -- ordinary-least-squares slope of the predicted closes,
  normalised by the last close (captures the predicted drift/trend).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class SignalConfig:
    mode: str = "mean"            # "endpoint" | "mean" | "slope"
    horizon: int | None = None    # bars of the forecast to use; None -> all
    long_threshold: float = 0.0   # go long when expected return >  long_threshold
    short_threshold: float = 0.0  # go short when expected return < -short_threshold
    allow_short: bool = True      # if False, a short signal becomes flat (0)


def expected_return(pred_close: np.ndarray, last_close: float, cfg: SignalConfig) -> float:
    """Compute the expected return of a forecast relative to ``last_close``."""
    pred_close = np.asarray(pred_close, dtype=float)
    h = len(pred_close) if cfg.horizon is None else min(cfg.horizon, len(pred_close))
    if h <= 0 or last_close <= 0:
        return 0.0
    window = pred_close[:h]

    if cfg.mode == "endpoint":
        return float(window[-1] / last_close - 1.0)
    if cfg.mode == "mean":
        return float(window.mean() / last_close - 1.0)
    if cfg.mode == "slope":
        # Slope per bar of the predicted path, scaled to a per-last-close return.
        x = np.arange(h, dtype=float)
        slope = np.polyfit(x, window, 1)[0] if h >= 2 else 0.0
        return float(slope / last_close)
    raise ValueError(f"Unknown signal mode: {cfg.mode!r}")


def position_from_forecast(
    pred_close: np.ndarray, last_close: float, cfg: SignalConfig
) -> int:
    """Map a forecast to a target position in ``{-1, 0, +1}``."""
    er = expected_return(pred_close, last_close, cfg)
    if er > cfg.long_threshold:
        return 1
    if er < -cfg.short_threshold:
        return -1 if cfg.allow_short else 0
    return 0
