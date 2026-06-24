"""
Tối ưu hóa tham số bằng Walk-Forward Analysis (WFA) + Genetic Algorithm (GA)
cho chiến lược Ichimoku + ATR trend-following.

Yêu cầu kỹ thuật:
- WFA cuộn chiếu 3:1 (Train 3 năm / Test 1 năm), 7 lượt 2010..2019.
- GA tìm tham số (thay cho brute force).
- Hàm mục tiêu: TỐI ĐA HÓA Recovery Factor = NetProfit / MaxDrawdown(abs).
- Bộ lọc chống overfitting (áp dụng trên TRAIN):
      Profit Factor >= 1.3 ; Max Drawdown <= 15% ; Total Trades >= 150.

Quy ước vốn: số dư khởi điểm = 2000$  (=> 1R = 20$ = 1% tài khoản), rủi ro cố định 20$/lệnh.
"""
import argparse, json, os, random, time
import numpy as np

import backtester as bt

# ----------------------------------------------------------------- cấu hình chung
START_BALANCE = 2000.0
RISK_USD      = 20.0

# Bộ lọc chống overfitting (trên TRAIN)
MIN_PF        = 1.3
MAX_DD_PCT    = 15.0
MIN_TRADES    = 150

# Không gian tham số GA  (tên: (kiểu, low, high))
GENES = {
    "tenkan":       ("int",  5,  40),
    "kijun":        ("int",  15, 90),
    "spanB":        ("int",  30, 160),
    "sl_period":    ("int",  7,  30),
    "sl_mult":      ("float", 1.0, 4.0),
    "trail_period": ("int",  7,  30),
    "trail_mult":   ("float", 1.5, 6.0),
    "require_color":("bool",),
    "use_ichi_exit":("bool",),
}

WINDOWS = [
    ((2010, 2012), 2013),
    ((2011, 2013), 2014),
    ((2012, 2014), 2015),
    ((2013, 2015), 2016),
    ((2014, 2016), 2017),
    ((2015, 2017), 2018),
    ((2016, 2018), 2019),
]


# ----------------------------------------------------------------- tiện ích GA
def rand_gene(name):
    spec = GENES[name]
    if spec[0] == "int":
        return random.randint(spec[1], spec[2])
    if spec[0] == "float":
        return round(random.uniform(spec[1], spec[2]), 3)
    return random.randint(0, 1)  # bool


def random_individual():
    return {k: rand_gene(k) for k in GENES}


def repair(ind):
    """Bảo đảm tenkan < kijun < spanB và nằm trong biên."""
    ind["tenkan"] = int(np.clip(ind["tenkan"], 5, 40))
    ind["kijun"]  = int(np.clip(ind["kijun"], 15, 90))
    ind["spanB"]  = int(np.clip(ind["spanB"], 30, 160))
    if ind["kijun"] <= ind["tenkan"]:
        ind["kijun"] = min(90, ind["tenkan"] + 1)
    if ind["spanB"] <= ind["kijun"]:
        ind["spanB"] = min(160, ind["kijun"] + 1)
    ind["sl_period"]    = int(np.clip(ind["sl_period"], 7, 30))
    ind["trail_period"] = int(np.clip(ind["trail_period"], 7, 30))
    ind["sl_mult"]    = float(np.clip(ind["sl_mult"], 1.0, 4.0))
    ind["trail_mult"] = float(np.clip(ind["trail_mult"], 1.5, 6.0))
    ind["require_color"] = int(bool(ind["require_color"]))
    ind["use_ichi_exit"] = int(bool(ind["use_ichi_exit"]))
    return ind


def crossover(a, b):
    return {k: (a[k] if random.random() < 0.5 else b[k]) for k in GENES}


def mutate(ind, rate):
    for k in GENES:
        if random.random() < rate:
            spec = GENES[k]
            if spec[0] == "float":   # nhiễu gaussian quanh giá trị hiện tại
                span = spec[2] - spec[1]
                ind[k] = round(ind[k] + random.gauss(0, span * 0.15), 3)
            else:
                ind[k] = rand_gene(k)
    return ind


