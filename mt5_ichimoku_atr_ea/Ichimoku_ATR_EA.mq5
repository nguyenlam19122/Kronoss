//+------------------------------------------------------------------+
//|                                            Ichimoku_ATR_EA.mq5    |
//|   Chien luoc: Ichimoku Kumo (loc xu huong) + ATR Trailing Stop   |
//|               (ceyhun) lam tin hieu vao lenh.                    |
//|   Quan ly von: rui ro co dinh 1R (mac dinh 50$) moi lenh.        |
//|                                                                  |
//|   - Entry LONG : ATR Buy (Trail1 cat len Trail2) + gia tren may  |
//|   - Entry SHORT: ATR Sell(Trail1 cat xuong Trail2)+ gia duoi may |
//|   - Stop Loss  : tai Slow Trail (Trail2) luc vao lenh            |
//|   - Take Profit: bao nhieu R (mac dinh 2R)                       |
//|   - Tin hieu chi tinh tren NEN DA DONG (khong repaint)           |
//+------------------------------------------------------------------+
#property copyright "Generated for Kronoss user"
#property link      ""
#property version   "1.00"
#property strict

#include <Trade/Trade.mqh>
CTrade trade;

//================== INPUTS: ICHIMOKU =================================
input group "=== Ichimoku ==="
input int    InpTenkan          = 9;     // Conversion Line (Tenkan)
input int    InpKijun           = 26;    // Base Line (Kijun)
input int    InpSenkouB         = 52;    // Leading Span B length
input int    InpDisplacement    = 26;    // Displacement (do dich may)
input bool   InpUseCloudFilter  = true;  // Bat buoc gia ra ngoai may Kumo
input bool   InpRequireCloudColor = false;// Bat buoc mau may trung huong (SpanA vs SpanB)

//================== INPUTS: ATR TRAILING STOP =======================
input group "=== ATR Trailing Stop (ceyhun) ==="
input int    InpFastATRPeriod   = 5;     // Fast ATR period (AP1)
input double InpFastATRMult     = 0.5;   // Fast ATR multiplier (AF1)
input int    InpSlowATRPeriod   = 10;    // Slow ATR period (AP2)
input double InpSlowATRMult     = 3.0;   // Slow ATR multiplier (AF2)

//================== INPUTS: RISK / SL / TP ==========================
input group "=== Quan ly rui ro ==="
input double InpRiskMoney       = 50.0;  // 1R = rui ro moi lenh (tien tai khoan)
input int    InpSLMode          = 0;     // SL: 0=SlowTrail(Trail2) 1=ATR 2=Kijun
input double InpSLATRMult       = 1.5;   // He so ATR cho SL khi SLMode=1
input double InpMinSLpips       = 5.0;   // Khoang cach SL toi thieu (pips) - an toan
input double InpTakeProfitRR    = 2.0;   // TP tinh theo R (0 = khong dat TP co dinh)
input double InpMaxLots         = 5.0;   // Tran khoi luong (an toan)

//================== INPUTS: TRADE MANAGEMENT ========================
input group "=== Quan ly lenh ==="
input bool   InpUseTrailing     = false; // Doi SL theo Slow Trail (Trail2)
input bool   InpExitOnOpposite  = true;  // Dong lenh khi co tin hieu nguoc
input long   InpMagic           = 990011;// Magic number
input int    InpMaxSpreadPts    = 30;    // Spread toi da (points) cho phep vao lenh
input int    InpSlippagePts     = 20;    // Do truot gia cho phep (points)
input int    InpWarmupBars      = 1500;  // So nen mom (seed) gia tri Trail

//================== TRANG THAI TOAN CUC =============================
int      hATR1 = INVALID_HANDLE;   // handle Fast ATR
int      hATR2 = INVALID_HANDLE;   // handle Slow ATR

double   gTrail1     = 0.0;        // Fast Trail tai nen da dong gan nhat (shift 1)
double   gTrail2     = 0.0;        // Slow Trail tai shift 1
double   gTrail1Prev = 0.0;        // Fast Trail tai shift 2 (de bat cat nhau)
double   gTrail2Prev = 0.0;        // Slow Trail tai shift 2
bool     gSeeded     = false;      // da seed lich su chua
datetime gLastBarTime = 0;         // thoi gian nen hien tai (shift 0)

double   gPoint, gPip;
int      gDigits;

