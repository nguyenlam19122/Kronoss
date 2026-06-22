"""Phân loại chế độ thị trường (regime) bằng THỐNG KÊ — theo đúng workflow course:
"xác định thị trường có xu hướng hay thiếu xu hướng".

Công cụ:
  - Hurst exponent        : H > 0.5 xu hướng | H < 0.5 hồi quy về trung bình (MR) | ~0.5 ngẫu nhiên
  - Variance Ratio (Lo-MacKinlay) : VR > 1 xu hướng | VR < 1 MR | kèm z-stat & p-value
  - Tự tương quan return  : dương -> quán tính (trend) | âm -> đảo chiều (MR)
  - Efficiency Ratio (Kaufman)    : cao -> đi thẳng (trend) | thấp -> nhiễu (sideway)

Dùng để: (1) chẩn đoán 1 thị trường nên trend-following hay mean-reversion,
         (2) gắn nhãn regime theo từng nến cho bộ định tuyến (router) chiến lược.
"""
import numpy as np
import pandas as pd
from scipy import stats

from . import indicators as ind


# ----------------------------------------------------------------------
# Các thước đo ở cấp ĐỘ TẬP DỮ LIỆU (mô tả tính chất thị trường)
# ----------------------------------------------------------------------
def hurst_exponent(log_price: np.ndarray, max_lag: int = 60) -> float:
    """Hurst qua độ phân tán của sai phân theo lag (log-log slope)."""
    p = np.asarray(log_price, dtype=float)
    max_lag = min(max_lag, len(p) // 2)
    if max_lag < 5:
        return float("nan")
    lags = np.arange(2, max_lag)
    tau = np.array([np.std(p[lag:] - p[:-lag]) for lag in lags])
    mask = tau > 0
    if mask.sum() < 3:
        return float("nan")
    slope = np.polyfit(np.log(lags[mask]), np.log(tau[mask]), 1)[0]
    return float(slope)


def variance_ratio(log_price: np.ndarray, q: int):
    """Variance Ratio test (homoskedastic). VR>1 trend, VR<1 mean-revert."""
    p = np.asarray(log_price, dtype=float)
    n = len(p) - 1
    if n < q * 2 or q < 2:
        return None
    mu = (p[-1] - p[0]) / n
    r = np.diff(p)
    sigma_a2 = np.sum((r - mu) ** 2) / (n - 1)
    if sigma_a2 <= 0:
        return None
    diffs_q = p[q:] - p[:-q] - q * mu
    m = q * (n - q + 1) * (1.0 - q / n)
    sigma_c2 = np.sum(diffs_q ** 2) / m
    vr = sigma_c2 / sigma_a2
    var_vr = (2.0 * (2 * q - 1) * (q - 1)) / (3.0 * q * n)
    z = (vr - 1.0) / np.sqrt(var_vr)
    p_value = 2.0 * stats.norm.sf(abs(z))   # 2 phía
    return {"q": q, "vr": float(vr), "z": float(z), "p_value": float(p_value)}


def efficiency_ratio(close: pd.Series, period: int = 20) -> pd.Series:
    """Kaufman Efficiency Ratio: |biến động ròng| / tổng |biến động| trong N nến."""
    change = close.diff(period).abs()
    volatility = close.diff().abs().rolling(period).sum()
    return change / volatility


# ----------------------------------------------------------------------
# Gắn nhãn regime theo TỪNG NẾN (cho router chiến lược)
# ----------------------------------------------------------------------
def classify_bars(df: pd.DataFrame, adx_period: int = 14, adx_min: float = 25.0,
                  er_period: int = 20, er_min: float = 0.30) -> pd.Series:
    """Trả về Series nhãn: 'trend' (đủ xu hướng) hoặc 'range' (đi ngang)."""
    adx_, _, _ = ind.adx(df["high"], df["low"], df["close"], adx_period)
    er = efficiency_ratio(df["close"], er_period)
    is_trend = (adx_ >= adx_min) & (er >= er_min)
    return pd.Series(np.where(is_trend, "trend", "range"), index=df.index, name="regime")


# ----------------------------------------------------------------------
# Báo cáo tổng hợp + kết luận
# ----------------------------------------------------------------------
def diagnose(df: pd.DataFrame) -> dict:
    close = df["close"]
    logp = np.log(close.to_numpy(float))
    ret = close.pct_change().dropna()

    H = hurst_exponent(logp)
    vr2 = variance_ratio(logp, 2)
    vr5 = variance_ratio(logp, 5)
    vr10 = variance_ratio(logp, 10)
    ac1 = float(ret.autocorr(1)) if len(ret) > 2 else float("nan")
    ac5 = float(ret.autocorr(5)) if len(ret) > 6 else float("nan")
    er = efficiency_ratio(close, 20)
    er_mean = float(er.mean())
    pct_trend = float((classify_bars(df) == "trend").mean())

    # Kết luận: gộp Hurst + VR(5) + tự tương quan
    vr_val = vr5["vr"] if vr5 else 1.0
    vr_sig = (vr5 is not None) and (vr5["p_value"] < 0.05)
    trend_score = 0
    if H > 0.52:
        trend_score += 1
    if H < 0.48:
        trend_score -= 1
    if vr_val > 1.0:
        trend_score += 1
    if vr_val < 1.0:
        trend_score -= 1
    if ac1 > 0:
        trend_score += 1
    if ac1 < 0:
        trend_score -= 1

    if trend_score >= 2:
        verdict = "CÓ XU HƯỚNG → ưu tiên TREND-FOLLOWING"
    elif trend_score <= -2:
        verdict = "HỒI QUY TRUNG BÌNH → ưu tiên MEAN-REVERSION (fade biên)"
    else:
        verdict = "GẦN NGẪU NHIÊN (random walk) → khó có edge bền, cần lọc kỹ"
    if vr_sig:
        verdict += "  [VR có ý nghĩa thống kê]"

    return {
        "hurst": H, "vr2": vr2, "vr5": vr5, "vr10": vr10,
        "autocorr_lag1": ac1, "autocorr_lag5": ac5,
        "efficiency_ratio_mean": er_mean, "pct_time_trending": pct_trend,
        "trend_score": trend_score, "verdict": verdict,
    }


def format_diagnosis(d: dict, title: str = "") -> str:
    L = []
    if title:
        L += [title, "=" * len(title)]
    L.append(f"  Hurst exponent       : {d['hurst']:.3f}   (>0.5 xu hướng | <0.5 hồi quy TB)")
    for k in ("vr2", "vr5", "vr10"):
        v = d[k]
        if v:
            sig = "✓ ý nghĩa" if v["p_value"] < 0.05 else "không ý nghĩa"
            L.append(f"  Variance Ratio q={v['q']:<2}  : {v['vr']:.3f}   z={v['z']:+.2f}  p={v['p_value']:.3f} ({sig})")
    L.append(f"  Tự tương quan lag1   : {d['autocorr_lag1']:+.3f}   (dương=quán tính | âm=đảo chiều)")
    L.append(f"  Efficiency Ratio TB  : {d['efficiency_ratio_mean']:.3f}   (cao=đi thẳng | thấp=nhiễu)")
    L.append(f"  % thời gian có trend : {d['pct_time_trending']:.1%}")
    L.append(f"  → KẾT LUẬN: {d['verdict']}")
    return "\n".join(L)
