"""
Configuration for ST0CKG - Opening Range Breakout Strategy
"""
from datetime import time

ST0CKG_CONFIG = {
    'bot_id': 'st0ckg',
    'strategy_name': 'Opening Range Breakout',
    
    # Trading window
    'trading_start_time': time(9, 40),
    'trading_end_time': time(10, 30),
    
    # Opening range calculation
    'opening_range_start': time(9, 30),
    'opening_range_end': time(9, 40),
    'min_opening_range': 0.50,  # Minimum range in dollars
    
    # Entry conditions
    'breakout_threshold': 0.001,  # 0.1% above/below range
    'min_signal_strength': 0.5,
    'confirmation_bars': 1,
    
    # Position sizing
    'capital': 5000,
    'max_risk_per_trade': 0.02,  # 2% risk per trade
    'max_position_size': 0.25,   # 25% of capital max per position
    
    # Option selection
    'target_dte_min': 0,  # Same day expiry
    'target_dte_max': 1,  # Next day max
    'target_delta': 0.30,  # Target 30 delta options
    'delta_range': 0.10,   # Accept 20-40 delta
    'min_volume': 100,     # Minimum option volume
    'max_spread_pct': 0.10,  # Max 10% bid-ask spread
    
    # Exit rules
    'stop_loss_atr_multiplier': 1.5,
    'target_1_atr_multiplier': 1.0,
    'target_2_atr_multiplier': 2.0,
    'time_stop': time(10, 25),  # Exit all by 10:25
    'trailing_stop_activation': 0.10,  # Activate at 10% profit
    'trailing_stop_distance': 0.05,    # Trail by 5%
    
    # Risk management
    'max_daily_loss': 500,
    'max_consecutive_losses': 3,
    'max_trades_per_day': 5,
    'max_positions': 2,
    
    # Technical indicators
    'ema_fast': 8,
    'ema_slow': 21,
    'atr_period': 14,
    'volume_ma_period': 20,
    'min_volume_ratio': 1.2,  # 20% above average
    
    # Filters
    'use_trend_filter': True,
    'trend_ema': 50,
    'min_atr': 0.50,  # Minimum volatility
    'max_atr': 5.00,  # Maximum volatility
    
    # Alpaca settings
    'alpaca': {
        'paper': True,
        'api_key': 'APCA_API_KEY_ID',  # Will be replaced with env var
        'secret_key': 'APCA_API_SECRET_KEY'  # Will be replaced with env var
    }
}