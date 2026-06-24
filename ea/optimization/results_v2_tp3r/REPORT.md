# WFA Optimization — EA Ichimoku + ATR (entry: Trail1×Trail2 cross)

**Muc tieu:** max Recovery Factor (NetProfit/MaxDD).  
**Loc TRAIN:** PF≥1.3, MaxDD≤15.0%, Trades≥150.  
**Von:** $5000, 1R=$50 (1%).  
**Cau hinh:** TP co dinh 3.0R, trailing = khong/gong.  **GA toi uu 4 tham so:** fast_period, fast_mult, slow_period, slow_mult (Ichimoku 9/26/52 co dinh de chong overfitting).

## 1. Ket qua tung luot (IS toi uu vs OOS toi uu vs OOS default-EA)

| Luot | Train | Test | IS ok? | IS RF | IS PF | IS DD% | IS lenh | OOS RF | OOS PF | OOS net | OOS lenh | DEF RF | DEF net |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 2010-2012 | 2013 | ✅ | 8.02 | 1.61 | 5.16 | 214 | -0.05 | 0.99 | $-28.27 | 96 | 0.07 | $33.80 |
| 2 | 2011-2013 | 2014 | ✅ | 3.89 | 1.32 | 7.00 | 260 | 0.32 | 1.09 | $168.75 | 83 | 0.32 | $153.98 |
| 3 | 2012-2014 | 2015 | ✅ | 4.67 | 1.39 | 7.71 | 273 | 2.09 | 1.56 | $1055.58 | 81 | 1.91 | $739.17 |
| 4 | 2013-2015 | 2016 | ✅ | 4.22 | 1.35 | 9.11 | 262 | 0.35 | 1.11 | $175.25 | 75 | 0.30 | $125.72 |
| 5 | 2014-2016 | 2017 | ✅ | 6.24 | 1.53 | 5.93 | 212 | 0.05 | 1.01 | $16.95 | 60 | 1.02 | $378.25 |
| 6 | 2015-2017 | 2018 | ✅ | 6.69 | 1.56 | 4.73 | 202 | 1.03 | 1.46 | $541.12 | 66 | 1.10 | $446.33 |
| 7 | 2016-2018 | 2019 | ✅ | 5.12 | 1.56 | 6.17 | 193 | 0.36 | 1.10 | $161.94 | 75 | 0.22 | $104.69 |
| 8 | 2017-2019 | 2020 | ✅ | 5.17 | 1.66 | 6.18 | 161 | 1.18 | 1.51 | $510.90 | 63 | 1.08 | $389.64 |
| 9 | 2018-2020 | 2021 | ✅ | 6.22 | 1.84 | 6.19 | 163 | -0.59 | 0.85 | $-218.45 | 67 | -0.19 | $-114.61 |
| 10 | 2019-2021 | 2022 | ✅ | 8.32 | 1.73 | 3.76 | 176 | -0.91 | 0.63 | $-521.97 | 64 | -0.34 | $-203.21 |
| 11 | 2020-2022 | 2023 | ❌ | 1.17 | 1.24 | 10.14 | 170 | -0.59 | 0.59 | $-469.71 | 62 | -0.35 | $-248.17 |
| 12 | 2021-2023 | 2024 | ❌ | -0.49 | 0.91 | 11.01 | 163 | -0.70 | 0.63 | $-487.70 | 62 | -0.57 | $-548.17 |
| 13 | 2022-2024 | 2025 | ❌ | 0.12 | 1.02 | 11.30 | 183 | 1.51 | 1.40 | $370.22 | 55 | 5.75 | $1125.09 |
| 14 | 2023-2025 | 2026 | ✅ | 1.94 | 1.34 | 12.40 | 186 | 0.81 | 1.44 | $201.11 | 27 | -0.26 | $-133.71 |

## 2. OOS tong hop ghep 14 nam test (2013-2026)

