#!/usr/bin/env python3
"""
ST0CK Real-Time Trading Visualizer

This script provides real-time visualization of SPY trading activity,
showing candlestick charts, technical indicators, and trade executions.
"""

import sys
import argparse
import logging
from dotenv import load_dotenv
import threading
import time

from config.trading_config import TRADING_CONFIG
from src.alpaca_market_data import AlpacaMarketDataProvider
from src.database import DatabaseManager
from src.candle_visualizer import CandleVisualizer
from src.web_dashboard import TradingDashboard
from src.trading_engine import TradingEngine
from src.mcp_broker import MCPBroker
from src.broker_interface import PaperTradingBroker

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description='ST0CK Trading Visualizer')
    parser.add_argument('--mode', choices=['matplotlib', 'web'], default='web',
                        help='Visualization mode (default: web)')
    parser.add_argument('--broker', choices=['mcp', 'paper'], default='mcp',
                        help='Broker to use for data (default: mcp)')
    parser.add_argument('--db', type=str, 
                        default='postgresql://localhost/options_scalper',
                        help='Database connection string')
    parser.add_argument('--port', type=int, default=None,
                        help='Port for web dashboard (default: 8050 or $PORT)')
    parser.add_argument('--live', action='store_true',
                        help='Connect to live trading engine')
    
    args = parser.parse_args()
    
    try:
        # Initialize database
        db = DatabaseManager(args.db)
        
        # Initialize market data provider - Alpaca only
        logger.info("Using Alpaca market data provider")
        market_data = AlpacaMarketDataProvider()
        
        # Initialize trading engine if live mode
        engine = None
        if args.live:
            logger.info("Connecting to live trading engine...")
            
            # Initialize broker
            if args.broker == 'mcp':
                broker = MCPBroker(mode='paper')
            else:
                broker = PaperTradingBroker(initial_capital=100000)
            
            # Create trading engine
            engine = TradingEngine(
                config=TRADING_CONFIG,
                broker=broker,
                db_connection_string=args.db,
                initial_equity=100000
            )
            
            # Start engine in separate thread
            engine_thread = threading.Thread(target=engine.run_trading_loop)
            engine_thread.daemon = True
            engine_thread.start()
            
            logger.info("Trading engine started in background")
        
        if args.mode == 'matplotlib':
            logger.info("Starting matplotlib visualizer...")
            
            # Initialize matplotlib visualizer
            visualizer = CandleVisualizer(market_data, db)
            
            # If connected to live engine, link them
            if engine:
                # Hook into engine's trade events
                def on_trade(trade_info):
                    visualizer.add_trade(trade_info)
                
                # This would require modifying the engine to emit events
                # For now, we'll poll the database
                def poll_trades():
                    last_trade_id = None
                    while True:
                        try:
                            trades = db.get_recent_trades(limit=1)
                            if trades and trades[0].get('id') != last_trade_id:
                                trade = trades[0]
                                last_trade_id = trade.get('id')
                                visualizer.add_trade({
                                    'timestamp': trade.get('timestamp'),
                                    'action': trade.get('action'),
                                    'price': trade.get('entry_price', 0),
                                    'quantity': trade.get('quantity', 0)
                                })
                        except:
                            pass
                        time.sleep(1)
                
                poll_thread = threading.Thread(target=poll_trades)
                poll_thread.daemon = True
                poll_thread.start()
            
            # Start visualization
            visualizer.start()
            
        else:  # Web mode
            logger.info(f"Starting web dashboard on port {args.port}...")
            
            # Initialize web dashboard
            dashboard = TradingDashboard(engine, market_data, db)
            
            # Run dashboard
            # Use PORT env variable for cloud deployment, fallback to args.port or 8050
            import os
            port = args.port or int(os.environ.get('PORT', 8050))
            dashboard.run(host='0.0.0.0', port=port, debug=False)
        
    except KeyboardInterrupt:
        logger.info("Visualization stopped by user")
    except Exception as e:
        logger.error(f"Error in visualizer: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()