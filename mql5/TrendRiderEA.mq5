//+------------------------------------------------------------------+
//|                                                 TrendRiderEA.mq5  |
//|   Trend-following EA cho MetaTrader 5 (khung H1 forex)            |
//|                                                                  |
//|   Logic (khop voi backtest Python forex_trend_bot/):             |
//|     - Loc trend : EMA_fast vs EMA_slow + ADX > nguong            |
//|     - Vao lenh  : breakout kenh Donchian theo chieu trend        |
//|     - GONG LENH : Chandelier ATR trailing stop (chi siet co loi) |
//|     - Sizing    : 1R co dinh theo $ (all-in, da gom spread)      |
//|                   hoac theo % equity                             |
//|                                                                  |
//|   Quyet dinh dung nen da DONG (shift 1), vao lenh tai nen moi.   |
//|   Test truc tiep: MT5 Strategy Tester (Ctrl+R), symbol = H1.     |
//+------------------------------------------------------------------+
#property copyright "forex_trend_bot"
#property version   "1.10"

#include <Trade/Trade.mqh>

enum ENUM_RISK_MODE
{
   RISK_FIXED_USD = 0,   // 1R co dinh theo $ (khop backtest)
   RISK_PERCENT   = 1    // Theo % equity
};

//--- Loc xu huong --------------------------------------------------
input int    EmaFast          = 50;       // EMA nhanh
input int    EmaSlow          = 200;      // EMA cham
input int    AdxPeriod        = 14;       // Chu ky ADX
input double AdxMin           = 20.0;     // ADX toi thieu (loai sideway)
//--- Vao lenh & bien dong ------------------------------------------
input int    DonchianPeriod   = 20;       // Breakout N nen
input int    AtrPeriod        = 14;       // Chu ky ATR
input double AtrStopMult      = 2.0;      // Stop ban dau = ATR * he so
//--- Gong lenh (trailing) ------------------------------------------
input int    ChandelierPeriod = 22;       // Lookback dinh/day
input double ChandelierMult   = 3.0;      // Trailing = ATR * he so (lon = gong dai hon)
input bool   ExitOnTrendFlip  = false;    // false = de trailing tu lo
//--- Quan tri von --------------------------------------------------
input ENUM_RISK_MODE RiskMode = RISK_FIXED_USD; // Che do rui ro
input double FixedRisk        = 50.0;     // 1R = $ (khi RiskMode = Fixed)
input double RiskPercent      = 1.0;      // % equity (khi RiskMode = Percent)
//--- Lenh ----------------------------------------------------------
input bool   AllowLong        = true;
input bool   AllowShort       = true;
input bool   TradeOnNewBarOnly= true;     // Chi xu ly 1 lan moi nen
input long   MagicNumber      = 770120;
input int    Slippage         = 10;       // Points
input bool   ShowInfoPanel    = true;     // Hien bang thong tin tren chart

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
   Comment("");
}

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

//--- Tim vi the cua EA nay (theo symbol + magic); de lai o trang thai selected
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

//--- So tien rui ro cho 1 lenh (1R)
double RiskMoney()
{
   if(RiskMode == RISK_FIXED_USD) return(FixedRisk);
   return(AccountInfoDouble(ACCOUNT_EQUITY) * RiskPercent / 100.0);
}

//--- Khoi luong sao cho lo toi da (gom spread) = risk_money
double CalcLots(double risk_money, double stop_dist_allin)
{
   double tick_value = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double tick_size  = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   if(stop_dist_allin <= 0 || tick_size <= 0 || tick_value <= 0) return(0.0);

   double loss_per_lot = stop_dist_allin / tick_size * tick_value;
   if(loss_per_lot <= 0) return(0.0);

   double lots = risk_money / loss_per_lot;
   double vmin  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double vmax  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double vstep = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   if(vstep > 0) lots = MathFloor(lots / vstep) * vstep;
   lots = MathMax(vmin, MathMin(vmax, lots));
   return(lots);
}

double MinStopDist()
{
   long stops_level = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL);
   return((double)stops_level * _Point);
}

