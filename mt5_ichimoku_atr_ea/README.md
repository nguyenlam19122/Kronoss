# EA MT5: Ichimoku Kumo + ATR Trailing Stop

EA (Expert Advisor) cho MetaTrader 5, xây dựng từ 2 indicator TradingView bạn cung cấp:
**Ichimoku Cloud** và **ATR Trailing Stop (ceyhun)** — kèm quản lý vốn rủi ro cố định **1R = 50$**.

> File chính: [`Ichimoku_ATR_EA.mq5`](./Ichimoku_ATR_EA.mq5)
> Backtest kiểm chứng (Python): [`backtest.py`](./backtest.py) · [`sweep.py`](./sweep.py)

---

## 1. Ý tưởng chiến lược

Bạn nói chưa có ý tưởng điểm vào lệnh và stop loss, nên mình thiết kế bằng cách cho mỗi
indicator một vai trò rõ ràng (đây là cách phối hợp kinh điển: 1 cái lọc xu hướng, 1 cái bấm cò):

| Thành phần | Vai trò | Logic |
|---|---|---|
| **Ichimoku Kumo (mây)** | **Bộ lọc xu hướng** | Chỉ cho Buy khi giá **nằm trên mây**, chỉ cho Sell khi giá **nằm dưới mây** |
| **ATR Trailing Stop** | **Tín hiệu vào lệnh** | Buy = Fast Trail cắt **lên** Slow Trail; Sell = Fast Trail cắt **xuống** Slow Trail |
| **Slow Trail (Trail2)** | **Stop Loss tự nhiên** | SL đặt ngay tại Slow Trail lúc vào lệnh — bản thân nó đã là 1 ATR-stop |
| **Rủi ro cố định 1R** | **Khối lượng (lot)** | Lot tự tính sao cho **nếu dính SL thì lỗ đúng ~50$** |

### Quy tắc vào lệnh

- **LONG (Mua):** có tín hiệu Buy của ATR (`Trail1` cắt lên `Trail2`) **VÀ** giá đóng cửa nằm **trên** mây Kumo.
- **SHORT (Bán):** có tín hiệu Sell của ATR (`Trail1` cắt xuống `Trail2`) **VÀ** giá đóng cửa nằm **dưới** mây Kumo.
- Tín hiệu chỉ được tính trên **nến đã đóng** → **không repaint**, không vào lệnh giữa nến.

### Stop Loss & Take Profit

- **SL** mặc định = giá trị **Slow Trail (Trail2)** tại thời điểm vào lệnh (có khoảng cách tối thiểu để
  tránh lot quá lớn). Đây chính là khoảng cách định nghĩa **1R**.
- **TP** mặc định = **2R** (tỉ lệ Risk:Reward = 1:2). Tức rủi ro 50$ để nhắm lời 100$.
- Tùy chọn: đóng lệnh sớm khi xuất hiện **tín hiệu ngược** (`ExitOnOpposite`), và/hoặc **dời SL** theo Slow Trail (`UseTrailing`).

### Position sizing — cốt lõi của "1R = 50$"

```
khoảng_cách_SL  = |giá_vào − giá_SL|
lỗ_mỗi_1_lot    = (khoảng_cách_SL / tick_size) × tick_value
lot             = RiskMoney(50$) / lỗ_mỗi_1_lot      → làm tròn xuống theo bước lot
```

Nhờ vậy, **dù SL gần hay xa, mỗi lệnh thua luôn ≈ 50$**. Đúng yêu cầu của bạn.

---

## 2. Kết quả backtest trên chính dữ liệu của bạn

Dữ liệu: **EURUSD H1, 2025.01.01 → 2025.12.31 (6.214 nến)**. Lời/lỗ tính theo **R** (1R = 50$).

```
Cấu hình                                | lệnh | win   | tổng lời       | PF   | DD
----------------------------------------+------+-------+----------------+------+------
Baseline (TP=2R)                        |  67  | 43.3% | +13.18R (+659$)| 1.46 | 3.98R
TP = 3R                ★ tốt nhất       |  67  | 43.3% | +23.33R (+1167$)| 1.82 | 3.98R
Trailing + TP=2R       (lời cao, DD cao)|  67  | 35.8% | +32.29R (+1614$)| 1.75 | 6.24R
TP = 1.5R                               |  67  | 43.3% | +11.18R (+559$)| 1.39 | 4.10R
TP = 1R                                 |  67  | 47.8% |  +4.55R (+228$)| 1.17 | 4.26R
Không lọc mây (chỉ ATR)                 | 150  | 38.0% | +14.12R (+706$)| 1.21 | 9.06R
+ Lọc màu mây                ✗ tệ hơn   |  34  | 32.4% |  −4.34R (−217$)| 0.76 | 7.25R
Trailing + bỏ TP             ✗ rất tệ   |  67  | 35.8% | −19.00R (−950$)| 0.56 | 21.0R
```
*(PF = Profit Factor; DD = max drawdown theo R. Chạy lại bằng `python3 sweep.py <csv>`)*

**Nhận xét:**
- Lọc bằng mây Ichimoku **giúp ích rõ rệt** (so với "chỉ ATR": ít lệnh hơn nhưng PF cao hơn, DD thấp hơn nhiều).
- **TP = 3R** cho kết quả tốt nhất về rủi ro/lợi nhuận: lời cao gần gấp đôi baseline mà **drawdown y hệt** (3.98R).
- **Trailing theo Slow Trail** cho tổng lời cao nhất nhưng win rate thấp (36%) và DD cao hơn — chỉ dùng **khi đã bật TP**. Bật trailing mà bỏ TP → thua nặng.
- Thêm điều kiện **màu mây** lại làm tệ đi → để mặc định **tắt**.

