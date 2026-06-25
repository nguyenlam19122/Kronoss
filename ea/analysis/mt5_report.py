"""
Parser cho MT5 Strategy Tester Report (.xlsx) -> settings + summary metrics + per-trade P&L.

EA scale-out chot nhieu phan => 1 vi the co nhieu "deal". Ham nay gop deals thanh per-trade
bang cach theo doi khoi luong rong: vi the bat dau khi volume roi 0, ket thuc khi ve 0.
Per-trade net = tong (profit + swap + commission) cua cac deal trong vi the.  R = net / risk_money.
"""
import re
import numpy as np
import pandas as pd


def _num(x):
    """Lay so thuc dau tien trong chuoi (vd '588.73 (11.27%)' -> 588.73)."""
    if x is None:
        return np.nan
    s = str(x).replace(",", "")
    m = re.search(r"-?\d+\.?\d*", s)
    return float(m.group()) if m else np.nan


def _pct(x):
    """Lay % trong ngoac (vd '588.73 (11.27%)' -> 11.27)."""
    m = re.search(r"\(([-\d.]+)%\)", str(x))
    return float(m.group(1)) if m else np.nan


def parse_report(path, risk_money=20.0):
    raw = pd.read_excel(path, header=None)
    nrow, ncol = raw.shape

    # ---------- 1) settings (Inputs) + ket qua: quet label:value ----------
    labelmap = {}
    settings = {}
    for i in range(nrow):
        for j in range(ncol - 1):
            c = raw.iat[i, j]
            if isinstance(c, str):
                s = c.strip()
                if s.endswith(":"):
                    # value = o ben phai khong rong gan nhat
                    val = None
                    for k in range(j + 1, ncol):
                        v = raw.iat[i, k]
                        if pd.notna(v) and str(v).strip() != "":
                            val = v; break
                    labelmap[s[:-1].strip()] = val
                m = re.match(r"\s*(Inp\w+)\s*=\s*(.+)", str(c))
                if m:
                    settings[m.group(1)] = m.group(2).strip()

    def g(label):
        return labelmap.get(label, None)

    summary = dict(
        symbol=str(g("Symbol")), period=str(g("Period")),
        net_profit=_num(g("Total Net Profit")),
        gross_profit=_num(g("Gross Profit")), gross_loss=_num(g("Gross Loss")),
        profit_factor=_num(g("Profit Factor")),
        expected_payoff=_num(g("Expected Payoff")),
        sharpe=_num(g("Sharpe Ratio")), recovery=_num(g("Recovery Factor")),
        zscore=_num(g("Z-Score")),
        dd_abs=_num(g("Balance Drawdown Maximal")),
        dd_pct=_pct(g("Balance Drawdown Maximal")),
        total_trades=_num(g("Total Trades")),
        avg_win=_num(g("Average profit trade")), avg_loss=_num(g("Average loss trade")),
        largest_win=_num(g("Largest profit trade")), largest_loss=_num(g("Largest loss trade")),
        init_deposit=_num(g("Initial Deposit")),
    )

    # ---------- 2) bang Deals ----------
    hdr = None
    for i in range(nrow):
        rowvals = [str(x) for x in raw.iloc[i].tolist()]
        joined = " | ".join(rowvals)
        if "Time" in joined and "Deal" in joined and "Direction" in joined and "Profit" in joined:
            hdr = i; break
    if hdr is None:
        raise ValueError("Khong tim thay header bang Deals")

    cols = [str(x).strip() for x in raw.iloc[hdr].tolist()]
    idx = {c: k for k, c in enumerate(cols)}
    deals = []
    for i in range(hdr + 1, nrow):
        r = raw.iloc[i]
        direction = str(r[idx["Direction"]]).strip().lower()
        typ = str(r[idx["Type"]]).strip().lower()
        if direction not in ("in", "out"):
            continue
        deals.append(dict(
            time=pd.to_datetime(r[idx["Time"]], errors="coerce"),
            typ=typ, direction=direction,
            volume=_num(r[idx["Volume"]]), price=_num(r[idx["Price"]]),
            commission=_num(r[idx["Commission"]]) if "Commission" in idx else 0.0,
            swap=_num(r[idx["Swap"]]) if "Swap" in idx else 0.0,
            profit=_num(r[idx["Profit"]]),
        ))
    dl = pd.DataFrame(deals)

    # ---------- 3) gop deals -> per-trade (theo khoi luong rong ve 0) ----------
    trades = []
    cur = None
    net_vol = 0.0
    for _, d in dl.iterrows():
        signed = d["volume"] * (1 if d["typ"] == "buy" else -1)
        pnl = (0 if np.isnan(d["profit"]) else d["profit"]) + \
              (0 if np.isnan(d["swap"]) else d["swap"]) + \
              (0 if np.isnan(d["commission"]) else d["commission"])
        if cur is None:
            cur = dict(open_time=d["time"], dir=("long" if d["typ"] == "buy" else "short"),
                       pnl=pnl, ndeals=1)
            net_vol = signed
        else:
            cur["pnl"] += pnl; cur["ndeals"] += 1
            net_vol += signed
        if cur is not None and abs(net_vol) < 1e-6:   # vi the dong hoan toan
            cur["close_time"] = d["time"]
            trades.append(cur); cur = None; net_vol = 0.0
    if cur is not None:
        cur["close_time"] = dl.iloc[-1]["time"]; trades.append(cur)

    tdf = pd.DataFrame(trades)
    if len(tdf):
        tdf["R"] = tdf["pnl"] / risk_money
    return dict(settings=settings, summary=summary, deals=dl, trades=tdf, risk_money=risk_money)


if __name__ == "__main__":
    import sys
    base = "/root/.claude/uploads/bbed706c-291e-5ab8-bf65-d655e0c7b959/"
    files = {"GBPUSD": base + "b1833274-GU.xlsx",
             "EURUSD": base + "9f179fa6-k_t_qu__2.xlsx",
             "USDJPY": base + "46c16317-UJ.xlsx"}
    for name, f in files.items():
        r = parse_report(f)
        t = r["trades"]; s = r["summary"]
        print(f"\n=== {name} ({s['period']}) ===")
        print(f"  MT5 Total Trades={s['total_trades']:.0f}  Net={s['net_profit']:.2f}  PF={s['profit_factor']:.3f}")
        print(f"  Parsed trades={len(t)}  sum(pnl)={t['pnl'].sum():.2f}  "
              f"win%={(t['pnl']>0).mean()*100:.1f}  mean R={t['R'].mean():+.4f}")
