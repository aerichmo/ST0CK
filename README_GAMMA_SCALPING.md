# ST0CK Gamma Scalping Implementation

This is a complete implementation of Alpaca's gamma scalping strategy integrated with ST0CK infrastructure.

## Features

- **True Options Trading**: Trades ATM straddles (call + put at same strike)
- **Delta Hedging**: Automatically hedges portfolio delta with stock trades
- **Greeks Calculation**: Uses QuantLib for accurate Delta, Gamma, Theta
- **Multiple Modes**: Simple scalping, volatility-based, or true gamma scalping
- **Risk Management**: Position limits, daily loss limits, and more

## Installation

1. Install base requirements:
```bash
pip install -r requirements.txt
```

2. Install gamma scalping dependencies:
```bash
pip install -r requirements_gamma.txt
```

3. Set environment variables:
```bash
export ST0CKAKEY="your-alpaca-api-key"
export ST0CKASECRET="your-alpaca-secret"
export DATABASE_URL="postgresql://..."  # Optional
export REDIS_URL="redis://..."         # Optional
```

## Usage

### Method 1: Via Main Unified Launcher
```bash
# Run true gamma scalping with options
python main_unified.py st0cka_options

# Run simpler volatility-based version
python main_unified.py st0cka_gamma
```

### Method 2: Direct Gamma Scalping
```bash
# Run with default settings
python launch_gamma_scalping.py

# Run 0DTE only (maximum gamma)
python launch_gamma_scalping.py --min-dte 0 --max-dte 0

# Resume with existing positions
python launch_gamma_scalping.py --mode resume

# Adjust delta threshold
python launch_gamma_scalping.py --delta-threshold 10
```

### Method 3: Using Shell Script
```bash
./start_gamma_scalping.sh
```

## Strategies Available

1. **st0cka** - Original simple $0.01 scalping
2. **st0cka_gamma** - Volatility-based scalping (stocks only)
3. **st0cka_options** - True gamma scalping with options

## Configuration

Edit `gamma-scalping-fork/config_st0ck.py` to adjust:
- Delta hedging threshold
- DTE range for options
- Position size limits
- Risk parameters

## Components

- **OptionsBroker**: Extended broker for options orders
- **GammaScalpingManager**: Orchestrates all components
- **DeltaEngine**: Calculates portfolio Greeks
- **MarketDataManager**: Real-time data streaming
- **PositionManager**: Executes trades and tracks P&L

## Risk Warning

⚠️ **IMPORTANT**: This strategy trades options which can result in significant losses. Always test in paper trading mode first!

## Monitoring

- Logs: `logs/gamma_scalping_*.log`
- Trade logs: `logs/gamma_trades/`
- Performance updates every 60 seconds
- Automatic shutdown on daily loss limit

## Troubleshooting

1. **QuantLib not found**: Install with `pip install QuantLib-Python`
2. **Options data missing**: Ensure Alpaca account has options trading enabled
3. **Insufficient buying power**: Reduce `MAX_CONTRACTS` in config

## Architecture

```
ST0CK Infrastructure
    ↓
GammaScalpingManager
    ├── OptionsBroker (handles orders)
    ├── MarketDataManager (streaming data)
    ├── DeltaEngine (Greeks calculation)
    ├── TradingStrategy (hedging logic)
    └── PositionManager (execution)
```

The implementation leverages Alpaca's production-grade gamma scalping with ST0CK's infrastructure for logging, database, and monitoring.