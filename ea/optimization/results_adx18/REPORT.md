# WFA Optimization — EA Ichimoku + ATR (entry: Trail1×Trail2 cross)

**Muc tieu:** max Recovery Factor (NetProfit/MaxDD).  
**Loc TRAIN:** PF≥1.3, MaxDD≤15.0%, Trades≥150.  
**Von:** $5000, 1R=$50 (1%).  
**Cau hinh:** gong loi (TP=0), trailing = Slow Trail, loc ADX(14)>=18.  **GA toi uu 4 tham so:** fast_period, fast_mult, slow_period, slow_mult (Ichimoku 9/26/52 co dinh de chong overfitting).

## 1. Ket qua tung luot (IS toi uu vs OOS toi uu vs OOS default-EA)

| Luot | Train | Test | IS ok? | IS RF | IS PF | IS DD% | IS lenh | OOS RF | OOS PF | OOS net | OOS lenh | DEF RF | DEF net |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 2010-2012 | 2013 | ✅ | 9.49 | 1.69 | 8.94 | 329 | -0.76 | 0.78 | $-785.56 | 139 | -0.38 | $-296.52 |
| 2 | 2011-2013 | 2014 | ✅ | 4.06 | 1.62 | 7.68 | 200 | -0.61 | 0.77 | $-373.62 | 79 | -0.28 | $-78.65 |
| 3 | 2012-2014 | 2015 | ✅ | 4.30 | 1.56 | 6.93 | 174 | 0.56 | 1.22 | $261.00 | 50 | 4.40 | $1133.22 |
| 4 | 2013-2015 | 2016 | ✅ | 2.92 | 1.45 | 9.75 | 168 | 0.80 | 1.33 | $271.58 | 44 | 1.56 | $447.38 |
| 5 | 2014-2016 | 2017 | ✅ | 5.07 | 1.68 | 6.40 | 152 | 2.74 | 1.99 | $446.59 | 31 | 2.99 | $510.08 |
| 6 | 2015-2017 | 2018 | ✅ | 5.25 | 1.83 | 5.98 | 152 | -0.20 | 0.91 | $-84.65 | 50 | -0.35 | $-89.67 |
| 7 | 2016-2018 | 2019 | ✅ | 3.54 | 1.50 | 5.47 | 150 | -0.39 | 0.81 | $-218.94 | 57 | -0.68 | $-380.78 |
| 8 | 2017-2019 | 2020 | ❌ | 2.58 | 1.29 | 14.41 | 351 | 0.91 | 1.29 | $601.14 | 118 | 0.49 | $146.71 |
| 9 | 2018-2020 | 2021 | ✅ | 3.86 | 1.33 | 10.53 | 364 | -0.75 | 0.78 | $-599.50 | 118 | 2.23 | $541.41 |
| 10 | 2019-2021 | 2022 | ✅ | 3.16 | 1.38 | 5.10 | 156 | 0.01 | 1.00 | $2.96 | 60 | -0.59 | $-316.50 |
| 11 | 2020-2022 | 2023 | ✅ | 2.95 | 1.64 | 9.61 | 166 | -0.91 | 0.54 | $-760.15 | 74 | -0.86 | $-514.76 |
| 12 | 2021-2023 | 2024 | ❌ | 1.79 | 1.32 | 6.48 | 124 | -0.83 | 0.60 | $-283.85 | 41 | -0.38 | $-153.53 |
| 13 | 2022-2024 | 2025 | ❌ | 1.12 | 1.30 | 9.39 | 139 | 0.85 | 1.34 | $186.34 | 46 | -0.20 | $-68.66 |
| 14 | 2023-2025 | 2026 | ❌ | 2.26 | 1.36 | 5.10 | 132 | 0.51 | 1.40 | $145.61 | 26 | -0.19 | $-37.45 |

## 2. OOS tong hop ghep 14 nam test (2013-2026)

