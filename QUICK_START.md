# APEX Trading System Quick Start Guide

## Prerequisites
- Python 3.8+
- Alpaca Paper Trading Account
- SQLite database (automatic)

## 1. Clone and Setup

```bash
# Clone repository
git clone [your-repo-url]
cd ST0CK

# Run deployment script
chmod +x deploy.sh
./deploy.sh
```

## 2. Configure Environment

Create/edit `.env` file:
```bash
# Alpaca API Keys
STOCKG_KEY=your-alpaca-api-key
ST0CKG_SECRET=your-alpaca-secret
ALPACA_BASE_URL=https://api.alpaca.markets

# Trading Capital
APEX_TRADING_CAPITAL=5000

# Database (SQLite by default)
DATABASE_URL=sqlite:///trading_multi.db
```

## 3. Test Configuration

```bash
# List registered bots
python3 main_multi.py --list
```

## 4. Run the APEX Bot

```bash
# Run APEX strategy
python3 main_multi.py apex
```

## 5. Monitor Performance

### View Performance Dashboard:
- Yearly Overview: https://st0ck.onrender.com/
- Monthly Details: https://st0ck.onrender.com/st0ckg

### Database Queries:
```sql
-- Today's trades
SELECT * FROM trades 
WHERE bot_id = 'apex' 
AND DATE(entry_time) = CURRENT_DATE;

-- Overall performance
SELECT COUNT(*) as total_trades, 
       SUM(realized_pnl) as total_pnl,
       AVG(realized_pnl) as avg_pnl
FROM trades
WHERE bot_id = 'apex' 
AND status = 'CLOSED';
```

### Logs:
- Local: `logs/multi_bot_YYYYMMDD.log`

## Trading Schedule
- **Trading Window**: 9:30-11:00 AM ET
- **Focus**: Morning momentum and VWAP reversions
- **Max Daily Trades**: 5
- **Risk Per Trade**: 3.5%

## Troubleshooting

### Bot not trading?
1. Check market hours (9:30-11:00 AM ET)
2. Verify API credentials are correct
3. Check logs for errors
4. Ensure sufficient buying power in Alpaca account

### Need help?
- Check `APEX_QUICK_REFERENCE.md` for strategy details
- Review bot strategy in `bots/apex/strategy.py`
- View performance metrics at dashboard URLs above