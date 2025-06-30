#!/bin/bash
# ST0CK Multi-Bot Deployment Script

set -e

echo "======================================"
echo "ST0CK Multi-Bot Deployment Setup"
echo "======================================"

# Check if .env file exists
if [ ! -f .env ]; then
    echo "Creating .env file template..."
    cat > .env << EOF
# Alpaca API Configuration
ST0CKGKEY=your-stockg-key
ST0CKGSECRET=your-stockg-secret
ST0CKAKEY=your-stocka-key
ST0CKASECRET=your-stocka-secret
ALPACA_BASE_URL=https://api.alpaca.markets

# Trading Capital
ST0CKG_TRADING_CAPITAL=5000
ST0CKA_TRADING_CAPITAL=10000

# Database
DATABASE_URL=sqlite:///trading_multi.db

# Optional: Notifications
EMAIL_USERNAME=
EMAIL_PASSWORD=
WEBHOOK_URL=
EOF
    echo "✓ Created .env template - please update with your credentials"
else
    echo "✓ .env file already exists"
fi

# Create necessary directories
echo ""
echo "Creating directories..."
mkdir -p logs
mkdir -p data
echo "✓ Directories created"

# Check Python version
echo ""
echo "Checking Python version..."
python_version=$(python3 --version 2>&1)
echo "Found: $python_version"

# Install dependencies
echo ""
echo "Installing dependencies..."
pip3 install -r requirements.txt
echo "✓ Dependencies installed"

# Database setup
echo ""
echo "Setting up database..."
if [ -f "migrations/add_multi_bot_support.sql" ]; then
    if [[ "$DATABASE_URL" == sqlite* ]]; then
        # SQLite setup
        echo "Using SQLite database"
        sqlite3 trading_multi.db < migrations/add_multi_bot_support.sql 2>/dev/null || echo "Migration may already be applied"
    else
        # PostgreSQL setup
        echo "Using PostgreSQL database"
        echo "Run this command manually:"
        echo "psql \$DATABASE_URL < migrations/add_multi_bot_support.sql"
    fi
fi
echo "✓ Database setup complete"

# Test configuration
echo ""
echo "Testing configuration..."
python3 main_unified.py

echo ""
echo "======================================"
echo "Deployment setup complete!"
echo ""
echo "Next steps:"
echo "1. Update .env with your API credentials"
echo "2. Set up GitHub Secrets for automated trading:"
echo "   - STOCKG_KEY, ST0CKG_SECRET"
echo "   - STOCKA_KEY, ST0CKA_SECRET"
echo "   - ALPACA_BASE_URL"
echo "   - DATABASE_URL"
echo "   - ST0CKG_TRADING_CAPITAL, ST0CKA_TRADING_CAPITAL"
echo ""
echo "To run a bot manually:"
echo "  python3 main_unified.py"
echo ""
echo "To enable automated trading:"
echo "  Push to GitHub and enable Actions"
echo "======================================"