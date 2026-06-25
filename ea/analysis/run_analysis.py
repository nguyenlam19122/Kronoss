"""
Chay toan bo phan tich: parse 3 MT5 report -> kiem dinh edge that/ao (T-test, bootstrap,
Monte Carlo, runs/chi-square) -> phan tich regime EURUSD 2020-2026 -> xuat REPORT + bieu do.
"""
import os, argparse, numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
import mt5_report as rep
import edge_stats as es
import market_regime as mr

UP = "/root/.claude/uploads/bbed706c-291e-5ab8-bf65-d655e0c7b959/"
REPORTS = {"EURUSD": UP + "9f179fa6-k_t_qu__2.xlsx",
           "GBPUSD": UP + "b1833274-GU.xlsx",
           "USDJPY": UP + "46c16317-UJ.xlsx"}
EU_CSV = UP + "826be848-EU.csv"
RISK = 20.0; START = 5000.0


def fnum(x, d=2):
    return "inf" if (isinstance(x, float) and not np.isfinite(x)) else f"{x:.{d}f}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--outdir", default=os.path.dirname(__file__))
    a = ap.parse_args(); os.makedirs(a.outdir, exist_ok=True)

    results = {}
    for name, f in REPORTS.items():
        r = rep.parse_report(f, RISK)
        R = r["trades"]["R"].to_numpy()
        v = es.verdict(R, RISK, START)
        results[name] = dict(parsed=r, R=R, v=v)

    # ---------------- console + report ----------------
    L = ["# Kiem dinh EDGE that hay ao — EA Ichimoku ATR ScaleOut (MT5, 2020-2026)\n",
         "Don vi phan tich = **per-trade R-multiple** (1R = $20). Du lieu = MT5 Strategy Tester.\n",
         "## 1. Tong hop & phan dinh\n",
         "| Symbol | N lenh | Win% | Expectancy | PF | SQN | T-test p (E>0) | Bootstrap CI(E) | MC P(lai) | MC MaxDD p95 | Phan dinh |",
         "|---|---|---|---|---|---|---|---|---|---|---|"]
    print("="*100)
    for name in REPORTS:
        d = results[name]["v"]["desc"]; tt = results[name]["v"]["ttest"]
        bs = results[name]["v"]["boot"]; mc = results[name]["v"]["mc"]; lab = results[name]["v"]["label"]
        L.append(f"| {name} | {d['n']} | {d['win_rate']:.0f}% | {d['expectancy_R']:+.3f}R | "
                 f"{fnum(d['profit_factor'])} | {d['sqn']:.2f} | {tt['p_one_sided']:.3f} | "
                 f"[{bs['ci_low']:+.3f}, {bs['ci_high']:+.3f}] | {mc['p_profit']*100:.0f}% | "
                 f"{mc['maxdd_p95']:.0f}% | **{lab}** |")
        print(f"\n### {name}  -> {lab}")
        print(f"  N={d['n']} Win={d['win_rate']:.1f}% E={d['expectancy_R']:+.4f}R PF={fnum(d['profit_factor'])} "
              f"SQN={d['sqn']:.2f} avg_win={d['avg_win']:+.2f}R avg_loss={d['avg_loss']:+.2f}R")
        print(f"  T-test: t={tt['t']:.2f} p1={tt['p_one_sided']:.4f} sig={tt['significant']}")
        print(f"  Bootstrap E: CI95=[{bs['ci_low']:+.4f},{bs['ci_high']:+.4f}] P(E>0)={bs['p_positive']*100:.1f}%")
        print(f"  MonteCarlo: net med=${mc['net_median']:.0f} [p5 ${mc['net_p05']:.0f}, p95 ${mc['net_p95']:.0f}] "
              f"P(lai)={mc['p_profit']*100:.1f}% MaxDD med={mc['maxdd_median']:.1f}% p95={mc['maxdd_p95']:.1f}% "
              f"P(ruin>{mc['ruin_dd_pct']:.0f}%)={mc['p_ruin']*100:.2f}%")
        rt = results[name]["v"]["runs"]; cs = results[name]["v"]["chi2"]
        print(f"  Runs test (doc lap W/L): z={rt['z']:.2f} p={rt['p']:.3f} phu_thuoc={rt['dependent']}")
        print(f"  Chi-square (streak):     chi2={cs['chi2']:.2f} p={cs['p']:.3f} phu_thuoc={cs['dependent']}")

    # ---------------- regime EURUSD 2020-2026 ----------------
    L.append("\n## 2. Thi truong co xu huong hay khong (EURUSD H1, 2020-2026)\n")
    reg = None
    try:
        df = pd.read_csv(EU_CSV, sep="\t")
        df.columns = [c.strip("<>").lower() for c in df.columns]
        df["dt"] = pd.to_datetime(df["date"] + " " + df["time"], format="%Y.%m.%d %H:%M:%S")
        d2 = df[df["dt"].dt.year >= 2020]
        reg = mr.analyze(close=d2["close"].to_numpy(), high=d2["high"].to_numpy(),
                         low=d2["low"].to_numpy(), open_=d2["open"].to_numpy())
        print("\n=== REGIME EURUSD 2020-2026 ===")
        for k, val in reg.items():
            print(f"  {k}: {val}")
        L.append(f"- **Hurst** = {fnum(reg['hurst'],3)}  (>0.5 trend, <0.5 hoi quy)")
        L.append(f"- **Variance Ratio(5)** = {fnum(reg['variance_ratio'],3)} (z={fnum(reg['vr_z'],2)})")
        L.append(f"- **Autocorr lag-1** = {fnum(reg['autocorr_lag1'],4)}")
        L.append(f"- **Efficiency Ratio** = {fnum(reg['efficiency_ratio'],3)}")
        L.append(f"- **ADX trung binh** = {fnum(reg['adx_mean'],1)} | **% thoi gian ADX>25** = {fnum(reg['adx_pct_above'],0)}%")
        L.append(f"- **Ket luan:** {reg['conclusion']}")
    except Exception as e:
        L.append(f"(Khong phan tich duoc regime: {e})")
        print("regime err", e)

    L.append("\n## 3. Doc ket qua\n")
    L.append("- **Edge that** can hoi du: Expectancy>0, T-test p<0.05, Bootstrap CI(E) khong chua 0 (can duoi>0), "
             "va Monte Carlo P(lai)>=95%. Thieu cac dieu nay => edge yeu/ao (co the do may rui).")
    L.append("- **Runs/Chi-square**: p<0.05 => chuoi thang/thua KHONG doc lap (co streak) — anh huong rui ro "
             "chuoi thua lien tiep, can tinh trong sizing.")
    L.append("- **Live duoc khong**: nhin Monte Carlo MaxDD p95 va P(ruin) — neu MaxDD p95 vuot suc chiu dung "
             "hoac P(lai)<60% thi khong nen chay live du backtest duong.")

    # ---------------- ket luan tong ----------------
    n_real = sum(1 for n in REPORTS if results[n]["v"]["label"] == "REAL EDGE")
    L.append("\n## 4. Ket luan tong\n")
    L.append(f"- **{n_real}/3 cap tien co edge that** theo tieu chi nghiem ngat.")
    L.append("- **EURUSD** la cap **in-sample** (chien luoc da duoc toi uu tren chinh no) => ket qua duong "
             "(E=+0.11R) co the do **selection bias**; T-test p=0.075 va bootstrap CI van **chua 0** => CHUA du y nghia thong ke.")
    L.append("- **GBPUSD & USDJPY** la **out-of-sample (cap tien khac)** — phep thu bao tong that su: ca hai "
             "**khong co edge** (GBPUSD am, USDJPY trong vung nhieu). Chien luoc **khong khai quat** sang cap khac.")
    if reg is not None:
        L.append(f"- Phu hop voi regime: EURUSD 2020-2026 **{reg['conclusion']}** (Hurst~{fnum(reg['hurst'],2)}, "
                 f"VR<1, Efficiency thap) — moi truong **thieu xu huong**, dung kieu thi truong ma trend-following thua.")
    L.append("- **Phan dinh chung: edge phan lon la FAKE/overfit + phu thuoc regime.** Khong nen chay live "
             "voi tien that o giai doan thi truong nhu 2020-2026; neu chay, chi demo/forward-test va bat buoc "
             "co bo loc che do thi truong (chi giao dich khi thuc su co trend).")

    open(os.path.join(a.outdir, "EDGE_REPORT.md"), "w").write("\n".join(L))
    _plots(results, a.outdir)
    print(f"\nLuu: {os.path.join(a.outdir,'EDGE_REPORT.md')} + bieu do")


