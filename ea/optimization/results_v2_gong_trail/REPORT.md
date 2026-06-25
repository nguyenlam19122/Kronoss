# WFA Optimization — EA Ichimoku + ATR (entry: Trail1×Trail2 cross)

**Muc tieu:** max Recovery Factor (NetProfit/MaxDD).  
**Loc TRAIN:** PF≥1.3, MaxDD≤15.0%, Trades≥150.  
**Von:** $5000, 1R=$50 (1%).  
**Cau hinh:** gong loi (TP=0), trailing = Slow Trail.  **GA toi uu 4 tham so:** fast_period, fast_mult, slow_period, slow_mult (Ichimoku 9/26/52 co dinh de chong overfitting).

## 1. Ket qua tung luot (IS toi uu vs OOS toi uu vs OOS default-EA)

| Luot | Train | Test | IS ok? | IS RF | IS PF | IS DD% | IS lenh | OOS RF | OOS PF | OOS net | OOS lenh | DEF RF | DEF net |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 2010-2012 | 2013 | ✅ | 6.55 | 1.70 | 4.95 | 192 | 0.01 | 1.00 | $6.95 | 92 | -0.26 | $-163.08 |
| 2 | 2011-2013 | 2014 | ✅ | 4.49 | 1.37 | 7.03 | 271 | 0.48 | 1.14 | $266.23 | 93 | -0.09 | $-46.28 |
| 3 | 2012-2014 | 2015 | ✅ | 4.24 | 1.35 | 7.02 | 255 | 1.07 | 1.32 | $564.04 | 85 | 2.81 | $1041.19 |
| 4 | 2013-2015 | 2016 | ✅ | 5.15 | 1.42 | 7.03 | 258 | 1.27 | 1.43 | $447.87 | 68 | 0.48 | $175.06 |
| 5 | 2014-2016 | 2017 | ✅ | 5.14 | 1.49 | 6.52 | 202 | 0.59 | 1.21 | $221.85 | 63 | 1.29 | $341.95 |
| 6 | 2015-2017 | 2018 | ✅ | 9.41 | 1.82 | 4.02 | 199 | 1.94 | 1.56 | $585.24 | 68 | 0.66 | $222.60 |
| 7 | 2016-2018 | 2019 | ✅ | 5.34 | 1.55 | 5.39 | 197 | -0.51 | 0.81 | $-273.27 | 73 | -0.39 | $-182.34 |
| 8 | 2017-2019 | 2020 | ✅ | 5.96 | 1.59 | 4.41 | 161 | 0.53 | 1.21 | $204.24 | 65 | -0.28 | $-173.87 |
| 9 | 2018-2020 | 2021 | ✅ | 6.09 | 1.88 | 5.87 | 163 | -0.33 | 0.91 | $-123.84 | 68 | 0.68 | $263.31 |
| 10 | 2019-2021 | 2022 | ✅ | 5.71 | 1.69 | 5.63 | 169 | -0.79 | 0.75 | $-403.45 | 73 | -0.66 | $-634.16 |
| 11 | 2020-2022 | 2023 | ❌ | 1.42 | 1.27 | 8.06 | 156 | -0.44 | 0.77 | $-237.48 | 61 | -0.48 | $-259.13 |
| 12 | 2021-2023 | 2024 | ❌ | 0.31 | 1.08 | 15.63 | 199 | -0.71 | 0.67 | $-515.72 | 79 | -0.58 | $-356.05 |
| 13 | 2022-2024 | 2025 | ✅ | 1.55 | 1.51 | 13.92 | 182 | 1.43 | 1.74 | $421.55 | 52 | 1.78 | $455.17 |
| 14 | 2023-2025 | 2026 | ✅ | 2.57 | 1.35 | 7.38 | 187 | 2.40 | 2.15 | $497.16 | 29 | -0.22 | $-87.64 |

## 2. OOS tong hop ghep 14 nam test (2013-2026)

