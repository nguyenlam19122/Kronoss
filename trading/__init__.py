"""Kronos trading toolkit: data -> forecast -> signal -> walk-forward backtest.

Works across Forex, Gold, BTC/crypto and US stocks via a unified data loader.
The backtest engine is model-agnostic (inject any ``predict_fn``), so it runs
with the real Kronos model or with the lightweight baselines for testing.
"""

from .backtest import (
    BacktestConfig,
    format_metrics,
    plot_results,
    run_walk_forward,
    save_results,
)
from .data import load_csv, load_data, load_mt5_csv, load_yfinance, resolve_symbol
from .signals import SignalConfig, expected_return, position_from_forecast
from .sizing import SizingConfig, size_position
from .trade_sim import (
    TradeConfig,
    format_trade_metrics,
    run_trade_sim,
    save_trade_results,
)

__all__ = [
    # return-compounding sketch
    "BacktestConfig",
    "run_walk_forward",
    "save_results",
    "plot_results",
    "format_metrics",
    # event-driven trade simulator (SL/TP, R-sizing, costs)
    "TradeConfig",
    "SizingConfig",
    "size_position",
    "run_trade_sim",
    "save_trade_results",
    "format_trade_metrics",
    # signals
    "SignalConfig",
    "expected_return",
    "position_from_forecast",
    # data
    "load_data",
    "load_csv",
    "load_mt5_csv",
    "load_yfinance",
    "resolve_symbol",
]
