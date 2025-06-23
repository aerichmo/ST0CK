"""
Configuration for ST0CKA - Simple SPY Scalping Strategy
Buy 1 share of SPY at market open and sell with $0.01 profit GTC
"""
from datetime import time

ST0CKA_CONFIG = {
    'bot_id': 'st0cka',
    'strategy_name': 'ST0CKA - SPY $0.01 Scalper',
    'active': True,  # Enable the strategy
    
    # Trading window - focus on market open
    'trading_window': {
        'start': time(9, 30),  # Market open
        'end': time(9, 31),    # Only trade in first minute
        'focus': 'SPY market open scalping'
    },
    
    # Position sizing - minimal risk
    'capital': 10000,
    'risk_per_trade': 0.01,  # 1% risk
    'max_position_size': 1,  # Always 1 share
    'max_daily_loss': 10,    # Maximum $10 loss per day
    'max_consecutive_losses': 5,
    'max_trades_per_day': 1,  # Only one trade per day
    'max_concurrent_positions': 1,
    
    # Strategy specific
    'symbol': 'SPY',
    'profit_target': 0.01,  # $0.01 profit target
    'stop_loss': 1.00,      # $1.00 stop loss for safety
    'order_type': 'GTC',    # Good Till Canceled
    
    # Alpaca settings
    'alpaca': {
        'paper': True,
        'api_key': 'APCA_API_KEY_ID',
        'secret_key': 'APCA_API_SECRET_KEY'
    }
}