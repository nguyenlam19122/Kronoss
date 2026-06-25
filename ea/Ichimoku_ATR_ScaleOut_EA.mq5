//+------------------------------------------------------------------+
//|                                  Ichimoku_ATR_ScaleOut_EA.mq5     |
//|   Phien ban CUOI: Entry ATR-cross (ceyhun) + loc may Kumo,        |
//|   EXIT scale-out theo triet ly "lo gioi han, loi co khong gian":  |
//|     1) SL ban dau = SLmult*ATR(SLatrPeriod)   -> gioi han lo (1R) |
//|     2) Dời breakeven khi dat +BEtriggerR       -> chan tra lai lai |
//|     3) Chot PartialFrac khoi luong tai +TP1multR -> khoa mot phan |
//|     4) Phan con lai (runner) gong theo TrailMult*ATR(TrailPeriod) |
//|   Quan ly von: 1R = RiskMoney (mac dinh 20$) DA gom spread+comm.  |
//|   Lot = Risk / ((SL_dist + spread)/tickSize*tickValue + comm)     |
//|   Tin hieu tinh tren NEN DA DONG (khong repaint); quan ly lenh    |
//|   (breakeven/partial) kiem tra moi tick de phan ung kip thoi.     |
//+------------------------------------------------------------------+
#property copyright "Kronoss"
#property version   "2.00"
#property strict

#include <Trade/Trade.mqh>
CTrade trade;

//================== INPUTS: ICHIMOKU (loc may) ======================
input group "=== Ichimoku (loc may Kumo) ==="
input int    InpTenkan        = 9;     // Tenkan
input int    InpKijun         = 26;    // Kijun
input int    InpSenkouB       = 52;    // Senkou Span B
input int    InpDisplacement  = 26;    // Displacement
input bool   InpUseCloudFilter= true;  // Bat buoc gia ra ngoai may

//================== INPUTS: ENTRY ATR-cross (ceyhun) ================
input group "=== Entry: ATR Trailing cross ==="
input int    InpFastATRPeriod = 5;     // Fast ATR period (Trail1)
input double InpFastATRMult   = 0.5;   // Fast ATR multiplier
input int    InpSlowATRPeriod = 10;    // Slow ATR period (Trail2)
input double InpSlowATRMult   = 3.0;   // Slow ATR multiplier

//================== INPUTS: EXIT scale-out (v5) =====================
input group "=== Exit scale-out ==="
input int    InpSLatrPeriod   = 14;    // ATR period cho SL ban dau
input double InpSLmult        = 2.5;   // He so ATR cho SL (1R)
input double InpBEtriggerR    = 1.0;   // Doi breakeven khi dat +X R
input double InpTP1multR       = 2.0;  // Chot mot phan tai +X R
input double InpPartialFrac    = 0.5;  // Ty le khoi luong chot (0 = khong chot phan)
input int    InpTrailATRPeriod = 10;   // ATR period cho trailing runner
input double InpTrailMult       = 2.0; // He so ATR trailing runner

//================== INPUTS: RISK / EXEC ============================
input group "=== Rui ro & thuc thi ==="
input double InpRiskMoney     = 20.0;  // 1R = rui ro moi lenh (USD), DA gom spread
input double InpCommPerLot    = 0.0;   // Commission round-turn / 1 lot
input int    InpMaxSpreadPts  = 30;    // Spread toi da (points) cho vao lenh
input int    InpSlippagePts   = 20;    // Deviation (points)
input long   InpMagic         = 990055;// Magic number
input int    InpWarmupBars    = 1500;  // So nen seed gia tri Trail

//================== STATE ==========================================
int    hATR1=INVALID_HANDLE,hATR2=INVALID_HANDLE,hATRsl=INVALID_HANDLE,hATRtr=INVALID_HANDLE;
double gTrail1=0,gTrail2=0,gTrail1Prev=0,gTrail2Prev=0;
bool   gSeeded=false; datetime gLastBarTime=0;
double gPoint,gPip; int gDigits;
// trang thai vi the hien tai
ulong  gTicket=0; double gEntry=0,gSLdist=0,gInitVol=0,gSprEntry=0; int gDir=0;
bool   gBeDone=false,gTp1Done=false;

