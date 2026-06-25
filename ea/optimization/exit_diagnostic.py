"""
Chan doan: VAN DE NAM O THOAT LENH HAY O ENTRY/REGIME?
Phan tich MFE/MAE (Maximum Favorable/Adverse Excursion) + phan bo R-multiple (Van Tharp)
cho chien luoc entry ATR-cross (EA goc). Tach 2013-2019 vs 2020-2026.

Voi moi lenh ghi: realized_R, MFE_R (lai toi da tung dat), MAE_R (lo toi da tung chiu),
ly do thoat (SL/TP/TRAIL/ICHI/EOD). Tu do biet:
- Capture = realized/MFE cua lenh thang: thap => cat non nguoi thang (loi EXIT).
- % lenh tung >=+1R roi dong <=0: tra lai lai (thieu breakeven stop).
- MFE trung binh tut o 2020-2026 => loi ENTRY/REGIME (gia khong con chay xa).
"""
import os, argparse, numpy as np
import backtester as base

CONTRACT = 100000.0; POINT = 0.00001; LOT_STEP = 0.01; MIN_LOT = 0.01
RISK = 20.0; DISP = 26


def ct(c, cp, prev, sl):
    if c > prev and cp > prev:
        v = c - sl; return prev if prev > v else v
    if c < prev and cp < prev:
        v = c + sl; return prev if prev < v else v
    return c - sl if c > prev else c + sl


def trails(close, af, as_, fm, sm):
    n = len(close); t1 = np.full(n, np.nan); t2 = np.full(n, np.nan)
    p1 = 0.0; p2 = 0.0; started = False
    for k in range(1, n):
        if np.isnan(af[k]) or np.isnan(as_[k]) or np.isnan(close[k - 1]) or np.isnan(close[k]):
            continue
        o1 = 0.0 if not started else p1; o2 = 0.0 if not started else p2; started = True
        p1 = ct(close[k], close[k - 1], o1, fm * af[k])
        p2 = ct(close[k], close[k - 1], o2, sm * as_[k])
        t1[k] = p1; t2[k] = p2
    return t1, t2


