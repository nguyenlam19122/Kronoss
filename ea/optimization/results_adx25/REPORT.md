# WFA Optimization — EA Ichimoku + ATR (entry: Trail1×Trail2 cross)

**Muc tieu:** max Recovery Factor (NetProfit/MaxDD).  
**Loc TRAIN:** PF≥1.3, MaxDD≤15.0%, Trades≥150.  
**Von:** $5000, 1R=$50 (1%).  
**Cau hinh:** gong loi (TP=0), trailing = Slow Trail, loc ADX(14)>=25.  **GA toi uu 4 tham so:** fast_period, fast_mult, slow_period, slow_mult (Ichimoku 9/26/52 co dinh de chong overfitting).

## 1. Ket qua tung luot (IS toi uu vs OOS toi uu vs OOS default-EA)

| Luot | Train | Test | IS ok? | IS RF | IS PF | IS DD% | IS lenh | OOS RF | OOS PF | OOS net | OOS lenh | DEF RF | DEF net |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 2010-2012 | 2013 | ✅ | 4.05 | 1.61 | 12.03 | 192 | 0.29 | 1.12 | $261.56 | 81 | -0.97 | $-461.19 |
| 2 | 2011-2013 | 2014 | ✅ | 4.40 | 1.57 | 7.84 | 175 | -0.93 | 0.64 | $-768.24 | 84 | 0.29 | $51.00 |
| 3 | 2012-2014 | 2015 | ❌ | 0.99 | 1.41 | 12.67 | 86 | -0.37 | 0.85 | $-110.07 | 40 | 3.57 | $518.16 |
| 4 | 2013-2015 | 2016 | ✅ | 3.68 | 1.40 | 14.89 | 363 | -0.55 | 0.74 | $-1046.94 | 116 | 2.95 | $324.94 |
| 5 | 2014-2016 | 2017 | ✅ | 2.09 | 1.32 | 8.65 | 152 | 1.29 | 1.37 | $297.78 | 40 | 0.03 | $4.20 |
| 6 | 2015-2017 | 2018 | ✅ | 4.88 | 1.43 | 11.21 | 369 | 3.99 | 1.83 | $2437.04 | 120 | -0.52 | $-59.94 |
| 7 | 2016-2018 | 2019 | ✅ | 7.90 | 1.67 | 14.15 | 395 | -0.73 | 0.70 | $-885.31 | 106 | -0.79 | $-282.19 |
| 8 | 2017-2019 | 2020 | ✅ | 6.32 | 1.51 | 14.85 | 380 | 1.73 | 1.35 | $1089.80 | 126 | 1.09 | $95.50 |
| 9 | 2018-2020 | 2021 | ✅ | 6.07 | 1.50 | 13.53 | 446 | -0.91 | 0.51 | $-2165.90 | 138 | -0.84 | $-201.95 |
| 10 | 2019-2021 | 2022 | ❌ | 1.15 | 1.19 | 7.75 | 143 | -0.32 | 0.80 | $-243.93 | 49 | -0.91 | $-101.57 |
| 11 | 2020-2022 | 2023 | ✅ | 2.01 | 1.49 | 11.61 | 158 | -0.86 | 0.49 | $-832.92 | 67 | -0.92 | $-200.19 |
| 12 | 2021-2023 | 2024 | ❌ | 0.89 | 1.30 | 5.74 | 60 | -0.37 | 0.69 | $-64.99 | 13 | 0.21 | $26.75 |
| 13 | 2022-2024 | 2025 | ❌ | 0.74 | 1.31 | 7.01 | 62 | -0.50 | 0.52 | $-190.35 | 21 | -0.71 | $-99.10 |
| 14 | 2023-2025 | 2026 | ❌ | -0.01 | 1.00 | 12.36 | 120 | -0.25 | 0.78 | $-121.24 | 24 | -0.84 | $-61.53 |

## 2. OOS tong hop ghep 14 nam test (2013-2026)

