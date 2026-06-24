//+------------------------------------------------------------------+
//|                                        IchimokuATR_TrendEA.mq5    |
//|   EA trend-following (v1)                                         |
//|   - Lọc xu hướng : Ichimoku (giá vs mây Kumo + màu mây + Kijun)   |
//|   - Điểm vào (v1): TK cross (Tenkan cắt Kijun) cùng hướng trend   |
//|   - SL ban đầu   : ATR(SLatrPeriod) x SLmult   => định nghĩa 1R   |
//|   - Trailing     : ATR(TrailPeriod) x TrailMult (ratchet)        |
//|   - Risk         : cố định InpRiskUSD mỗi lệnh (đã gồm spread)    |
//|                                                                  |
//|   GHI CHÚ QUAN TRỌNG:                                             |
//|   Toàn bộ đường Ichimoku được tính TRỰC TIẾP từ giá (Donchian)   |
//|   giống hệt Pine Script gốc, và mây được canh đúng độ dịch 26     |
//|   nến (đám mây nằm DƯỚI nến hiện tại = tính từ 26 nến trước).     |
//|   Cách này tránh hoàn toàn lỗi lệch buffer của iIchimoku.         |
//+------------------------------------------------------------------+
#property copyright "Kronoss"
#property version   "1.00"
#property strict

#include <Trade/Trade.mqh>
CTrade trade;

//==================== INPUTS ====================
input group "── Ichimoku (lọc xu hướng) ──"
input int    InpTenkan            = 9;     // Tenkan / Conversion Line
input int    InpKijun             = 26;    // Kijun / Base Line
input int    InpSpanB             = 52;    // Senkou Span B
input int    InpDisplacement      = 26;    // Độ dịch mây tới trước
input bool   InpRequireCloudColor = true;  // Bắt buộc mây cùng màu với hướng vào lệnh

input group "── ATR: SL ban đầu & Trailing ──"
input int    InpSLatrPeriod = 14;    // ATR period cho SL ban đầu
input double InpSLmult      = 2.0;   // Hệ số ATR cho SL ban đầu (= 1R)
input int    InpTrailPeriod = 10;    // ATR period cho trailing (giống Trail2 ceyhun)
input double InpTrailMult   = 3.0;   // Hệ số ATR cho trailing (giống Trail2 ceyhun)
input bool   InpUseIchiExit = true;  // Thoát sớm khi Ichimoku đảo chiều

input group "── Risk & Execution ──"
input double InpRiskUSD      = 20.0;   // Rủi ro mỗi lệnh (USD) = 1R, đã gồm spread
input int    InpMaxSpreadPts = 0;      // Spread tối đa cho phép (points); 0 = bỏ qua
input long   InpMagic        = 990019; // Magic number
input int    InpSlippagePts  = 30;     // Deviation tối đa (points)

//==================== GLOBALS ====================
datetime g_lastBarTime    = 0;
int      g_atrSLhandle    = INVALID_HANDLE;
int      g_atrTrailHandle = INVALID_HANDLE;

//==================== INIT / DEINIT ====================
int OnInit()
{
   g_atrSLhandle    = iATR(_Symbol, _Period, InpSLatrPeriod);
   g_atrTrailHandle = iATR(_Symbol, _Period, InpTrailPeriod);
   if(g_atrSLhandle == INVALID_HANDLE || g_atrTrailHandle == INVALID_HANDLE)
   {
      Print("Lỗi: không tạo được ATR handle");
      return(INIT_FAILED);
   }
   trade.SetExpertMagicNumber(InpMagic);
   trade.SetDeviationInPoints(InpSlippagePts);
   trade.SetTypeFillingBySymbol(_Symbol);
   PrintFormat("IchimokuATR_TrendEA v1 khởi động trên %s %s | Risk=%.2f USD/lệnh",
               _Symbol, EnumToString((ENUM_TIMEFRAMES)_Period), InpRiskUSD);
   return(INIT_SUCCEEDED);
}

void OnDeinit(const int reason)
{
   if(g_atrSLhandle    != INVALID_HANDLE) IndicatorRelease(g_atrSLhandle);
   if(g_atrTrailHandle != INVALID_HANDLE) IndicatorRelease(g_atrTrailHandle);
}

