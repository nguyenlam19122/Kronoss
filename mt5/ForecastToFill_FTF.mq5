//+------------------------------------------------------------------+
//|                                           ForecastToFill_FTF.mq5  |
//|        Faithful MQL5 replication of the "Forecast-to-Fill" paper  |
//|                                                                   |
//|  Reference:                                                       |
//|    Singha, Aguilera-Toste, Lahiri (2025),                         |
//|    "Forecast-to-Fill: Benchmark-Neutral Alpha and Billion-Dollar  |
//|     Capacity in Gold Futures (2015-2025)", arXiv:2511.08571v1.    |
//|                                                                   |
//|  This Expert Advisor reproduces, step for step, the daily-bar,    |
//|  long-only trend+momentum pipeline described in the paper:        |
//|                                                                   |
//|    1. EMA smoothing of log price          -> paper Sec 3.2 / 6.1  |
//|    2. Slope z-score (train-window stats)  -> paper Sec 3.2 / 6.1  |
//|    3. Clip + affine map -> p_trend in[0,1]-> paper Sec 3.3 / 6.2  |
//|    4. K=50 momentum blend -> p_bull       -> paper Sec 3.4 / 6.2  |
//|    5. Activation (p_bull>=0.52 & slope>0) -> paper Sec 3.5 / 6.3  |
//|    6. ATR(14) hard/trailing stops, timeout-> paper Sec 3.5 / 6.3  |
//|    7. EWMA variance vol targeting (15%)   -> paper Sec 4.1        |
//|    8. Confidence shaping w_conf           -> paper Sec 4.2        |
//|    9. Friction-adjusted Kelly fraction    -> paper Sec 4.3 / 7    |
//|   10. Weight -> executable position size  -> paper Sec 4.4 / 7.1  |
//|                                                                   |
//|  Walk-forward discipline (paper Sec 2.2, 5): every InpRetrainBars |
//|  bars the EA re-estimates and "freezes" the train-window stats    |
//|  (mu_train, sigma_train for the z-score; mu, sigma^2 for Kelly)   |
//|  from the trailing history on InpTimeframe, forward-only.         |
//|                                                                   |
//|  TIMEFRAME: this build runs NATIVE on InpTimeframe (default H1).  |
//|  All period parameters are in BAR units (momentum K=50 bars, ATR  |
//|  14 bars, timeout 30 bars) and volatility is annualized with      |
//|  InpBarsPerYear. On H1 this is a faster, short-horizon variant --  |
//|  it keeps the paper's STRUCTURE but is no longer the paper's      |
//|  daily-close edge. Set InpTimeframe=PERIOD_D1 + InpBarsPerYear=252 |
//|  to recover the exact daily strategy.                             |
//|                                                                   |
//|  NOTE: live brokers charge real spread/commission, so the paper's |
//|  k (0.7 bps) and gamma (0.02) are used ONLY inside the Kelly      |
//|  sizing math here (as the paper intends), not added synthetically |
//|  to fills. Use a NETTING account.                                 |
//+------------------------------------------------------------------+
#property copyright "Replication of arXiv:2511.08571v1"
#property link      "https://arxiv.org/abs/2511.08571"
#property version   "1.00"
#property strict

#include <Trade/Trade.mqh>

//==================================================================
//  INPUTS
//==================================================================
input group "=== Timeframe (NATIVE H1 build) ==="
input ENUM_TIMEFRAMES InpTimeframe = PERIOD_H1; // Bars the EA operates on. Paper is daily; for the exact paper set PERIOD_D1.

input group "=== Signal: trend EMA & momentum (paper Sec 3.2-3.4) ==="
input double InpLambda        = 0.90;   // EMA lambda: y~_t = lambda*y~_{t-1}+(1-lambda)*y_t (larger=slower). Paper tunes per window.
input int    InpMomK          = 50;     // Momentum lookback K (bars). Paper: K=50
input double InpOmega         = 0.60;   // Blend weight omega on trend vs momentum. Paper: 0.60
input double InpActThreshold  = 0.52;   // Activation threshold on p_bull. Paper: 0.52

