"""
Backtester v2 — khop DUNG logic EA cua nguoi dung (Ichimoku_ATR_EA.mq5):

- Trail1 (fast) & Trail2 (slow) = ATR Trailing Stop kieu ceyhun, tinh de quy (ComputeTrail).
- Entry LONG : Trail1 cat len Trail2 (buySig) + gia tren may Kumo (loc).
  Entry SHORT: Trail1 cat xuong Trail2 (sellSig) + gia duoi may.
- SL: mode 0 = Slow Trail (Trail2) luc vao | 1 = ATR | 2 = Kijun. Ep khoang cach toi thieu.
- TP: tp_rr * R (0 = gong thuan). 1R = rui ro co dinh (sizing dong).
- Quan ly: thoat khi tin hieu ATR nguoc (exit_opp), thoat khi gia pha may (exit_cloud),
  trailing SL (trail_mode>0). Cho phep dao lenh trong cung nen (giong EA).
- Tin hieu tinh tren NEN DA DONG (k = i-1), khop lenh tai open[i] (khong nhin truoc).
- Drawdown mark-to-market (gom lo/lai noi).

Dung lai phan nap data / cache chi bao / metrics tu backtester.py.
"""
import numpy as np
from numba import njit
import backtester as base

# tai su dung tien ich
load_data       = base.load_data
to_arrays       = base.to_arrays
year_bounds     = base.year_bounds
IndicatorCache  = base.IndicatorCache
metrics         = base.metrics

CONTRACT = 100000.0     # 1.0 lot EURUSD; PnL(USD) = (exit-entry)*CONTRACT*lot
POINT    = 0.00001
LOT_STEP = 0.01
MIN_LOT  = 0.01


@njit(cache=True, fastmath=True)
def _ct(c, cp, prev, sl):
    """1 buoc ATR Trailing Stop (ceyhun)."""
    if c > prev and cp > prev:
        v = c - sl
        return prev if prev > v else v        # max(prev, c-sl)
    if c < prev and cp < prev:
        v = c + sl
        return prev if prev < v else v        # min(prev, c+sl)
    if c > prev:
        return c - sl
    return c + sl


