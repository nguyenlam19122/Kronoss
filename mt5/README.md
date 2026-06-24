# Forecast-to-Fill (FTF) — MQL5 Expert Advisor

A faithful MetaTrader 5 replication of the strategy in:

> Mainak Singha, Jose Aguilera-Toste, Vinayak Lahiri (2025).
> **Forecast-to-Fill: Benchmark-Neutral Alpha and Billion-Dollar Capacity in Gold Futures (2015–2025).**
> arXiv:2511.08571v1 [q-fin.TR].

The EA reproduces, step for step, the paper's **daily-bar, long-only trend +
momentum** pipeline so you can backtest it in the MT5 Strategy Tester and run it
on demo/live. File: [`ForecastToFill_FTF.mq5`](ForecastToFill_FTF.mq5).

---

## 1. What the strategy does (paper → code map)

Every block below is implemented in `ProcessBar()` / `Retrain()` and runs **once
per completed D1 bar**.

| Paper section | Step | Code |
|---|---|---|
| 3.2 / 6.1 | Smooth log-price with an EMA: `ỹ_t = λ·ỹ_{t-1} + (1-λ)·y_t`, slope `Δỹ_t = ỹ_t − ỹ_{t-1}` | `ema[] / slope[]` loop |
| 3.2 / 6.1 | Standardize the slope with **training-window** stats: `z_t = (Δỹ_t − μ_train)/σ_train` | `g_muTrain`, `g_sigTrain` in `Retrain()` |
| 3.3 / 6.2 | Clip to `[−3,3]`, map to trend confidence `p_trend = (z̄+3)/6 ∈ [0,1]` | `ptrend` |
| 3.4 / 6.2 | `K=50` momentum `m_t = 1{P_t/P_{t−K} > 1}`, blend `p_bull = ω·p_trend + (1−ω)·m_t`, `ω=0.6` | `mom`, `pbull` |
| 3.5 / 6.3 | **Entry**: `p_bull ≥ 0.52` **and** `Δỹ_t > 0` | `activate` |
| 3.5 / 6.3 | ATR(14) simple mean; **hard stop** `P_ent − 2·ATR`, **trailing** `peak − 1.5·ATR`, **timeout** 30 days, **de-risk** when `p_bear > 0.5` (halve, then close) | exit block in `ProcessBar()` |
| 4.1 | EWMA variance `σ̂²_{t+1} = θ·σ̂²_t + (1−θ)·r_t²`, seed `Var_train(r)`; target `σ* = 15%/√252`; `w_vol = min(W_max, σ*/σ̂)`, `W_max=2` | `g_varEwma`, `w_vol` |
| 4.2 | Confidence shaping `w_conf = w_vol · (p_bull−0.5)/0.5` | `conf`, `w_conf` |
| 4.3 / 7 | Friction-adjusted Kelly: solve `2σ²x² + 3γn^{3/2}x − 2(μ−nk) = 0`, `f* = x²`; fractional `f̃ = λ_Kelly·f*`, `λ_Kelly=0.4` | `KellyFStar()`, `ftilde` |
| 4.4 / 7.1 | Final weight `w_t = f̃·w_conf` (baseline `0.25·w_conf` when `f*≈0`), capped at `W_max` | `w_target` |
| 2.2 / 5 | **Walk-forward freeze**: every `InpRetrainDays` bars, re-estimate `μ_train, σ_train, (μ,σ)` from the trailing `InpTrainYears` of D1 history, forward-only | `Retrain()` |
| 4.5 / 10 | Capacity note: largest `L>0` with `g(L)=0` (printed to the log, informational) | `Lmax` in `Retrain()` |

Position sizing converts the dimensionless weight `w_t` (notional per \$1 of
equity) into lots via `lots = w_t · equity / (contract_size · price)`, normalized
to the symbol's volume step.

---

## 2. Install & run

1. Copy `ForecastToFill_FTF.mq5` into your terminal's
   `MQL5/Experts/` folder
   (in MT5: **File → Open Data Folder → MQL5 → Experts**).
2. Open it in **MetaEditor** and press **Compile** (F7). It should compile with 0
   errors. *(MQL5 can only be compiled inside MetaTrader/MetaEditor — there is no
   Linux/CI compiler, so the source here has been reviewed by hand.)*
3. Attach the EA to a **Gold, D1** chart (e.g. `XAUUSD`, or your broker's GC
   contract). The EA always pulls D1 data internally, but a D1 chart is clearest.
4. Make sure the chart symbol has **enough D1 history** loaded — scroll back so
   the terminal downloads several years (ideally the full 10-year training
   window). With less history the EA degrades gracefully (it trains on whatever
   is available).

**Backtest:** open the **Strategy Tester**, pick the EA, symbol `XAUUSD`,
timeframe `D1`, model **"Open prices only"** (the logic is close-to-close daily,
so this is exact and fast), and a date range with 10+ years of preceding history
for training.

