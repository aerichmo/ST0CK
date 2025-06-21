#!/usr/bin/env python3
"""
Test environment configuration for multi-bot setup
"""
import os
import sys

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    print("Note: python-dotenv not installed, reading from environment only")

def check_env():
    """Check if all required environment variables are set"""
    print("ST0CK Multi-Bot Environment Check")
    print("=" * 50)
    
    # Required variables
    required = {
        'STOCKG_KEY': 'ST0CKG Alpaca API Key',
        'ST0CKG_SECRET': 'ST0CKG Alpaca Secret',
        'STOCKA_KEY': 'ST0CKA Alpaca API Key', 
        'ST0CKA_SECRET': 'ST0CKA Alpaca Secret',
        'ALPACA_BASE_URL': 'Alpaca Base URL',
        'DATABASE_URL': 'Database Connection'
    }
    
    # Optional variables
    optional = {
        'ST0CKG_TRADING_CAPITAL': 'ST0CKG Trading Capital',
        'ST0CKA_TRADING_CAPITAL': 'ST0CKA Trading Capital',
        'EMAIL_USERNAME': 'Email for notifications',
        'EMAIL_PASSWORD': 'Email password',
        'WEBHOOK_URL': 'Webhook for alerts'
    }
    
    missing = []
    
    print("\nRequired Variables:")
    print("-" * 50)
    for var, desc in required.items():
        value = os.getenv(var)
        if value:
            # Mask sensitive values
            if 'KEY' in var or 'SECRET' in var:
                masked = value[:4] + '*' * (len(value) - 8) + value[-4:] if len(value) > 8 else '***'
                print(f"✓ {var:<25} {masked}")
            else:
                print(f"✓ {var:<25} {value}")
        else:
            print(f"✗ {var:<25} NOT SET")
            missing.append(var)
    
    print("\nOptional Variables:")
    print("-" * 50)
    for var, desc in optional.items():
        value = os.getenv(var)
        if value:
            if 'PASSWORD' in var:
                print(f"✓ {var:<25} ***")
            else:
                print(f"✓ {var:<25} {value}")
        else:
            print(f"- {var:<25} Not set")
    
    # Test imports
    print("\nModule Imports:")
    print("-" * 50)
    try:
        import alpaca
        print("✓ alpaca-py")
    except:
        print("✗ alpaca-py - run: pip install alpaca-py")
        missing.append('alpaca-py')
    
    try:
        import pandas
        print("✓ pandas")
    except:
        print("✗ pandas - run: pip install pandas")
        missing.append('pandas')
    
    try:
        import sqlalchemy
        print("✓ sqlalchemy")
    except:
        print("✗ sqlalchemy - run: pip install sqlalchemy")
        missing.append('sqlalchemy')
    
    # Test bot configs
    print("\nBot Configurations:")
    print("-" * 50)
    for bot in ['st0ckg', 'st0cka']:
        try:
            import importlib
            config_module = importlib.import_module(f'bots.{bot}.config')
            config = getattr(config_module, f'{bot.upper()}_CONFIG')
            print(f"✓ {bot:<10} - {config.get('strategy_name', 'Unknown')}")
        except Exception as e:
            print(f"✗ {bot:<10} - Error: {str(e)}")
    
    # Summary
    print("\n" + "=" * 50)
    if missing:
        print(f"❌ Missing {len(missing)} required items:")
        for item in missing:
            print(f"   - {item}")
        print("\nPlease update your .env file or install missing packages")
        return False
    else:
        print("✅ All required configuration found!")
        print("\nYou can now run:")
        print("  python main_multi.py st0ckg")
        return True

if __name__ == "__main__":
    success = check_env()
    sys.exit(0 if success else 1)