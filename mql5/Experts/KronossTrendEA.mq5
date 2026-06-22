//+------------------------------------------------------------------+
//|                                               KronossTrendEA.mq5  |
//|   EA theo xu huong (trend-following)                              |
//|   Muc tieu thiet ke: KHONG can winrate cao, nhung Profit Factor  |
//|   (PF) >= 1.2 nho ty le Risk:Reward thuan loi.                    |
//|                                                                   |
//|   Triet ly (theo khung bai hoc quant):                           |
//|   - Loc che do thi truong (regime) bang EMA + ADX:               |
//|       chi giao dich khi thi truong CO xu huong (tranh sideway).  |
//|   - Vao lenh theo breakout Donchian thuan huong xu huong.        |
//|   - Cat lo nhanh bang ATR stop (sai thi thoat som -> nhieu lenh  |
//|       lo nho, winrate thap la binh thuong).                      |
//|   - De loi nhuan chay bang Chandelier trailing (ATR) ->          |
//|       it lenh thang nhung thang lon -> keo PF len.               |
//|   - Quan ly von theo % rui ro co dinh tren moi lenh.             |
//+------------------------------------------------------------------+
#property copyright "Kronoss"
#property version   "1.00"
#property description "Trend-following EA - low winrate, target Profit Factor >= 1.2"

#include <Trade/Trade.mqh>

//==================================================================
//  INPUTS
//==================================================================
input group "=== Loc xu huong (Regime filter) ==="
input int     EmaFastPeriod   = 50;     // EMA nhanh (loc huong)
input int     EmaSlowPeriod   = 200;    // EMA cham (loc huong)
input int     AdxPeriod       = 14;     // Chu ky ADX
input double  AdxThreshold     = 22.0;  // ADX toi thieu -> xac nhan co xu huong

input group "=== Tin hieu vao lenh (Entry) ==="
input int     EntryChannel    = 20;     // So nen kenh Donchian de breakout vao lenh
input bool    AllowLong       = true;   // Cho phep lenh Mua
input bool    AllowShort      = true;   // Cho phep lenh Ban

input group "=== Quan ly lenh (Risk & Exit) ==="
input int     AtrPeriod       = 14;     // Chu ky ATR
input double  AtrMultSL        = 2.0;   // He so ATR cho stop loss ban dau
input double  AtrMultTrail     = 3.0;   // He so ATR cho Chandelier trailing
input int     TrailChannel    = 22;     // So nen tinh dinh/day cho Chandelier
input double  TakeProfitR      = 0.0;   // TP theo boi so R (0 = tat, de loi chay)

input group "=== Quan ly von (Money management) ==="
input double  RiskPercent      = 1.0;   // % rui ro tren so du moi lenh
input double  FixedLots        = 0.0;   // Lot co dinh (>0 se bo qua RiskPercent)

input group "=== Bo loc giao dich ==="
input long    MagicNumber      = 20260622; // Magic number
input int     Slippage         = 30;       // Do truot toi da (points)
input double  MaxSpreadPoints   = 0;       // Spread toi da (points, 0 = bo qua)
input bool    TradeOnNewBarOnly = true;    // Chi xu ly khi co nen moi
input bool    ShowPanel         = true;    // Hien thi bang thong tin

//==================================================================
//  GLOBAL
//==================================================================
CTrade   trade;
int      emaFastHandle = INVALID_HANDLE;
int      emaSlowHandle = INVALID_HANDLE;
int      adxHandle     = INVALID_HANDLE;
int      atrHandle     = INVALID_HANDLE;
datetime lastBarTime   = 0;

//+------------------------------------------------------------------+
//| Init                                                             |
//+------------------------------------------------------------------+
int OnInit()
{
   emaFastHandle = iMA(_Symbol, _Period, EmaFastPeriod, 0, MODE_EMA, PRICE_CLOSE);
   emaSlowHandle = iMA(_Symbol, _Period, EmaSlowPeriod, 0, MODE_EMA, PRICE_CLOSE);
   adxHandle     = iADX(_Symbol, _Period, AdxPeriod);
   atrHandle     = iATR(_Symbol, _Period, AtrPeriod);

   if(emaFastHandle == INVALID_HANDLE || emaSlowHandle == INVALID_HANDLE ||
      adxHandle == INVALID_HANDLE     || atrHandle == INVALID_HANDLE)
   {
      Print("Loi khoi tao indicator handle.");
      return(INIT_FAILED);
   }

   if(EmaFastPeriod >= EmaSlowPeriod)
      Print("Canh bao: EmaFastPeriod nen nho hon EmaSlowPeriod.");

   trade.SetExpertMagicNumber((ulong)MagicNumber);
   trade.SetDeviationInPoints(Slippage);
   trade.SetTypeFillingBySymbol(_Symbol);

   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| Deinit                                                           |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   if(emaFastHandle != INVALID_HANDLE) IndicatorRelease(emaFastHandle);
   if(emaSlowHandle != INVALID_HANDLE) IndicatorRelease(emaSlowHandle);
   if(adxHandle     != INVALID_HANDLE) IndicatorRelease(adxHandle);
   if(atrHandle     != INVALID_HANDLE) IndicatorRelease(atrHandle);
   Comment("");
}