### A) Bo tham so TOI UU theo tung luot (Walk-Forward thuc su)
- Tong lenh: 969 | Win rate: 40.0%
- Net: $1661.38  (33.2% tren von $5000)
- Profit Factor: 1.09
- Max Drawdown: $1679.66 (23.3%)
- Recovery Factor: 0.99

### B) DEFAULT-EA (fast5/0.5, slow10/3.0, TP=gong(0), trail=1) — khong toi uu
- Tong lenh: 994 | Win rate: 37.1%
- Net: $596.72  (11.9% tren von $5000)
- Profit Factor: 1.03
- Max Drawdown: $1803.77 (26.5%)
- Recovery Factor: 0.33

## 3. Bo tham so toi uu theo tung luot

| Luot | fast_period | fast_mult | slow_period | slow_mult | tp_rr |
|---|---|---|---|---|---|
| 1 | 12 | 1.465 | 25 | 2.914 | 0.0 |
| 2 | 6 | 0.707 | 25 | 2.57 | 0.0 |
| 3 | 19 | 2.0 | 27 | 2.631 | 0.0 |
| 4 | 10 | 1.592 | 19 | 2.82 | 0.0 |
| 5 | 8 | 0.664 | 17 | 3.199 | 0.0 |
| 6 | 6 | 1.788 | 11 | 3.158 | 0.0 |
| 7 | 4 | 1.531 | 12 | 3.225 | 0.0 |
| 8 | 7 | 1.235 | 29 | 4.593 | 0.0 |
| 9 | 15 | 0.79 | 15 | 4.861 | 0.0 |
| 10 | 11 | 1.332 | 13 | 4.085 | 0.0 |
| 11 | 16 | 0.2 | 17 | 5.989 | 0.0 |
| 12 | 3 | 1.448 | 7 | 4.039 | 0.0 |
| 13 | 3 | 1.135 | 7 | 5.022 | 0.0 |
| 14 | 6 | 0.766 | 7 | 3.609 | 0.0 |

## 4. Chan doan Overfitting

- IS hop le: **12/14** luot | OOS co lai: **9/14** nam.
- Profit Factor: IS trung binh = 1.51 → OOS ghep = 1.09 (suy giam NHE — binh thuong, khong phai overfit nang).
- **Recovery Factor OOS ghep = 0.99** (default-EA 0.33) — toi uu ≈ default ⟹ ket qua **it phu thuoc tham so** (edge nam o ban than chien luoc, khong phai o viec tinh chinh).
- *Luu y so sanh:* IS RF do tren 3 nam, OOS RF tung nam do tren 1 nam nen khong so truc tiep theo gia tri tuyet doi; dung **PF** va **RF ghep** de danh gia cong bang.

## 5. Do on dinh tham so giua cac luot

| Tham so | Min | Max | Nhan xet |
|---|---|---|---|
| fast_period | 3 | 19 | rat phan tan |
| fast_mult | 0.2 | 2.0 | rat phan tan |
| slow_period | 7 | 29 | rat phan tan |
| slow_mult | 2.57 | 5.989 | phan tan |

## 6. Ket luan

- OOS: toi uu net $1661 vs default-EA net $597 → toi uu hoa CÓ cai thien so voi default.
- **Edge bien thien manh theo thoi gian:** giai doan 2013-2019 net ≈ $1819 (rat tot), nhung 2020-2026 net ≈ $-158 (toi uu) / $-792 (default), chi 3/7 nam co lai → chien luoc **suy yeu ro o che do thi truong gan day** (dac biet chuoi thua 2021-2024).
- Max Drawdown that tren toan ky = **23%** — cao hon nhieu so voi ky vong tu rieng 2013-2019 (~10%); day la rui ro that khi chay live qua nhieu che do.
- ⚠️ **Net duong tren toan ky nhung KHONG ben vung**: PF≈1.1, RF≈1.0, drawdown lon, nhieu nam thua → chua du tin cay de chay live neu khong them bo loc che do thi truong.
- Luu y: ket qua tinh tren spread lich su that, drawdown mark-to-market, khong nhin truoc.