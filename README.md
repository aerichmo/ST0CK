# ST0CK - SPY Options Trading Bot

A specialized automated trading system focused exclusively on SPY options during the opening range breakout period (9:40-10:30 ET).

## Overview

ST0CK implements a systematic opening range breakout strategy on SPY with disciplined risk management and precise option selection based on delta targeting. The system is designed to run autonomously with cloud deployment support and comprehensive monitoring.

### Key Features

- **SPY-Only Focus**: Specialized for trading SPY options with optimized parameters
- **Opening Range Breakout**: Trades breakouts of the 9:30-9:40 ET opening range
- **Delta-Targeted Options**: Selects ~0.40 delta options with liquidity validation
- **Dynamic Risk-Free Rate**: Fetches current Treasury rates for accurate Greeks calculation
- **OCO Exit Strategy**: Automated profit targets and stop losses
- **Risk Management**: Position sizing, daily loss limits, consecutive loss protection
- **Paper Trading Mode**: Realistic market simulation with bid-ask spreads and slippage
- **Cloud-Ready**: Supports GitHub Actions, AWS, GCP, and other cloud platforms
- **Database Integration**: PostgreSQL for trade logging and performance analytics
- **Real-time Monitoring**: Webhook support for Discord/Slack notifications
- **Alpaca MCP Integration**: Simplified API calls through Model Context Protocol server

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

### Prerequisites
- Python 3.8 or higher
- PostgreSQL database (local or cloud)
- Git

### Local Setup

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
# Local database
createdb st0ck_trading

# Or use a free cloud database:
# - Supabase: https://supabase.com (500MB free)
# - Neon: https://neon.tech (3GB free)
```

5. Configure environment variables:
```bash
# Create .env file with your settings
cat > .env << EOL
DATABASE_URL=postgresql://localhost/st0ck_trading
ALPACA_API_KEY=your_paper_api_key
ALPACA_API_SECRET=your_paper_api_secret
ALPACA_BASE_URL=https://paper-api.alpaca.markets
WEBHOOK_URL=your_discord_webhook_url
EOL
```

## Usage

### Quick Start with Alpaca MCP (Default)
```bash
# One-time setup
./setup_mcp.sh

# Run with default MCP broker
python main.py --mode paper --capital 100000
```

### Using Built-in Paper Trading (Offline Testing)
```bash
# Use built-in paper broker for offline testing
python main.py --broker paper --capital 100000
```

### With Custom Database
```bash
python main.py --mode paper --db "postgresql://user:pass@host:5432/dbname"
```

### Command-Line Options
- `--mode`: Trading mode (`paper` or `live`, default: `paper`)
- `--capital`: Initial trading capital (default: `100000`)
- `--db`: Database connection string (default: `postgresql://localhost/options_scalper`)
- `--broker`: Broker implementation (`mcp` or `paper`, default: `mcp`)

## Configuration

Key configuration parameters in `config/trading_config.py`:

- `target_delta`: 0.40 (option delta target)
- `position_risk_pct`: 0.10 (10% risk per trade)
- `daily_loss_limit_pct`: 0.20 (20% daily loss limit)
- `min_volume`: 100 (minimum option volume)
- `min_open_interest`: 500 (minimum OI for SPY)
- `max_spread_pct`: 0.10 (maximum 10% bid-ask spread)

## Architecture

### Core Components
- **Trading Engine** (`src/trading_engine.py`): Main orchestration and scheduling
- **Market Data Provider** (`src/market_data.py`): Real-time price and options data
- **Trend Filter** (`src/trend_filter.py`): EMA-based trend detection
- **Options Selector** (`src/options_selector.py`): Delta-targeted option selection
- **Risk Manager** (`src/risk_manager.py`): Position sizing and risk limits
- **Exit Manager** (`src/exit_manager.py`): OCO order management
- **Database Manager** (`src/database.py`): Trade logging and analytics
- **Broker Interface** (`src/broker_interface.py`): Paper/live trading abstraction

### Design Principles
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

## Cloud Deployment

### GitHub Actions (Recommended - Free)
The repository includes a GitHub Actions workflow for automated trading:

1. Fork or push to your GitHub repository
2. Add secrets in Settings → Secrets → Actions
3. Enable GitHub Actions
4. Bot runs automatically at 9:25 AM ET on weekdays

See `SETUP.md` for detailed deployment instructions.

### Alternative Deployment Options
- **Railway**: One-click deploy with free PostgreSQL
- **Google Cloud Run**: Serverless with Cloud Scheduler
- **AWS Lambda**: Event-driven serverless execution
- **Fly.io**: Modern PaaS with global deployment

See `cloud-deployment.md` for platform-specific guides.

## Development

### Running Tests
```bash
pytest tests/
```

### Code Structure
```
ST0CK/
├── config/           # Trading configuration
├── src/             # Core trading modules
├── logs/            # Trading logs
├── .github/         # GitHub Actions workflows
└── docs/            # Additional documentation
```

## Contributing

This is a specialized trading system. Any modifications should maintain the core SPY-only focus and risk management principles.

## Disclaimer

This software is for educational purposes only. Trading options involves substantial risk of loss. Past performance does not guarantee future results. Always test thoroughly in paper trading mode before considering live trading.

## License

MIT License - See LICENSE file for details