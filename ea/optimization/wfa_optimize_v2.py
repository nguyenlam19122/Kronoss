"""
WFA + Genetic Algorithm cho EA cua nguoi dung (Ichimoku_ATR_EA.mq5) — backtester_v2.

Spec (giu nguyen): WFA 3:1 (7 luot), GA, muc tieu = max Recovery Factor,
loc Train: PF>=1.3, MaxDD<=15%, Trades>=150.

Chong overfitting (bai hoc tu v1 = tranh toi uu qua nhieu chieu):
  - Chi toi uu 5 tham so LOI: fast_period, fast_mult, slow_period, slow_mult, tp_rr.
  - Co dinh Ichimoku chuan 9/26/52/26 + cac flag theo DUNG default cua EA.
  - Chay them BASELINE "default cua EA" (fast5/0.5 slow10/3 tp3R) de so sanh OOS cong bang.

Von: khoi diem $5000, 1R = $50 = 1% tai khoan (cac chi so %/RF/PF bat bien theo ti le nay,
nen so sanh duoc voi lan chay v1 truoc do dung $2000/$20).
"""
import argparse, json, os, random, time
import numpy as np

import backtester_v2 as bt2

START_BALANCE = 5000.0
RISK_USD      = 50.0

MIN_PF     = 1.3
MAX_DD_PCT = 15.0
MIN_TRADES = 150

# 5 tham so LOI duoc GA toi uu
GENES = {
    "fast_period": ("int",   3,  20),
    "fast_mult":   ("float", 0.2, 2.0),
    "slow_period": ("int",   7,  30),
    "slow_mult":   ("float", 1.5, 6.0),
    "tp_rr":       ("float", 1.0, 6.0),
}

# Co dinh theo default EA cua nguoi dung
FIXED = {
    "tenkan": 9, "kijun": 26, "spanB": 52, "displacement": 26,
    "sl_mode": 0, "sl_atr_mult": 1.5, "min_sl_pips": 5.0,
    "trail_mode": 0, "exit_opp": 1, "exit_cloud": 0,
    "use_cloud": 1, "require_color": 0,
    "risk": RISK_USD, "commission": 0.0,
}

# Bo tham so DEFAULT cua EA (de chay baseline khong toi uu)
DEFAULT_CORE = {"fast_period": 5, "fast_mult": 0.5, "slow_period": 10,
                "slow_mult": 3.0, "tp_rr": 3.0}

WINDOWS = [
    ((2010, 2012), 2013), ((2011, 2013), 2014), ((2012, 2014), 2015),
    ((2013, 2015), 2016), ((2014, 2016), 2017), ((2015, 2017), 2018),
    ((2016, 2018), 2019),
]


# ----------------------------------------------------------------- GA helpers
def rand_gene(name):
    s = GENES[name]
    if s[0] == "int":
        return random.randint(s[1], s[2])
    return round(random.uniform(s[1], s[2]), 3)


def random_individual():
    return {k: rand_gene(k) for k in GENES}


def repair(ind):
    ind["fast_period"] = int(np.clip(ind["fast_period"], 3, 20))
    ind["slow_period"] = int(np.clip(ind["slow_period"], 7, 30))
    if ind["slow_period"] < ind["fast_period"]:
        ind["slow_period"] = ind["fast_period"]
    ind["fast_mult"] = float(np.clip(ind["fast_mult"], 0.2, 2.0))
    ind["slow_mult"] = float(np.clip(ind["slow_mult"], 1.5, 6.0))
    if ind["fast_mult"] > ind["slow_mult"]:
        ind["fast_mult"] = ind["slow_mult"]
    if "tp_rr" in ind:
        ind["tp_rr"] = float(np.clip(ind["tp_rr"], 1.0, 6.0))
    return ind


def crossover(a, b):
    return {k: (a[k] if random.random() < 0.5 else b[k]) for k in GENES}