//+------------------------------------------------------------------+
//| Tinh 1 buoc cua ATR Trailing Stop (giong Pine cua ceyhun)        |
//|   c     : close nen hien tai                                     |
//|   cPrev : close nen truoc                                        |
//|   prev  : gia tri Trail nen truoc                                |
//|   sl    : mult * ATR cua nen hien tai                            |
//+------------------------------------------------------------------+
double ComputeTrail(const double c, const double cPrev, const double prev, const double sl)
{
   if(c > prev && cPrev > prev) return MathMax(prev, c - sl); // dang tang -> keo SL len
   if(c < prev && cPrev < prev) return MathMin(prev, c + sl); // dang giam -> keo SL xuong
   if(c > prev)                 return c - sl;                // vua flip len
   return c + sl;                                             // vua flip xuong
}

//+------------------------------------------------------------------+
//| Donchian giua (Ichimoku): (HH + LL)/2 cua `period` nen tu `shift`|
//+------------------------------------------------------------------+
double DonchianMid(const int period, const int shift)
{
   int hi = iHighest(_Symbol, _Period, MODE_HIGH, period, shift);
   int lo = iLowest (_Symbol, _Period, MODE_LOW,  period, shift);
   if(hi < 0 || lo < 0) return 0.0;
   return (iHigh(_Symbol, _Period, hi) + iLow(_Symbol, _Period, lo)) / 2.0;
}

//+------------------------------------------------------------------+
//| Lay 1 gia tri ATR tai shift cho truoc                            |
//+------------------------------------------------------------------+
double GetATR(const int handle, const int shift)
{
   double buf[];
   if(CopyBuffer(handle, 0, shift, 1, buf) < 1) return 0.0;
   return buf[0];
}

//+------------------------------------------------------------------+
//| Seed gia tri Trail1/Trail2 bang cach chay de quy tren lich su    |
//+------------------------------------------------------------------+
bool SeedTrails()
{
   int total = Bars(_Symbol, _Period);
   if(total < 100) return false;

   int warm = MathMin(total - 2, InpWarmupBars); // so nen tu shift 1 tro ve qua khu
   if(warm < 50) return false;

   double cl[], atr1[], atr2[];
   ArraySetAsSeries(cl, true);
   ArraySetAsSeries(atr1, true);
   ArraySetAsSeries(atr2, true);

   // shift 1 .. warm  (index 0 = shift1 = nen da dong gan nhat)
   if(CopyClose(_Symbol, _Period, 1, warm, cl)   < warm) return false;
   if(CopyBuffer(hATR1, 0, 1, warm, atr1)        < warm) return false;
   if(CopyBuffer(hATR2, 0, 1, warm, atr2)        < warm) return false;

   double prevT1 = 0.0, prevT2 = 0.0;   // nz(...,0) giong Pine
   // duyet tu nen cu nhat (index warm-1) den moi nhat (index 0)
   for(int i = warm - 1; i >= 0; i--)
   {
      double c     = cl[i];
      double cPrev = (i + 1 <= warm - 1) ? cl[i + 1] : cl[i];
      double sl1   = InpFastATRMult * atr1[i];
      double sl2   = InpSlowATRMult * atr2[i];

      // Truoc khi tinh nen shift1 (i==0), prevT1/prevT2 dang la gia tri tai shift2
      if(i == 0) { gTrail1Prev = prevT1; gTrail2Prev = prevT2; }

      prevT1 = ComputeTrail(c, cPrev, prevT1, sl1);
      prevT2 = ComputeTrail(c, cPrev, prevT2, sl2);
   }
   gTrail1 = prevT1;  // gia tri tai shift1
   gTrail2 = prevT2;
   gSeeded = true;
   return true;
}

//+------------------------------------------------------------------+
//| Cap nhat 1 buoc khi co nen moi dong                              |
//+------------------------------------------------------------------+
void UpdateTrailsIncremental()
{
   double c     = iClose(_Symbol, _Period, 1);
   double cPrev = iClose(_Symbol, _Period, 2);
   double sl1   = InpFastATRMult * GetATR(hATR1, 1);
   double sl2   = InpSlowATRMult * GetATR(hATR2, 1);

   double oldT1 = gTrail1, oldT2 = gTrail2;
   gTrail1Prev = oldT1;   // gia tri cu tro thanh "shift2"
   gTrail2Prev = oldT2;
   gTrail1 = ComputeTrail(c, cPrev, oldT1, sl1);
   gTrail2 = ComputeTrail(c, cPrev, oldT2, sl2);
}

//+------------------------------------------------------------------+
//| Co dang giu lenh cua EA nay khong?                               |
//+------------------------------------------------------------------+
bool HasPosition(long &type, double &openPrice, double &sl, double &tp, double &vol, ulong &ticket)
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong t = PositionGetTicket(i);
      if(t == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if(PositionGetInteger(POSITION_MAGIC) != InpMagic) continue;
      type      = PositionGetInteger(POSITION_TYPE);
      openPrice = PositionGetDouble(POSITION_PRICE_OPEN);
      sl        = PositionGetDouble(POSITION_SL);
      tp        = PositionGetDouble(POSITION_TP);
      vol       = PositionGetDouble(POSITION_VOLUME);
      ticket    = t;
      return true;
   }
   return false;
}

