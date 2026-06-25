"""
Backtester v3 — chien luoc Ichimoku TK-cross theo dung spec nguoi dung:

- Ichimoku KHOA 9/26/52 (displacement 26). Bo loc mau may.
- Entry LONG : Tenkan cat len Kijun + gia tren may + gia tren Kijun. SHORT doi xung.
- SL ky thuat = sl_mult * ATR(sl_atr_period).
- 1R = 20 USD DA gom spread:  Lot = 20 / ((SL_dist + spread) * CONTRACT).
  Lo khi dinh SL = (SL_dist + spread) * CONTRACT * Lot = dung 20 USD.
- TP cung theo R-multiple: TP_dist = tp_mult * SL_dist  (use_tp=1).
  Bien the "gong loi": use_tp=0 -> khong TP, thoat theo Slow Trail.
- Trailing: ATR(trail_period) * trail_mult kieu ratchet.
- use_ichi_exit: thoat khi gia dong cua quay ve duoi Kijun / vao may.
- Tin hieu tren nen da dong (j=i-1), khop tai open[i] (khong nhin truoc).
- Spread tinh nhu chi phi round-trip (tru vao PnL moi lenh). Drawdown mark-to-market.
"""
import numpy as np
from numba import njit
import backtester as base

load_data      = base.load_data
to_arrays      = base.to_arrays
year_bounds    = base.year_bounds
IndicatorCache = base.IndicatorCache

CONTRACT = 100000.0     # 1 lot EURUSD; gia tri 1 pip(0.0001)/1 lot = 10 USD
POINT    = 0.00001
LOT_STEP = 0.01
MIN_LOT  = 0.01


@njit(cache=True, fastmath=True)
def _run_v3(open_, high, low, close, spread,
            tenkan, kijun, spanB_raw, atr_sl, atr_tr, disp,
            sl_mult, tp_mult, trail_mult, use_tp, use_ichi_exit,
            risk, start_balance, start_idx, end_idx):
    cap = end_idx - start_idx + 2
    pnls = np.empty(cap if cap > 0 else 1, dtype=np.float64)
    nt = 0
    pos = 0; entry = 0.0; stop = 0.0; tp = 0.0; lot = 0.0; spr_e = 0.0
    realized = 0.0; peak = start_balance; max_dd = 0.0; max_dd_pct = 0.0

    for i in range(start_idx, end_idx):
        j = i - 1; jd = j - disp
        if jd < 1:
            continue
        tk = tenkan[j]; kj = kijun[j]; tkp = tenkan[j - 1]; kjp = kijun[j - 1]
        ta = tenkan[jd]; ka = kijun[jd]; sbv = spanB_raw[jd]
        asl = atr_sl[j]; atr_ = atr_tr[j]
        if (np.isnan(tk) or np.isnan(kj) or np.isnan(tkp) or np.isnan(kjp) or np.isnan(ta)
                or np.isnan(ka) or np.isnan(sbv) or np.isnan(asl) or np.isnan(atr_)):
            continue
        sa = (ta + ka) * 0.5; sb = sbv
        ctop = sa if sa > sb else sb
        cbot = sa if sa < sb else sb
        op = open_[i]; hi = high[i]; lo = low[i]; spr = spread[i]; cl = close[j]

        # --- quan ly vi the dang co ---
        if pos != 0:
            ex = False
            if use_ichi_exit == 1:
                if pos == 1 and (cl < kj or cl < cbot): ex = True
                elif pos == -1 and (cl > kj or cl > ctop): ex = True
            if ex:
                p = ((op - entry) if pos == 1 else (entry - op)) * CONTRACT * lot - spr_e * CONTRACT * lot
                pnls[nt] = p; nt += 1; realized += p; pos = 0
            else:                                   # trailing ratchet tu close[j]
                if pos == 1:
                    ns = cl - trail_mult * atr_
                    if ns > stop: stop = ns
                else:
                    ns = cl + trail_mult * atr_
                    if ns < stop: stop = ns

        # --- vao lenh moi (flat) tin hieu tai j ---
        if pos == 0:
            cu = (tkp <= kjp) and (tk > kj)
            cd = (tkp >= kjp) and (tk < kj)
            long_ok = cu and (cl > ctop) and (cl > kj)
            short_ok = cd and (cl < cbot) and (cl < kj)
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

        # --- SL/TP trong nen i (uu tien SL; co xu ly gap open) ---
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

        # --- equity mark-to-market -> drawdown ---
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

    if pos != 0:
        last = end_idx - 1
        p = ((close[last] - entry) if pos == 1 else (entry - close[last])) * CONTRACT * lot - spr_e * CONTRACT * lot
        pnls[nt] = p; nt += 1

    return pnls[:nt], max_dd, max_dd_pct


def backtest_v3(arr, cache, p, start_idx, end_idx, start_balance):
    tenkan = cache.donchian(9)
    kijun  = cache.donchian(26)
    spanB  = cache.donchian(52)
    disp   = 26
    atr_sl = cache.atr(int(p["sl_atr_period"]))
    atr_tr = cache.atr(int(p["trail_period"]))
    warmup = 52 + disp + 3
    eff_start = max(start_idx, warmup)
    if eff_start >= end_idx:
        return np.empty(0, dtype=np.float64), 0.0, 0.0
    return _run_v3(arr["open"], arr["high"], arr["low"], arr["close"], arr["spread"],
                   tenkan, kijun, spanB, atr_sl, atr_tr, disp,
                   float(p["sl_mult"]), float(p.get("tp_mult", 0.0)), float(p["trail_mult"]),
                   int(p.get("use_tp", 1)), int(p["use_ichi_exit"]),
                   float(p.get("risk", 20.0)), float(start_balance), eff_start, end_idx)


def metrics_v3(pnls, max_dd_abs, max_dd_pct, period_years, risk=20.0):
    """Annualized Sharpe theo R-multiple (Van Tharp): mean(R)/std(R) * sqrt(trades/nam)."""
    n = len(pnls)
    if n == 0:
        return dict(trades=0, net=0.0, profit_factor=0.0, max_dd_abs=0.0, max_dd_pct=0.0,
                    sharpe=0.0, win_rate=0.0)
    R = pnls / risk
    net = float(pnls.sum())
    gp = float(pnls[pnls > 0].sum()); gl = float(-pnls[pnls < 0].sum())
    pf = gp / gl if gl > 0 else (float("inf") if gp > 0 else 0.0)
    sd = float(R.std(ddof=1)) if n > 1 else 0.0
    if sd > 0 and period_years > 0:
        sharpe = (float(R.mean()) / sd) * np.sqrt(n / period_years)
    else:
        sharpe = 0.0
    return dict(trades=n, net=net, profit_factor=pf,
                max_dd_abs=float(max_dd_abs), max_dd_pct=float(max_dd_pct),
                sharpe=float(sharpe), win_rate=float((pnls > 0).mean() * 100.0))
