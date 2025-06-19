from datetime import time
import pytz

TRADING_CONFIG = {
    "universe": {
        "base_symbols": ["SPY"],  # Simplified to SPY only
        "pre_market_gap_threshold": 0.0075,
        "min_market_cap": 5_000_000_000,
        "min_avg_option_volume": 10_000,
        "max_additional_symbols": 0  # No additional symbols
    },
    
    "session": {
        "timezone": pytz.timezone("US/Eastern"),
        "active_start": time(9, 40),
        "active_end": time(10, 30),
        "opening_range_start": time(9, 30),
        "opening_range_end": time(9, 40)
    },
    
    "trend_filter": {
        "timeframe": "5min",
        "ema_fast": 8,
        "ema_slow": 21
    },
    
    "entry": {
        "atr_multiplier": 0.15,
        "volume_multiplier": 1.5,
        "volume_lookback": 10
    },
    
    "options": {
        "target_delta": 0.40,
        "delta_tolerance": 0.05,
        "use_weekly": True
    },
    
    "risk_management": {
        "position_risk_pct": 0.10,
        "daily_loss_limit_pct": 0.20,
        "consecutive_loss_limit": 2,
        "max_positions": 1  # Single position for SPY focus
    },
    
    "exit_strategy": {
        "stop_loss_r": -1.0,
        "target_1_r": 1.5,
        "target_1_size_pct": 0.5,
        "target_2_r": 3.0,
        "time_stop_minutes": 60
    }
}