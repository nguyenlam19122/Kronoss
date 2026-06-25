# Kết quả Walk-Forward Optimization — Ichimoku + ATR

**Hàm mục tiêu:** tối đa hóa Recovery Factor (NetProfit / MaxDrawdown).  
**Bộ lọc TRAIN:** PF ≥ 1.3, MaxDD ≤ 15.0%, Trades ≥ 150.  
**Vốn:** khởi điểm $2000, rủi ro cố định $20/lệnh (1R).

## 1. Bảng kết quả theo từng lượt

| Lượt | Train | Test | IS hợp lệ? | IS RF | IS PF | IS DD% | IS lệnh | OOS RF | OOS PF | OOS DD% | OOS lệnh | OOS net |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 2010-2012 | 2013 | ✅ | 9.68 | 2.02 | 3.92 | 166 | -0.05 | 0.98 | 12.69 | 68 | $-13.39 |
| 2 | 2011-2013 | 2014 | ✅ | 9.53 | 2.25 | 11.28 | 162 | 1.88 | 1.71 | 11.61 | 55 | $488.19 |
| 3 | 2012-2014 | 2015 | ✅ | 8.92 | 1.74 | 1.88 | 183 | 0.64 | 1.34 | 4.00 | 54 | $51.84 |
| 4 | 2013-2015 | 2016 | ✅ | 16.25 | 2.16 | 7.44 | 260 | -1.00 | 0.39 | 32.24 | 78 | $-641.86 |
| 5 | 2014-2016 | 2017 | ✅ | 10.14 | 1.88 | 4.77 | 197 | 0.02 | 1.01 | 8.33 | 56 | $2.65 |
| 6 | 2015-2017 | 2018 | ✅ | 11.78 | 2.21 | 1.82 | 160 | -0.49 | 0.80 | 3.05 | 48 | $-30.18 |
| 7 | 2016-2018 | 2019 | ✅ | 12.33 | 1.85 | 2.05 | 227 | -0.39 | 0.82 | 6.18 | 77 | $-48.63 |

## 2. Hiệu suất Out-of-Sample tổng hợp (ghép 7 năm test 2013–2019)

- **Tổng số lệnh:** 436
- **Net profit:** $-191.38  → số dư $2000 ⟶ $1808.62
- **Profit Factor:** 0.94
- **Max Drawdown:** $761.61 (30.1%)
- **Recovery Factor:** -0.25
- **Win rate:** 29.8%

## 3. Bộ tham số tối ưu theo từng lượt

| Lượt | tenkan | kijun | spanB | sl_period | sl_mult | trail_period | trail_mult | cloud_color | ichi_exit |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 37 | 53 | 160 | 15 | 2.707 | 15 | 3.404 | 0 | 0 |
| 2 | 36 | 62 | 148 | 7 | 1.0 | 30 | 5.147 | 0 | 1 |
| 3 | 33 | 60 | 132 | 20 | 3.826 | 17 | 1.5 | 0 | 0 |
| 4 | 35 | 55 | 56 | 13 | 1.009 | 16 | 1.5 | 0 | 1 |
| 5 | 21 | 50 | 87 | 7 | 1.764 | 26 | 1.848 | 0 | 1 |
| 6 | 24 | 43 | 81 | 23 | 4.0 | 30 | 1.5 | 1 | 1 |
| 7 | 8 | 31 | 154 | 25 | 3.816 | 17 | 1.5 | 0 | 0 |

## 4. Chẩn đoán Overfitting (IS so với OOS)

- **IS hợp lệ:** 7/7 lượt tìm được bộ tham số thỏa cả 3 bộ lọc.
- **OOS có lãi:** 3/7 năm test có lợi nhuận dương.
- **Recovery Factor trung bình:** IS = 11.23  →  OOS = 0.09.
- Khoảng cách IS→OOS rất lớn: tham số tối ưu trên Train **không giữ được hiệu quả** trên dữ liệu chưa thấy ⟶ đặc trưng overfitting.

## 5. Độ ổn định tham số giữa các lượt (range)

| Tham số | Nhỏ nhất | Lớn nhất | Nhận xét |
|---|---|---|---|
| tenkan | 8 | 37 | rất phân tán |
| kijun | 31 | 62 | phân tán |
| spanB | 56 | 160 | phân tán |
| sl_period | 7 | 25 | rất phân tán |
| sl_mult | 1.0 | 4.0 | rất phân tán |
| trail_period | 15 | 30 | phân tán |
| trail_mult | 1.5 | 5.147 | rất phân tán |

> Tham số 'rất phân tán' giữa các lượt = thêm bằng chứng overfitting (không có vùng tham số bền vững).

## 6. Kết luận & Khuyến nghị

- ❌ **Chưa có edge bền vững ngoài mẫu.** Mặc dù GA luôn đạt bộ lọc trên Train, hiệu suất OOS yếu/âm và drawdown thật cao hơn nhiều mức kỳ vọng từ Train.
- WFA đã làm đúng nhiệm vụ: **phơi bày** việc các bộ lọc IS (PF/DD/số lệnh) *một mình không đủ* để bảo chứng OOS.
- Hướng cải thiện ưu tiên:
  1. **Giảm số chiều tối ưu** (cố định Ichimoku 9-26-52, chỉ tối ưu ATR) để hạn chế curve-fitting.
  2. **Thêm lọc chế độ thị trường** (ADX>20 / độ dày mây) loại giai đoạn sideway.
  3. Đổi mục tiêu sang **độ bền** (vd: tối đa hóa RF *nhỏ nhất* trên nhiều đoạn con, hoặc phạt độ lệch tham số) thay vì chỉ RF tốt nhất trên Train.
  4. Thử **entry pullback về Kijun** (v2) — vào giá tốt hơn, R cao hơn.
  5. Bổ sung **chi phí/commission** & kiểm thử **đa seed** để đánh giá độ vững.