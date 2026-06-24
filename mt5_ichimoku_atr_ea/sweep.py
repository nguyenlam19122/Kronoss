#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""So sanh cac kieu thoat lenh (da gom spread that). Tap trung 'gong theo trend'."""
import sys
import backtest as bt

DEFAULTS = dict(USE_CLOUD_FILTER=True, REQUIRE_CLOUD_COLOR=False,
                TAKE_PROFIT_RR=0.0, TRAIL_MODE="none",
                EXIT_ON_CLOUD_BREAK=False, EXIT_ON_OPPOSITE=True,
                COMMISSION_PIPS=0.0)


def reset():
    for k, v in DEFAULTS.items():
        setattr(bt, k, v)


def run(label, **ov):
    reset()
    for k, v in ov.items():
        setattr(bt, k, v)
    s = bt.stats(bt.run_backtest(BARS))
    print(f"{label:42s} | {s['n']:3d} lenh | win {s['wr']:4.1f}% | "
          f"{s['total_r']:+6.2f}R ({s['total_r']*50:+8.1f}$) | PF {s['pf']:4.2f} | "
          f"DD {s['dd']:5.2f}R | max {s['best']:+5.1f}R")


if __name__ == "__main__":
    BARS = bt.load_csv(sys.argv[1])
    print(f"Du lieu: {len(BARS)} nen ({BARS[0].time} -> {BARS[-1].time})  [spread that ON]\n")
    print("-" * 118)
    print(">>> CO TP CO DINH (de tham khao):")
    run("TP=2R (none)",                 TAKE_PROFIT_RR=2.0)
    run("TP=3R (none)",                 TAKE_PROFIT_RR=3.0)
    print(">>> GONG THEO XU HUONG (bo TP co dinh):")
    run("Ride: exit-opposite only",     TRAIL_MODE="none")
    run("Ride: trail SLOW (Trail2)",    TRAIL_MODE="slow")
    run("Ride: trail FAST (Trail1)",    TRAIL_MODE="fast")
    run("Ride: trail KIJUN",            TRAIL_MODE="kijun")
    run("Ride: trail FAST, no exitOpp", TRAIL_MODE="fast",  EXIT_ON_OPPOSITE=False)
    run("Ride: trail KIJUN,no exitOpp", TRAIL_MODE="kijun", EXIT_ON_OPPOSITE=False)
    run("Ride: cloud-break exit",       TRAIL_MODE="none",  EXIT_ON_CLOUD_BREAK=True)
    run("Ride: FAST + cloud-break",     TRAIL_MODE="fast",  EXIT_ON_CLOUD_BREAK=True)
    run("Ride: KIJUN + cloud-break",    TRAIL_MODE="kijun", EXIT_ON_CLOUD_BREAK=True)
    print(">>> Anh huong commission (vd 0.7pip ~ 7$/lot) len cau hinh KHUYEN NGHI:")
    run("Recommended + comm 0.7pip",    TRAIL_MODE="none",  COMMISSION_PIPS=0.7)
    print("-" * 118)