def _plots(results, outdir):
    names = list(results)
    # R-distribution
    fig, ax = plt.subplots(1, 3, figsize=(15, 4.2))
    for i, n in enumerate(names):
        R = results[n]["R"]; d = results[n]["v"]["desc"]
        ax[i].hist(R, bins=40, color="#1565C0", alpha=0.8)
        ax[i].axvline(0, color="k", lw=0.8)
        ax[i].axvline(R.mean(), color="#C62828", ls="--", lw=1.2, label=f"E={R.mean():+.3f}R")
        ax[i].set_title(f"{n}  (N={d['n']}, SQN={d['sqn']:.2f})"); ax[i].set_xlabel("R"); ax[i].legend()
        ax[i].grid(alpha=0.3)
    fig.suptitle("Phan phoi R-multiple per-trade (2020-2026)")
    fig.tight_layout(); fig.savefig(os.path.join(outdir, "edge_R_distributions.png"), dpi=120); plt.close(fig)

    # Monte Carlo final-equity distribution
    fig, ax = plt.subplots(1, 3, figsize=(15, 4.2))
    for i, n in enumerate(names):
        mc = results[n]["v"]["mc"]; finals = mc["finals"]
        ax[i].hist(finals, bins=50, color="#2E7D32", alpha=0.8)
        ax[i].axvline(START, color="k", lw=1.0, label="von dau $5000")
        ax[i].axvline(np.percentile(finals, 5), color="#C62828", ls="--", lw=1, label="p5")
        ax[i].set_title(f"{n}  MC P(lai)={mc['p_profit']*100:.0f}%  MaxDD p95={mc['maxdd_p95']:.0f}%")
        ax[i].set_xlabel("So du cuoi ($)"); ax[i].legend(); ax[i].grid(alpha=0.3)
    fig.suptitle("Monte Carlo (10k resample) — phan phoi so du cuoi")
    fig.tight_layout(); fig.savefig(os.path.join(outdir, "edge_montecarlo.png"), dpi=120); plt.close(fig)


if __name__ == "__main__":
    main()
