#!/usr/bin/env python3
"""
Unified multi-bot launcher for ST0CK trading system
Uses the new unified architecture with improved performance
"""

import sys
import os
import argparse
import asyncio
from datetime import datetime
from typing import Dict, Any, List
import signal

# Create logs directory immediately
os.makedirs('logs', exist_ok=True)

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError as e:
    with open('logs/import_error.log', 'w') as f:
        f.write(f"Failed to import dotenv: {e}\n")
        f.write("Run: pip install python-dotenv\n")
    print(f"IMPORT ERROR: {e}")
    sys.exit(1)

# Bot version
VERSION = "2.0.0"

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from src.unified_logging import configure_logging, get_logger
    from src.unified_database import UnifiedDatabaseManager
    from src.unified_engine import UnifiedTradingEngine
    from src.strategies import ST0CKAStrategy, ST0CKGStrategy, ST0CKAGammaStrategy
    from src.error_reporter import ErrorReporter
except ImportError as e:
    with open('logs/import_error.log', 'w') as f:
        f.write(f"Failed to import ST0CK modules: {e}\n")
        f.write(f"Working directory: {os.getcwd()}\n")
        f.write(f"Python path: {sys.path}\n")
        import traceback
        f.write(f"Traceback:\n{traceback.format_exc()}\n")
    print(f"IMPORT ERROR: {e}")
    print("See logs/import_error.log for details")
    sys.exit(1)

# Bot Registry - Maps bot names to strategies
BOT_REGISTRY = {
    'st0cka': {
        'strategy_class': ST0CKAStrategy,
        'strategy_args': {'mode': 'simple'},
        'api_key_env': 'ST0CKAKEY',
        'secret_key_env': 'ST0CKASECRET',
        'description': 'Simple SPY scalping - $0.01 profit target'
    },
    'st0cka_advanced': {
        'strategy_class': ST0CKAStrategy,
        'strategy_args': {'mode': 'advanced'},
        'api_key_env': 'ST0CKAKEY',
        'secret_key_env': 'ST0CKASECRET',
        'description': 'Advanced SPY scalping - Multi-position'
    },
    'st0cka_gamma': {
        'strategy_class': ST0CKAGammaStrategy,
        'strategy_args': {'mode': 'gamma'},
        'api_key_env': 'ST0CKAKEY',
        'secret_key_env': 'ST0CKASECRET',
        'description': 'Gamma scalping - Volatility-based SPY trading'
    },
    'st0cka_options': {
        'strategy_class': 'gamma_scalping',  # Special marker for gamma scalping
        'strategy_args': {},
        'api_key_env': 'ST0CKAKEY',
        'secret_key_env': 'ST0CKASECRET',
        'description': 'True gamma scalping - SPY options straddles with delta hedging'
    },
    'st0ckg': {
        'strategy_class': ST0CKGStrategy,
        'strategy_args': {
            'start_time': '09:40',
            'end_time': '10:30',
            'max_positions': 2
        },
        'api_key_env': 'ST0CKGKEY',
        'secret_key_env': 'ST0CKGSECRET',
        'description': 'Battle Lines 0-DTE options strategy'
    }
}

class BotManager:
    """Manages multiple trading bots"""
    
    def __init__(self):
        self.logger = get_logger(__name__)
        self.bots: Dict[str, UnifiedTradingEngine] = {}
        self.tasks: List[asyncio.Task] = []
        self.shutdown_event = asyncio.Event()
    
    async def start_bot(self, bot_id: str, config: Dict[str, Any]):
        """Start a single bot"""
        try:
            self.logger.info(f"Starting bot: {bot_id}")
            
            # Get API credentials
            api_key = os.getenv(config['api_key_env'])
            api_secret = os.getenv(config['secret_key_env'])
            
            if not api_key or not api_secret:
                raise ValueError(f"Missing API credentials for {bot_id}")
            
            # Create strategy instance
            strategy_class = config['strategy_class']
            strategy_args = config.get('strategy_args', {})
            
            # Special handling for gamma scalping
            if strategy_class == 'gamma_scalping':
                # Launch separate gamma scalping process
                self.logger.info(f"Launching gamma scalping for {bot_id}")
                import subprocess
                gamma_process = subprocess.Popen([
                    sys.executable, 
                    'launch_gamma_scalping.py',
                    '--log-level', args.log_level if 'args' in locals() else 'INFO'
                ])
                self.logger.info(f"Gamma scalping launched with PID: {gamma_process.pid}")
                return
            
            # For ST0CKG, pass database and market data providers
            if strategy_class == ST0CKGStrategy:
                # These will be set by the engine after initialization
                strategy_args['db_manager'] = None
                strategy_args['market_data_provider'] = None
            
            strategy = strategy_class(**strategy_args)
            
            # Create engine
            engine = UnifiedTradingEngine(
                bot_id=bot_id,
                strategy=strategy,
                api_key=api_key,
                api_secret=api_secret,
                database_url=os.getenv('DATABASE_URL'),
                redis_url=os.getenv('REDIS_URL'),
                paper_trading=True
            )
            
            # For ST0CKG, set the database and market data references
            if strategy_class == ST0CKGStrategy:
                strategy.db_manager = engine.db
                strategy.market_data = engine.market_data
                # Also update components that need market data
                strategy.signal_detector.market_data = engine.market_data
                strategy.options_selector.market_data = engine.market_data
                if strategy.data_quality:
                    strategy.data_quality.market_data = engine.market_data
            
            # Initialize engine
            await engine.initialize()
            
            # Store reference
            self.bots[bot_id] = engine
            
            # Create and store task
            task = asyncio.create_task(engine.run())
            self.tasks.append(task)
            
            self.logger.info(f"Bot {bot_id} started successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to start bot {bot_id}: {e}")
            ErrorReporter.report_failure(bot_id, e, {'config': config})
            raise
    
    async def start_all(self, bot_names: List[str]):
        """Start all specified bots"""
        for bot_name in bot_names:
            if bot_name not in BOT_REGISTRY:
                self.logger.error(f"Unknown bot: {bot_name}")
                continue
            
            config = BOT_REGISTRY[bot_name]
            await self.start_bot(bot_name, config)
    
    async def shutdown(self):
        """Shutdown all bots gracefully"""
        self.logger.info("Shutting down all bots...")
        
        # Signal shutdown to all bots
        for bot_id, engine in self.bots.items():
            engine.shutdown_requested = True
        
        # Wait for all tasks to complete
        if self.tasks:
            await asyncio.gather(*self.tasks, return_exceptions=True)
        
        self.logger.info("All bots shut down successfully")
    
    def handle_signal(self, signum, frame):
        """Handle shutdown signals"""
        self.logger.info(f"Received signal {signum}, initiating shutdown...")
        asyncio.create_task(self.shutdown())