### A) Bo tham so TOI UU theo tung luot (Walk-Forward thuc su)
- Tong lenh: 936 | Win rate: 36.9%
- Net: $1475.71  (29.5% tren von $5000)
- Profit Factor: 1.08
- Max Drawdown: $1953.04 (25.3%)
- Recovery Factor: 0.76

### B) DEFAULT-EA (fast5/0.5, slow10/3.0, TP=3.0R, trail=0) — khong toi uu
- Tong lenh: 994 | Win rate: 37.2%
- Net: $2248.80  (45.0% tren von $5000)
- Profit Factor: 1.10
- Max Drawdown: $1933.29 (24.8%)
- Recovery Factor: 1.16

## 3. Bo tham so toi uu theo tung luot

| Luot | fast_period | fast_mult | slow_period | slow_mult | tp_rr |
|---|---|---|---|---|---|
| 1 | 3 | 0.617 | 24 | 2.705 | 3.0 |
| 2 | 7 | 0.613 | 25 | 2.641 | 3.0 |
| 3 | 8 | 0.983 | 23 | 2.599 | 3.0 |
| 4 | 7 | 0.445 | 21 | 2.643 | 3.0 |
| 5 | 8 | 1.95 | 18 | 3.075 | 3.0 |
| 6 | 5 | 1.559 | 9 | 3.135 | 3.0 |
| 7 | 6 | 1.701 | 11 | 3.126 | 3.0 |
| 8 | 12 | 1.185 | 30 | 4.608 | 3.0 |
| 9 | 5 | 1.5 | 9 | 4.173 | 3.0 |
| 10 | 6 | 1.827 | 7 | 4.117 | 3.0 |
| 11 | 3 | 0.986 | 10 | 5.524 | 3.0 |
| 12 | 7 | 1.398 | 12 | 5.97 | 3.0 |
| 13 | 8 | 1.452 | 21 | 4.795 | 3.0 |
| 14 | 8 | 1.181 | 8 | 3.558 | 3.0 |

## 4. Chan doan Overfitting

- IS hop le: **11/14** luot | OOS co lai: **9/14** nam.
- Profit Factor: IS trung binh = 1.43 → OOS ghep = 1.08 (suy giam NHE — binh thuong, khong phai overfit nang).
- **Recovery Factor OOS ghep = 0.76** (default-EA 1.16) — toi uu ≈ default ⟹ ket qua **it phu thuoc tham so** (edge nam o ban than chien luoc, khong phai o viec tinh chinh).
- *Luu y so sanh:* IS RF do tren 3 nam, OOS RF tung nam do tren 1 nam nen khong so truc tiep theo gia tri tuyet doi; dung **PF** va **RF ghep** de danh gia cong bang.

## 5. Do on dinh tham so giua cac luot

| Tham so | Min | Max | Nhan xet |
|---|---|---|---|
| fast_period | 3 | 12 | rat phan tan |
| fast_mult | 0.445 | 1.95 | rat phan tan |
| slow_period | 7 | 30 | rat phan tan |
| slow_mult | 2.599 | 5.97 | phan tan |

## 6. Ket luan

- OOS: toi uu net $1476 vs default-EA net $2249 → toi uu hoa KHÔNG cai thien so voi default.
- **Edge bien thien manh theo thoi gian:** giai doan 2013-2019 net ≈ $2091 (rat tot), nhung 2020-2026 net ≈ $-616 (toi uu) / $267 (default), chi 3/7 nam co lai → chien luoc **suy yeu ro o che do thi truong gan day** (dac biet chuoi thua 2021-2024).
- Max Drawdown that tren toan ky = **25%** — cao hon nhieu so voi ky vong tu rieng 2013-2019 (~10%); day la rui ro that khi chay live qua nhieu che do.
- ⚠️ **Net duong tren toan ky nhung KHONG ben vung**: PF≈1.1, RF≈1.0, drawdown lon, nhieu nam thua → chua du tin cay de chay live neu khong them bo loc che do thi truong.
- Luu y: ket qua tinh tren spread lich su that, drawdown mark-to-market, khong nhin truoc.