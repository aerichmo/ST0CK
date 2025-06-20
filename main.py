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
    parser.add_argument('--capital', type=float, default=100000,
                      help='Initial trading capital (default: 100000)')
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
        broker = PaperTradingBroker(initial_capital=args.capital)
    else:
        logger.error("Live trading requires MCP broker. Use --broker mcp")
        sys.exit(1)
    
    try:
        engine = TradingEngine(
            config=TRADING_CONFIG,
            broker=broker,
            db_connection_string=args.db,
            initial_equity=args.capital
        )
        
        logger.info(f"Trading engine initialized with ${args.capital:,.2f} capital")
        logger.info("Press Ctrl+C to stop")
        
        engine.run_trading_loop()
        
    except KeyboardInterrupt:
        logger.info("Shutdown requested by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()