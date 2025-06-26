"""
Configuration for ST0CKA - Simple SPY Scalping Strategy
Buy 1 share of SPY at market open and sell with $0.01 profit GTC
"""
from datetime import time

ST0CKA_CONFIG = {
    'bot_id': 'st0cka',
    'strategy_name': 'ST0CKA - SPY $0.01 Scalper',
    'active': True,  # Enable the strategy
    
    # Trading window - morning session only
    'trading_window': {
        'start': time(9, 30),  # Market open
        'end': time(11, 0),    # End of sell window
        'focus': 'SPY buy 9:30-10:15, sell 10:15-11:00'
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
    'stop_loss': 5.00,      # $5.00 stop loss for catastrophic protection
    'buy_window': {
        'start': time(9, 30),
        'end': time(10, 15)
    },
    'sell_window': {
        'start': time(10, 15),
        'end': time(11, 0)
    },
    
    # Alpaca settings
    'alpaca': {
        'paper': True,
        'api_key': 'APCA_API_KEY_ID',
        'secret_key': 'APCA_API_SECRET_KEY'
    }
}