# ST0CK - Multi-Bot SPY Options Trading System

A multi-bot trading platform for SPY options, supporting multiple strategies and Alpaca accounts with complete isolation and performance tracking.

## Overview

ST0CK is a modular trading system that allows running multiple trading bots simultaneously, each with their own:
- Trading strategy and parameters
- Alpaca account credentials
- Risk limits and capital allocation
- Performance tracking and metrics
- Execution schedule

### Active Bots

#### ST0CKG - Opening Range Breakout
- **Strategy**: Trades SPY options on opening range breakouts
- **Window**: 9:40-10:30 AM ET
- **Capital**: $5,000 (configurable)
- **Status**: Active

#### ST0CKA - [Strategy TBD]
- **Strategy**: To be implemented
- **Window**: TBD
- **Capital**: $10,000 (configurable)
- **Status**: Inactive (placeholder)

## Quick Start

### 1. Database Setup
```bash
# Apply multi-bot migration
psql $DATABASE_URL < migrations/add_multi_bot_support.sql
```

### 2. Environment Variables
```bash
# ST0CKG Bot
export STOCKG_KEY=your-key
export ST0CKG_SECRET=your-secret
export ST0CKG_TRADING_CAPITAL=5000

# ST0CKA Bot (when ready)
export STOCKA_KEY=your-key
export ST0CKA_SECRET=your-secret
export ST0CKA_TRADING_CAPITAL=10000

# Shared
export ALPACA_BASE_URL=https://api.alpaca.markets
export DATABASE_URL=postgresql://...
```

### 3. Run a Bot
```bash
# Run ST0CKG
python main_multi.py st0ckg

# List all bots
python main_multi.py --list
```

## Architecture

### Directory Structure
```
ST0CK/
├── bots/
│   ├── base/          # Abstract base classes
│   ├── st0ckg/        # Opening Range Breakout
│   └── st0cka/        # Future strategy
├── src/
│   ├── shared/        # Shared market data
│   └── ...           # Core components
└── main_multi.py      # Multi-bot launcher
```

### Key Features
- **Complete Isolation**: Each bot operates independently
- **Shared Market Data**: Efficient caching across bots
- **Performance Tracking**: Compare strategies side-by-side
- **Flexible Deployment**: Separate GitHub Actions per bot
- **Easy Scaling**: Add new bots without affecting existing ones

## ST0CKG Strategy Details

### Opening Range Breakout
- **Range**: 9:30-9:40 AM ET
- **Entry**: Break above/below range with volume confirmation
- **Options**: 0-1 DTE, ~30 delta
- **Exits**: ATR-based targets, time stop at 10:25 AM

### Risk Management
- 2% risk per trade
- $500 daily loss limit
- 3 consecutive loss limit
- Maximum 2 positions

## Deployment

### GitHub Actions
Each bot has its own workflow:
- `.github/workflows/st0ckg-trading.yml` - Runs at 9:25 AM ET
- `.github/workflows/st0cka-trading.yml` - Manual trigger

### Required Secrets
```
DATABASE_URL
ALPACA_BASE_URL
STOCKG_KEY
ST0CKG_SECRET
ST0CKG_TRADING_CAPITAL
STOCKA_KEY
ST0CKA_SECRET
ST0CKA_TRADING_CAPITAL
EMAIL_USERNAME
EMAIL_PASSWORD
WEBHOOK_URL
```

## Monitoring

### Performance Queries
```sql
-- Bot performance summary
SELECT bot_id, COUNT(*) as trades, SUM(realized_pnl) as pnl 
FROM trades 
WHERE status = 'CLOSED' 
GROUP BY bot_id;

-- Today's trades by bot
SELECT * FROM trades 
WHERE bot_id = 'st0ckg' 
AND DATE(entry_time) = CURRENT_DATE;
```

### Bot Status
```python
python main_multi.py --list
```

## Adding a New Bot

1. Create bot directory: `bots/st0ckx/`
2. Implement strategy inheriting from `BaseStrategy`
3. Create configuration in `config.py`
4. Add GitHub Actions workflow
5. Set environment variables
6. Register in database

See `MULTI_BOT_SETUP.md` for detailed instructions.

## Performance

- **Shared market data**: Single API connection for all bots
- **Batched database writes**: Optimized for high-frequency updates
- **Pre-fetched options**: Entire chain loaded at session start
- **Sub-second execution**: Direct Alpaca API integration

## Support

- Logs: `logs/multi_bot_YYYYMMDD.log`
- Database: Bot-specific tables with `bot_id`
- Monitoring: Separate metrics per bot