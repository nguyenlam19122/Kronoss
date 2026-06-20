# Kronos Trading — Tín hiệu + Backtest

Pipeline tổng quát biến dự báo của mô hình **Kronos** thành **tín hiệu giao dịch** và
**backtest walk-forward** (không look-ahead), dùng chung cho **Forex, Vàng, BTC/crypto
và Chứng khoán Mỹ**.

```
            ┌──────────────┐   ┌─────────────────┐   ┌──────────────┐   ┌────────────────────┐
 Dữ liệu →  │  data.py     │ → │  predictor.py   │ → │  signals.py  │ → │   backtest.py      │ → Báo cáo
 OHLCV      │ yfinance/CSV │   │ Kronos forecast │   │ → vị thế ±1  │   │ walk-forward + P&L │   (JSON/CSV/PNG)
            └──────────────┘   └─────────────────┘   └──────────────┘   └────────────────────┘
```

> ⚠️ **Miễn trừ trách nhiệm:** Đây là công cụ *nghiên cứu/định lượng*, KHÔNG phải lời
> khuyên đầu tư. Kronos là mô hình **dự báo xác suất**, không đảm bảo lợi nhuận. Kết quả
> backtest trong quá khứ không phản ánh tương lai. Luôn **paper trade** trước khi dùng
> tiền thật, và backtest đã đơn giản hoá (khớp lệnh tại giá đóng cửa, chi phí gộp một
> mức phẳng — xem mục [Cách backtest hoạt động](#cách-backtest-hoạt-động)).

---

## 1. Cài đặt

```bash
# Từ thư mục gốc repo
pip install -r requirements.txt          # lõi Kronos (numpy, pandas, torch, ...)
pip install -r trading/requirements.txt  # thêm: yfinance, matplotlib
```

### Lưu ý về mạng (allowlist)
Pipeline cần truy cập 2 nhóm host. Nếu chạy trong môi trường có **allowlist egress**
(như Claude Code on the web), hãy thêm các host sau vào cấu hình mạng của environment:

| Mục đích | Host |
|---|---|
| Tải weights Kronos | `huggingface.co`, `cdn-lfs.huggingface.co`, `*.hf.co` |
| Lấy dữ liệu giá | `query1.finance.yahoo.com`, `query2.finance.yahoo.com` |

Nếu không mở được mạng, vẫn chạy được pipeline bằng **file CSV cục bộ** (`--csv`) và
**baseline** (`--predictor momentum`) — xem mục Quick start.

---

## 2. Quick start

### a) Chạy thử không cần model/mạng (kiểm tra pipeline)
Dùng baseline `momentum` trên CSV có sẵn trong repo:

```bash
python -m trading.run_backtest \
  --csv finetune_csv/data/HK_ali_09988_kline_5min_all.csv \
  --predictor momentum --lookback 256 --pred-len 24 --quiet
```

### b) Backtest thật với Kronos
```bash
# BTC daily, 3 năm, trung bình 3 đường dự báo cho tín hiệu ổn định hơn
python -m trading.run_backtest \
  --symbol btc --interval 1d --period 3y \
  --predictor kronos --model NeoQuasar/Kronos-small \
  --lookback 400 --pred-len 24 --sample-count 3
```

### Ví dụ cho từng thị trường
```bash
python -m trading.run_backtest --symbol gold   --interval 1d --period 5y   # Vàng (GC=F)
python -m trading.run_backtest --symbol eurusd --interval 1d --period 5y   # Forex EUR/USD
python -m trading.run_backtest --symbol AAPL   --interval 1d --period 5y   # CK Mỹ
python -m trading.run_backtest --symbol BTC-USD --interval 1h --period 3mo # BTC khung 1h
```

Bí danh hỗ trợ sẵn: `btc, eth, gold, xauusd, silver, eurusd, gbpusd, usdjpy, audusd ...`
(mã không nằm trong danh sách sẽ được dùng nguyên văn, vd `SPY`, `TSLA`, `NVDA`).

---

## 3. Tham số quan trọng

| Nhóm | Cờ | Ý nghĩa |
|---|---|---|
| Dữ liệu | `--symbol / --csv` | Nguồn dữ liệu (Yahoo hoặc CSV cục bộ) |
| | `--interval` | Khung nến: `1d`, `1h`, `15m` ... (Yahoo giới hạn lịch sử intraday) |
| | `--period` / `--start --end` | Khoảng thời gian |
| Model | `--predictor` | `kronos` (model thật) \| `momentum` \| `persistence` (baseline) |
| | `--model` | `NeoQuasar/Kronos-small` \| `-base` \| `-mini` hoặc đường dẫn local |
| | `--sample-count` | Số đường dự báo lấy trung bình (≥2 giúp tín hiệu ổn định) |
| | `--T --top-p` | Nhiệt độ & nucleus sampling (độ ngẫu nhiên dự báo) |
| Tín hiệu | `--signal-mode` | `mean` (mặc định) \| `endpoint` \| `slope` — cách đọc kỳ vọng từ dự báo |
| | `--horizon` | Dùng bao nhiêu nến dự báo để ra tín hiệu (mặc định = `pred_len`) |
| | `--long-threshold` | Ngưỡng % lợi nhuận kỳ vọng để mở Long (lọc nhiễu) |
| | `--short-threshold` | Ngưỡng để mở Short |
| | `--no-short` | Chỉ Long/đứng ngoài (cho tài khoản không bán khống) |
| Backtest | `--lookback` | Số nến lịch sử nạp vào model (≤ `max_context` = 512) |
| | `--pred-len` | Số nến model dự báo mỗi bước |
| | `--step` | Tần suất tái cân bằng (mặc định = `pred_len`, không chồng lấn) |
| | `--cost` | Chi phí mỗi chiều (phần thập phân, vd `0.0005` = 0.05%) |
| | `--bars-per-year` | Hệ số quy năm (mặc định tự suy từ khoảng cách nến) |

---

## 4. Cách backtest hoạt động

Vòng lặp **walk-forward** (đứng tại giá đóng cửa nến `t-1`):

1. `context` = các nến `[t-lookback : t]` (chỉ quá khứ).
2. `predict_fn(context)` → dự báo `pred_len` nến tương lai.
3. So sánh dự báo với giá đóng cửa hiện tại → vị thế `{-1, 0, +1}` (short/đứng ngoài/long).
4. Áp vị thế đó lên **lợi suất thực tế** của `step` nến kế tiếp; trừ chi phí khi đổi vị thế.

Sau đó `t += step`. **Không look-ahead:** vị thế của nến `j` chỉ dùng dữ liệu tới nến `j-1`
(đã được kiểm chứng bằng test oracle/anti-oracle trong `test_pipeline.py`).

**Giả định / đơn giản hoá** (cố ý nêu rõ):
- Khớp lệnh tại giá đóng cửa; lợi suất tính close-to-close.
- Chi phí mô hình hoá bằng một mức phẳng mỗi chiều trên turnover (gồm phí + trượt giá).
  Chưa mô hình hoá khớp lệnh trong nến và tác động thị trường.
- Hệ số quy năm suy từ khoảng cách nến trung vị (với mã giao dịch theo phiên như cổ
  phiếu, nên cân nhắc đặt `--bars-per-year` thủ công thay vì để tự suy).

---

## 5. Kết quả xuất ra

Lưu trong `trading/results/<name>_*` (đã được `.gitignore`):

| File | Nội dung |
|---|---|
| `<name>_metrics.json` | Toàn bộ chỉ số (total return, CAGR, Sharpe, Sortino, max drawdown, win rate, turnover, so với buy & hold ...) |
| `<name>_trades.csv` | Danh sách lệnh (entry/exit, chiều, số nến giữ, lợi nhuận) |
| `<name>_equity.csv` | Chuỗi theo từng nến: vị thế, lợi suất, equity, benchmark |
| `<name>_backtest.png` | Biểu đồ equity vs buy & hold + đường drawdown |

---

## 6. Dùng như thư viện (Python)

```python
from trading import load_data, run_walk_forward, BacktestConfig, SignalConfig, save_results
from trading.predictor import load_kronos_predictor, make_kronos_predict_fn

df = load_data(symbol="btc", interval="1d", period="2y")

predictor = load_kronos_predictor("NeoQuasar/Kronos-small")
predict_fn = make_kronos_predict_fn(predictor, T=1.0, top_p=0.9, sample_count=3)

cfg = BacktestConfig(
    lookback=400, pred_len=24,
    signal=SignalConfig(mode="mean", long_threshold=0.002, allow_short=True),
    cost=0.0005,
)
result = run_walk_forward(df, predict_fn, cfg)
print(result["metrics"])
save_results(result, out_dir="trading/results", name="btc_kronos")
```

Engine nhận `predict_fn` qua dependency injection nên có thể cắm model Kronos thật,
baseline, hoặc bất kỳ bộ dự báo nào khác.

---

## 7. Kiểm thử

```bash
python -m trading.test_pipeline      # hoặc: pytest trading/test_pipeline.py
```

Bộ test kiểm chứng: dấu tín hiệu, không look-ahead, chi phí làm giảm lợi nhuận,
suy hệ số quy năm, và oracle (đoán đúng hướng) phải thắng buy & hold còn anti-oracle
phải thua.

---

## 8. Hướng phát triển tiếp (gợi ý)

- **Position sizing** theo độ tin cậy dự báo (độ phân tán các đường sample) thay vì ±1.
- **Stop-loss / take-profit** và quản trị rủi ro theo biến động (ATR).
- **Fine-tune** Kronos trên đúng mã/khung của bạn (xem `finetune_csv/`) rồi trỏ
  `--model` vào checkpoint local để cải thiện chất lượng dự báo.
- **Live/paper trading**: nối `predict_fn` với API sàn (vd ccxt cho crypto) — engine
  tín hiệu tái sử dụng được nguyên vẹn.