//+------------------------------------------------------------------+
//| Tinh khoi luong theo rui ro co dinh 1R                           |
//+------------------------------------------------------------------+
double CalcLots(const double slDistance)
{
   if(slDistance <= 0) return 0.0;
   double tickValue = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double tickSize  = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   if(tickValue <= 0 || tickSize <= 0) return 0.0;

   double lossPerLot = (slDistance / tickSize) * tickValue;  // tien thua/1 lot
   if(lossPerLot <= 0) return 0.0;

   double lots = InpRiskMoney / lossPerLot;

   double step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   double minL = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double maxL = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);

   lots = MathFloor(lots / step) * step;          // lam tron xuong -> rui ro <= muc tieu
   if(lots < minL)
   {
      // Lot toi thieu da vuot rui ro mong muon -> canh bao
      PrintFormat("[CanhBao] Lot tinh duoc (%.4f) < lot min (%.2f). Rui ro thuc te se > %.2f.",
                  lots, minL, InpRiskMoney);
      lots = minL;
   }
   lots = MathMin(lots, maxL);
   lots = MathMin(lots, InpMaxLots);
   return lots;
}

//+------------------------------------------------------------------+
//| Mo lenh                                                          |
//+------------------------------------------------------------------+
void OpenTrade(const bool isLong, const double kijun, const double atrSlow)
{
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double entry = isLong ? ask : bid;

   // --- xac dinh SL theo che do ---
   double slPrice;
   if(InpSLMode == 1)        slPrice = isLong ? entry - InpSLATRMult * atrSlow : entry + InpSLATRMult * atrSlow;
   else if(InpSLMode == 2)   slPrice = kijun;
   else                      slPrice = gTrail2;   // mac dinh: Slow Trail

   // --- ep SL ve dung phia + dam bao khoang cach toi thieu ---
   double minDist = InpMinSLpips * gPip;
   if(isLong)
   {
      if(slPrice >= entry - minDist) slPrice = entry - minDist;
   }
   else
   {
      if(slPrice <= entry + minDist) slPrice = entry + minDist;
   }

   double slDistance = MathAbs(entry - slPrice);
   double tpPrice = 0.0;
   if(InpTakeProfitRR > 0.0)
      tpPrice = isLong ? entry + InpTakeProfitRR * slDistance
                       : entry - InpTakeProfitRR * slDistance;

   double lots = CalcLots(slDistance);
   if(lots <= 0)
   {
      Print("[Bo qua] Khoi luong = 0, khong mo lenh.");
      return;
   }

   slPrice = NormalizeDouble(slPrice, gDigits);
   tpPrice = NormalizeDouble(tpPrice, gDigits);

   bool ok;
   if(isLong) ok = trade.Buy(lots, _Symbol, 0.0, slPrice, tpPrice, "Ichi+ATR Long");
   else       ok = trade.Sell(lots, _Symbol, 0.0, slPrice, tpPrice, "Ichi+ATR Short");

   if(ok)
      PrintFormat("[%s] lots=%.2f entry~%.5f SL=%.5f TP=%.5f (R=%.2f$, SLdist=%.5f)",
                  isLong ? "BUY" : "SELL", lots, entry, slPrice, tpPrice, InpRiskMoney, slDistance);
   else
      PrintFormat("[Loi mo lenh] retcode=%d %s", trade.ResultRetcode(), trade.ResultRetcodeDescription());
}

//+------------------------------------------------------------------+
//| Trailing SL theo Slow Trail                                      |
//+------------------------------------------------------------------+
void ManageTrailing(const long posType, const double curSL, const ulong ticket)
{
   double newSL = NormalizeDouble(gTrail2, gDigits);
   if(posType == POSITION_TYPE_BUY)
   {
      double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
      if(newSL > curSL && newSL < bid)
         trade.PositionModify(ticket, newSL, PositionGetDouble(POSITION_TP));
   }
   else
   {
      double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      if((curSL == 0.0 || newSL < curSL) && newSL > ask)
         trade.PositionModify(ticket, newSL, PositionGetDouble(POSITION_TP));
   }
}

