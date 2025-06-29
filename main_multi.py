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
from typing import Dict, Any
import pytz

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.alpaca_broker import AlpacaBroker
from src.multi_bot_database import MultiBotDatabaseManager
from src.unified_market_data import UnifiedMarketData
from src.performance_config import configure_logging

load_dotenv()

logger = logging.getLogger(__name__)


class BotLauncher:
    """Manages launching and running multiple trading bots"""
    
    def __init__(self, bot_id: str):
        self.bot_id = bot_id
        self.engine = None
        self.config = None
        self.is_running = False
        
    def load_bot_config(self) -> Dict[str, Any]:
        """Load bot-specific configuration"""
        try:
            config_module = importlib.import_module(f'bots.{self.bot_id}.config')
            config_name = f'{self.bot_id.upper()}_CONFIG'
            self.config = getattr(config_module, config_name)
            
            # Replace API keys with environment variables
            if self.bot_id == 'st0ckg':
                api_key_env = 'ST0CKGKEY'
                secret_key_env = 'ST0CKGSECRET'
            elif self.bot_id == 'st0cka':
                api_key_env = 'ST0CKAKEY'
                secret_key_env = 'ST0CKASECRET'
            else:
                api_key_env = f'{self.bot_id.upper()}_KEY'
                secret_key_env = f'{self.bot_id.upper()}_SECRET'
            
            self.config['alpaca']['api_key'] = os.getenv(api_key_env)
            self.config['alpaca']['secret_key'] = os.getenv(secret_key_env)
            self.config['alpaca']['base_url'] = os.getenv('ALPACA_BASE_URL', 'https://api.alpaca.markets')
            
            # Capital will be fetched from Alpaca account later
            # Remove any hardcoded capital values
            logger.info(f"Loaded configuration for {self.bot_id}")
            return self.config
            
        except Exception as e:
            logger.error(f"Failed to load config for {self.bot_id}: {e}")
            raise
    
    def create_broker(self) -> AlpacaBroker:
        """Create bot-specific broker instance"""
        return AlpacaBroker(
            api_key=self.config['alpaca']['api_key'],
            secret_key=self.config['alpaca']['secret_key'],
            base_url=self.config['alpaca'].get('base_url'),
            paper=self.config['alpaca'].get('paper', True)
        )
    
    def create_database(self) -> MultiBotDatabaseManager:
        """Create database manager with bot context"""
        db_url = os.getenv('DATABASE_URL', 'sqlite:///trading_multi.db')
        return MultiBotDatabaseManager(
            connection_string=db_url,
            bot_id=self.bot_id
        )
    
    def load_strategy(self):
        """Load bot-specific strategy"""
        try:
            # Import strategy module
            strategy_module = importlib.import_module(f'bots.{self.bot_id}.strategy')
            
            # Find strategy class (first class that inherits from BaseStrategy)
            from bots.base.strategy import BaseStrategy
            
            for name, obj in strategy_module.__dict__.items():
                if isinstance(obj, type) and issubclass(obj, BaseStrategy) and obj != BaseStrategy:
                    strategy_class = obj
                    return strategy_class(self.bot_id, self.config)
            
            raise ValueError(f"No strategy class found for {self.bot_id}")
            
        except Exception as e:
            logger.error(f"Failed to load strategy for {self.bot_id}: {e}")
            raise
    
    def create_engine(self):
        """Create trading engine for this bot"""
        try:
            if self.bot_id == 'st0ckg':
                from src.st0ckg_engine import ST0CKGEngine
                
                self.engine = ST0CKGEngine(
                    config=self.config,
                    capital=self.config['capital'],
                    db_connection_string=os.getenv('DATABASE_URL', 'sqlite:///trading_multi.db')
                )
            elif self.bot_id == 'st0cka':
                # ST0CKA uses unified simple engine
                from src.unified_simple_engine import UnifiedSimpleEngine
                
                # Add ST0CKA-specific configuration
                self.config['engine_mode'] = 'simple'
                self.config['symbol'] = 'SPY'
                self.config['use_market_data'] = True
                self.config['auto_shutdown'] = True
                self.config['profit_target'] = 0.01
                
                self.engine = UnifiedSimpleEngine(
                    config=self.config,
                    capital=self.config['capital'],
                    db_connection_string=os.getenv('DATABASE_URL', 'sqlite:///trading_multi.db')
                )
            else:
                logger.error(f"Engine not implemented for {self.bot_id}")
                raise NotImplementedError(f"Engine not implemented for {self.bot_id}")
                
        except Exception as e:
            logger.error(f"Failed to create engine for {self.bot_id}: {e}")
            raise
    
    def run(self):
        """Run the bot"""
        try:
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
            
            # Create broker first to get account info
            broker = self.create_broker()
            if broker.connect():
                account_info = broker.get_account_info()
                if account_info:
                    # Use actual account capital
                    self.config['capital'] = account_info['cash']
                    logger.info(f"Using Alpaca account capital: ${self.config['capital']:,.2f}")
                else:
                    logger.error("Failed to get account info from Alpaca")
                    return
            else:
                logger.error("Failed to connect to Alpaca")
                return
            
            # Create engine with actual capital
            self.create_engine()
            
            logger.info(f"Starting {self.bot_id} with ${self.config['capital']:,.2f} capital")
            self.is_running = True
            
            # Log initial status and check if we should wait
            et_tz = pytz.timezone('America/New_York')
            now_et = datetime.now(et_tz)
            now_utc = datetime.now(pytz.UTC)
            
            logger.info(f"Current time: {now_et.strftime('%I:%M %p')} ET / {now_utc.strftime('%I:%M %p')} UTC")
            logger.info(f"Weekday: {now_et.weekday()} (0=Monday, 6=Sunday)")
            logger.info(f"Hour: {now_et.hour}")
            
            if now_et.weekday() >= 5:
                logger.info("Today is weekend - market is closed. Exiting.")
                return
            elif now_et.hour < 8:  # Before 8 AM ET
                logger.info(f"Too early to start. Bot should be scheduled closer to market open.")
                return
            elif now_et.hour >= 17:  # After 5 PM ET
                logger.info(f"Market has closed for the day. Exiting.")
                return
            elif now_et.hour < 9 or now_et.hour >= 16:
                logger.info(f"Outside market hours. Waiting for market open at 9:30 AM ET...")
            
            last_status_log = datetime.now()
            
            logger.info(f"About to start main trading loop for {self.bot_id}")
            logger.info(f"is_running = {self.is_running}")
            logger.info(f"engine = {self.engine}")
            
            # Main trading loop
            logger.info(f"Starting main trading loop for {self.bot_id}")
            while self.is_running:
                try:
                    # Only run during market hours (Eastern Time)
                    now_et = datetime.now(et_tz)
                    if now_et.weekday() < 5 and 9 <= now_et.hour < 16:
                        self.engine.run_trading_cycle()
                    else:
                        # Log status every 5 minutes
                        if (datetime.now() - last_status_log).total_seconds() > 300:
                            if now_et.weekday() >= 5:
                                logger.info("Waiting... (weekend - market closed)")
                            else:
                                logger.info(f"Waiting for market hours... (current time: {now_et.strftime('%I:%M %p')} ET)")
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