//+------------------------------------------------------------------+
double ComputeTrail(const double c,const double cPrev,const double prev,const double sl)
{
   if(c>prev && cPrev>prev) return MathMax(prev,c-sl);
   if(c<prev && cPrev<prev) return MathMin(prev,c+sl);
   if(c>prev)               return c-sl;
   return c+sl;
}
double DonchianMid(const int period,const int shift)
{
   int hi=iHighest(_Symbol,_Period,MODE_HIGH,period,shift);
   int lo=iLowest (_Symbol,_Period,MODE_LOW ,period,shift);
   if(hi<0||lo<0) return 0.0;
   return (iHigh(_Symbol,_Period,hi)+iLow(_Symbol,_Period,lo))/2.0;
}
double GetATR(const int handle,const int shift)
{
   double b[]; if(CopyBuffer(handle,0,shift,1,b)<1) return 0.0; return b[0];
}
double MinStopDist(){ return (double)SymbolInfoInteger(_Symbol,SYMBOL_TRADE_STOPS_LEVEL)*gPoint; }

//+------------------------------------------------------------------+
bool SeedTrails()
{
   int total=Bars(_Symbol,_Period); if(total<100) return false;
   int warm=MathMin(total-2,InpWarmupBars); if(warm<50) return false;
   double cl[],a1[],a2[]; ArraySetAsSeries(cl,true);ArraySetAsSeries(a1,true);ArraySetAsSeries(a2,true);
   if(CopyClose(_Symbol,_Period,1,warm,cl)<warm) return false;
   if(CopyBuffer(hATR1,0,1,warm,a1)<warm) return false;
   if(CopyBuffer(hATR2,0,1,warm,a2)<warm) return false;
   double p1=0,p2=0;
   for(int i=warm-1;i>=0;i--)
   {
      double c=cl[i], cP=(i+1<=warm-1)?cl[i+1]:cl[i];
      if(i==0){ gTrail1Prev=p1; gTrail2Prev=p2; }
      p1=ComputeTrail(c,cP,p1,InpFastATRMult*a1[i]);
      p2=ComputeTrail(c,cP,p2,InpSlowATRMult*a2[i]);
   }
   gTrail1=p1; gTrail2=p2; gSeeded=true; return true;
}
void UpdateTrailsIncremental()
{
   double c=iClose(_Symbol,_Period,1), cP=iClose(_Symbol,_Period,2);
   double o1=gTrail1,o2=gTrail2; gTrail1Prev=o1; gTrail2Prev=o2;
   gTrail1=ComputeTrail(c,cP,o1,InpFastATRMult*GetATR(hATR1,1));
   gTrail2=ComputeTrail(c,cP,o2,InpSlowATRMult*GetATR(hATR2,1));
}

//+------------------------------------------------------------------+
bool SelectPos()
{
   if(!PositionSelect(_Symbol)) return false;
   if(PositionGetInteger(POSITION_MAGIC)!=InpMagic) return false;
   return true;
}
double NormVol(double v)
{
   double st=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_STEP);
   double mn=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MIN);
   double mx=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MAX);
   if(st<=0) st=0.01;
   v=MathFloor(v/st)*st; v=MathMax(mn,MathMin(mx,v)); return v;
}
double CalcLots(const double slDist,const double spreadPrice)
{
   double tv=SymbolInfoDouble(_Symbol,SYMBOL_TRADE_TICK_VALUE);
   double ts=SymbolInfoDouble(_Symbol,SYMBOL_TRADE_TICK_SIZE);
   if(tv<=0||ts<=0||slDist<=0) return 0.0;
   double moneyPerLot=((slDist+spreadPrice)/ts)*tv + InpCommPerLot;
   if(moneyPerLot<=0) return 0.0;
   return NormVol(InpRiskMoney/moneyPerLot);
}

//+------------------------------------------------------------------+
void OpenTrade(const bool isLong)
{
   double ask=SymbolInfoDouble(_Symbol,SYMBOL_ASK), bid=SymbolInfoDouble(_Symbol,SYMBOL_BID);
   double spread=ask-bid;
   double slDist=InpSLmult*GetATR(hATRsl,1);
   double minStop=MinStopDist();
   if(slDist<minStop) slDist=minStop;
   double lot=CalcLots(slDist,spread);
   if(lot<=0){ Print("[Bo qua] lot=0"); return; }
   double entry=isLong?ask:bid;
   double sl=isLong?entry-slDist:entry+slDist;
   sl=NormalizeDouble(sl,gDigits);
   bool ok=isLong?trade.Buy(lot,_Symbol,0,sl,0,"IchiATR ScaleOut")
                 :trade.Sell(lot,_Symbol,0,sl,0,"IchiATR ScaleOut");
   if(!ok){ PrintFormat("[Loi mo lenh] %d %s",trade.ResultRetcode(),trade.ResultRetcodeDescription()); return; }
   // luu trang thai
   if(SelectPos())
   {
      gTicket  =(ulong)PositionGetInteger(POSITION_IDENTIFIER);
      gEntry   =PositionGetDouble(POSITION_PRICE_OPEN);
      gInitVol =PositionGetDouble(POSITION_VOLUME);
      gSLdist  =slDist; gSprEntry=spread; gDir=isLong?1:-1;
      gBeDone=false; gTp1Done=false;
      PrintFormat("[%s] lot=%.2f entry=%.5f SL=%.5f 1R=%.2f$ (SLdist=%.5f gom spread)",
                  isLong?"BUY":"SELL",gInitVol,gEntry,sl,InpRiskMoney,slDist+spread);
   }
}