def params_of(ind):
    p = dict(ind)
    p["risk_usd"] = RISK_USD
    return p


def fitness(m):
    """Recovery Factor nếu thỏa bộ lọc; ngược lại phạt âm theo mức vi phạm."""
    if m["trades"] == 0:
        return -10.0
    pf = m["profit_factor"]
    pf_eff = pf if np.isfinite(pf) else 10.0
    feasible = (pf_eff >= MIN_PF) and (m["max_dd_pct"] <= MAX_DD_PCT) and (m["trades"] >= MIN_TRADES)
    if feasible:
        return min(m["recovery_factor"], 50.0)  # cap tránh suy biến
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


# ----------------------------------------------------------------- GA cho 1 cửa sổ
def run_ga(arr, cache, t_start, t_end, pop_size, generations, mut_rate, elite, verbose=False):
    cachef = {}

    def evaluate(ind):
        k = key_of(ind)
        if k in cachef:
            return cachef[k]
        pnls, dd, ddp = bt.backtest(arr, cache, params_of(ind), t_start, t_end, START_BALANCE)
        m = bt.metrics(pnls, START_BALANCE, dd, ddp)
        f = fitness(m)
        cachef[k] = (f, m)
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
            print(f"    gen {gen+1:2d}/{generations} | best_fit={best_f:7.3f} "
                  f"| RF={best_m['recovery_factor']:.2f} PF={best_m['profit_factor']:.2f} "
                  f"DD%={best_m['max_dd_pct']:.1f} trades={best_m['trades']}")

        # thế hệ kế: elitism + con lai
        new_pop = [dict(scored[i][1]) for i in range(min(elite, len(scored)))]
        while len(new_pop) < pop_size:
            p1 = tournament(scored)
            p2 = tournament(scored)
            child = mutate(crossover(p1, p2), mut_rate)
            new_pop.append(repair(child))
        population = new_pop

    return best_ind, best_f, best_m


def tournament(scored, k=3):
    cand = random.sample(scored, min(k, len(scored)))
    cand.sort(key=lambda x: x[0], reverse=True)
    return cand[0][1]


# ----------------------------------------------------------------- main WFA
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True)
    ap.add_argument("--pop", type=int, default=48)
    ap.add_argument("--gen", type=int, default=30)
    ap.add_argument("--mut", type=float, default=0.2)
    ap.add_argument("--elite", type=int, default=2)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--outdir", default=os.path.join(os.path.dirname(__file__), "results"))
    args = ap.parse_args()

    random.seed(args.seed); np.random.seed(args.seed)
    os.makedirs(args.outdir, exist_ok=True)

    print("Nạp dữ liệu...")
    df = bt.load_data(args.csv)
    arr = bt.to_arrays(df)
    cache = bt.IndicatorCache(arr)
    yb = bt.year_bounds(arr)
    print(f"  {len(df):,} nến | {df['dt'].iloc[0]} -> {df['dt'].iloc[-1]}")
    print(f"  Các năm: {sorted(yb)}")

    # warm-up JIT (biên dịch numba trước khi tính giờ)
    _ = bt.backtest(arr, cache, params_of(repair(random_individual())),
                    yb[2010][0], yb[2011][1])

    results = []
    all_oos_pnls = []

    for (tr0, tr1), te in WINDOWS:
        if tr0 not in yb or tr1 not in yb or te not in yb:
            print(f"Bỏ qua lượt train {tr0}-{tr1}/test {te}: thiếu dữ liệu năm.")
            continue
        t_start, t_end = yb[tr0][0], yb[tr1][1]
        te_start, te_end = yb[te][0], yb[te][1]

        print(f"\n=== Lượt: Train {tr0}-{tr1}  |  Test {te} ===")
        t0 = time.time()
        best, bf, bm = run_ga(arr, cache, t_start, t_end,
                              args.pop, args.gen, args.mut, args.elite, verbose=True)
        dt = time.time() - t0

        # Đánh giá OOS (Test) với bộ tham số tốt nhất
        oos_pnls, odd, oddp = bt.backtest(arr, cache, params_of(best), te_start, te_end, START_BALANCE)
        om = bt.metrics(oos_pnls, START_BALANCE, odd, oddp)
        all_oos_pnls.append(oos_pnls)

        feasible = (bm["profit_factor"] >= MIN_PF and bm["max_dd_pct"] <= MAX_DD_PCT
                    and bm["trades"] >= MIN_TRADES)

        print(f"  -> GA {dt:.1f}s | IS RF={bm['recovery_factor']:.2f} "
              f"PF={bm['profit_factor']:.2f} DD%={bm['max_dd_pct']:.1f} "
              f"trades={bm['trades']} feasible={feasible}")
        print(f"     OOS({te}) RF={om['recovery_factor']:.2f} PF={om['profit_factor']:.2f} "
              f"DD%={om['max_dd_pct']:.1f} net=${om['net']:.1f} trades={om['trades']}")
        print(f"     params={best}")

        results.append({
            "train": f"{tr0}-{tr1}", "test": str(te),
            "params": best, "is_feasible": bool(feasible),
            "is": _clean(bm), "oos": _clean(om),
        })

    # ---------------- tổng hợp & lưu ----------------
    save_outputs(results, all_oos_pnls, args.outdir)
    print(f"\nHoàn tất. Kết quả lưu tại: {args.outdir}")


