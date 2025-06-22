# ST0CK - Advanced SPY Options Trading System

High-performance automated trading platform for SPY options using institutional-grade analytics and Alpaca Markets API.

## 🚀 Active Strategy: APEX

### ✅ APEX - Advanced Pattern EXecution
- **Strategy**: Multi-signal pattern recognition with 6 entry types
- **Sessions**: 
  - Morning: 9:30-11:00 AM ET (40-45 delta options)
  - Midday: 1:00-2:30 PM ET (30-35 delta options)
  - Power Hour: 3:00-3:45 PM ET (45-50 delta options)
- **Capital**: $5,000
- **Risk**: Dynamic 2-6% per trade (aggressive for small capital)
- **Target**: 25-40% monthly returns

## 🎯 Quick Start

### 1. Set Environment Variables
```bash
export STOCKG_KEY=your-alpaca-key
export ST0CKG_SECRET=your-alpaca-secret
export APEX_TRADING_CAPITAL=5000
export ALPACA_BASE_URL=https://paper-api.alpaca.markets  # Use paper for testing
export DATABASE_URL=sqlite:///trading_multi.db  # Or PostgreSQL
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Run APEX
```bash
python main_multi.py apex
```

## 🏗️ Architecture

```
ST0CK/
├── bots/
│   └── st0ckg/           # APEX strategy (renamed from ST0CKG)
│       ├── config.py     # APEX configuration
│       └── strategy.py   # APEXStrategy implementation
├── src/
│   ├── unified_market_data.py      # Alpaca data with caching
│   ├── alpaca_broker.py           # Alpaca order execution
│   ├── apex_engine.py             # APEX trading engine
│   ├── market_microstructure.py   # Volume profile, VWAP, GEX
│   ├── apex_signals.py            # Signal detection system
│   └── apex_options_selector.py   # Smart option selection
└── main_multi.py                  # Launcher
```

## 📊 APEX Signal Types

1. **Gamma Squeeze** - Market maker positioning imbalances
2. **VWAP Reclaim** - Mean reversion to volume-weighted price
3. **Opening Drive** - Momentum continuation from open
4. **Liquidity Vacuum** - Rapid moves through thin order books
5. **Options Pin** - Price magnetization to high OI strikes
6. **Dark Pool Flow** - Institutional directional bias

## ⚡ Performance Features

- **100% Alpaca API** - All market data and execution via Alpaca
- **Sub-second execution** - Optimized for 0DTE options
- **Smart caching** - 5s quotes, 60s options chains
- **Async architecture** - Non-blocking I/O operations
- **Minimal dependencies** - Lean codebase for speed

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

## 📊 Monitoring

- Real-time console logging
- Trade execution in logs/
- Performance metrics tracked

## 🎯 Trading Schedule

**Morning Session** (9:30-11:00 AM ET)
- Focus: Opening momentum, gamma squeezes
- Delta: 40-45 (aggressive)

**Midday Session** (1:00-2:30 PM ET)  
- Focus: VWAP reclaims, reversals
- Delta: 30-35 (conservative)

**Power Hour** (3:00-3:45 PM ET)
- Focus: EOD momentum, gamma unwind
- Delta: 45-50 (aggressive)

## ⚠️ Important Notes

- **Paper trading first** - Test with Alpaca paper account
- **0DTE options risk** - Can lose 100% rapidly
- **Requires monitoring** - Not set-and-forget
- **Options approval needed** - Alpaca account must have options enabled

## 🔧 Monitoring

```bash
# View logs
tail -f logs/multi_bot_$(date +%Y%m%d).log

# Check positions
python main_multi.py --list
```

## 📄 License

Proprietary - All rights reserved