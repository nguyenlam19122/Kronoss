# WFA Optimization — EA Ichimoku + ATR (entry: Trail1×Trail2 cross)

**Muc tieu:** max Recovery Factor (NetProfit/MaxDD).  
**Loc TRAIN:** PF≥1.3, MaxDD≤15.0%, Trades≥150.  
**Von:** $5000, 1R=$50 (1%).  
**Cau hinh:** TP toi uu trong GA, trailing = khong/gong.  **GA toi uu 5 tham so:** fast_period, fast_mult, slow_period, slow_mult, tp_rr (Ichimoku 9/26/52 co dinh de chong overfitting).

## 1. Ket qua tung luot (IS toi uu vs OOS toi uu vs OOS default-EA)

| Luot | Train | Test | IS ok? | IS RF | IS PF | IS DD% | IS lenh | OOS RF | OOS PF | OOS net | OOS lenh | DEF RF | DEF net |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 2010-2012 | 2013 | ✅ | 8.50 | 1.68 | 5.16 | 216 | 0.30 | 1.07 | $164.68 | 103 | 0.07 | $33.80 |
| 2 | 2011-2013 | 2014 | ✅ | 5.50 | 1.39 | 6.65 | 256 | 0.83 | 1.17 | $306.40 | 82 | 0.32 | $153.98 |
| 3 | 2012-2014 | 2015 | ✅ | 4.90 | 1.47 | 8.27 | 271 | 3.14 | 1.79 | $1579.73 | 84 | 1.91 | $739.17 |
| 4 | 2013-2015 | 2016 | ✅ | 6.87 | 1.57 | 8.87 | 257 | 0.26 | 1.10 | $139.09 | 68 | 0.30 | $125.72 |
| 5 | 2014-2016 | 2017 | ✅ | 7.93 | 1.52 | 5.21 | 218 | 0.84 | 1.22 | $277.30 | 62 | 1.02 | $378.25 |
| 6 | 2015-2017 | 2018 | ✅ | 6.98 | 1.70 | 5.57 | 202 | 1.14 | 1.31 | $394.63 | 66 | 1.10 | $446.33 |
| 7 | 2016-2018 | 2019 | ✅ | 12.78 | 1.73 | 2.94 | 206 | -0.17 | 0.94 | $-101.77 | 76 | 0.22 | $104.69 |
| 8 | 2017-2019 | 2020 | ✅ | 8.71 | 1.53 | 3.43 | 188 | 0.61 | 1.15 | $186.76 | 68 | 1.08 | $389.64 |
| 9 | 2018-2020 | 2021 | ✅ | 12.55 | 1.93 | 3.48 | 184 | -0.79 | 0.71 | $-609.95 | 86 | -0.19 | $-114.61 |
| 10 | 2019-2021 | 2022 | ✅ | 8.77 | 1.76 | 4.92 | 186 | -0.65 | 0.77 | $-386.56 | 73 | -0.34 | $-203.21 |
| 11 | 2020-2022 | 2023 | ✅ | 1.98 | 1.35 | 8.02 | 151 | -0.65 | 0.64 | $-412.67 | 59 | -0.35 | $-248.17 |
| 12 | 2021-2023 | 2024 | ❌ | 0.21 | 1.03 | 8.73 | 182 | -0.18 | 0.95 | $-68.53 | 64 | -0.57 | $-548.17 |
| 13 | 2022-2024 | 2025 | ❌ | 1.29 | 1.16 | 9.01 | 184 | 1.97 | 1.54 | $578.59 | 60 | 5.75 | $1125.09 |
| 14 | 2023-2025 | 2026 | ✅ | 5.86 | 1.55 | 5.48 | 178 | -0.15 | 0.89 | $-74.24 | 31 | -0.26 | $-133.71 |

## 2. OOS tong hop ghep 14 nam test (2013-2026)