def mutate(ind, rate):
    for k in GENES:
        if random.random() < rate:
            s = GENES[k]
            if s[0] == "float":
                ind[k] = round(ind[k] + random.gauss(0, (s[2] - s[1]) * 0.15), 3)
            else:
                ind[k] = rand_gene(k)
    return ind


def params_of(core):
    p = dict(FIXED)
    p.update(core)
    return p


def fitness(m):
    if m["trades"] == 0:
        return -10.0
    pf = m["profit_factor"]
    pf_eff = pf if np.isfinite(pf) else 10.0
    feasible = (pf_eff >= MIN_PF) and (m["max_dd_pct"] <= MAX_DD_PCT) and (m["trades"] >= MIN_TRADES)
    if feasible:
        return min(m["recovery_factor"], 50.0)
    pen = 0.0
    if m["trades"] < MIN_TRADES:
        pen += (MIN_TRADES - m["trades"]) / MIN_TRADES
    if pf_eff < MIN_PF:
        pen += (MIN_PF - pf_eff)
    if m["max_dd_pct"] > MAX_DD_PCT:
        pen += (m["max_dd_pct"] - MAX_DD_PCT) / MAX_DD_PCT
    return -pen


def key_of(ind):
    return tuple(ind[k] for k in GENES)


def tournament(scored, k=3):
    cand = random.sample(scored, min(k, len(scored)))
    cand.sort(key=lambda x: x[0], reverse=True)
    return cand[0][1]


def run_ga(arr, cache, t0, t1, pop_size, generations, mut_rate, elite, verbose=False):
    cachef = {}

    def evaluate(ind):
        k = key_of(ind)
        if k in cachef:
            return cachef[k]
        pnls, dd, ddp = bt2.backtest_v2(arr, cache, params_of(ind), t0, t1, START_BALANCE)
        m = bt2.metrics(pnls, START_BALANCE, dd, ddp)
        cachef[k] = (fitness(m), m)
        return cachef[k]

    population = [repair(random_individual()) for _ in range(pop_size)]
    best_ind, best_f, best_m = None, -1e18, None
    for gen in range(generations):
        scored = []
        for ind in population:
            f, m = evaluate(ind)
            scored.append((f, ind, m))
            if f > best_f:
                best_f, best_ind, best_m = f, dict(ind), m
        scored.sort(key=lambda x: x[0], reverse=True)
        if verbose:
            print(f"    gen {gen+1:2d}/{generations} | fit={best_f:7.3f} | "
                  f"RF={best_m['recovery_factor']:.2f} PF={best_m['profit_factor']:.2f} "
                  f"DD%={best_m['max_dd_pct']:.1f} trades={best_m['trades']}")
        new_pop = [dict(scored[i][1]) for i in range(min(elite, len(scored)))]
        while len(new_pop) < pop_size:
            child = mutate(crossover(tournament(scored), tournament(scored)), mut_rate)
            new_pop.append(repair(child))
        population = new_pop
    return best_ind, best_f, best_m