//+------------------------------------------------------------------+
//| Tick                                                             |
//+------------------------------------------------------------------+
void OnTick()
{
   // Quan ly trailing chay theo tung tick de bao ve loi nhuan kip thoi
   ManageTrailing();

   if(TradeOnNewBarOnly && !IsNewBar())
   {
      if(ShowPanel) UpdatePanel();
      return;
   }

   CheckEntry();

   if(ShowPanel) UpdatePanel();
}

//+------------------------------------------------------------------+
//| Phat hien nen moi                                                |
//+------------------------------------------------------------------+
bool IsNewBar()
{
   datetime t = iTime(_Symbol, _Period, 0);
   if(t != lastBarTime)
   {
      lastBarTime = t;
      return(true);
   }
   return(false);
}

//+------------------------------------------------------------------+
//| Doc 1 gia tri buffer cua indicator                               |
//+------------------------------------------------------------------+
double GetBuffer(int handle, int buffer, int shift)
{
   double arr[];
   if(CopyBuffer(handle, buffer, shift, 1, arr) <= 0)
      return(0.0);
   return(arr[0]);
}

//+------------------------------------------------------------------+
//| Dem so vi the cua EA tren symbol nay                             |
//+------------------------------------------------------------------+
int CountPositions()
{
   int n = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(!PositionSelectByTicket(ticket)) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if(PositionGetInteger(POSITION_MAGIC) != MagicNumber) continue;
      n++;
   }
   return(n);
}

//+------------------------------------------------------------------+
//| Chuan hoa khoi luong lot                                         |
//+------------------------------------------------------------------+
double NormalizeVolume(double vol)
{
   double minV = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double maxV = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   if(step <= 0) step = 0.01;

   vol = MathFloor(vol / step) * step;     // lam tron xuong -> khong vuot rui ro
   if(vol < minV) vol = minV;
   if(vol > maxV) vol = maxV;

   int digits = (int)MathCeil(-MathLog10(step));
   if(digits < 0) digits = 0;
   return(NormalizeDouble(vol, digits));
}

//+------------------------------------------------------------------+
//| Tinh lot theo % rui ro va khoang cach SL (theo gia)              |
//+------------------------------------------------------------------+
double CalcLots(double slPriceDistance)
{
   if(FixedLots > 0)
      return(NormalizeVolume(FixedLots));

   if(slPriceDistance <= 0)
      return(0.0);

   double riskMoney = AccountInfoDouble(ACCOUNT_BALANCE) * RiskPercent / 100.0;
   double tickValue = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double tickSize  = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   if(tickSize <= 0 || tickValue <= 0)
      return(0.0);

   double lossPerLot = (slPriceDistance / tickSize) * tickValue;
   if(lossPerLot <= 0)
      return(0.0);

   double lots = riskMoney / lossPerLot;
   return(NormalizeVolume(lots));
}

//+------------------------------------------------------------------+
//| Kiem tra dieu kien vao lenh                                      |
//+------------------------------------------------------------------+
void CheckEntry()
{
   if(CountPositions() > 0)               // chi giu 1 vi the / symbol
      return;

   // Bo loc spread
   double spread = (SymbolInfoDouble(_Symbol, SYMBOL_ASK) -
                    SymbolInfoDouble(_Symbol, SYMBOL_BID)) / _Point;
   if(MaxSpreadPoints > 0 && spread > MaxSpreadPoints)
      return;

   double emaFast = GetBuffer(emaFastHandle, 0, 1);
   double emaSlow = GetBuffer(emaSlowHandle, 0, 1);
   double adx     = GetBuffer(adxHandle, 0, 1);   // buffer 0 = duong ADX chinh
   double atr     = GetBuffer(atrHandle, 0, 1);
   if(atr <= 0 || emaSlow <= 0)
      return;

   bool trendUp   = (emaFast > emaSlow) && (adx > AdxThreshold);
   bool trendDown = (emaFast < emaSlow) && (adx > AdxThreshold);

   double close1  = iClose(_Symbol, _Period, 1);

   // Kenh Donchian: lay dinh/day cua EntryChannel nen, BO QUA nen vua dong (bat dau tu shift 2)
   int    hiIdx   = iHighest(_Symbol, _Period, MODE_HIGH, EntryChannel, 2);
   int    loIdx   = iLowest(_Symbol, _Period, MODE_LOW,  EntryChannel, 2);
   if(hiIdx < 0 || loIdx < 0)
      return;
   double donHigh = iHigh(_Symbol, _Period, hiIdx);
   double donLow  = iLow(_Symbol, _Period, loIdx);

   // Breakout thuan huong xu huong
   if(AllowLong && trendUp && close1 > donHigh)
      OpenTrade(ORDER_TYPE_BUY, atr);
   else if(AllowShort && trendDown && close1 < donLow)
      OpenTrade(ORDER_TYPE_SELL, atr);
}

