# Walk-Forward Optimization — Ichimoku + ATR

Tối ưu hóa tham số cho chiến lược trend-following (Ichimoku lọc xu hướng + ATR trailing,
entry TK cross) bằng **Walk-Forward Analysis (WFA)** + **Genetic Algorithm (GA)**, trên
dữ liệu **EURUSD H1**.

## Phương pháp (đúng yêu cầu kỹ thuật)

| Hạng mục | Cách làm |
|---|---|
| Phân rã dữ liệu | WFA cuộn chiếu **3:1** (Train 3 năm / Test 1 năm), 7 lượt 2010→2019 |
| Thuật toán tối ưu | **Genetic Algorithm** (tournament + uniform crossover + mutation + elitism) |
| Hàm mục tiêu | **Tối đa hóa Recovery Factor** = NetProfit / MaxDrawdown(abs) |
| Lọc chống overfitting (Train) | PF ≥ 1.3 **và** MaxDD ≤ 15% **và** Total Trades ≥ 150 |

Các lượt WFA:

| Lượt | Train (In-Sample) | Test (Out-of-Sample) |
|---|---|---|
| 1 | 2010–2012 | 2013 |
| 2 | 2011–2013 | 2014 |
| 3 | 2012–2014 | 2015 |
| 4 | 2013–2015 | 2016 |
| 5 | 2014–2016 | 2017 |
| 6 | 2015–2017 | 2018 |
| 7 | 2016–2018 | 2019 |

## Tham số được GA tối ưu

`tenkan, kijun, spanB` (Ichimoku) · `sl_period, sl_mult` (SL ban đầu = 1R) ·
`trail_period, trail_mult` (ATR trailing) · `require_color`, `use_ichi_exit` (bật/tắt).
Ràng buộc: `tenkan < kijun < spanB`; displacement = kijun (chuẩn Ichimoku).

## Giả định mô phỏng (quan trọng)

- **Vốn khởi điểm:** $2000 → 1R = $20 = **1% tài khoản** (chọn để bộ lọc MaxDD ≤ 15% có ý nghĩa;
  vì rủi ro cố định theo $, %DD phụ thuộc số vốn này — đổi `START_BALANCE` để xem mức khác).
- **Rủi ro/lệnh:** cố định $20, khối lượng tính động, **đã cộng spread** vào khoảng SL.
- **Spread:** dùng **spread lịch sử thật** từ cột `<SPREAD>` của dữ liệu (points → giá), tính
  round-trip nửa spread khi vào và nửa khi ra.
- **Khớp lệnh:** tín hiệu trên nến đã đóng (i-1), vào lệnh tại `open` nến kế (không nhìn trước).
- **Drawdown:** tính theo equity **mark-to-market** (gồm lỗ/lãi nổi trong lệnh) — sát thực tế.
- **Chưa tính commission/swap** (có thể thêm 1 dòng trong `backtester.py`).

> Lưu ý dữ liệu: file thực bắt đầu **2010-05-19** (không phải 01/01), nên Train của lượt 1
> chỉ có ~7,5 tháng của năm 2010 (sau khi trừ warmup chỉ báo).

## Chạy

```bash
cd ea/optimization
python3 wfa_optimize.py --csv /đường/dẫn/EU.csv --pop 80 --gen 60 --seed 42
```

Tùy chọn: `--pop` (kích thước quần thể), `--gen` (số thế hệ), `--mut` (tỉ lệ đột biến),
`--elite`, `--seed`, `--outdir`. Toàn bộ 7 lượt chạy ~12 giây (numba + cache chỉ báo).

## Kết quả xuất ra (`results/`)

- `REPORT.md` — báo cáo đầy đủ: bảng IS/OOS, chẩn đoán overfitting, độ ổn định tham số, kết luận.
- `wfa_summary.csv` — bảng tóm tắt từng lượt.
- `wfa_results.json` — chi tiết tham số + mọi chỉ số.
- `oos_equity_curve.png` — đường vốn Out-of-Sample ghép 7 năm test + drawdown.

## Phụ thuộc

`numpy`, `pandas`, `numba`, `matplotlib`.

## Cấu trúc code

- `backtester.py` — nạp data, cache chỉ báo (Donchian/ATR), engine backtest numba, hàm metrics.
- `wfa_optimize.py` — GA, vòng lặp WFA, hàm mục tiêu + bộ lọc, xuất báo cáo & biểu đồ.