input group "=== Exits: ATR stops & timeout (paper Sec 3.5) ==="
input int    InpAtrN          = 14;     // ATR period (simple mean). Paper: n=14
input double InpHardStopMult  = 2.0;    // Hard stop = P_ent - mult*ATR. Paper: 2.0
input double InpTrailMult     = 1.5;    // Trailing stop = peak - mult*ATR. Paper: 1.5
input int    InpMaxAgeBars    = 30;     // Max holding age in BARS. Paper: 30 (days on D1; here bars of InpTimeframe)
input double InpBearDerisk    = 0.50;   // De-risk when p_bear > this. Paper: 0.50

input group "=== Volatility targeting (paper Sec 4.1) ==="
input double InpTargetVolAnn  = 0.15;   // Annualized vol target. Paper: 15%
input int    InpBarsPerYear   = 6048;   // Bars per year for annualization. H1~=24*252=6048; D1=252 (paper)
input double InpEwmaTheta     = 0.94;   // EWMA variance decay theta (RiskMetrics). sigma2_{t+1}=theta*sigma2_t+(1-theta)*r_t^2
input double InpWmax          = 2.0;    // Leverage cap W_max on the weight. Paper: 2.0

input group "=== Friction-adjusted Kelly (paper Sec 4.3 / 7) ==="
input double InpKelly         = 0.40;   // Fractional-Kelly multiplier lambda_Kelly. Paper: 0.40
input double InpCostK_bps     = 0.7;    // Linear round-trip cost k in bps, used in Kelly. Paper: 0.7 bps
input double InpGamma         = 0.02;   // Square-root impact parameter gamma, used in Kelly. Paper: 0.02
input double InpN_RoundTrips  = 1.0;    // n round trips/bar in Kelly. Paper: n=1
input double InpBaselineFrac  = 0.25;   // Baseline = frac * regime-scaled budget when f~0. Paper: 0.25
input bool   InpBaselineUsesConf = true;// true: baseline=0.25*w_conf (Sec 4.3 "regime-scaled"); false: 0.25*w_vol (Sec 7.1)

input group "=== Walk-forward training (paper Sec 2.2 / 5) ==="
input int    InpTrainYears    = 10;     // Training lookback in years (clamped to available history). Paper: 10
input int    InpRetrainBars   = 504;    // Re-freeze train stats every N bars (~monthly: 21*24 on H1). Paper advances monthly.

input group "=== Execution / position sizing (paper Sec 4.4 / 7.1) ==="
input double InpExposureScale = 1.0;    // Multiplier on final weight. 1.0=as-written (realized vol ~0.91%). ~16.5 emulates the paper's 15%-vol / 43%/yr headline.
input bool   InpAllowMinLot   = true;   // If target lots < broker min but weight>0, trade the min lot.
input double InpRebalanceBand = 0.0;    // Min |delta lots| to act on (0 = use 1 volume step). Reduces churn from per-bar vol-target rebalancing.
input long   InpMagic         = 8508711;// EA magic number
input int    InpDeviation     = 30;     // Max price deviation (points)
input bool   InpVerbose       = true;   // Print signal/sizing diagnostics each bar

//==================================================================
//  GLOBAL STATE
//==================================================================
CTrade   trade;

// Frozen (walk-forward) parameters -- re-estimated every InpRetrainBars bars
double   g_muTrain   = 0.0;     // mean of slope over training window
double   g_sigTrain  = 1.0;     // std  of slope over training window
double   g_kMu       = 0.0;     // Kelly mu: mean active-day unit-notional return
double   g_kSig2     = 1.0e-6;  // Kelly sigma^2: var active-day unit-notional return
bool     g_trained   = false;
int      g_barsSinceRetrain = 0;

// Recursive (forward-only) EWMA variance forecast -- paper Sec 4.1
double   g_varEwma   = 0.0;
bool     g_haveVarSeed = false;

// Bar bookkeeping
datetime g_lastBarTime = 0;
long     g_barCounter  = 0;     // increments each processed bar (for trade age)

// Open-position record (reconstructed on restart if needed)
bool     g_inPos       = false;
double   g_entryPrice  = 0.0;
double   g_peakPrice   = 0.0;
long     g_entryBar    = 0;
bool     g_halvedOnce  = false;

//==================================================================
//  HELPERS
//==================================================================

