//+------------------------------------------------------------------+
//|                                                 TrendRiderEA.mq5  |
//|   Trend-following EA cho MetaTrader 5 (khung H1 forex)            |
//|                                                                  |
//|   Logic (khop voi backtest Python forex_trend_bot/):             |
//|     - Loc trend : EMA_fast vs EMA_slow + ADX > nguong            |
//|     - Vao lenh  : breakout kenh Donchian theo chieu trend        |
//|     - GONG LENH : Chandelier ATR trailing stop (chi siet co loi) |
//|     - Sizing    : rui ro co dinh % equity, khoi luong theo ATR   |
//|                                                                  |
//|   Quyet dinh dung nen da DONG (shift 1), vao lenh tai nen moi.   |
//+------------------------------------------------------------------+
#property copyright "forex_trend_bot"
#property version   "1.00"
#property strict

#include <Trade/Trade.mqh>

//--- Inputs: loc xu huong
input int    EmaFast          = 50;       // EMA nhanh
input int    EmaSlow          = 200;      // EMA cham
input int    AdxPeriod        = 14;       // chu ky ADX
input double AdxMin           = 20.0;     // ADX toi thieu (loai sideway)

//--- Inputs: vao lenh & bien dong
input int    DonchianPeriod   = 20;       // breakout N nen
input int    AtrPeriod        = 14;       // chu ky ATR
input double AtrStopMult      = 2.0;      // stop ban dau = ATR * he so (de sizing)

//--- Inputs: gong lenh (trailing)
input int    ChandelierPeriod = 22;       // lookback dinh/day cao nhat
input double ChandelierMult   = 3.0;      // khoang trailing = ATR * he so (lon = gong dai hon)
input bool   ExitOnTrendFlip  = false;    // false = de trailing tu lo (gong dai theo trend)

//--- Inputs: quan tri von & lenh
input double RiskPercent      = 1.0;      // rui ro moi lenh (% equity)
input bool   AllowLong        = true;
input bool   AllowShort       = true;
input bool   TradeOnNewBarOnly= true;     // chi xu ly 1 lan moi nen
input long   MagicNumber      = 770120;
input int    Slippage         = 10;       // points

//--- Globals
CTrade        trade;
int           hEmaFast, hEmaSlow, hAdx, hAtr;
datetime      g_lastBarTime = 0;

//+------------------------------------------------------------------+
int OnInit()
{
   hEmaFast = iMA(_Symbol, PERIOD_CURRENT, EmaFast, 0, MODE_EMA, PRICE_CLOSE);
   hEmaSlow = iMA(_Symbol, PERIOD_CURRENT, EmaSlow, 0, MODE_EMA, PRICE_CLOSE);
   hAdx     = iADX(_Symbol, PERIOD_CURRENT, AdxPeriod);
   hAtr     = iATR(_Symbol, PERIOD_CURRENT, AtrPeriod);

   if(hEmaFast==INVALID_HANDLE || hEmaSlow==INVALID_HANDLE ||
      hAdx==INVALID_HANDLE || hAtr==INVALID_HANDLE)
   {
      Print("Loi tao indicator handle");
      return(INIT_FAILED);
   }

   trade.SetExpertMagicNumber(MagicNumber);
   trade.SetDeviationInPoints(Slippage);
   trade.SetTypeFillingBySymbol(_Symbol);
   return(INIT_SUCCEEDED);
}

void OnDeinit(const int reason)
{
   IndicatorRelease(hEmaFast); IndicatorRelease(hEmaSlow);
   IndicatorRelease(hAdx);     IndicatorRelease(hAtr);
}

//+------------------------------------------------------------------+
//| Doc 1 gia tri buffer tai shift                                   |
//+------------------------------------------------------------------+
bool GetVal(const int handle, const int buffer, const int shift, double &out)
{
   double tmp[];
   if(CopyBuffer(handle, buffer, shift, 1, tmp) != 1) return(false);
   out = tmp[0];
   return(true);
}

bool IsNewBar()
{
   datetime t = iTime(_Symbol, PERIOD_CURRENT, 0);
   if(t == g_lastBarTime) return(false);
   g_lastBarTime = t;
   return(true);
}

//+------------------------------------------------------------------+
//| Tim vi the cua EA nay (theo symbol + magic)                      |
//+------------------------------------------------------------------+
bool SelectOurPosition()
{
   for(int i = PositionsTotal()-1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) == _Symbol &&
         PositionGetInteger(POSITION_MAGIC) == MagicNumber)
         return(true);
   }
   return(false);
}

//+------------------------------------------------------------------+
//| Tinh khoi luong theo rui ro co dinh                              |
//+------------------------------------------------------------------+
double CalcLots(double stop_dist_price)
{
   double tick_value = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double tick_size  = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   if(stop_dist_price <= 0 || tick_size <= 0 || tick_value <= 0) return(0.0);

   double risk_money   = AccountInfoDouble(ACCOUNT_EQUITY) * RiskPercent / 100.0;
   double loss_per_lot = stop_dist_price / tick_size * tick_value;
   if(loss_per_lot <= 0) return(0.0);

   double lots = risk_money / loss_per_lot;

   double vmin  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double vmax  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double vstep = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   if(vstep > 0) lots = MathFloor(lots / vstep) * vstep;
   lots = MathMax(vmin, MathMin(vmax, lots));
   return(lots);
}

