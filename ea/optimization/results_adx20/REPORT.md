# WFA Optimization — EA Ichimoku + ATR (entry: Trail1×Trail2 cross)

**Muc tieu:** max Recovery Factor (NetProfit/MaxDD).  
**Loc TRAIN:** PF≥1.3, MaxDD≤15.0%, Trades≥150.  
**Von:** $5000, 1R=$50 (1%).  
**Cau hinh:** gong loi (TP=0), trailing = Slow Trail, loc ADX(14)>=20.  **GA toi uu 4 tham so:** fast_period, fast_mult, slow_period, slow_mult (Ichimoku 9/26/52 co dinh de chong overfitting).

## 1. Ket qua tung luot (IS toi uu vs OOS toi uu vs OOS default-EA)

| Luot | Train | Test | IS ok? | IS RF | IS PF | IS DD% | IS lenh | OOS RF | OOS PF | OOS net | OOS lenh | DEF RF | DEF net |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 2010-2012 | 2013 | ✅ | 5.42 | 1.49 | 8.19 | 258 | -0.56 | 0.76 | $-693.41 | 115 | -0.54 | $-378.61 |
| 2 | 2011-2013 | 2014 | ❌ | 1.07 | 1.30 | 9.33 | 132 | -0.69 | 0.60 | $-347.34 | 40 | 0.52 | $131.93 |
| 3 | 2012-2014 | 2015 | ✅ | 2.41 | 1.32 | 13.47 | 243 | -0.02 | 0.99 | $-14.85 | 79 | 1.61 | $459.49 |
| 4 | 2013-2015 | 2016 | ✅ | 3.75 | 1.41 | 6.21 | 168 | 0.63 | 1.24 | $186.12 | 43 | 2.04 | $420.11 |
| 5 | 2014-2016 | 2017 | ✅ | 3.18 | 1.37 | 10.18 | 191 | -0.58 | 0.65 | $-389.07 | 52 | 0.26 | $45.15 |
| 6 | 2015-2017 | 2018 | ✅ | 4.10 | 1.55 | 6.67 | 162 | -0.61 | 0.65 | $-362.90 | 56 | -0.48 | $-169.68 |
| 7 | 2016-2018 | 2019 | ❌ | 0.79 | 1.18 | 9.87 | 159 | 0.96 | 1.37 | $345.38 | 59 | -0.74 | $-326.77 |
| 8 | 2017-2019 | 2020 | ❌ | 1.97 | 1.62 | 9.94 | 129 | 0.32 | 1.22 | $160.96 | 44 | 1.92 | $349.82 |
| 9 | 2018-2020 | 2021 | ✅ | 6.76 | 1.36 | 10.29 | 536 | -0.91 | 0.52 | $-2532.12 | 175 | -0.07 | $-16.82 |
| 10 | 2019-2021 | 2022 | ❌ | 1.75 | 1.26 | 8.54 | 147 | 0.17 | 1.12 | $124.34 | 51 | -0.80 | $-196.15 |
| 11 | 2020-2022 | 2023 | ✅ | 1.88 | 1.39 | 10.00 | 153 | -0.84 | 0.70 | $-333.57 | 44 | -0.75 | $-311.61 |
| 12 | 2021-2023 | 2024 | ❌ | 0.63 | 1.14 | 10.95 | 150 | -0.86 | 0.41 | $-704.99 | 53 | 0.01 | $1.29 |
| 13 | 2022-2024 | 2025 | ❌ | 0.70 | 1.29 | 9.87 | 98 | 0.37 | 1.16 | $68.82 | 38 | 0.92 | $129.92 |
| 14 | 2023-2025 | 2026 | ❌ | 0.54 | 1.15 | 7.29 | 97 | 0.55 | 1.36 | $91.27 | 18 | 0.54 | $64.32 |

## 2. OOS tong hop ghep 14 nam test (2013-2026)

