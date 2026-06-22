"""Tạo dữ liệu H1 GIẢ LẬP để smoke-test pipeline.

⚠️  CHỈ để kiểm tra code chạy đúng end-to-end. Đây KHÔNG phải dữ liệu thật và
KHÔNG dùng để đánh giá edge. Hãy thay bằng 3 bộ dữ liệu H1 thật của bạn.

Sinh chuỗi giá có xen kẽ các giai đoạn có xu hướng (trend) và đi ngang (range)
để hệ thống trend-following có "đất diễn".
"""
import os

import numpy as np
import pandas as pd


def generate(n_bars=8000, start="2021-01-04", seed=7, start_price=1.10):
    rng = np.random.default_rng(seed)
    # Lịch H1 ngày thường (bỏ cuối tuần) cho giống forex
    idx = pd.bdate_range(start=start, periods=n_bars, freq="h")

    drift = np.zeros(n_bars)
    i = 0
    while i < n_bars:
        block = rng.integers(150, 500)          # độ dài 1 chế độ
        regime = rng.choice(["up", "down", "range"], p=[0.35, 0.30, 0.35])
        mu = {"up": 0.00012, "down": -0.00012, "range": 0.0}[regime]
        drift[i:i + block] = mu
        i += block

    vol = 0.0009
    rets = drift[:n_bars] + rng.normal(0, vol, n_bars)
    close = start_price * np.exp(np.cumsum(rets))

    open_ = np.empty(n_bars)
    open_[0] = start_price
    open_[1:] = close[:-1]
    intrabar = np.abs(rng.normal(0, vol, n_bars)) * close
    high = np.maximum(open_, close) + intrabar
    low = np.minimum(open_, close) - intrabar
    volume = rng.integers(500, 5000, n_bars)

    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": volume},
        index=idx,
    )


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    out_dir = os.path.join(here, "data")
    os.makedirs(out_dir, exist_ok=True)
    df = generate()
    out = os.path.join(out_dir, "SAMPLE_synthetic_H1.csv")
    df.to_csv(out, index_label="time")
    print(f"Đã tạo dữ liệu giả lập: {out}  ({len(df):,} nến)")
    print("⚠️  Chỉ để test pipeline — không phải dữ liệu thật.")


if __name__ == "__main__":
    main()