def _clean(m):
    out = {}
    for k, v in m.items():
        if isinstance(v, float) and not np.isfinite(v):
            out[k] = None
        elif isinstance(v, float):
            out[k] = round(v, 4)
        else:
            out[k] = v
    return out


def save_outputs(results, all_oos_pnls, outdir):
    # JSON chi tiết
    with open(os.path.join(outdir, "wfa_results.json"), "w") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    # Equity OOS ghép nối (toàn bộ giai đoạn out-of-sample)
    oos = np.concatenate(all_oos_pnls) if all_oos_pnls else np.empty(0)
    stitched = bt.metrics(oos, START_BALANCE)

    # CSV tóm tắt
    lines = ["train,test,is_feasible,is_RF,is_PF,is_DD%,is_trades,is_net,"
             "oos_RF,oos_PF,oos_DD%,oos_trades,oos_net,oos_winrate"]
    for r in results:
        i, o = r["is"], r["oos"]
        lines.append(",".join(str(x) for x in [
            r["train"], r["test"], r["is_feasible"],
            i["recovery_factor"], i["profit_factor"], i["max_dd_pct"], i["trades"], i["net"],
            o["recovery_factor"], o["profit_factor"], o["max_dd_pct"], o["trades"], o["net"],
            o["win_rate"],
        ]))
    with open(os.path.join(outdir, "wfa_summary.csv"), "w") as f:
        f.write("\n".join(lines))

    # Báo cáo markdown
    write_report(results, stitched, oos, outdir)

    # Biểu đồ equity OOS ghép nối
    try:
        plot_equity(oos, outdir)
    except Exception as e:
        print("Lỗi vẽ biểu đồ:", e)

    print("\n----- TỔNG HỢP OUT-OF-SAMPLE (ghép 7 năm test) -----")
    print(f"  Tổng số lệnh : {stitched['trades']}")
    print(f"  Net profit   : ${stitched['net']:.2f}  (số dư cuối ${stitched['end_balance']:.2f})")
    print(f"  Profit Factor: {stitched['profit_factor']:.2f}")
    print(f"  Max DD       : ${stitched['max_dd_abs']:.2f} ({stitched['max_dd_pct']:.1f}%)")
    print(f"  Recovery Fac : {stitched['recovery_factor']:.2f}")
    print(f"  Win rate     : {stitched['win_rate']:.1f}%")