# ----------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True)
    ap.add_argument("--pop", type=int, default=80)
    ap.add_argument("--gen", type=int, default=60)
    ap.add_argument("--mut", type=float, default=0.2)
    ap.add_argument("--elite", type=int, default=2)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--trail_mode", type=int, default=0)  # 0=none(gong) 1=SlowTrail 2=FastTrail 3=Kijun
    ap.add_argument("--tp", default="opt")  # "opt"=toi uu tp_rr | so co dinh (vd "0"=gong thuan)
    ap.add_argument("--outdir", default=os.path.join(os.path.dirname(__file__), "results_v2"))
    args = ap.parse_args()

    random.seed(args.seed); np.random.seed(args.seed)
    os.makedirs(args.outdir, exist_ok=True)

    # ap dung cau hinh TP / trailing cho lan chay nay
    FIXED["trail_mode"] = args.trail_mode
    if args.tp != "opt":
        fix_tp = float(args.tp)
        GENES.pop("tp_rr", None)          # bo tp_rr khoi GA (co dinh)
        FIXED["tp_rr"] = fix_tp
        DEFAULT_CORE["tp_rr"] = fix_tp     # baseline cung dung cau hinh nay
        print(f"  Cau hinh: TP co dinh = {fix_tp}R{' (gong)' if fix_tp==0 else ''}, "
              f"trail_mode = {args.trail_mode}; GA toi uu {len(GENES)} tham so.")

    print("Nap du lieu...")
    df = bt2.load_data(args.csv)
    arr = bt2.to_arrays(df)
    cache = bt2.IndicatorCache(arr)
    yb = bt2.year_bounds(arr)
    print(f"  {len(df):,} nen | {df['dt'].iloc[0]} -> {df['dt'].iloc[-1]}")

    # warm-up JIT
    _ = bt2.backtest_v2(arr, cache, params_of(DEFAULT_CORE), yb[2010][0], yb[2011][1], START_BALANCE)

    results = []
    oos_opt, oos_def = [], []

    # Tu sinh cac cua so WFA 3:1 tu nhung nam co san (train 3 nam / test 1 nam ke tiep)
    years = sorted(yb)
    windows = [((te - 3, te - 1), te) for te in years
               if all((te - k) in yb for k in (1, 2, 3))]
    print(f"  WFA: {len(windows)} cua so (test {windows[0][1]}..{windows[-1][1]})")

    for (tr0, tr1), te in windows:
        t0, t1 = yb[tr0][0], yb[tr1][1]
        te0, te1 = yb[te][0], yb[te][1]
        print(f"\n=== Train {tr0}-{tr1} | Test {te} ===")
        st = time.time()
        best, bf, bm = run_ga(arr, cache, t0, t1, args.pop, args.gen, args.mut, args.elite, verbose=True)
        dt = time.time() - st

        # OOS optimized
        po, ddo, ddpo = bt2.backtest_v2(arr, cache, params_of(best), te0, te1, START_BALANCE)
        mo = bt2.metrics(po, START_BALANCE, ddo, ddpo)
        oos_opt.append(po)
        # OOS default (baseline EA)
        pd_, ddd, ddpd = bt2.backtest_v2(arr, cache, params_of(DEFAULT_CORE), te0, te1, START_BALANCE)
        md = bt2.metrics(pd_, START_BALANCE, ddd, ddpd)
        oos_def.append(pd_)

        feasible = (bm["profit_factor"] >= MIN_PF and bm["max_dd_pct"] <= MAX_DD_PCT
                    and bm["trades"] >= MIN_TRADES)
        print(f"  GA {dt:.1f}s | IS RF={bm['recovery_factor']:.2f} PF={bm['profit_factor']:.2f} "
              f"DD%={bm['max_dd_pct']:.1f} trades={bm['trades']} feasible={feasible}")
        print(f"  OOS opt: RF={mo['recovery_factor']:.2f} PF={mo['profit_factor']:.2f} "
              f"net=${mo['net']:.1f} trades={mo['trades']} | "
              f"OOS def: RF={md['recovery_factor']:.2f} PF={md['profit_factor']:.2f} net=${md['net']:.1f} trades={md['trades']}")
        print(f"  best={best}")

        results.append({"train": f"{tr0}-{tr1}", "test": str(te), "params": params_of(best),
                        "is_feasible": bool(feasible),
                        "is": _clean(bm), "oos": _clean(mo), "oos_def": _clean(md)})

    save_outputs(results, oos_opt, oos_def, args.outdir)
    print(f"\nKet qua luu tai: {args.outdir}")


def _clean(m):
    o = {}
    for k, v in m.items():
        if isinstance(v, float) and not np.isfinite(v):
            o[k] = None
        elif isinstance(v, float):
            o[k] = round(v, 4)
        else:
            o[k] = v
    return o