//+------------------------------------------------------------------+
//| Khoang cach stop toi thieu cho phep (points -> price)            |
//+------------------------------------------------------------------+
double MinStopDist()
{
   long stops_level = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL);
   return((double)stops_level * _Point);
}

//+------------------------------------------------------------------+
//| Gong lenh: cap nhat trailing stop (Chandelier)                   |
//+------------------------------------------------------------------+
void ManageTrailing(double atr1)
{
   if(!SelectOurPosition()) return;

   long   type    = PositionGetInteger(POSITION_TYPE);
   double cur_sl  = PositionGetDouble(POSITION_SL);
   double cur_tp  = PositionGetDouble(POSITION_TP);
   double bid     = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double ask     = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double min_d   = MinStopDist();

   if(type == POSITION_TYPE_BUY)
   {
      int    hh_idx     = iHighest(_Symbol, PERIOD_CURRENT, MODE_HIGH, ChandelierPeriod, 1);
      double chand_high = iHigh(_Symbol, PERIOD_CURRENT, hh_idx);
      double new_sl     = chand_high - atr1 * ChandelierMult;
      new_sl            = MathMin(new_sl, bid - min_d);            // ton trong stops level
      if(new_sl > cur_sl + _Point*0.5)                            // chi siet len
         trade.PositionModify(_Symbol, NormalizeDouble(new_sl, _Digits), cur_tp);

      if(ExitOnTrendFlip)
      {
         double emaF, emaS;
         if(GetVal(hEmaFast,0,1,emaF) && GetVal(hEmaSlow,0,1,emaS) && emaF < emaS)
            trade.PositionClose(_Symbol);
      }
   }
   else if(type == POSITION_TYPE_SELL)
   {
      int    ll_idx    = iLowest(_Symbol, PERIOD_CURRENT, MODE_LOW, ChandelierPeriod, 1);
      double chand_low = iLow(_Symbol, PERIOD_CURRENT, ll_idx);
      double new_sl    = chand_low + atr1 * ChandelierMult;
      new_sl           = MathMax(new_sl, ask + min_d);
      if(cur_sl < _Point*0.5 || new_sl < cur_sl - _Point*0.5)     // chi siet xuong
         trade.PositionModify(_Symbol, NormalizeDouble(new_sl, _Digits), cur_tp);

      if(ExitOnTrendFlip)
      {
         double emaF, emaS;
         if(GetVal(hEmaFast,0,1,emaF) && GetVal(hEmaSlow,0,1,emaS) && emaF > emaS)
            trade.PositionClose(_Symbol);
      }
   }
}

//+------------------------------------------------------------------+
//| Thu vao lenh moi neu dang flat                                   |
//+------------------------------------------------------------------+
void TryEnter(double emaF1, double emaS1, double adx1, double atr1)
{
   if(SelectOurPosition()) return;                                // chi 1 vi the / symbol

   bool trend_up = (emaF1 > emaS1) && (adx1 >= AdxMin);
   bool trend_dn = (emaF1 < emaS1) && (adx1 >= AdxMin);

   double close1 = iClose(_Symbol, PERIOD_CURRENT, 1);            // nen da dong

   // Donchian cua N nen NGAY TRUOC nen quyet dinh (bat dau shift 2) -> khong lookahead
   int    hh_idx   = iHighest(_Symbol, PERIOD_CURRENT, MODE_HIGH, DonchianPeriod, 2);
   int    ll_idx   = iLowest(_Symbol, PERIOD_CURRENT, MODE_LOW,  DonchianPeriod, 2);
   double dc_upper = iHigh(_Symbol, PERIOD_CURRENT, hh_idx);
   double dc_lower = iLow(_Symbol, PERIOD_CURRENT, ll_idx);

   bool long_sig  = AllowLong  && trend_up && (close1 > dc_upper);
   bool short_sig = AllowShort && trend_dn && (close1 < dc_lower);
   if(!long_sig && !short_sig) return;

   double stop_dist    = atr1 * AtrStopMult;
   double spread_price = SymbolInfoDouble(_Symbol, SYMBOL_ASK) - SymbolInfoDouble(_Symbol, SYMBOL_BID);
   // Sizing tinh CA spread vao rui ro -> lo toi da tai SL (da gom spread) ~ RiskPercent
   double lots         = CalcLots(stop_dist + spread_price);
   if(lots <= 0) return;

   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);

   if(long_sig)
   {
      double sl = NormalizeDouble(ask - stop_dist, _Digits);
      trade.Buy(lots, _Symbol, 0.0, sl, 0.0, "TrendRider long");
   }
   else
   {
      double sl = NormalizeDouble(bid + stop_dist, _Digits);
      trade.Sell(lots, _Symbol, 0.0, sl, 0.0, "TrendRider short");
   }
}

//+------------------------------------------------------------------+
void OnTick()
{
   if(TradeOnNewBarOnly && !IsNewBar()) return;

   double emaF1, emaS1, adx1, atr1;
   if(!GetVal(hEmaFast, 0, 1, emaF1)) return;
   if(!GetVal(hEmaSlow, 0, 1, emaS1)) return;
   if(!GetVal(hAdx,     0, 1, adx1))  return;     // buffer 0 = duong ADX chinh
   if(!GetVal(hAtr,     0, 1, atr1))  return;
   if(atr1 <= 0) return;

   ManageTrailing(atr1);   // gong lenh truoc
   TryEnter(emaF1, emaS1, adx1, atr1);
}
//+------------------------------------------------------------------+
