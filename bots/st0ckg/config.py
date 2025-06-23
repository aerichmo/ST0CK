"""
Configuration for APEX - Simplified SPY Options Strategy
Lean, efficient, focused on execution
"""
from datetime import time

ST0CKG_CONFIG = {
    'bot_id': 'st0ckg',
    'strategy_name': 'ST0CKG - APEX Strategy',
    
    # Single morning session only
    'trading_window': {
        'start': time(9, 30),
        'end': time(11, 0),
        'focus': 'Morning momentum and breakouts'
    },
    
    # Simplified position sizing
    'capital': 5000,
    'risk_per_trade': 0.035,  # 3.5% flat risk
    'max_position_size': 0.40,  # 40% of capital max
    'max_daily_loss': 500,
    'max_consecutive_losses': 3,
    'max_trades_per_day': 5,
    'max_concurrent_positions': 2,
    
    # Simple entry signals (only 2)
    'entry_signals': {
        'momentum_breakout': {
            'enabled': True,
            'min_move': 0.003,  # 0.3% move required
            'volume_confirmation': 1.3,  # 30% above average
            'confirmation_bars': 2
        },
        'vwap_mean_reversion': {
            'enabled': True,
            'min_distance': 0.002,  # 0.2% from VWAP
            'max_distance': 0.005,  # 0.5% max distance
            'volume_confirmation': 1.2
        }
    },
    
    # Options configuration (required by engine)
    'options': {
        'target_delta': 0.50,  # ATM options
        'max_dte': 0,  # 0DTE only
        'min_volume': 500,
        'max_spread': 0.10,  # $0.10 max spread
        'min_time_to_expiry': 180  # 3 hours minimum
    },
    
    # Simple option selection
    'option_selection': {
        'target_dte': 0,  # 0DTE only
        'strike_selection': 'ATM',  # Just use ATM
        'min_volume': 500,
        'max_spread_pct': 0.05,  # 5% max spread
        'min_time_to_expiry': 180  # 3 hours minimum
    },
    
    # Basic exit rules
    'exit_rules': {
        'stop_loss_atr': 1.5,
        'profit_target_atr': 2.0,
        'time_stop_minutes': 60,  # Exit after 60 minutes
        'trailing_stop_activation': 1.5,  # Activate at 1.5R
        'trailing_stop_distance': 0.5  # Trail by 0.5R
    },
    
    # Simple filters
    'filters': {
        'min_spy_volume': 1000000,  # Need decent volume
        'max_vix': 30,  # Skip high volatility days
        'min_atr': 1.0,  # Need movement
        'trend_filter': True,  # Trade with 20 EMA
    },
    
    # Technical indicators (minimal)
    'indicators': {
        'ema_period': 20,
        'atr_period': 14,
        'volume_period': 20,
        'vwap_enabled': True
    },
    
    # Alpaca settings
    'alpaca': {
        'paper': True,
        'api_key': 'APCA_API_KEY_ID',
        'secret_key': 'APCA_API_SECRET_KEY'
    }
}