async def main():
    """Main entry point"""
    # Create logs directory first thing
    os.makedirs('logs', exist_ok=True)
    
    parser = argparse.ArgumentParser(
        description='ST0CK Unified Trading System',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Available bots:
  st0cka          - Simple SPY scalping ($0.01 profit target)
  st0cka_advanced - Advanced SPY scalping (multi-position)
  st0cka_gamma    - Gamma scalping - Volatility-based SPY trading
  st0cka_options  - True gamma scalping - SPY options straddles with delta hedging
  st0ckg          - Battle Lines 0-DTE options strategy

Examples:
  python main_unified.py st0cka               # Run simple scalping
  python main_unified.py st0cka_gamma         # Run volatility-based scalping
  python main_unified.py st0cka_options       # Run true options gamma scalping
  python main_unified.py st0cka st0ckg        # Run multiple bots
  python main_unified.py --all                 # Run all bots
  python main_unified.py --list                # List available bots
        """
    )
    
    parser.add_argument('bots', nargs='*', help='Bot names to run')
    parser.add_argument('--all', action='store_true', help='Run all registered bots')
    parser.add_argument('--list', action='store_true', help='List available bots')
    parser.add_argument('--version', action='version', version=f'ST0CK v{VERSION}')
    parser.add_argument('--log-level', default='INFO', 
                       choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
                       help='Set logging level')
    parser.add_argument('--no-sentry', action='store_true', 
                       help='Disable Sentry error reporting')
    
    args = parser.parse_args()
    
    # Configure logging
    configure_logging(
        log_level=args.log_level,
        log_to_file=True,  # Ensure file logging is enabled
        sentry_dsn=None if args.no_sentry else os.getenv('SENTRY_DSN')
    )
    
    logger = get_logger(__name__)
    
    # List bots if requested
    if args.list:
        print("\nAvailable bots:")
        for bot_name, config in BOT_REGISTRY.items():
            print(f"  {bot_name:<20} - {config['description']}")
        return
    
    # Determine which bots to run
    if args.all:
        bot_names = list(BOT_REGISTRY.keys())
    elif args.bots:
        bot_names = args.bots
    else:
        parser.print_help()
        return
    
    # Validate bot names
    invalid_bots = [b for b in bot_names if b not in BOT_REGISTRY]
    if invalid_bots:
        logger.error(f"Unknown bots: {', '.join(invalid_bots)}")
        print(f"\nError: Unknown bots: {', '.join(invalid_bots)}")
        print("Use --list to see available bots")
        return
    
    # Create bot manager
    manager = BotManager()
    
    # Setup signal handlers
    signal.signal(signal.SIGINT, manager.handle_signal)
    signal.signal(signal.SIGTERM, manager.handle_signal)
    
    try:
        # Start bots
        logger.info(f"Starting bots: {', '.join(bot_names)}")
        await manager.start_all(bot_names)
        
        # Keep running until shutdown
        await manager.shutdown_event.wait()
        
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        ErrorReporter.report_failure('system', e, {'bots': bot_names})
    finally:
        await manager.shutdown()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except Exception as e:
        # Emergency logging in case of startup failure
        import traceback
        os.makedirs('logs', exist_ok=True)
        with open('logs/startup_error.log', 'w') as f:
            f.write(f"Startup error at {datetime.now()}:\n")
            f.write(f"Error: {str(e)}\n")
            f.write(f"Traceback:\n{traceback.format_exc()}\n")
        print(f"FATAL ERROR: {str(e)}")
        print("See logs/startup_error.log for details")
        sys.exit(1)