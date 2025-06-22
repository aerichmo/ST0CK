"""
Configuration for ST0CKA - Placeholder Strategy
To be implemented
"""
from datetime import time

ST0CKA_CONFIG = {
    'bot_id': 'st0cka',
    'strategy_name': 'ST0CKA - TBD Strategy',
    'active': False,  # Disabled until strategy is defined
    
    # Trading window placeholder
    'trading_window': {
        'start': time(9, 30),
        'end': time(15, 30),
        'focus': 'TBD'
    },
    
    # Position sizing placeholder
    'capital': 10000,
    'risk_per_trade': 0.02,
    'max_position_size': 0.25,
    'max_daily_loss': 500,
    'max_consecutive_losses': 3,
    'max_trades_per_day': 10,
    'max_concurrent_positions': 3,
    
    # Alpaca settings
    'alpaca': {
        'paper': True,
        'api_key': 'APCA_API_KEY_ID',
        'secret_key': 'APCA_API_SECRET_KEY'
    }
}