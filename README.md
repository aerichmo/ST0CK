# ST0CK - Multi-Bot SPY Options Trading System

A high-performance automated trading platform for SPY options, supporting multiple independent trading bots with isolated strategies and accounts.

## 🚀 Current Status

### ✅ ST0CKG - READY TO DEPLOY
- **Strategy**: Opening Range Breakout (9:40-10:30 AM ET)
- **Status**: Fully functional and independent
- **Capital**: $5,000
- **Can run WITHOUT ST0CKA**

### 🚧 ST0CKA - PENDING DEVELOPMENT
- **Strategy**: TBD (placeholder ready)
- **Status**: Infrastructure ready, strategy not implemented
- **Capital**: $10,000
- **Not blocking ST0CKG deployment**

## 🎯 Quick Start for ST0CKG

### 1. Set Environment Variables
```bash
export STOCKG_KEY=your-alpaca-key
export ST0CKG_SECRET=your-alpaca-secret
export ST0CKG_TRADING_CAPITAL=5000
export ALPACA_BASE_URL=https://api.alpaca.markets
export DATABASE_URL=postgresql://...
```

### 2. Run Database Migration
```bash
psql $DATABASE_URL < migrations/add_multi_bot_support.sql
```

### 3. Deploy ST0CKG
```bash
# Local testing
python main_multi.py st0ckg

# GitHub Actions (automatic at 9:25 AM ET)
# Push to main branch and it runs daily
```

## 🏗️ Architecture

```
ST0CK/
├── bots/
│   ├── st0ckg/          # ✅ Complete & Independent
│   │   ├── config.py    # Trading parameters
│   │   └── strategy.py  # Opening range breakout logic
│   └── st0cka/          # 🚧 Placeholder only
│       └── config.py    # Inactive configuration
├── src/
│   ├── unified_market_data.py  # Shared SPY data (cached)
│   ├── alpaca_broker.py        # Direct API integration
│   └── multi_bot_database.py   # Bot-aware persistence
└── main_multi.py               # Multi-bot launcher
```

## ✅ ST0CKG Independence Verification

ST0CKG is **100% independent** and can run without ST0CKA:

1. **Separate API Credentials** - Uses STOCKG_KEY/ST0CKG_SECRET
2. **Isolated Database Records** - All trades tagged with bot_id='st0ckg'
3. **Independent Risk Management** - Own capital and loss limits
4. **Separate GitHub Workflow** - `.github/workflows/st0ckg-trading.yml`
5. **No Shared State** - Only market data is cached/shared for efficiency

### Proof of Independence:
```python
# ST0CKG runs fine even if ST0CKA credentials are missing
# The launcher checks each bot individually:
if bot_id == 'st0ckg' and has_credentials:
    run_st0ckg()  # Runs independently
```

## 🔧 What's Needed for ST0CKA

To make ST0CKA functional, implement:

### 1. Strategy Implementation
Create `bots/st0cka/strategy.py`:
```python
from bots.base.strategy import BaseStrategy

class YourStrategyName(BaseStrategy):
    def check_entry_conditions(self, price, market_data):
        # Your strategy logic here
        pass
    
    def calculate_position_size(self, signal, balance, price):
        # Position sizing logic
        pass
    
    # ... other required methods
```

### 2. Update Configuration
Edit `bots/st0cka/config.py`:
- Set `'active': True`
- Define strategy parameters
- Set trading window

### 3. Create Trading Engine
Create `src/st0cka_engine.py` similar to st0ckg_engine.py

### 4. Add Credentials
```bash
export STOCKA_KEY=your-second-alpaca-key
export ST0CKA_SECRET=your-second-alpaca-secret
```

### 5. Enable Workflow
Update `.github/workflows/st0cka-trading.yml` schedule

## 🚀 Deployment Options

### GitHub Actions (Recommended)
1. Add secrets to repository
2. Push to main branch
3. ST0CKG runs automatically at 9:25 AM ET

### Manual Deployment
```bash
# Deploy only ST0CKG
python main_multi.py st0ckg

# List all bots
python main_multi.py --list
```

### Cloud Deployment
- Each bot can be deployed separately
- Different servers/regions possible
- No coordination required

## 📊 Dashboard

Multi-bot dashboard at https://st0ck.onrender.com shows:
- Combined P&L across all bots
- Side-by-side performance comparison
- Real-time trade log
- Individual bot metrics

**Note**: Dashboard shows ST0CKA as "INACTIVE" until implemented

## 🔒 Security

- Each bot uses separate Alpaca account/API keys
- Database access controlled by bot_id
- No cross-bot data access
- Independent risk limits

## 📈 Performance

- **Shared**: Market data (SPY quotes/options cached)
- **Isolated**: Everything else (orders, positions, risk)
- **Fast**: Sub-second execution per bot
- **Scalable**: Add more bots without affecting others

## 🎯 Summary

**ST0CKG is ready to trade NOW**. It doesn't need ST0CKA to function. Deploy it today and add ST0CKA whenever you're ready with a strategy.

The system is designed for complete bot independence - each bot is a self-contained trading unit that happens to share infrastructure for efficiency.