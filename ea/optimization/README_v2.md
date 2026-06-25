# WFA Optimization v2 — EA của người dùng (Ichimoku_ATR_EA.mq5)

Tối ưu hóa **EA do bạn tự viết** (entry = ATR Trail1×Trail2 cross + lọc mây Kumo,
SL = Slow Trail, TP theo R "gồng có trần", thoát khi ATR đảo chiều) bằng WFA + GA,
trên EURUSD H1 2010–2019.

> Khác với v1 (`README.md`, entry TK cross — đã **sụp đổ OOS**), bản v2 này tối ưu đúng
> logic EA của bạn và cho kết quả **out-of-sample bền vững**.

## Chiến lược (khớp đúng EA của bạn)

- **Trail1 (fast) / Trail2 (slow):** ATR Trailing Stop kiểu ceyhun, tính đệ quy (`ComputeTrail`).
- **Entry LONG:** Trail1 cắt lên Trail2 **và** giá đóng cửa trên mây Kumo. SHORT: đối xứng.
- **SL:** tại Slow Trail (Trail2) lúc vào = 1R. **TP:** `tp_rr` × R. **Thoát sớm:** khi có tín hiệu ATR ngược.
- Tín hiệu trên nến đã đóng, vào lệnh ở `open` nến kế (không nhìn trước). Drawdown mark-to-market.
  Spread dùng **giá trị lịch sử thật** từ dữ liệu.

## Phương pháp (đúng spec)

| Hạng mục | Cách làm |
|---|---|
| Phân rã dữ liệu | WFA cuộn chiếu 3:1, 7 lượt 2013→2019 OOS |
| Thuật toán | Genetic Algorithm |
| Hàm mục tiêu | Max Recovery Factor = NetProfit / MaxDrawdown |
| Lọc Train | PF ≥ 1.3 **và** MaxDD ≤ 15% **và** Trades ≥ 150 |

## Chống overfitting — chỉ tối ưu 5 tham số lõi

Bài học từ v1 (tối ưu 9 chiều → overfit nặng): bản v2 **chỉ tối ưu 5 tham số cốt lõi**
và **cố định** phần còn lại theo đúng default EA của bạn.

- **Tối ưu:** `fast_period`, `fast_mult`, `slow_period`, `slow_mult`, `tp_rr`.
- **Cố định:** Ichimoku 9/26/52/26; SL=Slow Trail; thoát-khi-ATR-đảo=bật; lọc mây=bật;
  trailing=tắt (gồng); commission=0; 1R=$50; vốn $5000 (1R = 1%).

Đồng thời chạy **baseline DEFAULT của EA** (fast5/0.5, slow10/3, TP=3R) để so sánh
xem việc tối ưu có thật sự cải thiện so với cấu hình gốc hay không.

## Kết quả (chi tiết trong `results_v2/REPORT.md`)

| OOS ghép 2013–2019 | Net | PF | MaxDD | **RF** | Win |
|---|---|---|---|---|---|
| **Tối ưu (WFA)** | +$2633 (+52.7%) | 1.22 | 9.6% | **4.43** | 38.5% |
| **Default EA** | +$1982 (+39.6%) | 1.18 | 9.2% | **4.11** | 38.9% |

- **7/7 lượt** Train đạt bộ lọc; **6/7 năm** OOS có lãi.
- `slow_mult` hội tụ ổn định quanh **~2.6–3.1** (≈ default 3.0) → vùng tham số bền.
- Tối ưu cải thiện ~33% net so với default, nhưng default **tự thân đã tốt** ⟹ edge nằm ở
  **chiến lược**, ít phụ thuộc tham số (rủi ro overfitting thấp).

## ⚠️ Cập nhật quan trọng: chạy mở rộng trên dữ liệu 2010–2026

Khi chạy lại trên bộ dữ liệu dài hơn (EURUSD H1 tới 2026-06, WFA tự sinh **14 cửa sổ**,
OOS 2013–2026 — xem `results_v2_2026/`), bức tranh đẹp của riêng 2013–2019 **không còn giữ được**:

| OOS ghép | Net | PF | MaxDD | RF | Số năm có lãi |
|---|---|---|---|---|---|
| **2013–2019** (7 năm) | +52.7% | 1.22 | ~10% | **4.43** | 6/7 |
| **2013–2026** (14 năm) | +39.5% | 1.09 | **24%** | **1.01** | 8/14 |

- Chiến lược **rất tốt 2013–2019** (net ≈ +$2760) nhưng **suy yếu rõ 2020–2026** (net ≈ −$787,
  chỉ 2/7 năm lãi), với chuỗi thua kéo dài **2021–2024** và drawdown thật ~24%.
- Tối ưu hóa **không** vượt được default ngay cả trên toàn kỳ ⟹ edge nằm ở chiến lược, và edge đó
  **đang phụ thuộc chế độ thị trường**. Đây là lý do *bắt buộc* phải test trên dữ liệu dài/mới.

## Chạy

```bash
cd ea/optimization
# 2010-2019:
python3 wfa_optimize_v2.py --csv EU_2010_2019.csv --pop 80 --gen 60 --seed 42 --outdir results_v2
# 2010-2026 (tu sinh cua so toi het du lieu):
python3 wfa_optimize_v2.py --csv EU_2010_2026.csv --pop 80 --gen 60 --seed 42 --outdir results_v2_2026
```

Xuất ra `results_v2/`: `REPORT.md`, `wfa_summary.csv`, `wfa_results.json`, `oos_equity_v2.png`.
Toàn bộ chạy ~15 giây.

## Cấu trúc code

- `backtester_v2.py` — engine numba khớp đúng EA (trail đệ quy, TP theo R, thoát-ATR-đảo).
  Tái dùng nạp data / cache chỉ báo / metrics từ `backtester.py`.
- `wfa_optimize_v2.py` — GA + WFA + baseline default + báo cáo & biểu đồ.

## Giả định & lưu ý

- Vốn $5000, 1R=$50 (1%). Các chỉ số %/PF/RF **bất biến theo tỉ lệ này** nên so sánh được
  với lần chạy v1 ($2000/$20).
- Chưa tính commission/swap (mặc định 0 — thêm `commission` trong params nếu cần).
- 1 lệnh/symbol; cho phép đảo lệnh trong cùng nến (giống EA).
- Kết quả tốt trên backtest **không đảm bảo** tương lai — bước kế tiếp nên là **forward-test demo**.
