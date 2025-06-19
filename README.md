# ST0CK - SPY Options Trading Bot

A specialized automated trading system focused exclusively on SPY options during the opening range breakout period (9:40-10:30 ET).

## Overview

ST0CK implements a systematic opening range breakout strategy on SPY with disciplined risk management and precise option selection based on delta targeting.

### Key Features

- **SPY-Only Focus**: Specialized for trading SPY options with optimized parameters
- **Opening Range Breakout**: Trades breakouts of the 9:30-9:40 ET opening range
- **Delta-Targeted Options**: Selects ~0.40 delta options with liquidity validation
- **Dynamic Risk-Free Rate**: Fetches current Treasury rates for accurate Greeks calculation
- **OCO Exit Strategy**: Automated profit targets and stop losses
- **Risk Management**: Position sizing, daily loss limits, consecutive loss protection
- **Paper Trading Mode**: Realistic market simulation with bid-ask spreads and slippage

## Trading Strategy

### Entry Criteria
- Breakout above/below opening range (9:30-9:40 ET)
- ATR-based breakout confirmation (0.15x ATR threshold)
- Volume surge confirmation (1.5x average)
- EMA trend alignment (8/21 EMA)

### Exit Strategy
- Stop Loss: -1R (100% of risk)
- Target 1: +1.5R (50% position)
- Target 2: +3R (remaining 50%)
- Time Stop: 60 minutes maximum hold

### Risk Management
- 10% account risk per trade
- 20% daily loss limit
- 2 consecutive loss limit
- Single position maximum

## Technical Improvements

### Data Reliability
- Primary data source with automatic fallback mechanisms
- Retry logic for API calls
- Data caching to reduce API load
- Parallel data fetching where applicable

### Realistic Paper Trading
- Dynamic bid-ask spread calculation based on volatility and volume
- Realistic slippage modeling
- Tiered commission structure
- Market impact simulation

### Performance Optimizations
- Batched database writes with background flushing
- Connection pooling for database
- Smart caching for frequently accessed data
- Efficient parallel processing

### SPY-Specific Enhancements
- Support for 0DTE options during market hours
- Higher liquidity thresholds
- Tighter spread requirements
- Dynamic risk-free rate fetching from Treasury yields

## Installation

1. Clone the repository:
```bash
git clone https://github.com/aerichmo/ST0CK.git
cd ST0CK
```

2. Create virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Set up PostgreSQL database:
```bash
createdb st0ck_trading
```

5. Configure environment variables:
```bash
cp .env.example .env
# Edit .env with your settings
```

## Usage

### Paper Trading Mode
```bash
python main.py --paper
```

### With Custom Config
```bash
python main.py --paper --config config/custom_config.py
```

### Monitor Only Mode
```bash
python main.py --monitor
```

## Configuration

Key configuration parameters in `config/trading_config.py`:

- `target_delta`: 0.40 (option delta target)
- `position_risk_pct`: 0.10 (10% risk per trade)
- `daily_loss_limit_pct`: 0.20 (20% daily loss limit)
- `min_volume`: 100 (minimum option volume)
- `min_open_interest`: 500 (minimum OI for SPY)
- `max_spread_pct`: 0.10 (maximum 10% bid-ask spread)

## Architecture

- **Modular Design**: Clean separation of concerns
- **Event-Driven**: Scheduled tasks and real-time monitoring
- **Database-Backed**: PostgreSQL for trade logging and analytics
- **Thread-Safe**: Proper locking for concurrent operations
- **Fault Tolerant**: Comprehensive error handling and recovery

## Monitoring

The system provides comprehensive logging and monitoring:

- Real-time position tracking
- P&L monitoring
- Risk metrics tracking
- Daily performance reports
- Trade execution logs

## Safety Features

- Paper trading mode for testing
- Automatic position closure at EOD
- Risk limit enforcement
- Consecutive loss protection
- Time-based position stops

## Contributing

This is a specialized trading system. Any modifications should maintain the core SPY-only focus and risk management principles.

## Disclaimer

This software is for educational purposes only. Trading options involves substantial risk of loss. Past performance does not guarantee future results. Always test thoroughly in paper trading mode before considering live trading.