# Options Scalping Trading Engine

A fully automated options scalping system that trades SPY, QQQ, and high-liquidity gapping stocks during the 9:40-10:30 ET window.

## Strategy Overview

- **Universe**: SPY, QQQ + 5 stocks gapping ≥±0.75% with >$5B market cap
- **Active Window**: 9:40-10:30 ET only
- **Entry**: Opening range breakout with trend confirmation (EMA 8/21)
- **Options**: Weekly expiry, ~0.40 delta
- **Risk**: 1% per trade, -3% daily stop
- **Exits**: OCO orders with -1R stop, +1.5R (50%), +3R targets

## Installation

```bash
cd "/Users/alecrichmond/Library/Mobile Documents/com~apple~CloudDocs/st0ck/options-scalper"
pip install -r requirements.txt
```

## Configuration

1. Copy `.env.example` to `.env` and configure:
   - Database credentials
   - Broker API keys (for live trading)
   - Alert settings

2. Set up PostgreSQL database:
```sql
CREATE DATABASE options_scalper;
```

## Usage

### Paper Trading Mode (Default)
```bash
python main.py --mode paper --capital 100000
```

### With Custom Database
```bash
python main.py --db postgresql://user:pass@localhost/dbname
```

## Project Structure

```
options-scalper/
├── config/
│   └── trading_config.py      # Trading parameters
├── src/
│   ├── market_data.py         # Market data fetching
│   ├── trend_filter.py        # EMA trend analysis
│   ├── options_selector.py    # Option contract selection
│   ├── risk_manager.py        # Position sizing & risk
│   ├── exit_manager.py        # OCO order management
│   ├── broker_interface.py    # Broker integration
│   ├── database.py            # Trade logging
│   ├── monitoring.py          # Alerts & monitoring
│   └── trading_engine.py      # Main engine
├── logs/                      # Trading logs
├── main.py                    # Entry point
└── requirements.txt          # Dependencies
```

## Risk Controls

- **Position Risk**: 10% of account per trade
- **Daily Loss Limit**: -20% automatic shutdown
- **Consecutive Losses**: 2 losses = trading disabled
- **Time Stop**: 60-minute maximum hold time
- **Max Positions**: 5 concurrent positions

## Database Schema

The system logs all trades, executions, and risk metrics to PostgreSQL:
- `trades`: Complete trade records with entry/exit
- `execution_logs`: Detailed fill information
- `risk_metrics`: Real-time risk tracking

## Monitoring

The system includes:
- Real-time P&L tracking
- Risk limit monitoring
- Email/webhook alerts for critical events
- Daily performance summaries
- Expectancy reports

## Important Notes

1. **Paper Trading Only**: Currently configured for paper trading. Live broker integration requires additional setup.

2. **Market Data**: Uses Yahoo Finance for data. Consider upgrading to professional data feeds for production.

3. **Options Liquidity**: The system validates option liquidity before trading but slippage may still occur.

4. **Risk Management**: Never override the risk controls. The system will automatically disable trading when limits are hit.

## Compliance

This system implements strict algorithmic trading with no discretionary overrides. All stops, targets, and risk limits are enforced automatically.