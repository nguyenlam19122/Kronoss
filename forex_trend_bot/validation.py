"""Kiểm định độ bền: real-edge hay fake-edge?

Gồm 3 bài test theo đúng tinh thần phát triển chiến lược chuyên nghiệp:
  1. Walk-forward / phân đoạn  -> edge có ỔN ĐỊNH qua các giai đoạn không?
  2. Monte Carlo (bootstrap)   -> đường vốn/drawdown bền tới đâu khi xáo thứ tự lệnh?
  3. T-test một phía           -> kỳ vọng lợi nhuận có khác 0 CÓ Ý NGHĨA THỐNG KÊ không?
"""
import numpy as np
import pandas as pd
from scipy import stats

from .backtest import run_backtest
from .config import BacktestParams, StrategyParams
from . import metrics as M


def segment_analysis(df: pd.DataFrame, sp: StrategyParams, bp: BacktestParams, n_segments: int = 4):
    """Chia dữ liệu thành N đoạn liên tiếp, backtest từng đoạn để xem edge có nhất quán."""
    bounds = np.linspace(0, len(df), n_segments + 1, dtype=int)
    rows = []
    for s in range(n_segments):
        seg = df.iloc[bounds[s]:bounds[s + 1]]
        if len(seg) < 50:
            continue
        trades, equity = run_backtest(seg, sp, bp)
        m = M.compute(trades, equity, bp.initial_equity)
        rows.append({
            "segment": s + 1,
            "from": seg.index[0].date(),
            "to": seg.index[-1].date(),
            "n_trades": m["n_trades"],
            "total_return": m["total_return"],
            "sharpe": m["sharpe"],
            "max_drawdown": m["max_drawdown"],
            "profit_factor": m["profit_factor"],
        })
    return pd.DataFrame(rows)


def monte_carlo(trades: pd.DataFrame, bp: BacktestParams, n_sims: int = 2000, seed: int = 42):
    """Bootstrap (lấy mẫu có hoàn lại) các bội số R, dựng lại đường vốn compounding.

    equity_{t+1} = equity_t * (1 + R_t * risk_pct), vì pnl = R * (equity * risk_pct).
    Trả về phân phối lợi nhuận cuối & max drawdown -> đo rủi ro đường vốn.
    """
    if len(trades) < 5:
        return None
    R = trades["R"].to_numpy(float)
    rng = np.random.default_rng(seed)
    n = len(R)

    final_returns = np.empty(n_sims)
    max_dds = np.empty(n_sims)
    for k in range(n_sims):
        sample = R[rng.integers(0, n, size=n)]
        growth = 1.0 + sample * bp.risk_pct
        equity = bp.initial_equity * np.cumprod(growth)
        final_returns[k] = equity[-1] / bp.initial_equity - 1.0
        peak = np.maximum.accumulate(equity)
        max_dds[k] = float(((equity - peak) / peak).min())

    pct = lambda a, q: float(np.percentile(a, q))
    return {
        "n_sims": n_sims,
        "ret_p05": pct(final_returns, 5),     # đuôi xấu của lợi nhuận
        "ret_p50": pct(final_returns, 50),
        "ret_p95": pct(final_returns, 95),
        "dd_p50": pct(max_dds, 50),
        "dd_worst_p95": pct(max_dds, 5),      # drawdown là số âm -> đuôi xấu ở percentile 5
        "prob_loss": float((final_returns < 0).mean()),
    }


def t_test(trades: pd.DataFrame):
    """T-test một phía: H0 kỳ vọng R = 0, H1 kỳ vọng R > 0."""
    if len(trades) < 5:
        return None
    R = trades["R"].to_numpy(float)
    t_stat, p_two = stats.ttest_1samp(R, 0.0)
    p_one = p_two / 2.0 if t_stat > 0 else 1.0 - p_two / 2.0
    return {
        "n": int(len(R)),
        "mean_R": float(np.mean(R)),
        "t_stat": float(t_stat),
        "p_value_one_sided": float(p_one),
        "significant_5pct": bool(p_one < 0.05 and t_stat > 0),
    }


def format_validation(seg_df, mc, tt) -> str:
    lines = ["", "KIỂM ĐỊNH ĐỘ BỀN (REAL-EDGE?)", "=" * 32]

    lines.append("\n[1] Phân tích theo đoạn (edge có ổn định qua thời gian?)")
    if seg_df is not None and len(seg_df):
        for _, r in seg_df.iterrows():
            lines.append(
                f"  Đoạn {int(r['segment'])} ({r['from']}→{r['to']}): "
                f"{int(r['n_trades']):>3} lệnh | LN {r['total_return']:>7.2%} | "
                f"Sharpe {r['sharpe']:>5.2f} | PF {r['profit_factor']:>5.2f}"
            )
    else:
        lines.append("  (không đủ dữ liệu)")

    lines.append("\n[2] Monte Carlo (bootstrap đường vốn)")
    if mc:
        lines.append(f"  Lợi nhuận cuối  P05/P50/P95: {mc['ret_p05']:>7.2%} / {mc['ret_p50']:>7.2%} / {mc['ret_p95']:>7.2%}")
        lines.append(f"  Max drawdown    P50/P95 xấu: {mc['dd_p50']:>7.2%} / {mc['dd_worst_p95']:>7.2%}")
        lines.append(f"  Xác suất thua lỗ            : {mc['prob_loss']:>7.2%}")
    else:
        lines.append("  (cần >= 5 lệnh)")

    lines.append("\n[3] T-test (kỳ vọng có > 0 đáng kể?)")
    if tt:
        verdict = "CÓ Ý NGHĨA ✅ (nghiêng về real-edge)" if tt["significant_5pct"] else "CHƯA đủ ý nghĩa ⚠️ (cảnh giác fake-edge)"
        lines.append(f"  n={tt['n']} | mean R={tt['mean_R']:.3f} | t={tt['t_stat']:.2f} | p(1 phía)={tt['p_value_one_sided']:.4f}")
        lines.append(f"  Kết luận: {verdict}")
    else:
        lines.append("  (cần >= 5 lệnh)")

    return "\n".join(lines)
