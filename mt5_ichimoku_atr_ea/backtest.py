#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Backtest cho chien luoc Ichimoku Kumo + ATR Trailing Stop (ceyhun).
Tai hien dung logic cua EA Ichimoku_ATR_EA.mq5 de kiem chung tren du lieu lich su
truoc khi chay tren MT5.

Cach dung:
    python3 backtest.py <duong_dan_csv>

Du lieu CSV (xuat tu MT5, tab-separated):
    <DATE> <TIME> <OPEN> <HIGH> <LOW> <CLOSE> <TICKVOL> <VOL> <SPREAD>

Loi/lai duoc tinh theo R: moi lenh thua = -1R, thang chot 2R = +2R.
1R quy doi ra tien = RISK_MONEY (mac dinh 50$).
"""

import sys
import csv
from dataclasses import dataclass, field

# ----------------------- Tham so chien luoc -----------------------
TENKAN          = 9
KIJUN           = 26
SENKOU_B        = 52
DISPLACEMENT    = 26

FAST_ATR_PERIOD = 5
FAST_ATR_MULT   = 0.5
SLOW_ATR_PERIOD = 10
SLOW_ATR_MULT   = 3.0

USE_CLOUD_FILTER    = True   # gia phai ra ngoai may
REQUIRE_CLOUD_COLOR = False  # mau may trung huong
TAKE_PROFIT_RR      = 2.0    # TP theo R (0 = khong dat)
EXIT_ON_OPPOSITE    = True   # dong khi co tin hieu nguoc
USE_TRAILING        = False  # doi SL theo Slow Trail
SL_MIN_PIPS         = 5.0    # khoang cach SL toi thieu (pips)
RISK_MONEY          = 50.0   # 1R = 50$

PIP = 0.0001  # EURUSD 5-digit


# ----------------------- Doc du lieu ------------------------------
@dataclass
class Bar:
    time: str
    o: float
    h: float
    l: float
    c: float


def load_csv(path):
    bars = []
    with open(path, newline="") as f:
        reader = csv.reader(f, delimiter="\t")
        header = next(reader)
        for row in reader:
            if len(row) < 6:
                continue
            bars.append(Bar(
                time=f"{row[0]} {row[1]}",
                o=float(row[2]), h=float(row[3]),
                l=float(row[4]), c=float(row[5]),
            ))
    return bars


# ----------------------- Chi bao ----------------------------------
def wilder_atr(bars, period):
    """ATR theo Wilder (RMA) - khop voi ta.atr cua Pine & iATR cua MT5."""
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
    first = sum(tr[:period]) / period
    atr[period - 1] = first
    prev = first
    for i in range(period, n):
        prev = (prev * (period - 1) + tr[i]) / period
        atr[i] = prev
    return atr


def donchian_mid(bars, period, i):
    """(HH + LL)/2 cua `period` nen ket thuc tai index i (bao gom i)."""
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
    entry: float
    sl: float
    tp: float
    exit_i: int = -1
    exit: float = 0.0
    reason: str = ""
    r: float = 0.0


def run_backtest(bars, verbose=False):
    n = len(bars)
    atr_fast = wilder_atr(bars, FAST_ATR_PERIOD)
    atr_slow = wilder_atr(bars, SLOW_ATR_PERIOD)

    # Trail series (de quy tu dau, giong EA seed)
    t1 = [0.0] * n
    t2 = [0.0] * n
    for i in range(n):
        if i == 0:
            t1[i] = compute_trail(bars[i].c, bars[i].c, 0.0,
                                  FAST_ATR_MULT * (atr_fast[i] if atr_fast[i] == atr_fast[i] else 0.0))
            t2[i] = compute_trail(bars[i].c, bars[i].c, 0.0,
                                  SLOW_ATR_MULT * (atr_slow[i] if atr_slow[i] == atr_slow[i] else 0.0))
            continue
        af = atr_fast[i] if atr_fast[i] == atr_fast[i] else 0.0
        asw = atr_slow[i] if atr_slow[i] == atr_slow[i] else 0.0
        t1[i] = compute_trail(bars[i].c, bars[i - 1].c, t1[i - 1], FAST_ATR_MULT * af)
        t2[i] = compute_trail(bars[i].c, bars[i - 1].c, t2[i - 1], SLOW_ATR_MULT * asw)

    trades = []
    open_trade = None
    # bat dau sau khi du warmup cho moi chi bao
    start = max(SENKOU_B + DISPLACEMENT, SLOW_ATR_PERIOD) + 2

    for i in range(start, n):
        # --- tin hieu tinh tren nen da dong = i-1, vao lenh tai open cua nen i ---
        sig = i - 1
        buy_sig  = t1[sig - 1] <= t2[sig - 1] and t1[sig] >  t2[sig]
        sell_sig = t1[sig - 1] >= t2[sig - 1] and t1[sig] <  t2[sig]

        kijun = donchian_mid(bars, KIJUN, sig)
        # may "duoi" nen sig: span tinh truoc do (displacement-1) nen,
        # khop voi offset cua TradingView va shift cua EA (.mq5)
        cs = sig - (DISPLACEMENT - 1)
        spanA = spanB = None
        if cs >= 0:
            t = donchian_mid(bars, TENKAN, cs)
            k = donchian_mid(bars, KIJUN, cs)
            spanA = (t + k) / 2.0 if (t is not None and k is not None) else None
            spanB = donchian_mid(bars, SENKOU_B, cs)

        cloud_ok = spanA is not None and spanB is not None
        c1 = bars[sig].c
        above = cloud_ok and c1 > max(spanA, spanB)
        below = cloud_ok and c1 < min(spanA, spanB)
        bull  = cloud_ok and spanA > spanB
        bear  = cloud_ok and spanA < spanB

        long_ok  = buy_sig  and (not USE_CLOUD_FILTER or above) and (not REQUIRE_CLOUD_COLOR or bull)
        short_ok = sell_sig and (not USE_CLOUD_FILTER or below) and (not REQUIRE_CLOUD_COLOR or bear)

        # --- quan ly lenh dang mo (kiem tra SL/TP tren nen i) ---
        if open_trade is not None:
            b = bars[i]
            closed = False
            if open_trade.direction == "long":
                # bao thu: neu ca SL va TP cham trong cung nen -> gia dinh SL truoc
                if b.l <= open_trade.sl:
                    _close(open_trade, i, open_trade.sl, "SL"); closed = True
                elif open_trade.tp > 0 and b.h >= open_trade.tp:
                    _close(open_trade, i, open_trade.tp, "TP"); closed = True
            else:
                if b.h >= open_trade.sl:
                    _close(open_trade, i, open_trade.sl, "SL"); closed = True
                elif open_trade.tp > 0 and b.l <= open_trade.tp:
                    _close(open_trade, i, open_trade.tp, "TP"); closed = True

            if not closed and EXIT_ON_OPPOSITE:
                if open_trade.direction == "long" and sell_sig:
                    _close(open_trade, i, bars[i].o, "OPP"); closed = True
                elif open_trade.direction == "short" and buy_sig:
                    _close(open_trade, i, bars[i].o, "OPP"); closed = True

            if not closed and USE_TRAILING:
                if open_trade.direction == "long":
                    open_trade.sl = max(open_trade.sl, t2[sig])
                else:
                    open_trade.sl = min(open_trade.sl, t2[sig])

            if closed:
                trades.append(open_trade)
                open_trade = None

        # --- vao lenh moi tai open nen i ---
        if open_trade is None and (long_ok or short_ok):
            entry = bars[i].o
            if long_ok:
                sl = t2[sig]
                min_dist = SL_MIN_PIPS * PIP
                if sl >= entry - min_dist:
                    sl = entry - min_dist
                dist = entry - sl
                tp = entry + TAKE_PROFIT_RR * dist if TAKE_PROFIT_RR > 0 else 0.0
                open_trade = Trade("long", i, entry, sl, tp)
            else:
                sl = t2[sig]
                min_dist = SL_MIN_PIPS * PIP
                if sl <= entry + min_dist:
                    sl = entry + min_dist
                dist = sl - entry
                tp = entry - TAKE_PROFIT_RR * dist if TAKE_PROFIT_RR > 0 else 0.0
                open_trade = Trade("short", i, entry, sl, tp)

    # dong lenh con mo o cuoi du lieu
    if open_trade is not None:
        _close(open_trade, n - 1, bars[-1].c, "EOD")
        trades.append(open_trade)

    return trades


def _close(tr, i, price, reason):
    tr.exit_i = i
    tr.exit = price
    tr.reason = reason
    risk = abs(tr.entry - tr.sl)
    if risk <= 0:
        tr.r = 0.0
    elif tr.direction == "long":
        tr.r = (tr.exit - tr.entry) / risk
    else:
        tr.r = (tr.entry - tr.exit) / risk


# ----------------------- Bao cao ----------------------------------
def report(trades):
    if not trades:
        print("Khong co lenh nao.")
        return
    n = len(trades)
    wins = [t for t in trades if t.r > 0]
    losses = [t for t in trades if t.r <= 0]
    total_r = sum(t.r for t in trades)
    longs = [t for t in trades if t.direction == "long"]
    shorts = [t for t in trades if t.direction == "short"]

    # max drawdown (theo R, tren duong von cong don)
    eq = 0.0
    peak = 0.0
    max_dd = 0.0
    for t in trades:
        eq += t.r
        peak = max(peak, eq)
        max_dd = max(max_dd, peak - eq)

    gross_win = sum(t.r for t in wins)
    gross_loss = abs(sum(t.r for t in losses))
    pf = (gross_win / gross_loss) if gross_loss > 0 else float("inf")

    reasons = {}
    for t in trades:
        reasons[t.reason] = reasons.get(t.reason, 0) + 1

    print("=" * 56)
    print("  KET QUA BACKTEST  Ichimoku Kumo + ATR Trailing Stop")
    print("=" * 56)
    print(f"  Tong so lenh         : {n}  (Long {len(longs)} / Short {len(shorts)})")
    print(f"  Thang / Thua         : {len(wins)} / {len(losses)}")
    print(f"  Win rate             : {100*len(wins)/n:.1f}%")
    print(f"  Tong loi nhuan       : {total_r:+.2f} R   = {total_r*RISK_MONEY:+,.2f} $ (1R={RISK_MONEY:.0f}$)")
    print(f"  Trung binh / lenh    : {total_r/n:+.3f} R = {total_r/n*RISK_MONEY:+.2f} $")
    print(f"  Profit factor        : {pf:.2f}")
    print(f"  Max drawdown         : {max_dd:.2f} R = {max_dd*RISK_MONEY:,.2f} $")
    print(f"  Ly do dong lenh      : {reasons}")
    print("=" * 56)
    cfg = (f"  Cau hinh: TP={TAKE_PROFIT_RR}R  CloudFilter={USE_CLOUD_FILTER}  "
           f"CloudColor={REQUIRE_CLOUD_COLOR}  Trailing={USE_TRAILING}  "
           f"ExitOpp={EXIT_ON_OPPOSITE}")
    print(cfg)
    print("=" * 56)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Dung: python3 backtest.py <csv>")
        sys.exit(1)
    bars = load_csv(sys.argv[1])
    print(f"Da nap {len(bars)} nen tu {bars[0].time} den {bars[-1].time}")
    trades = run_backtest(bars)
    report(trades)
