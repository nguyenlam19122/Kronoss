"""
Backtester v4 — ENTRY = ATR-cross cua EA goc (ceyhun Trail1xTrail2) + loc may,
ghep voi khung quan ly von/exit cua v3 (de so sanh cong bang voi TK-cross).

- Entry signal: Trail1 (fast ATR) cat Trail2 (slow ATR), tinh de quy nhu ceyhun.
  Entry ATR-cross KHOA o mac dinh ceyhun: fast 5/0.5, slow 10/3 (giong cach v3 khoa Ichimoku).
  Loc: chi LONG khi gia tren may Kumo, SHORT khi duoi may (khong loc mau).
- Quan ly von giong v3: SL = sl_mult*ATR(sl_atr_period); 1R=20$ gom spread;
  Lot=20/((SL_dist+spread)*CONTRACT); TP cung = tp_mult*SL_dist (use_tp=1) hoac gong (0);
  trailing = trail_mult*ATR(trail_period) ratchet; use_ichi_exit.
- Khong nhin truoc (tin hieu tai nen dong k=i-1, khop open[i]). Drawdown mark-to-market.
"""
import numpy as np
from numba import njit
import backtester as base

load_data = base.load_data; to_arrays = base.to_arrays
year_bounds = base.year_bounds; IndicatorCache = base.IndicatorCache

CONTRACT = 100000.0; POINT = 0.00001; LOT_STEP = 0.01; MIN_LOT = 0.01


@njit(cache=True, fastmath=True)
def _ct(c, cp, prev, sl):
    if c > prev and cp > prev:
        v = c - sl; return prev if prev > v else v
    if c < prev and cp < prev:
        v = c + sl; return prev if prev < v else v
    if c > prev:
        return c - sl
    return c + sl


