#!/usr/bin/env python3
"""
Multi-bot launcher for ST0CK trading system
Supports running multiple bots with different strategies
"""

import sys
import os
import argparse
import logging
import importlib
from datetime import datetime
from dotenv import load_dotenv
import time
from typing import Dict, Any, Type
import pytz
import atexit

# Bot version
VERSION = "1.0.0"

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.alpaca_broker import AlpacaBroker
from src.multi_bot_database import MultiBotDatabaseManager
from src.performance_config import configure_logging
from src.base_engine import BaseEngine

load_dotenv()

logger = logging.getLogger(__name__)

# Bot Registry - Centralized bot configuration
BOT_REGISTRY = {
    'st0cka': {
        'engine_class': 'src.st0cka_engine.ST0CKAEngine',
        'api_key_env': 'ST0CKAKEY',
        'secret_key_env': 'ST0CKASECRET',
        'config_module': 'bots.st0cka.config',
        'config_name': 'ST0CKA_CONFIG'
    },
    'st0ckg': {
        'engine_class': 'src.st0ckg_engine.ST0CKGEngine',
        'api_key_env': 'ST0CKGKEY',
        'secret_key_env': 'ST0CKGSECRET',
        'config_module': 'bots.st0ckg.config',
        'config_name': 'ST0CKG_CONFIG'
    }
}


def create_pid_file(bot_id: str) -> str:
    """Create PID file to prevent duplicate instances"""
    pid_dir = "/tmp/st0ck"
    os.makedirs(pid_dir, exist_ok=True)
    pid_file = os.path.join(pid_dir, f"{bot_id}.pid")
    
    # Check if PID file exists
    if os.path.exists(pid_file):
        try:
            with open(pid_file, 'r') as f:
                old_pid = int(f.read().strip())
            
            # Check if process is still running
            try:
                os.kill(old_pid, 0)  # This doesn't kill, just checks if process exists
                raise RuntimeError(f"{bot_id} is already running with PID {old_pid}")
            except OSError:
                # Process doesn't exist, remove stale PID file
                logger.warning(f"Removing stale PID file for {bot_id}")
                os.remove(pid_file)
        except Exception as e:
            logger.error(f"Error checking PID file: {e}")
    
    # Write current PID
    current_pid = os.getpid()
    with open(pid_file, 'w') as f:
        f.write(str(current_pid))
    
    # Register cleanup function
    def cleanup_pid_file():
        try:
            if os.path.exists(pid_file):
                os.remove(pid_file)
                logger.info(f"Removed PID file for {bot_id}")
        except Exception as e:
            logger.error(f"Error removing PID file: {e}")
    
    atexit.register(cleanup_pid_file)
    logger.info(f"Created PID file for {bot_id} with PID {current_pid}")
    return pid_file


