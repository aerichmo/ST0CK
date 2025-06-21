# Multi-Bot Trading System Setup

## Overview

The ST0CK trading system now supports running multiple bots with different strategies and Alpaca accounts. Each bot operates independently with its own:
- Trading strategy
- Alpaca account credentials
- Risk limits and capital allocation
- Performance tracking
- GitHub Actions workflow

## Current Bots

### ST0CKG - Opening Range Breakout
- **Strategy**: Trades SPY options based on opening range breakouts
- **Trading Window**: 9:40 AM - 10:30 AM ET
- **Default Capital**: $5,000
- **Status**: Active

### ST0CKA - [Strategy TBD]
- **Strategy**: To be implemented
- **Trading Window**: TBD
- **Default Capital**: $10,000
- **Status**: Inactive (placeholder)

## Environment Variables

Each bot requires its own set of environment variables:

### ST0CKG Variables
```bash
ST0CKG_APCA_API_KEY_ID=your-api-key
ST0CKG_APCA_API_SECRET_KEY=your-secret-key
ST0CKG_TRADING_CAPITAL=5000
ST0CKG_ALPACA_ACCOUNT=primary
```

### ST0CKA Variables
```bash
ST0CKA_APCA_API_KEY_ID=your-api-key
ST0CKA_APCA_API_SECRET_KEY=your-secret-key
ST0CKA_TRADING_CAPITAL=10000
ST0CKA_ALPACA_ACCOUNT=secondary
```

### Shared Variables
```bash
DATABASE_URL=postgresql://...
EMAIL_USERNAME=your-email
EMAIL_PASSWORD=your-password
WEBHOOK_URL=https://...
```

## Database Migration

Before running the multi-bot system, apply the database migration:

```bash
# For PostgreSQL
psql $DATABASE_URL < migrations/add_multi_bot_support.sql

# For SQLite (local testing)
sqlite3 trading_multi.db < migrations/add_multi_bot_support.sql
```

## Running Bots

### Local Development

Run a single bot:
```bash
python main_multi.py st0ckg
```

List all registered bots:
```bash
python main_multi.py --list
```

### GitHub Actions

Each bot has its own workflow:
- `.github/workflows/st0ckg-trading.yml` - Runs ST0CKG at 9:25 AM ET
- `.github/workflows/st0cka-trading.yml` - Manual trigger only (until strategy defined)

### Setting Up GitHub Secrets

Add these secrets to your GitHub repository:

1. **Database**
   - `DATABASE_URL`

2. **ST0CKG Bot**
   - `ST0CKG_APCA_API_KEY_ID`
   - `ST0CKG_APCA_API_SECRET_KEY`
   - `ST0CKG_TRADING_CAPITAL`

3. **ST0CKA Bot**
   - `ST0CKA_APCA_API_KEY_ID`
   - `ST0CKA_APCA_API_SECRET_KEY`
   - `ST0CKA_TRADING_CAPITAL`

4. **Notifications**
   - `EMAIL_USERNAME`
   - `EMAIL_PASSWORD`
   - `WEBHOOK_URL`

## Adding a New Bot

1. **Create bot directory structure**:
   ```
   bots/
   └── st0ckx/
       ├── config.py
       └── strategy.py
   ```

2. **Implement strategy**:
   - Inherit from `BaseStrategy`
   - Implement all abstract methods

3. **Create configuration**:
   - Define trading parameters
   - Set risk limits

4. **Create GitHub Actions workflow**:
   - Copy and modify existing workflow
   - Set appropriate schedule

5. **Add environment variables**:
   - Add to GitHub Secrets
   - Update documentation

## Performance Monitoring

### Bot-Specific Metrics
```python
# Get performance for specific bot
from src.multi_bot_database import MultiBotDatabaseManager

db = MultiBotDatabaseManager(DATABASE_URL)
metrics = db.get_bot_performance_metrics('st0ckg', days=30)
```

### Compare All Bots
```python
# Compare performance across all bots
comparison = db.compare_bots_performance(days=30)
```

### Database Queries
```sql
-- Bot-specific trades
SELECT * FROM trades WHERE bot_id = 'st0ckg' AND DATE(entry_time) = CURRENT_DATE;

-- Bot performance summary
SELECT bot_id, COUNT(*) as trades, SUM(realized_pnl) as total_pnl 
FROM trades 
WHERE status = 'CLOSED' 
GROUP BY bot_id;

-- Daily performance by bot
SELECT * FROM bot_trades WHERE trade_date = CURRENT_DATE;
```

## Architecture Benefits

1. **Complete Isolation**: Each bot operates independently
2. **Different Strategies**: Easy to test different approaches
3. **Risk Distribution**: Separate capital and risk limits
4. **Performance Tracking**: Compare strategies side-by-side
5. **Easy Scaling**: Add new bots without affecting existing ones
6. **Flexible Scheduling**: Each bot can run at different times

## Troubleshooting

### Bot Not Trading
1. Check if bot is active in config
2. Verify API credentials are set
3. Check database connection
4. Review logs for errors

### Database Issues
1. Ensure migration was applied
2. Check bot_id is being set in all queries
3. Verify database connection string

### Performance Issues
1. Market data is shared across bots (efficient)
2. Each bot has its own broker connection
3. Database writes are batched