### A) Bo tham so TOI UU theo tung luot (Walk-Forward thuc su)
- Tong lenh: 933 | Win rate: 35.6%
- Net: $-1191.04  (-23.8% tren von $5000)
- Profit Factor: 0.94
- Max Drawdown: $1953.84 (36.4%)
- Recovery Factor: -0.61

### B) DEFAULT-EA (fast5/0.5, slow10/3.0, TP=gong(0), trail=1) — khong toi uu
- Tong lenh: 535 | Win rate: 37.8%
- Net: $842.27  (16.8% tren von $5000)
- Profit Factor: 1.08
- Max Drawdown: $1434.33 (20.2%)
- Recovery Factor: 0.59

## 3. Bo tham so toi uu theo tung luot

| Luot | fast_period | fast_mult | slow_period | slow_mult | tp_rr |
|---|---|---|---|---|---|
| 1 | 15 | 1.524 | 26 | 1.669 | 0.0 |
| 2 | 4 | 1.557 | 17 | 2.665 | 0.0 |
| 3 | 6 | 1.003 | 23 | 2.616 | 0.0 |
| 4 | 14 | 1.893 | 14 | 2.711 | 0.0 |
| 5 | 6 | 1.688 | 13 | 2.712 | 0.0 |
| 6 | 4 | 1.65 | 16 | 2.95 | 0.0 |
| 7 | 3 | 1.557 | 11 | 2.948 | 0.0 |
| 8 | 6 | 1.023 | 7 | 1.507 | 0.0 |
| 9 | 3 | 0.593 | 20 | 1.501 | 0.0 |
| 10 | 3 | 1.998 | 27 | 4.086 | 0.0 |
| 11 | 6 | 1.968 | 17 | 2.724 | 0.0 |
| 12 | 7 | 1.483 | 7 | 3.769 | 0.0 |
| 13 | 3 | 1.836 | 7 | 5.756 | 0.0 |
| 14 | 8 | 1.616 | 8 | 5.556 | 0.0 |

## 4. Chan doan Overfitting

- IS hop le: **10/14** luot | OOS co lai: **7/14** nam.
- Profit Factor: IS trung binh = 1.50 → OOS ghep = 0.94 (suy giam NHE — binh thuong, khong phai overfit nang).
- **Recovery Factor OOS ghep = -0.61** (default-EA 0.59) — toi uu ≈ default ⟹ ket qua **it phu thuoc tham so** (edge nam o ban than chien luoc, khong phai o viec tinh chinh).
- *Luu y so sanh:* IS RF do tren 3 nam, OOS RF tung nam do tren 1 nam nen khong so truc tiep theo gia tri tuyet doi; dung **PF** va **RF ghep** de danh gia cong bang.

## 5. Do on dinh tham so giua cac luot

| Tham so | Min | Max | Nhan xet |
|---|---|---|---|
| fast_period | 3 | 15 | rat phan tan |
| fast_mult | 0.593 | 1.998 | rat phan tan |
| slow_period | 7 | 27 | rat phan tan |
| slow_mult | 1.501 | 5.756 | rat phan tan |

## 6. Ket luan

- OOS: toi uu net $-1191 vs default-EA net $842 → toi uu hoa KHÔNG cai thien so voi default.
- **Edge bien thien manh theo thoi gian:** giai doan 2013-2019 net ≈ $-484 (rat tot), nhung 2020-2026 net ≈ $-707 (toi uu) / $-403 (default), chi 4/7 nam co lai → chien luoc **suy yeu ro o che do thi truong gan day** (dac biet chuoi thua 2021-2024).
- Max Drawdown that tren toan ky = **36%** — cao hon nhieu so voi ky vong tu rieng 2013-2019 (~10%); day la rui ro that khi chay live qua nhieu che do.
- ⚠️ **Net duong tren toan ky nhung KHONG ben vung**: PF≈1.1, RF≈1.0, drawdown lon, nhieu nam thua → chua du tin cay de chay live neu khong them bo loc che do thi truong.
- Luu y: ket qua tinh tren spread lich su that, drawdown mark-to-market, khong nhin truoc.