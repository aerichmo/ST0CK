"""
Configuration for ST0CKA - Strategy TBD
"""
from datetime import time

ST0CKA_CONFIG = {
    'bot_id': 'st0cka',
    'strategy_name': 'Strategy TBD',
    
    # Trading window (placeholder)
    'trading_start_time': time(9, 30),
    'trading_end_time': time(16, 0),
    
    # Position sizing
    'capital': 10000,
    'max_risk_per_trade': 0.02,
    'max_position_size': 0.25,
    
    # Risk management
    'max_daily_loss': 1000,
    'max_consecutive_losses': 3,
    'max_trades_per_day': 10,
    'max_positions': 3,
    
    # Alpaca settings
    'alpaca': {
        'paper': True,
        'api_key': 'APCA_API_KEY_ID',
        'secret_key': 'APCA_API_SECRET_KEY'
    },
    
    # Placeholder - strategy not yet implemented
    'active': False
}