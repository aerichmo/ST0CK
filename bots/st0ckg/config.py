"""
Configuration for ST0CKG - Battle Lines Strategy
"""
from datetime import time

ST0CKG_CONFIG = {
    'bot_id': 'st0ckg',
    'strategy_name': 'ST0CKG - Battle Lines 0-DTE',
    'active': True,  # Enable the strategy
    
    # Trading window - after first 5-min bar
    'trading_window': {
        'start': time(9, 35),   # After first 5-min bar
        'end': time(15, 50),    # Before market close
        'entry_cutoff': time(11, 0),  # No new positions after 11:00 AM
        'focus': 'Battle line break-and-retest setups'
    },
    
    # Capital and risk
    'capital': 5000,
    'risk_per_trade': 0.05,    # 5% risk per trade
    'max_daily_loss': 0.02,    # 2R daily stop
    'max_wins_per_day': 2,     # Stop after 2 wins
    'max_losses_per_day': 2,   # Stop after 2 losses
    
    # Position sizing
    'max_position_size': 10,   # Max 10 contracts
    'default_stop_distance': 0.10,  # $0.10 SPY stop
    
    # Option selection
    'options': {
        'target_delta': 0.30,      # ATM options
        'delta_tolerance': 0.05,   # Accept deltas within +/- 0.05 of target
        'max_dte': 0,             # 0-DTE only
        'min_volume': 100,        # Minimum option volume
        'max_spread': 0.10,       # Max bid-ask spread
        'max_spread_pct': 2.0,    # Max spread as % of mid price
    },
    'option_selection': {
        'target_delta': 0.30,   # ATM options
        'max_dte': 0,          # 0-DTE only
        'min_volume': 100,     # Minimum option volume
        'max_spread': 0.10,    # Max bid-ask spread
    },
    
    # Trend filter configuration
    'trend_filter': {
        'ema_fast': 8,         # Fast EMA period
        'ema_slow': 21,        # Slow EMA period
    },
    
    # Session configuration
    'session': {
        'timezone': 'America/New_York',
    },
    
    # Entry configuration
    'entry': {
        'atr_multiplier': 1.5,     # ATR multiplier for volatility filter
        'volume_multiplier': 1.2,  # Volume multiplier for activity filter
    },
    
    # Battle line thresholds
    'bias_threshold': 0.10,    # $0.10 beyond PDH/PDL for bias
    'retest_zone': 0.50,       # Look for setups within $0.50 of levels
    
    # Risk management configuration
    'risk_management': {
        'position_risk_pct': 5.0,         # 5% risk per position
        'daily_loss_limit_pct': 10.0,      # 10% daily loss limit (2 x 5% losses)
        'consecutive_loss_limit': 2,       # Stop after 2 consecutive losses
        'max_positions': 1,                # Max 1 position at a time
        'account_size_tiers': {            # Position sizing tiers
            0: 1,        # Under $25k: 1 contract
            25000: 2,    # $25k+: 2 contracts
            50000: 3,    # $50k+: 3 contracts
            100000: 5,   # $100k+: 5 contracts
        }
    },
    
    # R-based exit targets
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