"""
Backtester cho chiến lược Ichimoku + ATR trend-following (khớp với IchimokuATR_TrendEA.mq5).

Thiết kế cho tối ưu hóa WFA + GA:
- Indicator (Donchian, ATR) được CACHE theo (len/period) trên toàn bộ dataset -> tái dùng
  cho mọi cửa sổ và mọi cá thể GA.
- Vòng lặp state-machine được JIT bằng numba để chạy hàng nghìn lần thật nhanh.
- Không nhìn trước (no look-ahead): tín hiệu tính trên nến đã đóng (i-1), khớp lệnh tại open[i].
- Max Drawdown tính theo equity MARK-TO-MARKET (gồm lỗ/lãi nổi trong lệnh) -> sát thực tế.
"""
import numpy as np
import pandas as pd
from numba import njit

POINT    = 0.00001      # EURUSD 5-digit: 1 point = 0.00001
CONTRACT = 100000.0     # 1.0 lot = 100,000 units; PnL(USD) = (exit-entry)*CONTRACT*lot
LOT_STEP = 0.01
MIN_LOT  = 0.01


# ----------------------------------------------------------------------------- data
def load_data(csv_path):
    """Nạp CSV định dạng MT5 export (tab-separated) -> DataFrame có cột year."""
    df = pd.read_csv(csv_path, sep="\t")
    df.columns = [c.strip("<>").lower() for c in df.columns]
    df["dt"] = pd.to_datetime(df["date"] + " " + df["time"], format="%Y.%m.%d %H:%M:%S")
    df = df.sort_values("dt").reset_index(drop=True)
    df["year"] = df["dt"].dt.year
    return df


def to_arrays(df):
    return {
        "open":   df["open"].to_numpy(np.float64),
        "high":   df["high"].to_numpy(np.float64),
        "low":    df["low"].to_numpy(np.float64),
        "close":  df["close"].to_numpy(np.float64),
        "spread": df["spread"].to_numpy(np.float64) * POINT,   # points -> price
        "year":   df["year"].to_numpy(np.int64),
    }


def year_bounds(arr):
    """Trả về dict {year: (start_idx, end_idx)} (end_idx loại trừ)."""
    years = arr["year"]
    bounds = {}
    for y in np.unique(years):
        idx = np.where(years == y)[0]
        bounds[int(y)] = (int(idx[0]), int(idx[-1]) + 1)
    return bounds


# ------------------------------------------------------------------- indicator cache
class IndicatorCache:
    """Tính & cache Donchian(len) và ATR(period) trên TOÀN dataset (tính 1 lần, dùng lại)."""
    def __init__(self, arr):
        self.h = arr["high"]; self.l = arr["low"]; self.c = arr["close"]
        self._donch = {}; self._atr = {}; self._adx = {}

    def donchian(self, length):
        if length not in self._donch:
            hh = pd.Series(self.h).rolling(length).max().to_numpy()
            ll = pd.Series(self.l).rolling(length).min().to_numpy()
            self._donch[length] = (hh + ll) * 0.5
        return self._donch[length]

    def atr(self, period):
        if period not in self._atr:
            h, l, c = self.h, self.l, self.c
            prev_c = np.empty_like(c); prev_c[0] = c[0]; prev_c[1:] = c[:-1]
            tr = np.maximum(h - l, np.maximum(np.abs(h - prev_c), np.abs(l - prev_c)))
            atr = np.full_like(tr, np.nan)
            if len(tr) > period:
                atr[period] = np.mean(tr[1:period + 1])      # Wilder RMA seed
                a = 1.0 / period
                for i in range(period + 1, len(tr)):
                    atr[i] = atr[i - 1] * (1 - a) + tr[i] * a
            self._atr[period] = atr
        return self._atr[period]

    def adx(self, period):
        """ADX (Wilder) tinh tren toan dataset, cache theo period."""
        if period not in self._adx:
            h, l, c = self.h, self.l, self.c
            n = len(c)
            tr = np.zeros(n); pdm = np.zeros(n); mdm = np.zeros(n)
            for i in range(1, n):
                up = h[i] - h[i - 1]; dn = l[i - 1] - l[i]
                pdm[i] = up if (up > dn and up > 0.0) else 0.0
                mdm[i] = dn if (dn > up and dn > 0.0) else 0.0
                tr[i] = max(h[i] - l[i], abs(h[i] - c[i - 1]), abs(l[i] - c[i - 1]))
            adx = np.full(n, np.nan)
            if n > 2 * period + 1:
                str_ = tr[1:period + 1].sum()
                spd = pdm[1:period + 1].sum()
                smd = mdm[1:period + 1].sum()
                dx = np.full(n, np.nan)
                a = 1.0 / period
                for i in range(period, n):
                    if i > period:                      # Wilder smoothing
                        str_ = str_ - str_ * a + tr[i]
                        spd = spd - spd * a + pdm[i]
                        smd = smd - smd * a + mdm[i]
                    pdi = 100.0 * spd / str_ if str_ > 0 else 0.0
                    mdi = 100.0 * smd / str_ if str_ > 0 else 0.0
                    s = pdi + mdi
                    dx[i] = 100.0 * abs(pdi - mdi) / s if s > 0 else 0.0
                first = 2 * period
                if first < n:
                    adx[first] = np.mean(dx[period:first + 1])
                    for i in range(first + 1, n):
                        adx[i] = adx[i - 1] * (1 - a) + dx[i] * a
            self._adx[period] = adx
        return self._adx[period]


