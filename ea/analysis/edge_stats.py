"""
Kiem dinh EDGE that hay ao tu chuoi R-multiple cua tung lenh (Van Tharp).
Gom: thong ke mo ta, T-test (expectancy>0), Bootstrap CI, Monte Carlo (equity/DD/risk-of-ruin),
Runs test (Wald-Wolfowitz) va Chi-square cho tinh doc lap chuoi thang/thua.
"""
import numpy as np
from scipy import stats


# ----------------------------------------------------------------- mo ta
def describe(R):
    R = np.asarray(R, float); n = len(R)
    win = R > 0
    gp = R[R > 0].sum(); gl = -R[R < 0].sum()
    sd = R.std(ddof=1) if n > 1 else 0.0
    return dict(
        n=n, mean_R=float(R.mean()) if n else 0.0, std_R=float(sd),
        win_rate=float(win.mean() * 100) if n else 0.0,
        avg_win=float(R[win].mean()) if win.any() else 0.0,
        avg_loss=float(R[~win].mean()) if (~win).any() else 0.0,
        payoff=float(R[win].mean() / -R[~win].mean()) if win.any() and (~win).any() and R[~win].mean() != 0 else np.nan,
        profit_factor=float(gp / gl) if gl > 0 else np.inf,
        expectancy_R=float(R.mean()) if n else 0.0,
        sqn=float(R.mean() / sd * np.sqrt(min(n, 100))) if sd > 0 else 0.0,
        total_R=float(R.sum()),
    )


# ----------------------------------------------------------------- T-test
def t_test_expectancy(R):
    """H0: E[R]=0  vs  H1: E[R]>0 (mot phia). Tra ve t, p_one_sided."""
    R = np.asarray(R, float)
    if len(R) < 2 or R.std(ddof=1) == 0:
        return dict(t=0.0, p_one_sided=1.0, df=len(R) - 1, significant=False)
    t, p_two = stats.ttest_1samp(R, 0.0)
    p_one = p_two / 2 if t > 0 else 1 - p_two / 2
    return dict(t=float(t), p_one_sided=float(p_one), df=len(R) - 1,
                significant=bool(p_one < 0.05 and t > 0))


# ----------------------------------------------------------------- Bootstrap
def bootstrap_expectancy(R, n_boot=10000, seed=42):
    """CI 95% cua expectancy + xac suat E[R]>0 (lay mau co hoan lai)."""
    rng = np.random.default_rng(seed); R = np.asarray(R, float); n = len(R)
    if n < 2:
        return dict(ci_low=np.nan, ci_high=np.nan, p_positive=np.nan)
    means = R[rng.integers(0, n, size=(n_boot, n))].mean(axis=1)
    return dict(ci_low=float(np.percentile(means, 2.5)),
                ci_high=float(np.percentile(means, 97.5)),
                p_positive=float((means > 0).mean()),
                boot_mean=float(means.mean()))


# ----------------------------------------------------------------- Monte Carlo
def monte_carlo(R, risk_money=20.0, start_balance=5000.0, n_sims=10000, seed=42, ruin_dd_pct=50.0):
    """Lay mau co hoan lai thu tu lenh -> phan phoi: net, MaxDD%, P(lai), P(ruin)."""
    rng = np.random.default_rng(seed); R = np.asarray(R, float); n = len(R)
    if n < 2:
        return {}
    pnl = R * risk_money
    finals = np.empty(n_sims); maxdd = np.empty(n_sims); ruin = 0
    for s in range(n_sims):
        path = pnl[rng.integers(0, n, size=n)]
        eq = start_balance + np.cumsum(path)
        peak = np.maximum.accumulate(np.concatenate(([start_balance], eq)))[1:]
        dd = (peak - eq) / peak * 100.0
        finals[s] = eq[-1]; maxdd[s] = dd.max()
        if dd.max() >= ruin_dd_pct:
            ruin += 1
    return dict(
        net_median=float(np.median(finals) - start_balance),
        net_p05=float(np.percentile(finals, 5) - start_balance),
        net_p95=float(np.percentile(finals, 95) - start_balance),
        p_profit=float((finals > start_balance).mean()),
        maxdd_median=float(np.median(maxdd)), maxdd_p95=float(np.percentile(maxdd, 95)),
        p_ruin=float(ruin / n_sims), ruin_dd_pct=ruin_dd_pct,
        finals=finals, maxdds=maxdd)


# ----------------------------------------------------------------- Runs test
def runs_test(R):
    """Wald-Wolfowitz tren chuoi thang(+)/thua(-): kiem tinh doc lap (streak)."""
    R = np.asarray(R, float); s = np.where(R > 0, 1, 0)
    n1 = int(s.sum()); n2 = int(len(s) - n1); n = n1 + n2
    if n1 == 0 or n2 == 0:
        return dict(runs=0, z=0.0, p=1.0, dependent=False)
    runs = 1 + int(np.sum(s[1:] != s[:-1]))
    mu = 1 + 2 * n1 * n2 / n
    var = (2 * n1 * n2 * (2 * n1 * n2 - n)) / (n * n * (n - 1))
    z = (runs - mu) / np.sqrt(var) if var > 0 else 0.0
    p = 2 * (1 - stats.norm.cdf(abs(z)))
    return dict(runs=runs, expected_runs=float(mu), z=float(z), p=float(p),
                dependent=bool(p < 0.05))


# ----------------------------------------------------------------- Chi-square
def chi_square_streak(R):
    """Bang 2x2: ket qua lenh truoc (W/L) vs lenh sau (W/L). Kiem tinh doc lap."""
    R = np.asarray(R, float); w = (R > 0).astype(int)
    if len(w) < 3:
        return dict(chi2=0.0, p=1.0, dependent=False)
    prev, nxt = w[:-1], w[1:]
    tbl = np.zeros((2, 2), int)
    for a, b in zip(prev, nxt):
        tbl[a, b] += 1
    if (tbl.sum(0) == 0).any() or (tbl.sum(1) == 0).any():
        return dict(chi2=0.0, p=1.0, dependent=False, table=tbl.tolist())
    chi2, p, dof, _ = stats.chi2_contingency(tbl, correction=True)
    return dict(chi2=float(chi2), p=float(p), dof=int(dof),
                dependent=bool(p < 0.05), table=tbl.tolist())


# ----------------------------------------------------------------- Verdict
def verdict(R, risk_money=20.0, start_balance=5000.0):
    d = describe(R); tt = t_test_expectancy(R)
    bs = bootstrap_expectancy(R); mc = monte_carlo(R, risk_money, start_balance)
    rt = runs_test(R); cs = chi_square_streak(R)
    # tieu chi "edge that": expectancy>0 & T-test co y nghia & bootstrap CI duoi >0 & MC P(lai) cao
    real = (d["expectancy_R"] > 0 and tt["significant"]
            and bs["ci_low"] > 0 and mc.get("p_profit", 0) >= 0.95)
    weak = (d["expectancy_R"] > 0 and (tt["p_one_sided"] < 0.20) and mc.get("p_profit", 0) >= 0.6)
    label = "REAL EDGE" if real else ("WEAK / chua chac" if weak else "FAKE / khong du bang chung")
    return dict(desc=d, ttest=tt, boot=bs, mc=mc, runs=rt, chi2=cs, label=label)
