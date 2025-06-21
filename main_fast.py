#!/usr/bin/env python3
"""
Fast, lean entry point for ST0CK trading bot
Optimized for minimal latency
"""

import sys
import os
import logging
import time
from datetime import datetime
from dotenv import load_dotenv

from config.trading_config import TRADING_CONFIG
from src.fast_trading_engine import FastTradingEngine

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s.%(msecs)03d - %(name)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)

logger = logging.getLogger(__name__)

def main():
    """Fast main with minimal overhead"""
    
    # Get configuration
    capital = float(os.getenv('TRADING_CAPITAL', '5000'))
    db_url = os.getenv('DATABASE_URL', 'sqlite:///trading.db')
    
    # Validate environment
    if not os.getenv('APCA_API_KEY_ID') or not os.getenv('APCA_API_SECRET_KEY'):
        logger.error("Alpaca API credentials not found in environment")
        sys.exit(1)
    
    logger.info(f"Starting FAST trading engine with ${capital:,.2f}")
    
    try:
        # Initialize engine
        engine = FastTradingEngine(
            config=TRADING_CONFIG,
            capital=capital,
            db_connection_string=db_url
        )
        
        logger.info("Fast engine initialized - entering trading loop")
        logger.info("Press Ctrl+C to stop")
        
        # Main trading loop
        while True:
            try:
                # Only run during market hours
                now = datetime.now()
                if now.weekday() < 5 and 9 <= now.hour < 16:
                    engine.run_trading_cycle()
                    
                # Fast cycle - 1 second intervals during trading window
                if 9 <= now.hour <= 10 and now.minute <= 30:
                    time.sleep(1)  # 1 second during active trading
                else:
                    time.sleep(5)  # 5 seconds outside window
                    
            except KeyboardInterrupt:
                raise
            except Exception as e:
                logger.error(f"Error in trading cycle: {e}")
                time.sleep(5)  # Brief pause on error
        
    except KeyboardInterrupt:
        logger.info("Shutdown requested")
        if 'engine' in locals():
            engine.shutdown()
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()