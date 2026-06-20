"""Data loading utilities for the Kronos trading pipeline.

A single, unified loader produces a standardized OHLCV DataFrame for any of the
target asset classes (Forex, Gold, BTC/crypto, US stocks). Two sources are
supported:

* ``load_yfinance`` -- pulls candles from Yahoo Finance (needs network access;
  the hosts ``query1.finance.yahoo.com`` / ``query2.finance.yahoo.com`` must be
  reachable / allow-listed).
* ``load_csv`` -- reads a local CSV (no network), accepting the same column
  layout used elsewhere in this repo.

The standardized schema returned by every loader is a ``pandas.DataFrame`` with:

    index   : pandas.DatetimeIndex (named ``timestamps``)
    columns : open, high, low, close, volume, amount

``amount`` (turnover) is approximated as ``volume * close`` when the source does
not provide it; Kronos only needs OHLC + volume for forecasting.
"""

from __future__ import annotations

import pandas as pd

STD_COLS = ["open", "high", "low", "close", "volume", "amount"]

# Friendly aliases -> Yahoo Finance tickers, covering the four requested asset
# classes. Anything not listed is passed through unchanged (e.g. "AAPL", "SPY").
SYMBOL_ALIASES = {
    # Crypto
    "btc": "BTC-USD", "btcusd": "BTC-USD", "bitcoin": "BTC-USD",
    "eth": "ETH-USD", "ethusd": "ETH-USD", "ethereum": "ETH-USD",
    # Gold / metals
    "gold": "GC=F", "xau": "XAUUSD=X", "xauusd": "XAUUSD=X",
    "silver": "SI=F", "xag": "XAGUSD=X",
    # Forex majors
    "eurusd": "EURUSD=X", "gbpusd": "GBPUSD=X", "usdjpy": "JPY=X",
    "audusd": "AUDUSD=X", "usdchf": "CHF=X", "usdcad": "CAD=X",
    "nzdusd": "NZDUSD=X",
}


def resolve_symbol(symbol: str) -> str:
    """Map a friendly alias (e.g. ``"gold"``) to a Yahoo Finance ticker.

    Unknown symbols are returned unchanged so any valid ticker still works.
    """
    return SYMBOL_ALIASES.get(symbol.strip().lower(), symbol)


def _standardize(df: pd.DataFrame) -> pd.DataFrame:
    """Coerce an arbitrary OHLCV frame into the standardized schema."""
    df = df.copy()

    # Normalise column names: lower-case, strip, map common synonyms.
    rename = {
        "时间": "timestamps", "日期": "timestamps", "date": "timestamps",
        "datetime": "timestamps", "time": "timestamps", "timestamp": "timestamps",
        "开盘价": "open", "最高价": "high", "最低价": "low", "收盘价": "close",
        "成交量": "volume", "成交额": "amount", "vol": "volume", "turnover": "amount",
        "adj close": "close", "adj_close": "close",
    }
    df.columns = [str(c).strip() for c in df.columns]
    df = df.rename(columns={c: rename.get(c.lower(), c.lower()) for c in df.columns})

    # Build / set the DatetimeIndex.
    if "timestamps" in df.columns:
        df["timestamps"] = pd.to_datetime(df["timestamps"])
        df = df.set_index("timestamps")
    elif not isinstance(df.index, pd.DatetimeIndex):
        df.index = pd.to_datetime(df.index)
    df.index.name = "timestamps"

    missing = [c for c in ["open", "high", "low", "close"] if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required price column(s): {missing}")

    if "volume" not in df.columns:
        df["volume"] = 0.0
    if "amount" not in df.columns:
        df["amount"] = df["volume"] * df["close"]

    df = df[STD_COLS].astype(float)
    df = df[~df.index.duplicated(keep="last")].sort_index()
    df = df.dropna(subset=["open", "high", "low", "close"])
    return df


def load_csv(path: str) -> pd.DataFrame:
    """Load a local CSV into the standardized OHLCV schema."""
    df = pd.read_csv(path, encoding="utf-8-sig")
    return _standardize(df)


def load_yfinance(
    symbol: str,
    start: str | None = None,
    end: str | None = None,
    period: str | None = None,
    interval: str = "1d",
) -> pd.DataFrame:
    """Download candles from Yahoo Finance for ``symbol``.

    Args:
        symbol: Ticker or friendly alias (``"btc"``, ``"gold"``, ``"eurusd"``,
            ``"AAPL"``, ...). Resolved via :func:`resolve_symbol`.
        start, end: ISO date strings (``"2023-01-01"``). Ignored if ``period``
            is given.
        period: Relative range understood by yfinance (``"2y"``, ``"60d"`` ...).
        interval: Candle size (``"1d"``, ``"1h"``, ``"15m"`` ...). Note Yahoo
            limits intraday history (e.g. ``1h`` ~ 730 days, ``15m`` ~ 60 days).

    Returns:
        Standardized OHLCV DataFrame.
    """
    try:
        import yfinance as yf
    except ImportError as exc:  # pragma: no cover - dependency hint
        raise ImportError(
            "yfinance is required for live data. Install it with "
            "`pip install yfinance` (see trading/requirements.txt)."
        ) from exc

    ticker = resolve_symbol(symbol)
    kwargs = dict(interval=interval, auto_adjust=True, progress=False)
    if period:
        kwargs["period"] = period
    else:
        kwargs["start"] = start
        kwargs["end"] = end

    raw = yf.download(ticker, **kwargs)
    if raw is None or len(raw) == 0:
        raise RuntimeError(
            f"No data returned for '{symbol}' (ticker '{ticker}'). Check the "
            f"symbol, interval/period limits, and network access to Yahoo Finance."
        )

    # Flatten the (field, ticker) MultiIndex columns yfinance returns.
    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = raw.columns.get_level_values(0)

    return _standardize(raw)


def load_data(
    symbol: str | None = None,
    csv: str | None = None,
    start: str | None = None,
    end: str | None = None,
    period: str | None = None,
    interval: str = "1d",
) -> pd.DataFrame:
    """Convenience dispatcher: use ``csv`` if provided, else Yahoo Finance."""
    if csv:
        return load_csv(csv)
    if not symbol:
        raise ValueError("Provide either `symbol` (for yfinance) or `csv`.")
    return load_yfinance(symbol, start=start, end=end, period=period, interval=interval)
