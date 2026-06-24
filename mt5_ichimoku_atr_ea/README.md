# EA MT5: Ichimoku Kumo + ATR Trailing Stop

EA (Expert Advisor) cho MetaTrader 5, xây dựng từ 2 indicator TradingView bạn cung cấp:
**Ichimoku Cloud** và **ATR Trailing Stop (ceyhun)** — quản lý vốn rủi ro cố định **1R = 50$ (đã gồm spread + commission)**,
mặc định **gồng theo xu hướng** (không TP cố định, thoát khi ATR đảo chiều).

> File chính: [`Ichimoku_ATR_EA.mq5`](./Ichimoku_ATR_EA.mq5)
> Backtest kiểm chứng (Python): [`backtest.py`](./backtest.py) · [`sweep.py`](./sweep.py)

---

## 1. Ý tưởng chiến lược

Bạn nói chưa có ý tưởng điểm vào lệnh và stop loss, nên mình thiết kế bằng cách cho mỗi
indicator một vai trò rõ ràng (đây là cách phối hợp kinh điển: 1 cái lọc xu hướng, 1 cái bấm cò):

| Thành phần | Vai trò | Logic |
|---|---|---|
| **Ichimoku Kumo (mây)** | **Bộ lọc xu hướng** | Chỉ cho Buy khi giá **nằm trên mây**, chỉ cho Sell khi giá **nằm dưới mây** |
| **ATR Trailing Stop** | **Tín hiệu vào & thoát** | Vào: Fast Trail cắt **lên** Slow Trail (Buy) / cắt **xuống** (Sell). Thoát: khi cắt **ngược lại** (đảo trend) |
| **Slow Trail (Trail2)** | **Stop Loss tự nhiên** | SL đặt ngay tại Slow Trail lúc vào lệnh — bản thân nó đã là 1 ATR-stop |
| **Rủi ro cố định 1R** | **Khối lượng (lot)** | Lot tự tính sao cho **nếu dính SL thì lỗ đúng 50$ (đã gồm spread + commission)** |

### Quy tắc vào lệnh

- **LONG (Mua):** có tín hiệu Buy của ATR (`Trail1` cắt lên `Trail2`) **VÀ** giá đóng cửa nằm **trên** mây Kumo.
- **SHORT (Bán):** có tín hiệu Sell của ATR (`Trail1` cắt xuống `Trail2`) **VÀ** giá đóng cửa nằm **dưới** mây Kumo.
- Tín hiệu chỉ được tính trên **nến đã đóng** → **không repaint**, không vào lệnh giữa nến.

### Stop Loss & "gồng" theo xu hướng (Take Profit)

- **SL** = giá trị **Slow Trail (Trail2)** tại thời điểm vào lệnh (có khoảng cách tối thiểu để tránh lot quá lớn).
  Đây chính là khoảng cách định nghĩa **1R**.
- **Thoát lệnh (mặc định = GỒNG theo trend):** **KHÔNG đặt TP cố định**, giữ lệnh chạy cho tới khi
  **ATR Trailing Stop đảo chiều** (`Trail1` cắt ngược `Trail2`) — đó chính là tín hiệu trend đã quay đầu.
  Cách này để **lệnh thắng chạy dài** (backtest có lệnh ăn tới **+4.5R**) trong khi lệnh thua vẫn bị chặn ở đúng 1R.
- Vì sao **không** dùng trailing-stop bám sát giá? Vì Slow Trail (3×ATR) quá lỏng, còn Fast Trail/Kijun lại quá chặt —
  cả hai đều **bóp** đà của trend và làm giảm lời (xem bảng mục 2). Để trend tự chạy đến khi hệ thống báo đảo là tốt nhất.
- Tùy chọn khác (có thể bật trong Inputs): TP cố định theo R, dời SL theo Slow/Fast/Kijun, hoặc thoát khi giá phá mây.

### Position sizing — cốt lõi của "1R = 50$ (đã gồm spread)"

```
khoảng_cách_SL  = |giá_vào − giá_SL|     (giá_vào = Ask khi mua / Bid khi bán → ĐÃ gồm spread)
lỗ_mỗi_1_lot    = (khoảng_cách_SL / tick_size) × tick_value + commission_mỗi_lot
lot             = 50$ / lỗ_mỗi_1_lot     → làm tròn xuống theo bước lot
```

Vì vào lệnh ở giá **Ask/Bid** nên khi dính SL, phần spread đã **nằm sẵn** trong khoản lỗ; cộng thêm
`InpCommissionPerLot` nữa là **trọn vẹn chi phí**. Kết quả: **dù SL gần hay xa, mỗi lệnh thua luôn = đúng 50$
(gồm spread + commission)**. Đúng như bạn yêu cầu.

---

## 2. Kết quả backtest trên chính dữ liệu của bạn

