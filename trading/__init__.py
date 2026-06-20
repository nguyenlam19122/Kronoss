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
from .data import load_csv, load_data, load_yfinance, resolve_symbol
from .signals import SignalConfig, expected_return, position_from_forecast

__all__ = [
    "BacktestConfig",
    "SignalConfig",
    "run_walk_forward",
    "save_results",
    "plot_results",
    "format_metrics",
    "expected_return",
    "position_from_forecast",
    "load_data",
    "load_csv",
    "load_yfinance",
    "resolve_symbol",
]