//+------------------------------------------------------------------+
//| Gong lenh: cap nhat Chandelier trailing stop                     |
//+------------------------------------------------------------------+
void ManageTrailing(double atr1)
{
   if(!SelectOurPosition()) return;

   long   type   = PositionGetInteger(POSITION_TYPE);
   double cur_sl = PositionGetDouble(POSITION_SL);
   double cur_tp = PositionGetDouble(POSITION_TP);
   double bid    = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double ask    = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double min_d  = MinStopDist();

   if(type == POSITION_TYPE_BUY)
   {
      int hh = iHighest(_Symbol, PERIOD_CURRENT, MODE_HIGH, ChandelierPeriod, 1);
      if(hh < 0) return;
      double new_sl = iHigh(_Symbol, PERIOD_CURRENT, hh) - atr1 * ChandelierMult;
      new_sl = MathMin(new_sl, bid - min_d);
      if(new_sl > cur_sl + _Point*0.5)                          // chi siet len
         trade.PositionModify(_Symbol, NormalizeDouble(new_sl, _Digits), cur_tp);

      if(ExitOnTrendFlip)
      {
         double ef, es;
         if(GetVal(hEmaFast,0,1,ef) && GetVal(hEmaSlow,0,1,es) && ef < es)
            trade.PositionClose(_Symbol);
      }
   }
   else if(type == POSITION_TYPE_SELL)
   {
      int ll = iLowest(_Symbol, PERIOD_CURRENT, MODE_LOW, ChandelierPeriod, 1);
      if(ll < 0) return;
      double new_sl = iLow(_Symbol, PERIOD_CURRENT, ll) + atr1 * ChandelierMult;
      new_sl = MathMax(new_sl, ask + min_d);
      if(cur_sl < _Point*0.5 || new_sl < cur_sl - _Point*0.5)   // chi siet xuong
         trade.PositionModify(_Symbol, NormalizeDouble(new_sl, _Digits), cur_tp);

      if(ExitOnTrendFlip)
      {
         double ef, es;
         if(GetVal(hEmaFast,0,1,ef) && GetVal(hEmaSlow,0,1,es) && ef > es)
            trade.PositionClose(_Symbol);
      }
   }
}

//+------------------------------------------------------------------+
//| Thu vao lenh moi neu dang flat                                   |
//+------------------------------------------------------------------+
void TryEnter(double emaF1, double emaS1, double adx1, double atr1)
{
   if(SelectOurPosition()) return;

   bool trend_up = (emaF1 > emaS1) && (adx1 >= AdxMin);
   bool trend_dn = (emaF1 < emaS1) && (adx1 >= AdxMin);
   double close1 = iClose(_Symbol, PERIOD_CURRENT, 1);

   int hh = iHighest(_Symbol, PERIOD_CURRENT, MODE_HIGH, DonchianPeriod, 2);
   int ll = iLowest(_Symbol, PERIOD_CURRENT, MODE_LOW,  DonchianPeriod, 2);
   if(hh < 0 || ll < 0) return;
   double dc_upper = iHigh(_Symbol, PERIOD_CURRENT, hh);
   double dc_lower = iLow(_Symbol, PERIOD_CURRENT, ll);

   bool long_sig  = AllowLong  && trend_up && (close1 > dc_upper);
   bool short_sig = AllowShort && trend_dn && (close1 < dc_lower);
   if(!long_sig && !short_sig) return;

   double stop_dist    = atr1 * AtrStopMult;
   double spread_price = SymbolInfoDouble(_Symbol, SYMBOL_ASK) - SymbolInfoDouble(_Symbol, SYMBOL_BID);
   // Sizing tinh CA spread vao rui ro -> lo toi da tai SL (da gom spread) = 1R
   double lots = CalcLots(RiskMoney(), stop_dist + spread_price);
   if(lots <= 0) return;

   double ask   = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double bid   = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double min_d = MinStopDist();

   if(long_sig)
   {
      double sl = MathMin(ask - stop_dist, bid - min_d);         // ton trong stops level
      trade.Buy(lots, _Symbol, 0.0, NormalizeDouble(sl, _Digits), 0.0, "TrendRider long");
   }
   else
   {
      double sl = MathMax(bid + stop_dist, ask + min_d);
      trade.Sell(lots, _Symbol, 0.0, NormalizeDouble(sl, _Digits), 0.0, "TrendRider short");
   }
}

//+------------------------------------------------------------------+
//| Bang thong tin tren chart (de test truc tiep)                    |
//+------------------------------------------------------------------+
void UpdateInfo(double adx1, double emaF1, double emaS1)
{
   if(!ShowInfoPanel) return;

   string trend = (emaF1 > emaS1 && adx1 >= AdxMin) ? "UP"
                : (emaF1 < emaS1 && adx1 >= AdxMin ? "DOWN" : "-- (sideway)");
   string pos = "Flat";
   double profit = 0.0, sl = 0.0;
   if(SelectOurPosition())
   {
      pos    = (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY) ? "LONG" : "SHORT";
      profit = PositionGetDouble(POSITION_PROFIT);
      sl     = PositionGetDouble(POSITION_SL);
   }
   string rmode = (RiskMode == RISK_FIXED_USD)
                  ? StringFormat("1R = $%.0f (all-in)", FixedRisk)
                  : StringFormat("%.1f%% equity", RiskPercent);
   double r = (RiskMode == RISK_FIXED_USD && FixedRisk > 0) ? profit / FixedRisk : 0.0;

   Comment(StringFormat(
      "=== TrendRider EA (H1) ===\nXu huong: %s | ADX: %.1f\nVi the: %s | SL: %.5f\nLoi nhuan mo: $%.2f (%.2fR)\nRui ro: %s",
      trend, adx1, pos, sl, profit, r, rmode));
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

   ManageTrailing(atr1);                          // gong lenh truoc
   TryEnter(emaF1, emaS1, adx1, atr1);
   UpdateInfo(adx1, emaF1, emaS1);
}
//+------------------------------------------------------------------+
