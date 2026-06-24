"""
WFA cuon chieu 3:1 (13 folds) + Optuna NSGA-II (Genetic Algorithm).
Chien luoc: Ichimoku TK-cross (khoa 9/26/52) + ATR SL/TP/Trailing, 1R=20$ gom spread.

Muc tieu: TOI DA HOA Annualized Sharpe (theo R-multiple) tren Train.
Loc Train hop le: Sharpe>=1.0, PF>=1.25, MaxDD<=10%, Trades>=150.
Toi uu: sl_atr_period[10..20], sl_mult[1.0..3.5/0.25], tp_mult[1.5..4.0/0.25],
        trail_period[5..30], trail_mult[1.0..3.5/0.25], use_ichi_exit{T,F}.
So sanh 2 bien the:  DEFAULT (TP cung tp_mult)  vs  GONG loi (bo TP, theo Slow Trail).
"""
import argparse, json, os, numpy as np
import optuna
import backtester_v3 as b3

optuna.logging.set_verbosity(optuna.logging.WARNING)

START_BALANCE = 2000.0     # 1R = 20$ = 1% tai khoan
RISK = 20.0
SHARPE_MIN, PF_MIN, DD_MAX, TRADES_MIN = 1.0, 1.25, 10.0, 150

FOLDS = [((2010, 2012), [2013]), ((2011, 2013), [2014]), ((2012, 2014), [2015]),
         ((2013, 2015), [2016]), ((2014, 2016), [2017]), ((2015, 2017), [2018]),
         ((2016, 2018), [2019]), ((2017, 2019), [2020]), ((2018, 2020), [2021]),
         ((2019, 2021), [2022]), ((2020, 2022), [2023]), ((2021, 2023), [2024]),
         ((2022, 2024), [2025, 2026])]


def suggest(trial, variant):
    p = {"sl_atr_period": trial.suggest_int("sl_atr_period", 10, 20),
         "sl_mult":       trial.suggest_float("sl_mult", 1.0, 3.5, step=0.25),
         "trail_period":  trial.suggest_int("trail_period", 5, 30),
         "trail_mult":    trial.suggest_float("trail_mult", 1.0, 3.5, step=0.25),
         "use_ichi_exit": trial.suggest_categorical("use_ichi_exit", [True, False]),
         "risk": RISK}
    if variant == "default":
        p["use_tp"] = 1
        p["tp_mult"] = trial.suggest_float("tp_mult", 1.5, 4.0, step=0.25)
    else:
        p["use_tp"] = 0; p["tp_mult"] = 0.0
    return p


def full_params(variant, params):
    p = dict(params); p["risk"] = RISK
    if variant == "default":
        p["use_tp"] = 1
    else:
        p["use_tp"] = 0; p["tp_mult"] = 0.0
    return p


def objective_value(m):
    pf = m["profit_factor"]; pfe = pf if np.isfinite(pf) else 10.0
    feasible = (m["sharpe"] >= SHARPE_MIN and pfe >= PF_MIN
                and m["max_dd_pct"] <= DD_MAX and m["trades"] >= TRADES_MIN)
    if feasible:
        return m["sharpe"], True
    viol = 0.0
    if m["sharpe"] < SHARPE_MIN: viol += (SHARPE_MIN - m["sharpe"])
    if pfe < PF_MIN: viol += (PF_MIN - pfe)
    if m["max_dd_pct"] > DD_MAX: viol += (m["max_dd_pct"] - DD_MAX) / DD_MAX
    if m["trades"] < TRADES_MIN: viol += (TRADES_MIN - m["trades"]) / TRADES_MIN
    return -viol, False


def run_fold(arr, cache, variant, t0, t1, py_train, n_trials, pop, seed):
    def objective(trial):
        p = suggest(trial, variant)
        pn, dd, ddp = b3.backtest_v3(arr, cache, p, t0, t1, START_BALANCE)
        m = b3.metrics_v3(pn, dd, ddp, py_train)
        return objective_value(m)[0]

    sampler = optuna.samplers.NSGAIISampler(seed=seed, population_size=pop)
    study = optuna.create_study(direction="maximize", sampler=sampler)
    study.optimize(objective, n_trials=n_trials, show_progress_bar=False)
    return study.best_params, study.best_value


def period_years(dt, s, e):
    return max((dt[e - 1] - dt[s]).total_seconds() / (365.25 * 86400.0), 1e-9)