Dữ liệu: **EURUSD H1, 2025.01.01 → 2025.12.31 (6.214 nến)**. Lời/lỗ theo **R** (1R = 50$),
**đã mô phỏng spread thật** (lấy từ cột `<SPREAD>` của từng nến trong file của bạn).

```
>>> CÓ TP CỐ ĐỊNH (tham khảo)         | lệnh | win   | tổng lời        | PF   | DD     | lệnh thắng to nhất
TP = 2R                               |  67  | 43.3% | +14.01R (+701$) | 1.51 | 3.72R  | +2.0R
TP = 3R                               |  67  | 43.3% | +24.01R (+1201$)| 1.87 | 3.72R  | +3.0R
>>> GỒNG THEO XU HƯỚNG (bỏ TP cố định)
Giữ đến khi ATR đảo chiều  ★ MẶC ĐỊNH |  67  | 43.3% | +17.09R (+855$) | 1.62 | 3.72R  | +4.5R
  └ trên + commission 0.7pip (~7$/lot)|  67  | 43.3% | +15.74R (+787$) | 1.57 | 3.74R  | +4.4R
Trail theo Slow Trail (Trail2)        |  67  | 35.8% |  +9.06R (+453$) | 1.37 | 3.54R  | +4.4R
Thoát khi giá phá mây (cloud break)   |  67  | 37.3% |  +8.32R (+416$) | 1.29 | 4.34R  | +4.5R
Trail theo Fast Trail (Trail1)  ✗ chặt|  67  | 34.3% |  +1.69R  (+84$) | 1.25 | 1.58R  | +1.0R
Trail theo Kijun                ✗ tệ  |  67  | 32.8% |  +0.51R  (+26$) | 1.03 | 4.89R  | +3.6R
```
*(PF = Profit Factor; DD = max drawdown theo R. Chạy lại: `python3 sweep.py <csv>`)*

**Nhận xét:**
- ✅ **Cấu hình mặc định (gồng đến khi ATR đảo chiều)** là lựa chọn tốt nhất cho mục tiêu *bám trend* của bạn:
  **+17R (+855$)**, lệnh thắng chạy được tới **+4.5R**, mà max drawdown vẫn chỉ **~186$** (≈3.7R).
- Mọi kiểu **trailing-stop bám sát** đều **làm giảm lời** (cắt trend non): Fast Trail +1.7R, Kijun +0.5R, Slow Trail +9R.
  → Với chiến lược này, cách "gồng" tốt nhất là **không** trailing, để hệ thống ATR tự báo điểm thoát.
- **Chi phí thật ảnh hưởng nhỏ:** thêm commission 7$/lot, lời chỉ giảm từ +855$ xuống **+787$** → chiến lược vẫn lãi tốt sau phí.
- Nếu bạn thích **win-rate cao + chốt nhanh** thay vì gồng, dùng **TP=3R** (PF 1.87, +1201$) — nhưng sẽ cắt mất các con sóng lớn.

> ⚠️ **Lưu ý trung thực:** đây vẫn là backtest **in-sample 1 năm**. Đã gồm **spread thật** nhưng *chưa* mô phỏng
> slippage và requote. Hãy chạy lại trong **Strategy Tester của MT5** (Model = *Every tick based on real ticks*)
> với spread/commission **của chính broker bạn**, rồi **forward-test demo** trước khi vào tiền thật.

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
| `InpRiskMoney` | **50.0** | **1R — tiền rủi ro mỗi lệnh (đã gồm spread + commission)** |
| `InpCommissionPerLot` | 0.0 | Commission round-turn / 1 lot (nhập theo broker, vd 7.0) |
| `InpSLMode` | 0 | SL: `0`=Slow Trail, `1`=ATR×hệ số, `2`=Kijun |
| `InpSLATRMult` | 1.5 | Hệ số ATR cho SL khi `SLMode=1` |
| `InpMinSLpips` | 5.0 | Khoảng cách SL tối thiểu (pips) — chặn lot phình to |
| `InpTakeProfitRR` | **0.0** | TP theo bội số R. **`0` = gồng theo trend** (mặc định). Đặt `3.0` nếu muốn chốt cố định |
| `InpMaxLots` | 5.0 | Trần khối lượng an toàn |
| **Quản lý lệnh (thoát lệnh)** | | |
| `InpTrailMode` | **0** | Dời SL: `0`=none (gồng — khuyến nghị), `1`=Slow, `2`=Fast, `3`=Kijun |
| `InpExitOnOpposite` | true | Đóng khi ATR đảo chiều (= tín hiệu đảo trend) — **đây là cách gồng** |
| `InpExitOnCloudBreak` | false | Đóng khi giá đóng cửa quay lại qua mây Kumo |
| `InpMagic` | 990011 | Magic number (phân biệt lệnh của EA) |
| `InpMaxSpreadPts` | 30 | Spread tối đa (points) cho phép vào lệnh |

### Gồng hay TP? — Phân tích độ tối ưu & ổn định (chạy `python3 analyze.py <csv>`)