//+------------------------------------------------------------------+
//| OnInit                                                           |
//+------------------------------------------------------------------+
int OnInit()
{
   gDigits = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
   gPoint  = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   gPip    = (gDigits == 3 || gDigits == 5) ? 10 * gPoint : gPoint;

   hATR1 = iATR(_Symbol, _Period, InpFastATRPeriod);
   hATR2 = iATR(_Symbol, _Period, InpSlowATRPeriod);
   if(hATR1 == INVALID_HANDLE || hATR2 == INVALID_HANDLE)
   {
      Print("Khong tao duoc handle ATR.");
      return INIT_FAILED;
   }

   trade.SetExpertMagicNumber(InpMagic);
   trade.SetDeviationInPoints(InpSlippagePts);
   trade.SetTypeFillingBySymbol(_Symbol);

   gSeeded = false;
   gLastBarTime = 0;
   Print("Ichimoku_ATR_EA khoi tao OK. 1R = ", InpRiskMoney, " ", AccountInfoString(ACCOUNT_CURRENCY));
   return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
//| OnDeinit                                                         |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   if(hATR1 != INVALID_HANDLE) IndicatorRelease(hATR1);
   if(hATR2 != INVALID_HANDLE) IndicatorRelease(hATR2);
}

//+------------------------------------------------------------------+
//| OnTick - chi xu ly khi co NEN MOI                                |
//+------------------------------------------------------------------+
void OnTick()
{
   datetime barTime = iTime(_Symbol, _Period, 0);
   if(barTime == gLastBarTime) return;     // chua co nen moi
   // co nen moi: nen vua dong la shift 1

   // dam bao du du lieu ATR
   if(BarsCalculated(hATR1) < InpFastATRPeriod + 2 ||
      BarsCalculated(hATR2) < InpSlowATRPeriod + 2)
      return;

   if(!gSeeded)
   {
      if(!SeedTrails()) return;            // chua du lich su -> doi
   }
   else
   {
      UpdateTrailsIncremental();
   }
   gLastBarTime = barTime;

   //--- Tin hieu ATR (cat nhau tai shift1) ---
   bool buySig  = (gTrail1Prev <= gTrail2Prev) && (gTrail1 >  gTrail2);
   bool sellSig = (gTrail1Prev >= gTrail2Prev) && (gTrail1 <  gTrail2);

   //--- Ichimoku tai nen da dong (shift1) + may dich chuyen ---
   double kijun = DonchianMid(InpKijun, 1);
   // May "duoi" nen shift1 = span tinh tai shift = displacement
   int cs = InpDisplacement;
   double spanA = (DonchianMid(InpTenkan, cs) + DonchianMid(InpKijun, cs)) / 2.0;
   double spanB = DonchianMid(InpSenkouB, cs);
   double cloudTop = MathMax(spanA, spanB);
   double cloudBot = MathMin(spanA, spanB);
   double c1 = iClose(_Symbol, _Period, 1);

   bool cloudOK = (spanA != 0.0 && spanB != 0.0);
   bool aboveCloud = c1 > cloudTop;
   bool belowCloud = c1 < cloudBot;
   bool bullCloud  = spanA > spanB;
   bool bearCloud  = spanA < spanB;

   bool longOK = buySig
              && (!InpUseCloudFilter   || (cloudOK && aboveCloud))
              && (!InpRequireCloudColor|| bullCloud);
   bool shortOK = sellSig
              && (!InpUseCloudFilter   || (cloudOK && belowCloud))
              && (!InpRequireCloudColor|| bearCloud);

   //--- Quan ly lenh dang co ---
   long   posType; double posOpen, posSL, posTP, posVol; ulong ticket;
   bool   inPos = HasPosition(posType, posOpen, posSL, posTP, posVol, ticket);

   if(inPos)
   {
      // dong khi co tin hieu nguoc
      if(InpExitOnOpposite)
      {
         if(posType == POSITION_TYPE_BUY && sellSig)  { trade.PositionClose(ticket); inPos = false; }
         else if(posType == POSITION_TYPE_SELL && buySig){ trade.PositionClose(ticket); inPos = false; }
      }
      // trailing theo Slow Trail
      if(inPos && InpUseTrailing)
         ManageTrailing(posType, posSL, ticket);
   }

   //--- Vao lenh moi ---
   if(!inPos && (longOK || shortOK))
   {
      // loc spread
      long spread = SymbolInfoInteger(_Symbol, SYMBOL_SPREAD);
      if(spread > InpMaxSpreadPts)
      {
         PrintFormat("[Bo qua] Spread %d > %d points.", (int)spread, InpMaxSpreadPts);
         return;
      }
      double atrSlow = GetATR(hATR2, 1);
      if(longOK)  OpenTrade(true,  kijun, atrSlow);
      else        OpenTrade(false, kijun, atrSlow);
   }
}
//+------------------------------------------------------------------+
