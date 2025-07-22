# ST0CK Setup Guide

Complete installation and configuration guide for the ST0CK trading system.

## Prerequisites

- Python 3.9 or higher
- Alpaca Markets account with API access
- Options trading approval (for ST0CKG strategy)
- Git (for cloning the repository)

## Installation

### 1. Clone Repository

```bash
git clone https://github.com/yourusername/st0ck.git
cd st0ck
```

### 2. Create Virtual Environment (Recommended)

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Database Setup

The system uses SQLite by default. For production, PostgreSQL is recommended.

```bash
# SQLite (default)
# Database will be created automatically at trading_multi.db

# PostgreSQL (optional)
export DATABASE_URL=postgresql://user:password@host:port/dbname
```

## Configuration

### 1. Environment Variables

Create a `.env` file in the project root:

```bash
# Alpaca API Credentials
ST0CKGKEY=your-alpaca-api-key       # For ST0CKG strategy
ST0CKGSECRET=your-alpaca-secret-key
ST0CKAKEY=your-alpaca-api-key       # For simple stock strategy
ST0CKASECRET=your-alpaca-secret-key

# Trading Configuration
ALPACA_BASE_URL=https://paper-api.alpaca.markets  # Paper trading
# ALPACA_BASE_URL=https://api.alpaca.markets      # Live trading

# Capital Allocation (optional - uses account balance by default)
ST0CKG_TRADING_CAPITAL=5000
ST0CKA_TRADING_CAPITAL=100

# Database
DATABASE_URL=sqlite:///trading_multi.db

# Optional: Notifications
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
TELEGRAM_BOT_TOKEN=your-telegram-bot-token

# Optional: Web Dashboard
PORT=10000
```

### 2. Bot Configuration

Each bot has its own configuration file:

- **ST0CKG**: `bots/st0ckg/config.py`
- **Simple Stock (ST0CKA)**: `bots/st0cka/config.py`

Key configuration options:

```python
# Risk Management
'risk_per_trade': 0.03,  # 3% base risk
'max_daily_loss': 500,   # Max daily loss in dollars
'max_consecutive_losses': 3,

# Trading Windows
'trading_window': {
    'start': '09:30',
    'end': '11:00'
},

# Position Limits
'max_positions': 1,
'max_contracts': 10,
```

## Running the System

### Manual Execution

```bash
# List available bots
# Run the unified trading system
python main_unified.py
```

### Automated Execution (GitHub Actions)

The system includes GitHub Actions workflows for automated daily trading:

1. **Fork the repository** to your GitHub account
2. **Add secrets** to your repository:
   - Go to Settings → Secrets → Actions
   - Add: `STOCKGKEY`, `ST0CKGSECRET`, `ALPACA_BASE_URL`, `DATABASE_URL`
3. **Enable Actions** in your repository
4. **Workflows run automatically** at scheduled times (9:20 AM ET weekdays)

### Web Dashboard

Start the dashboard server:

```bash
python app.py
# or for production:
gunicorn app:app --bind 0.0.0.0:10000
```

Access dashboards:
- Performance: `http://localhost:10000/`
- Metrics: `http://localhost:10000/metrics`
- ST0CKG Monthly: `http://localhost:10000/st0ckg`

## Testing

### 1. Paper Trading

Always test with paper trading first:

```bash
export ALPACA_BASE_URL=https://paper-api.alpaca.markets
python main_unified.py st0ckg
```

### 2. Verify Connection

```python
# Test API connection
python -c "
from src.alpaca_broker import AlpacaBroker
broker = AlpacaBroker()
if broker.connect():
    print('Connection successful!')
    account = broker.get_account_info()
    print(f'Account balance: ${account[\"cash\"]:,.2f}')
"
```

### 3. Monitor Logs

```bash
# Real-time log monitoring
tail -f logs/multi_bot_$(date +%Y%m%d).log

# Check for errors
grep ERROR logs/multi_bot_$(date +%Y%m%d).log
```

## Performance Monitoring

### System Metrics

Monitor system performance at `/metrics`:
- Cache hit rates
- Connection pool utilization
- API request statistics
- Rate limiting events

### Trading Performance

Track P&L and trades:

```sql
-- Today's performance
SELECT bot_id, COUNT(*) as trades, SUM(realized_pnl) as total_pnl
FROM trades
WHERE DATE(entry_time) = DATE('now')
GROUP BY bot_id;

-- Monthly performance
SELECT 
    strftime('%Y-%m', entry_time) as month,
    COUNT(*) as trades,
    SUM(CASE WHEN realized_pnl > 0 THEN 1 ELSE 0 END) as wins,
    SUM(realized_pnl) as total_pnl
FROM trades
WHERE bot_id = 'st0ckg'
GROUP BY month;
```

## Troubleshooting

### Common Issues

1. **"No API credentials found"**
   - Ensure `.env` file exists with correct credentials
   - Check environment variable names match exactly

2. **"Failed to connect to Alpaca"**
   - Verify API credentials are correct
   - Check if using correct base URL (paper vs live)
   - Ensure your IP is whitelisted (if using live account)

3. **"Options trading not enabled"**
   - Contact Alpaca support to enable options trading
   - Paper accounts have options enabled by default

4. **Database errors**
   - Ensure write permissions for SQLite file
   - Check PostgreSQL connection string if using

5. **Rate limiting errors**
   - System includes automatic rate limiting
   - If persistent, reduce concurrent operations

### Debug Mode

Enable verbose logging:

```python
# In src/unified_logging.py
setup_logging(log_level="DEBUG")
```

### Support

- Check logs in `logs/` directory
- Review error messages for specific guidance
- Ensure all dependencies are installed correctly

## Security Best Practices

1. **Never commit credentials** - Use environment variables
2. **Use paper trading** for testing
3. **Set appropriate risk limits** in configuration
4. **Monitor positions** regularly
5. **Enable 2FA** on your Alpaca account
6. **Restrict API key permissions** to only what's needed

## Next Steps

1. Start with paper trading
2. Run ST0CKA (simple strategy) first
3. Monitor performance for at least 1 week
4. Gradually increase position sizes
5. Consider ST0CKG strategy after gaining experience

For technical details and architecture information, see [TECHNICAL_DOCS.md](TECHNICAL_DOCS.md).