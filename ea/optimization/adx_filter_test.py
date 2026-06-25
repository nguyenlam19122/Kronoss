"""So sanh tac dong cua loc ADX tren bo tham so DEFAULT (gong + Slow Trail),
tach theo che do thi truong 2013-2019 vs 2020-2026. Phep thu SACH (khong co GA lam nhieu)."""
import json, os, numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(__file__)
CFG = [("Khong ADX", "results_v2_gong_trail", "#9E9E9E"),
       ("ADX>=18",  "results_adx18", "#1565C0"),
       ("ADX>=20",  "results_adx20", "#2E7D32"),
       ("ADX>=25",  "results_adx25", "#C62828")]

def split(d):
    r = json.load(open(os.path.join(HERE, d, "wfa_results.json")))
    e = sum(w["oos_def"]["net"] for w in r if int(w["test"]) <= 2019)
    l = sum(w["oos_def"]["net"] for w in r if int(w["test"]) >= 2020)
    tr = sum(w["oos_def"]["trades"] for w in r)
    return e, l, e + l, tr

groups = ["2013-2019\n(che do trend)", "2020-2026\n(che do gan day)", "Tong 2013-2026"]
x = np.arange(len(groups)); w = 0.2
fig, ax = plt.subplots(figsize=(11, 6))
for i, (name, d, col) in enumerate(CFG):
    e, l, t, tr = split(d)
    ax.bar(x + (i - 1.5) * w, [e, l, t], w, color=col, label=f"{name} ({tr} lenh)")
ax.axhline(0, color="#333", lw=0.8)
ax.set_xticks(x); ax.set_xticklabels(groups)
ax.set_ylabel("Net P&L ($)  — von $5000, 1R=$50")
ax.set_title("Tac dong loc ADX (tham so DEFAULT, gong+Slow Trail) — EURUSD H1 OOS")
ax.legend(); ax.grid(axis="y", alpha=0.3)
for i, (name, d, col) in enumerate(CFG):
    e, l, t, _ = split(d)
    for j, v in enumerate([e, l, t]):
        ax.annotate(f"{v:.0f}", (x[j] + (i - 1.5) * w, v),
                    ha="center", va="bottom" if v >= 0 else "top", fontsize=7)
fig.tight_layout()
out = os.path.join(HERE, "adx_filter_compare.png")
fig.savefig(out, dpi=120)
print("saved", out)
for name, d, col in CFG:
    e, l, t, tr = split(d)
    print(f"{name:10} | 2013-19 ${e:6.0f} | 2020-26 ${l:7.0f} | Tong ${t:6.0f} | {tr} lenh")