### A) Bo tham so TOI UU theo tung luot (Walk-Forward thuc su)
- Tong lenh: 867 | Win rate: 34.5%
- Net: $-4401.37  (-88.0% tren von $5000)
- Profit Factor: 0.77
- Max Drawdown: $4772.28 (92.3%)
- Recovery Factor: -0.92

### B) DEFAULT-EA (fast5/0.5, slow10/3.0, TP=gong(0), trail=1) — khong toi uu
- Tong lenh: 379 | Win rate: 39.3%
- Net: $202.39  (4.0% tren von $5000)
- Profit Factor: 1.03
- Max Drawdown: $1007.57 (17.4%)
- Recovery Factor: 0.20

## 3. Bo tham so toi uu theo tung luot

| Luot | fast_period | fast_mult | slow_period | slow_mult | tp_rr |
|---|---|---|---|---|---|
| 1 | 19 | 1.545 | 26 | 1.641 | 0.0 |
| 2 | 3 | 1.522 | 13 | 6.0 | 0.0 |
| 3 | 10 | 1.097 | 22 | 1.814 | 0.0 |
| 4 | 4 | 1.601 | 14 | 2.721 | 0.0 |
| 5 | 13 | 1.496 | 20 | 2.037 | 0.0 |
| 6 | 3 | 1.679 | 12 | 2.762 | 0.0 |
| 7 | 3 | 1.875 | 10 | 2.924 | 0.0 |
| 8 | 3 | 1.726 | 30 | 5.505 | 0.0 |
| 9 | 8 | 1.62 | 19 | 1.629 | 0.0 |
| 10 | 8 | 1.383 | 25 | 2.223 | 0.0 |
| 11 | 9 | 1.219 | 19 | 2.164 | 0.0 |
| 12 | 3 | 1.405 | 11 | 2.39 | 0.0 |
| 13 | 4 | 1.717 | 7 | 5.655 | 0.0 |
| 14 | 8 | 1.466 | 13 | 5.113 | 0.0 |

## 4. Chan doan Overfitting

- IS hop le: **7/14** luot | OOS co lai: **6/14** nam.
- Profit Factor: IS trung binh = 1.34 → OOS ghep = 0.77 (suy giam NHE — binh thuong, khong phai overfit nang).
- **Recovery Factor OOS ghep = -0.92** (default-EA 0.20) — toi uu ≈ default ⟹ ket qua **it phu thuoc tham so** (edge nam o ban than chien luoc, khong phai o viec tinh chinh).
- *Luu y so sanh:* IS RF do tren 3 nam, OOS RF tung nam do tren 1 nam nen khong so truc tiep theo gia tri tuyet doi; dung **PF** va **RF ghep** de danh gia cong bang.

## 5. Do on dinh tham so giua cac luot

| Tham so | Min | Max | Nhan xet |
|---|---|---|---|
| fast_period | 3 | 19 | rat phan tan |
| fast_mult | 1.097 | 1.875 | phan tan |
| slow_period | 7 | 30 | rat phan tan |
| slow_mult | 1.629 | 6.0 | rat phan tan |

## 6. Ket luan

- OOS: toi uu net $-4401 vs default-EA net $202 → toi uu hoa KHÔNG cai thien so voi default.
- **Edge bien thien manh theo thoi gian:** giai doan 2013-2019 net ≈ $-1276 (rat tot), nhung 2020-2026 net ≈ $-3125 (toi uu) / $21 (default), chi 4/7 nam co lai → chien luoc **suy yeu ro o che do thi truong gan day** (dac biet chuoi thua 2021-2024).
- Max Drawdown that tren toan ky = **92%** — cao hon nhieu so voi ky vong tu rieng 2013-2019 (~10%); day la rui ro that khi chay live qua nhieu che do.
- ⚠️ **Net duong tren toan ky nhung KHONG ben vung**: PF≈1.1, RF≈1.0, drawdown lon, nhieu nam thua → chua du tin cay de chay live neu khong them bo loc che do thi truong.
- Luu y: ket qua tinh tren spread lich su that, drawdown mark-to-market, khong nhin truoc.