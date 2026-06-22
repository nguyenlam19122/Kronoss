# MQL5 — EA & script cho MetaTrader 5

| File | Công dụng |
|------|-----------|
| `TrendRiderEA.mq5` | EA giao dịch thuận xu hướng (gồng lệnh bằng Chandelier trailing). Chạy live & Strategy Tester. |
| `ExportH1CSV.mq5` | Script xuất lịch sử nến H1 ra CSV (đầu vào cho backtest Python). |

EA dùng **cùng logic** với backtest Python `forex_trend_bot/`, và mặc định **1R = $50 all-in (đã gồm spread)** — đúng thiết lập để test edge.

## 1. Nạp EA vào MT5

1. MT5 → **File → Open Data Folder** → mở `MQL5/Experts/`.
2. Copy `TrendRiderEA.mq5` vào đó (script thì copy vào `MQL5/Scripts/`).
3. Mở **MetaEditor** (F4) → mở file → **Compile (F7)**. Yêu cầu **0 errors**.
4. Về MT5 → Navigator → **Refresh** → EA hiện trong *Expert Advisors*.

## 2. Test trực tiếp bằng Strategy Tester (nhanh nhất) ⭐

1. MT5 → **View → Strategy Tester** (Ctrl+R).
2. **Expert**: chọn `TrendRiderEA`.
3. **Symbol**: cặp tiền cần test; **Period (TF)**: **H1**.
4. **Modeling**: nên chọn *Every tick based on real ticks* (sát thực tế nhất).
5. Đặt **khoảng thời gian** test (Date from → to).
6. Tab **Inputs**: kiểm tra `RiskMode = 1R cố định theo $`, `FixedRisk = 50`.
7. Bấm **Start**. Xem tab **Backtest/Graph/Report**: Net Profit, Profit Factor, Drawdown, số lệnh...

> 💡 Bật **Visual mode** để xem EA vào/ra lệnh và bảng thông tin trực tiếp trên chart.

## 3. Chạy trên tài khoản DEMO

1. Bật nút **Algo Trading** trên thanh công cụ.
2. Mở chart cặp tiền, đổi khung **H1**.
3. Kéo `TrendRiderEA` thả vào chart → tab **Common** tick *Allow Algo Trading* → **OK**.
4. Góc trên phải hiện **mặt cười 🙂** = EA đang chạy. Bảng thông tin hiện ở góc trái chart.

## 4. Tham số chính

| Nhóm | Input | Mặc định | Ý nghĩa |
|------|-------|----------|---------|
| Trend | `EmaFast / EmaSlow` | 50 / 200 | Lọc chiều xu hướng |
| Trend | `AdxMin` | 20 | Bỏ qua thị trường sideway |
| Entry | `DonchianPeriod` | 20 | Breakout N nến |
| Stop | `AtrStopMult` | 2.0 | Dừng lỗ ban đầu = ATR × hệ số |
| Gồng | `ChandelierMult` | 3.0 | Trailing rộng = gồng dài hơn |
| Vốn | `RiskMode` | 1R = $ | Fixed $ (khớp backtest) hoặc % equity |
| Vốn | `FixedRisk` | 50 | 1R = $50 all-in (đã gồm spread) |

## ⚠️ Lưu ý

- **Compile trước** rồi mới test; nếu báo lỗi, gửi mình log lỗi.
- Mỗi cặp giữ **1 lệnh** tại một thời điểm (chưa pyramiding).
- Test **Strategy Tester + DEMO** kỹ trước khi dùng tiền thật. EA không đảm bảo có lãi.
