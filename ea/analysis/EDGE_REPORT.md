# Kiem dinh EDGE that hay ao — EA Ichimoku ATR ScaleOut (MT5, 2020-2026)

Don vi phan tich = **per-trade R-multiple** (1R = $20). Du lieu = MT5 Strategy Tester.

## 1. Tong hop & phan dinh

| Symbol | N lenh | Win% | Expectancy | PF | SQN | T-test p (E>0) | Bootstrap CI(E) | MC P(lai) | MC MaxDD p95 | Phan dinh |
|---|---|---|---|---|---|---|---|---|---|---|
| EURUSD | 266 | 41% | +0.113R | 1.30 | 0.88 | 0.075 | [-0.037, +0.270] | 93% | 9% | **WEAK / chua chac** |
| GBPUSD | 402 | 42% | -0.022R | 0.94 | -0.22 | 0.668 | [-0.121, +0.081] | 33% | 20% | **FAKE / khong du bang chung** |
| USDJPY | 294 | 41% | +0.043R | 1.11 | 0.37 | 0.264 | [-0.086, +0.181] | 73% | 13% | **FAKE / khong du bang chung** |

## 2. Thi truong co xu huong hay khong (EURUSD H1, 2020-2026)

- **Hurst** = 0.534  (>0.5 trend, <0.5 hoi quy)
- **Variance Ratio(5)** = 0.964 (z=-3.31)
- **Autocorr lag-1** = -0.0186
- **Efficiency Ratio** = 0.245
- **ADX trung binh** = 26.2 | **% thoi gian ADX>25** = 47%
- **Ket luan:** GAN NGAU NHIEN (random walk)

## 3. Doc ket qua

- **Edge that** can hoi du: Expectancy>0, T-test p<0.05, Bootstrap CI(E) khong chua 0 (can duoi>0), va Monte Carlo P(lai)>=95%. Thieu cac dieu nay => edge yeu/ao (co the do may rui).
- **Runs/Chi-square**: p<0.05 => chuoi thang/thua KHONG doc lap (co streak) — anh huong rui ro chuoi thua lien tiep, can tinh trong sizing.
- **Live duoc khong**: nhin Monte Carlo MaxDD p95 va P(ruin) — neu MaxDD p95 vuot suc chiu dung hoac P(lai)<60% thi khong nen chay live du backtest duong.

## 4. Ket luan tong

- **0/3 cap tien co edge that** theo tieu chi nghiem ngat.
- **EURUSD** la cap **in-sample** (chien luoc da duoc toi uu tren chinh no) => ket qua duong (E=+0.11R) co the do **selection bias**; T-test p=0.075 va bootstrap CI van **chua 0** => CHUA du y nghia thong ke.
- **GBPUSD & USDJPY** la **out-of-sample (cap tien khac)** — phep thu bao tong that su: ca hai **khong co edge** (GBPUSD am, USDJPY trong vung nhieu). Chien luoc **khong khai quat** sang cap khac.
- Phu hop voi regime: EURUSD 2020-2026 **GAN NGAU NHIEN (random walk)** (Hurst~0.53, VR<1, Efficiency thap) — moi truong **thieu xu huong**, dung kieu thi truong ma trend-following thua.
- **Phan dinh chung: edge phan lon la FAKE/overfit + phu thuoc regime.** Khong nen chay live voi tien that o giai doan thi truong nhu 2020-2026; neu chay, chi demo/forward-test va bat buoc co bo loc che do thi truong (chi giao dich khi thuc su co trend).