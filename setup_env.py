#!/usr/bin/env python3
"""Set up environment variables for ST0CKA bot"""

import os
import sys

print("=== ST0CKA Environment Setup ===")
print("\nThis script will help you set up your API credentials.")
print("Your credentials will be saved to .env file (which should be in .gitignore)")

# Get credentials
api_key = input("\nEnter your Alpaca API Key: ").strip()
secret_key = input("Enter your Alpaca Secret Key: ").strip()

# Validate
if not api_key or not secret_key:
    print("\n❌ Error: Both API key and secret key are required")
    sys.exit(1)

# Write to .env
env_content = f"""# ST0CKA Bot Credentials
st0ckakey={api_key}
st0ckasecret={secret_key}

# ST0CKG Bot Credentials (if you have a second account)
STOCKG_KEY=your_alpaca_api_key_here
ST0CKG_SECRET=your_alpaca_secret_key_here

# Alpaca Base URL (paper trading)
ALPACA_BASE_URL=https://paper-api.alpaca.markets

# Database Configuration
DATABASE_URL=sqlite:///trading_multi.db

# Trading Configuration
INITIAL_CAPITAL=5000
TRADING_MODE=paper
"""

with open('.env', 'w') as f:
    f.write(env_content)

print("\n✅ Environment file created successfully!")
print("\nYou can now run the bot with:")
print("  python3 main_multi.py st0cka")

# Test the setup
print("\nTesting connection...")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

# Verify environment variables are loaded
if os.getenv('st0ckakey') == api_key:
    print("✅ Environment variables loaded correctly")
else:
    print("❌ Error loading environment variables")

# Quick connection test
try:
    from src.alpaca_broker import AlpacaBroker
    broker = AlpacaBroker(
        api_key=api_key,
        secret_key=secret_key,
        base_url='https://paper-api.alpaca.markets',
        paper=True
    )
    if broker.connect():
        account = broker.get_account_info()
        if account:
            print(f"✅ Connected to Alpaca! Account balance: ${account['cash']:,.2f}")
        else:
            print("❌ Connected but couldn't get account info")
    else:
        print("❌ Failed to connect to Alpaca - check your credentials")
except Exception as e:
    print(f"❌ Error testing connection: {e}")