# KronossTrendEA — EA theo xu hướng (Profit Factor ≥ 1.2)

EA này được xây dựng theo đúng triết lý trong khung bài học quant:
**không cần winrate cao**, nhưng phải có **edge thật** thể hiện qua **Profit Factor (PF) ≥ 1.2**.
Cách đạt được điều này là dùng hệ thống **trend-following**: thua nhiều lệnh nhỏ, thắng ít
lệnh nhưng lớn (R:R thuận lợi) → tổng lời/tổng lỗ ≥ 1.2.

> File EA: [`Experts/KronossTrendEA.mq5`](Experts/KronossTrendEA.mq5)

---

## 1. Vì sao "winrate thấp" vẫn cho PF ≥ 1.2?

Profit Factor được định nghĩa:

```
PF = Tổng lời (gross profit) / Tổng lỗ (gross loss)
```

Với hệ thống có winrate `W`, lời trung bình `R` lần lỗ trung bình (boi so R), ta có gần đúng:

```
PF ≈ (W × R) / (1 − W)
```

| Winrate (W) | R:R trung bình | PF (xấp xỉ) |
|:-----------:|:--------------:|:-----------:|
| 35%         | 2.5            | **1.35**    |
| 40%         | 2.0            | **1.33**    |
| 40%         | 2.5            | **1.67**    |
| 45%         | 1.8            | **1.47**    |

→ Chỉ cần **giữ lỗ nhỏ, để lời chạy** (R ≥ ~2) thì winrate 35–45% là đủ vượt ngưỡng 1.2.
Đây chính là lý do EA tập trung vào quản lý lệnh hơn là tìm tín hiệu "đẹp".

---

## 2. Logic chiến lược

Hệ thống gồm 5 khối, mỗi khối map trực tiếp vào kỹ năng trong giáo án:

### 2.1. Lọc chế độ thị trường (Regime filter) — *"thị trường có xu hướng hay thiếu xu hướng?"*
- `EMA(50)` so với `EMA(200)` → xác định hướng (tăng/giảm).
- `ADX(14) > AdxThreshold` (mặc định 22) → xác nhận thị trường **đang có xu hướng**.
- Nếu ADX dưới ngưỡng → coi như **sideway → KHÔNG vào lệnh** (tránh môi trường nhiễu,
  nơi trend-following bị "cưa").

### 2.2. Tín hiệu vào lệnh (Entry) — breakout Donchian
- **Mua**: thị trường xu hướng tăng **và** giá đóng cửa vượt **đỉnh cao nhất** của
  `EntryChannel` (mặc định 20) nến gần nhất.
- **Bán**: ngược lại với xu hướng giảm.
- Vào theo breakout thuận xu hướng → bắt được những con sóng lớn (nguồn của các lệnh thắng lớn).

### 2.3. Cắt lỗ (Initial stop) — ATR
- SL ban đầu = `entry ∓ ATR(14) × AtrMultSL` (mặc định 2.0).
- Stop theo độ biến động (volatility-adjusted) → khách quan, không đặt cảm tính.
- Sai → thoát sớm với **lỗ nhỏ** → đây là nguồn của winrate thấp (và điều đó OK).

### 2.4. Để lời chạy (Exit) — Chandelier trailing
- Trailing stop = `đỉnh cao nhất TrailChannel nến − ATR × AtrMultTrail` (long; short đối xứng).
- Chỉ dời stop theo hướng có lợi → khóa dần lợi nhuận nhưng **vẫn cho sóng chạy hết**.
- Tùy chọn `TakeProfitR` (bội số R) — mặc định **0 = tắt** để không chặn lời sớm.

### 2.5. Quản lý vốn (Money management)
- Khối lượng lot tính theo **% rủi ro cố định** (`RiskPercent`, mặc định 1%) dựa trên
  khoảng cách SL → mỗi lệnh rủi ro như nhau theo tiền, bất kể biến động.
- Hoặc đặt `FixedLots > 0` để dùng lot cố định.

---

## 3. Bảng tham số