### A) Bo tham so TOI UU theo tung luot (Walk-Forward thuc su)
- Tong lenh: 982 | Win rate: 38.5%
- Net: $1973.46  (39.5% tren von $5000)
- Profit Factor: 1.09
- Max Drawdown: $1951.24 (23.9%)
- Recovery Factor: 1.01

### B) DEFAULT-EA (fast5/0.5, slow10/3.0, TP=3.0R, trail=0) — khong toi uu
- Tong lenh: 994 | Win rate: 37.2%
- Net: $2248.80  (45.0% tren von $5000)
- Profit Factor: 1.10
- Max Drawdown: $1933.29 (24.8%)
- Recovery Factor: 1.16

## 3. Bo tham so toi uu theo tung luot

| Luot | fast_period | fast_mult | slow_period | slow_mult | tp_rr |
|---|---|---|---|---|---|
| 1 | 7 | 1.209 | 14 | 2.726 | 5.4 |
| 2 | 9 | 1.661 | 19 | 2.792 | 5.588 |
| 3 | 4 | 0.916 | 23 | 2.611 | 6.0 |
| 4 | 11 | 1.563 | 22 | 2.757 | 5.681 |
| 5 | 8 | 1.99 | 19 | 3.067 | 1.864 |
| 6 | 9 | 1.949 | 13 | 3.036 | 6.0 |
| 7 | 3 | 0.747 | 8 | 2.885 | 1.013 |
| 8 | 7 | 1.866 | 25 | 3.473 | 1.0 |
| 9 | 3 | 1.794 | 25 | 3.913 | 1.195 |
| 10 | 3 | 1.878 | 13 | 4.08 | 2.15 |
| 11 | 14 | 1.285 | 25 | 6.0 | 5.351 |
| 12 | 3 | 1.0 | 28 | 5.311 | 1.248 |
| 13 | 10 | 1.594 | 30 | 4.747 | 1.816 |
| 14 | 4 | 1.459 | 25 | 4.766 | 2.057 |

## 4. Chan doan Overfitting

- IS hop le: **12/14** luot | OOS co lai: **8/14** nam.
- Profit Factor: IS trung binh = 1.53 → OOS ghep = 1.09 (suy giam NHE — binh thuong, khong phai overfit nang).
- **Recovery Factor OOS ghep = 1.01** (default-EA 1.16) — toi uu ≈ default ⟹ ket qua **it phu thuoc tham so** (edge nam o ban than chien luoc, khong phai o viec tinh chinh).
- *Luu y so sanh:* IS RF do tren 3 nam, OOS RF tung nam do tren 1 nam nen khong so truc tiep theo gia tri tuyet doi; dung **PF** va **RF ghep** de danh gia cong bang.

## 5. Do on dinh tham so giua cac luot

| Tham so | Min | Max | Nhan xet |
|---|---|---|---|
| fast_period | 3 | 14 | rat phan tan |
| fast_mult | 0.747 | 1.99 | phan tan |
| slow_period | 8 | 30 | rat phan tan |
| slow_mult | 2.611 | 6.0 | phan tan |
| tp_rr | 1.0 | 6.0 | rat phan tan |

## 6. Ket luan

- OOS: toi uu net $1973 vs default-EA net $2249 → toi uu hoa KHÔNG cai thien so voi default.
- **Edge bien thien manh theo thoi gian:** giai doan 2013-2019 net ≈ $2760 (rat tot), nhung 2020-2026 net ≈ $-787 (toi uu) / $267 (default), chi 2/7 nam co lai → chien luoc **suy yeu ro o che do thi truong gan day** (dac biet chuoi thua 2021-2024).
- Max Drawdown that tren toan ky = **24%** — cao hon nhieu so voi ky vong tu rieng 2013-2019 (~10%); day la rui ro that khi chay live qua nhieu che do.
- ⚠️ **Net duong tren toan ky nhung KHONG ben vung**: PF≈1.1, RF≈1.0, drawdown lon, nhieu nam thua → chua du tin cay de chay live neu khong them bo loc che do thi truong.
- Luu y: ket qua tinh tren spread lich su that, drawdown mark-to-market, khong nhin truoc.