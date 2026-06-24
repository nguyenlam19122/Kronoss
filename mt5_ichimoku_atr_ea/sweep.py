#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""So sanh nhanh cac cau hinh tham so de chon setup tot."""
import sys
import backtest as bt


def run(label, **overrides):
    for k, v in overrides.items():
        setattr(bt, k, v)
    trades = bt.run_backtest(BARS)
    n = len(trades)
    wins = sum(1 for t in trades if t.r > 0)
    total_r = sum(t.r for t in trades)
    gl = abs(sum(t.r for t in trades if t.r <= 0))
    gw = sum(t.r for t in trades if t.r > 0)
    pf = gw / gl if gl > 0 else float("inf")
    eq = peak = dd = 0.0
    for t in trades:
        eq += t.r; peak = max(peak, eq); dd = max(dd, peak - eq)
    print(f"{label:38s} | trades {n:3d} | win {100*wins/n:4.1f}% | "
          f"{total_r:+6.2f}R ({total_r*50:+8.1f}$) | PF {pf:4.2f} | DD {dd:4.2f}R")


DEFAULTS = dict(USE_CLOUD_FILTER=True, REQUIRE_CLOUD_COLOR=False,
                TAKE_PROFIT_RR=2.0, EXIT_ON_OPPOSITE=True, USE_TRAILING=False)


def reset():
    for k, v in DEFAULTS.items():
        setattr(bt, k, v)


if __name__ == "__main__":
    BARS = bt.load_csv(sys.argv[1])
    print(f"Du lieu: {len(BARS)} nen ({BARS[0].time} -> {BARS[-1].time})\n")
    print("-" * 110)
    reset(); run("Baseline (TP=2R, exitOpp, cloud filter)")
    reset(); run("+ Cloud color filter", REQUIRE_CLOUD_COLOR=True)
    reset(); run("+ Trailing SlowTrail", USE_TRAILING=True)
    reset(); run("Trailing + no fixed TP", USE_TRAILING=True, TAKE_PROFIT_RR=0.0)
    reset(); run("No exit-on-opposite (pure TP/SL)", EXIT_ON_OPPOSITE=False)
    reset(); run("TP = 1.5R", TAKE_PROFIT_RR=1.5)
    reset(); run("TP = 3R", TAKE_PROFIT_RR=3.0)
    reset(); run("TP = 1R", TAKE_PROFIT_RR=1.0)
    reset(); run("No cloud filter (ATR only)", USE_CLOUD_FILTER=False)
    reset(); run("TP=3R + cloud color", TAKE_PROFIT_RR=3.0, REQUIRE_CLOUD_COLOR=True)
    reset(); run("TP=2R + cloud color + trailing", REQUIRE_CLOUD_COLOR=True, USE_TRAILING=True)
    print("-" * 110)