| Nhóm | Tham số | Mặc định | Ý nghĩa |
|------|---------|:--------:|---------|
| Regime | `EmaFastPeriod` | 50 | EMA nhanh lọc hướng |
| Regime | `EmaSlowPeriod` | 200 | EMA chậm lọc hướng |
| Regime | `AdxPeriod` | 14 | Chu kỳ ADX |
| Regime | `AdxThreshold` | 22 | Ngưỡng ADX xác nhận xu hướng |
| Entry | `EntryChannel` | 20 | Số nến kênh Donchian breakout |
| Entry | `AllowLong/Short` | true | Cho phép Mua/Bán |
| Risk | `AtrPeriod` | 14 | Chu kỳ ATR |
| Risk | `AtrMultSL` | 2.0 | Hệ số ATR cho SL ban đầu |
| Risk | `AtrMultTrail` | 3.0 | Hệ số ATR cho trailing |
| Risk | `TrailChannel` | 22 | Số nến tính đỉnh/đáy Chandelier |
| Risk | `TakeProfitR` | 0.0 | TP theo bội số R (0 = tắt) |
| MM | `RiskPercent` | 1.0 | % rủi ro mỗi lệnh |
| MM | `FixedLots` | 0.0 | Lot cố định (>0 sẽ ưu tiên) |
| Filter | `MaxSpreadPoints` | 0 | Spread tối đa (0 = bỏ qua) |
| Filter | `TradeOnNewBarOnly` | true | Chỉ xử lý khi có nến mới |

---

## 4. Cài đặt

1. Copy `Experts/KronossTrendEA.mq5` vào `MQL5/Experts/` của MetaTrader 5.
2. Mở **MetaEditor** → mở file → **Compile** (F7). Phải 0 lỗi.
3. Kéo EA vào chart, bật **Algo Trading**.

---

## 5. Kiểm định để chắc chắn PF ≥ 1.2 (theo workflow giáo án)

EA chỉ là phần "thực thi". Để khẳng định **real edge** chứ không phải **fake edge**, làm theo
đúng quy trình kiểm định trong khung bài học:

### Bước 1 — Backtest trong Strategy Tester (MT5)
- Khung gợi ý: **H1 / H4 / D1**; thị trường có xu hướng rõ: **XAUUSD, US30/NAS100, EURUSD, USDJPY**.
- Dùng dữ liệu chất lượng cao ("Every tick based on real ticks"), tối thiểu 5–10 năm.
- Đọc các chỉ số: **Profit Factor**, **Expected Payoff**, **Recovery Factor**, **Max Drawdown**.
- Mục tiêu nghiệm thu: **PF ≥ 1.2** kèm số lệnh đủ lớn (≥ 100–200 lệnh) để có ý nghĩa thống kê.

### Bước 2 — Tối ưu hóa thận trọng (tránh overfit)
- Tối ưu các tham số chính: `AtrMultSL`, `AtrMultTrail`, `EntryChannel`, `AdxThreshold`.
- Ưu tiên **vùng tham số ổn định** (plateau) thay vì đỉnh nhọn cô lập → bền vững khi live.
- Bắt buộc **Walk-Forward Analysis** để kiểm tra tính tổng quát hóa.

### Bước 3 — Kiểm tra độ bền (robustness) bằng Python
Xuất lịch sử giao dịch (Strategy Tester → Report) rồi dùng Python (đúng phần "mã Python phục vụ
kiểm tra độ bền, Monte Carlo, thống kê" trong giáo án):

- **Monte Carlo**: xáo trộn thứ tự lệnh hàng nghìn lần → phân phối PF & max drawdown.
  Cần **P5 của PF vẫn ≥ ~1.1–1.2** thì edge mới đáng tin.
- **T-test / bootstrap** trên chuỗi lợi nhuận mỗi lệnh: kiểm định kỳ vọng > 0 có ý nghĩa
  thống kê (p-value đủ nhỏ) → phân biệt **real edge vs fake edge**.
- **Out-of-sample**: tách dữ liệu IS/OOS, chỉ chấp nhận khi OOS vẫn giữ PF ≥ 1.2.

> Gợi ý: tận dụng luôn pipeline Python sẵn có trong repo Kronos để khảo sát dữ liệu/đặc tính
> chuỗi giá trước khi chọn thị trường & khung thời gian phù hợp cho EA.

---

## 6. Lưu ý rủi ro
- Kết quả backtest **không đảm bảo** kết quả tương lai. Luôn forward-test trên tài khoản demo
  trước khi đưa vào live.
- Trend-following sẽ có **chuỗi thua liên tiếp** trong giai đoạn sideway — đây là đặc tính bình
  thường, không phải lỗi. Quản lý vốn (`RiskPercent`) là yếu tố sống còn.
- Tham số mặc định chỉ là điểm khởi đầu hợp lý, **chưa** được tối ưu cho một thị trường cụ thể.
