"""
Configuration for ST0CKG - Battle Lines Strategy
"""
from datetime import time

def validate_config(config):
    """Validate ST0CKG configuration"""
    # Risk parameters
    assert 0 < config['risk_per_trade'] <= 1.0, f"risk_per_trade must be between 0 and 1, got {config['risk_per_trade']}"
    assert 0 < config['max_daily_loss'] <= 1.0, f"max_daily_loss must be between 0 and 1, got {config['max_daily_loss']}"
    assert config['max_wins_per_day'] > 0, f"max_wins_per_day must be positive, got {config['max_wins_per_day']}"
    assert config['max_losses_per_day'] > 0, f"max_losses_per_day must be positive, got {config['max_losses_per_day']}"
    
    # Position sizing
    assert config['max_position_size'] > 0, f"max_position_size must be positive, got {config['max_position_size']}"
    assert config['default_stop_distance'] > 0, f"default_stop_distance must be positive, got {config['default_stop_distance']}"
    
    # Option parameters
    opts = config['options']
    assert 0 < opts['target_delta'] <= 1.0, f"target_delta must be between 0 and 1, got {opts['target_delta']}"
    assert opts['delta_tolerance'] > 0, f"delta_tolerance must be positive, got {opts['delta_tolerance']}"
    assert opts['max_dte'] >= 0, f"max_dte must be non-negative, got {opts['max_dte']}"
    assert opts['min_volume'] >= 0, f"min_volume must be non-negative, got {opts['min_volume']}"
    assert opts['max_spread'] > 0, f"max_spread must be positive, got {opts['max_spread']}"
    assert opts['max_spread_pct'] > 0, f"max_spread_pct must be positive, got {opts['max_spread_pct']}"
    
    # Risk management
    rm = config['risk_management']
    assert 0 < rm['position_risk_pct'] <= 100, f"position_risk_pct must be between 0 and 100, got {rm['position_risk_pct']}"
    assert 0 < rm['daily_loss_limit_pct'] <= 100, f"daily_loss_limit_pct must be between 0 and 100, got {rm['daily_loss_limit_pct']}"
    assert rm['consecutive_loss_limit'] > 0, f"consecutive_loss_limit must be positive, got {rm['consecutive_loss_limit']}"
    assert rm['max_positions'] > 0, f"max_positions must be positive, got {rm['max_positions']}"
    
    # Time windows
    assert config['trading_window']['start'] < config['trading_window']['end'], "trading window start must be before end"
    
    # Capital
    assert config['capital'] > 0, f"capital must be positive, got {config['capital']}"
    
    # R-based targets
    assert config['breakeven_r'] > 0, f"breakeven_r must be positive, got {config['breakeven_r']}"
    assert config['scale_out_r'] > config['breakeven_r'], f"scale_out_r must be greater than breakeven_r"
    assert config['final_target_r'] > config['scale_out_r'], f"final_target_r must be greater than scale_out_r"
    
    return True

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

# Validate config on import
validate_config(ST0CKG_CONFIG)