def evaluate(arr, cache, variant, params, s, e, dt):
    p = full_params(variant, params)
    pn, dd, ddp = b3.backtest_v3(arr, cache, p, s, e, START_BALANCE)
    m = b3.metrics_v3(pn, dd, ddp, period_years(dt, s, e))
    return m, pn


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True)
    ap.add_argument("--trials", type=int, default=300)
    ap.add_argument("--pop", type=int, default=50)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--outdir", default=os.path.join(os.path.dirname(__file__), "results_v3"))
    args = ap.parse_args()
    os.makedirs(args.outdir, exist_ok=True)

    print("Nap du lieu...")
    df = b3.load_data(args.csv)
    arr = b3.to_arrays(df)
    cache = b3.IndicatorCache(arr)
    yb = b3.year_bounds(arr)
    dt = df["dt"].dt.to_pydatetime().tolist()   # list datetime de tinh so nam
    print(f"  {len(df):,} nen | {df['dt'].iloc[0]} -> {df['dt'].iloc[-1]}")

    # warm-up JIT
    _ = b3.backtest_v3(arr, cache, full_params("default",
        {"sl_atr_period": 14, "sl_mult": 2.0, "tp_mult": 2.0, "trail_period": 10, "trail_mult": 2.0,
         "use_ichi_exit": True}), yb[2010][0], yb[2011][1], START_BALANCE)

    out = {"default": [], "gong": []}
    oos = {"default": [], "gong": []}

    for variant in ("default", "gong"):
        print(f"\n===== BIEN THE: {variant.upper()} =====")
        for k, ((tr0, tr1), te) in enumerate(FOLDS, 1):
            if tr0 not in yb or tr1 not in yb or any(y not in yb for y in te):
                print(f"  Fold {k}: thieu du lieu, bo qua."); continue
            t0, t1 = yb[tr0][0], yb[tr1][1]
            e0, e1 = yb[te[0]][0], yb[te[-1]][1]
            pyt = period_years(dt, t0, t1)
            best, bv = run_fold(arr, cache, variant, t0, t1, pyt, args.trials, args.pop, args.seed)
            feasible = bv >= SHARPE_MIN - 1e-9
            m_tr, _ = evaluate(arr, cache, variant, best, t0, t1, dt)
            m_te, pn_te = evaluate(arr, cache, variant, best, e0, e1, dt)
            oos[variant].append(pn_te)
            te_lbl = f"{te[0]}" if len(te) == 1 else f"{te[0]}-{te[-1]}"
            out[variant].append({"fold": k, "train": f"{tr0}-{tr1}", "test": te_lbl,
                                 "feasible": bool(feasible), "params": best,
                                 "is": _c(m_tr), "oos": _c(m_te)})
            print(f"  Fold {k:2d} Tr{tr0}-{tr1}/Te{te_lbl} | IS Sh={m_tr['sharpe']:.2f} PF={m_tr['profit_factor']:.2f} "
                  f"DD={m_tr['max_dd_pct']:.1f}% n={m_tr['trades']} feas={feasible} | "
                  f"OOS Sh={m_te['sharpe']:.2f} PF={m_te['profit_factor']:.2f} net=${m_te['net']:.0f} n={m_te['trades']}")

    save(out, oos, dt, args.outdir)
    print(f"\nKet qua luu tai: {args.outdir}")


def _c(m):
    o = {}
    for k, v in m.items():
        if isinstance(v, float) and not np.isfinite(v): o[k] = None
        elif isinstance(v, float): o[k] = round(v, 4)
        else: o[k] = v
    return o


def _stitch(pnls_list):
    p = np.concatenate(pnls_list) if pnls_list else np.empty(0)
    n = len(p)
    if n == 0: return dict(trades=0, net=0.0, pf=0.0, dd=0.0, sharpe=0.0, wr=0.0)
    eq = START_BALANCE + np.cumsum(p)
    peak = np.maximum.accumulate(np.concatenate(([START_BALANCE], eq)))[1:]
    dd = float(((peak - eq) / peak).max() * 100)
    gp = p[p > 0].sum(); gl = -p[p < 0].sum()
    pf = gp / gl if gl > 0 else float("inf")
    R = p / RISK; sd = R.std(ddof=1) if n > 1 else 0.0
    # nam OOS ghep ~ so nam test (13 fold ~ 14 nam test 2013..2026)
    sharpe = (R.mean() / sd) * np.sqrt(n / 14.0) if sd > 0 else 0.0
    return dict(trades=n, net=float(p.sum()), pf=pf, dd=dd, sharpe=float(sharpe),
                wr=float((p > 0).mean() * 100), pnls=p)


