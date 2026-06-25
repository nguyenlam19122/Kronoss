"""
Xac dinh thi truong CO XU HUONG hay THIEU XU HUONG (mean-reverting/choppy) tu chuoi gia.
- Hurst exponent (R/S): >0.5 trending, ~0.5 ngau nhien, <0.5 hoi quy ve trung binh.
- Variance Ratio (Lo-MacKinlay): >1 trending, <1 mean-revert; kem z-stat.
- Autocorrelation lag-1 cua log return.
- Efficiency Ratio (Kaufman): cao = trend manh, thap = nhieu/sideway.
- % thoi gian ADX > nguong (suc manh xu huong).
"""
import numpy as np


def hurst_rs(returns):
    x = np.asarray(returns, float); x = x[np.isfinite(x)]; N = len(x)
    if N < 100:
        return np.nan
    ns = np.unique(np.floor(np.logspace(1, np.log10(N // 2), 18)).astype(int))
    pts = []
    for n in ns:
        k = N // n
        if k < 1 or n < 8:
            continue
        rs = []
        for i in range(k):
            seg = x[i * n:(i + 1) * n]
            z = seg - seg.mean(); Z = np.cumsum(z)
            R = Z.max() - Z.min(); S = seg.std()
            if S > 0:
                rs.append(R / S)
        if rs:
            pts.append((n, np.mean(rs)))
    if len(pts) < 4:
        return np.nan
    lx = np.log([p[0] for p in pts]); ly = np.log([p[1] for p in pts])
    return float(np.polyfit(lx, ly, 1)[0])


def variance_ratio(returns, k=5):
    r = np.asarray(returns, float); r = r[np.isfinite(r)]; n = len(r)
    if n < k * 3:
        return dict(vr=np.nan, z=np.nan)
    mu = r.mean()
    var1 = np.sum((r - mu) ** 2) / (n - 1)
    rk = np.convolve(r, np.ones(k), "valid")          # tong k-period returns
    m = n - k + 1
    vark = np.sum((rk - k * mu) ** 2) / (m * k)
    vr = vark / var1 if var1 > 0 else np.nan
    # z-stat (gia dinh phuong sai dong nhat)
    phi = 2 * (2 * k - 1) * (k - 1) / (3 * k * n)
    z = (vr - 1) / np.sqrt(phi) if phi > 0 else np.nan
    return dict(vr=float(vr), z=float(z))


def autocorr(returns, lag=1):
    r = np.asarray(returns, float); r = r[np.isfinite(r)]
    if len(r) < lag + 2:
        return np.nan
    return float(np.corrcoef(r[:-lag], r[lag:])[0, 1])


def efficiency_ratio(prices, period=20):
    p = np.asarray(prices, float)
    if len(p) < period + 1:
        return np.nan
    er = []
    for i in range(period, len(p)):
        change = abs(p[i] - p[i - period])
        vol = np.sum(np.abs(np.diff(p[i - period:i + 1])))
        if vol > 0:
            er.append(change / vol)
    return float(np.mean(er)) if er else np.nan


def adx_pct(high, low, close, period=14, threshold=25.0):
    h, l, c = map(lambda a: np.asarray(a, float), (high, low, close))
    n = len(c)
    if n < 3 * period:
        return dict(adx_mean=np.nan, pct_above=np.nan)
    tr = np.zeros(n); pdm = np.zeros(n); mdm = np.zeros(n)
    for i in range(1, n):
        up = h[i] - h[i - 1]; dn = l[i - 1] - l[i]
        pdm[i] = up if (up > dn and up > 0) else 0.0
        mdm[i] = dn if (dn > up and dn > 0) else 0.0
        tr[i] = max(h[i] - l[i], abs(h[i] - c[i - 1]), abs(l[i] - c[i - 1]))
    a = 1.0 / period
    str_ = tr[1:period + 1].sum(); spd = pdm[1:period + 1].sum(); smd = mdm[1:period + 1].sum()
    dx = np.full(n, np.nan)
    for i in range(period, n):
        if i > period:
            str_ += tr[i] - str_ * a; spd += pdm[i] - spd * a; smd += mdm[i] - smd * a
        pdi = 100 * spd / str_ if str_ > 0 else 0; mdi = 100 * smd / str_ if str_ > 0 else 0
        s = pdi + mdi; dx[i] = 100 * abs(pdi - mdi) / s if s > 0 else 0
    adx = np.full(n, np.nan); f = 2 * period
    if f < n:
        adx[f] = np.nanmean(dx[period:f + 1])
        for i in range(f + 1, n):
            adx[i] = adx[i - 1] * (1 - a) + dx[i] * a
    av = adx[np.isfinite(adx)]
    return dict(adx_mean=float(av.mean()) if len(av) else np.nan,
                pct_above=float((av > threshold).mean() * 100) if len(av) else np.nan,
                threshold=threshold)


def analyze(open_=None, high=None, low=None, close=None):
    close = np.asarray(close, float)
    logret = np.diff(np.log(close))
    H = hurst_rs(logret)
    vr = variance_ratio(logret, k=5)
    ac = autocorr(logret, 1)
    er = efficiency_ratio(close, 20)
    adx = adx_pct(high, low, close) if high is not None else dict(adx_mean=np.nan, pct_above=np.nan, threshold=25)
    # ket luan
    votes = []
    if np.isfinite(H): votes.append("trend" if H > 0.55 else ("revert" if H < 0.45 else "random"))
    if np.isfinite(vr["vr"]): votes.append("trend" if vr["vr"] > 1.05 else ("revert" if vr["vr"] < 0.95 else "random"))
    if np.isfinite(ac): votes.append("trend" if ac > 0.03 else ("revert" if ac < -0.03 else "random"))
    trend = votes.count("trend"); revert = votes.count("revert")
    if trend > revert and trend >= 2: concl = "CO XU HUONG (trending)"
    elif revert > trend and revert >= 2: concl = "THIEU XU HUONG / hoi quy (mean-reverting/choppy)"
    else: concl = "GAN NGAU NHIEN (random walk)"
    return dict(hurst=H, variance_ratio=vr["vr"], vr_z=vr["z"], autocorr_lag1=ac,
                efficiency_ratio=er, adx_mean=adx["adx_mean"], adx_pct_above=adx["pct_above"],
                conclusion=concl)
