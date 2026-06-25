# WFA Optimization — EA Ichimoku + ATR (entry: Trail1×Trail2 cross)

**Muc tieu:** max Recovery Factor (NetProfit/MaxDD).  
**Loc TRAIN:** PF≥1.3, MaxDD≤15.0%, Trades≥150.  
**Von:** $5000, 1R=$50 (1%).  
**Cau hinh:** gong loi (TP=0), trailing = khong/gong.  **GA toi uu 4 tham so:** fast_period, fast_mult, slow_period, slow_mult (Ichimoku 9/26/52 co dinh de chong overfitting).

## 1. Ket qua tung luot (IS toi uu vs OOS toi uu vs OOS default-EA)

| Luot | Train | Test | IS ok? | IS RF | IS PF | IS DD% | IS lenh | OOS RF | OOS PF | OOS net | OOS lenh | DEF RF | DEF net |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 2010-2012 | 2013 | ✅ | 6.13 | 1.56 | 5.87 | 215 | -0.20 | 0.94 | $-136.80 | 102 | 0.41 | $193.68 |
| 2 | 2011-2013 | 2014 | ✅ | 4.88 | 1.43 | 8.02 | 265 | -0.10 | 0.97 | $-58.70 | 88 | -0.32 | $-177.47 |
| 3 | 2012-2014 | 2015 | ✅ | 4.08 | 1.37 | 8.12 | 254 | 2.71 | 1.85 | $1703.69 | 84 | 2.54 | $1051.16 |
| 4 | 2013-2015 | 2016 | ✅ | 5.36 | 1.47 | 8.75 | 247 | 0.11 | 1.04 | $51.14 | 66 | -0.17 | $-73.35 |
| 5 | 2014-2016 | 2017 | ✅ | 4.86 | 1.48 | 7.98 | 216 | 1.32 | 1.37 | $477.49 | 61 | 2.22 | $864.10 |
| 6 | 2015-2017 | 2018 | ✅ | 7.23 | 1.63 | 5.05 | 203 | 0.49 | 1.24 | $277.43 | 63 | 0.56 | $261.04 |
| 7 | 2016-2018 | 2019 | ✅ | 4.80 | 1.78 | 10.31 | 189 | -0.25 | 0.92 | $-124.01 | 69 | -0.43 | $-239.53 |
| 8 | 2017-2019 | 2020 | ✅ | 8.26 | 2.63 | 6.66 | 170 | 0.75 | 1.24 | $279.44 | 62 | 0.80 | $294.48 |
| 9 | 2018-2020 | 2021 | ✅ | 5.22 | 1.89 | 5.69 | 164 | -0.68 | 0.75 | $-367.64 | 65 | -0.14 | $-99.70 |
| 10 | 2019-2021 | 2022 | ✅ | 5.16 | 1.63 | 5.31 | 190 | -0.91 | 0.64 | $-622.49 | 74 | -0.37 | $-236.89 |
| 11 | 2020-2022 | 2023 | ✅ | 2.35 | 1.44 | 9.24 | 171 | -0.64 | 0.53 | $-545.28 | 63 | -0.15 | $-99.22 |
| 12 | 2021-2023 | 2024 | ❌ | 0.11 | 1.02 | 14.16 | 192 | -0.92 | 0.59 | $-783.57 | 77 | -0.70 | $-716.37 |
| 13 | 2022-2024 | 2025 | ❌ | -0.03 | 1.00 | 10.89 | 185 | 0.15 | 1.05 | $48.61 | 60 | 2.81 | $808.51 |
| 14 | 2023-2025 | 2026 | ❌ | 1.27 | 1.28 | 11.33 | 174 | -0.09 | 0.93 | $-40.22 | 31 | -0.43 | $-226.69 |

## 2. OOS tong hop ghep 14 nam test (2013-2026)

