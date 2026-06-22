"""Chạy backtest + kiểm định cho 1 file hoặc cả thư mục dữ liệu H1.

Ví dụ:
    python -m forex_trend_bot.run_backtest                       # quét forex_trend_bot/data/
    python -m forex_trend_bot.run_backtest --data path/to/EURUSD_H1.csv
    python -m forex_trend_bot.run_backtest --data my_dir --plot
    python -m forex_trend_bot.run_backtest --short-off          # chỉ long
"""
import argparse
import os

from . import data as data_mod
from . import metrics as M
from . import validation as V
from .backtest import run_backtest
from .config import BacktestParams, StrategyParams
from .strategy import prepare

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DATA_DIR = os.path.join(HERE, "data")
RESULTS_DIR = os.path.join(HERE, "results")


def _plot(name, df, equity, trades):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(13, 10), sharex=True)

    ax1.plot(df.index, df["close"], color="#444", lw=0.8, label="Close")
    ax1.plot(df.index, df["ema_fast"], color="#1f77b4", lw=1.0, label="EMA fast")
    ax1.plot(df.index, df["ema_slow"], color="#ff7f0e", lw=1.0, label="EMA slow")
    if len(trades):
        longs = trades[trades["direction"] == "long"]
        shorts = trades[trades["direction"] == "short"]
        ax1.scatter(longs["entry_time"], longs["entry_price"], marker="^", color="green", s=40, label="Long", zorder=5)
        ax1.scatter(shorts["entry_time"], shorts["entry_price"], marker="v", color="red", s=40, label="Short", zorder=5)
        ax1.scatter(trades["exit_time"], trades["exit_price"], marker="x", color="black", s=30, label="Exit", zorder=5)
    ax1.set_ylabel("Giá"); ax1.legend(loc="best", fontsize=8); ax1.grid(alpha=0.3)
    ax1.set_title(f"{name} — Trend Rider (H1)")

    ax2.plot(equity.index, equity.values, color="#2ca02c", lw=1.2, label="Equity")
    ax2.axhline(equity.iloc[0], color="red", ls="--", lw=0.8)
    ax2.set_ylabel("Vốn"); ax2.legend(loc="best", fontsize=8); ax2.grid(alpha=0.3)

    peak = equity.cummax()
    dd = (equity - peak) / peak
    ax3.fill_between(equity.index, dd.values, 0, color="red", alpha=0.3)
    ax3.set_ylabel("Drawdown"); ax3.grid(alpha=0.3)

    fig.tight_layout()
    os.makedirs(RESULTS_DIR, exist_ok=True)
    out = os.path.join(RESULTS_DIR, f"{name}_backtest.png")
    fig.savefig(out, dpi=130, bbox_inches="tight")
    plt.close(fig)
    print(f"  📊 Đã lưu biểu đồ: {out}")


def run_one(path, sp, bp, do_plot, segments, mc_sims, validate):
    name = os.path.splitext(os.path.basename(path))[0]
    print("\n" + "#" * 72)
    print(f"# {name}")
    print("#" * 72)

    df = data_mod.load_ohlcv(path)
    print(f"Dữ liệu: {len(df):,} nến | {df.index[0]} → {df.index[-1]}")

    df = prepare(df, sp)
    trades, equity = run_backtest(df, sp, bp)

    if bp.risk_mode == "fixed":
        print(f"Chế độ rủi ro: 1R = ${bp.fixed_risk:.0f} ALL-IN (đã GỒM spread) | spread = {bp.spread:g}")
        print(f"  → lệnh dính stop ban đầu = tổng lỗ đúng ${bp.fixed_risk:.0f} (= -1.00R)")
    else:
        print(f"Chế độ rủi ro: {bp.risk_pct:.2%} equity/lệnh (đã gồm spread) | spread = {bp.spread:g}")
    if len(trades):
        spread_cost = float((trades["size"] * bp.spread).sum())
        extra = f"  (≈ {spread_cost / bp.fixed_risk:.1f}R)" if bp.risk_mode == "fixed" else ""
        print(f"Tổng phí spread (nằm trong rủi ro): ${spread_cost:,.2f}{extra}")

    m = M.compute(trades, equity, bp.initial_equity)
    print("\n" + M.format_report(m, "HIỆU NĂNG"))

    if validate:
        seg = V.segment_analysis(df, sp, bp, n_segments=segments)
        mc = V.monte_carlo(trades, bp, n_sims=mc_sims)
        tt = V.t_test(trades)
        print(V.format_validation(seg, mc, tt))

    if do_plot:
        _plot(name, df, equity, trades)
    return m


def build_params(args):
    sp = StrategyParams()
    bp = BacktestParams(
        initial_equity=args.equity,
        risk_mode=args.risk_mode,
        fixed_risk=args.fixed_risk,
        risk_pct=args.risk,
        spread=args.spread,
        allow_long=not args.long_off,
        allow_short=not args.short_off,
    )
    if args.exit_on_flip:
        sp.exit_on_trend_flip = True
    return sp, bp


def main():
    ap = argparse.ArgumentParser(description="Backtest chiến lược trend-following H1 (forex).")
    ap.add_argument("--data", default=DEFAULT_DATA_DIR, help="File CSV hoặc thư mục chứa các file CSV H1")
    ap.add_argument("--plot", action="store_true", help="Lưu biểu đồ equity/drawdown")
    ap.add_argument("--equity", type=float, default=10_000.0)
    ap.add_argument("--risk-mode", choices=["fixed", "percent"], default="fixed",
                    help="fixed = 1R cố định $ (mặc định, dễ thống kê edge); percent = %% equity")
    ap.add_argument("--fixed-risk", type=float, default=50.0, help="1R = bao nhiêu $ (khi --risk-mode fixed)")
    ap.add_argument("--risk", type=float, default=0.01, help="Rủi ro mỗi lệnh khi --risk-mode percent (mặc định 1%%)")
    ap.add_argument("--spread", type=float, default=0.0001, help="Spread theo đơn vị giá (vd EURUSD 0.0001)")
    ap.add_argument("--segments", type=int, default=4, help="Số đoạn cho walk-forward")
    ap.add_argument("--mc-sims", type=int, default=2000, help="Số mô phỏng Monte Carlo")
    ap.add_argument("--no-validation", action="store_true")
    ap.add_argument("--long-off", action="store_true")
    ap.add_argument("--short-off", action="store_true")
    ap.add_argument("--exit-on-flip", action="store_true", help="Thoát khi trend đảo (mặc định: gồng bằng trailing)")
    args = ap.parse_args()

    sp, bp = build_params(args)

    if os.path.isdir(args.data):
        files = data_mod.discover_csvs(args.data)
        if not files:
            print(f"⚠️  Không tìm thấy file .csv nào trong: {args.data}")
            print("    Hãy thả các file dữ liệu H1 của bạn vào đó rồi chạy lại.")
            return
    else:
        files = [args.data]

    for path in files:
        try:
            run_one(path, sp, bp, args.plot, args.segments, args.mc_sims, not args.no_validation)
        except Exception as e:
            print(f"❌ Lỗi với {path}: {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    main()
