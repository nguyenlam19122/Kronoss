"""Position sizing — translate a fixed *risk per trade* into a position size.

The account risks a fixed amount per trade ("1R"). Given the stop-loss distance
(in price units), the number of units is chosen so that hitting the stop loses
exactly 1R (before costs):

    units = risk_amount / stop_distance

``1R`` can be a fixed dollar amount (``mode="fixed"``, e.g. $25) or a percentage
of the *current* equity (``mode="percent"``, e.g. 0.5%). A take-profit placed at
``rr`` times the stop distance therefore yields ``+rr`` R when hit.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SizingConfig:
    mode: str = "fixed"        # "fixed" (dollar R) | "percent" (R = pct of equity)
    risk_amount: float = 25.0  # 1R in account currency when mode == "fixed"
    risk_pct: float = 0.005    # 1R as a fraction of equity when mode == "percent"
    max_leverage: float | None = None  # cap notional / equity (None = uncapped)


def risk_per_trade(equity: float, cfg: SizingConfig) -> float:
    """Dollar value of 1R for the current equity."""
    if cfg.mode == "percent":
        return max(0.0, equity * cfg.risk_pct)
    return max(0.0, cfg.risk_amount)


def size_position(
    equity: float, entry_price: float, stop_distance: float, cfg: SizingConfig
) -> tuple[float, float]:
    """Return ``(units, risk_dollars)`` for a trade.

    ``stop_distance`` is the absolute price gap between entry and stop-loss.
    The position is capped by ``max_leverage`` if set; when the cap binds, the
    realised risk falls below the nominal 1R (reported back as ``risk_dollars``).
    """
    if stop_distance <= 0 or entry_price <= 0 or equity <= 0:
        return 0.0, 0.0

    risk_dollars = risk_per_trade(equity, cfg)
    units = risk_dollars / stop_distance

    if cfg.max_leverage is not None:
        max_units = cfg.max_leverage * equity / entry_price
        if units > max_units:
            units = max_units
            risk_dollars = units * stop_distance  # actual risk after the cap
    return units, risk_dollars
