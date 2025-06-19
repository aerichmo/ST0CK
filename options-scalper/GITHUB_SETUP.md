# GitHub Actions Setup for Daily Trading

## Steps to Enable Automatic Daily Trading

1. **Push your code to GitHub**
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   git remote add origin https://github.com/YOUR_USERNAME/options-scalper.git
   git push -u origin main
   ```

2. **Add GitHub Secrets**
   Go to Settings → Secrets and variables → Actions, then add:
   - `ALPACA_API_KEY`
   - `ALPACA_API_SECRET`
   - `DATABASE_URL` (use a cloud database like Supabase or Neon)
   - `EMAIL_USERNAME`
   - `EMAIL_PASSWORD`
   - `WEBHOOK_URL`

3. **Enable GitHub Actions**
   - Go to Actions tab in your repository
   - Enable workflows if prompted

4. **Cloud Database Options**
   Since GitHub Actions runs in the cloud, you'll need a cloud database:
   - **Supabase** (free tier): https://supabase.com
   - **Neon** (free tier): https://neon.tech
   - **Railway**: https://railway.app

## Benefits
- Free (GitHub Actions provides 2000 minutes/month)
- No local machine needed
- Automatic daily runs
- Can monitor from anywhere
- Built-in logging in GitHub

## Manual Trigger
You can manually start the bot anytime from the Actions tab → Daily Trading Bot → Run workflow.