//==================== MAIN ====================
void OnTick()
{
   if(!IsNewBar()) return;       // chỉ xử lý 1 lần mỗi nến đã đóng
   ManageOpenPosition();         // trailing + thoát theo Ichimoku
   CheckForEntry();              // vào lệnh mới (nếu chưa có lệnh)
}

//==================== HELPERS ====================
bool IsNewBar()
{
   datetime t = iTime(_Symbol, _Period, 0);
   if(t != g_lastBarTime)
   {
      g_lastBarTime = t;
      return(true);
   }
   return(false);
}

// Donchian midpoint = (highest(len) + lowest(len)) / 2, tính tại 'shift'
// Đây là công thức gốc của Ichimoku trong Pine: donchian(len)
double Donchian(int len, int shift)
{
   int hh = iHighest(_Symbol, _Period, MODE_HIGH, len, shift);
   int ll = iLowest(_Symbol, _Period, MODE_LOW, len, shift);
   if(hh < 0 || ll < 0) return(0.0);
   return((iHigh(_Symbol, _Period, hh) + iLow(_Symbol, _Period, ll)) / 2.0);
}

double ATRval(int handle)
{
   double buf[];
   if(CopyBuffer(handle, 0, 1, 1, buf) < 1) return(0.0); // shift 1 = nến đã đóng
   return(buf[0]);
}

double MinStopDist()
{
   long lvl = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL);
   return((double)lvl * _Point);
}

bool PositionExistsForEA()
{
   if(!PositionSelect(_Symbol)) return(false);
   return(PositionGetInteger(POSITION_MAGIC) == InpMagic);
}

//==================== ICHIMOKU STATE ====================
struct IchiState
{
   double tenkan, kijun;          // tại nến đã đóng (shift 1)
   double tenkanPrev, kijunPrev;  // tại nến trước nữa (shift 2) -> để bắt cross
   double spanA, spanB;           // mây nằm DƯỚI nến đã đóng (đã canh độ dịch)
   double close1;                 // close nến đã đóng
};

// Lấy trạng thái Ichimoku tại nến đã đóng (shift = 1)
bool GetIchi(IchiState &s)
{
   int need = InpSpanB + InpDisplacement + 5;
   if(Bars(_Symbol, _Period) < need) return(false);

   s.tenkan     = Donchian(InpTenkan, 1);
   s.kijun      = Donchian(InpKijun,  1);
   s.tenkanPrev = Donchian(InpTenkan, 2);
   s.kijunPrev  = Donchian(InpKijun,  2);

   // Mây dưới nến hiện tại = giá trị Senkou tính từ InpDisplacement nến trước.
   // SpanA = avg(Tenkan, Kijun); SpanB = Donchian(SpanB) -> đều dịch tới 26 nến.
   int back = 1 + InpDisplacement;
   s.spanA = (Donchian(InpTenkan, back) + Donchian(InpKijun, back)) / 2.0;
   s.spanB = Donchian(InpSpanB, back);

   s.close1 = iClose(_Symbol, _Period, 1);

   if(s.tenkan == 0 || s.kijun == 0 || s.spanA == 0 || s.spanB == 0) return(false);
   return(true);
}

//==================== ENTRY ====================
void CheckForEntry()
{
   if(PositionExistsForEA()) return;  // v1: chỉ 1 lệnh / symbol, không nhồi lệnh

   if(InpMaxSpreadPts > 0)
   {
      long sp = SymbolInfoInteger(_Symbol, SYMBOL_SPREAD);
      if(sp > InpMaxSpreadPts) return; // spread quá rộng -> bỏ qua
   }

   IchiState s;
   if(!GetIchi(s)) return;

   double cloudTop = MathMax(s.spanA, s.spanB);
   double cloudBot = MathMin(s.spanA, s.spanB);

   bool crossUp   = (s.tenkanPrev <= s.kijunPrev && s.tenkan > s.kijun);
   bool crossDown = (s.tenkanPrev >= s.kijunPrev && s.tenkan < s.kijun);

   bool cloudBull = (!InpRequireCloudColor) || (s.spanA > s.spanB);
   bool cloudBear = (!InpRequireCloudColor) || (s.spanA < s.spanB);

   // Lớp 1 (lọc) + Lớp 2 (trigger)
   bool longOK  = (s.close1 > cloudTop) && cloudBull && (s.close1 > s.kijun) && crossUp;
   bool shortOK = (s.close1 < cloudBot) && cloudBear && (s.close1 < s.kijun) && crossDown;

   if(longOK)       OpenTrade(true);
   else if(shortOK) OpenTrade(false);
}

