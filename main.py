#!/usr/bin/env python3

import sys
import argparse
import logging
from dotenv import load_dotenv

from config.trading_config import TRADING_CONFIG
from src.trading_engine import TradingEngine
from src.broker_interface import PaperTradingBroker
from src.mcp_broker import MCPBroker

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

def main():
    parser = argparse.ArgumentParser(description='Options Scalping Trading Engine')
    parser.add_argument('--mode', choices=['paper', 'live'], default='paper',
                      help='Trading mode (default: paper)')
    parser.add_argument('--capital', type=float, default=None,
                      help='Initial trading capital (default: fetch from broker)')
    parser.add_argument('--db', type=str, 
                      default='postgresql://localhost/options_scalper',
                      help='Database connection string')
    parser.add_argument('--broker', choices=['mcp', 'paper'], default='mcp',
                      help='Broker implementation to use (default: mcp)')
    
    args = parser.parse_args()
    
    if args.broker == 'mcp':
        logger.info(f"Starting with MCP broker in {args.mode.upper()} mode")
        broker = MCPBroker(mode=args.mode)
    elif args.mode == 'paper':
        logger.info("Starting with built-in PAPER TRADING broker")
        initial_capital = args.capital if args.capital else 100000
        broker = PaperTradingBroker(initial_capital=initial_capital)
    else:
        logger.error("Live trading requires MCP broker. Use --broker mcp")
        sys.exit(1)
    
    try:
        # Connect to broker first
        if not broker.connect():
            logger.error("Failed to connect to broker")
            sys.exit(1)
        
        # Fetch actual account balance if not specified
        if args.capital is None:
            account_info = broker.get_account_info()
            if account_info:
                capital = account_info.get('buying_power', account_info.get('cash', 0))
                logger.info(f"Fetched account balance: ${capital:,.2f}")
            else:
                logger.error("Failed to fetch account balance")
                sys.exit(1)
        else:
            capital = args.capital
        
        engine = TradingEngine(
            config=TRADING_CONFIG,
            broker=broker,
            db_connection_string=args.db,
            initial_equity=capital
        )
        
        logger.info(f"Trading engine initialized with ${capital:,.2f} capital")
        logger.info("Press Ctrl+C to stop")
        
        engine.run_trading_loop()
        
    except KeyboardInterrupt:
        logger.info("Shutdown requested by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()