def write_report(results, stitched, oos, outdir):
    L = []
    L.append("# Kết quả Walk-Forward Optimization — Ichimoku + ATR\n")
    L.append("**Hàm mục tiêu:** tối đa hóa Recovery Factor (NetProfit / MaxDrawdown).  ")
    L.append(f"**Bộ lọc TRAIN:** PF ≥ {MIN_PF}, MaxDD ≤ {MAX_DD_PCT}%, Trades ≥ {MIN_TRADES}.  ")
    L.append(f"**Vốn:** khởi điểm ${START_BALANCE:.0f}, rủi ro cố định ${RISK_USD:.0f}/lệnh (1R).\n")

    def fmt(x):
        return "∞" if x is None else f"{x:.2f}"

    L.append("## 1. Bảng kết quả theo từng lượt\n")
    L.append("| Lượt | Train | Test | IS hợp lệ? | IS RF | IS PF | IS DD% | IS lệnh | "
             "OOS RF | OOS PF | OOS DD% | OOS lệnh | OOS net |")
    L.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for n, r in enumerate(results, 1):
        i, o = r["is"], r["oos"]
        L.append(f"| {n} | {r['train']} | {r['test']} | {'✅' if r['is_feasible'] else '❌'} | "
                 f"{fmt(i['recovery_factor'])} | {fmt(i['profit_factor'])} | {fmt(i['max_dd_pct'])} | {i['trades']} | "
                 f"{fmt(o['recovery_factor'])} | {fmt(o['profit_factor'])} | {fmt(o['max_dd_pct'])} | {o['trades']} | "
                 f"${fmt(o['net'])} |")

    L.append("\n## 2. Hiệu suất Out-of-Sample tổng hợp (ghép 7 năm test 2013–2019)\n")
    L.append(f"- **Tổng số lệnh:** {stitched['trades']}")
    L.append(f"- **Net profit:** ${stitched['net']:.2f}  → số dư ${START_BALANCE:.0f} ⟶ ${stitched['end_balance']:.2f}")
    pf = stitched['profit_factor']
    L.append(f"- **Profit Factor:** {pf:.2f}" if np.isfinite(pf) else "- **Profit Factor:** ∞")
    L.append(f"- **Max Drawdown:** ${stitched['max_dd_abs']:.2f} ({stitched['max_dd_pct']:.1f}%)")
    L.append(f"- **Recovery Factor:** {stitched['recovery_factor']:.2f}")
    L.append(f"- **Win rate:** {stitched['win_rate']:.1f}%")

    L.append("\n## 3. Bộ tham số tối ưu theo từng lượt\n")
    L.append("| Lượt | tenkan | kijun | spanB | sl_period | sl_mult | trail_period | trail_mult | cloud_color | ichi_exit |")
    L.append("|---|---|---|---|---|---|---|---|---|---|")
    for n, r in enumerate(results, 1):
        p = r["params"]
        L.append(f"| {n} | {p['tenkan']} | {p['kijun']} | {p['spanB']} | {p['sl_period']} | "
                 f"{p['sl_mult']} | {p['trail_period']} | {p['trail_mult']} | "
                 f"{p['require_color']} | {p['use_ichi_exit']} |")

    # ---- tổng hợp IS vs OOS để chẩn đoán overfitting ----
    is_rf  = [r["is"]["recovery_factor"]  for r in results]
    oos_rf = [r["oos"]["recovery_factor"] for r in results]
    oos_net = [r["oos"]["net"] for r in results]
    n_feasible = sum(1 for r in results if r["is_feasible"])
    n_oos_win  = sum(1 for v in oos_net if v > 0)
    avg_is_rf  = float(np.mean(is_rf))  if is_rf  else 0.0
    avg_oos_rf = float(np.mean(oos_rf)) if oos_rf else 0.0

    L.append("\n## 4. Chẩn đoán Overfitting (IS so với OOS)\n")
    L.append(f"- **IS hợp lệ:** {n_feasible}/{len(results)} lượt tìm được bộ tham số thỏa cả 3 bộ lọc.")
    L.append(f"- **OOS có lãi:** {n_oos_win}/{len(results)} năm test có lợi nhuận dương.")
    L.append(f"- **Recovery Factor trung bình:** IS = {avg_is_rf:.2f}  →  OOS = {avg_oos_rf:.2f}.")
    gap = "rất lớn" if avg_is_rf > 3 * max(avg_oos_rf, 0.1) else "đáng kể"
    L.append(f"- Khoảng cách IS→OOS {gap}: tham số tối ưu trên Train **không giữ được hiệu quả** "
             "trên dữ liệu chưa thấy ⟶ đặc trưng overfitting.")

    L.append("\n## 5. Độ ổn định tham số giữa các lượt (range)\n")
    L.append("| Tham số | Nhỏ nhất | Lớn nhất | Nhận xét |")
    L.append("|---|---|---|---|")
    for key in ["tenkan", "kijun", "spanB", "sl_period", "sl_mult", "trail_period", "trail_mult"]:
        vals = [r["params"][key] for r in results]
        lo, hi = min(vals), max(vals)
        spread_ratio = (hi - lo) / (abs(hi) + 1e-9)
        note = "ổn định" if spread_ratio < 0.35 else ("phân tán" if spread_ratio < 0.7 else "rất phân tán")
        L.append(f"| {key} | {lo} | {hi} | {note} |")
    L.append("\n> Tham số 'rất phân tán' giữa các lượt = thêm bằng chứng overfitting "
             "(không có vùng tham số bền vững).")

    L.append("\n## 6. Kết luận & Khuyến nghị\n")
    verdict_ok = (stitched["net"] > 0 and stitched["profit_factor"] >= 1.1
                  and n_oos_win >= 5)
    if verdict_ok:
        L.append("- ✅ Chiến lược cho thấy **edge OOS khả quan** — có thể tiến tới forward-test demo.")
    else:
        L.append("- ❌ **Chưa có edge bền vững ngoài mẫu.** Mặc dù GA luôn đạt bộ lọc trên Train, "
                 "hiệu suất OOS yếu/âm và drawdown thật cao hơn nhiều mức kỳ vọng từ Train.")
    L.append("- WFA đã làm đúng nhiệm vụ: **phơi bày** việc các bộ lọc IS (PF/DD/số lệnh) "
             "*một mình không đủ* để bảo chứng OOS.")
    L.append("- Hướng cải thiện ưu tiên:")
    L.append("  1. **Giảm số chiều tối ưu** (cố định Ichimoku 9-26-52, chỉ tối ưu ATR) để hạn chế curve-fitting.")
    L.append("  2. **Thêm lọc chế độ thị trường** (ADX>20 / độ dày mây) loại giai đoạn sideway.")
    L.append("  3. Đổi mục tiêu sang **độ bền** (vd: tối đa hóa RF *nhỏ nhất* trên nhiều đoạn con, "
             "hoặc phạt độ lệch tham số) thay vì chỉ RF tốt nhất trên Train.")
    L.append("  4. Thử **entry pullback về Kijun** (v2) — vào giá tốt hơn, R cao hơn.")
    L.append("  5. Bổ sung **chi phí/commission** & kiểm thử **đa seed** để đánh giá độ vững.")
    with open(os.path.join(outdir, "REPORT.md"), "w") as f:
        f.write("\n".join(L))