def simulate(arr, cache, cfg, start_idx, end_idx):
    o, h, l, c, sp = arr["open"], arr["high"], arr["low"], arr["close"], arr["spread"]
    tk = cache.donchian(9); kj = cache.donchian(26); sB = cache.donchian(52)
    af = cache.atr(cfg["fast_period"]); as_ = cache.atr(cfg["slow_period"])
    asl = cache.atr(cfg["sl_atr_period"]); atr_ = cache.atr(cfg["trail_period"])
    t1, t2 = trails(c, af, as_, cfg["fast_mult"], cfg["slow_mult"])
    sl_m, tp_m, tr_m = cfg["sl_mult"], cfg["tp_mult"], cfg["trail_mult"]
    use_tp, use_ichi = cfg["use_tp"], cfg["use_ichi_exit"]

    pos = 0; entry = 0.0; stop = 0.0; tp = 0.0; lot = 0.0; spr_e = 0.0; Rd = 0.0
    exh = 0.0; exl = 0.0
    trades = []  # (realized_R, MFE_R, MAE_R, reason, exit_year)

    def close_trade(exit_price, reason, yr):
        nonlocal pos
        pnl = ((exit_price - entry) if pos == 1 else (entry - exit_price)) * CONTRACT * lot - spr_e * CONTRACT * lot
        if pos == 1:
            mfe = (exh - entry); mae = (entry - exl)
        else:
            mfe = (entry - exl); mae = (exh - entry)
        trades.append((pnl / RISK, mfe / Rd, mae / Rd, reason, yr))
        pos = 0

    for i in range(start_idx, end_idx):
        j = i - 1; jd = j - DISP
        if jd < 1: continue
        if (np.isnan(t1[j]) or np.isnan(t2[j]) or np.isnan(t1[j - 1]) or np.isnan(t2[j - 1])
                or np.isnan(tk[jd]) or np.isnan(kj[jd]) or np.isnan(sB[jd])
                or np.isnan(asl[j]) or np.isnan(atr_[j])):
            continue
        sa = (tk[jd] + kj[jd]) * 0.5; sb = sB[jd]
        ctop = max(sa, sb); cbot = min(sa, sb)
        op = o[i]; hi = h[i]; lo = l[i]; spr = sp[i]; cl = c[j]; yr = arr["year"][i]
        cu = t1[j - 1] <= t2[j - 1] and t1[j] > t2[j]
        cd = t1[j - 1] >= t2[j - 1] and t1[j] < t2[j]

        if pos != 0:
            # cap nhat MFE/MAE bang range nen i
            if hi > exh: exh = hi
            if lo < exl: exl = lo
            # ichi exit
            ex = False
            if use_ichi:
                if pos == 1 and (cl < kj[j] or cl < cbot): ex = True
                elif pos == -1 and (cl > kj[j] or cl > ctop): ex = True
            if ex:
                close_trade(op, "ICHI", yr);
            else:
                if pos == 1:
                    ns = cl - tr_m * atr_[j]
                    if ns > stop: stop = ns
                elif pos == -1:
                    ns = cl + tr_m * atr_[j]
                    if ns < stop: stop = ns
        if pos == 1:
            if lo <= stop:
                close_trade(stop if op >= stop else op, "STOP", yr)
            elif use_tp and tp > 0 and hi >= tp:
                close_trade(tp if op <= tp else op, "TP", yr)
        elif pos == -1:
            if hi >= stop:
                close_trade(stop if op <= stop else op, "STOP", yr)
            elif use_tp and tp > 0 and lo <= tp:
                close_trade(tp if op >= tp else op, "TP", yr)

        if pos == 0:
            long_ok = cu and cl > ctop
            short_ok = cd and cl < cbot
            if long_ok or short_ok:
                sl_dist = sl_m * asl[j]
                if sl_dist > 0:
                    lot = np.floor((RISK / ((sl_dist + spr) * CONTRACT)) / LOT_STEP) * LOT_STEP
                    if lot >= MIN_LOT:
                        spr_e = spr; Rd = sl_dist + spr; entry = op; exh = hi; exl = lo
                        if long_ok:
                            pos = 1; stop = op - sl_dist; tp = op + tp_m * sl_dist if use_tp else 0.0
                        else:
                            pos = -1; stop = op + sl_dist; tp = op - tp_m * sl_dist if use_tp else 0.0
    return np.array([t[:3] for t in trades], dtype=float), [t[3] for t in trades], np.array([t[4] for t in trades])


def stats(R, MFE, MAE, reasons):
    n = len(R)
    if n == 0: return {}
    win = R > 0
    out = dict(n=n, expectancy=R.mean(), win_rate=win.mean() * 100,
               avg_win=R[win].mean() if win.any() else 0, avg_loss=R[~win].mean() if (~win).any() else 0,
               sqn=(R.mean() / R.std(ddof=1) * np.sqrt(min(n, 100))) if R.std(ddof=1) > 0 else 0,
               mfe_all=MFE.mean(), mfe_win=MFE[win].mean() if win.any() else 0,
               mae_all=MAE.mean(),
               capture=(R[win].mean() / MFE[win].mean()) if win.any() and MFE[win].mean() > 0 else 0,
               reach2R=(MFE >= 2.0).mean() * 100,
               cut_winner=(((MFE >= 2.0) & (R < 1.0)).sum() / max((MFE >= 2.0).sum(), 1)) * 100,
               gaveback=(((MFE >= 1.0) & (R <= 0)).sum() / max((MFE >= 1.0).sum(), 1)) * 100)
    rc = {}
    for r in set(reasons): rc[r] = reasons.count(r)
    out["reasons"] = rc
    return out