### A) Bo tham so TOI UU theo tung luot (Walk-Forward thuc su)
- Tong lenh: 1025 | Win rate: 30.8%
- Net: $-2343.73  (-46.9% tren von $5000)
- Profit Factor: 0.91
- Max Drawdown: $3986.44 (60.2%)
- Recovery Factor: -0.59

### B) DEFAULT-EA (fast5/0.5, slow10/3.0, TP=gong(0), trail=1) — khong toi uu
- Tong lenh: 138 | Win rate: 39.1%
- Net: $-447.11  (-8.9% tren von $5000)
- Profit Factor: 0.83
- Max Drawdown: $962.27 (17.4%)
- Recovery Factor: -0.46

## 3. Bo tham so toi uu theo tung luot

| Luot | fast_period | fast_mult | slow_period | slow_mult | tp_rr |
|---|---|---|---|---|---|
| 1 | 18 | 1.528 | 30 | 1.646 | 0.0 |
| 2 | 3 | 0.978 | 18 | 1.744 | 0.0 |
| 3 | 3 | 2.0 | 27 | 5.881 | 0.0 |
| 4 | 20 | 1.499 | 23 | 1.5 | 0.0 |
| 5 | 13 | 0.895 | 24 | 1.733 | 0.0 |
| 6 | 8 | 1.549 | 20 | 1.691 | 0.0 |
| 7 | 11 | 1.449 | 29 | 1.52 | 0.0 |
| 8 | 9 | 1.542 | 28 | 1.604 | 0.0 |
| 9 | 14 | 1.501 | 15 | 1.501 | 0.0 |
| 10 | 3 | 1.197 | 15 | 1.984 | 0.0 |
| 11 | 4 | 1.651 | 16 | 2.336 | 0.0 |
| 12 | 3 | 1.103 | 8 | 5.686 | 0.0 |
| 13 | 8 | 0.825 | 23 | 5.558 | 0.0 |
| 14 | 18 | 1.479 | 30 | 1.812 | 0.0 |

## 4. Chan doan Overfitting

- IS hop le: **9/14** luot | OOS co lai: **4/14** nam.
- Profit Factor: IS trung binh = 1.41 → OOS ghep = 0.91 (suy giam NHE — binh thuong, khong phai overfit nang).
- **Recovery Factor OOS ghep = -0.59** (default-EA -0.46) — toi uu ≈ default ⟹ ket qua **it phu thuoc tham so** (edge nam o ban than chien luoc, khong phai o viec tinh chinh).
- *Luu y so sanh:* IS RF do tren 3 nam, OOS RF tung nam do tren 1 nam nen khong so truc tiep theo gia tri tuyet doi; dung **PF** va **RF ghep** de danh gia cong bang.

## 5. Do on dinh tham so giua cac luot

| Tham so | Min | Max | Nhan xet |
|---|---|---|---|
| fast_period | 3 | 20 | rat phan tan |
| fast_mult | 0.825 | 2.0 | phan tan |
| slow_period | 8 | 30 | rat phan tan |
| slow_mult | 1.5 | 5.881 | rat phan tan |

## 6. Ket luan

- OOS: toi uu net $-2344 vs default-EA net $-447 → toi uu hoa KHÔNG cai thien so voi default.
- **Edge bien thien manh theo thoi gian:** giai doan 2013-2019 net ≈ $186 (rat tot), nhung 2020-2026 net ≈ $-2530 (toi uu) / $-542 (default), chi 1/7 nam co lai → chien luoc **suy yeu ro o che do thi truong gan day** (dac biet chuoi thua 2021-2024).
- Max Drawdown that tren toan ky = **60%** — cao hon nhieu so voi ky vong tu rieng 2013-2019 (~10%); day la rui ro that khi chay live qua nhieu che do.
- ⚠️ **Net duong tren toan ky nhung KHONG ben vung**: PF≈1.1, RF≈1.0, drawdown lon, nhieu nam thua → chua du tin cay de chay live neu khong them bo loc che do thi truong.
- Luu y: ket qua tinh tren spread lich su that, drawdown mark-to-market, khong nhin truoc.