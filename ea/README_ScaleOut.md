# Ichimoku + ATR ScaleOut — phiên bản cuối

Kết tinh cả quá trình nghiên cứu: **entry ATR-cross (EA gốc của bạn) + exit scale-out** theo
triết lý "lỗ giới hạn, lời có không gian chạy, phân phối R dương".

- `Ichimoku_ATR_ScaleOut_EA.mq5` — EA cho **MT5**.
- `Ichimoku_ATR_ScaleOut.pine` — chỉ báo cho **TradingView** (Pine v6).

## Logic

**Entry:** Trail1 (fast ATR) cắt Trail2 (slow ATR) kiểu ceyhun **+ lọc mây Kumo**
(LONG khi giá trên mây, SHORT khi dưới mây). Tín hiệu tính trên nến đã đóng (không repaint).

**Exit (scale-out):**
1. **SL** = `SLmult × ATR(SLatrPeriod)` → giới hạn lỗ. 1R = `RiskMoney` (mặc định **$20**, đã gồm spread).
2. **Breakeven**: khi đạt **+BEtriggerR** → dời SL về hòa vốn (chặn trả lại lãi).
3. **Chốt một phần**: đóng `PartialFrac` khối lượng tại **+TP1multR** (khóa lời).
4. **Runner**: phần còn lại gồng theo `TrailMult × ATR(TrailATRPeriod)`.

**Sizing động:** `Lot = RiskMoney / ((SL_dist + spread)/tickSize × tickValue + commission)`
→ nếu dính SL, lỗ ≈ đúng 1R = $20 (gồm spread).

## Tham số mặc định (lấy từ các fold WFA hợp lệ, EURUSD H1)

| Nhóm | Tham số | Giá trị |
|---|---|---|
| Entry | fast 5/0.5, slow 10/3.0 | (cố định kiểu ceyhun) |
| SL | SLatrPeriod / SLmult | 14 / 2.5 |
| Breakeven | BEtriggerR | 1.0 R |
| Partial | TP1multR / PartialFrac | 2.0 R / 0.5 |
| Runner | TrailATRPeriod / TrailMult | 10 / 2.0 |
| Risk | RiskMoney | 20 USD |

## Cài đặt

**MT5:** chép `.mq5` vào `MQL5/Experts/` → MetaEditor biên dịch (F7, 0 errors) →
kéo EA vào chart EURUSD H1. Test ở Strategy Tester "Every tick based on real ticks".

**TradingView:** mở Pine Editor → dán nội dung `.pine` → Add to chart. Chỉ báo vẽ Trail1/Trail2,
mây Kumo, nhãn BUY/SELL và các mức SL/BE/TP1 cho tín hiệu mới nhất. Tạo Alert với
"Once Per Bar Close".

## Lưu ý trung thực (từ kết quả WFA 2010–2026)

- Đây là cấu hình **tốt nhất** trong tất cả những gì đã thử: phân phối R đúng dạng (lỗ ~−1R,
  đuôi phải tới +5R, expectancy dương) và **ăn đậm nhất trong giai đoạn có xu hướng (2013–2020)**.
- Nhưng OOS tổng vẫn khiêm tốn vì **2021–2024 EURUSD H1 thiếu trend** (win rate tụt 38%→30%);
  không cơ chế exit nào tạo được cú thắng khi entry không bắt được sóng.
- Khuyến nghị: chạy demo/forward-test trước; cân nhắc **tắt giao dịch khi không có trend**
  (lọc ADX / trend khung D1) và quản trị rủi ro chặt ở giai đoạn sideway.