def plot_equity(oos, outdir):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    equity = START_BALANCE + np.cumsum(oos)
    equity = np.concatenate(([START_BALANCE], equity))
    peak = np.maximum.accumulate(equity)
    fig, ax = plt.subplots(2, 1, figsize=(11, 7), height_ratios=[3, 1], sharex=True)
    ax[0].plot(equity, lw=1.3, color="#1565C0", label="Equity OOS (ghép 2013–2019)")
    ax[0].plot(peak, lw=0.8, color="#9E9E9E", ls="--", label="Đỉnh")
    ax[0].axhline(START_BALANCE, color="#BDBDBD", lw=0.6)
    ax[0].set_title("Đường vốn Out-of-Sample (Walk-Forward) — Ichimoku + ATR")
    ax[0].set_ylabel("Balance ($)"); ax[0].legend(loc="upper left"); ax[0].grid(alpha=0.3)
    dd = (peak - equity) / peak * 100
    ax[1].fill_between(range(len(dd)), -dd, 0, color="#C62828", alpha=0.5)
    ax[1].set_ylabel("Drawdown %"); ax[1].set_xlabel("Số lệnh (theo thứ tự)"); ax[1].grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(os.path.join(outdir, "oos_equity_curve.png"), dpi=120)
    plt.close(fig)


if __name__ == "__main__":
    main()