//--- sample mean over inclusive index range [s,e] of array a (ascending)
double RangeMean(const double &a[], const int s, const int e)
{
   if(e < s) return 0.0;
   double sum = 0.0; int n = 0;
   for(int i = s; i <= e; i++){ sum += a[i]; n++; }
   return (n > 0) ? sum / n : 0.0;
}

//--- sample std (n-1) over inclusive index range [s,e]
double RangeStd(const double &a[], const int s, const int e, const double mean)
{
   if(e <= s) return 0.0;
   double ss = 0.0; int n = 0;
   for(int i = s; i <= e; i++){ double d = a[i]-mean; ss += d*d; n++; }
   return (n > 1) ? MathSqrt(ss/(n-1)) : 0.0;
}

//--- friction-adjusted Kelly optimal fraction f* (paper Sec 4.3 / 7)
//    Solve 2*sigma2*x^2 + 3*gamma*n^1.5*x - 2*(mu - n*k) = 0 for x>=0, f*=x^2.
double KellyFStar(const double mu, const double sigma2,
                  const double n, const double k, const double gamma)
{
   double edge = mu - n*k;                 // net edge after linear cost
   if(edge <= 0.0 || sigma2 <= 0.0) return 0.0;   // no edge -> f*=0 (paper)
   double a = 2.0*sigma2;
   double b = 3.0*gamma*MathPow(n, 1.5);
   double c = -2.0*edge;
   double disc = b*b - 4.0*a*c;            // = 9*gamma^2*n^3 + 16*sigma2*edge
   if(disc < 0.0) return 0.0;
   double x = (-b + MathSqrt(disc)) / (2.0*a);
   if(x <= 0.0) return 0.0;
   return x*x;                             // f* = (x*)^2
}

//--- normalize a lot size to the symbol's volume step / min / max
double NormalizeLots(double lots)
{
   double minl = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double maxl = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   if(step <= 0.0) step = 0.01;
   lots = MathFloor(lots/step + 0.5) * step;
   if(lots > maxl) lots = maxl;
   if(lots < 0.0)  lots = 0.0;
   return lots;
}

//--- convert a target portfolio weight (notional per $1 equity) into lots
double WeightToLots(const double weight, const double price)
{
   if(weight <= 0.0 || price <= 0.0) return 0.0;
   double equity   = AccountInfoDouble(ACCOUNT_EQUITY);
   double contract = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_CONTRACT_SIZE);
   if(equity <= 0.0 || contract <= 0.0) return 0.0;

   double notional = weight * equity;              // desired USD notional exposure
   double rawLots  = notional / (contract * price);// 1 lot notional = contract*price
   double lots     = NormalizeLots(rawLots);

   double minl = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   if(lots < minl)
      lots = (InpAllowMinLot && rawLots > 0.0) ? minl : 0.0;
   return lots;
}

//--- current NET long volume held by this EA (negative if net short)
double NetLong()
{
   double net = 0.0;
   for(int i = PositionsTotal()-1; i >= 0; i--)
   {
      ulong tk = PositionGetTicket(i);
      if(tk == 0) continue;
      if(!PositionSelectByTicket(tk)) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if(PositionGetInteger(POSITION_MAGIC) != InpMagic) continue;
      double v = PositionGetDouble(POSITION_VOLUME);
      net += (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY) ? v : -v;
   }
   return net;
}

//--- set the appropriate fill policy for the symbol
void ConfigureFilling()
{
   long fm = (long)SymbolInfoInteger(_Symbol, SYMBOL_FILLING_MODE);
   if((fm & SYMBOL_FILLING_FOK) != 0)      trade.SetTypeFilling(ORDER_FILLING_FOK);
   else if((fm & SYMBOL_FILLING_IOC) != 0) trade.SetTypeFilling(ORDER_FILLING_IOC);
   else                                    trade.SetTypeFilling(ORDER_FILLING_RETURN);
}