//+------------------------------------------------------------------+
//| Dong bo trang thai (vd EA khoi dong lai giua lenh)               |
//+------------------------------------------------------------------+
void SyncState()
{
   ulong id=(ulong)PositionGetInteger(POSITION_IDENTIFIER);
   if(id==gTicket && gDir!=0) return;            // da co trang thai
   gTicket=id;
   gEntry =PositionGetDouble(POSITION_PRICE_OPEN);
   gInitVol=PositionGetDouble(POSITION_VOLUME);
   gDir   =(PositionGetInteger(POSITION_TYPE)==POSITION_TYPE_BUY)?1:-1;
   double cur=PositionGetDouble(POSITION_SL);
   gSLdist=(cur>0)?MathAbs(gEntry-cur):InpSLmult*GetATR(hATRsl,1);
   gSprEntry=SymbolInfoDouble(_Symbol,SYMBOL_ASK)-SymbolInfoDouble(_Symbol,SYMBOL_BID);
   // suy doan breakeven da chua: SL da o ben loi
   gBeDone=((gDir==1 && cur>=gEntry) || (gDir==-1 && cur>0 && cur<=gEntry));
   gTp1Done=false;
}

//+------------------------------------------------------------------+
//| Quan ly moi tick: breakeven + chot mot phan                     |
//+------------------------------------------------------------------+
void ManageTick()
{
   double bid=SymbolInfoDouble(_Symbol,SYMBOL_BID), ask=SymbolInfoDouble(_Symbol,SYMBOL_ASK);
   double curSL=PositionGetDouble(POSITION_SL), tp=PositionGetDouble(POSITION_TP);
   double minStop=MinStopDist();

   if(gDir==1)
   {
      // breakeven
      if(!gBeDone && bid>=gEntry+InpBEtriggerR*gSLdist)
      {
         double be=NormalizeDouble(gEntry+gSprEntry,gDigits);
         if(be>curSL && be<bid-minStop){ if(trade.PositionModify(_Symbol,be,tp)) gBeDone=true; }
         else gBeDone=true;
      }
      // partial
      if(InpPartialFrac>0 && !gTp1Done && bid>=gEntry+InpTP1multR*gSLdist)
      {
         double vol=NormVol(InpPartialFrac*gInitVol);
         double rem=PositionGetDouble(POSITION_VOLUME)-vol;
         double mn=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MIN);
         if(vol>=mn && rem>=mn){ if(trade.PositionClosePartial(_Symbol,vol)) gTp1Done=true; }
         else gTp1Done=true;
      }
   }
   else if(gDir==-1)
   {
      if(!gBeDone && ask<=gEntry-InpBEtriggerR*gSLdist)
      {
         double be=NormalizeDouble(gEntry-gSprEntry,gDigits);
         if((curSL==0||be<curSL) && be>ask+minStop){ if(trade.PositionModify(_Symbol,be,tp)) gBeDone=true; }
         else gBeDone=true;
      }
      if(InpPartialFrac>0 && !gTp1Done && ask<=gEntry-InpTP1multR*gSLdist)
      {
         double vol=NormVol(InpPartialFrac*gInitVol);
         double rem=PositionGetDouble(POSITION_VOLUME)-vol;
         double mn=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MIN);
         if(vol>=mn && rem>=mn){ if(trade.PositionClosePartial(_Symbol,vol)) gTp1Done=true; }
         else gTp1Done=true;
      }
   }
}

//+------------------------------------------------------------------+
//| Trailing runner tren nen moi (tu nen da dong)                   |
//+------------------------------------------------------------------+
void ManageNewBarTrail()
{
   double curSL=PositionGetDouble(POSITION_SL), tp=PositionGetDouble(POSITION_TP);
   double c1=iClose(_Symbol,_Period,1), atrt=GetATR(hATRtr,1);
   double minStop=MinStopDist();
   if(gDir==1)
   {
      double newSL=NormalizeDouble(c1-InpTrailMult*atrt,gDigits);
      double bid=SymbolInfoDouble(_Symbol,SYMBOL_BID);
      if(newSL>curSL && newSL<bid-minStop) trade.PositionModify(_Symbol,newSL,tp);
   }
   else if(gDir==-1)
   {
      double newSL=NormalizeDouble(c1+InpTrailMult*atrt,gDigits);
      double ask=SymbolInfoDouble(_Symbol,SYMBOL_ASK);
      if((curSL==0||newSL<curSL) && newSL>ask+minStop) trade.PositionModify(_Symbol,newSL,tp);
   }
}