@njit(cache=True, fastmath=True)
def _run_v4(open_, high, low, close, spread,
            tenkan, kijun, spanB_raw, atr1, atr2, atr_sl, atr_tr, disp,
            fast_mult, slow_mult, sl_mult, tp_mult, trail_mult, use_tp, use_ichi_exit,
            risk, start_balance, seed_start, start_idx, end_idx):
    cap = 2 * (end_idx - start_idx) + 8
    pnls = np.empty(cap if cap > 0 else 1, dtype=np.float64)
    nt = 0
    pos = 0; entry = 0.0; stop = 0.0; tp = 0.0; lot = 0.0; spr_e = 0.0
    realized = 0.0; peak = start_balance; max_dd = 0.0; max_dd_pct = 0.0
    t1 = 0.0; t2 = 0.0; first = True
    k = seed_start

    while k <= end_idx - 2:
        a1 = atr1[k]; a2 = atr2[k]; ck = close[k]; ckm1 = close[k - 1]
        if np.isnan(a1) or np.isnan(a2) or np.isnan(ck) or np.isnan(ckm1):
            k += 1; continue
        ot1 = 0.0 if first else t1
        ot2 = 0.0 if first else t2
        first = False
        nt1 = _ct(ck, ckm1, ot1, fast_mult * a1)
        nt2 = _ct(ck, ckm1, ot2, slow_mult * a2)

        i = k + 1
        if i >= start_idx and i < end_idx:
            cu = (ot1 <= ot2) and (nt1 > nt2)
            cd = (ot1 >= ot2) and (nt1 < nt2)
            jd = k - disp
            cloud_ok = False; sa = 0.0; sb = 0.0; ctop = 0.0; cbot = 0.0
            if jd >= 1 and not np.isnan(tenkan[jd]) and not np.isnan(kijun[jd]) and not np.isnan(spanB_raw[jd]):
                sa = (tenkan[jd] + kijun[jd]) * 0.5; sb = spanB_raw[jd]
                ctop = sa if sa > sb else sb; cbot = sa if sa < sb else sb
                cloud_ok = True
            kj = kijun[k]
            asl = atr_sl[k]; atr_ = atr_tr[k]
            op = open_[i]; hi = high[i]; lo = low[i]; spr = spread[i]
            valid_mm = (not np.isnan(asl)) and (not np.isnan(atr_))

            # --- quan ly vi the ---
            if pos != 0:
                ex = False
                if use_ichi_exit == 1 and cloud_ok:
                    if pos == 1 and (ck < kj or ck < cbot): ex = True
                    elif pos == -1 and (ck > kj or ck > ctop): ex = True
                if ex:
                    p = ((op - entry) if pos == 1 else (entry - op)) * CONTRACT * lot - spr_e * CONTRACT * lot
                    pnls[nt] = p; nt += 1; realized += p; pos = 0
                elif valid_mm:
                    if pos == 1:
                        ns = ck - trail_mult * atr_
                        if ns > stop: stop = ns
                    else:
                        ns = ck + trail_mult * atr_
                        if ns < stop: stop = ns

            # --- vao lenh moi ---
            if pos == 0 and valid_mm and cloud_ok:
                long_ok = cu and (ck > ctop)
                short_ok = cd and (ck < cbot)
                if long_ok or short_ok:
                    sl_dist = sl_mult * asl
                    if sl_dist > 0:
                        lot = np.floor((risk / ((sl_dist + spr) * CONTRACT)) / LOT_STEP) * LOT_STEP
                        if lot >= MIN_LOT:
                            spr_e = spr
                            if long_ok:
                                pos = 1; entry = op; stop = op - sl_dist
                                tp = op + tp_mult * sl_dist if use_tp == 1 else 0.0
                            else:
                                pos = -1; entry = op; stop = op + sl_dist
                                tp = op - tp_mult * sl_dist if use_tp == 1 else 0.0

            # --- SL/TP trong nen i ---
            if pos == 1:
                if lo <= stop:
                    fill = stop if op >= stop else op
                    p = (fill - entry) * CONTRACT * lot - spr_e * CONTRACT * lot
                    pnls[nt] = p; nt += 1; realized += p; pos = 0
                elif use_tp == 1 and tp > 0.0 and hi >= tp:
                    fill = tp if op <= tp else op
                    p = (fill - entry) * CONTRACT * lot - spr_e * CONTRACT * lot
                    pnls[nt] = p; nt += 1; realized += p; pos = 0
            elif pos == -1:
                if hi >= stop:
                    fill = stop if op <= stop else op
                    p = (entry - fill) * CONTRACT * lot - spr_e * CONTRACT * lot
                    pnls[nt] = p; nt += 1; realized += p; pos = 0
                elif use_tp == 1 and tp > 0.0 and lo <= tp:
                    fill = tp if op >= tp else op
                    p = (entry - fill) * CONTRACT * lot - spr_e * CONTRACT * lot
                    pnls[nt] = p; nt += 1; realized += p; pos = 0

            # --- equity MtM ---
            floating = 0.0
            if pos == 1: floating = (close[i] - entry) * CONTRACT * lot
            elif pos == -1: floating = (entry - close[i]) * CONTRACT * lot
            eq = start_balance + realized + floating
            if eq > peak: peak = eq
            dd = peak - eq
            if dd > max_dd: max_dd = dd
            if peak > 0:
                ddp = dd / peak * 100.0
                if ddp > max_dd_pct: max_dd_pct = ddp

        t1 = nt1; t2 = nt2; k += 1

    if pos != 0:
        last = end_idx - 1
        p = ((close[last] - entry) if pos == 1 else (entry - close[last])) * CONTRACT * lot - spr_e * CONTRACT * lot
        pnls[nt] = p; nt += 1

    return pnls[:nt], max_dd, max_dd_pct


def backtest_v4(arr, cache, p, start_idx, end_idx, start_balance):
    tenkan = cache.donchian(9); kijun = cache.donchian(26); spanB = cache.donchian(52); disp = 26
    atr1 = cache.atr(int(p["fast_period"]))
    atr2 = cache.atr(int(p["slow_period"]))
    atr_sl = cache.atr(int(p["sl_atr_period"]))
    atr_tr = cache.atr(int(p["trail_period"]))
    warmup = 52 + disp + 3
    eff_start = max(start_idx, warmup)
    atr_warm = max(int(p["fast_period"]), int(p["slow_period"]), int(p["sl_atr_period"]), int(p["trail_period"])) + 2
    seed_start = max(atr_warm, eff_start - 1000)
    if seed_start < 1: seed_start = 1
    if eff_start >= end_idx or seed_start >= end_idx - 1:
        return np.empty(0, dtype=np.float64), 0.0, 0.0
    return _run_v4(arr["open"], arr["high"], arr["low"], arr["close"], arr["spread"],
                   tenkan, kijun, spanB, atr1, atr2, atr_sl, atr_tr, disp,
                   float(p["fast_mult"]), float(p["slow_mult"]), float(p["sl_mult"]),
                   float(p.get("tp_mult", 0.0)), float(p["trail_mult"]),
                   int(p.get("use_tp", 1)), int(p["use_ichi_exit"]),
                   float(p.get("risk", 20.0)), float(start_balance), seed_start, eff_start, end_idx)