//==================================================================
//  WALK-FORWARD RE-ESTIMATION ("freeze" train-window parameters)
//==================================================================
//  close/high/low are ascending (oldest -> newest), length N.
//  ema/slope precomputed over the same window with the frozen lambda.
//  Estimates:
//    * g_muTrain, g_sigTrain : mean/std of the smoothed slope         (z-score)
//    * g_kMu, g_kSig2         : mean/var of active-day next-day return (Kelly)
//    * EWMA variance seed     : Var_train(simple returns)             (Sec 4.1)
void Retrain(const double &close[], const double &slope[], const double &ema[], const int N)
{
   int trainBars = InpTrainYears * InpBarsPerYear;
   int minStart  = InpMomK + InpAtrN + 2;          // need history for momentum/ATR/return
   int s = N - 1 - trainBars;
   if(s < minStart) s = minStart;                  // clamp to available history
   int e = N - 1;                                  // newest completed bar

   // --- (a) slope standardization stats: mu_train, sigma_train
   g_muTrain  = RangeMean(slope, s, e);
   g_sigTrain = RangeStd(slope, s, e, g_muTrain);
   if(g_sigTrain <= 0.0) g_sigTrain = 1.0e-12;

   // --- (b) seed the EWMA variance with Var_train(r) once (forward-only thereafter)
   if(!g_haveVarSeed)
   {
      double rsum = 0.0; int rn = 0;
      for(int i = s+1; i <= e; i++){ double r = close[i]/close[i-1]-1.0; rsum += r; rn++; }
      double rmean = (rn>0)? rsum/rn : 0.0;
      double rss = 0.0;
      for(int i = s+1; i <= e; i++){ double r = close[i]/close[i-1]-1.0; double d=r-rmean; rss += d*d; }
      g_varEwma = (rn>1)? rss/(rn-1) : 1.0e-8;
      if(g_varEwma <= 0.0) g_varEwma = 1.0e-8;
      g_haveVarSeed = true;
   }

   // --- (c) Kelly mu, sigma^2 from active-day unit-notional returns.
   //     Replay the (frozen) regime signal across training; when a long is
   //     active at day i, record next-day simple return r_{i+1}. mu/sigma^2
   //     of that set are the unit-notional edge moments fed to Kelly.
   double acc[]; ArrayResize(acc, 0); int m = 0;
   for(int i = s; i <= e-1; i++)
   {
      if(i-1 < 0 || i-InpMomK < 0) continue;
      double sl = slope[i];
      double z  = (sl - g_muTrain)/g_sigTrain;
      double zc = MathMax(-3.0, MathMin(3.0, z));
      double ptrend = (zc + 3.0)/6.0;
      double mom = (close[i]/close[i-InpMomK] > 1.0) ? 1.0 : 0.0;
      double pbull = InpOmega*ptrend + (1.0-InpOmega)*mom;
      if(pbull >= InpActThreshold && sl > 0.0)
      {
         double rnext = close[i+1]/close[i] - 1.0;   // unit-notional return
         ArrayResize(acc, m+1); acc[m] = rnext; m++;
      }
   }
   if(m >= 20)
   {
      g_kMu   = RangeMean(acc, 0, m-1);
      g_kSig2 = MathPow(RangeStd(acc, 0, m-1, g_kMu), 2.0);
      if(g_kSig2 <= 0.0) g_kSig2 = 1.0e-8;
   }
   else
   {
      // too few active samples -> let Kelly be ~0, baseline allocation will apply
      g_kMu = 0.0; g_kSig2 = 1.0e-6;
   }

   g_trained = true;
   g_barsSinceRetrain = 0;

   // --- capacity note (paper Sec 4.5 / 10): largest L>0 with g(L)=0 (info only)
   double n     = InpN_RoundTrips;
   double kfrac = InpCostK_bps * 1.0e-4;
   double mu_u  = g_kMu, sig_u = MathSqrt(g_kSig2);
   double Lmax  = 0.0;
   if(mu_u - n*kfrac > 0.0)
   {
      double lo = 1.0e-9, hi = 1.0;
      for(int it = 0; it < 100; it++)
      {
         double mid = 0.5*(lo+hi);
         double g = mu_u*mid - 0.5*MathPow(sig_u*mid,2.0) - n*kfrac*mid - InpGamma*MathPow(n*mid,1.5);
         if(g > 0.0) lo = mid; else hi = mid;
      }
      Lmax = 0.5*(lo+hi);
   }

   if(InpVerbose)
      PrintFormat("[FTF retrain] train[%d..%d] mu_train=%.3e sig_train=%.3e | KellyMu=%.3e KellySig2=%.3e (nAct=%d) | varSeed=%.3e | Lmax=%.3e",
                  s, e, g_muTrain, g_sigTrain, g_kMu, g_kSig2, m, g_varEwma, Lmax);
}

