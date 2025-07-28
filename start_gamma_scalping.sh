#!/bin/bash
# Start ST0CKA with gamma scalping strategy

echo "Starting ST0CKA Gamma Scalping..."
echo "This will use Alpaca's gamma scalping infrastructure"
echo ""

# Export ST0CK credentials for gamma scalping
export TRADING_API_KEY="${ST0CKAKEY}"
export TRADING_API_SECRET="${ST0CKASECRET}"
export IS_PAPER_TRADING="true"

# Configure for aggressive scalping
export HEDGING_DELTA_THRESHOLD="5.0"
export STRATEGY_MULTIPLIER="2"
export MIN_DAYS_TO_EXPIRATION="0"
export MAX_DAYS_TO_EXPIRATION="7"

# Change to gamma scalping directory
cd "$(dirname "$0")/gamma-scalping-fork"

# Run with ST0CK preferences
echo "Configuration:"
echo "- Trading SPY options (0-7 DTE)"
echo "- Delta threshold: 5.0"
echo "- Position multiplier: 2x"
echo "- Mode: Paper trading"
echo ""

# Start gamma scalping
python main.py --symbol SPY --track_opts