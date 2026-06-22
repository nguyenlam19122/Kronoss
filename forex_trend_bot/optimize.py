"""Quét tham số (parameter sweep) — kiểm tra ĐỘ NHẠY của chiến lược, đặc biệt là
TRAILING STOP, để trả lời câu hỏi: "có phải do trailing chưa tối ưu?".

Đúng tinh thần course: "tối ưu hóa tham số/lợi thế". Nếu nới/siết trailing
(ChandelierMult) hay đổi AtrStopMult mà ∑R vẫn âm trên thị trường đi ngang,
thì trailing KHÔNG phải gốc rễ — vấn đề là regime/điểm vào lệnh.

Lưu ý: prepare() không phụ thuộc AtrStopMult/ChandelierMult nên chỉ cần tính 1 lần.

Chạy:
    python -m forex_trend_bot.optimize --data forex_trend_bot/data/EURUSD_H1.csv
    python -m forex_trend_bot.optimize --data <file> --regime-filter
    python -m forex_trend_bot.optimize --data <file> --chand-mult 1.5,2,2.5,3,4,5,6
"""
import argparse
import itertools
import os

import pandas as pd

from . import data as data_mod
from .backtest import run_backtest
from .config import BacktestParams, StrategyParams
from .strategy import prepare


def evaluate(df, sp, bp):
    trades, equity = run_backtest(df, sp, bp)
    if len(trades) == 0:
        return None
    R = trades["R"]
    wins, losses = R[R > 0], R[R < 0]
    cumR = R.cumsum()
    return {
        "trades": int(len(trades)),
        "win%": float((R > 0).mean() * 100),
        "avgWinR": float(wins.mean()) if len(wins) else 0.0,
        "avgLossR": float(losses.mean()) if len(losses) else 0.0,
        "payoff": float(wins.mean() / abs(losses.mean())) if len(wins) and len(losses) else float("nan"),
        "sumR": float(R.sum()),
        "maxDD_R": float((cumR - cumR.cummax()).min()),
    }


def main():
    ap = argparse.ArgumentParser(description="Quét tham số trailing stop / dừng lỗ.")
    ap.add_argument("--data", required=True)
    ap.add_argument("--regime-filter", action="store_true")
    ap.add_argument("--atr-stop", default="1.5,2.0,2.5,3.0", help="Danh sách AtrStopMult")
    ap.add_argument("--chand-mult", default="2.0,3.0,4.0,5.0", help="Danh sách ChandelierMult (trailing)")
    args = ap.parse_args()

    df0 = data_mod.load_ohlcv(args.data)
    df = prepare(df0, StrategyParams())                  # bất biến với tham số quét -> tính 1 lần
    atr_list = [float(x) for x in args.atr_stop.split(",")]
    chand_list = [float(x) for x in args.chand_mult.split(",")]

    rows = []
    for a, c in itertools.product(atr_list, chand_list):
        sp = StrategyParams(atr_stop_mult=a, chandelier_mult=c)
        bp = BacktestParams(regime_filter=args.regime_filter)
        m = evaluate(df, sp, bp)
        if m:
            m["atrStop"], m["chandMult"] = a, c
            rows.append(m)

    if not rows:
        print("Không có lệnh nào — kiểm tra dữ liệu.")
        return

    res = pd.DataFrame(rows).sort_values("sumR", ascending=False)
    cols = ["atrStop", "chandMult", "trades", "win%", "avgWinR", "avgLossR", "payoff", "sumR", "maxDD_R"]
    pd.set_option("display.float_format", lambda v: f"{v:.2f}")

    print(f"\nQUÉT THAM SỐ — {os.path.basename(args.data)} | regime_filter={args.regime_filter}")
    print("(sắp theo ∑R giảm dần)\n")
    print(res[cols].to_string(index=False))

    best, worst = res.iloc[0], res.iloc[-1]
    print("\nKẾT LUẬN nhanh:")
    print(f"  ∑R tốt nhất = {best['sumR']:.1f}  (AtrStop={best['atrStop']}, ChandMult={best['chandMult']})")
    print(f"  ∑R tệ nhất  = {worst['sumR']:.1f}")
    if best["sumR"] <= 0:
        print("  → Mọi cấu hình trailing đều ∑R ≤ 0: TRAILING KHÔNG phải gốc rễ,")
        print("    vấn đề nằm ở regime/điểm vào lệnh (nên lọc chop hoặc đổi chiến lược cho sideway).")
    else:
        print("  → Có vùng tham số cho ∑R > 0: trailing/stop CÓ ảnh hưởng — nhưng phải kiểm định")
        print("    walk-forward/out-of-sample trước khi tin (tránh overfit chọn đỉnh may rủi).")


if __name__ == "__main__":
    main()
