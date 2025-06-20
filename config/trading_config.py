from datetime import time
import pytz

TRADING_CONFIG = {
    "universe": {
        "base_symbols": ["SPY"],  # SPY only trading
        "pre_market_gap_threshold": 0.0075,
        "min_market_cap": 5_000_000_000,
        "min_avg_option_volume": 10_000,
        "max_additional_symbols": 0  # No additional symbols
    },
    
    "session": {
        "timezone": pytz.timezone("US/Eastern"),
        "active_start": time(9, 40),
        "active_end": time(10, 30),  # Morning only
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
        "use_weekly": True,
        "min_volume": 100,
        "min_open_interest": 500,
        "max_spread_pct": 0.10,  # Tighter spread for SPY
        "min_liquidity_score": 15  # Higher liquidity requirement for SPY
    },
    
    "risk_management": {
        "position_risk_pct": 0.20,  # Antiles approach: 20% for small accounts
        "daily_loss_limit_pct": 0.40,  # Allow 2 full losses
        "consecutive_loss_limit": 3,  # Slightly more room
        "max_positions": 1,  # Single position for SPY focus
        "account_size_tiers": {  # Antiles-style account building
            "micro": {"max": 5000, "risk_pct": 0.20},      # <$5k: 20% risk
            "small": {"max": 10000, "risk_pct": 0.15},     # $5-10k: 15% risk
            "medium": {"max": 25000, "risk_pct": 0.10},    # $10-25k: 10% risk
            "large": {"max": 50000, "risk_pct": 0.05},     # $25-50k: 5% risk
            "pro": {"max": float('inf'), "risk_pct": 0.03} # $50k+: 3% risk
        }
    },
    
    "exit_strategy": {
        "stop_loss_r": -1.0,
        "target_1_r": 1.0,  # Antiles: Quick base hits
        "target_1_size_pct": 0.75,  # Take most off the table
        "target_2_r": 2.0,  # Reduced from 3.0 for day trading
        "time_stop_minutes": 30  # Antiles: Quick in and out
    },
    
    "market_simulation": {
        "base_spread_pct": 0.02,
        "volatility_spread_mult": 0.5,
        "volume_spread_div": 10000,
        "min_spread_pct": 0.01,
        "max_spread_pct": 0.10,
        "price_drift": 0.02,
        "price_volatility": 0.1
    },
    
    "commission": {
        "base_rate": 0.65,
        "tier_1_threshold": 100,
        "tier_1_rate": 0.50,
        "tier_2_threshold": 1000,
        "tier_2_rate": 0.35
    },
    
    "monitoring": {
        "risk_threshold_pct": -2.5,
        "loss_threshold_dollars": -500
    },
    
    "execution_timing": {
        "pre_market_start": time(9, 20),
        "active_intervals": {
            "signal_scan": 1,
            "position_monitor": 1,
            "risk_log": 30
        },
        "monitoring_intervals": {
            "signal_scan": 5,
            "position_monitor": 2,
            "risk_log": 60
        },
        "idle_intervals": {
            "signal_scan": 30,
            "position_monitor": 10,
            "risk_log": 300
        }
    },
    
    "cache": {
        "market_data_ttl": 60,
        "risk_free_rate_ttl": 3600
    },
    
    "defaults": {
        "risk_free_rate": 0.045,
        "implied_volatility": 0.20
    }
}