//==================================================================
//  PER-BAR PROCESSING (runs once per completed bar of InpTimeframe)
//==================================================================
void ProcessBar()
{
   // ---- pull enough completed history (skip the forming bar at shift 0) ----
   int trainBars = InpTrainYears * InpBarsPerYear;
   int need = trainBars + InpMomK + InpAtrN + 10;
   if(need > 120000) need = 120000;                // cap; broker returns what history it has

   MqlRates rates[];
   ArraySetAsSeries(rates, false);                 // ascending: [0]=oldest
   int got = CopyRates(_Symbol, InpTimeframe, 1, need, rates);
   if(got < InpMomK + InpAtrN + 5)
   {
      if(InpVerbose) PrintFormat("[FTF] not enough %s history yet (got=%d)",
                                 EnumToString(InpTimeframe), got);
      return;
   }
   int N = got;

   // ---- build close/high/low + log price, EMA, slope (paper Sec 3.2 / 6.1) ----
   double close[], high[], low[], y[], ema[], slope[];
   ArrayResize(close,N); ArrayResize(high,N); ArrayResize(low,N);
   ArrayResize(y,N); ArrayResize(ema,N); ArrayResize(slope,N);
   for(int i=0;i<N;i++)
   {
      close[i]=rates[i].close; high[i]=rates[i].high; low[i]=rates[i].low;
      y[i]=MathLog(close[i]);
   }
   ema[0]=y[0]; slope[0]=0.0;
   for(int i=1;i<N;i++)
   {
      ema[i]   = InpLambda*ema[i-1] + (1.0-InpLambda)*y[i];   // y~_t = lambda*y~_{t-1}+(1-lambda)*y_t
      slope[i] = ema[i]-ema[i-1];                              // Delta y~_t
   }

   // ---- (re)freeze train-window parameters on schedule ----
   if(!g_trained || g_barsSinceRetrain >= InpRetrainBars)
      Retrain(close, slope, ema, N);

   int t = N-1;                                    // newest completed bar index

   // ---- update the recursive EWMA variance forecast (paper Sec 4.1) ----
   double r_t = close[t]/close[t-1] - 1.0;
   g_varEwma = InpEwmaTheta*g_varEwma + (1.0-InpEwmaTheta)*r_t*r_t;
   double sigmaHat = MathSqrt(MathMax(g_varEwma, 1.0e-12)); // sigma_hat_{t+1}

   // ---- regime probability at t (paper Sec 3.3-3.4 / 6.2) ----
   double sl     = slope[t];
   double z      = (sl - g_muTrain)/g_sigTrain;
   double zc     = MathMax(-3.0, MathMin(3.0, z));
   double ptrend = (zc + 3.0)/6.0;                                  // [0,1]
   double mom    = (close[t]/close[t-InpMomK] > 1.0) ? 1.0 : 0.0;   // K-day momentum
   double pbull  = InpOmega*ptrend + (1.0-InpOmega)*mom;
   double pbear  = 1.0 - pbull;

   // ---- ATR(14) simple mean (paper Sec 3.5 / 6.3) ----
   double atrSum=0.0;
   for(int j=0;j<InpAtrN;j++)
   {
      int k=t-j;
      double tr = MathMax(high[k]-low[k],
                  MathMax(MathAbs(high[k]-close[k-1]), MathAbs(low[k]-close[k-1])));
      atrSum += tr;
   }
   double atr = atrSum/InpAtrN;

   // ---- volatility targeting -> w_vol (paper Sec 4.1) ----
   double sigmaStar = InpTargetVolAnn/MathSqrt((double)InpBarsPerYear); // per-bar target
   double w_vol = MathMin(InpWmax, sigmaStar/MathMax(sigmaHat,1.0e-12));

   // ---- confidence shaping -> w_conf (paper Sec 4.2) ----
   double conf  = (pbull - 0.5)/0.5;
   conf = MathMax(0.0, MathMin(1.0, conf));
   double w_conf = w_vol*conf;

   // ---- friction-adjusted Kelly (paper Sec 4.3 / 7) ----
   double kfrac  = InpCostK_bps * 1.0e-4;                  // bps -> fraction
   double fstar  = KellyFStar(g_kMu, g_kSig2, InpN_RoundTrips, kfrac, InpGamma);
   double ftilde = InpKelly * fstar;                       // fractional Kelly

   // ---- combine into final target weight (paper Sec 4.4 / 7.1) ----
   double w_raw;
   if(fstar <= 1.0e-9)                                      // f* numerically tiny -> baseline
      w_raw = InpBaselineFrac * (InpBaselineUsesConf ? w_conf : w_vol);
   else
      w_raw = ftilde * w_conf;
   double w_target = MathMin(InpWmax, InpExposureScale * w_raw);
   if(w_target < 0.0) w_target = 0.0;

   // ---- entry eligibility (paper Sec 3.5 / 6.3) ----
   bool activate = (pbull >= InpActThreshold) && (sl > 0.0);

   // ---- reconcile our position record with the actual book ----
   double netLong = NetLong();
   bool   holding = (netLong > 0.0);
   if(holding && !g_inPos)
   {
      // restarted with an existing position: reconstruct a conservative record
      g_inPos      = true;
      g_entryPrice = 0.0;
      // try to read the actual open price of our position
      for(int i=PositionsTotal()-1;i>=0;i--)
      {
         ulong tk=PositionGetTicket(i);
         if(tk && PositionSelectByTicket(tk)
            && PositionGetString(POSITION_SYMBOL)==_Symbol
            && PositionGetInteger(POSITION_MAGIC)==InpMagic)
         { g_entryPrice=PositionGetDouble(POSITION_PRICE_OPEN); break; }
      }
      if(g_entryPrice<=0.0) g_entryPrice=close[t];
      g_peakPrice = MathMax(g_entryPrice, close[t]);
      g_entryBar  = g_barCounter;
      g_halvedOnce= false;
   }
   if(!holding) g_inPos = false;

   // ---- decide desired weight & manage exits ----
   double desiredWeight = 0.0;
   string action = "flat";

   if(!g_inPos)
   {
      if(activate)
      {
         desiredWeight = w_target;
         action = "ENTER";
      }
   }
   else
   {
      // update running peak (close-to-close discipline, paper Sec 8)
      g_peakPrice = MathMax(g_peakPrice, close[t]);
      long age = g_barCounter - g_entryBar;

      double hardStop  = g_entryPrice - InpHardStopMult*atr;
      double trailStop = g_peakPrice  - InpTrailMult   *atr;

      bool exitHard  = (close[t] <= hardStop);
      bool exitTrail = (close[t] <= trailStop);
      bool exitTime  = (age >= InpMaxAgeBars);

      if(exitHard || exitTrail || exitTime)
      {
         desiredWeight = 0.0;
         action = exitHard ? "EXIT(hardstop)" : (exitTrail ? "EXIT(trail)" : "EXIT(timeout)");
      }
      else if(pbear > InpBearDerisk)
      {
         // regime de-risk: halve once, close if it persists (paper Sec 3.5)
         if(!g_halvedOnce){ desiredWeight = 0.5*w_target; g_halvedOnce=true; action="DERISK(halve)"; }
         else             { desiredWeight = 0.0;          action="DERISK(close)"; }
      }
      else
      {
         g_halvedOnce = false;                  // regime recovered
         desiredWeight = w_target;              // per-bar vol-target rebalance
         action = "HOLD/rebalance";
      }
   }

   // ---- translate desired weight into lots and trade the difference ----
   double price       = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   if(price<=0.0) price = close[t];
   double targetLots  = WeightToLots(desiredWeight, price);
   double step        = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   if(step<=0.0) step = 0.01;
   double band        = (InpRebalanceBand>0.0) ? InpRebalanceBand : step;
   double curLong     = MathMax(0.0, netLong);
   double diff        = targetLots - curLong;

   if(MathAbs(diff) >= band - 1.0e-12 && MathAbs(diff) >= step*0.5)
   {
      if(diff > 0.0)
      {
         if(trade.Buy(NormalizeLots(diff), _Symbol, 0.0, 0.0, 0.0, "FTF"))
         {
            if(!g_inPos)   // fresh entry bookkeeping
            {
               g_inPos=true; g_entryPrice=price; g_peakPrice=close[t];
               g_entryBar=g_barCounter; g_halvedOnce=false;
            }
         }
      }
      else
      {
         double reduce = NormalizeLots(-diff);
         if(reduce > 0.0)
         {
            if(targetLots <= 0.0) { trade.PositionClose(_Symbol); g_inPos=false; }
            else                    trade.Sell(reduce, _Symbol, 0.0, 0.0, 0.0, "FTF");
         }
      }
   }
   if(targetLots <= 0.0 && curLong <= 0.0) g_inPos = false;

   // ---- diagnostics ----
   if(InpVerbose)
      PrintFormat("[FTF %s] p_bull=%.3f p_trend=%.3f mom=%.0f slope=%.2e | sigmaHat=%.4f w_vol=%.3f w_conf=%.3f f*=%.2e w=%.4f | ATR=%.2f tgtLots=%.2f net=%.2f",
                  action, pbull, ptrend, mom, sl, sigmaHat, w_vol, w_conf, fstar, w_target, atr, targetLots, netLong);

   Comment(StringFormat(
      "Forecast-to-Fill (FTF) | %s %s\n"
      "-----------------------------------\n"
      "p_bull=%.3f  p_trend=%.3f  mom=%.0f  (act>=%.2f)\n"
      "slope=%.3e  z=%.2f\n"
      "sigmaHat(ann)=%.2f%%  w_vol=%.3f  conf=%.2f  w_conf=%.3f\n"
      "Kelly f*=%.3e  f~=%.3e  ->  w_target=%.4f (scale x%.1f)\n"
      "ATR(%d)=%.2f  state=%s  netLots=%.2f  tgtLots=%.2f\n"
      "trained=%s  barsSinceRetrain=%d",
      _Symbol, EnumToString(InpTimeframe),
      pbull, ptrend, mom, InpActThreshold,
      sl, z,
      sigmaHat*MathSqrt((double)InpBarsPerYear)*100.0, w_vol, conf, w_conf,
      fstar, ftilde, w_target, InpExposureScale,
      InpAtrN, atr, action, netLong, targetLots,
      (g_trained?"yes":"no"), g_barsSinceRetrain));
}

