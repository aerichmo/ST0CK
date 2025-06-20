# Deploying ST0CK Dashboard to Render

This guide walks you through deploying the ST0CK trading dashboard to Render.com for 24/7 web access.

## Prerequisites

1. GitHub account with ST0CK repository
2. Render.com account (free tier works)
3. Alpaca API credentials (for real-time data)

## Quick Deploy Steps

### 1. Push Latest Code to GitHub
```bash
git add .
git commit -m "Add Render deployment configuration"
git push origin main
```

### 2. Create New Web Service on Render

1. Go to [Render Dashboard](https://dashboard.render.com)
2. Click "New +" → "Web Service"
3. Connect your GitHub account if needed
4. Select your `ST0CK` repository
5. Configure the service:
   - **Name**: `st0ck-dashboard`
   - **Runtime**: Python
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python render_dashboard.py`
   - **Plan**: Free ($0/month)

### 3. Set Environment Variables

In Render dashboard, add these environment variables:

#### Required for Market Data:
```
ALPACA_API_KEY=your_alpaca_paper_api_key
ALPACA_API_SECRET=your_alpaca_paper_api_secret
ALPACA_BASE_URL=https://paper-api.alpaca.markets
```

#### Optional Database (for trade history):
```
DATABASE_URL=postgresql://user:pass@host:5432/dbname
```

You can use Render's PostgreSQL or external services like:
- Supabase (500MB free)
- Neon (3GB free)
- Aiven (1 month free trial)

### 4. Deploy

Click "Create Web Service" and Render will:
1. Clone your repository
2. Install dependencies
3. Start the dashboard
4. Provide a URL like: `https://st0ck-dashboard.onrender.com`

## Features on Render

### What Works:
- ✅ Real-time SPY candlestick charts (9:30 AM - 10:35 AM ET focus)
- ✅ 5-minute candle updates during market hours only
- ✅ Technical indicators (EMA 8/21)
- ✅ Opening range visualization (9:30-9:40 AM ET)
- ✅ Active trading window indicator (9:40-10:30 AM ET)
- ✅ Volume analysis
- ✅ View-only mode (no trading)
- ✅ Smart status display showing current trading phase

### What's Different:
- 📊 **View-only mode** - No live trading execution
- 🔄 **Market data only** - Shows current market conditions
- 📈 **Historical trades** - If database is connected
- 🌐 **Public URL** - Accessible from anywhere

## Configuration Options

### 1. Basic Deployment (No Database)
Just add Alpaca credentials. Dashboard will show:
- Live market data
- Real-time charts
- Technical indicators

### 2. With Database
Add DATABASE_URL for:
- Historical trade viewing
- Performance tracking
- Trade log display

### 3. Security Considerations

For production use, add authentication:

```python
# In render_dashboard.py, add:
import dash_auth

# Basic auth
auth = dash_auth.BasicAuth(
    app,
    {'username': 'password'}
)
```

Or use Render's built-in authentication features.

## Monitoring Your Deployment

### Check Logs
```bash
# In Render dashboard
Services → st0ck-dashboard → Logs
```

### Common Issues

#### "Application failed to respond"
- Check environment variables are set
- Verify ALPACA credentials are correct
- Look at logs for specific errors

#### "Module not found"
- Ensure all dependencies are in requirements.txt
- Check Python version compatibility

#### Slow Loading
- Free tier may sleep after 15 min inactivity
- First load takes 30-60 seconds to wake up
- Consider upgrading for always-on service

## Advanced Setup

### Custom Domain
1. In Render: Settings → Custom Domains
2. Add your domain: `trading.yourdomain.com`
3. Update DNS records as instructed

### Scheduled Updates
Add to render.yaml for periodic data refresh:
```yaml
crons:
  - name: refresh-data
    command: python scripts/refresh_cache.py
    schedule: "*/5 * * * *"  # Every 5 minutes
```

### Multi-Region Deployment
Upgrade to Render's paid plans for:
- Multiple regions
- Auto-scaling
- Zero downtime deploys

## Cost Breakdown

### Free Tier Includes:
- 750 hours/month (enough for 24/7)
- 512MB RAM
- Shared CPU
- Auto-SSL certificates

### Paid Options ($7/month):
- Dedicated resources
- No sleep timeout
- Priority support
- Custom domains

## Local Development vs Render

| Feature | Local | Render |
|---------|-------|---------|
| Live Trading | ✅ Yes | ❌ View only |
| Real-time Data | ✅ Yes | ✅ Yes |
| Access | 🏠 Local only | 🌐 Anywhere |
| Cost | 💻 Your computer | 🆓 Free tier |
| Uptime | ⏰ When running | 🔄 24/7* |

*Free tier sleeps after 15 min inactivity

## Next Steps

1. **Test Deployment**: Visit your Render URL
2. **Add Authentication**: Secure your dashboard
3. **Connect Database**: Enable trade history
4. **Set Up Alerts**: Use Render's monitoring
5. **Optimize Performance**: Consider caching

Your dashboard is now accessible from anywhere! Perfect for monitoring market conditions and reviewing your trading strategy on the go.