class BotLauncher:
    """Manages launching and running multiple trading bots"""
    
    def __init__(self, bot_id: str):
        self.bot_id = bot_id
        self.engine = None
        self.config = None
        self.broker = None
        self.is_running = False
        self.pid_file = None
        self.db_url = os.getenv('DATABASE_URL', 'sqlite:///trading_multi.db')
        
        # Get bot info from registry
        if bot_id not in BOT_REGISTRY:
            raise ValueError(f"Unknown bot: {bot_id}")
        self.bot_info = BOT_REGISTRY[bot_id]
        
    def load_bot_config(self) -> Dict[str, Any]:
        """Load bot-specific configuration"""
        try:
            # Import config module
            config_module = importlib.import_module(self.bot_info['config_module'])
            self.config = getattr(config_module, self.bot_info['config_name'])
            
            # Replace API keys with environment variables
            api_key = os.getenv(self.bot_info['api_key_env'])
            secret_key = os.getenv(self.bot_info['secret_key_env'])
            
            self.config['alpaca']['api_key'] = api_key
            self.config['alpaca']['secret_key'] = secret_key
            self.config['alpaca']['base_url'] = os.getenv('ALPACA_BASE_URL', 'https://api.alpaca.markets')
            
            logger.info(f"Loaded configuration for {self.bot_id}")
            return self.config
            
        except Exception as e:
            logger.error(f"Failed to load config for {self.bot_id}: {e}")
            raise
    
    def create_broker(self) -> AlpacaBroker:
        """Create bot-specific broker instance"""
        if not self.broker:
            self.broker = AlpacaBroker(
                api_key=self.config['alpaca']['api_key'],
                secret_key=self.config['alpaca']['secret_key'],
                base_url=self.config['alpaca'].get('base_url'),
                paper=self.config['alpaca'].get('paper', True)
            )
        return self.broker
    
    def create_engine(self) -> BaseEngine:
        """Create trading engine using factory pattern"""
        try:
            # Dynamically import engine class
            module_path, class_name = self.bot_info['engine_class'].rsplit('.', 1)
            engine_module = importlib.import_module(module_path)
            engine_class = getattr(engine_module, class_name)
            
            # Create engine instance
            self.engine = engine_class(
                config=self.config,
                capital=self.config['capital'],
                db_connection_string=self.db_url
            )
            
            return self.engine
            
        except Exception as e:
            logger.error(f"Failed to create engine for {self.bot_id}: {e}")
            raise
    
    def run_startup_checks(self) -> bool:
        """Run startup sanity checks"""
        logger.info(f"Running startup checks for {self.bot_id}")
        
        try:
            # Check database connectivity first (before creating engine)
            db = MultiBotDatabaseManager(self.db_url, self.bot_id)
            try:
                db.engine.execute("SELECT 1")
                logger.info("✓ Database connectivity verified")
            except Exception as e:
                logger.error(f"Database connection failed: {e}")
                return False
            
            # Check configuration validity
            config_module = self.bot_info['config_module']
            if config_module:
                try:
                    mod = importlib.import_module(config_module)
                    if hasattr(mod, 'validate_config'):
                        mod.validate_config(self.config)
                        logger.info("✓ Configuration validated")
                except Exception as e:
                    logger.error(f"Configuration validation failed: {e}")
                    return False
            
            logger.info(f"All startup checks passed for {self.bot_id}")
            return True
            
        except Exception as e:
            logger.error(f"Startup checks failed with error: {e}")
            return False
    
    def run(self):
        """Run the bot"""
        try:
            # Create PID file to prevent duplicate instances
            try:
                self.pid_file = create_pid_file(self.bot_id)
            except RuntimeError as e:
                logger.error(str(e))
                return
            
            # Load configuration
            self.load_bot_config()
            
            # Check if bot is active
            if not self.config.get('active', True):
                logger.info(f"Bot {self.bot_id} is not active, skipping")
                return
            
            # Validate API credentials
            if not self.config['alpaca']['api_key'] or not self.config['alpaca']['secret_key']:
                logger.error(f"API credentials not found for {self.bot_id}")
                return
            
            # Run startup checks (before broker connection)
            if not self.run_startup_checks():
                logger.error(f"Startup checks failed for {self.bot_id}")
                return
            
            # Create and connect broker
            broker = self.create_broker()
            if not broker.connect():
                logger.error("Failed to connect to Alpaca")
                return
                
            # Get account info and set capital
            account_info = broker.get_account_info()
            if not account_info:
                logger.error("Failed to get account info from Alpaca")
                return
                
            self.config['capital'] = account_info['cash']
            logger.info(f"Using Alpaca account capital: ${self.config['capital']:,.2f}")
            
            # Create engine with actual capital
            self.create_engine()
            
            # Log version and start time
            start_time = datetime.now()
            logger.info(f"Starting {self.bot_id} v{VERSION} at {start_time.strftime('%Y-%m-%d %H:%M:%S %Z')}")
            logger.info(f"Configuration: bot_id={self.bot_id}, strategy={self.config.get('strategy_name', 'Unknown')}")
            logger.info(f"Capital: ${self.config['capital']:,.2f}")
            
            self.is_running = True
            
            # Check market hours once at startup
            et_tz = pytz.timezone('America/New_York')
            now_et = datetime.now(et_tz)
            
            if now_et.weekday() >= 5:
                logger.info("Today is weekend - market is closed. Exiting.")
                return
            elif now_et.hour < 8:
                logger.info("Too early to start. Bot should be scheduled closer to market open.")
                return
            elif now_et.hour >= 17:
                logger.info("Market has closed for the day. Exiting.")
                return
            
            # Main trading loop
            logger.info(f"Starting main trading loop for {self.bot_id}")
            last_status_log = datetime.now()
            
            while self.is_running:
                try:
                    # Engine handles its own market hours checking
                    self.engine.run_trading_cycle()
                    
                    # Log status occasionally outside market hours
                    now_et = datetime.now(et_tz)
                    if now_et.weekday() >= 5 or now_et.hour < 9 or now_et.hour >= 16:
                        if (datetime.now() - last_status_log).total_seconds() > 300:
                            logger.info(f"Waiting for market hours... (current: {now_et.strftime('%I:%M %p')} ET)")
                            last_status_log = datetime.now()
                    
                    # Sleep interval - 1 second for responsive trading
                    time.sleep(1)
                        
                except KeyboardInterrupt:
                    raise
                except Exception as e:
                    logger.error(f"Error in {self.bot_id} trading cycle: {e}")
                    time.sleep(5)
                    
        except KeyboardInterrupt:
            logger.info(f"Shutdown requested for {self.bot_id}")
        except Exception as e:
            logger.error(f"Fatal error in {self.bot_id}: {e}", exc_info=True)
        finally:
            if self.engine:
                self.engine.shutdown()
            self.is_running = False


def list_bots():
    """List all registered bots"""
    db = MultiBotDatabaseManager(os.getenv('DATABASE_URL', 'sqlite:///trading_multi.db'))
    bots = db.list_active_bots()
    
    print("\nRegistered Bots:")
    print("-" * 70)
    print(f"{'ID':<10} {'Name':<30} {'Strategy':<30}")
    print("-" * 70)
    
    for bot in bots:
        print(f"{bot['bot_id']:<10} {bot['bot_name']:<30} {bot['strategy_type']:<30}")
    
    # Also show available bots from registry
    print("\nAvailable Bots in Registry:")
    print("-" * 70)
    for bot_id in BOT_REGISTRY:
        print(f"{bot_id:<10} (configured)")
    print("-" * 70)


def main():
    parser = argparse.ArgumentParser(description='Multi-Bot Trading System Launcher')
    
    # Get available bots from registry
    available_bots = list(BOT_REGISTRY.keys()) + ['all']
    parser.add_argument('bot', choices=available_bots,
                      help='Which bot to run (or "all" for all active bots)')
    parser.add_argument('--list', action='store_true',
                      help='List all registered bots')
    
    args = parser.parse_args()
    
    # Create logs directory
    os.makedirs('logs', exist_ok=True)
    
    # Configure logging
    log_name = args.bot if args.bot != 'all' else 'multi'
    configure_logging(log_name)
    
    if args.list:
        list_bots()
        return
    
    if args.bot == 'all':
        # TODO: Implement multi-bot execution with multiprocessing
        logger.error("Running all bots not yet implemented - run individually for now")
    else:
        # Run single bot
        launcher = BotLauncher(args.bot)
        launcher.run()


if __name__ == "__main__":
    main()