@njit(cache=True, fastmath=True)
def _run_v2(open_, high, low, close, spread,
            tenkan, kijun, spanB_raw, atr1, atr2, adx, disp,
            fast_mult, slow_mult, use_cloud, require_color, use_adx, adx_min,
            sl_mode, sl_atr_mult, min_sl_dist, tp_rr, trail_mode,
            exit_opp, exit_cloud, risk, commission, start_balance,
            seed_start, start_idx, end_idx):

    cap = 2 * (end_idx - start_idx) + 8
    if cap < 1:
        cap = 1
    pnls = np.empty(cap, dtype=np.float64)
    nt = 0

    pos = 0; entry = 0.0; sl = 0.0; tp = 0.0; lot = 0.0
    realized = 0.0
    peak_eq = start_balance
    max_dd = 0.0
    max_dd_pct = 0.0

    t1 = 0.0; t2 = 0.0          # Trail tai bar (k-1)
    first = True
    k = seed_start

    while k <= end_idx - 2:
        a1 = atr1[k]; a2 = atr2[k]
        ck = close[k]; ckm1 = close[k - 1]
        if np.isnan(a1) or np.isnan(a2) or np.isnan(ck) or np.isnan(ckm1):
            k += 1
            continue

        old_t1 = 0.0 if first else t1
        old_t2 = 0.0 if first else t2
        first = False
        new_t1 = _ct(ck, ckm1, old_t1, fast_mult * a1)
        new_t2 = _ct(ck, ckm1, old_t2, slow_mult * a2)

        i = k + 1
        if i >= start_idx and i < end_idx:
            cross_up = (old_t1 <= old_t2) and (new_t1 > new_t2)
            cross_dn = (old_t1 >= old_t2) and (new_t1 < new_t2)

            jd = k - disp
            cloud_valid = False
            sa = 0.0; sb = 0.0; ctop = 0.0; cbot = 0.0
            if jd >= 1 and not np.isnan(tenkan[jd]) and not np.isnan(kijun[jd]) \
               and not np.isnan(spanB_raw[jd]):
                sa = (tenkan[jd] + kijun[jd]) * 0.5
                sb = spanB_raw[jd]
                ctop = sa if sa > sb else sb
                cbot = sa if sa < sb else sb
                cloud_valid = True
            kj_line = kijun[k]
            op = open_[i]; hi = high[i]; lo = low[i]
            half = spread[i] * 0.5

            # === 1. thoat khi tin hieu ATR nguoc ===
            if pos != 0 and exit_opp == 1:
                if pos == 1 and cross_dn:
                    p = ((op - half) - entry) * CONTRACT * lot - commission * lot
                    pnls[nt] = p; nt += 1; realized += p; pos = 0
                elif pos == -1 and cross_up:
                    p = (entry - (op + half)) * CONTRACT * lot - commission * lot
                    pnls[nt] = p; nt += 1; realized += p; pos = 0

            # === 2. thoat khi pha may ===
            if pos != 0 and exit_cloud == 1 and cloud_valid:
                if pos == 1 and ck < cbot:
                    p = ((op - half) - entry) * CONTRACT * lot - commission * lot
                    pnls[nt] = p; nt += 1; realized += p; pos = 0
                elif pos == -1 and ck > ctop:
                    p = (entry - (op + half)) * CONTRACT * lot - commission * lot
                    pnls[nt] = p; nt += 1; realized += p; pos = 0

            # === 3. trailing SL (chi khi trail_mode>0) ===
            if pos != 0 and trail_mode > 0:
                line = new_t2 if trail_mode == 1 else (new_t1 if trail_mode == 2 else kj_line)
                if pos == 1:
                    if line > sl and line < op:
                        sl = line
                else:
                    if (sl == 0.0 or line < sl) and line > op:
                        sl = line

            # === 4. vao lenh moi (neu flat) — quyet dinh tai open[i] ===
            if pos == 0:
                long_ok = cross_up
                short_ok = cross_dn
                if use_cloud == 1:
                    if not cloud_valid:
                        long_ok = False; short_ok = False
                    else:
                        long_ok = long_ok and (ck > ctop)
                        short_ok = short_ok and (ck < cbot)
                if require_color == 1:
                    if cloud_valid:
                        long_ok = long_ok and (sa > sb)
                        short_ok = short_ok and (sa < sb)
                    else:
                        long_ok = False; short_ok = False
                if use_adx == 1:                       # loc che do thi truong: chi trade khi co trend
                    av = adx[k]
                    if np.isnan(av) or av < adx_min:
                        long_ok = False; short_ok = False

                if long_ok or short_ok:
                    is_long = long_ok
                    e = (op + half) if is_long else (op - half)
                    if sl_mode == 0:
                        slp = new_t2
                    elif sl_mode == 1:
                        slp = (e - sl_atr_mult * a2) if is_long else (e + sl_atr_mult * a2)
                    else:
                        slp = kj_line
                    if is_long:
                        if slp >= e - min_sl_dist:
                            slp = e - min_sl_dist
                    else:
                        if slp <= e + min_sl_dist:
                            slp = e + min_sl_dist
                    sl_dist = (e - slp) if is_long else (slp - e)
                    if sl_dist > 0:
                        loss_per_lot = sl_dist * CONTRACT + commission
                        lt = np.floor((risk / loss_per_lot) / LOT_STEP) * LOT_STEP
                        if lt >= MIN_LOT:
                            entry = e; lot = lt; pos = 1 if is_long else -1; sl = slp
                            tp = 0.0
                            if tp_rr > 0.0:
                                tp = (e + tp_rr * sl_dist) if is_long else (e - tp_rr * sl_dist)

            # === 5. SL/TP trong nen i (vi the dang mo; co xu ly gap open) ===
            if pos == 1:
                if op <= sl:
                    p = (op - entry) * CONTRACT * lot - commission * lot
                    pnls[nt] = p; nt += 1; realized += p; pos = 0
                elif tp > 0.0 and op >= tp:
                    p = (op - entry) * CONTRACT * lot - commission * lot
                    pnls[nt] = p; nt += 1; realized += p; pos = 0
                elif lo <= sl:
                    p = (sl - entry) * CONTRACT * lot - commission * lot
                    pnls[nt] = p; nt += 1; realized += p; pos = 0
                elif tp > 0.0 and hi >= tp:
                    p = (tp - entry) * CONTRACT * lot - commission * lot
                    pnls[nt] = p; nt += 1; realized += p; pos = 0
            elif pos == -1:
                if op >= sl:
                    p = (entry - op) * CONTRACT * lot - commission * lot
                    pnls[nt] = p; nt += 1; realized += p; pos = 0
                elif tp > 0.0 and op <= tp:
                    p = (entry - op) * CONTRACT * lot - commission * lot
                    pnls[nt] = p; nt += 1; realized += p; pos = 0
                elif hi >= sl:
                    p = (entry - sl) * CONTRACT * lot - commission * lot
                    pnls[nt] = p; nt += 1; realized += p; pos = 0
                elif tp > 0.0 and lo <= tp:
                    p = (entry - tp) * CONTRACT * lot - commission * lot
                    pnls[nt] = p; nt += 1; realized += p; pos = 0

            # === 6. equity mark-to-market -> drawdown ===
            floating = 0.0
            if pos == 1:
                floating = (close[i] - entry) * CONTRACT * lot
            elif pos == -1:
                floating = (entry - close[i]) * CONTRACT * lot
            eq = start_balance + realized + floating
            if eq > peak_eq:
                peak_eq = eq
            dd = peak_eq - eq
            if dd > max_dd:
                max_dd = dd
            if peak_eq > 0:
                ddp = dd / peak_eq * 100.0
                if ddp > max_dd_pct:
                    max_dd_pct = ddp

        t1 = new_t1; t2 = new_t2
        k += 1

    # dong vi the con mo cuoi ky
    if pos != 0:
        last = end_idx - 1
        if pos == 1:
            p = (close[last] - entry) * CONTRACT * lot - commission * lot
        else:
            p = (entry - close[last]) * CONTRACT * lot - commission * lot
        pnls[nt] = p; nt += 1

    return pnls[:nt], max_dd, max_dd_pct


