"""
WFA + Optuna (NSGA-II) cho EXIT v5 (scale-out: SL + breakeven + partial TP + runner trailing).
Entry = ATR-cross EA goc (khoa fast5/0.5, slow10/3). 13 folds, muc tieu Sharpe (R-multiple),
loc Train Sharpe>=1/PF>=1.25/DD<=10%/>=150 lenh. Bao cao IS/OOS + Expectancy + phan phoi R.
"""
import argparse, json, os, numpy as np
import optuna
import backtester_v5 as b5
import backtester_v3 as b3

optuna.logging.set_verbosity(optuna.logging.WARNING)
START_BALANCE = 2000.0; RISK = 20.0
SHARPE_MIN, PF_MIN, DD_MAX, TRADES_MIN = 1.0, 1.25, 10.0, 150
ENTRY = {"fast_period": 5, "fast_mult": 0.5, "slow_period": 10, "slow_mult": 3.0}
FOLDS = [((2010, 2012), [2013]), ((2011, 2013), [2014]), ((2012, 2014), [2015]),
         ((2013, 2015), [2016]), ((2014, 2016), [2017]), ((2015, 2017), [2018]),
         ((2016, 2018), [2019]), ((2017, 2019), [2020]), ((2018, 2020), [2021]),
         ((2019, 2021), [2022]), ((2020, 2022), [2023]), ((2021, 2023), [2024]),
         ((2022, 2024), [2025, 2026])]


def suggest(trial):
    p = {"sl_atr_period": trial.suggest_int("sl_atr_period", 10, 20),
         "sl_mult":       trial.suggest_float("sl_mult", 1.0, 3.5, step=0.25),
         "be_trigger":    trial.suggest_float("be_trigger", 0.5, 2.0, step=0.25),
         "tp1_mult":      trial.suggest_float("tp1_mult", 1.0, 3.0, step=0.25),
         "partial_frac":  trial.suggest_categorical("partial_frac", [0.0, 0.25, 0.5, 0.75]),
         "trail_period":  trial.suggest_int("trail_period", 5, 30),
         "trail_mult":    trial.suggest_float("trail_mult", 1.0, 3.5, step=0.25)}
    p.update(ENTRY); p["risk"] = RISK
    return p


def full_params(params):
    p = dict(params); p.update(ENTRY); p["risk"] = RISK
    return p


def obj_val(m):
    pf = m["profit_factor"]; pfe = pf if np.isfinite(pf) else 10.0
    if (m["sharpe"] >= SHARPE_MIN and pfe >= PF_MIN and m["max_dd_pct"] <= DD_MAX and m["trades"] >= TRADES_MIN):
        return m["sharpe"]
    v = 0.0
    if m["sharpe"] < SHARPE_MIN: v += SHARPE_MIN - m["sharpe"]
    if pfe < PF_MIN: v += PF_MIN - pfe
    if m["max_dd_pct"] > DD_MAX: v += (m["max_dd_pct"] - DD_MAX) / DD_MAX
    if m["trades"] < TRADES_MIN: v += (TRADES_MIN - m["trades"]) / TRADES_MIN
    return -v


def py(dt, s, e):
    return max((dt[e - 1] - dt[s]).total_seconds() / (365.25 * 86400.0), 1e-9)


def run_fold(arr, cache, t0, t1, pyt, n, pop, seed):
    def f(trial):
        pn, dd, ddp = b5.backtest_v5(arr, cache, suggest(trial), t0, t1, START_BALANCE)
        return obj_val(b3.metrics_v3(pn, dd, ddp, pyt))
    st = optuna.create_study(direction="maximize",
                             sampler=optuna.samplers.NSGAIISampler(seed=seed, population_size=pop))
    st.optimize(f, n_trials=n, show_progress_bar=False)
    return st.best_params, st.best_value


