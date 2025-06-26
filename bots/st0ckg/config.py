"""
Configuration for ST0CKG - Battle Lines Strategy
"""
from datetime import time

ST0CKG_CONFIG = {
    'bot_id': 'st0ckg',
    'strategy_name': 'ST0CKG - Battle Lines 0-DTE',
    
    # Trading window - after first 5-min bar
    'trading_window': {
        'start': time(9, 35),   # After first 5-min bar
        'end': time(15, 50),    # Before market close
        'focus': 'Battle line break-and-retest setups'
    },
    
    # Capital and risk
    'capital': 5000,
    'risk_per_trade': 0.01,    # 1% risk per trade
    'max_daily_loss': 0.02,    # 2R daily stop
    'max_wins_per_day': 2,     # Stop after 2 wins
    'max_losses_per_day': 2,   # Stop after 2 losses
    
    # Position sizing
    'max_position_size': 10,   # Max 10 contracts
    'default_stop_distance': 0.10,  # $0.10 SPY stop
    
    # Option selection
    'option_selection': {
        'target_delta': 0.30,   # ATM options
        'max_dte': 0,          # 0-DTE only
        'min_volume': 100,     # Minimum option volume
        'max_spread': 0.10,    # Max bid-ask spread
    },
    
    # Battle line thresholds
    'bias_threshold': 0.10,    # $0.10 beyond PDH/PDL for bias
    'retest_zone': 0.50,       # Look for setups within $0.50 of levels
    
    # Risk management
    'breakeven_r': 1.0,        # Move stop to BE at 1R
    'scale_out_r': 1.5,        # Scale half at 1.5R
    'final_target_r': 3.0,     # Full exit at 3R
    
    # Alpaca settings
    'alpaca': {
        'paper': True,
        'api_key': 'APCA_API_KEY_ID',
        'secret_key': 'APCA_API_SECRET_KEY'
    }
}