Quét mịn giá trị TP + chia đôi dữ liệu 2025 (nửa đầu / nửa cuối) để xem cấu hình nào **ổn định**:

```
Cấu hình   | tổng R  | PF   | avgWin | Nửa đầu      | Nửa cuối
-----------+---------+------+--------+--------------+-------------
TP=2R      | +14.0R  | 1.51 | +1.43R | +9.8R        | +4.2R
TP=2.5R    | +22.0R  | 1.80 | +1.71R | +13.8R       | +8.2R
TP=3R   ★  | +24.0R  | 1.87 | +1.78R | +12.6R       | +11.5R   ← cao nhất & CÂN nhất 2 nửa
TP=4R      | +20.5R  | 1.75 | +1.66R | +12.9R       | +7.6R
TP=6R      | +22.3R  | 1.81 | +1.72R | +12.4R       | +9.9R
GỒNG (TP=0)| +17.1R  | 1.62 | +1.54R | +10.9R       | +6.2R
```

**Kết luận: trên dữ liệu này, `TP = 3R` tối ưu hơn gồng** — lời cao hơn (+24R vs +17R), PF cao hơn (1.87 vs 1.62),
**và đều ở cả 2 nửa năm** (12.6R / 11.5R), trong khi **drawdown y hệt nhau** (mọi cấu hình ~3.7R, vì DD do logic
SL/vào lệnh quyết định, không phải do cách chốt). Đáng tin vì 3R **không phải đỉnh nhọn**: cả vùng 2.5R–6R đều cho +20–24R.

**Vì sao?** Trong 2025, EURUSD hay quay đầu sau khi đi được ~3R, nên "gồng" thường **trả lại lời** trong lúc chờ ATR
đảo chiều (avgWin của gồng chỉ +1.54R, thấp hơn TP=3R +1.78R). Một mức TP trần ~3R **chốt lời trước khi sóng hồi**.
→ Hiểu đúng: `TP=3R` thực ra là **"gồng có trần 3R"** (vẫn thoát sớm khi ATR đảo chiều nếu trend gãy trước 3R).

### Khuyến nghị cuối cùng
- 🥇 **Tối ưu theo số liệu:** `InpTakeProfitRR = 3.0`, `InpTrailMode = 0`, `InpExitOnOpposite = true`.
- 🥈 **Đúng "gồng" thuần (bạn yêu cầu):** `InpTakeProfitRR = 0`. Lợi thế *tiềm năng*: nếu gặp **năm có sóng cực lớn**
  (trend kéo dài > 4–5R), gồng sẽ ăn trọn còn TP=3R bị chốt sớm. 2025 không có sóng như vậy nên TP=3R thắng.
- ⚠️ Mọi con số là **in-sample 1 năm**. Vùng TP tối ưu có thể đổi theo năm/cặp tiền. Hãy chạy `analyze.py` trên dữ
  liệu năm khác (hoặc Strategy Tester MT5) để xác nhận trước khi quyết định. **Nhớ nhập `InpCommissionPerLot` của broker.**

---

## 5. Kiểm chứng lại bằng Python

```bash
cd mt5_ichimoku_atr_ea
python3 backtest.py  /đường_dẫn/EURUSD_H1_2025.csv   # 1 cấu hình + báo cáo chi tiết
python3 sweep.py     /đường_dẫn/EURUSD_H1_2025.csv   # so sánh nhiều cấu hình
```
File `backtest.py` tái hiện **đúng logic** của EA (Ichimoku donchian, ATR Wilder, đệ quy Trailing,
lọc mây, SL=Slow Trail, **mô phỏng spread thật + commission**, các kiểu thoát lệnh, vào lệnh ở open nến kế tiếp)
để bạn đối chiếu trước khi chạy MT5. Sửa các tham số ở đầu file `backtest.py` để thử cấu hình khác.

---

## 6. Giới hạn & lời khuyên

- Backtest 1 năm, in-sample. Đã gồm **spread thật + commission**, nhưng **chưa** mô phỏng slippage/requote
  → kết quả thật có thể thấp hơn chút. **Đừng kỳ vọng y hệt.**
- Nên **forward-test demo** vài tuần trước khi dùng tiền thật.
- Nhập `InpCommissionPerLot` đúng của broker. `tick_value`/`tick_size` EA tự lấy từ broker; nếu loại tài khoản
  (cent/standard) hay tiền tệ tài khoản khác, lot tự điều chỉnh — hãy xem log `[BUY/SELL] ... R=50$` để chắc rủi ro đúng.
- "Gồng theo trend" nghĩa là **không có TP** — có thể có lúc lời nổi rất lớn rồi co lại trước khi ATR báo đảo chiều.
  Đó là bản chất của cách bám trend; bù lại các con sóng lớn được giữ trọn. Nếu không chịu được, dùng `InpTrailMode=1`.
- EA mặc định **chỉ giữ 1 lệnh tại một thời điểm** trên symbol.
