# Bộ công cụ kiểm định EDGE (thật hay ảo) + nhận diện chế độ thị trường

Phục vụ: khảo sát/mô tả dữ liệu, thống kê, kiểm tra độ bền, Monte Carlo, và phán định
chiến lược có **real edge** hay **fake edge**, có thể **live** được không.

## Module

| File | Chức năng |
|---|---|
| `mt5_report.py` | Parse **MT5 Strategy Tester Report (.xlsx)** → settings + summary + **per-trade P&L** (gộp deals scale-out theo vị thế). |
| `edge_stats.py` | Thống kê mô tả + **T-test** (E[R]>0), **Bootstrap** CI expectancy, **Monte Carlo** (so dư cuối/MaxDD/risk-of-ruin), **Runs test** & **Chi-square** (độc lập chuỗi W/L), hàm `verdict()`. |
| `market_regime.py` | **Hurst**, **Variance Ratio** (Lo-MacKinlay), autocorrelation, **Efficiency Ratio** (Kaufman), **%ADX>25** → kết luận trending / mean-reverting / random. |
| `run_analysis.py` | Chạy trọn bộ trên 3 report + regime EURUSD → `EDGE_REPORT.md` + biểu đồ. |

## Chạy

```bash
cd ea/analysis
python3 run_analysis.py          # parse 3 report uploaded + EURUSD CSV
# hoac dung module rieng:
python3 mt5_report.py            # kiem tra parser
```
Cần: `pandas numpy scipy matplotlib openpyxl`.

## Tiêu chí phán định "edge thật"
Phải hội đủ: **Expectancy(R) > 0**, **T-test p < 0.05** (một phía), **Bootstrap CI(E) không chứa 0**
(cận dưới > 0), và **Monte Carlo P(lãi) ≥ 95%**. Thiếu ⇒ edge yếu/ảo (có thể do may rủi).

## Kết quả lần chạy (EA ScaleOut, 2020–2026)

| Symbol | N | Win% | E(R) | PF | SQN | T-test p | Bootstrap CI(E) | MC P(lãi) | Phán định |
|---|---|---|---|---|---|---|---|---|---|
| EURUSD (in-sample) | 266 | 41% | +0.113 | 1.30 | 0.88 | 0.075 | [−0.04, +0.27] | 93% | Yếu/chưa chắc |
| GBPUSD (OOS) | 402 | 42% | −0.022 | 0.94 | −0.22 | 0.67 | [−0.12, +0.08] | 33% | Fake |
| USDJPY (OOS) | 294 | 41% | +0.043 | 1.11 | 0.37 | 0.26 | [−0.09, +0.18] | 73% | Fake |

**Kết luận:** 0/3 cặp đạt edge thật. EURUSD (in-sample) chỉ borderline (p=0.075, CI chứa 0);
GBPUSD/USDJPY (out-of-sample khác cặp tiền) **không có edge** → chiến lược không khái quát.
Regime EURUSD 2020–2026 = **gần ngẫu nhiên** (Hurst 0.53, VR<1, Efficiency 0.24) ⇒ thiếu xu hướng,
đúng môi trường mà trend-following thua. **Chưa nên live**.
