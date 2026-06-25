"""
Backtester v5 — THIET KE EXIT theo triet ly: lo gioi han, loi co khong gian chay,
phan phoi R co expectancy duong.  Entry = ATR-cross (EA goc, khoa fast5/0.5 slow10/3) + loc may.

Co che exit (scale-out):
  1. Initial SL = sl_mult * ATR(sl_atr_period)         -> GIOI HAN LO (1R = 20$ gom spread).
  2. Breakeven: khi close >= +be_trigger R, doi SL ve hoa von (entry + spread) -> chan TRA LAI lai.
  3. Partial TP: chot partial_frac khoi luong tai +tp1_mult R                   -> KHOA mot phan loi.
  4. Runner: phan con lai gong theo trailing ATR(trail_period)*trail_mult       -> cho LOI CHAY (duoi to).
  (khong TP cung cho runner)

Sizing: Lot = 20 / ((SL_dist + spread) * CONTRACT). Spread tru theo ty le khoi luong dong.
Tin hieu tren nen dong (k=i-1), khop open[i]. Drawdown mark-to-market. R-level theo sl_dist ky thuat.
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
    return c - sl if c > prev else c + sl


@njit(cache=True, fastmath=True)
def _run_v5(open_, high, low, close, spread, tenkan, kijun, spanB_raw,
            atr1, atr2, atr_sl, atr_tr, disp,
            fast_mult, slow_mult, sl_mult, be_trigger, tp1_mult, partial_frac, trail_mult,
            risk, start_balance, seed_start, start_idx, end_idx):
    cap = 2 * (end_idx - start_idx) + 8
    pnls = np.empty(cap if cap > 0 else 1, dtype=np.float64)
    nt = 0
    pos = 0; entry = 0.0; stop = 0.0; sl_dist = 0.0; lot0 = 0.0; lot_rem = 0.0
    spr_e = 0.0; be_done = False; tp1_done = False; trade_pnl = 0.0
    realized = 0.0; peak = start_balance; max_dd = 0.0; max_dd_pct = 0.0
    t1 = 0.0; t2 = 0.0; first = True
    k = seed_start

    while k <= end_idx - 2:
        a1 = atr1[k]; a2 = atr2[k]; ck = close[k]; ckm1 = close[k - 1]
        if np.isnan(a1) or np.isnan(a2) or np.isnan(ck) or np.isnan(ckm1):
            k += 1; continue
        ot1 = 0.0 if first else t1; ot2 = 0.0 if first else t2; first = False
        nt1 = _ct(ck, ckm1, ot1, fast_mult * a1)
        nt2 = _ct(ck, ckm1, ot2, slow_mult * a2)
        i = k + 1
        if i >= start_idx and i < end_idx:
            cu = (ot1 <= ot2) and (nt1 > nt2)
            cd = (ot1 >= ot2) and (nt1 < nt2)
            jd = k - disp
            cok = False; ctop = 0.0; cbot = 0.0
            if jd >= 1 and not np.isnan(tenkan[jd]) and not np.isnan(kijun[jd]) and not np.isnan(spanB_raw[jd]):
                sa = (tenkan[jd] + kijun[jd]) * 0.5; sb = spanB_raw[jd]
                ctop = sa if sa > sb else sb; cbot = sa if sa < sb else sb; cok = True
            asl = atr_sl[k]; atrt = atr_tr[k]
            op = open_[i]; hi = high[i]; lo = low[i]; spr = spread[i]
            vmm = (not np.isnan(asl)) and (not np.isnan(atrt))

            if pos != 0 and vmm:
                # breakeven tu close da xac nhan
                if not be_done:
                    if pos == 1 and ck >= entry + be_trigger * sl_dist:
                        be = entry + spr_e
                        if be > stop: stop = be
                        be_done = True
                    elif pos == -1 and ck <= entry - be_trigger * sl_dist:
                        be = entry - spr_e
                        if be < stop: stop = be
                        be_done = True
                # trailing runner
                if pos == 1:
                    ns = ck - trail_mult * atrt
                    if ns > stop: stop = ns
                else:
                    ns = ck + trail_mult * atrt
                    if ns < stop: stop = ns

            # --- thoat trong nen i ---
            if pos == 1:
                if op <= stop:                                   # gap thung stop
                    p = (op - entry) * CONTRACT * lot_rem - spr_e * CONTRACT * lot_rem
                    trade_pnl += p; realized += p; pnls[nt] = trade_pnl; nt += 1; pos = 0
                else:
                    if partial_frac > 0.0 and (not tp1_done):
                        lvl = entry + tp1_mult * sl_dist
                        if hi >= lvl:
                            fl = partial_frac * lot0
                            p = (lvl - entry) * CONTRACT * fl - spr_e * CONTRACT * fl
                            trade_pnl += p; realized += p; lot_rem -= fl; tp1_done = True
                    if pos == 1 and lo <= stop:
                        p = (stop - entry) * CONTRACT * lot_rem - spr_e * CONTRACT * lot_rem
                        trade_pnl += p; realized += p; pnls[nt] = trade_pnl; nt += 1; pos = 0
            elif pos == -1:
                if op >= stop:
                    p = (entry - op) * CONTRACT * lot_rem - spr_e * CONTRACT * lot_rem
                    trade_pnl += p; realized += p; pnls[nt] = trade_pnl; nt += 1; pos = 0
                else:
                    if partial_frac > 0.0 and (not tp1_done):
                        lvl = entry - tp1_mult * sl_dist
                        if lo <= lvl:
                            fl = partial_frac * lot0
                            p = (entry - lvl) * CONTRACT * fl - spr_e * CONTRACT * fl
                            trade_pnl += p; realized += p; lot_rem -= fl; tp1_done = True
                    if pos == -1 and hi >= stop:
                        p = (entry - stop) * CONTRACT * lot_rem - spr_e * CONTRACT * lot_rem
                        trade_pnl += p; realized += p; pnls[nt] = trade_pnl; nt += 1; pos = 0

            # --- vao lenh moi ---
            if pos == 0 and vmm and cok:
                long_ok = cu and (ck > ctop); short_ok = cd and (ck < cbot)
                if long_ok or short_ok:
                    sld = sl_mult * asl
                    if sld > 0:
                        lt = np.floor((risk / ((sld + spr) * CONTRACT)) / LOT_STEP) * LOT_STEP
                        if lt >= MIN_LOT:
                            spr_e = spr; sl_dist = sld; lot0 = lt; lot_rem = lt
                            be_done = False; tp1_done = False; trade_pnl = 0.0; entry = op
                            if long_ok: pos = 1; stop = op - sld
                            else: pos = -1; stop = op + sld

            # --- equity MtM ---
            fl_ = 0.0
            if pos == 1: fl_ = (close[i] - entry) * CONTRACT * lot_rem
            elif pos == -1: fl_ = (entry - close[i]) * CONTRACT * lot_rem
            eq = start_balance + realized + fl_
            if eq > peak: peak = eq
            dd = peak - eq
            if dd > max_dd: max_dd = dd
            if peak > 0:
                ddp = dd / peak * 100.0
                if ddp > max_dd_pct: max_dd_pct = ddp
        t1 = nt1; t2 = nt2; k += 1

    if pos != 0:
        last = end_idx - 1
        p = ((close[last] - entry) if pos == 1 else (entry - close[last])) * CONTRACT * lot_rem - spr_e * CONTRACT * lot_rem
        trade_pnl += p; pnls[nt] = trade_pnl; nt += 1
    return pnls[:nt], max_dd, max_dd_pct


def backtest_v5(arr, cache, p, start_idx, end_idx, start_balance):
    tenkan = cache.donchian(9); kijun = cache.donchian(26); spanB = cache.donchian(52); disp = 26
    atr1 = cache.atr(int(p["fast_period"])); atr2 = cache.atr(int(p["slow_period"]))
    atr_sl = cache.atr(int(p["sl_atr_period"])); atr_tr = cache.atr(int(p["trail_period"]))
    warmup = 52 + disp + 3
    eff_start = max(start_idx, warmup)
    aw = max(int(p["fast_period"]), int(p["slow_period"]), int(p["sl_atr_period"]), int(p["trail_period"])) + 2
    seed_start = max(aw, eff_start - 1000)
    if seed_start < 1: seed_start = 1
    if eff_start >= end_idx or seed_start >= end_idx - 1:
        return np.empty(0, dtype=np.float64), 0.0, 0.0
    return _run_v5(arr["open"], arr["high"], arr["low"], arr["close"], arr["spread"],
                   tenkan, kijun, spanB, atr1, atr2, atr_sl, atr_tr, disp,
                   float(p["fast_mult"]), float(p["slow_mult"]), float(p["sl_mult"]),
                   float(p["be_trigger"]), float(p["tp1_mult"]), float(p["partial_frac"]),
                   float(p["trail_mult"]), float(p.get("risk", 20.0)), float(start_balance),
                   seed_start, eff_start, end_idx)