def backtest_v2(arr, cache, p, start_idx, end_idx, start_balance):
    """Chay backtest 1 bo params tren [start_idx, end_idx). Tra ve (pnls, dd_abs, dd_pct)."""
    tenkan = cache.donchian(int(p["tenkan"]))
    kijun  = cache.donchian(int(p["kijun"]))
    spanB  = cache.donchian(int(p["spanB"]))
    disp   = int(p["displacement"])
    atr1   = cache.atr(int(p["fast_period"]))
    atr2   = cache.atr(int(p["slow_period"]))
    adx    = cache.adx(int(p.get("adx_period", 14)))

    warmup = max(int(p["tenkan"]), int(p["kijun"]), int(p["spanB"])) + disp + 3
    eff_start = max(start_idx, warmup)
    atr_warm = max(int(p["fast_period"]), int(p["slow_period"])) + 2
    seed_start = max(atr_warm, eff_start - 1000)
    if seed_start < 1:
        seed_start = 1
    if eff_start >= end_idx or seed_start >= end_idx - 1:
        return np.empty(0, dtype=np.float64), 0.0, 0.0

    pip = 10 * POINT
    min_sl_dist = p["min_sl_pips"] * pip

    return _run_v2(arr["open"], arr["high"], arr["low"], arr["close"], arr["spread"],
                   tenkan, kijun, spanB, atr1, atr2, adx, disp,
                   float(p["fast_mult"]), float(p["slow_mult"]),
                   int(p["use_cloud"]), int(p["require_color"]),
                   int(p.get("use_adx", 0)), float(p.get("adx_min", 0.0)),
                   int(p["sl_mode"]), float(p["sl_atr_mult"]), float(min_sl_dist),
                   float(p["tp_rr"]), int(p["trail_mode"]),
                   int(p["exit_opp"]), int(p["exit_cloud"]),
                   float(p["risk"]), float(p["commission"]), float(start_balance),
                   seed_start, eff_start, end_idx)