//+------------------------------------------------------------------+
//| Mo lenh                                                          |
//+------------------------------------------------------------------+
void OpenTrade(ENUM_ORDER_TYPE dir, double atr)
{
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);

   long   stopsLevel = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL);
   double minDist    = (double)stopsLevel * _Point;
   double spread     = ask - bid;

   double slDist = atr * AtrMultSL;
   if(slDist < minDist + spread)          // dam bao SL khong qua gan
      slDist = minDist + spread;

   double price, sl, tp = 0.0;

   if(dir == ORDER_TYPE_BUY)
   {
      price = ask;
      sl    = price - slDist;
      if(TakeProfitR > 0) tp = price + slDist * TakeProfitR;
   }
   else
   {
      price = bid;
      sl    = price + slDist;
      if(TakeProfitR > 0) tp = price - slDist * TakeProfitR;
   }

   sl = NormalizeDouble(sl, _Digits);
   tp = NormalizeDouble(tp, _Digits);

   double lots = CalcLots(slDist);
   if(lots <= 0)
   {
      Print("Khoi luong = 0, bo qua lenh. Kiem tra RiskPercent/so du.");
      return;
   }

   bool ok;
   if(dir == ORDER_TYPE_BUY)
      ok = trade.Buy(lots, _Symbol, price, sl, tp, "KronossTrend");
   else
      ok = trade.Sell(lots, _Symbol, price, sl, tp, "KronossTrend");

   if(!ok)
      PrintFormat("Mo lenh that bai. Retcode=%d (%s)",
                  trade.ResultRetcode(), trade.ResultRetcodeDescription());
}

//+------------------------------------------------------------------+
//| Chandelier trailing stop (ATR) - de loi nhuan chay              |
//+------------------------------------------------------------------+
void ManageTrailing()
{
   double atr = GetBuffer(atrHandle, 0, 1);
   if(atr <= 0)
      return;

   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);

   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(!PositionSelectByTicket(ticket)) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if(PositionGetInteger(POSITION_MAGIC) != MagicNumber) continue;

      ENUM_POSITION_TYPE ptype = (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);
      double curSL = PositionGetDouble(POSITION_SL);
      double curTP = PositionGetDouble(POSITION_TP);

      if(ptype == POSITION_TYPE_BUY)
      {
         int    hiIdx = iHighest(_Symbol, _Period, MODE_HIGH, TrailChannel, 1);
         if(hiIdx < 0) continue;
         double hh    = iHigh(_Symbol, _Period, hiIdx);
         double newSL = NormalizeDouble(hh - atr * AtrMultTrail, _Digits);

         // chi doi SL len va phai nam duoi gia hien tai
         if(newSL > curSL && newSL < bid)
            trade.PositionModify(ticket, newSL, curTP);
      }
      else if(ptype == POSITION_TYPE_SELL)
      {
         int    loIdx = iLowest(_Symbol, _Period, MODE_LOW, TrailChannel, 1);
         if(loIdx < 0) continue;
         double ll    = iLow(_Symbol, _Period, loIdx);
         double newSL = NormalizeDouble(ll + atr * AtrMultTrail, _Digits);

         // chi doi SL xuong va phai nam tren gia hien tai
         if((curSL == 0.0 || newSL < curSL) && newSL > ask)
            trade.PositionModify(ticket, newSL, curTP);
      }
   }
}

//+------------------------------------------------------------------+
//| Bang thong tin tren chart                                        |
//+------------------------------------------------------------------+
void UpdatePanel()
{
   double emaFast = GetBuffer(emaFastHandle, 0, 1);
   double emaSlow = GetBuffer(emaSlowHandle, 0, 1);
   double adx     = GetBuffer(adxHandle, 0, 1);
   double atr     = GetBuffer(atrHandle, 0, 1);

   string regime;
   if(emaFast > emaSlow && adx > AdxThreshold)      regime = "XU HUONG TANG";
   else if(emaFast < emaSlow && adx > AdxThreshold) regime = "XU HUONG GIAM";
   else                                             regime = "SIDEWAY (khong vao lenh)";

   string txt = StringFormat(
      "KronossTrendEA  |  %s %s\n"
      "Che do thi truong: %s\n"
      "ADX=%.1f (nguong %.1f)   ATR=%.5f\n"
      "Vi the dang mo: %d   Rui ro/lenh: %.2f%%",
      _Symbol, EnumToString((ENUM_TIMEFRAMES)_Period),
      regime, adx, AdxThreshold, atr,
      CountPositions(), RiskPercent);

   Comment(txt);
}
//+------------------------------------------------------------------+
