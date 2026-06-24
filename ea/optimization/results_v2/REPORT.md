# WFA Optimization — EA Ichimoku + ATR (entry: Trail1×Trail2 cross)

**Muc tieu:** max Recovery Factor (NetProfit/MaxDD).  
**Loc TRAIN:** PF≥1.3, MaxDD≤15.0%, Trades≥150.  
**Von:** $5000, 1R=$50 (1%).  
**Toi uu 5 tham so loi:** fast_period, fast_mult, slow_period, slow_mult, tp_rr (Ichimoku 9/26/52 + cac flag = default EA, co dinh de chong overfitting).

## 1. Ket qua tung luot (IS toi uu vs OOS toi uu vs OOS default-EA)

| Luot | Train | Test | IS ok? | IS RF | IS PF | IS DD% | IS lenh | OOS RF | OOS PF | OOS net | OOS lenh | DEF RF | DEF net |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 2010-2012 | 2013 | ✅ | 7.88 | 1.64 | 5.13 | 218 | 0.07 | 1.01 | $37.51 | 102 | 0.07 | $33.80 |
| 2 | 2011-2013 | 2014 | ✅ | 5.50 | 1.39 | 6.65 | 256 | 0.83 | 1.17 | $306.40 | 82 | 0.32 | $153.98 |
| 3 | 2012-2014 | 2015 | ✅ | 4.90 | 1.47 | 8.27 | 271 | 3.14 | 1.79 | $1579.73 | 84 | 1.91 | $739.17 |
| 4 | 2013-2015 | 2016 | ✅ | 6.87 | 1.57 | 8.87 | 257 | 0.26 | 1.10 | $139.09 | 68 | 0.30 | $125.72 |
| 5 | 2014-2016 | 2017 | ✅ | 7.93 | 1.52 | 5.21 | 218 | 0.84 | 1.22 | $277.30 | 62 | 1.02 | $378.25 |
| 6 | 2015-2017 | 2018 | ✅ | 6.98 | 1.70 | 5.57 | 202 | 1.14 | 1.31 | $394.63 | 66 | 1.10 | $446.33 |
| 7 | 2016-2018 | 2019 | ✅ | 12.78 | 1.73 | 2.94 | 206 | -0.17 | 0.94 | $-101.77 | 76 | 0.22 | $104.69 |

## 2. OOS tong hop ghep 7 nam test (2013-2019)

### A) Bo tham so TOI UU theo tung luot (Walk-Forward thuc su)
- Tong lenh: 540 | Win rate: 38.5%
- Net: $2632.89  (52.7% tren von $5000)
- Profit Factor: 1.22
- Max Drawdown: $594.32 (9.6%)
- Recovery Factor: 4.43

### B) Bo tham so DEFAULT cua EA (fast5/0.5, slow10/3, TP=3R) — khong toi uu
- Tong lenh: 514 | Win rate: 38.9%
- Net: $1981.94  (39.6% tren von $5000)
- Profit Factor: 1.18
- Max Drawdown: $482.68 (9.2%)
- Recovery Factor: 4.11

## 3. Bo tham so toi uu theo tung luot

| Luot | fast_period | fast_mult | slow_period | slow_mult | tp_rr |
|---|---|---|---|---|---|
| 1 | 5 | 0.377 | 14 | 2.754 | 5.366 |
| 2 | 9 | 1.661 | 19 | 2.792 | 5.588 |
| 3 | 4 | 0.916 | 23 | 2.611 | 6.0 |
| 4 | 11 | 1.563 | 22 | 2.757 | 5.681 |
| 5 | 8 | 1.99 | 19 | 3.067 | 1.864 |
| 6 | 9 | 1.949 | 13 | 3.036 | 6.0 |
| 7 | 3 | 0.747 | 8 | 2.885 | 1.013 |

## 4. Chan doan Overfitting

- IS hop le: **7/7** luot | OOS co lai: **6/7** nam.
- Profit Factor: IS trung binh = 1.57 → OOS ghep = 1.22 (suy giam NHE — binh thuong, khong phai overfit nang).
- **Recovery Factor OOS ghep = 4.43** (gan voi default-EA 4.11) → chien luoc BEN VUNG, it nhay theo tham so. Khac han v1 (TK cross) bi sup do OOS.
- *Luu y so sanh:* IS RF do tren 3 nam, con OOS RF tung nam do tren 1 nam nen khong so truc tiep theo gia tri tuyet doi; dung **PF** va **RF ghep** de danh gia cong bang.

## 5. Do on dinh tham so giua cac luot

| Tham so | Min | Max | Nhan xet |
|---|---|---|---|
| fast_period | 3 | 11 | rat phan tan |
| fast_mult | 0.377 | 1.99 | rat phan tan |
| slow_period | 8 | 23 | phan tan |
| slow_mult | 2.611 | 3.067 | on dinh |
| tp_rr | 1.013 | 6.0 | rat phan tan |

## 6. Ket luan

- OOS: toi uu net $2633 vs default-EA net $1982 → toi uu hoa CÓ cai thien so voi default.
- ✅ Co edge OOS kha quan.
- Luu y: ket qua tinh tren spread lich su that, drawdown mark-to-market, khong nhin truoc.