//==================================================================
//  MT5 EVENT HANDLERS
//==================================================================
int OnInit()
{
   trade.SetExpertMagicNumber(InpMagic);
   trade.SetDeviationInPoints(InpDeviation);
   trade.SetMarginMode();
   ConfigureFilling();

   if(_Period != InpTimeframe)
      Print("[FTF] NOTE: chart timeframe differs from InpTimeframe (",
            EnumToString(InpTimeframe), "). The EA uses InpTimeframe data regardless; ",
            "attaching it to a matching chart is recommended for clarity.");

   long mm = (long)AccountInfoInteger(ACCOUNT_MARGIN_MODE);
   if(mm == ACCOUNT_MARGIN_MODE_RETAIL_HEDGING)
      Print("[FTF] WARNING: account is in HEDGING mode. This EA assumes NETTING ",
            "(single net position). Please use a netting account for faithful behavior.");

   g_lastBarTime = 0;            // force processing on the first tick
   g_trained = false;
   g_haveVarSeed = false;
   g_inPos = (NetLong() > 0.0);
   Print("[FTF] initialized. Replicating arXiv:2511.08571v1 on ", _Symbol,
         " / ", EnumToString(InpTimeframe), " (native-bar build).");
   return(INIT_SUCCEEDED);
}

void OnDeinit(const int reason)
{
   Comment("");
}

void OnTick()
{
   // run once per completed bar of InpTimeframe
   datetime curBar = iTime(_Symbol, InpTimeframe, 0);
   if(curBar == g_lastBarTime) return;
   g_lastBarTime = curBar;

   g_barCounter++;
   if(g_trained) g_barsSinceRetrain++;

   ProcessBar();
}
//+------------------------------------------------------------------+
