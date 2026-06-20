# Kronos Trading — Tín hiệu + Backtest

Biến dự báo của mô hình **Kronos** thành **tín hiệu giao dịch** rồi **backtest**, dùng
chung cho **Forex, Vàng, BTC/crypto và Chứng khoán Mỹ**. Hỗ trợ dữ liệu **MetaTrader 5**
và Yahoo Finance.

> ⚠️ **Miễn trừ trách nhiệm:** Công cụ *nghiên cứu/định lượng*, KHÔNG phải lời khuyên đầu
> tư. Kronos là mô hình dự báo xác suất, không đảm bảo lợi nhuận. Backtest quá khứ không
> phản ánh tương lai và đã đơn giản hoá. Luôn **paper-trade** trước khi dùng tiền thật.

## Hai engine backtest

| Engine | File | Khi nào dùng |
|---|---|---|
| **Event-driven (khuyên dùng)** | `trade_sim.py` | Có **điểm vào, stop-loss/take-profit, sizing theo R ($ thật), spread/slippage/commission**. Giống cách giao dịch thật. |
| Return-compounding (sơ khởi) | `backtest.py` | Bản nhanh, vị thế ±1, không SL/TP — chỉ để kiểm tra nhanh sức mạnh tín hiệu. |

```
         ┌────────────┐  ┌──────────────┐  ┌─────────────┐  ┌────────────────────────────┐
 Dữ liệu →│  data.py   │→ │ predictor.py │→ │  signals.py │→ │        trade_sim.py        │→ Báo cáo
 MT5/yf  │ OHLCV+spread│  │Kronos forecast│  │ → hướng L/S │  │ vào lệnh→SL/TP→sizing R→phí│  (JSON/CSV/PNG)
         └────────────┘  └──────────────┘  └─────────────┘  └────────────────────────────┘
```

---

## 🚀 Cách 1: Google Colab (khuyên dùng để test nhanh, có GPU)