def ev(arr, cache, params, s, e, dt):
    pn, dd, ddp = b5.backtest_v5(arr, cache, full_params(params), s, e, START_BALANCE)
    m = b3.metrics_v3(pn, dd, ddp, py(dt, s, e))
    m["expectancy"] = (m["net"] / m["trades"] / RISK) if m["trades"] else 0.0
    return m, pn


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--csv", required=True)
    ap.add_argument("--trials", type=int, default=350); ap.add_argument("--pop", type=int, default=50)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--outdir", default=os.path.join(os.path.dirname(__file__), "results_v5"))
    a = ap.parse_args(); os.makedirs(a.outdir, exist_ok=True)
    print("Nap du lieu..."); df = b5.load_data(a.csv); arr = b5.to_arrays(df)
    cache = b5.IndicatorCache(arr); yb = b5.year_bounds(arr)
    dt = df["dt"].dt.to_pydatetime().tolist()
    print(f"  {len(df):,} nen | {df['dt'].iloc[0]} -> {df['dt'].iloc[-1]}")
    _ = b5.backtest_v5(arr, cache, full_params({"sl_atr_period": 14, "sl_mult": 2.0, "be_trigger": 1.0,
        "tp1_mult": 1.5, "partial_frac": 0.5, "trail_period": 10, "trail_mult": 2.5}),
        yb[2010][0], yb[2011][1], START_BALANCE)

    rows = []; oos = []
    print("\n===== EXIT v5 (scale-out: SL + breakeven + partial + runner) =====")
    for k, ((tr0, tr1), te) in enumerate(FOLDS, 1):
        if tr0 not in yb or tr1 not in yb or any(y not in yb for y in te): continue
        t0, t1 = yb[tr0][0], yb[tr1][1]; e0, e1 = yb[te[0]][0], yb[te[-1]][1]
        best, bv = run_fold(arr, cache, t0, t1, py(dt, t0, t1), a.trials, a.pop, a.seed)
        feas = bv >= SHARPE_MIN - 1e-9
        mtr, _ = ev(arr, cache, best, t0, t1, dt); mte, pnte = ev(arr, cache, best, e0, e1, dt)
        oos.append(pnte)
        lbl = f"{te[0]}" if len(te) == 1 else f"{te[0]}-{te[-1]}"
        rows.append({"fold": k, "train": f"{tr0}-{tr1}", "test": lbl, "feasible": bool(feas),
                     "params": best, "is": _c(mtr), "oos": _c(mte)})
        print(f"  Fold {k:2d} Te{lbl} | IS Sh={mtr['sharpe']:.2f} E={mtr['expectancy']:+.3f}R "
              f"PF={mtr['profit_factor']:.2f} DD={mtr['max_dd_pct']:.1f}% n={mtr['trades']} feas={feas} | "
              f"OOS Sh={mte['sharpe']:.2f} E={mte['expectancy']:+.3f}R net=${mte['net']:.0f} n={mte['trades']}")
    save(rows, oos, a.outdir)
    print(f"\nKet qua: {a.outdir}")


def _c(m):
    return {k: (None if isinstance(v, float) and not np.isfinite(v) else (round(v, 4) if isinstance(v, float) else v))
            for k, v in m.items()}


def _stitch(pl):
    p = np.concatenate(pl) if pl else np.empty(0); n = len(p)
    if n == 0: return dict(trades=0, net=0.0, pf=0.0, dd=0.0, sharpe=0.0, wr=0.0, exp=0.0, pnls=p)
    eq = START_BALANCE + np.cumsum(p)
    peak = np.maximum.accumulate(np.concatenate(([START_BALANCE], eq)))[1:]
    dd = float(((peak - eq) / peak).max() * 100)
    gp = p[p > 0].sum(); gl = -p[p < 0].sum(); pf = gp / gl if gl > 0 else float("inf")
    R = p / RISK; sd = R.std(ddof=1) if n > 1 else 0.0
    sh = (R.mean() / sd) * np.sqrt(n / 14.0) if sd > 0 else 0.0
    return dict(trades=n, net=float(p.sum()), pf=pf, dd=dd, sharpe=float(sh),
                wr=float((p > 0).mean() * 100), exp=float(R.mean()), pnls=p)