//+------------------------------------------------------------------+
int OnInit()
{
   gDigits=(int)SymbolInfoInteger(_Symbol,SYMBOL_DIGITS);
   gPoint =SymbolInfoDouble(_Symbol,SYMBOL_POINT);
   gPip   =(gDigits==3||gDigits==5)?10*gPoint:gPoint;
   hATR1 =iATR(_Symbol,_Period,InpFastATRPeriod);
   hATR2 =iATR(_Symbol,_Period,InpSlowATRPeriod);
   hATRsl=iATR(_Symbol,_Period,InpSLatrPeriod);
   hATRtr=iATR(_Symbol,_Period,InpTrailATRPeriod);
   if(hATR1==INVALID_HANDLE||hATR2==INVALID_HANDLE||hATRsl==INVALID_HANDLE||hATRtr==INVALID_HANDLE)
   { Print("Khong tao duoc ATR handle"); return INIT_FAILED; }
   trade.SetExpertMagicNumber(InpMagic);
   trade.SetDeviationInPoints(InpSlippagePts);
   trade.SetTypeFillingBySymbol(_Symbol);
   gSeeded=false; gLastBarTime=0; gTicket=0; gDir=0;
   PrintFormat("Ichimoku_ATR_ScaleOut_EA OK | 1R=%.2f %s | exit: BE@%.2fR, partial %.0f%%@%.2fR, runner ATR%dx%.2f",
               InpRiskMoney,AccountInfoString(ACCOUNT_CURRENCY),InpBEtriggerR,
               InpPartialFrac*100,InpTP1multR,InpTrailATRPeriod,InpTrailMult);
   return INIT_SUCCEEDED;
}
void OnDeinit(const int reason)
{
   if(hATR1!=INVALID_HANDLE) IndicatorRelease(hATR1);
   if(hATR2!=INVALID_HANDLE) IndicatorRelease(hATR2);
   if(hATRsl!=INVALID_HANDLE)IndicatorRelease(hATRsl);
   if(hATRtr!=INVALID_HANDLE)IndicatorRelease(hATRtr);
}

//+------------------------------------------------------------------+
void OnTick()
{
   // 1) Quan ly vi the moi tick (breakeven + partial)
   if(SelectPos()){ SyncState(); ManageTick(); }
   else { gTicket=0; gDir=0; }

   // 2) Cong viec tren NEN MOI
   datetime bt=iTime(_Symbol,_Period,0);
   if(bt==gLastBarTime) return;
   if(BarsCalculated(hATR1)<InpFastATRPeriod+2 || BarsCalculated(hATR2)<InpSlowATRPeriod+2 ||
      BarsCalculated(hATRsl)<InpSLatrPeriod+2 || BarsCalculated(hATRtr)<InpTrailATRPeriod+2) return;
   if(!gSeeded){ if(!SeedTrails()) return; } else UpdateTrailsIncremental();
   gLastBarTime=bt;

   // tin hieu ATR cross (nen da dong)
   bool buySig =(gTrail1Prev<=gTrail2Prev)&&(gTrail1> gTrail2);
   bool sellSig=(gTrail1Prev>=gTrail2Prev)&&(gTrail1< gTrail2);
   // loc may duoi nen da dong
   double c1=iClose(_Symbol,_Period,1);
   int cs=InpDisplacement;
   double spanA=(DonchianMid(InpTenkan,cs)+DonchianMid(InpKijun,cs))/2.0;
   double spanB=DonchianMid(InpSenkouB,cs);
   bool cloudOK=(spanA!=0&&spanB!=0);
   double ctop=MathMax(spanA,spanB), cbot=MathMin(spanA,spanB);
   bool longOK = buySig  && (!InpUseCloudFilter || (cloudOK && c1>ctop));
   bool shortOK= sellSig && (!InpUseCloudFilter || (cloudOK && c1<cbot));

   if(SelectPos()){ SyncState(); ManageNewBarTrail(); }    // runner trailing
   else
   {
      if(longOK||shortOK)
      {
         long sp=SymbolInfoInteger(_Symbol,SYMBOL_SPREAD);
         if(sp>InpMaxSpreadPts){ PrintFormat("[Bo qua] spread %d>%d",(int)sp,InpMaxSpreadPts); return; }
         OpenTrade(longOK);
      }
   }
}
//+------------------------------------------------------------------+