Mở **[`trading/Kronos_Trading_Colab.ipynb`](./Kronos_Trading_Colab.ipynb)** trên
[Google Colab](https://colab.research.google.com/) (Runtime → GPU), rồi chạy từng cell:
nó tự clone repo, cài đặt, cho bạn **upload file MT5**, tải model Kronos và chạy backtest
với 1R = $25, SL/TP theo ATR, chi phí thật. Không cần cài gì trên máy.

## 💻 Cách 2: Chạy cục bộ (CLI)

```bash
pip install -r requirements.txt          # lõi Kronos (torch, ...)
pip install -r trading/requirements.txt  # yfinance, matplotlib

# Backtest thật trên file MT5 của bạn (Vàng M5), 1R = $25, R:R = 2:1
python -m trading.run_trade_backtest \
  --csv XAUUSDm_M5.csv --predictor kronos --model NeoQuasar/Kronos-small \
  --lookback 256 --pred-len 24 --signal-every 12 \
  --sl-atr 1.5 --rr 2.0 --risk-amount 25 --initial-capital 5000 \
  --slippage-points 5 --max-leverage 30
```

Thử nhanh **không cần model/mạng** bằng baseline:
```bash
python -m trading.run_trade_backtest --csv XAUUSDm_M5.csv --predictor momentum \
  --sl-atr 1.5 --rr 2 --risk-amount 25 --slippage-points 5
```

> **Lưu ý mạng (allowlist):** môi trường có allowlist egress cần mở `huggingface.co`
> (tải model) và `query1/query2.finance.yahoo.com` (dữ liệu yfinance). File MT5 cục bộ +
> baseline thì không cần mạng.

---

## ⭐ Bước 0 — Đo "edge" TRƯỚC khi tối ưu

Việc giá trị nhất trước mọi thứ: kiểm tra Kronos có **dự báo đúng hướng** không. Tối ưu
SL/TP/sizing trên một tín hiệu vô dụng là vô nghĩa.

```bash
python -m trading.run_trade_backtest --csv US30_M30.csv --predictor kronos \
  --lookback 256 --pred-len 24 --signal-every 4 --edge-only
```

Đọc kết quả:
- **Directional accuracy** ≥ ~55% (p nhỏ) → có edge rõ → đáng để giao dịch & tối ưu.
- ~50% (p lớn) → **không có edge** → đổi mã/khung, tăng `--sample-count`/`--ensemble`,
  hoặc fine-tune; đừng đụng SL/TP.
- **IC / Rank IC** > 0 và **accuracy theo |pred|** tăng dần (high > low) → tín hiệu mạnh
  thì đáng tin hơn → bật lọc độ tin cậy sẽ có ích.

> Lưu ý: bộ lọc trend/confidence chỉ **khuếch đại** một tín hiệu đã có edge; trên tín hiệu
> vô dụng (vd baseline momentum: accuracy ~48%, IC≈0) chúng chỉ làm nhỏ mẫu, không cứu được.

Đo **nhiều mã cùng lúc** (nạp model 1 lần) bằng bảng tổng hợp:

```bash
python -m trading.measure_edge_all --predictor kronos --model NeoQuasar/Kronos-small \
  --lookback 256 --pred-len 24 --signal-every 4 \
  --csv XAUUSD_M30.csv US30_M30.csv US500_M30.csv USTEC_M30.csv BTC_M30.csv
```

## Chiến lược: vào lệnh / stop-loss / take-profit

1. **Tín hiệu:** Kronos dự báo `pred_len` nến từ `lookback` nến gần nhất. Tính lợi nhuận
   kỳ vọng (`mean`/`endpoint`/`slope` của giá dự báo so với giá hiện tại). Vượt ngưỡng →
   **Long**; dưới ngưỡng âm → **Short**; còn lại đứng ngoài.
2. **Vào lệnh:** tại **giá mở nến kế tiếp** (không look-ahead), cộng nửa spread + slippage.
3. **Stop-loss / take-profit (theo ATR):**
   * `SL = entry ∓ sl_atr × ATR`  → khoảng cách này = **1R**
   * `TP = entry ± rr × (sl_atr × ATR)`  → chạm TP được **+rr R**
   * ATR tự co giãn theo biến động nên cùng tham số chạy được cho BTC, Vàng, Forex.
4. **Khối lượng (1R = $25):** `units = risk_$ ÷ khoảng_cách_SL`. Chạm SL mất đúng ~1R = $25.
   `--risk-mode percent --risk-pct 0.005` để 1R = 0.5% vốn (cuốn lãi theo tài khoản).
5. **Thoát:** SL/TP kiểm tra **trong nến** (dùng high/low; SL ưu tiên khi cả hai cùng nến).
   Nếu hết `max_hold` nến chưa chạm → thoát tại giá đóng cửa.
6. **Trailing stop (tùy chọn, `--trail`):** sau khi lời `trail_activate_r` R, SL được dời
   theo đỉnh/đáy thuận lợi (cách `trail_atr × ATR`), chỉ đi theo hướng có lợi để khóa lời.
   Kết hợp `--rr 0` (tắt TP) để "thả lệnh thắng chạy". Cập nhật trailing tính **sau** khi
   kiểm tra thoát trong mỗi nến nên **không look-ahead**.
7. **Chi phí:** **spread** (lấy thật từ cột `<SPREAD>` của MT5 theo từng nến) + **slippage**
   + **commission**, được **báo cáo tách riêng** để thấy rõ tác động.

### ⚠️ Hai cạm bẫy phải để ý (báo cáo đều hiển thị)
- **Đòn bẩy:** sizing theo R với stop hẹp → notional có thể gấp nhiều lần vốn
  (`Avg leverage`). Dùng `--max-leverage` để chặn.
- **Chi phí ăn mòn:** trên M5 giao dịch dày, riêng spread có thể vượt cả vốn
  (`Total costs paid`). Giảm bằng cách tăng `--signal-every`, nâng `--long-threshold`,
  hoặc dùng khung thời gian lớn hơn.

---

## Tham số chính (`run_trade_backtest`)

| Nhóm | Cờ | Ý nghĩa |
|---|---|---|
| Dữ liệu | `--csv / --symbol` | File MT5/CSV cục bộ hoặc mã yfinance |
| Model | `--predictor` | `kronos` \| `momentum` \| `persistence` |
| | `--model` `--sample-count` | Checkpoint Kronos; số đường dự báo lấy trung bình |
| | `--lookback` `--pred-len` `--signal-every` | Context; số nến dự báo; tần suất chạy model |
| Tín hiệu | `--signal-mode` `--long-threshold` `--no-short` | Cách đọc & lọc tín hiệu |
| SL/TP | `--sl-atr` `--rr` `--atr-period` `--max-hold` | Stop theo ATR (=1R); bội số R cho TP (`--rr 0` = tắt TP) |
| Trailing | `--trail` `--trail-atr` `--trail-activate-r` | Bật trailing stop; cách đỉnh/đáy bao nhiêu ATR; kích hoạt sau +mấy R |
| Lọc vào lệnh | `--trend-filter` `--trend-ema` | Chỉ vào lệnh thuận xu hướng EMA |
| | `--min-expected-r` | Chỉ vào khi dự báo move ≥ mấy R |
| | `--ensemble N` `--min-confidence` | Chạy N dự báo đo độ đồng thuận; chỉ vào khi đồng thuận ≥ ngưỡng |
| Chẩn đoán | `--edge-only` | Đo độ chính xác hướng / IC thay vì backtest |
| Vốn/rủi ro | `--risk-mode` `--risk-amount` `--risk-pct` | `fixed` $25 hoặc `percent` 0.5% vốn |
| | `--initial-capital` `--max-leverage` | Vốn ban đầu; trần đòn bẩy |
| Chi phí | `--no-data-spread` `--spread-points` | Dùng spread thật hay cố định |
| | `--slippage-points` `--commission-bps` `--commission-per-trade` | Trượt giá & hoa hồng |

---

## Dữ liệu MetaTrader 5

Loader tự nhận diện file xuất từ MT5 (`<DATE> <TIME> <OPEN> ... <SPREAD>`), tự suy
**point-size** từ số chữ số thập phân và quy đổi cột `<SPREAD>` (points) sang giá để mô
hình hoá chi phí. Đã kiểm thử trên BTCUSDTm / EURUSDm / XAUUSDm (M5).

## Kết quả xuất ra (`trading/results/`, đã `.gitignore`)
`<name>_metrics.json` · `<name>_trades.csv` · `<name>_equity.csv` · `<name>_backtest.png`

Chỉ số gồm: net profit ($), total return, CAGR, max drawdown, Sharpe, **win rate, profit
factor, expectancy, avg R**, số lệnh long/short, **đếm hit TP/SL/timeout**, **avg leverage**,
và **bóc tách chi phí** (spread/slippage/commission), kèm benchmark buy & hold.

## Dùng như thư viện

```python
from trading.data import load_csv
from trading.trade_sim import TradeConfig, run_trade_sim, save_trade_results, format_trade_metrics
from trading.signals import SignalConfig
from trading.sizing import SizingConfig
from trading.predictor import load_kronos_predictor, make_kronos_predict_fn

df = load_csv("XAUUSDm_M5.csv")                       # tự nhận diện MT5 + spread
predictor = load_kronos_predictor("NeoQuasar/Kronos-small", device="cuda:0")
predict_fn = make_kronos_predict_fn(predictor, sample_count=3)

cfg = TradeConfig(
    lookback=256, pred_len=24, signal_every=12,
    sl_atr=1.5, rr=2.0,
    sizing=SizingConfig(mode="fixed", risk_amount=25, max_leverage=30),
    initial_capital=5000, use_data_spread=True, slippage_points=5,
    signal=SignalConfig(mode="mean", allow_short=True),
)
result = run_trade_sim(df, predict_fn, cfg)
print(format_trade_metrics(result["metrics"]))
save_trade_results(result, "trading/results", "XAUUSD_kronos")
```

## Kiểm thử

```bash
python -m trading.test_trade_sim     # SL=-1R, TP=+rrR, chi phí, sizing, timeout
python -m trading.test_pipeline      # engine sơ khởi: dấu tín hiệu, không look-ahead
```

## Hướng phát triển tiếp
- **Position sizing** theo độ tin cậy dự báo (độ phân tán các đường sample).
- **Break-even tự động**, lọc theo phiên giao dịch, lọc biến động (trailing stop đã có).
- **Fine-tune** Kronos trên đúng mã/khung của bạn (xem `finetune_csv/`) rồi trỏ `--model`
  vào checkpoint local.
- **Paper/live**: nối `predict_fn` với API sàn (vd MT5 qua `MetaTrader5`, crypto qua `ccxt`).
