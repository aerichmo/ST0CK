# Cloud Deployment Guide for Autonomous Trading

## Option 1: GitHub Actions (Recommended for Free Tier)

### Pros:
- **FREE** for public repos (2,000 mins/month) or private repos (3,000 mins/month with Pro)
- No server management required
- Built-in secrets management
- Automatic scheduling with cron
- Logs and artifacts storage

### Setup:
1. Push code to GitHub repository
2. Go to Settings → Secrets → Actions
3. Add these secrets:
   - `DATABASE_URL`: Your cloud PostgreSQL URL (e.g., Supabase, Neon, or Railway)
   - `BROKER_API_KEY`: Your broker API key
   - `BROKER_API_SECRET`: Your broker API secret
   - `EMAIL_USERNAME`: Email for alerts
   - `EMAIL_PASSWORD`: Email app password
   - `WEBHOOK_URL`: Slack/Discord webhook

4. The bot will run automatically at 9:25 AM ET every weekday

### Free Database Options:
- **Supabase**: 500MB free PostgreSQL
- **Neon**: 3GB free PostgreSQL  
- **Railway**: $5 credit/month

## Option 2: Railway.app (Simple One-Click Deploy)

### Pros:
- One-click deploy from GitHub
- $5 free credit monthly
- Built-in PostgreSQL
- Easy environment variables
- Automatic deploys on git push

### Setup:
```bash
# Install Railway CLI
npm install -g @railway/cli

# Login and initialize
railway login
railway init

# Deploy
railway up
```

## Option 3: AWS Lambda (Serverless)

### Pros:
- Pay only for execution time
- 1M free requests/month
- Can use EventBridge for scheduling
- Scales automatically

### Cons:
- 15-minute timeout limit (may need to split trading session)
- More complex setup

## Option 4: Google Cloud Run + Cloud Scheduler

### Pros:
- $300 free credit for new users
- Generous free tier
- Managed container service
- Cloud Scheduler for cron jobs

### Setup:
```bash
# Build and push to Google Container Registry
gcloud builds submit --tag gcr.io/YOUR_PROJECT/options-scalper

# Deploy to Cloud Run
gcloud run deploy options-scalper \
  --image gcr.io/YOUR_PROJECT/options-scalper \
  --platform managed \
  --region us-east1 \
  --timeout 3600

# Create Cloud Scheduler job
gcloud scheduler jobs create http trading-job \
  --schedule="25 9 * * 1-5" \
  --uri=YOUR_CLOUD_RUN_URL \
  --http-method=GET \
  --time-zone="America/New_York"
```

## Option 5: Fly.io (Modern Heroku Alternative)

### Pros:
- Generous free tier
- Global deployment
- Built-in PostgreSQL
- Easy CLI deployment

### Setup:
```bash
# Install Fly CLI
curl -L https://fly.io/install.sh | sh

# Launch app
fly launch

# Set secrets
fly secrets set DATABASE_URL=...
fly secrets set BROKER_API_KEY=...

# Deploy
fly deploy
```

## Recommended Architecture

For production trading with 10% per trade risk:

1. **GitHub Actions** for scheduling and orchestration
2. **Supabase/Neon** for free PostgreSQL database
3. **Slack/Discord** webhook for real-time alerts
4. **GitHub** for version control and CI/CD

This gives you:
- Zero monthly cost
- Automatic daily runs
- Full audit trail in GitHub
- Easy rollback capability
- Secure secrets management

## Security Considerations

1. **Never commit secrets** - Always use environment variables
2. **Use read-only API keys** where possible
3. **Enable 2FA** on all services
4. **Monitor usage** to avoid unexpected charges
5. **Set up billing alerts** on cloud providers

## Monitoring Setup

Add these to your GitHub Actions:
```yaml
- name: Send Discord notification
  if: failure()
  run: |
    curl -X POST ${{ secrets.WEBHOOK_URL }} \
    -H "Content-Type: application/json" \
    -d '{"content":"⚠️ Trading bot failed! Check logs: ${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}"}'
```