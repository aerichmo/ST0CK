import os
import json
import subprocess
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import logging
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


class MCPMarketDataProvider:
    """
    Market data provider using Alpaca MCP server.
    Provides a simplified interface to Alpaca's market data API.
    """
    
    def __init__(self):
        """Initialize MCP Market Data Provider."""
        self.mcp_server_path = os.path.expanduser("~/alpaca-mcp-server")
        self._verify_mcp_installation()
        
    def _verify_mcp_installation(self):
        """Verify MCP server is installed."""
        if not os.path.exists(self.mcp_server_path):
            raise RuntimeError(
                "Alpaca MCP server not found. Please install it first:\n"
                "git clone https://github.com/alpacahq/alpaca-mcp-server.git ~/alpaca-mcp-server"
            )
    
    def _call_mcp(self, method: str, **kwargs) -> Dict:
        """Call MCP server method."""
        try:
            cmd = ["python", "-m", "alpaca_mcp_server.client", method]
            
            for key, value in kwargs.items():
                cmd.extend([f"--{key}", str(value)])
            
            result = subprocess.run(
                cmd,
                cwd=self.mcp_server_path,
                capture_output=True,
                text=True,
                timeout=30,
                env={
                    **os.environ,
                    "ALPACA_API_KEY": os.getenv("ALPACA_API_KEY"),
                    "ALPACA_SECRET_KEY": os.getenv("ALPACA_API_SECRET"),
                    "PAPER": "True"
                }
            )
            
            if result.returncode != 0:
                raise RuntimeError(f"MCP call failed: {result.stderr}")
            
            return json.loads(result.stdout) if result.stdout else {}
            
        except json.JSONDecodeError:
            return {"response": result.stdout}
        except Exception as e:
            logger.error(f"MCP call failed: {e}")
            raise
    
    def get_stock_quote(self, symbol: str) -> Dict[str, float]:
        """Get current stock quote through MCP."""
        try:
            response = self._call_mcp("get_stock_quote", symbol=symbol)
            
            if response and "quote" in response:
                quote = response["quote"]
                return {
                    "price": float(quote.get("last_price", 0)),
                    "bid": float(quote.get("bid_price", 0)),
                    "ask": float(quote.get("ask_price", 0)),
                    "volume": int(quote.get("volume", 0)),
                    "high": float(quote.get("high", 0)),
                    "low": float(quote.get("low", 0)),
                    "open": float(quote.get("open", 0))
                }
            
            return {}
            
        except Exception as e:
            logger.error(f"Failed to get stock quote for {symbol}: {e}")
            return {}
    
    def get_stock_bars(
        self,
        symbol: str,
        timeframe: str = "5Min",
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        limit: int = 100
    ) -> pd.DataFrame:
        """Get historical stock bars through MCP."""
        try:
            # Convert timeframe to MCP format
            timeframe_map = {
                "1Min": "1min",
                "5Min": "5min",
                "15Min": "15min",
                "1Hour": "1hour",
                "1Day": "1day"
            }
            mcp_timeframe = timeframe_map.get(timeframe, "5min")
            
            # Format dates
            if not start:
                start = datetime.now() - timedelta(days=1)
            if not end:
                end = datetime.now()
            
            response = self._call_mcp(
                "get_stock_bars",
                symbol=symbol,
                timeframe=mcp_timeframe,
                start=start.isoformat(),
                end=end.isoformat(),
                limit=limit
            )
            
            if response and "bars" in response:
                bars = response["bars"]
                df = pd.DataFrame(bars)
                if not df.empty:
                    df['timestamp'] = pd.to_datetime(df['timestamp'])
                    df.set_index('timestamp', inplace=True)
                    df = df[['open', 'high', 'low', 'close', 'volume']]
                    return df
            
            return pd.DataFrame()
            
        except Exception as e:
            logger.error(f"Failed to get stock bars for {symbol}: {e}")
            return pd.DataFrame()
    
    def get_option_chain(
        self,
        symbol: str,
        expiration: Optional[str] = None
    ) -> Dict[str, pd.DataFrame]:
        """Get option chain through MCP."""
        try:
            kwargs = {"symbol": symbol}
            if expiration:
                kwargs["expiration"] = expiration
            
            response = self._call_mcp("get_option_chain", **kwargs)
            
            if response and "options" in response:
                options = response["options"]
                
                # Separate calls and puts
                calls = []
                puts = []
                
                for option in options:
                    opt_data = {
                        "strike": float(option.get("strike", 0)),
                        "bid": float(option.get("bid_price", 0)),
                        "ask": float(option.get("ask_price", 0)),
                        "last": float(option.get("last_price", 0)),
                        "volume": int(option.get("volume", 0)),
                        "open_interest": int(option.get("open_interest", 0)),
                        "implied_volatility": float(option.get("implied_volatility", 0)),
                        "delta": float(option.get("delta", 0)),
                        "gamma": float(option.get("gamma", 0)),
                        "theta": float(option.get("theta", 0)),
                        "vega": float(option.get("vega", 0))
                    }
                    
                    if option.get("type") == "call":
                        calls.append(opt_data)
                    else:
                        puts.append(opt_data)
                
                return {
                    "calls": pd.DataFrame(calls).set_index("strike") if calls else pd.DataFrame(),
                    "puts": pd.DataFrame(puts).set_index("strike") if puts else pd.DataFrame()
                }
            
            return {"calls": pd.DataFrame(), "puts": pd.DataFrame()}
            
        except Exception as e:
            logger.error(f"Failed to get option chain for {symbol}: {e}")
            return {"calls": pd.DataFrame(), "puts": pd.DataFrame()}
    
    def get_option_quote(
        self,
        symbol: str,
        expiration: str,
        strike: float,
        option_type: str
    ) -> Dict[str, float]:
        """Get option quote through MCP."""
        try:
            # Format option symbol for Alpaca
            exp_date = datetime.strptime(expiration, "%Y-%m-%d").strftime("%y%m%d")
            strike_str = f"{int(strike * 1000):08d}"
            option_symbol = f"{symbol}{exp_date}{option_type[0].upper()}{strike_str}"
            
            response = self._call_mcp("get_option_quote", symbol=option_symbol)
            
            if response and "quote" in response:
                quote = response["quote"]
                return {
                    "bid": float(quote.get("bid_price", 0)),
                    "ask": float(quote.get("ask_price", 0)),
                    "last": float(quote.get("last_price", 0)),
                    "volume": int(quote.get("volume", 0)),
                    "open_interest": int(quote.get("open_interest", 0)),
                    "implied_volatility": float(quote.get("implied_volatility", 0)),
                    "delta": float(quote.get("delta", 0)),
                    "gamma": float(quote.get("gamma", 0)),
                    "theta": float(quote.get("theta", 0)),
                    "vega": float(quote.get("vega", 0))
                }
            
            return {}
            
        except Exception as e:
            logger.error(f"Failed to get option quote: {e}")
            return {}
    
    def get_market_hours(self, date: Optional[datetime] = None) -> Dict[str, datetime]:
        """Get market hours for a given date."""
        try:
            if not date:
                date = datetime.now()
            
            response = self._call_mcp(
                "get_market_calendar",
                date=date.strftime("%Y-%m-%d")
            )
            
            if response and "market_hours" in response:
                hours = response["market_hours"]
                return {
                    "open": datetime.fromisoformat(hours.get("open")),
                    "close": datetime.fromisoformat(hours.get("close")),
                    "is_open": hours.get("is_open", False)
                }
            
            # Default market hours if API fails
            market_open = date.replace(hour=9, minute=30, second=0)
            market_close = date.replace(hour=16, minute=0, second=0)
            
            return {
                "open": market_open,
                "close": market_close,
                "is_open": date.weekday() < 5  # Mon-Fri
            }
            
        except Exception as e:
            logger.error(f"Failed to get market hours: {e}")
            # Return default hours
            if not date:
                date = datetime.now()
            return {
                "open": date.replace(hour=9, minute=30, second=0),
                "close": date.replace(hour=16, minute=0, second=0),
                "is_open": date.weekday() < 5
            }
    
    def scan_pre_market_gaps(self, symbols: List[str], min_gap_pct: float = 2.0) -> List[Dict]:
        """Scan for pre-market gaps using MCP."""
        gaps = []
        
        for symbol in symbols:
            try:
                # Get yesterday's close
                yesterday = datetime.now() - timedelta(days=1)
                bars = self.get_stock_bars(symbol, "1Day", yesterday, yesterday, 1)
                
                if bars.empty:
                    continue
                
                prev_close = bars.iloc[-1]['close']
                
                # Get current pre-market quote
                quote = self.get_stock_quote(symbol)
                current_price = quote.get('price', 0)
                
                if current_price and prev_close:
                    gap_pct = ((current_price - prev_close) / prev_close) * 100
                    
                    if abs(gap_pct) >= min_gap_pct:
                        gaps.append({
                            'symbol': symbol,
                            'gap_pct': gap_pct,
                            'prev_close': prev_close,
                            'current_price': current_price
                        })
                
            except Exception as e:
                logger.error(f"Error scanning {symbol}: {e}")
                continue
        
        return sorted(gaps, key=lambda x: abs(x['gap_pct']), reverse=True)
    
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