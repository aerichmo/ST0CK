#!/usr/bin/env python3
"""
ST0CK Enhanced Launcher
Easy way to run different ST0CK strategies with gamma scalping infrastructure
"""

import os
import sys
import argparse
import subprocess
from datetime import datetime

def setup_environment(strategy_mode, paper_trading=True, log_level="INFO"):
    """Set up environment variables for the selected strategy"""
    
    # Set strategy mode
    os.environ["STRATEGY_MODE"] = strategy_mode
    os.environ["IS_PAPER_TRADING"] = str(paper_trading).lower()
    os.environ["LOG_LEVEL"] = log_level
    
    # Set initialization mode based on strategy
    if strategy_mode == "gamma_scalping":
        # Gamma scalping needs initial straddle
        os.environ["INITIALIZATION_MODE"] = "init"
    else:
        # ST0CK strategies start fresh each day
        os.environ["INITIALIZATION_MODE"] = "init"
    
    print(f"🚀 Launching ST0CK Enhanced in {strategy_mode.upper()} mode")
    print(f"📊 Paper Trading: {paper_trading}")
    print(f"📝 Log Level: {log_level}")
    print(f"⏰ Start Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


def check_requirements():
    """Check if required dependencies are installed"""
    try:
        import alpaca
        import numpy
        import pandas
        import dotenv
        print("✅ Core dependencies found")
        return True
    except ImportError as e:
        print(f"❌ Missing dependencies: {e}")
        print("Please run: pip install -r requirements_st0ck.txt")
        return False


def check_credentials():
    """Check if API credentials are configured"""
    from dotenv import load_dotenv
    load_dotenv()
    
    # Check for any API credentials
    has_creds = any([
        os.getenv("ST0CKAKEY"),
        os.getenv("ST0CKGKEY"), 
        os.getenv("TRADING_API_KEY")
    ])
    
    if not has_creds:
        print("❌ No API credentials found")
        print("Please copy .env.st0ck.template to .env and add your credentials")
        return False
    
    print("✅ API credentials found")
    return True


def run_strategy(strategy_mode, **kwargs):
    """Run the selected strategy"""
    
    # Pre-flight checks
    if not check_requirements():
        return False
    
    if not check_credentials():
        return False
    
    # Setup environment
    setup_environment(strategy_mode, **kwargs)
    
    try:
        # Import and run
        print("\n" + "="*50)
        print(f"Starting {strategy_mode.upper()} strategy...")
        print("="*50)
        
        # Run the main application
        import main_st0ck
        import asyncio
        asyncio.run(main_st0ck.main())
        
    except KeyboardInterrupt:
        print("\n⏹️  Strategy stopped by user")
        return True
    except Exception as e:
        print(f"\n❌ Error running strategy: {e}")
        return False


def main():
    """Main CLI interface"""
    parser = argparse.ArgumentParser(
        description="ST0CK Enhanced Trading System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_st0ck.py st0cka                    # Run ST0CKA strategy
  python run_st0ck.py st0ckg --live             # Run ST0CKG live trading
  python run_st0ck.py gamma_scalping            # Run original gamma scalping
  python run_st0ck.py hybrid --debug            # Run hybrid mode with debug logs
  python run_st0ck.py st0cka --volatility-off   # ST0CKA without volatility sizing

Available Strategies:
  st0cka         - Simple SPY scalping ($0.01 profit target)
  st0ckg         - Battle Lines 0-DTE options strategy  
  gamma_scalping - Original Alpaca gamma scalping
  hybrid         - Adaptive strategy switching
        """
    )
    
    # Strategy selection
    parser.add_argument(
        "strategy",
        choices=["st0cka", "st0ckg", "gamma_scalping", "hybrid"],
        help="Trading strategy to run"
    )
    
    # Trading mode
    parser.add_argument(
        "--live", 
        action="store_true",
        help="Use live trading (default: paper trading)"
    )
    
    # Logging
    parser.add_argument(
        "--debug",
        action="store_true", 
        help="Enable debug logging"
    )
    
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Set logging level"
    )
    
    # Strategy-specific options
    parser.add_argument(
        "--volatility-off",
        action="store_true",
        help="Disable volatility-based position sizing (ST0CKA)"
    )
    
    parser.add_argument(
        "--mean-reversion",
        action="store_true", 
        help="Enable mean reversion mode (ST0CKA)"
    )
    
    # Parse arguments
    args = parser.parse_args()
    
    # Set log level
    log_level = "DEBUG" if args.debug else args.log_level
    
    # Set strategy-specific environment variables
    if args.volatility_off:
        os.environ["USE_VOLATILITY_SIZING"] = "false"
    
    if args.mean_reversion:
        os.environ["USE_MEAN_REVERSION"] = "true"
    
    # Run the strategy
    success = run_strategy(
        args.strategy,
        paper_trading=not args.live,
        log_level=log_level
    )
    
    if success:
        print("\n✅ Strategy completed successfully")
        sys.exit(0)
    else:
        print("\n❌ Strategy failed")
        sys.exit(1)


if __name__ == "__main__":
    main()