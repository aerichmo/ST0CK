# Alpaca Setup for GitHub Actions

## GitHub Secrets to Add

Go to https://github.com/aerichmo/ST0CK/settings/secrets/actions and add:

### Required Secrets:

1. **ALPACA_API_KEY**
   - Your Alpaca API Key ID
   - Get from: https://app.alpaca.markets/paper/dashboard/overview

2. **ALPACA_API_SECRET**
   - Your Alpaca Secret Key
   - Get from same dashboard (only shown once!)

3. **ALPACA_BASE_URL**
   - For paper trading: `https://paper-api.alpaca.markets`
   - For live trading: `https://api.alpaca.markets`

4. **DATABASE_URL**
   - Your PostgreSQL connection string
   - Example: `postgresql://user:password@host:5432/dbname`

### Optional Secrets:

5. **WEBHOOK_URL**
   - Discord/Slack webhook for trade notifications
   - Example: `https://discord.com/api/webhooks/...`

## Security Best Practices:

✅ **DO:**
- Use Alpaca's paper trading API first
- Create separate API keys for paper vs live
- Rotate keys every 90 days
- Use GitHub's secret scanning

❌ **DON'T:**
- Share API keys in code or commits
- Use same keys for multiple bots
- Store keys in plain text files

## How GitHub Protects Your Secrets:

1. **Encrypted at rest** - Using AES-256
2. **Encrypted in transit** - Over HTTPS
3. **Access controlled** - Only accessible during workflow runs
4. **Not logged** - Automatically redacted from logs
5. **Not in forks** - Secrets don't copy to forked repos

## Testing Your Setup:

After adding secrets, trigger a manual run:
1. Go to Actions tab
2. Click "Options Scalper Trading Bot"
3. Click "Run workflow"
4. Check logs to confirm connection

## Alpaca Options Trading Note:

Alpaca currently supports:
- ✅ Stock trading
- ✅ Crypto trading
- ⚠️ Options trading (limited, check current availability)

For full options support, you may need to integrate with:
- Interactive Brokers (via ib_insync)
- TD Ameritrade
- E*TRADE

The bot architecture supports swapping brokers by implementing the BrokerInterface.