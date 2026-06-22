"""Tham số cấu hình cho chiến lược trend-following H1 (forex).

Tách riêng StrategyParams (logic tín hiệu) và BacktestParams (mô phỏng vốn/chi phí)
để dễ tối ưu hoá và kiểm định độ bền (robustness) về sau.
"""
from dataclasses import dataclass


@dataclass
class StrategyParams:
    # --- Lọc xu hướng: chỉ giao dịch khi THỰC SỰ có trend ---
    ema_fast: int = 50          # EMA nhanh
    ema_slow: int = 200         # EMA chậm -> xác định chiều trend chính
    adx_period: int = 14
    adx_min: float = 20.0       # ADX phải > ngưỡng này (loại bỏ sideway)

    # --- Vào lệnh: breakout kênh Donchian theo chiều trend ---
    donchian_period: int = 20   # phá đỉnh/đáy N nến gần nhất

    # --- Đo biến động / dừng lỗ ---
    atr_period: int = 14
    atr_stop_mult: float = 2.0  # stop ban đầu = entry -/+ ATR * hệ số này (dùng để sizing)

    # --- Gồng lệnh: Chandelier trailing stop (trái tim của hệ thống) ---
    chandelier_period: int = 22  # lookback cho đỉnh/đáy cao nhất
    chandelier_mult: float = 3.0  # khoảng cách trailing = ATR * hệ số (lớn = gồng dài hơn)

    exit_on_trend_flip: bool = False  # False = để trailing stop tự lo, gồng lệnh dài theo trend


@dataclass
class BacktestParams:
    initial_equity: float = 10_000.0
    risk_pct: float = 0.01      # rủi ro cố định mỗi lệnh = 1% equity (position sizing theo ATR)
    spread: float = 0.0001      # spread/phí round-turn tính theo đơn vị giá (EURUSD ~1 pip = 0.0001)
    allow_long: bool = True
    allow_short: bool = True
