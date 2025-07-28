# ST0CK - Automated Trading System

High-performance automated trading platform for stocks and options using Alpaca Markets API.

## 🚀 Active Strategy: ST0CKG

### ✅ ST0CKG - Advanced Pattern Recognition (SPY Only)
- **Strategy**: Multi-signal pattern recognition with 6 entry types
- **Instrument**: SPY options only (0-DTE)
- **Sessions** (Optimized for volatility): 
  - Morning: 9:30-11:00 AM ET (40-45 delta options) - Highest volatility
  - ~~Midday: 1:00-2:30 PM ET~~ - REMOVED (low volatility period)
  - Power Hour: 3:00-3:45 PM ET (45-50 delta options) - Second volatility spike
- **Capital**: $5,000
- **Risk**: Dynamic 2-6% per trade (aggressive for small capital)
- **Target**: 25-40% monthly returns

## 🎯 Quick Start

For detailed setup instructions, see [SETUP_GUIDE.md](SETUP_GUIDE.md).

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure environment (.env file)
cp .env.example .env
# Edit .env with your API credentials

# 3. Run a bot
python main_unified.py
```

## 🏗️ Architecture

```
ST0CK/
├── bots/                          # Trading strategies
│   ├── st0ckg/                   # ST0CKG options strategy
│   └── st0cka/                   # Simple stock strategy
├── src/
│   ├── unified_engine.py         # Unified trading engine
│   ├── unified_market_data.py    # Market data with caching & pooling
│   ├── connection_pool.py        # API connection management
│   ├── alpaca_broker.py          # Order execution
│   ├── unified_database.py       # Unified database manager
│   └── risk_manager.py           # Risk management
├── public/                       # Web dashboards
│   ├── index.html               # Performance dashboard
│   └── metrics.html             # System metrics
└── main_unified.py              # Unified launcher
```

## 📊 ST0CKG Signal Types

1. **Gamma Squeeze** - Market maker positioning imbalances
2. **VWAP Reclaim** - Mean reversion to volume-weighted price
3. **Opening Drive** - Momentum continuation from open
4. **Liquidity Vacuum** - Rapid moves through thin order books
5. **Options Pin** - Price magnetization to high OI strikes
6. **Dark Pool Flow** - Institutional directional bias

## ⚡ Performance Features

- **Connection Pooling** - Reuses API connections for 50% overhead reduction
- **Rate Limiting** - Prevents API throttling with intelligent request management
- **Multi-level Caching** - 5s quotes, 60s options, 5m historical data
- **Async Operations** - Concurrent API calls for 3-5x speed improvement
- **Database Batching** - Bulk operations for 20% performance gain
- **Real-time Metrics** - Monitor cache hit rates and connection pool usage

## 🔒 Risk Management

- **Capital-based sizing**: Higher risk for accounts under $10k
- **Dynamic adjustment** based on 7 factors
- **Multiple exit strategies** (stop loss, targets, time, trailing)
- **Session-based limits** and regime filters
- **Max daily loss**: $500
- **Max consecutive losses**: 3

## 📈 Expected Performance

Based on enhanced Graystone methodology:
- **Win Rate**: 55-65%
- **Average Winner**: 2.5R
- **Average Loser**: 1R
- **Monthly Return**: 25-40%
- **Daily Trades**: 5-7

## 📊 Monitoring & Dashboards

- **Performance Dashboard**: `http://localhost:10000/` - P&L tracking
- **Metrics Dashboard**: `http://localhost:10000/metrics` - System performance
- **Real-time Logs**: `tail -f logs/multi_bot_$(date +%Y%m%d).log`
- **API Endpoints**:
  - `/api/performance` - Trading performance data
  - `/api/metrics` - Cache & connection pool statistics
  - `/api/trades` - Recent trade history

## 🎯 Active Trading Strategies

### ST0CKG - Advanced Options Trading
- **Sessions**: Morning (9:30-11:00), Power Hour (3:00-3:45)
- **Signals**: 6 pattern types with weighted scoring
- **Risk**: Dynamic 2-6% per trade
- **Target**: 25-40% monthly returns

### ST0CKA - Simple Stock Trading
- **Sessions**: Morning (9:30-11:00), Power Hour (3:00-3:45)
- **Strategy**: Buy SPY, sell for $0.01 profit
- **Risk**: Fixed 1 share per trade
- **Target**: Consistent small gains
- **Updated**: Now trades during both high-volatility periods

## 📚 Documentation

- [Setup Guide](SETUP_GUIDE.md) - Detailed installation and configuration
- [Technical Documentation](TECHNICAL_DOCS.md) - Architecture and implementation details

## 🤝 Contributing

Contributions are welcome! Please read the technical documentation before submitting PRs.

## 📄 License

Proprietary - All rights reserved