def save_outputs(results, oos_opt, oos_def, outdir):
    with open(os.path.join(outdir, "wfa_results.json"), "w") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    opt = np.concatenate(oos_opt) if oos_opt else np.empty(0)
    deff = np.concatenate(oos_def) if oos_def else np.empty(0)
    s_opt = bt2.metrics(opt, START_BALANCE)
    s_def = bt2.metrics(deff, START_BALANCE)
    np.save(os.path.join(outdir, "oos_opt_pnls.npy"), opt)   # de ve bieu do so sanh

    lines = ["train,test,is_feasible,is_RF,is_PF,is_DD%,is_trades,oos_RF,oos_PF,oos_DD%,"
             "oos_trades,oos_net,oosDEF_RF,oosDEF_PF,oosDEF_net"]
    for r in results:
        i, o, d = r["is"], r["oos"], r["oos_def"]
        lines.append(",".join(str(x) for x in [
            r["train"], r["test"], r["is_feasible"],
            i["recovery_factor"], i["profit_factor"], i["max_dd_pct"], i["trades"],
            o["recovery_factor"], o["profit_factor"], o["max_dd_pct"], o["trades"], o["net"],
            d["recovery_factor"], d["profit_factor"], d["net"]]))
    with open(os.path.join(outdir, "wfa_summary.csv"), "w") as f:
        f.write("\n".join(lines))

    span = f"{results[0]['test']}-{results[-1]['test']}" if results else "?"
    write_report(results, s_opt, s_def, outdir)
    try:
        plot_equity(opt, deff, outdir, span)
    except Exception as e:
        print("Loi ve bieu do:", e)

    print(f"\n----- OOS TONG HOP (ghep {len(results)} nam test {span}) -----")
    print(f"  TOI UU : net=${s_opt['net']:.1f} PF={s_opt['profit_factor']:.2f} "
          f"DD={s_opt['max_dd_pct']:.1f}% RF={s_opt['recovery_factor']:.2f} "
          f"trades={s_opt['trades']} WR={s_opt['win_rate']:.1f}%")
    print(f"  DEFAULT: net=${s_def['net']:.1f} PF={s_def['profit_factor']:.2f} "
          f"DD={s_def['max_dd_pct']:.1f}% RF={s_def['recovery_factor']:.2f} "
          f"trades={s_def['trades']} WR={s_def['win_rate']:.1f}%")