void OpenTrade(bool isLong)
{
   double atrSLdist = ATRval(g_atrSLhandle) * InpSLmult;  // khoảng SL theo giá
   if(atrSLdist <= 0) return;

   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double spread = ask - bid;

   double minStop = MinStopDist();
   if(atrSLdist < minStop) atrSLdist = minStop; // tôn trọng stops level tối thiểu

   // Sizing: cộng spread vào khoảng SL để loss thực tế <= InpRiskUSD (đã gồm spread)
   double sizingDist = atrSLdist + spread;
   double lot = CalcLot(sizingDist);
   if(lot <= 0)
   {
      Print("Lot tính ra = 0, bỏ qua lệnh");
      return;
   }

   double price, sl;
   if(isLong) { price = ask; sl = NormalizeDouble(ask - atrSLdist, _Digits); }
   else       { price = bid; sl = NormalizeDouble(bid + atrSLdist, _Digits); }

   bool ok = isLong
             ? trade.Buy(lot,  _Symbol, price, sl, 0.0, "IchiATR v1 LONG")
             : trade.Sell(lot, _Symbol, price, sl, 0.0, "IchiATR v1 SHORT");

   if(!ok)
      PrintFormat("Mở lệnh thất bại: retcode=%d (%s)",
                  trade.ResultRetcode(), trade.ResultRetcodeDescription());
   else
      PrintFormat("Mở %s | lot=%.2f | entry=%.5f | SL=%.5f | risk≈%.2f USD",
                  (isLong ? "LONG" : "SHORT"), lot, price, sl, InpRiskUSD);
}

// Khối lượng để rủi ro = InpRiskUSD khi SL bị quét
double CalcLot(double slDistancePrice)
{
   double tickValue = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double tickSize  = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   if(tickValue <= 0 || tickSize <= 0 || slDistancePrice <= 0) return(0.0);

   double moneyPerLot = slDistancePrice / tickSize * tickValue; // lỗ/1.0 lot nếu chạm SL
   if(moneyPerLot <= 0) return(0.0);

   double lot = InpRiskUSD / moneyPerLot;

   // Chuẩn hóa theo broker
   double step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   double minv = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double maxv = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   if(step <= 0) step = 0.01;
   lot = MathFloor(lot / step) * step;
   lot = MathMax(minv, MathMin(maxv, lot));
   return(lot);
}

//==================== MANAGE / TRAILING ====================
void ManageOpenPosition()
{
   if(!PositionSelect(_Symbol)) return;
   if(PositionGetInteger(POSITION_MAGIC) != InpMagic) return;

   long   type   = PositionGetInteger(POSITION_TYPE);
   double curSL  = PositionGetDouble(POSITION_SL);
   double close1 = iClose(_Symbol, _Period, 1);

   // 1) Thoát sớm khi Ichimoku đảo chiều (tùy chọn)
   if(InpUseIchiExit)
   {
      IchiState s;
      if(GetIchi(s))
      {
         double cloudBot = MathMin(s.spanA, s.spanB);
         double cloudTop = MathMax(s.spanA, s.spanB);
         if(type == POSITION_TYPE_BUY  && (s.close1 < s.kijun || s.close1 < cloudBot))
         { trade.PositionClose(_Symbol); return; }
         if(type == POSITION_TYPE_SELL && (s.close1 > s.kijun || s.close1 > cloudTop))
         { trade.PositionClose(_Symbol); return; }
      }
   }

   // 2) Trailing stop ATR kiểu ratchet (chỉ dời theo hướng có lợi)
   double atrTrail = ATRval(g_atrTrailHandle) * InpTrailMult;
   if(atrTrail <= 0) return;

   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double minStop = MinStopDist();

   if(type == POSITION_TYPE_BUY)
   {
      double newSL = NormalizeDouble(close1 - atrTrail, _Digits);
      if((curSL == 0 || newSL > curSL) && (bid - newSL) >= minStop)
         trade.PositionModify(_Symbol, newSL, 0.0);
   }
   else if(type == POSITION_TYPE_SELL)
   {
      double newSL = NormalizeDouble(close1 + atrTrail, _Digits);
      if((curSL == 0 || newSL < curSL) && (newSL - ask) >= minStop)
         trade.PositionModify(_Symbol, newSL, 0.0);
   }
}
//+------------------------------------------------------------------+
