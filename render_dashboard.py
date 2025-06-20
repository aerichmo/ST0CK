#!/usr/bin/env python3
"""
Simplified dashboard entry point for Render deployment.
This version doesn't require live trading engine connection.
"""

import os
import sys
import logging
from dotenv import load_dotenv

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config.trading_config import TRADING_CONFIG
from src.mcp_market_data import MCPMarketDataProvider
from src.market_data import MarketDataProvider
from src.database import DatabaseManager
from src.web_dashboard import TradingDashboard

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def main():
    """Run the dashboard for Render deployment."""
    try:
        # Get database URL from environment
        db_url = os.environ.get('DATABASE_URL', 'postgresql://localhost/options_scalper')
        
        # Convert Render's postgres:// to postgresql://
        if db_url.startswith('postgres://'):
            db_url = db_url.replace('postgres://', 'postgresql://', 1)
        
        # Initialize database (optional - will work without it)
        try:
            db = DatabaseManager(db_url)
            logger.info("Connected to database")
        except Exception as e:
            logger.warning(f"Database connection failed: {e}. Running without database.")
            db = None
        
        # Initialize market data provider
        try:
            # Try MCP first if credentials are available
            if os.environ.get('ALPACA_API_KEY'):
                logger.info("Using MCP market data provider")
                market_data = MCPMarketDataProvider()
            else:
                raise Exception("No Alpaca credentials")
        except Exception as e:
            logger.info("Falling back to Yahoo Finance market data provider")
            market_data = MarketDataProvider(TRADING_CONFIG)
        
        # Initialize dashboard without live engine
        dashboard = TradingDashboard(
            trading_engine=None,  # No live engine for view-only mode
            market_data_provider=market_data,
            db_manager=db
        )
        
        # Get port from environment
        port = int(os.environ.get('PORT', 8050))
        
        logger.info(f"Starting dashboard on port {port}")
        
        # Run dashboard
        dashboard.run(host='0.0.0.0', port=port, debug=False)
        
    except Exception as e:
        logger.error(f"Failed to start dashboard: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()