def show(tag, s):
    if not s: print(f"\n[{tag}] khong co lenh"); return
    print(f"\n[{tag}]  n={s['n']}  Expectancy={s['expectancy']:+.3f}R  WR={s['win_rate']:.0f}%  "
          f"SQN={s['sqn']:.2f}")
    print(f"   avg_win={s['avg_win']:+.2f}R  avg_loss={s['avg_loss']:+.2f}R")
    print(f"   MFE(all)={s['mfe_all']:.2f}R  MFE(win)={s['mfe_win']:.2f}R  MAE(all)={s['mae_all']:.2f}R")
    print(f"   CAPTURE(win realized/MFE)={s['capture']*100:.0f}%   "
          f"%lenh dat>=2R MFE={s['reach2R']:.0f}%")
    print(f"   trong so lenh dat>=2R MFE: %dong<1R (cat non)={s['cut_winner']:.0f}%")
    print(f"   %lenh tung>=+1R roi dong<=0 (tra lai)={s['gaveback']:.0f}%   exits={s['reasons']}")


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--csv", required=True)
    ap.add_argument("--outdir", default=os.path.dirname(__file__)); a = ap.parse_args()
    df = base.load_data(a.csv); arr = base.to_arrays(df); cache = base.IndicatorCache(arr)
    yb = base.year_bounds(arr)
    base_cfg = dict(fast_period=5, fast_mult=0.5, slow_period=10, slow_mult=3.0,
                    sl_atr_period=14, sl_mult=2.0, tp_mult=3.0, trail_period=10, trail_mult=3.0,
                    use_ichi_exit=0)
    s0 = yb[2013][0]; s_split = yb[2020][0]; e = yb[2026][1]
    for variant, use_tp in (("DEFAULT TP=3R", 1), ("GONG (no TP)", 0)):
        cfg = dict(base_cfg); cfg["use_tp"] = use_tp
        print("\n" + "=" * 70 + f"\n### {variant} (entry ATR-cross) ###")
        for tag, s, ee in (("2013-2026", s0, e), ("2013-2019", s0, s_split), ("2020-2026", s_split, e)):
            R3, rs, yrs = simulate(arr, cache, cfg, s, ee)
            if len(R3):
                show(tag, stats(R3[:, 0], R3[:, 1], R3[:, 2], rs))
        if use_tp == 1:
            _plot(R3, rs, a.outdir)  # plot tren default 2020-2026 (R3 con la lan cuoi: 2020-2026)


def _plot(R3, rs, outdir):
    try:
        import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
        R, MFE = R3[:, 0], R3[:, 1]
        fig, ax = plt.subplots(1, 2, figsize=(13, 5))
        ax[0].hist(R, bins=40, color="#1565C0", alpha=0.8)
        ax[0].axvline(0, color="k", lw=0.8); ax[0].set_title("Phan bo R-multiple (DEFAULT, 2020-2026)")
        ax[0].set_xlabel("R"); ax[0].set_ylabel("So lenh")
        w = R > 0
        ax[1].scatter(MFE[~w], R[~w], s=10, c="#C62828", label="thua", alpha=0.6)
        ax[1].scatter(MFE[w], R[w], s=10, c="#2E7D32", label="thang", alpha=0.6)
        lim = max(MFE.max(), 1); ax[1].plot([0, lim], [0, lim], "k--", lw=0.7, label="realized=MFE")
        ax[1].set_xlabel("MFE (R)"); ax[1].set_ylabel("Realized (R)")
        ax[1].set_title("MFE vs Realized — khoang cach = lai bi tra lai"); ax[1].legend()
        for x in ax: x.grid(alpha=0.3)
        fig.tight_layout(); fig.savefig(os.path.join(outdir, "exit_diagnostic.png"), dpi=120)
        print("\nLuu bieu do: exit_diagnostic.png")
    except Exception as ex:
        print("plot err", ex)


if __name__ == "__main__":
    main()
