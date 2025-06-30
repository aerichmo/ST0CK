#!/bin/bash
# Migration script to unified ST0CK architecture

echo "=== ST0CK Migration to Unified Architecture ==="
echo "This script will help migrate to the new unified architecture"
echo ""

# Check if running from ST0CK directory
if [ ! -f "requirements.txt" ]; then
    echo "Error: Must run from ST0CK root directory"
    exit 1
fi

# Step 1: Backup
echo "Step 1: Creating backup..."
BACKUP_DIR="../ST0CK_backup_$(date +%Y%m%d_%H%M%S)"
cp -r . "$BACKUP_DIR"
echo "✓ Backup created at: $BACKUP_DIR"

# Step 2: Install new dependencies
echo ""
echo "Step 2: Installing new dependencies..."
pip install python-json-logger==2.0.7
pip install sentry-sdk==1.39.1
pip install redis==5.0.1
pip install aioredis==2.0.1
echo "✓ Dependencies installed"

# Step 3: Check Redis
echo ""
echo "Step 3: Checking Redis connection..."
if [ -z "$REDIS_URL" ]; then
    echo "⚠️  Warning: REDIS_URL not set. Using default redis://localhost:6379"
    echo "   To use Redis caching, set REDIS_URL environment variable"
else
    echo "✓ Redis URL configured: $REDIS_URL"
fi

# Step 4: Update environment
echo ""
echo "Step 4: Updating environment variables..."
if [ -f ".env" ]; then
    # Add new variables if not present
    grep -q "REDIS_URL" .env || echo "REDIS_URL=redis://localhost:6379" >> .env
    grep -q "SENTRY_DSN" .env || echo "# SENTRY_DSN=your_sentry_dsn_here" >> .env
    echo "✓ Environment variables updated"
else
    echo "⚠️  No .env file found. Please set environment variables manually"
fi

# Step 5: Database migration
echo ""
echo "Step 5: Running database migrations..."
if [ -f "migrations/add_performance_indexes.sql" ]; then
    echo "   Please run the following migration on your database:"
    echo "   psql $DATABASE_URL < migrations/add_performance_indexes.sql"
    echo "   (or equivalent for your database)"
fi

# Step 6: Create unified directories
echo ""
echo "Step 6: Creating new directories..."
mkdir -p src/services
mkdir -p src/utils
mkdir -p src/strategies
echo "✓ Directories created"

# Step 7: Test imports
echo ""
echo "Step 7: Testing new imports..."
python -c "
try:
    from src.unified_engine import UnifiedTradingEngine
    from src.unified_database import UnifiedDatabaseManager
    from src.unified_cache import UnifiedCache
    from src.unified_logging import configure_logging
    print('✓ All imports successful')
except Exception as e:
    print(f'✗ Import error: {e}')
"

# Step 8: Update deployment scripts
echo ""
echo "Step 8: Updating deployment scripts..."
if [ -f "deploy.sh" ]; then
    # Create new deploy script
    cat > deploy_unified.sh << 'EOF'
#!/bin/bash
# Unified deployment script

# Load environment
source .env

# Run unified engine
python main_unified.py "$@"
EOF
    chmod +x deploy_unified.sh
    echo "✓ Created deploy_unified.sh"
fi

# Step 9: Create systemd service (optional)
echo ""
echo "Step 9: Creating systemd service template..."
cat > st0ck-unified.service << EOF
[Unit]
Description=ST0CK Unified Trading System
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$(pwd)
Environment="PATH=/usr/local/bin:/usr/bin:/bin"
EnvironmentFile=$(pwd)/.env
ExecStart=/usr/bin/python3 $(pwd)/main_unified.py --all
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
echo "✓ Created st0ck-unified.service template"

# Step 10: Summary
echo ""
echo "=== Migration Summary ==="
echo ""
echo "✅ Completed:"
echo "   - Created backup"
echo "   - Installed dependencies"
echo "   - Updated environment"
echo "   - Created directories"
echo "   - Generated deployment scripts"
echo ""
echo "⚠️  Manual steps required:"
echo "   1. Run database migrations"
echo "   2. Update Redis URL if using external Redis"
echo "   3. Configure Sentry DSN for error tracking"
echo "   4. Test with: python main_unified.py --list"
echo "   5. Remove old files after testing (see cleanup_analysis.md)"
echo ""
echo "📝 To test the new system:"
echo "   python main_unified.py st0cka  # Test ST0CKA"
echo "   python main_unified.py st0ckg  # Test ST0CKG"
echo ""
echo "Migration preparation complete!"