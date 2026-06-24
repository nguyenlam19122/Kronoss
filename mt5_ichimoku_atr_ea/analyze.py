#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Phan tich do TOI UU & do ON DINH (robustness) cua cau hinh thoat lenh:
  1) Quet min gia tri TP  -> xem 3R la "dinh nhon" (overfit) hay "vung phang" (ben vung).
  2) Chia doi du lieu (nua dau / nua cuoi) -> cau hinh nao an dong deu o ca 2 giai doan.

Dung:  python3 analyze.py <csv> [commission_pips]
"""
import sys
import backtest as bt


def main(path, comm=0.0):
    BARS = bt.load_csv(path)
    n = len(BARS); mid = n // 2

    def cfg(**ov):
        base = dict(TAKE_PROFIT_RR=0.0, TRAIL_MODE="none", EXIT_ON_CLOUD_BREAK=False,
                    EXIT_ON_OPPOSITE=True, COMMISSION_PIPS=comm)
        base.update(ov)
        for k, v in base.items():
            setattr(bt, k, v)
        return bt.run_backtest(BARS)

    def show(label, trades):
        s = bt.stats(trades)
        h1 = [t for t in trades if t.entry_i < mid]
        h2 = [t for t in trades if t.entry_i >= mid]
        s1, s2 = bt.stats(h1), bt.stats(h2)
        wins = [t.r for t in trades if t.r > 0]
        avgw = sum(wins) / len(wins) if wins else 0.0
        print(f"{label:13s}| tot {s['total_r']:+6.2f}R | PF {s['pf']:.2f} | DD {s['dd']:.2f}R | "
              f"avgWin {avgw:+.2f}R | NuaDau {s1['total_r']:+5.1f}R (PF{s1['pf']:.2f}) | "
              f"NuaCuoi {s2['total_r']:+5.1f}R (PF{s2['pf']:.2f})")

    print(f"Du lieu {n} nen. Diem chia = nen {mid} ({BARS[mid].time}). commission={comm}pip\n")
    print("== QUET TP (xem co bi overfit khong) ==")
    for tp in [1, 1.5, 2, 2.5, 3, 3.5, 4, 5, 6]:
        show(f"TP={tp}R", cfg(TAKE_PROFIT_RR=tp))
    print("\n== GONG (khong TP, thoat khi ATR dao chieu) ==")
    show("Gong", cfg(TAKE_PROFIT_RR=0.0))
    print("\nDoc ket qua: cau hinh tot = tong R cao + PF cao + 'NuaDau' va 'NuaCuoi' DEU duong va can nhau.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Dung: python3 analyze.py <csv> [commission_pips]"); sys.exit(1)
    main(sys.argv[1], float(sys.argv[2]) if len(sys.argv) > 2 else 0.0)