### A) Bo tham so TOI UU theo tung luot (Walk-Forward thuc su)
- Tong lenh: 965 | Win rate: 36.1%
- Net: $159.09  (3.2% tren von $5000)
- Profit Factor: 1.01
- Max Drawdown: $2756.70 (35.5%)
- Recovery Factor: 0.06

### B) DEFAULT-EA (fast5/0.5, slow10/3.0, TP=gong(0), trail=0) — khong toi uu
- Tong lenh: 994 | Win rate: 37.1%
- Net: $1603.74  (32.1% tren von $5000)
- Profit Factor: 1.07
- Max Drawdown: $1947.18 (25.4%)
- Recovery Factor: 0.82

## 3. Bo tham so toi uu theo tung luot

| Luot | fast_period | fast_mult | slow_period | slow_mult | tp_rr |
|---|---|---|---|---|---|
| 1 | 3 | 0.593 | 14 | 2.723 | 0.0 |
| 2 | 4 | 0.951 | 28 | 2.629 | 0.0 |
| 3 | 14 | 1.344 | 27 | 2.627 | 0.0 |
| 4 | 11 | 1.724 | 27 | 2.932 | 0.0 |
| 5 | 10 | 1.407 | 22 | 2.995 | 0.0 |
| 6 | 4 | 1.318 | 9 | 3.129 | 0.0 |
| 7 | 4 | 1.122 | 16 | 3.19 | 0.0 |
| 8 | 3 | 1.057 | 10 | 3.62 | 0.0 |
| 9 | 10 | 1.544 | 30 | 5.396 | 0.0 |
| 10 | 3 | 1.885 | 14 | 4.123 | 0.0 |
| 11 | 3 | 1.621 | 9 | 5.567 | 0.0 |
| 12 | 7 | 0.782 | 7 | 4.033 | 0.0 |
| 13 | 4 | 1.395 | 28 | 4.754 | 0.0 |
| 14 | 5 | 1.256 | 19 | 4.933 | 0.0 |

## 4. Chan doan Overfitting

- IS hop le: **11/14** luot | OOS co lai: **6/14** nam.
- Profit Factor: IS trung binh = 1.54 → OOS ghep = 1.01 (suy giam NHE — binh thuong, khong phai overfit nang).
- **Recovery Factor OOS ghep = 0.06** (default-EA 0.82) — toi uu ≈ default ⟹ ket qua **it phu thuoc tham so** (edge nam o ban than chien luoc, khong phai o viec tinh chinh).
- *Luu y so sanh:* IS RF do tren 3 nam, OOS RF tung nam do tren 1 nam nen khong so truc tiep theo gia tri tuyet doi; dung **PF** va **RF ghep** de danh gia cong bang.

## 5. Do on dinh tham so giua cac luot

| Tham so | Min | Max | Nhan xet |
|---|---|---|---|
| fast_period | 3 | 14 | rat phan tan |
| fast_mult | 0.593 | 1.885 | phan tan |
| slow_period | 7 | 30 | rat phan tan |
| slow_mult | 2.627 | 5.567 | phan tan |

## 6. Ket luan

- OOS: toi uu net $159 vs default-EA net $1604 → toi uu hoa KHÔNG cai thien so voi default.
- **Edge bien thien manh theo thoi gian:** giai doan 2013-2019 net ≈ $2190 (rat tot), nhung 2020-2026 net ≈ $-2031 (toi uu) / $-276 (default), chi 2/7 nam co lai → chien luoc **suy yeu ro o che do thi truong gan day** (dac biet chuoi thua 2021-2024).
- Max Drawdown that tren toan ky = **35%** — cao hon nhieu so voi ky vong tu rieng 2013-2019 (~10%); day la rui ro that khi chay live qua nhieu che do.
- ⚠️ **Net duong tren toan ky nhung KHONG ben vung**: PF≈1.1, RF≈1.0, drawdown lon, nhieu nam thua → chua du tin cay de chay live neu khong them bo loc che do thi truong.
- Luu y: ket qua tinh tren spread lich su that, drawdown mark-to-market, khong nhin truoc.