# GitHub Repository Setup for Automated Trading

## Step 1: Create Repository
1. Go to GitHub.com and create a new **private** repository
2. Name it `options-scalper` or similar

## Step 2: Push Code
```bash
cd "/Users/alecrichmond/Library/Mobile Documents/com~apple~CloudDocs/st0ck/options-scalper"
git init
git add .
git commit -m "Initial commit - Options scalper trading bot"
git branch -M main
git remote add origin https://github.com/aerichmo/ST0CK.git
git push -u origin main
```

## Step 3: Set Up Free Cloud Database
Go to [Supabase](https://supabase.com) or [Neon](https://neon.tech):
1. Create free account
2. Create new PostgreSQL database
3. Copy the connection string (looks like: `postgresql://user:pass@host:5432/dbname`)

## Step 4: Configure GitHub Secrets
In your GitHub repo, go to **Settings → Secrets and variables → Actions** and add:

- `DATABASE_URL`: Your Supabase/Neon PostgreSQL connection string
- `WEBHOOK_URL`: (Optional) Discord/Slack webhook for alerts

For paper trading, that's all you need!

## Step 5: Enable GitHub Actions
1. Go to **Actions** tab in your repo
2. You should see "Options Scalper Trading Bot" workflow
3. Click "Enable workflow"

## Step 6: Test Manual Run
1. Go to Actions tab
2. Click "Options Scalper Trading Bot"
3. Click "Run workflow" → "Run workflow"
4. Watch it execute!

## That's It! 🎉

Your bot will now:
- Run automatically at 9:25 AM ET every weekday
- Trade from 9:40-10:30 AM ET
- Shut down at 4:00 PM ET
- Save all logs to GitHub
- Cost: **$0/month**

## Monitoring

Check your bot's performance:
1. Go to Actions tab to see run history
2. Click any run to see logs
3. Download artifacts for detailed logs

## Optional Enhancements

### Discord Alerts
1. Create Discord webhook in your server
2. Add `WEBHOOK_URL` secret
3. Get real-time trade notifications

### Email Alerts
Add these secrets for email notifications:
- `EMAIL_USERNAME`: Your Gmail
- `EMAIL_PASSWORD`: App-specific password (not regular password)

### Live Trading (Future)
When ready for live trading:
- `BROKER_API_KEY`: Your broker's API key
- `BROKER_API_SECRET`: Your broker's API secret
- Change `--mode paper` to `--mode live` in workflow