def main():
    parser = argparse.ArgumentParser(description='Multi-Bot Trading System Launcher')
    parser.add_argument('bot', choices=['st0ckg', 'st0cka', 'all'],
                      help='Which bot to run (or "all" for all active bots)')
    parser.add_argument('--list', action='store_true',
                      help='List all registered bots')
    
    args = parser.parse_args()
    
    # Create logs directory
    os.makedirs('logs', exist_ok=True)
    
    # Configure logging with bot_id
    if args.bot and args.bot != 'all':
        configure_logging(args.bot)
    else:
        configure_logging('multi')
    
    if args.list:
        # List all bots
        db = MultiBotDatabaseManager(os.getenv('DATABASE_URL', 'sqlite:///trading_multi.db'))
        bots = db.list_active_bots()
        print("\nRegistered Bots:")
        print("-" * 60)
        for bot in bots:
            print(f"ID: {bot['bot_id']:<10} Name: {bot['bot_name']:<30} Strategy: {bot['strategy_type']}")
        print("-" * 60)
        return
    
    # Market data initialization moved to individual bots
    # Each bot will initialize its own market data as needed
    
    if args.bot == 'all':
        # Run all active bots (would need multiprocessing for true parallel execution)
        logger.error("Running all bots not yet implemented - run individually for now")
    else:
        # Run single bot
        launcher = BotLauncher(args.bot)
        launcher.run()


if __name__ == "__main__":
    main()