> **Account type:** use a **NETTING** account (Tools → Options → or a netting
> demo). The EA manages a single net long position; hedging accounts will warn in
> the log and may behave differently.

---

## 3. Inputs (defaults = paper values)

| Input | Default | Paper |
|---|---|---|
| `InpLambda` | 0.90 | EMA λ — *the paper tunes this per window and never prints the value; 0.90 is a sensible mid-grid default. This is your main signal-speed knob.* |
| `InpMomK` | 50 | momentum window `K=50` |
| `InpOmega` | 0.60 | blend weight `ω=0.6` |
| `InpActThreshold` | 0.52 | activation `p_bull ≥ 0.52` |
| `InpAtrN` | 14 | ATR period |
| `InpHardStopMult` / `InpTrailMult` | 2.0 / 1.5 | stop multiples |
| `InpMaxAgeDays` | 30 | timeout |
| `InpBearDerisk` | 0.50 | de-risk threshold |
| `InpTargetVolAnn` | 0.15 | 15% vol target |
| `InpEwmaTheta` | 0.94 | RiskMetrics EWMA decay (paper says "20-day EWMA"; 0.94 is the cited RiskMetrics standard — tune to taste) |
| `InpWmax` | 2.0 | leverage cap |
| `InpKelly` | 0.40 | fractional Kelly `λ_Kelly` |
| `InpCostK_bps` | 0.7 | linear cost `k` (used **only** inside Kelly) |
| `InpGamma` | 0.02 | impact `γ` (used **only** inside Kelly) |
| `InpN_RoundTrips` | 1.0 | `n ≤ 1` round trip/day |
| `InpBaselineFrac` | 0.25 | baseline allocation when `f*≈0` |
| `InpTrainYears` | 10 | training lookback |
| `InpRetrainDays` | 21 | re-freeze cadence (~monthly walk-forward step) |
| `InpExposureScale` | **1.0** | see caveat below |

---

## 4. Important caveats — read before trusting any number

These are honest notes so your experiments aren't misled. The EA reproduces the
paper's **logic** exactly; it cannot reproduce the paper's **dataset** or fix the
issues baked into the paper's own reporting.

1. **The "43%/yr, Sharpe 2.88" headline is a hypothetical re-scaling, not the
   strategy as it actually trades.** The realized strategy in the paper runs at
   **0.91% annualized volatility** with **2.65% CAGR**. The 43% figure comes from
   multiplying every position by `c = 15/0.91 ≈ 16.5` to *pretend* it ran at the
   15% vol budget (paper Sec 10). With `InpExposureScale = 1.0` you get the real,
   small-exposure strategy (mean weight ≈ 0.033). Set `InpExposureScale ≈ 16.5`
   to emulate the headline 15%-vol version — but that is ~16× leverage and will
   be capped by `InpWmax` and by your broker's margin.

2. **`λ` (EMA smoothing) is not published in the paper.** It is listed among the
   per-window-tuned parameters but no value is given. `0.90` is a reasonable
   default; treat it as the primary thing to sweep in your experiments.

3. **Costs are handled twice, by design.** In the paper, `k` and `γ` are
   subtracted from a simulated P&L. Live/MT5, your broker charges real
   spread/commission on fills, so this EA uses `k` and `γ` **only** where the
   paper uses them analytically — inside the Kelly fraction. Don't expect the EA
   to add a synthetic 0.7 bps to each trade; set realistic spread/commission in
   the Strategy Tester instead.

4. **Walk-forward is trailing, not the paper's exact monthly slices.** Live, the
   EA re-estimates frozen stats from the trailing 10 years every `InpRetrainDays`
   bars (forward-only, no look-ahead). This matches *deployment*; it is not a
   bit-for-bit reproduction of the paper's overlapping 6-month OOS windows.

5. **The paper's results are extraordinary and self-reported.** A 0.52% max
   drawdown with a 2.88 Sharpe over 11 years is far outside typical trend-system
   behavior, and several of the paper's claims (e.g. CAGR re-scaling, capacity
   mapping) rest on assumptions you should scrutinize. Backtest it yourself on
   independent data before drawing conclusions — which is exactly what this EA is
   for.

6. **Not financial advice.** This is a research replication for experimentation.
   Test on **demo** first.

---

## 5. Reading the on-chart panel

While running, the EA prints a live panel (and a per-bar log line) showing
`p_bull`, `p_trend`, momentum, the standardized slope `z`, the annualized
`σ̂`, `w_vol` / `w_conf`, the Kelly `f*` / `f̃`, the final target weight, ATR, the
current state (`ENTER` / `HOLD` / `EXIT(...)` / `DERISK(...)`), and net vs. target
lots. Use it to verify each pipeline stage against the formulas above.
