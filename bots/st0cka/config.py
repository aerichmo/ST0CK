"""
Configuration for ST0CKA - Simple SPY Scalping Strategy
Buy 1 share of SPY at market open and sell with $0.01 profit GTC
"""
from datetime import time

def validate_config(config):
    """Validate ST0CKA configuration"""
    # Risk parameters
    assert 0 < config['risk_per_trade'] <= 1.0, f"risk_per_trade must be between 0 and 1, got {config['risk_per_trade']}"
    assert config['max_position_size'] > 0, f"max_position_size must be positive, got {config['max_position_size']}"
    assert config['max_daily_loss'] > 0, f"max_daily_loss must be positive, got {config['max_daily_loss']}"
    assert config['max_consecutive_losses'] > 0, f"max_consecutive_losses must be positive, got {config['max_consecutive_losses']}"
    assert config['max_trades_per_day'] > 0, f"max_trades_per_day must be positive, got {config['max_trades_per_day']}"
    
    # Strategy parameters
    assert config['symbol'], "symbol cannot be empty"
    assert config['profit_target'] > 0, f"profit_target must be positive, got {config['profit_target']}"
    assert config['stop_loss'] > config['profit_target'], f"stop_loss ({config['stop_loss']}) must be greater than profit_target ({config['profit_target']})"
    
    # Time windows
    assert config['trading_window']['start'] < config['trading_window']['end'], "trading window start must be before end"
    assert config['buy_window']['start'] < config['buy_window']['end'], "buy window start must be before end"
    assert config['sell_window']['start'] < config['sell_window']['end'], "sell window start must be before end"
    
    # Capital
    assert config['capital'] > 0, f"capital must be positive, got {config['capital']}"
    
    return True

ST0CKA_CONFIG = {
    'bot_id': 'st0cka',
    'strategy_name': 'ST0CKA - SPY $0.01 Scalper',
    'active': True,  # Enable the strategy
    
    # Engine configuration
    'engine_mode': 'simple',
    'symbol': 'SPY',
    'use_market_data': True,
    'auto_shutdown': True
    
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

# Validate config on import
validate_config(ST0CKA_CONFIG)