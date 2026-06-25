"""So sanh cac bo tham so exit (SL/BE/TP1/Trail) do nguoi dung cung cap, tren engine v5.
Tach IS (2010-2019) vs OOS (2020-2026) de kiem do ben (overfit hay khong)."""
import os, numpy as np
import backtester_v5 as b5

CSV = "/root/.claude/uploads/bbed706c-291e-5ab8-bf65-d655e0c7b959/826be848-EU.csv"
START = 5000.0; RISK = 20.0
# tham so co dinh (theo report EA cua nguoi dung)
FIXED = dict(fast_period=5, fast_mult=0.5, slow_period=10, slow_mult=3.0,
             sl_atr_period=14, trail_period=2, partial_frac=0.5, risk=RISK)
# Pass, SL(sl_mult), BE(be_trigger), TP1(tp1_mult), Trail(trail_mult)
SETS = [
    (1182, 2.25, 0.75, 2.50, 4.0),
    (1279, 1.75, 1.00, 3.00, 4.0),
    (1362, 2.25, 0.75, 3.50, 4.0),
    (1227, 2.25, 0.75, 2.75, 4.0),
    (1451, 2.00, 0.75, 4.00, 4.0),
    (1271, 2.00, 0.75, 3.00, 4.0),
    (1406, 2.00, 0.75, 3.75, 4.0),
    (1297, 1.75, 1.50, 3.00, 4.0),
]


def metrics(pnls, dd_abs, dd_pct):
    n = len(pnls)
    if n == 0:
        return dict(n=0, net=0, pf=0, expusd=0, expR=0, dd=0, rec=0)
    net = float(pnls.sum()); gp = pnls[pnls > 0].sum(); gl = -pnls[pnls < 0].sum()
    pf = gp / gl if gl > 0 else float("inf")
    return dict(n=n, net=net, pf=pf, expusd=net / n, expR=net / n / RISK,
                dd=dd_pct, rec=(net / dd_abs if dd_abs > 0 else float("inf")))


def run(arr, cache, p, s, e):
    pn, da, dp = b5.backtest_v5(arr, cache, p, s, e, START)
    return metrics(pn, da, dp), pn


def main():
    df = b5.load_data(CSV); arr = b5.to_arrays(df); cache = b5.IndicatorCache(arr)
    yb = b5.year_bounds(arr)
    full = (yb[2010][0], yb[2026][1]); IS = (yb[2010][0], yb[2019][1]); OOS = (yb[2020][0], yb[2026][1])
    _ = b5.backtest_v5(arr, cache, {**FIXED, "sl_mult": 2, "be_trigger": 1, "tp1_mult": 2, "trail_mult": 2}, *full, START)

    def F(x, d=2): return "inf" if not np.isfinite(x) else f"{x:.{d}f}"
    hdr = (f"{'Pass':>5} {'SL':>4} {'BE':>4} {'TP1':>4} {'Tr':>3} | "
           f"{'FULL PF':>7} {'ExpR':>5} {'DD%':>5} {'Rec':>4} {'N':>4} | "
           f"{'IS PF':>5} {'IS ExpR':>7} {'IS DD':>5} | {'OOS PF':>6} {'OOSExpR':>7} {'OOS DD':>6} {'OOSrec':>6} {'OOSn':>4}")
    print(hdr); print("-" * len(hdr))
    rows = [hdr, "-" * len(hdr)]
    oos_curves = {}
    for ps, sl, be, tp1, tr in SETS:
        p = {**FIXED, "sl_mult": sl, "be_trigger": be, "tp1_mult": tp1, "trail_mult": tr}
        mf, _ = run(arr, cache, p, *full)
        mi, _ = run(arr, cache, p, *IS)
        mo, pno = run(arr, cache, p, *OOS)
        oos_curves[ps] = pno
        line = (f"{ps:>5} {sl:>4} {be:>4} {tp1:>4} {int(tr):>3} | "
                f"{F(mf['pf']):>7} {mf['expR']:>+5.2f} {mf['dd']:>5.1f} {F(mf['rec']):>4} {mf['n']:>4} | "
                f"{F(mi['pf']):>5} {mi['expR']:>+7.2f} {mi['dd']:>5.1f} | "
                f"{F(mo['pf']):>6} {mo['expR']:>+7.2f} {mo['dd']:>6.1f} {F(mo['rec']):>6} {mo['n']:>4}")
        print(line); rows.append(line)

    outdir = os.path.dirname(__file__)
    open(os.path.join(outdir, "param_sets_compare.txt"), "w").write("\n".join(rows))

    # plot OOS equity cua 8 bo
    try:
        import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(11, 6))
        for ps, pn in oos_curves.items():
            eq = np.concatenate(([START], START + np.cumsum(pn)))
            ax.plot(eq, lw=1.1, label=f"#{ps} (net ${pn.sum():.0f}, n={len(pn)})")
        ax.axhline(START, color="#bbb", lw=0.7)
        ax.set_title("OOS 2020-2026 (EURUSD) — 8 bo tham so cua ban (engine v5)")
        ax.set_xlabel("So lenh OOS"); ax.set_ylabel("Balance $"); ax.legend(fontsize=8); ax.grid(alpha=0.3)
        fig.tight_layout(); fig.savefig(os.path.join(outdir, "param_sets_oos.png"), dpi=120)
        print("\nLuu: param_sets_compare.txt + param_sets_oos.png")
    except Exception as e:
        print("plot err", e)


if __name__ == "__main__":
    main()
