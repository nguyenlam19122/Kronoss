"""Engine backtest event-driven cho chiến lược trend-following.

Đặc điểm:
  - Không lookahead: quyết định dùng dữ liệu nến i-1, khớp lệnh tại open nến i.
  - Position sizing theo rủi ro cố định: khối lượng = (equity * risk%) / khoảng_dừng_lỗ.
  - GỒNG LỆNH: Chandelier trailing stop chỉ siết theo chiều có lợi (ratchet),
    không bao giờ nới lỏng -> cho lãi chạy, bảo vệ lợi nhuận.
  - Mô phỏng chi phí spread (nửa spread mỗi chiều vào/ra).

Đầu vào df cần các cột do strategy.prepare() tạo ra.
Trả về (trades_df, equity_series).
"""
import numpy as np
import pandas as pd

from .config import BacktestParams, StrategyParams


def _record(index, entry_i, exit_i, direction, entry_price, exit_price, size, pnl, risk_amount):
    return {
        "entry_time": index[entry_i],
        "exit_time": index[exit_i],
        "direction": direction,
        "entry_price": entry_price,
        "exit_price": exit_price,
        "size": size,
        "bars_held": exit_i - entry_i,
        "pnl": pnl,
        "R": pnl / risk_amount if risk_amount else 0.0,  # bội số rủi ro
    }


def run_backtest(df: pd.DataFrame, sp: StrategyParams, bp: BacktestParams):
    o = df["open"].to_numpy(float)
    h = df["high"].to_numpy(float)
    l = df["low"].to_numpy(float)
    c = df["close"].to_numpy(float)
    ema_f = df["ema_fast"].to_numpy(float)
    ema_s = df["ema_slow"].to_numpy(float)
    adx = df["adx"].to_numpy(float)
    atr = df["atr"].to_numpy(float)
    dc_up = df["dc_upper_prev"].to_numpy(float)
    dc_lo = df["dc_lower_prev"].to_numpy(float)
    ch_hi = df["chand_high"].to_numpy(float)
    ch_lo = df["chand_low"].to_numpy(float)
    index = df.index

    n = len(df)
    spread = bp.spread            # chi phí spread round-turn (đơn vị giá) — tính TRỌN trong 1R
    cm = sp.chandelier_mult
    equity = bp.initial_equity
    equity_curve = np.full(n, bp.initial_equity, dtype=float)

    pos = 0                        # 0 = flat, 1 = long, -1 = short
    entry_price = init_stop = trail = size = risk_amount = 0.0
    entry_i = 0
    trades = []

    # Nến đầu tiên có đủ chỉ báo (cần thêm 1 vì quyết định dùng i-1)
    need = ~(np.isnan(ema_s) | np.isnan(adx) | np.isnan(atr) | np.isnan(dc_up) | np.isnan(ch_hi))
    valid = np.where(need)[0]
    start = (valid[0] + 1) if len(valid) else n

    for i in range(start, n):
        # ---------- 1) VÀO LỆNH (nếu đang flat), tín hiệu từ nến i-1 ----------
        if pos == 0:
            stop_dist = atr[i - 1] * sp.atr_stop_mult
            trend_up = (ema_f[i - 1] > ema_s[i - 1]) and (adx[i - 1] >= sp.adx_min)
            trend_dn = (ema_f[i - 1] < ema_s[i - 1]) and (adx[i - 1] >= sp.adx_min)
            long_sig = bp.allow_long and trend_up and (c[i - 1] > dc_up[i - 1])
            short_sig = bp.allow_short and trend_dn and (c[i - 1] < dc_lo[i - 1])

            if stop_dist > 0 and (long_sig or short_sig):
                # 1R cố định theo $ (mặc định) hoặc theo % equity
                risk_amount = bp.fixed_risk if bp.risk_mode == "fixed" else equity * bp.risk_pct
                # Sizing tính CẢ spread vào rủi ro: lỗ tối đa tại stop ban đầu (đã gồm
                # spread round-turn) = đúng risk_amount, vì lỗ = (stop_dist + spread) * size.
                size = risk_amount / (stop_dist + spread)
                entry_i = i
                if long_sig:
                    pos = 1
                    entry_price = o[i]
                    init_stop = entry_price - stop_dist
                    trail = init_stop
                else:
                    pos = -1
                    entry_price = o[i]
                    init_stop = entry_price + stop_dist
                    trail = init_stop

        # ---------- 2) GỒNG LỆNH / THOÁT (stop tính từ dữ liệu nến i-1) ----------
        if pos != 0:
            if pos == 1:
                trail = max(trail, ch_hi[i - 1] - atr[i - 1] * cm)   # chỉ siết lên
                stop = max(trail, init_stop)
                flip = sp.exit_on_trend_flip and (ema_f[i - 1] < ema_s[i - 1])
                if l[i] <= stop or flip:
                    exit_price = o[i] if flip else min(o[i], stop)
                    pnl = (exit_price - entry_price) * size - spread * size  # trừ phí spread round-turn
                    equity += pnl
                    trades.append(_record(index, entry_i, i, "long",
                                          entry_price, exit_price, size, pnl, risk_amount))
                    pos = 0
            else:
                trail = min(trail, ch_lo[i - 1] + atr[i - 1] * cm)   # chỉ siết xuống
                stop = min(trail, init_stop)
                flip = sp.exit_on_trend_flip and (ema_f[i - 1] > ema_s[i - 1])
                if h[i] >= stop or flip:
                    exit_price = o[i] if flip else max(o[i], stop)
                    pnl = (entry_price - exit_price) * size - spread * size  # trừ phí spread round-turn
                    equity += pnl
                    trades.append(_record(index, entry_i, i, "short",
                                          entry_price, exit_price, size, pnl, risk_amount))
                    pos = 0

        # ---------- 3) Định giá vốn theo close (mark-to-market, đã trừ phí thoát) ----------
        if pos == 1:
            equity_curve[i] = equity + (c[i] - entry_price) * size - spread * size
        elif pos == -1:
            equity_curve[i] = equity + (entry_price - c[i]) * size - spread * size
        else:
            equity_curve[i] = equity

    # Đóng lệnh còn mở tại nến cuối (để thống kê đầy đủ)
    if pos != 0:
        last = n - 1
        if pos == 1:
            exit_price = c[last]
            pnl = (exit_price - entry_price) * size - spread * size
        else:
            exit_price = c[last]
            pnl = (entry_price - exit_price) * size - spread * size
        equity += pnl
        trades.append(_record(index, entry_i, last, "long" if pos == 1 else "short",
                              entry_price, exit_price, size, pnl, risk_amount))
        equity_curve[last] = equity

    trades_df = pd.DataFrame(trades)
    equity_series = pd.Series(equity_curve, index=index, name="equity")
    return trades_df, equity_series
