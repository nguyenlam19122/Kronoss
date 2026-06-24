#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Backtest cho chien luoc Ichimoku Kumo + ATR Trailing Stop (ceyhun).
Tai hien dung logic cua EA Ichimoku_ATR_EA.mq5.

DAC DIEM:
  * MO PHONG SPREAD THAT (cot <SPREAD> trong file CSV) + commission tuy chon
    -> "1R" da bao gom toan bo chi phi: khi dinh SL, lo dung 1R (= RISK_MONEY).
  * Nhieu kieu thoat lenh de GONG THEO XU HUONG (bo TP co dinh):
       TRAIL_MODE = none | slow | fast | kijun
       cong them EXIT_ON_CLOUD_BREAK / EXIT_ON_OPPOSITE.

Cach dung:
    python3 backtest.py <duong_dan_csv>

CSV (xuat tu MT5, tab-separated):
    <DATE> <TIME> <OPEN> <HIGH> <LOW> <CLOSE> <TICKVOL> <VOL> <SPREAD>
Gia tri lo/lai tinh theo R (1R = RISK_MONEY do, mac dinh 50$).
"""

import sys
import csv
from dataclasses import dataclass

# ----------------------- Tham so chien luoc -----------------------
TENKAN          = 9
KIJUN           = 26
SENKOU_B        = 52
DISPLACEMENT    = 26

FAST_ATR_PERIOD = 5
FAST_ATR_MULT   = 0.5
SLOW_ATR_PERIOD = 10
SLOW_ATR_MULT   = 3.0

USE_CLOUD_FILTER    = True    # gia phai ra ngoai may moi vao lenh
REQUIRE_CLOUD_COLOR = False   # mau may trung huong

# --- Cau hinh MAC DINH = toi uu+on dinh nhat tren data 2025 ("gong co tran 3R") ---
TAKE_PROFIT_RR      = 3.0     # TP theo R (3R toi uu; dat 0 = gong thuan, khong tran)
TRAIL_MODE          = "none"  # none|slow|fast|kijun. 'none' = khong doi SL bam theo
EXIT_ON_CLOUD_BREAK = False   # dong khi gia dong cua quay lai trong/qua may
EXIT_ON_OPPOSITE    = True    # dong khi co tin hieu ATR nguoc (= thoat som neu trend gay)

SL_MIN_PIPS         = 5.0     # khoang cach SL toi thieu (pips)
RISK_MONEY          = 50.0    # 1R = 50$ (DA bao gom chi phi)

# ----------------------- Chi phi giao dich ------------------------
POINT           = 0.00001     # EURUSD 5 chu so
PIP             = 0.0001
COMMISSION_PIPS = 0.0         # commission quy ra pip round-turn (vd 0.7 ~ 7$/lot)
# Spread lay tu cot <SPREAD> cua tung nen (don vi point).


@dataclass
class Bar:
    time: str
    o: float
    h: float
    l: float
    c: float
    spread: int = 0


def load_csv(path):
    bars = []
    with open(path, newline="") as f:
        reader = csv.reader(f, delimiter="\t")
        next(reader)  # header
        for row in reader:
            if len(row) < 6:
                continue
            spread = int(row[8]) if len(row) > 8 and row[8] != "" else 0
            bars.append(Bar(
                time=f"{row[0]} {row[1]}",
                o=float(row[2]), h=float(row[3]),
                l=float(row[4]), c=float(row[5]), spread=spread,
            ))
    return bars


# ----------------------- Chi bao ----------------------------------
def wilder_atr(bars, period):
    """ATR theo Wilder (RMA) - khop ta.atr cua Pine & iATR cua MT5."""
    n = len(bars)
    tr = [0.0] * n
    for i in range(n):
        if i == 0:
            tr[i] = bars[i].h - bars[i].l
        else:
            pc = bars[i - 1].c
            tr[i] = max(bars[i].h - bars[i].l, abs(bars[i].h - pc), abs(bars[i].l - pc))
    atr = [float("nan")] * n
    if n < period:
        return atr
    prev = sum(tr[:period]) / period
    atr[period - 1] = prev
    for i in range(period, n):
        prev = (prev * (period - 1) + tr[i]) / period
        atr[i] = prev
    return atr


def donchian_mid(bars, period, i):
    """(HH + LL)/2 cua `period` nen ket thuc tai index i."""
    if i - period + 1 < 0:
        return None
    hi = max(b.h for b in bars[i - period + 1: i + 1])
    lo = min(b.l for b in bars[i - period + 1: i + 1])
    return (hi + lo) / 2.0


def compute_trail(c, c_prev, prev, sl):
    if c > prev and c_prev > prev:
        return max(prev, c - sl)
    if c < prev and c_prev < prev:
        return min(prev, c + sl)
    if c > prev:
        return c - sl
    return c + sl


# ----------------------- Backtest ---------------------------------
@dataclass
class Trade:
    direction: str
    entry_i: int
    entry: float        # gia vao (da gom chi phi)
    sl: float
    tp: float
    risk: float
    exit_i: int = -1
    exit: float = 0.0
    reason: str = ""
    r: float = 0.0


def _finish(tr, i, price, reason):
    tr.exit_i = i
    tr.exit = price
    tr.reason = reason
    if tr.risk <= 0:
        tr.r = 0.0
    elif tr.direction == "long":
        tr.r = (price - tr.entry) / tr.risk
    else:
        tr.r = (tr.entry - price) / tr.risk


def run_backtest(bars):
    n = len(bars)
    atr_fast = wilder_atr(bars, FAST_ATR_PERIOD)
    atr_slow = wilder_atr(bars, SLOW_ATR_PERIOD)

    t1 = [0.0] * n   # Fast Trail
    t2 = [0.0] * n   # Slow Trail
    for i in range(n):
        af = atr_fast[i] if atr_fast[i] == atr_fast[i] else 0.0
        asw = atr_slow[i] if atr_slow[i] == atr_slow[i] else 0.0
        if i == 0:
            t1[i] = compute_trail(bars[i].c, bars[i].c, 0.0, FAST_ATR_MULT * af)
            t2[i] = compute_trail(bars[i].c, bars[i].c, 0.0, SLOW_ATR_MULT * asw)
        else:
            t1[i] = compute_trail(bars[i].c, bars[i - 1].c, t1[i - 1], FAST_ATR_MULT * af)
            t2[i] = compute_trail(bars[i].c, bars[i - 1].c, t2[i - 1], SLOW_ATR_MULT * asw)

    trades = []
    pos = None
    start = max(SENKOU_B + DISPLACEMENT, SLOW_ATR_PERIOD) + 2

    for i in range(start, n):
        sig = i - 1   # nen da dong -> tinh tin hieu, vao lenh tai open nen i
        buy_sig  = t1[sig - 1] <= t2[sig - 1] and t1[sig] >  t2[sig]
        sell_sig = t1[sig - 1] >= t2[sig - 1] and t1[sig] <  t2[sig]

        kij = donchian_mid(bars, KIJUN, sig)
        cs = sig - (DISPLACEMENT - 1)   # may "duoi" nen sig (khop EA & TradingView)
        spanA = spanB = None
        if cs >= 0:
            t = donchian_mid(bars, TENKAN, cs)
            k = donchian_mid(bars, KIJUN, cs)
            spanA = (t + k) / 2.0 if (t is not None and k is not None) else None
            spanB = donchian_mid(bars, SENKOU_B, cs)

        cloud_ok = spanA is not None and spanB is not None
        c1 = bars[sig].c
        cloud_top = max(spanA, spanB) if cloud_ok else None
        cloud_bot = min(spanA, spanB) if cloud_ok else None
        above = cloud_ok and c1 > cloud_top
        below = cloud_ok and c1 < cloud_bot
        bull  = cloud_ok and spanA > spanB
        bear  = cloud_ok and spanA < spanB

        long_ok  = buy_sig  and (not USE_CLOUD_FILTER or above) and (not REQUIRE_CLOUD_COLOR or bull)
        short_ok = sell_sig and (not USE_CLOUD_FILTER or below) and (not REQUIRE_CLOUD_COLOR or bear)

        # ---------------- quan ly lenh dang mo ----------------
        if pos is not None:
            o = bars[i].o
            # 1) thoat theo tin hieu (quyet dinh tren nen sig) -> khop tai open nen i
            sig_exit = False
            if EXIT_ON_OPPOSITE:
                if pos.direction == "long" and sell_sig:  sig_exit = True
                elif pos.direction == "short" and buy_sig: sig_exit = True
            if not sig_exit and EXIT_ON_CLOUD_BREAK and cloud_ok:
                if pos.direction == "long" and c1 < cloud_bot:  sig_exit = True
                elif pos.direction == "short" and c1 > cloud_top: sig_exit = True

            if sig_exit:
                _finish(pos, i, o, "EXIT")
                trades.append(pos); pos = None
            else:
                # 2) doi SL bam theo (ratchet) dua tren nen da dong sig
                if TRAIL_MODE == "slow":   line = t2[sig]
                elif TRAIL_MODE == "fast": line = t1[sig]
                elif TRAIL_MODE == "kijun":line = kij
                else:                      line = None
                if line is not None:
                    if pos.direction == "long":  pos.sl = max(pos.sl, line)
                    else:                         pos.sl = min(pos.sl, line)

                # 3) kiem tra SL/TP trong nen i (bao thu: SL truoc TP)
                b = bars[i]
                if pos.direction == "long":
                    if b.l <= pos.sl:
                        _finish(pos, i, pos.sl, "SL"); trades.append(pos); pos = None
                    elif pos.tp > 0 and b.h >= pos.tp:
                        _finish(pos, i, pos.tp, "TP"); trades.append(pos); pos = None
                else:
                    if b.h >= pos.sl:
                        _finish(pos, i, pos.sl, "SL"); trades.append(pos); pos = None
                    elif pos.tp > 0 and b.l <= pos.tp:
                        _finish(pos, i, pos.tp, "TP"); trades.append(pos); pos = None

        # ---------------- vao lenh moi tai open nen i ----------------
        if pos is None and (long_ok or short_ok):
            # chi phi round-turn (spread that cua nen + commission) tinh vao gia vao
            cost = bars[i].spread * POINT + COMMISSION_PIPS * PIP
            min_dist = SL_MIN_PIPS * PIP
            if long_ok:
                entry = bars[i].o + cost                 # mua o Ask + phi
                sl = t2[sig]
                if sl >= entry - min_dist: sl = entry - min_dist
                risk = entry - sl
                tp = entry + TAKE_PROFIT_RR * risk if TAKE_PROFIT_RR > 0 else 0.0
                pos = Trade("long", i, entry, sl, tp, risk)
            else:
                entry = bars[i].o - cost                 # ban o Bid, phi tinh truoc
                sl = t2[sig]
                if sl <= entry + min_dist: sl = entry + min_dist
                risk = sl - entry
                tp = entry - TAKE_PROFIT_RR * risk if TAKE_PROFIT_RR > 0 else 0.0
                pos = Trade("short", i, entry, sl, tp, risk)

    if pos is not None:
        _finish(pos, n - 1, bars[-1].c, "EOD")
        trades.append(pos)
    return trades


# ----------------------- Bao cao ----------------------------------
def stats(trades):
    n = len(trades)
    wins = [t for t in trades if t.r > 0]
    total_r = sum(t.r for t in trades)
    gl = abs(sum(t.r for t in trades if t.r <= 0))
    gw = sum(t.r for t in wins)
    pf = (gw / gl) if gl > 0 else float("inf")
    eq = peak = dd = 0.0
    for t in trades:
        eq += t.r; peak = max(peak, eq); dd = max(dd, peak - eq)
    return dict(n=n, win=len(wins), wr=100*len(wins)/n if n else 0,
                total_r=total_r, pf=pf, dd=dd,
                best=max((t.r for t in trades), default=0))


def report(trades):
    if not trades:
        print("Khong co lenh nao."); return
    s = stats(trades)
    reasons = {}
    for t in trades:
        reasons[t.reason] = reasons.get(t.reason, 0) + 1
    print("=" * 58)
    print("  KET QUA BACKTEST (da gom spread that + commission)")
    print("=" * 58)
    print(f"  Tong so lenh         : {s['n']}")
    print(f"  Win rate             : {s['wr']:.1f}%  ({s['win']}/{s['n']})")
    print(f"  Tong loi nhuan       : {s['total_r']:+.2f} R = {s['total_r']*RISK_MONEY:+,.2f} $")
    print(f"  Trung binh / lenh    : {s['total_r']/s['n']:+.3f} R")
    print(f"  Profit factor        : {s['pf']:.2f}")
    print(f"  Max drawdown         : {s['dd']:.2f} R = {s['dd']*RISK_MONEY:,.2f} $")
    print(f"  Lenh thang lon nhat  : {s['best']:+.2f} R  (gong theo trend)")
    print(f"  Ly do dong lenh      : {reasons}")
    print("=" * 58)
    print(f"  TP={TAKE_PROFIT_RR}R  TrailMode={TRAIL_MODE}  CloudBreakExit={EXIT_ON_CLOUD_BREAK}"
          f"  ExitOpp={EXIT_ON_OPPOSITE}")
    print(f"  CloudFilter={USE_CLOUD_FILTER}  Commission={COMMISSION_PIPS}pip  1R={RISK_MONEY}$")
    print("=" * 58)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Dung: python3 backtest.py <csv>"); sys.exit(1)
    bars = load_csv(sys.argv[1])
    print(f"Da nap {len(bars)} nen tu {bars[0].time} den {bars[-1].time}")
    report(run_backtest(bars))
