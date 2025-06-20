import os
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest, StockLatestQuoteRequest
from alpaca.data.timeframe import TimeFrame

logger = logging.getLogger(__name__)


class AlpacaMarketDataProvider:
    """
    Direct Alpaca market data provider for cloud deployment.
    Uses Alpaca-py SDK directly without MCP server requirement.
    """
    
    def __init__(self):
        """Initialize Alpaca market data client."""
        api_key = os.environ.get('ALPACA_API_KEY')
        api_secret = os.environ.get('ALPACA_API_SECRET')
        
        if not api_key or not api_secret:
            raise ValueError("Alpaca API credentials not found in environment variables")
            
        # Initialize Alpaca data client (no paper/live distinction for market data)
        self.client = StockHistoricalDataClient(api_key, api_secret)
        logger.info("Initialized Alpaca market data provider")
        
    def get_stock_quote(self, symbol: str) -> Dict[str, float]:
        """Get current stock quote from Alpaca."""
        try:
            request = StockLatestQuoteRequest(symbol_or_symbols=symbol)
            quote = self.client.get_stock_latest_quote(request)
            
            if symbol in quote:
                q = quote[symbol]
                return {
                    "price": float(q.ask_price) if q.ask_price else float(q.bid_price),
                    "bid": float(q.bid_price) if q.bid_price else 0,
                    "ask": float(q.ask_price) if q.ask_price else 0,
                    "bid_size": int(q.bid_size) if q.bid_size else 0,
                    "ask_size": int(q.ask_size) if q.ask_size else 0,
                    "timestamp": q.timestamp
                }
            return {}
            
        except Exception as e:
            logger.error(f"Failed to get quote for {symbol}: {e}")
            return {}
    
    def get_stock_bars(
        self,
        symbol: str,
        timeframe: str = "5Min",
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        limit: int = 100
    ) -> pd.DataFrame:
        """Get historical stock bars from Alpaca."""
        try:
            # Map timeframe strings to Alpaca TimeFrame
            timeframe_map = {
                "1Min": TimeFrame.Minute,
                "5Min": TimeFrame(5, "Min"),
                "15Min": TimeFrame(15, "Min"),
                "30Min": TimeFrame(30, "Min"),
                "1Hour": TimeFrame.Hour,
                "1Day": TimeFrame.Day
            }
            
            alpaca_timeframe = timeframe_map.get(timeframe, TimeFrame(5, "Min"))
            
            # Default time range if not specified
            if not end:
                end = datetime.now()
            if not start:
                start = end - timedelta(hours=2)
                
            # Create request
            request = StockBarsRequest(
                symbol_or_symbols=symbol,
                timeframe=alpaca_timeframe,
                start=start,
                end=end,
                limit=limit
            )
            
            # Get bars
            bars = self.client.get_stock_bars(request)
            
            if symbol in bars:
                df = bars[symbol].df
                if not df.empty:
                    # Ensure index is timezone-aware
                    if df.index.tz is None:
                        df.index = df.index.tz_localize('America/New_York')
                    return df
                    
            return pd.DataFrame()
            
        except Exception as e:
            logger.error(f"Failed to get bars for {symbol}: {e}")
            return pd.DataFrame()
    
    def get_opening_range(
        self,
        symbol: str,
        start_time: datetime,
        end_time: datetime
    ) -> Tuple[float, float, float]:
        """Get opening range high, low, and volume."""
        try:
            bars = self.get_stock_bars(
                symbol,
                "1Min",
                start_time,
                end_time,
                limit=10
            )
            
            if not bars.empty:
                high = bars['high'].max()
                low = bars['low'].min()
                volume = bars['volume'].sum()
                return high, low, volume
                
            return 0.0, 0.0, 0.0
            
        except Exception as e:
            logger.error(f"Failed to get opening range for {symbol}: {e}")
            return 0.0, 0.0, 0.0
    
    def get_market_hours(self, date: Optional[datetime] = None) -> Dict[str, datetime]:
        """Get market hours for a given date."""
        # Alpaca market hours (NYSE)
        if not date:
            date = datetime.now()
            
        # Skip weekends
        if date.weekday() >= 5:
            return {
                "open": None,
                "close": None,
                "is_open": False
            }
            
        # Standard market hours
        market_open = date.replace(hour=9, minute=30, second=0, microsecond=0)
        market_close = date.replace(hour=16, minute=0, second=0, microsecond=0)
        
        # Could enhance with Alpaca calendar API if needed
        return {
            "open": market_open,
            "close": market_close,
            "is_open": True
        }