def save(out, oos, dt, outdir):
    json.dump(out, open(os.path.join(outdir, "wfa_v3_results.json"), "w"), indent=2, ensure_ascii=False)
    st = {v: _stitch(oos[v]) for v in ("default", "gong")}

    def fmt(x): return "∞" if x is None or (isinstance(x, float) and not np.isfinite(x)) else f"{x:.2f}"

    L = ["# WFA + Optuna (NSGA-II) — Ichimoku TK-cross | 1R=$20 gom spread\n",
         "**Muc tieu:** toi da hoa Annualized Sharpe (R-multiple) tren Train.  ",
         f"**Loc Train:** Sharpe>={SHARPE_MIN}, PF>={PF_MIN}, MaxDD<={DD_MAX}%, Trades>={TRADES_MIN}.  ",
         f"**Von ${START_BALANCE:.0f}, 1R=${RISK:.0f}.** Ichimoku khoa 9/26/52, bo loc mau may.  ",
         "**Sharpe (annualized) = mean(R)/std(R) × √(so lenh/nam)**, R = PnL/1R (Van Tharp).\n"]

    for variant, title in (("default", "DEFAULT (TP cung = tp_mult × R)"),
                           ("gong", "GONG LOI (bo TP, thoat theo Slow Trail)")):
        L.append(f"\n## Bien the: {title}\n")
        L.append("| Fold | Train | Test | IS feas | IS Sharpe | IS PF | IS DD% | IS lenh | "
                 "OOS Sharpe | OOS PF | OOS DD% | OOS lenh | OOS net |")
        L.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
        for r in out[variant]:
            i, o = r["is"], r["oos"]
            L.append(f"| {r['fold']} | {r['train']} | {r['test']} | {'✅' if r['feasible'] else '❌'} | "
                     f"{fmt(i['sharpe'])} | {fmt(i['profit_factor'])} | {fmt(i['max_dd_pct'])} | {i['trades']} | "
                     f"{fmt(o['sharpe'])} | {fmt(o['profit_factor'])} | {fmt(o['max_dd_pct'])} | {o['trades']} | "
                     f"${fmt(o['net'])} |")
        s = st[variant]
        feas = sum(1 for r in out[variant] if r["feasible"])
        win = sum(1 for r in out[variant] if (r["oos"]["net"] or 0) > 0)
        L.append(f"\n**OOS ghep ({variant}):** net ${s['net']:.0f} ({s['net']/START_BALANCE*100:.0f}%), "
                 f"PF {fmt(s['pf'])}, MaxDD {s['dd']:.1f}%, Sharpe {s['sharpe']:.2f}, "
                 f"WR {s['wr']:.0f}%, {s['trades']} lenh. "
                 f"IS hop le {feas}/{len(out[variant])} fold, OOS co lai {win}/{len(out[variant])} fold.")

    # so sanh
    d, g = st["default"], st["gong"]
    L.append("\n## So sanh DEFAULT vs GONG (OOS ghep 2013-2026)\n")
    L.append("| Chi so | DEFAULT (TP cung) | GONG (Slow Trail) |")
    L.append("|---|---|---|")
    L.append(f"| Net | ${d['net']:.0f} | ${g['net']:.0f} |")
    L.append(f"| Profit Factor | {fmt(d['pf'])} | {fmt(g['pf'])} |")
    L.append(f"| Max Drawdown % | {d['dd']:.1f}% | {g['dd']:.1f}% |")
    L.append(f"| Sharpe (annual) | {d['sharpe']:.2f} | {g['sharpe']:.2f} |")
    L.append(f"| Win rate | {d['wr']:.0f}% | {g['wr']:.0f}% |")
    L.append(f"| Tong lenh | {d['trades']} | {g['trades']} |")
    L.append("\n*Luu y: 2010 bat dau tu 19/05 va 2026 chi toi ~thang 6 (du lieu thuc).* ")
    open(os.path.join(outdir, "REPORT.md"), "w").write("\n".join(L))

    # CSV
    rows = ["variant,fold,train,test,feasible,IS_sharpe,IS_pf,IS_dd,IS_trades,OOS_sharpe,OOS_pf,OOS_dd,OOS_trades,OOS_net"]
    for v in ("default", "gong"):
        for r in out[v]:
            i, o = r["is"], r["oos"]
            rows.append(",".join(str(x) for x in [v, r["fold"], r["train"], r["test"], r["feasible"],
                i["sharpe"], i["profit_factor"], i["max_dd_pct"], i["trades"],
                o["sharpe"], o["profit_factor"], o["max_dd_pct"], o["trades"], o["net"]]))
    open(os.path.join(outdir, "wfa_v3_summary.csv"), "w").write("\n".join(rows))

    try:
        plot(st, outdir)
    except Exception as e:
        print("Loi ve bieu do:", e)

    print("\n----- OOS GHEP -----")
    for v in ("default", "gong"):
        s = st[v]
        print(f"  {v:8}: net ${s['net']:.0f} | PF {fmt(s['pf'])} | DD {s['dd']:.1f}% | "
              f"Sharpe {s['sharpe']:.2f} | WR {s['wr']:.0f}% | {s['trades']} lenh")


def plot(st, outdir):
    import matplotlib; matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(11, 6))
    for v, col in (("default", "#E65100"), ("gong", "#1565C0")):
        p = st[v]["pnls"]
        eq = np.concatenate(([START_BALANCE], START_BALANCE + np.cumsum(p)))
        ax.plot(eq, lw=1.5, color=col,
                label=f"{v} | net ${p.sum():.0f}, Sharpe {st[v]['sharpe']:.2f}, DD {st[v]['dd']:.0f}%")
    ax.axhline(START_BALANCE, color="#bbb", lw=0.7)
    ax.set_title("WFA OOS 2013-2026 (Ichimoku TK-cross) — DEFAULT (TP) vs GONG (Slow Trail)")
    ax.set_xlabel("So lenh OOS (theo thu tu)"); ax.set_ylabel("Balance ($)")
    ax.legend(); ax.grid(alpha=0.3)
    fig.tight_layout(); fig.savefig(os.path.join(outdir, "oos_default_vs_gong.png"), dpi=120)
    plt.close(fig)


if __name__ == "__main__":
    main()
