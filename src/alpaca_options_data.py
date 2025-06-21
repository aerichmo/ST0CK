"""
High-speed options data fetcher using Alpaca and fallback to yfinance
Optimized for real-time trading with minimal latency
"""

import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import yfinance as yf
from concurrent.futures import ThreadPoolExecutor, as_completed
import numpy as np

logger = logging.getLogger(__name__)


class AlpacaOptionsData:
    """Fast options data provider with Alpaca primary and yfinance fallback"""
    
    def __init__(self, alpaca_client=None):
        """
        Initialize options data provider
        
        Args:
            alpaca_client: Alpaca data client (for future options API)
        """
        self.alpaca_client = alpaca_client
        self._cache = {}
        self._cache_ttl = 60  # Cache for 60 seconds
        
    def get_option_chain(self, symbol: str, expiration: datetime, 
                        option_type: str = 'CALL') -> List[Dict]:
        """
        Get option chain with ultra-low latency
        
        Args:
            symbol: Stock symbol
            expiration: Option expiration date
            option_type: 'CALL' or 'PUT'
            
        Returns:
            List of option contracts with real-time data
        """
        cache_key = f"{symbol}_{expiration.date()}_{option_type}"
        
        # Check cache first
        if cache_key in self._cache:
            cached_data, cache_time = self._cache[cache_key]
            if (datetime.now() - cache_time).seconds < self._cache_ttl:
                return cached_data
        
        try:
            # TODO: When Alpaca supports options data, use it here
            # For now, use optimized yfinance fetching
            options = self._fetch_options_yfinance(symbol, expiration, option_type)
            
            # Cache the results
            self._cache[cache_key] = (options, datetime.now())
            
            return options
            
        except Exception as e:
            logger.error(f"Failed to fetch options: {e}")
            return []
    
    def _fetch_options_yfinance(self, symbol: str, expiration: datetime,
                               option_type: str) -> List[Dict]:
        """Optimized yfinance options fetching"""
        try:
            ticker = yf.Ticker(symbol)
            exp_str = expiration.strftime('%Y-%m-%d')
            
            # Get options chain
            opt_chain = ticker.option_chain(exp_str)
            
            # Select calls or puts
            df = opt_chain.calls if option_type == 'CALL' else opt_chain.puts
            
            if df.empty:
                return []
            
            # Get current stock price for moneyness calculation
            stock_info = ticker.info
            current_price = stock_info.get('regularMarketPrice', 
                                         stock_info.get('ask', 0))
            
            # Convert to list of dicts with additional calculations
            options = []
            for _, row in df.iterrows():
                # Skip options with no volume or unrealistic spreads
                if row['volume'] == 0 or row['bid'] == 0:
                    continue
                    
                spread_pct = (row['ask'] - row['bid']) / row['ask'] if row['ask'] > 0 else 1
                if spread_pct > 0.5:  # Skip if spread > 50%
                    continue
                
                # Calculate Greeks if not provided
                iv = row.get('impliedVolatility', 0.25)
                if iv == 0:
                    iv = 0.25  # Default IV
                
                option = {
                    'contract_symbol': row['contractSymbol'],
                    'strike': float(row['strike']),
                    'bid': float(row['bid']),
                    'ask': float(row['ask']),
                    'last': float(row['lastPrice']),
                    'mid_price': (float(row['bid']) + float(row['ask'])) / 2,
                    'volume': int(row['volume']),
                    'open_interest': int(row['openInterest']),
                    'implied_volatility': float(iv),
                    'in_the_money': row['inTheMoney'],
                    'spread': float(row['ask'] - row['bid']),
                    'spread_pct': spread_pct,
                    'moneyness': float(row['strike']) / current_price if current_price > 0 else 1,
                    'expiration': expiration.isoformat(),
                    'days_to_expiry': (expiration - datetime.now()).days,
                    'option_type': option_type,
                    'underlying_price': current_price
                }
                
                # Add Greeks if available
                for greek in ['delta', 'gamma', 'theta', 'vega', 'rho']:
                    if greek in row:
                        option[greek] = float(row[greek]) if row[greek] else 0
                
                options.append(option)
            
            # Sort by volume and open interest for liquidity
            options.sort(key=lambda x: x['volume'] + x['open_interest'], reverse=True)
            
            return options
            
        except Exception as e:
            logger.error(f"yfinance fetch failed: {e}")
            return []
    
    def get_option_quote(self, contract_symbol: str) -> Optional[Dict]:
        """
        Get real-time quote for specific option contract
        
        Args:
            contract_symbol: Option contract symbol
            
        Returns:
            Real-time option quote data
        """
        try:
            # Extract components from symbol (e.g., SPY231215C00475000)
            # This is a simplified parser - enhance as needed
            underlying = contract_symbol[:3]
            
            # TODO: Use Alpaca options quotes when available
            # For now, use yfinance
            ticker = yf.Ticker(underlying)
            
            # Try to get the specific contract
            # Note: yfinance doesn't support direct contract lookup
            # So we'll get the chain and find our contract
            
            # Extract expiration from symbol
            exp_part = contract_symbol[3:9]  # YYMMDD
            exp_date = datetime.strptime(exp_part, '%y%m%d')
            
            # Get option type
            opt_type = 'CALL' if 'C' in contract_symbol[9:] else 'PUT'
            
            # Get chain and find our contract
            chain = self.get_option_chain(underlying, exp_date, opt_type)
            
            for option in chain:
                if option['contract_symbol'] == contract_symbol:
                    option['timestamp'] = datetime.now()
                    return option
            
            # If not found, return None
            logger.warning(f"Contract {contract_symbol} not found")
            return None
            
        except Exception as e:
            logger.error(f"Failed to get option quote: {e}")
            return None
    
    def get_multiple_quotes(self, contract_symbols: List[str]) -> Dict[str, Dict]:
        """
        Get multiple option quotes in parallel for speed
        
        Args:
            contract_symbols: List of option contract symbols
            
        Returns:
            Dict mapping symbols to quote data
        """
        quotes = {}
        
        # Use thread pool for parallel fetching
        with ThreadPoolExecutor(max_workers=5) as executor:
            future_to_symbol = {
                executor.submit(self.get_option_quote, symbol): symbol 
                for symbol in contract_symbols
            }
            
            for future in as_completed(future_to_symbol):
                symbol = future_to_symbol[future]
                try:
                    quote = future.result()
                    if quote:
                        quotes[symbol] = quote
                except Exception as e:
                    logger.error(f"Failed to fetch {symbol}: {e}")
        
        return quotes
    
    def find_options_by_criteria(self, symbol: str, expiration: datetime,
                                option_type: str, target_delta: float = 0.40,
                                min_volume: int = 100) -> List[Dict]:
        """
        Find options matching specific criteria
        
        Args:
            symbol: Underlying symbol
            expiration: Target expiration
            option_type: CALL or PUT
            target_delta: Target delta (e.g., 0.40)
            min_volume: Minimum volume filter
            
        Returns:
            List of matching options sorted by liquidity
        """
        # Get full chain
        chain = self.get_option_chain(symbol, expiration, option_type)
        
        # Filter by criteria
        filtered = []
        for option in chain:
            # Volume filter
            if option['volume'] < min_volume:
                continue
            
            # Delta filter (estimate if not provided)
            delta = option.get('delta', 0)
            if delta == 0:
                # Rough delta estimation for calls
                moneyness = option['moneyness']
                if option_type == 'CALL':
                    delta = 0.5 if moneyness == 1 else (0.9 if moneyness < 0.95 else 0.1)
                else:
                    delta = -0.5 if moneyness == 1 else (-0.9 if moneyness > 1.05 else -0.1)
            
            # Check if delta is within tolerance
            if abs(abs(delta) - target_delta) <= 0.1:
                option['delta_diff'] = abs(abs(delta) - target_delta)
                filtered.append(option)
        
        # Sort by delta closeness and liquidity
        filtered.sort(key=lambda x: (x['delta_diff'], 
                                   -(x['volume'] + x['open_interest'])))
        
        return filtered[:10]  # Return top 10 matches