def save(rows, oos, outdir):
    json.dump(rows, open(os.path.join(outdir, "wfa_v5_results.json"), "w"), indent=2, ensure_ascii=False)
    s = _stitch(oos)

    def fmt(x): return "∞" if x is None or (isinstance(x, float) and not np.isfinite(x)) else f"{x:.2f}"
    L = ["# WFA + Optuna — EXIT v5 scale-out (entry ATR-cross EA goc)\n",
         "**Exit:** SL (gioi han lo) + breakeven sau +be_trigger R + partial TP tai +tp1_mult R "
         "+ runner gong theo ATR trail. 1R=$20 gom spread.  ",
         f"**Loc Train:** Sharpe>={SHARPE_MIN}, PF>={PF_MIN}, MaxDD<={DD_MAX}%, Trades>={TRADES_MIN}. "
         "Muc tieu: max Sharpe (R-multiple).\n",
         "| Fold | Train | Test | IS feas | IS Sharpe | IS Exp(R) | IS PF | IS DD% | IS n | "
         "OOS Sharpe | OOS Exp(R) | OOS PF | OOS DD% | OOS n | OOS net |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        i, o = r["is"], r["oos"]
        L.append(f"| {r['fold']} | {r['train']} | {r['test']} | {'✅' if r['feasible'] else '❌'} | "
                 f"{fmt(i['sharpe'])} | {i.get('expectancy',0):+.3f} | {fmt(i['profit_factor'])} | "
                 f"{fmt(i['max_dd_pct'])} | {i['trades']} | {fmt(o['sharpe'])} | {o.get('expectancy',0):+.3f} | "
                 f"{fmt(o['profit_factor'])} | {fmt(o['max_dd_pct'])} | {o['trades']} | ${fmt(o['net'])} |")
    feas = sum(1 for r in rows if r["feasible"]); win = sum(1 for r in rows if (r["oos"]["net"] or 0) > 0)
    L.append(f"\n**OOS ghep:** net ${s['net']:.0f} ({s['net']/START_BALANCE*100:.0f}%), Expectancy "
             f"{s['exp']:+.3f}R, PF {fmt(s['pf'])}, MaxDD {s['dd']:.1f}%, Sharpe {s['sharpe']:.2f}, "
             f"WR {s['wr']:.0f}%, {s['trades']} lenh. IS hop le {feas}/{len(rows)}, OOS co lai {win}/{len(rows)}.")
    open(os.path.join(outdir, "REPORT.md"), "w").write("\n".join(L))

    try:
        import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
        p = s["pnls"]; R = p / RISK
        fig, ax = plt.subplots(1, 2, figsize=(13, 5))
        eq = np.concatenate(([START_BALANCE], START_BALANCE + np.cumsum(p)))
        ax[0].plot(eq, color="#1565C0", lw=1.4)
        ax[0].axhline(START_BALANCE, color="#bbb", lw=0.7)
        ax[0].set_title(f"EXIT v5 — OOS equity (net ${p.sum():.0f}, Sharpe {s['sharpe']:.2f}, DD {s['dd']:.0f}%)")
        ax[0].set_xlabel("So lenh OOS"); ax[0].set_ylabel("Balance ($)"); ax[0].grid(alpha=0.3)
        ax[1].hist(R, bins=45, color="#2E7D32", alpha=0.8); ax[1].axvline(0, color="k", lw=0.8)
        ax[1].axvline(R.mean(), color="#C62828", lw=1.2, ls="--", label=f"Expectancy {R.mean():+.3f}R")
        ax[1].set_title("Phan phoi R-multiple OOS (exit v5)"); ax[1].set_xlabel("R"); ax[1].legend()
        ax[1].grid(alpha=0.3)
        fig.tight_layout(); fig.savefig(os.path.join(outdir, "exit_v5_oos.png"), dpi=120)
    except Exception as e:
        print("plot err", e)

    print(f"\n----- OOS GHEP (exit v5) -----")
    print(f"  net ${s['net']:.0f} | Expectancy {s['exp']:+.3f}R | PF {fmt(s['pf'])} | DD {s['dd']:.1f}% | "
          f"Sharpe {s['sharpe']:.2f} | WR {s['wr']:.0f}% | {s['trades']} lenh")


if __name__ == "__main__":
    main()
