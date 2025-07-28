# ST0CK Enhanced Configuration
# Adapted from Alpaca's gamma scalping for ST0CK strategies

import os
from dotenv import load_dotenv

# --- Load Environment Variables ---
load_dotenv(override=True)

# Alpaca API credentials and trading mode
IS_PAPER_TRADING = os.getenv("IS_PAPER_TRADING", "true").lower() == "true"

# Support multiple bot configurations
ST0CKA_API_KEY = os.getenv("ST0CKAKEY", os.getenv("TRADING_API_KEY"))
ST0CKA_API_SECRET = os.getenv("ST0CKASECRET", os.getenv("TRADING_API_SECRET"))
ST0CKG_API_KEY = os.getenv("ST0CKGKEY", os.getenv("TRADING_API_KEY"))
ST0CKG_API_SECRET = os.getenv("ST0CKGSECRET", os.getenv("TRADING_API_SECRET"))

# Active strategy configuration
ACTIVE_STRATEGY = os.getenv("ACTIVE_STRATEGY", "ST0CKA_ENHANCED")  # ST0CKA_ENHANCED, ST0CKG_ENHANCED, GAMMA_SCALPING

# --- Asset Configuration ---
HEDGING_ASSET = "SPY"  # Primary asset for all ST0CK strategies
TRADE_LOG_DIR = "trades"

# --- Strategy Selection ---
# Strategy modes: 'st0cka', 'st0ckg', 'gamma_scalping', 'hybrid'
STRATEGY_MODE = os.getenv("STRATEGY_MODE", "st0cka")

# --- Initialization Mode ---
# 'init': Start fresh (liquidate existing positions)
# 'resume': Continue with existing positions
INITIALIZATION_MODE = os.getenv("INITIALIZATION_MODE", "init")

# --- ST0CKA Strategy Parameters ---
ST0CKA_CONFIG = {
    "enabled": True,
    "profit_target": 0.01,  # $0.01 per share
    "position_size_min": 1,  # Minimum shares
    "position_size_max": 3,  # Maximum shares (volatility-based)
    "buy_window_start": "09:30",
    "buy_window_end": "10:00",
    "sell_window_start": "10:00",
    "sell_window_end": "11:00",
    "use_volatility_sizing": True,
    "use_mean_reversion": False,
    "entry_interval_seconds": 30,  # For advanced mode
}

# --- ST0CKG Strategy Parameters ---
ST0CKG_CONFIG = {
    "enabled": False,
    "risk_per_trade": 0.01,  # 1% risk
    "trading_window_start": "09:40",
    "trading_window_end": "10:30",
    "max_positions": 2,
    "signal_weights": {
        "GAMMA_SQUEEZE": 8.5,
        "VWAP_RECLAIM": 7.0,
        "OPENING_DRIVE": 7.5,
        "LIQUIDITY_VACUUM": 6.5,
        "OPTIONS_PIN": 6.0,
        "DARK_POOL_FLOW": 5.5,
        "DEALER_GAMMA": 9.0  # New signal from gamma scalping
    },
    "use_options": True,  # Enable options trading for ST0CKG
}

# --- Gamma Scalping Parameters (Original) ---
GAMMA_SCALPING_CONFIG = {
    "enabled": False,
    "delta_threshold": 2.0,
    "strategy_multiplier": 1,
    "min_expiration_days": 30,
    "max_expiration_days": 90,
    "min_open_interest": 100,
    "theta_weight": 1.0,
    "default_risk_free_rate": 0.05,
}

# --- Volatility Configuration ---
VOLATILITY_CONFIG = {
    "lookback_period": 20,  # Days for historical volatility
    "low_vol_threshold": 0.10,  # 10% annualized
    "high_vol_threshold": 0.25,  # 25% annualized
    "use_vix": True,
    "vix_low": 15,
    "vix_high": 25,
}

# --- Market State Trigger Parameters ---
# More sensitive for ST0CK strategies
PRICE_CHANGE_THRESHOLD = 0.02  # $0.02 for SPY (more sensitive than original $0.05)
HEARTBEAT_TRIGGER_SECONDS = 2.0  # Faster heartbeat for scalping

# --- Mean Reversion Parameters ---
MEAN_REVERSION_CONFIG = {
    "enabled": True,
    "vwap_deviation_threshold": 0.005,  # 0.5% from VWAP
    "bollinger_bands_period": 20,
    "bollinger_bands_std": 2.0,
    "rsi_period": 14,
    "rsi_oversold": 30,
    "rsi_overbought": 70,
}

# --- Risk Management ---
RISK_MANAGEMENT = {
    "max_daily_loss": -500.0,
    "max_consecutive_losses": 3,
    "max_portfolio_heat": 0.06,  # 6% of portfolio
    "max_position_size": 0.25,  # 25% of portfolio
    "use_kelly_criterion": False,
    "kelly_fraction": 0.25,  # Use 1/4 Kelly
}

# --- Position Manager Parameters ---
TRADE_COMMAND_TTL_SECONDS = 3.0  # Faster execution for scalping
OPTIONS_CONTRACT_MULTIPLIER = 100

# --- Data Quality Management ---
DATA_QUALITY_CONFIG = {
    "use_quality_checks": True,
    "stale_quote_threshold_seconds": 5,
    "max_spread_percentage": 0.002,  # 0.2% for SPY
    "min_volume_threshold": 1000000,  # 1M shares
}

# --- Performance Tracking ---
PERFORMANCE_CONFIG = {
    "track_metrics": True,
    "metrics_interval_seconds": 60,
    "export_trades": True,
    "export_format": "csv",  # csv or json
}

# --- Hybrid Mode Configuration ---
HYBRID_CONFIG = {
    "enabled": False,
    "volatility_threshold_for_gamma": 0.20,  # Switch to gamma scalping above 20% vol
    "market_regime_detection": True,
    "regime_lookback_days": 30,
}

# --- Logging Configuration ---
LOG_FORMAT = "%(asctime)s - %(levelname)s - %(name)s - %(message)s"
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# --- Database Configuration ---
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///trading_multi.db")
REDIS_URL = os.getenv("REDIS_URL", None)

# --- Web Dashboard ---
DASHBOARD_PORT = int(os.getenv("PORT", 10000))
DASHBOARD_ENABLED = os.getenv("DASHBOARD_ENABLED", "true").lower() == "true"

# --- Helper Functions ---
def get_active_config():
    """Return configuration for the active strategy"""
    if STRATEGY_MODE == "st0cka":
        return ST0CKA_CONFIG
    elif STRATEGY_MODE == "st0ckg":
        return ST0CKG_CONFIG
    elif STRATEGY_MODE == "gamma_scalping":
        return GAMMA_SCALPING_CONFIG
    else:
        return HYBRID_CONFIG

def get_api_credentials():
    """Return API credentials based on active strategy"""
    if STRATEGY_MODE in ["st0cka", "ST0CKA_ENHANCED"]:
        return ST0CKA_API_KEY, ST0CKA_API_SECRET
    elif STRATEGY_MODE in ["st0ckg", "ST0CKG_ENHANCED"]:
        return ST0CKG_API_KEY, ST0CKG_API_SECRET
    else:
        # Default to ST0CKA credentials
        return ST0CKA_API_KEY, ST0CKA_API_SECRET