# --------------------------------------------------------------------- numba engine
@njit(cache=True, fastmath=True)
def _run(open_, high, low, close, spread,
         tenkan, kijun, spanB_raw, atr_sl, atr_trail, disp,
         sl_mult, trail_mult, require_color, use_ichi_exit,
         risk_usd, start_idx, end_idx, start_balance):
    n_max = end_idx - start_idx
    pnls = np.empty(n_max, dtype=np.float64)
    nt = 0

    pos = 0; entry = 0.0; sl = 0.0; lot = 0.0
    realized = 0.0
    peak_eq = start_balance
    max_dd = 0.0
    max_dd_pct = 0.0

    for i in range(start_idx, end_idx):
        j = i - 1            # nến đã đóng (tín hiệu + ATR + trailing lấy từ đây)
        jd = j - disp        # nến tạo nên đám mây nằm DƯỚI nến j
        if jd < 1:
            continue

        tk = tenkan[j]; kj = kijun[j]; tkp = tenkan[j - 1]; kjp = kijun[j - 1]
        ta = tenkan[jd]; ka = kijun[jd]; sbv = spanB_raw[jd]
        if np.isnan(tk) or np.isnan(kj) or np.isnan(tkp) or np.isnan(kjp) \
           or np.isnan(ta) or np.isnan(ka) or np.isnan(sbv) \
           or np.isnan(atr_sl[j]) or np.isnan(atr_trail[j]):
            continue
        sa = (ta + ka) * 0.5     # Senkou A dưới nến j
        sb = sbv                 # Senkou B dưới nến j
        cloud_top = sa if sa > sb else sb
        cloud_bot = sa if sa < sb else sb
        op = open_[i]; hi = high[i]; lo = low[i]
        half = spread[i] * 0.5
        closed_this_bar = False

        # === A. Quản lý vị thế hiện có (tại open[i], dựa trên nến j) ===
        if pos != 0:
            if use_ichi_exit == 1:
                if pos == 1 and (close[j] < kj or close[j] < cloud_bot):
                    p = (op - half - entry) * CONTRACT * lot
                    pnls[nt] = p; nt += 1; realized += p; pos = 0; closed_this_bar = True
                elif pos == -1 and (close[j] > kj or close[j] > cloud_top):
                    p = (entry - (op + half)) * CONTRACT * lot
                    pnls[nt] = p; nt += 1; realized += p; pos = 0; closed_this_bar = True
            if pos != 0:                          # trailing ratchet từ close[j]
                if pos == 1:
                    new_sl = close[j] - atr_trail[j] * trail_mult
                    if new_sl > sl: sl = new_sl
                else:
                    new_sl = close[j] + atr_trail[j] * trail_mult
                    if new_sl < sl: sl = new_sl

        # === B. SL chạm trong nến i (vị thế đang mở) ===
        if pos == 1 and lo <= sl:
            fill = sl if op >= sl else op          # xử lý gap
            p = (fill - entry) * CONTRACT * lot
            pnls[nt] = p; nt += 1; realized += p; pos = 0; closed_this_bar = True
        elif pos == -1 and hi >= sl:
            fill = sl if op <= sl else op
            p = (entry - fill) * CONTRACT * lot
            pnls[nt] = p; nt += 1; realized += p; pos = 0; closed_this_bar = True

        # === C. Vào lệnh mới (flat & chưa đóng lệnh trong nến này) ===
        if pos == 0 and not closed_this_bar:
            cross_up = (tkp <= kjp) and (tk > kj)
            cross_dn = (tkp >= kjp) and (tk < kj)
            cl = close[j]
            color_bull = (require_color == 0) or (sa > sb)
            color_bear = (require_color == 0) or (sa < sb)
            long_ok  = (cl > cloud_top) and color_bull and (cl > kj) and cross_up
            short_ok = (cl < cloud_bot) and color_bear and (cl < kj) and cross_dn
            if long_ok or short_ok:
                atrd = atr_sl[j] * sl_mult
                if atrd > 0:
                    raw_lot = risk_usd / ((atrd + spread[j]) * CONTRACT)
                    lot = np.floor(raw_lot / LOT_STEP) * LOT_STEP
                    if lot >= MIN_LOT:
                        if long_ok:
                            entry = op + half; sl = entry - atrd; pos = 1
                            if lo <= sl:                       # bị quét ngay nến vào
                                fill = sl if op >= sl else op
                                p = (fill - entry) * CONTRACT * lot
                                pnls[nt] = p; nt += 1; realized += p; pos = 0
                        else:
                            entry = op - half; sl = entry + atrd; pos = -1
                            if hi >= sl:
                                fill = sl if op <= sl else op
                                p = (entry - fill) * CONTRACT * lot
                                pnls[nt] = p; nt += 1; realized += p; pos = 0

        # === D. Equity mark-to-market cuối nến i -> theo dõi drawdown ===
        floating = 0.0
        if pos == 1:
            floating = (close[i] - entry) * CONTRACT * lot
        elif pos == -1:
            floating = (entry - close[i]) * CONTRACT * lot
        eq = start_balance + realized + floating
        if eq > peak_eq: peak_eq = eq
        dd = peak_eq - eq
        if dd > max_dd: max_dd = dd
        if peak_eq > 0:
            ddp = dd / peak_eq * 100.0
            if ddp > max_dd_pct: max_dd_pct = ddp

    # đóng vị thế còn mở ở cuối kỳ (mark-to-market tại close cuối)
    if pos != 0:
        last = end_idx - 1
        if pos == 1: p = (close[last] - entry) * CONTRACT * lot
        else:        p = (entry - close[last]) * CONTRACT * lot
        pnls[nt] = p; nt += 1; realized += p

    return pnls[:nt], max_dd, max_dd_pct