> ⚠️ **Lưu ý trung thực:** đây là backtest **in-sample 1 năm**, **chưa trừ spread/commission/slippage** (R tính theo giá thuần). Spread EURUSD trong file ~0.6–1.6 pip, trên SL trung bình ~25–40 pip sẽ "ăn" vài % mỗi lệnh; cộng phí hoa hồng nữa thì kết quả thực sẽ **thấp hơn** bảng trên. Hãy chạy lại trong **Strategy Tester của MT5** (chế độ "Every tick based on real ticks") với spread/phí thật của broker trước khi giao dịch tiền thật.

---

## 3. Cách cài đặt vào MetaTrader 5

1. Mở MT5 → menu **File → Open Data Folder**.
2. Vào thư mục `MQL5/Experts/`, chép file `Ichimoku_ATR_EA.mq5` vào đây.
3. Mở **MetaEditor** (F4) → mở file → nhấn **Compile** (F7). Phải báo *0 error, 0 warning*.
4. Quay lại MT5, mở chart **EURUSD khung H1**, kéo EA từ *Navigator → Expert Advisors* vào chart.
5. Trong tab **Common**: bật *Allow Algo Trading*. Trong tab **Inputs**: chỉnh tham số (xem mục 4).
6. Bật nút **Algo Trading** trên thanh công cụ.

**Để backtest trong MT5:** mở **View → Strategy Tester (Ctrl+R)** → chọn EA, EURUSD, H1, khoảng thời gian 2025, Model = *Every tick based on real ticks*, nhập spread/commission của broker → **Start**.

---

## 4. Bảng tham số (Inputs)

| Tham số | Mặc định | Ý nghĩa |
|---|---|---|
| **Ichimoku** | | |
| `InpTenkan` | 9 | Conversion Line (Tenkan) |
| `InpKijun` | 26 | Base Line (Kijun) |
| `InpSenkouB` | 52 | Leading Span B |
| `InpDisplacement` | 26 | Độ dịch mây |
| `InpUseCloudFilter` | true | Bắt buộc giá ra ngoài mây mới vào lệnh |
| `InpRequireCloudColor` | false | Bắt buộc màu mây trùng hướng *(backtest cho thấy nên để tắt)* |
| **ATR Trailing Stop** | | |
| `InpFastATRPeriod` / `InpFastATRMult` | 5 / 0.5 | Fast Trail (AP1 / AF1) |
| `InpSlowATRPeriod` / `InpSlowATRMult` | 10 / 3.0 | Slow Trail (AP2 / AF2) |
| **Quản lý rủi ro** | | |
| `InpRiskMoney` | **50.0** | **1R — số tiền rủi ro mỗi lệnh** |
| `InpSLMode` | 0 | SL: `0`=Slow Trail, `1`=ATR×hệ số, `2`=Kijun |
| `InpSLATRMult` | 1.5 | Hệ số ATR cho SL khi `SLMode=1` |
| `InpMinSLpips` | 5.0 | Khoảng cách SL tối thiểu (pips) — chặn lot phình to |
| `InpTakeProfitRR` | 2.0 | TP theo bội số R (đặt `3.0` theo backtest; `0`=không TP cố định) |
| `InpMaxLots` | 5.0 | Trần khối lượng an toàn |
| **Quản lý lệnh** | | |
| `InpUseTrailing` | false | Dời SL theo Slow Trail (chỉ bật khi có TP) |
| `InpExitOnOpposite` | true | Đóng lệnh khi có tín hiệu ngược |
| `InpMagic` | 990011 | Magic number (phân biệt lệnh của EA) |
| `InpMaxSpreadPts` | 30 | Spread tối đa (points) cho phép vào lệnh |

### Khuyến nghị cấu hình (theo backtest)
- **An toàn / dễ giao dịch:** giữ mặc định nhưng đổi `InpTakeProfitRR = 3.0` (PF 1.82, DD thấp nhất).
- **Tăng trưởng mạnh hơn:** `InpUseTrailing = true`, giữ `InpTakeProfitRR = 2.0` (lời cao nhất, chấp nhận DD & win rate thấp hơn).

---

## 5. Kiểm chứng lại bằng Python

```bash
cd mt5_ichimoku_atr_ea
python3 backtest.py  /đường_dẫn/EURUSD_H1_2025.csv   # 1 cấu hình + báo cáo chi tiết
python3 sweep.py     /đường_dẫn/EURUSD_H1_2025.csv   # so sánh nhiều cấu hình
```
File `backtest.py` tái hiện **đúng logic** của EA (Ichimoku donchian, ATR Wilder, đệ quy Trailing,
lọc mây, SL=Slow Trail, TP theo R, vào lệnh ở open nến kế tiếp) để bạn đối chiếu trước khi chạy MT5.

---

## 6. Giới hạn & lời khuyên

- Backtest chỉ 1 năm, in-sample, chưa trừ chi phí → **đừng kỳ vọng y hệt** khi chạy thật.
- Nên forward-test trên **tài khoản demo** vài tuần trước khi dùng tiền thật.
- `tick_value`/`tick_size` lấy từ broker; nếu loại tài khoản (cent/standard) hoặc tiền tệ tài khoản
  khác nhau, lot sẽ tự điều chỉnh — nhưng hãy kiểm tra log "BUY/SELL ... R=50$" để chắc chắn rủi ro đúng ý.
- EA mặc định **chỉ giữ 1 lệnh tại một thời điểm** trên symbol.
