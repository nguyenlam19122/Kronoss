# IchimokuATR_TrendEA (v1)

EA trend-following cho **MT5 / MQL5**, dựng từ 2 indicator TradingView:
**Ichimoku Cloud** (lọc xu hướng) + **ATR Trailing Stop của ceyhun** (trailing để "ăn" trọn sóng).

> Bản **v1** này là *baseline để backtest và tinh chỉnh*, chưa phải bản tối ưu.
> Mục tiêu: có một con EA chạy được đúng logic cốt lõi để đo edge trước, rồi mới nâng cấp.

---

## 1. Logic cốt lõi — kiến trúc 3 lớp

| Lớp | Vai trò | Thành phần |
|-----|---------|------------|
| **1. Lọc (Filter)** | Cho phép LONG / SHORT / cấm vào lệnh | Ichimoku |
| **2. Kích hoạt (Trigger)** | Bấm nút vào lệnh trong vùng được phép | TK cross |
| **3. Thoát + Sizing** | SL ban đầu (= 1R), trailing, khối lượng | ATR + công thức risk |

**Điều kiện vào LONG** (SHORT đảo ngược hoàn toàn):
- `close` nằm **trên mây** Kumo (trên cả Senkou A và B)
- mây **xanh** (`Senkou A > Senkou B`) — bật/tắt bằng `InpRequireCloudColor`
- `close > Kijun`
- **Tenkan cắt lên Kijun** (TK cross) ngay tại nến vừa đóng

→ Khi giá nằm **trong mây** thì EA **không vào lệnh** (vùng nhiễu, nguồn gốc của hầu hết lệnh thua trend-following).

**Thoát lệnh:**
- **Trailing stop ATR** kiểu ratchet: `SL = close − ATR(10)×3` (chỉ dời theo hướng có lợi). Đây chính là *Trail2* trong indicator của ceyhun.
- **Thoát sớm theo Ichimoku** (tùy chọn `InpUseIchiExit`): đóng lệnh khi giá đóng cửa rớt dưới Kijun hoặc chui vào mây.

---

## 2. Quản lý vốn — "$20 = 1R, đã gồm spread"

Khối lượng được tính **động** cho từng lệnh sao cho nếu chạm SL thì lỗ ≈ `InpRiskUSD`:

```
Khoảng_SL (giá) = ATR(SLatrPeriod) × SLmult
Khoảng_sizing   = Khoảng_SL + spread          ← cộng spread để loss thực ≤ 20$
Lỗ_trên_1_lot   = Khoảng_sizing / tickSize × tickValue
LotSize         = InpRiskUSD / Lỗ_trên_1_lot   → làm tròn xuống theo VOLUME_STEP
```

Dùng `SYMBOL_TRADE_TICK_VALUE` / `SYMBOL_TRADE_TICK_SIZE` nên công thức tự đúng cho mọi sản phẩm (forex, vàng, index...), và được clamp theo `VOLUME_MIN/MAX/STEP`.

**Ví dụ EURUSD** (1 pip = $10/lot): SL 22 pip + spread 3 pip = 25 pip → lỗ/lot = $250 → **LotSize = 20/250 = 0.08 lot**.

---

## 3. Bộ tham số thô v1 (mặc định trong code)

| Nhóm | Tham số | Giá trị | Ghi chú |
|------|---------|---------|---------|
| Ichimoku | Tenkan / Kijun / SpanB / Displacement | 9 / 26 / 52 / 26 | giữ chuẩn |
| Ichimoku | `InpRequireCloudColor` | true | bắt buộc mây cùng màu |
| SL ban đầu | `InpSLatrPeriod` × `InpSLmult` | ATR(14) × 2.0 | định nghĩa 1R |
| Trailing | `InpTrailPeriod` × `InpTrailMult` | ATR(10) × 3.0 | = Trail2 ceyhun |
| Thoát sớm | `InpUseIchiExit` | true | đảo Ichimoku |
| Risk | `InpRiskUSD` | 20.0 | mỗi lệnh, gồm spread |
| Khác | 1 lệnh/symbol, không nhồi lệnh | — | v1 |

**Khuyến nghị test:** Forex major (EURUSD/GBPUSD...), khung **H1**.

---

## 4. Cài đặt & backtest

1. Copy `IchimokuATR_TrendEA.mq5` vào `MQL5/Experts/` của thư mục data MT5
   (MetaTrader 5 → **File → Open Data Folder**).
2. Mở **MetaEditor** → biên dịch (F7). Phải **0 errors**.
3. Mở **Strategy Tester** (Ctrl+R) → chọn EA, symbol forex major, khung **H1**,
   mode *Every tick based on real ticks*, nạp đủ lịch sử ≥ 80 nến để Ichimoku có dữ liệu.
4. Kiểm tra: lot có đúng quy mô để mỗi lệnh rủi ro ≈ $20 không; SL/trailing chạy đúng không.

> Lưu ý kỹ thuật: toàn bộ đường Ichimoku được tính **trực tiếp từ giá** (Donchian) giống hệt
> Pine Script, và mây được **canh đúng độ dịch 26 nến** — đám mây nằm *dưới* nến hiện tại được
> tính từ 26 nến trước. Cách này tránh lỗi lệch buffer thường gặp khi dùng `iIchimoku`.
>
> EA giả định **tài khoản netting** (1 vị thế/symbol). Nếu dùng tài khoản hedging cần điều chỉnh
> phần quản lý vị thế.

---

## 5. Lộ trình nâng cấp (sau khi v1 có dữ liệu backtest)

- **v1.1 — Lọc sideway:** thêm lọc độ dày mây hoặc `ADX > 20` để bỏ thị trường lình xình
  (giảm whipsaw — kẻ thù số 1 của TK cross).
- **v2 — Entry pullback:** đổi trigger sang "hồi về Kijun rồi bật lại" để có **stop sát hơn →
  size lớn hơn → R tốt hơn** với cùng mức rủi ro $20.
- **v3 — Tích hợp Kronos:** chỉ vào lệnh khi *Ichimoku + ATR cho setup* **và** model dự đoán
  nến **Kronos** (trong chính repo này) dự báo giá tiếp diễn cùng chiều — biến phần "điểm vào"
  thành một bộ lọc xác suất bằng AI.
