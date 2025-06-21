# ST0CK Multi-Bot Quick Start Guide

## Prerequisites
- Python 3.8+
- Alpaca Paper Trading Account(s)
- PostgreSQL or SQLite database

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
# Alpaca API Keys (from your saved secrets)
STOCKG_KEY=your-stockg-key
ST0CKG_SECRET=your-stockg-secret
STOCKA_KEY=your-stocka-key
ST0CKA_SECRET=your-stocka-secret
ALPACA_BASE_URL=https://api.alpaca.markets

# Trading Capital
ST0CKG_TRADING_CAPITAL=5000
ST0CKA_TRADING_CAPITAL=10000

# Database (use PostgreSQL for production)
DATABASE_URL=postgresql://user:pass@host/dbname
# or for local testing:
# DATABASE_URL=sqlite:///trading_multi.db
```

## 3. Test Configuration

```bash
# Check environment
python3 test_env.py

# List registered bots
python3 main_multi.py --list
```

## 4. Run Manually

```bash
# Run ST0CKG (Opening Range Breakout)
python3 main_multi.py st0ckg

# Run ST0CKA (when implemented)
python3 main_multi.py st0cka
```

## 5. Deploy to GitHub Actions

### Add GitHub Secrets:
Go to Settings → Secrets → Actions and add:

- `ALPACA_BASE_URL` - https://api.alpaca.markets
- `DATABASE_URL` - Your PostgreSQL connection string
- `STOCKG_KEY` - ST0CKG API key
- `ST0CKG_SECRET` - ST0CKG secret
- `ST0CKG_TRADING_CAPITAL` - 5000
- `STOCKA_KEY` - ST0CKA API key
- `ST0CKA_SECRET` - ST0CKA secret
- `ST0CKA_TRADING_CAPITAL` - 10000

### Enable Workflows:
1. Go to Actions tab
2. Enable workflows
3. ST0CKG will run automatically at 9:25 AM ET
4. ST0CKA can be triggered manually

## 6. Monitor Performance

### Database Queries:
```sql
-- Today's trades
SELECT * FROM trades 
WHERE bot_id = 'st0ckg' 
AND DATE(entry_time) = CURRENT_DATE;

-- Bot performance
SELECT bot_id, COUNT(*) as trades, SUM(realized_pnl) as total_pnl
FROM trades
WHERE status = 'CLOSED'
GROUP BY bot_id;
```

### Logs:
- Local: `logs/multi_bot_YYYYMMDD.log`
- GitHub Actions: Check workflow runs

## Troubleshooting

### Bot not trading?
1. Check market hours (9:40-10:30 AM ET for ST0CKG)
2. Verify API credentials: `python3 test_env.py`
3. Check logs for errors
4. Ensure sufficient buying power in Alpaca account

### Database errors?
1. Run migration: `psql $DATABASE_URL < migrations/add_multi_bot_support.sql`
2. Check connection string format
3. Verify bot_id columns exist

### Need help?
- Check `MULTI_BOT_SETUP.md` for detailed setup
- Review bot strategy in `bots/st0ckg/strategy.py`
- Check GitHub Actions logs for automated runs