# --------------------------------------------------------------- high-level wrappers
def backtest(arr, cache, params, start_idx, end_idx, start_balance=2000.0):
    """Chạy backtest 1 bộ params trên [start_idx, end_idx). Trả về (pnls, max_dd_abs, max_dd_pct)."""
    tenkan = cache.donchian(params["tenkan"])
    kijun  = cache.donchian(params["kijun"])
    spanB_raw = cache.donchian(params["spanB"])
    disp = int(params["kijun"])                 # displacement = Kijun (chuẩn Ichimoku)
    atr_sl    = cache.atr(params["sl_period"])
    atr_trail = cache.atr(params["trail_period"])

    warmup = max(params["tenkan"], params["kijun"], params["spanB"],
                 params["sl_period"], params["trail_period"]) + disp + 3
    eff_start = max(start_idx, warmup)
    if eff_start >= end_idx:
        return np.empty(0, dtype=np.float64), 0.0, 0.0

    return _run(arr["open"], arr["high"], arr["low"], arr["close"], arr["spread"],
                tenkan, kijun, spanB_raw, atr_sl, atr_trail, disp,
                float(params["sl_mult"]), float(params["trail_mult"]),
                int(params["require_color"]), int(params["use_ichi_exit"]),
                float(params["risk_usd"]), eff_start, end_idx, float(start_balance))


def metrics(pnls, start_balance, max_dd_abs=None, max_dd_pct=None):
    """Tính chỉ số hiệu suất. Nếu max_dd_* = None -> tính DD trên equity theo lệnh đã đóng."""
    n = len(pnls)
    if n == 0:
        return dict(trades=0, net=0.0, gross_profit=0.0, gross_loss=0.0,
                    profit_factor=0.0, max_dd_abs=0.0, max_dd_pct=0.0,
                    recovery_factor=0.0, win_rate=0.0, end_balance=start_balance)
    if max_dd_abs is None:
        equity = start_balance + np.cumsum(pnls)
        peak = np.maximum.accumulate(np.concatenate(([start_balance], equity)))[1:]
        dd = peak - equity
        max_dd_abs = float(dd.max())
        max_dd_pct = float((dd / peak).max() * 100.0)
    net = float(pnls.sum())
    gp = float(pnls[pnls > 0].sum()); gl = float(-pnls[pnls < 0].sum())
    pf = gp / gl if gl > 0 else (float("inf") if gp > 0 else 0.0)
    rf = net / max(max_dd_abs, 1.0)
    wr = float((pnls > 0).mean() * 100.0)
    return dict(trades=n, net=net, gross_profit=gp, gross_loss=gl,
                profit_factor=pf, max_dd_abs=float(max_dd_abs), max_dd_pct=float(max_dd_pct),
                recovery_factor=rf, win_rate=wr, end_balance=start_balance + net)