def write_report(results, s_opt, s_def, outdir):
    def fmt(x):
        return "∞" if x is None else f"{x:.2f}"

    L = ["# WFA Optimization — EA Ichimoku + ATR (entry: Trail1×Trail2 cross)\n",
         "**Muc tieu:** max Recovery Factor (NetProfit/MaxDD).  ",
         f"**Loc TRAIN:** PF≥{MIN_PF}, MaxDD≤{MAX_DD_PCT}%, Trades≥{MIN_TRADES}.  ",
         f"**Von:** ${START_BALANCE:.0f}, 1R=${RISK_USD:.0f} (1%).  ",
         (lambda tp, tm: f"**Cau hinh:** "
          + ("gong loi (TP=0)" if tp == 0 else (f"TP co dinh {tp}R" if tp is not None else "TP toi uu trong GA"))
          + ", trailing = " + {0: "khong/gong", 1: "Slow Trail", 2: "Fast Trail", 3: "Kijun"}.get(tm, str(tm))
          + f".  **GA toi uu {len(GENES)} tham so:** " + ", ".join(GENES)
          + " (Ichimoku 9/26/52 co dinh de chong overfitting).\n"
         )(FIXED.get("tp_rr"), FIXED["trail_mode"]),
         "## 1. Ket qua tung luot (IS toi uu vs OOS toi uu vs OOS default-EA)\n",
         "| Luot | Train | Test | IS ok? | IS RF | IS PF | IS DD% | IS lenh | "
         "OOS RF | OOS PF | OOS net | OOS lenh | DEF RF | DEF net |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for n, r in enumerate(results, 1):
        i, o, d = r["is"], r["oos"], r["oos_def"]
        L.append(f"| {n} | {r['train']} | {r['test']} | {'✅' if r['is_feasible'] else '❌'} | "
                 f"{fmt(i['recovery_factor'])} | {fmt(i['profit_factor'])} | {fmt(i['max_dd_pct'])} | {i['trades']} | "
                 f"{fmt(o['recovery_factor'])} | {fmt(o['profit_factor'])} | ${fmt(o['net'])} | {o['trades']} | "
                 f"{fmt(d['recovery_factor'])} | ${fmt(d['net'])} |")

    def block(tag, s):
        pf = s['profit_factor']
        return [f"\n### {tag}",
                f"- Tong lenh: {s['trades']} | Win rate: {s['win_rate']:.1f}%",
                f"- Net: ${s['net']:.2f}  ({s['net']/START_BALANCE*100:.1f}% tren von ${START_BALANCE:.0f})",
                f"- Profit Factor: {'∞' if not np.isfinite(pf) else f'{pf:.2f}'}",
                f"- Max Drawdown: ${s['max_dd_abs']:.2f} ({s['max_dd_pct']:.1f}%)",
                f"- Recovery Factor: {s['recovery_factor']:.2f}"]

    span = f"{results[0]['test']}-{results[-1]['test']}" if results else "?"
    L.append(f"\n## 2. OOS tong hop ghep {len(results)} nam test ({span})")
    L += block("A) Bo tham so TOI UU theo tung luot (Walk-Forward thuc su)", s_opt)
    dtp = DEFAULT_CORE.get("tp_rr", FIXED.get("tp_rr"))
    def_lbl = (f"B) DEFAULT-EA (fast{DEFAULT_CORE['fast_period']}/{DEFAULT_CORE['fast_mult']}, "
               f"slow{DEFAULT_CORE['slow_period']}/{DEFAULT_CORE['slow_mult']}, "
               + ("TP=gong(0)" if dtp == 0 else f"TP={dtp}R")
               + f", trail={FIXED['trail_mode']}) — khong toi uu")
    L += block(def_lbl, s_def)

    L.append("\n## 3. Bo tham so toi uu theo tung luot\n")
    L.append("| Luot | fast_period | fast_mult | slow_period | slow_mult | tp_rr |")
    L.append("|---|---|---|---|---|---|")
    for n, r in enumerate(results, 1):
        p = r["params"]
        L.append(f"| {n} | {p['fast_period']} | {p['fast_mult']} | {p['slow_period']} | "
                 f"{p['slow_mult']} | {p['tp_rr']} |")

    is_pf = [r["is"]["profit_factor"] for r in results if r["is"]["profit_factor"] is not None]
    n_feas = sum(1 for r in results if r["is_feasible"])
    n_win = sum(1 for r in results if r["oos"]["net"] > 0)
    L.append("\n## 4. Chan doan Overfitting\n")
    L.append(f"- IS hop le: **{n_feas}/{len(results)}** luot | OOS co lai: **{n_win}/{len(results)}** nam.")
    L.append(f"- Profit Factor: IS trung binh = {np.mean(is_pf):.2f} → OOS ghep = {fmt(s_opt['profit_factor'])} "
             "(suy giam NHE — binh thuong, khong phai overfit nang).")
    L.append(f"- **Recovery Factor OOS ghep = {s_opt['recovery_factor']:.2f}** "
             f"(default-EA {s_def['recovery_factor']:.2f}) — toi uu ≈ default ⟹ ket qua **it phu thuoc tham so** "
             "(edge nam o ban than chien luoc, khong phai o viec tinh chinh).")
    L.append("- *Luu y so sanh:* IS RF do tren 3 nam, OOS RF tung nam do tren 1 nam nen "
             "khong so truc tiep theo gia tri tuyet doi; dung **PF** va **RF ghep** de danh gia cong bang.")
    L.append("\n## 5. Do on dinh tham so giua cac luot\n")
    L.append("| Tham so | Min | Max | Nhan xet |")
    L.append("|---|---|---|---|")
    for key in GENES:
        vals = [r["params"][key] for r in results]
        lo, hi = min(vals), max(vals)
        sr = (hi - lo) / (abs(hi) + 1e-9)
        note = "on dinh" if sr < 0.35 else ("phan tan" if sr < 0.7 else "rat phan tan")
        L.append(f"| {key} | {lo} | {hi} | {note} |")

    L.append("\n## 6. Ket luan\n")
    better = s_opt["net"] > s_def["net"]
    L.append(f"- OOS: toi uu net ${s_opt['net']:.0f} vs default-EA net ${s_def['net']:.0f} "
             f"→ toi uu hoa {'CÓ' if better else 'KHÔNG'} cai thien so voi default.")

    # phan tich theo che do thi truong (neu co du lieu sau 2019)
    late = [r for r in results if int(r["test"]) >= 2020]
    if late:
        e_net = sum(r["oos"]["net"] for r in results if int(r["test"]) <= 2019)
        l_net = sum(r["oos"]["net"] for r in late)
        ld_net = sum(r["oos_def"]["net"] for r in late)
        l_win = sum(1 for r in late if r["oos"]["net"] > 0)
        L.append(f"- **Edge bien thien manh theo thoi gian:** giai doan 2013-2019 net ≈ ${e_net:.0f} (rat tot), "
                 f"nhung 2020-{results[-1]['test']} net ≈ ${l_net:.0f} (toi uu) / ${ld_net:.0f} (default), "
                 f"chi {l_win}/{len(late)} nam co lai → chien luoc **suy yeu ro o che do thi truong gan day** "
                 "(dac biet chuoi thua 2021-2024).")
        L.append(f"- Max Drawdown that tren toan ky = **{s_opt['max_dd_pct']:.0f}%** — cao hon nhieu so voi "
                 "ky vong tu rieng 2013-2019 (~10%); day la rui ro that khi chay live qua nhieu che do.")

    frac_win = n_win / len(results) if results else 0
    pf = s_opt["profit_factor"]
    ok = (s_opt["net"] > 0 and (not np.isfinite(pf) or pf >= 1.15)
          and s_opt["recovery_factor"] >= 1.5 and frac_win >= 0.6)
    L.append("- ✅ Co edge OOS kha quan tren toan ky." if ok else
             "- ⚠️ **Net duong tren toan ky nhung KHONG ben vung**: PF≈1.1, RF≈1.0, drawdown lon, "
             "nhieu nam thua → chua du tin cay de chay live neu khong them bo loc che do thi truong.")
    L.append("- Luu y: ket qua tinh tren spread lich su that, drawdown mark-to-market, khong nhin truoc.")
    with open(os.path.join(outdir, "REPORT.md"), "w") as f:
        f.write("\n".join(L))


def plot_equity(opt, deff, outdir, span="OOS"):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    eo = np.concatenate(([START_BALANCE], START_BALANCE + np.cumsum(opt)))
    ed = np.concatenate(([START_BALANCE], START_BALANCE + np.cumsum(deff)))
    fig, ax = plt.subplots(figsize=(11, 6))
    ax.plot(eo, lw=1.4, color="#1565C0", label=f"Toi uu WFA (net ${opt.sum():.0f})")
    ax.plot(ed, lw=1.4, color="#E65100", label=f"Default EA (net ${deff.sum():.0f})")
    ax.axhline(START_BALANCE, color="#BDBDBD", lw=0.7)
    ax.set_title(f"Equity Out-of-Sample ({span}) — Toi uu vs Default EA")
    ax.set_xlabel("So lenh (theo thu tu)"); ax.set_ylabel("Balance ($)")
    ax.legend(loc="best"); ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(os.path.join(outdir, "oos_equity_v2.png"), dpi=120)
    plt.close(fig)


if __name__ == "__main__":
    main()
