# Forex Trend Rider — Bot giao dịch thuận xu hướng (H1)

Bot **trend-following "gồng lệnh"** cho forex khung **H1**, gồm 2 phần dùng chung một logic:

- **Python** (`forex_trend_bot/`): nghiên cứu, **backtest** và **kiểm định độ bền** (real-edge?).
- **MQL5** (`../mql5/TrendRiderEA.mq5`): **Expert Advisor** chạy live trên MetaTrader 5.

## Logic chiến lược

| Khối | Quy tắc |
|------|---------|
| **Lọc xu hướng** | `EMA(50)` vs `EMA(200)` xác định chiều; `ADX(14) > 20` để loại sideway |
| **Vào lệnh** | Breakout kênh **Donchian(20)** theo chiều trend (long khi phá đỉnh, short khi phá đáy) |
| **GỒNG LỆNH** | **Chandelier trailing stop** = `đỉnh_cao_nhất(22) − ATR(14)×3`, chỉ siết theo chiều có lợi → cho lãi chạy |
| **Thoát** | Khi trailing stop bị chạm (mặc định để trailing tự lo, gồng dài theo trend) |
| **Sizing** | Backtest mặc định **1R = $50 ALL-IN** (đã gồm spread): khối lượng = rủi ro ÷ (dừng lỗ ATR **+ spread**) → lỗ tối đa mỗi lệnh khi dính stop = đúng **$50 = -1.00R**. EA live dùng **% equity** (`RiskPercent`), cũng tính spread vào sizing. |

> Đặc tính trend-following: **win rate thấp (~35–45%)** nhưng **payoff cao** — cắt lỗ nhanh, gồng lãi lớn. Lãi tổng đến từ một số ít lệnh thắng đậm.

## Cài đặt

```bash
pip install -r ../requirements.txt   # hoặc: pip install pandas numpy scipy matplotlib
```

## Chạy backtest với DỮ LIỆU CỦA BẠN

1. Thả các file CSV H1 vào thư mục `forex_trend_bot/data/` (đặt tên dễ nhận, vd `EURUSD_H1.csv`).
2. Chạy:

```bash
# Quét toàn bộ file trong data/
python -m forex_trend_bot.run_backtest --data forex_trend_bot/data --plot

# Hoặc một file cụ thể
python -m forex_trend_bot.run_backtest --data path/to/EURUSD_H1.csv --plot

# Tùy chọn
python -m forex_trend_bot.run_backtest --fixed-risk 50 --spread 0.0002  # 1R=$50, spread 2 pip (mặc định fixed)
python -m forex_trend_bot.run_backtest --risk-mode percent --risk 0.01  # đổi sang rủi ro 1% equity (compounding)
python -m forex_trend_bot.run_backtest --short-off                      # chỉ giao dịch long
python -m forex_trend_bot.run_backtest --exit-on-flip                   # thoát khi EMA đảo
```

### Định dạng dữ liệu

Loader tự nhận diện dấu phân cách và tên cột. Chấp nhận:
- Xuất từ **MetaTrader 5** (`Date, Time, Open, High, Low, Close, TickVolume`).
- Định dạng chung: cột thời gian (`time`/`timestamp`/`date`) + `open, high, low, close` (`volume` tùy chọn).
- File có cột ngày & giờ tách rời sẽ được tự ghép.

Chưa có dữ liệu thật? Tạo bộ giả lập để thử pipeline (⚠️ **không phải edge thật**):

```bash
python -m forex_trend_bot.make_sample_data
```

## Đọc kết quả

- **HIỆU NĂNG**: **∑R (tổng R)**, kỳ vọng (R)/lệnh, **Max DD theo R**, profit factor, Sharpe, max drawdown, win rate... Khi 1R = $50 cố định thì **∑R + T-test là thước đo edge sạch nhất**.
- **KIỂM ĐỊNH ĐỘ BỀN** (real-edge hay fake-edge):
  1. **Phân tích theo đoạn** — edge có ổn định qua các giai đoạn không?
  2. **Monte Carlo** (bootstrap) — phân phối lợi nhuận & drawdown, xác suất thua lỗ.
  3. **T-test** — kỳ vọng lợi nhuận có > 0 *có ý nghĩa thống kê* không (p < 0.05)?

Biểu đồ equity/drawdown/điểm vào-ra lưu ở `forex_trend_bot/results/`.

## Chạy live bằng EA MQL5

1. Mở **MetaEditor** → copy `mql5/TrendRiderEA.mq5` vào `MQL5/Experts/` → **Compile** (F7).
2. Trong MetaTrader 5: kéo EA vào chart **H1** của cặp tiền cần chạy, bật **Algo Trading**.
3. Tham số EA khớp với backtest (EMA 50/200, ADX 20, Donchian 20, ATR 14, Chandelier 22×3, Risk 1%).
4. **Khuyến nghị:** test trên **Strategy Tester** + tài khoản **demo** trước khi dùng tiền thật.

## ⚠️ Lưu ý quan trọng

- Đây là **khung khởi đầu** minh bạch, chưa phải hệ thống production.
- Kết quả backtest **không đảm bảo** kết quả tương lai. Spread/slippage/phí thực tế ảnh hưởng lớn ở H1.
- Hãy luôn **kiểm định out-of-sample** và chạy **demo** trước khi giao dịch thật.
