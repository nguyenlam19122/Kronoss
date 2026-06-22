"""Khảo sát & mô tả dữ liệu — BƯỚC ĐẦU theo workflow course:
xác định mỗi thị trường CÓ XU HƯỚNG hay THIẾU XU HƯỚNG (bằng thống kê).

Chạy:
    python -m forex_trend_bot.analyze_regime --data forex_trend_bot/data
    python -m forex_trend_bot.analyze_regime --data path/to/EURUSD_H1.csv

Kết quả giúp quyết định mỗi cặp nên dùng trend-following, mean-reversion,
hay nên đứng ngoài (gần ngẫu nhiên).
"""
import argparse
import os

from . import data as data_mod
from . import regime as R

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DATA_DIR = os.path.join(HERE, "data")


def run_one(path):
    name = os.path.splitext(os.path.basename(path))[0]
    df = data_mod.load_ohlcv(path)
    d = R.diagnose(df)
    print("\n" + "#" * 72)
    print(f"# {name}   ({len(df):,} nến | {df.index[0].date()} → {df.index[-1].date()})")
    print("#" * 72)
    print(R.format_diagnosis(d))
    return name, d


def main():
    ap = argparse.ArgumentParser(description="Chẩn đoán regime thị trường (trend vs mean-reversion).")
    ap.add_argument("--data", default=DEFAULT_DATA_DIR, help="File CSV hoặc thư mục chứa CSV H1")
    args = ap.parse_args()

    if os.path.isdir(args.data):
        files = data_mod.discover_csvs(args.data)
        if not files:
            print(f"⚠️  Không có file .csv trong: {args.data}")
            return
    else:
        files = [args.data]

    results = []
    for path in files:
        try:
            results.append(run_one(path))
        except Exception as e:
            print(f"❌ Lỗi với {path}: {e}")

    if len(results) > 1:
        print("\n" + "=" * 72)
        print("TỔNG HỢP — nên dùng chiến lược gì cho từng thị trường")
        print("=" * 72)
        for name, d in results:
            print(f"  {name:<28} H={d['hurst']:.2f}  score={d['trend_score']:+d}  → {d['verdict']}")


if __name__ == "__main__":
    main()
