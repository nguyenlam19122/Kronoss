"""Loader CSV forex linh hoạt.

Tự nhận diện dấu phân cách và tên cột cho các định dạng phổ biến:
  - Xuất từ MetaTrader 5 / History Center (Date, Time, Open, High, Low, Close, Volume)
  - Định dạng chung: time/timestamp/date + open/high/low/close[/volume]
  - File có cột ngày & giờ tách rời sẽ được ghép lại.

Trả về DataFrame có DatetimeIndex tăng dần và các cột: open, high, low, close, volume.
"""
import glob
import os

import pandas as pd

# Các biến thể tên cột -> tên chuẩn
_COLUMN_ALIASES = {
    "open": "open", "o": "open", "<open>": "open", "giá mở": "open", "gia mo": "open",
    "high": "high", "h": "high", "<high>": "high", "giá cao": "high", "gia cao": "high",
    "low": "low", "l": "low", "<low>": "low", "giá thấp": "low", "gia thap": "low",
    "close": "close", "c": "close", "<close>": "close", "price": "close", "giá đóng": "close", "gia dong": "close",
    "volume": "volume", "vol": "volume", "v": "volume", "<vol>": "volume", "tickvol": "volume",
    "<tickvol>": "volume", "tick_volume": "volume", "khối lượng": "volume", "khoi luong": "volume",
}

_TIME_NAMES = {"time", "timestamp", "datetime", "date_time", "gmt time", "<datetime>", "thời gian", "thoi gian"}
_DATE_NAMES = {"date", "<date>", "ngày", "ngay"}
_TIME_ONLY_NAMES = {"time", "<time>", "giờ", "gio"}


def _norm(name: str) -> str:
    return str(name).strip().lower().replace("﻿", "")


def load_ohlcv(path: str) -> pd.DataFrame:
    """Đọc một file CSV và trả về DataFrame OHLCV chuẩn hoá."""
    # engine='python' + sep=None để tự dò dấu phân cách (',', ';', tab, khoảng trắng)
    df = pd.read_csv(path, sep=None, engine="python")
    df.columns = [_norm(c) for c in df.columns]

    # 1) Xử lý cột thời gian
    time_col = next((c for c in df.columns if c in _TIME_NAMES), None)
    if time_col is not None:
        ts = pd.to_datetime(df[time_col], errors="coerce", dayfirst=False)
    else:
        date_col = next((c for c in df.columns if c in _DATE_NAMES), None)
        time_only = next((c for c in df.columns if c in _TIME_ONLY_NAMES and c != date_col), None)
        if date_col is not None and time_only is not None:
            ts = pd.to_datetime(df[date_col].astype(str) + " " + df[time_only].astype(str), errors="coerce")
        elif date_col is not None:
            ts = pd.to_datetime(df[date_col], errors="coerce")
        else:
            # Không có cột thời gian -> dùng cột đầu tiên
            ts = pd.to_datetime(df.iloc[:, 0], errors="coerce")

    # 2) Đổi tên cột OHLCV
    renamed = {c: _COLUMN_ALIASES[c] for c in df.columns if c in _COLUMN_ALIASES}
    df = df.rename(columns=renamed)

    required = ["open", "high", "low", "close"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(
            f"File {os.path.basename(path)} thiếu cột {missing}. "
            f"Các cột đọc được: {list(df.columns)}"
        )

    if "volume" not in df.columns:
        df["volume"] = 0.0

    out = df[["open", "high", "low", "close", "volume"]].copy()
    out.index = pd.DatetimeIndex(ts)
    out = out[out.index.notna()]
    for col in ["open", "high", "low", "close", "volume"]:
        out[col] = pd.to_numeric(out[col], errors="coerce")
    out = out.dropna(subset=["open", "high", "low", "close"])
    out = out[~out.index.duplicated(keep="first")].sort_index()

    if len(out) == 0:
        raise ValueError(f"Không parse được dữ liệu hợp lệ từ {path}")
    return out


def discover_csvs(data_dir: str):
    """Liệt kê các file .csv trong thư mục (bỏ qua file ẩn)."""
    files = sorted(glob.glob(os.path.join(data_dir, "*.csv")))
    return [f for f in files if not os.path.basename(f).startswith(".")]
