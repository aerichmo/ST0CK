"""
Unified, cached market data provider for ultra-fast options trading
Consolidates all data fetching with intelligent caching
"""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from collections import OrderedDict
import time
import threading
from alpaca.data.historical.option import OptionHistoricalDataClient
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import (
    OptionSnapshotRequest, 
    OptionLatestQuoteRequest,
    StockQuotesRequest,
    StockBarsRequest
)
from alpaca.data.timeframe import TimeFrame
import pandas as pd
import os

logger = logging.getLogger(__name__)


class TTLCache:
    """Simple thread-safe TTL cache"""
    def __init__(self, maxsize: int = 1000, ttl: int = 60):
        self.maxsize = maxsize
        self.ttl = ttl
        self.cache = OrderedDict()
        self.lock = threading.Lock()
        
    def get(self, key: str) -> Optional[Any]:
        with self.lock:
            if key in self.cache:
                value, timestamp = self.cache[key]
                if time.time() - timestamp < self.ttl:
                    # Move to end (LRU)
                    self.cache.move_to_end(key)
                    return value
                else:
                    # Expired
                    del self.cache[key]
            return None
    
    def set(self, key: str, value: Any):
        with self.lock:
            self.cache[key] = (value, time.time())
            # Enforce maxsize
            if len(self.cache) > self.maxsize:
                self.cache.popitem(last=False)
                
    def clear(self):
        with self.lock:
            self.cache.clear()


class UnifiedMarketData:
    """
    Single source of truth for all market data
    Optimized for SPY options trading with aggressive caching
    """
    
    def __init__(self, api_key: str = None, api_secret: str = None, skip_options: bool = False):
        # Get credentials
        self.api_key = api_key or os.environ.get('APCA_API_KEY_ID')
        self.api_secret = api_secret or os.environ.get('APCA_API_SECRET_KEY')
        
        # Debug logging
        logger.debug(f"API Key from env: {'Set' if self.api_key else 'Not set'}")
        logger.debug(f"API Secret from env: {'Set' if self.api_secret else 'Not set'}")
        
        # Initialize clients only if credentials are available
        self.option_client = None
        self.stock_client = None
        
        if self.api_key and self.api_secret:
            # Initialize clients
            if not skip_options:
                try:
                    self.option_client = OptionHistoricalDataClient(self.api_key, self.api_secret)
                except Exception as e:
                    logger.warning(f"Could not initialize option client: {e}")
            
            self.stock_client = StockHistoricalDataClient(self.api_key, self.api_secret)
        else:
            logger.warning("No Alpaca API credentials found. Market data will not be available.")
        
        # Initialize caches with appropriate TTLs
        self.quote_cache = TTLCache(maxsize=1000, ttl=5)      # 5 seconds for quotes
        self.option_cache = TTLCache(maxsize=5000, ttl=60)    # 60 seconds for options
        self.snapshot_cache = TTLCache(maxsize=2000, ttl=30)  # 30 seconds for snapshots
        self.bar_cache = TTLCache(maxsize=100, ttl=300)       # 5 minutes for bars
        self.static_cache = TTLCache(maxsize=50, ttl=3600)    # 1 hour for static data
        
        # Pre-fetched data
        self.current_session_options = {}
        self.opening_ranges = {}
        
        logger.info("Initialized UnifiedMarketData with aggressive caching")
    
    def prefetch_session_data(self, symbol: str = 'SPY'):
        """Pre-fetch all option data for today's trading session"""
        try:
            logger.info(f"Pre-fetching {symbol} options for trading session...")
            
            # Get next 3 weekly expirations
            expirations = self._get_weekly_expirations(3)
            
            for expiry in expirations:
                # Pre-fetch option chains for both calls and puts
                logger.info(f"Pre-fetching options for {expiry.date()}")
                
                # Fetch CALL options
                call_chain = self.get_option_chain_fast(symbol, expiry, 'CALL')
                if call_chain:
                    key = f"{symbol}_{expiry.date()}_C"
                    self.current_session_options[key] = call_chain
                
                # Fetch PUT options
                put_chain = self.get_option_chain_fast(symbol, expiry, 'PUT')
                if put_chain:
                    key = f"{symbol}_{expiry.date()}_P"
                    self.current_session_options[key] = put_chain
            
            logger.info(f"Pre-fetched {len(self.current_session_options)} option chains")
            
        except Exception as e:
            logger.error(f"Failed to prefetch session data: {e}")
    
    def get_spy_quote(self) -> Dict:
        """Get SPY quote with caching"""
        cache_key = "SPY_quote"
        cached = self.quote_cache.get(cache_key)
        if cached:
            return cached
        
        try:
            request = StockQuotesRequest(symbol_or_symbols="SPY", limit=1)
            quotes = self.stock_client.get_stock_quotes(request)
            
            if "SPY" in quotes and quotes["SPY"]:
                quote = quotes["SPY"][0]
                result = {
                    'symbol': 'SPY',
                    'price': float(quote.ask_price),
                    'bid': float(quote.bid_price),
                    'ask': float(quote.ask_price),
                    'bid_size': int(quote.bid_size),
                    'ask_size': int(quote.ask_size),
                    'timestamp': quote.timestamp
                }
                self.quote_cache.set(cache_key, result)
                return result
        except Exception as e:
            logger.error(f"Failed to get SPY quote: {e}")
        
        return {'symbol': 'SPY', 'price': 0, 'bid': 0, 'ask': 0}
    
    def get_option_chain_fast(self, symbol: str, expiration: datetime, 
                             option_type: str = 'CALL') -> List[Dict]:
        """Get option chain - uses pre-fetched data when available"""
        key = f"{symbol}_{expiration.date()}_{option_type[0]}"
        
        # Check pre-fetched data first
        if key in self.current_session_options:
            return self.current_session_options[key]
        
        # Check cache
        cached = self.option_cache.get(key)
        if cached:
            return cached
        
        # Fetch from API using snapshots
        try:
            # Get current SPY price
            spy_quote = self.get_spy_quote()
            current_price = spy_quote['price']
            
            # Calculate ATM strike range (within 2% of current price)
            min_strike = int(current_price * 0.98)
            max_strike = int(current_price * 1.02)
            
            # Build list of potential option symbols
            options = []
            exp_str = expiration.strftime('%y%m%d')
            
            for strike in range(min_strike, max_strike + 1):
                # Format: SPY231215C400 (SPY + YYMMDD + C/P + Strike)
                opt_type = 'C' if option_type == 'CALL' else 'P'
                contract_symbol = f"SPY{exp_str}{opt_type}{strike:03d}000"
                
                options.append({
                    'contract_symbol': contract_symbol,
                    'strike': float(strike),
                    'expiration': expiration.isoformat(),
                    'option_type': option_type
                })
            
            self.option_cache.set(key, options)
            return options
            
        except Exception as e:
            logger.error(f"Failed to fetch option chain: {e}")
            return []
    
    def get_option_quotes_batch(self, symbols: List[str]) -> Dict[str, Dict]:
        """Get multiple option quotes in a single API call"""
        # Check cache first
        result = {}
        uncached_symbols = []
        
        for symbol in symbols:
            cached = self.quote_cache.get(f"option_{symbol}")
            if cached:
                result[symbol] = cached
            else:
                uncached_symbols.append(symbol)
        
        # Fetch uncached in batch
        if uncached_symbols:
            try:
                request = OptionLatestQuoteRequest(symbol_or_symbols=uncached_symbols)
                quotes = self.option_client.get_option_latest_quote(request)
                
                for symbol, quote in quotes.items():
                    quote_dict = {
                        'symbol': symbol,
                        'bid': float(quote.bid_price) if quote.bid_price else 0,
                        'ask': float(quote.ask_price) if quote.ask_price else 0,
                        'bid_size': int(quote.bid_size) if quote.bid_size else 0,
                        'ask_size': int(quote.ask_size) if quote.ask_size else 0,
                        'mid': float((quote.bid_price + quote.ask_price) / 2) if quote.bid_price and quote.ask_price else 0,
                        'timestamp': quote.timestamp.isoformat() if quote.timestamp else datetime.now().isoformat()
                    }
                    result[symbol] = quote_dict
                    self.quote_cache.set(f"option_{symbol}", quote_dict)
                    
            except Exception as e:
                logger.error(f"Failed to fetch option quotes batch: {e}")
        
        return result
    
    def get_option_snapshot_batch(self, symbols: List[str]) -> Dict[str, Dict]:
        """Get option snapshots with Greeks in batch"""
        # Check cache
        result = {}
        uncached_symbols = []
        
        for symbol in symbols:
            cached = self.snapshot_cache.get(symbol)
            if cached:
                result[symbol] = cached
            else:
                uncached_symbols.append(symbol)
        
        # Fetch uncached
        if uncached_symbols:
            try:
                request = OptionSnapshotRequest(symbol_or_symbols=uncached_symbols)
                snapshots = self.option_client.get_option_snapshot(request)
                
                for symbol, snapshot in snapshots.items():
                    if snapshot.latest_quote and snapshot.greeks:
                        snapshot_dict = {
                            'symbol': symbol,
                            'quote': {
                                'bid': float(snapshot.latest_quote.bid_price) if snapshot.latest_quote.bid_price else 0,
                                'ask': float(snapshot.latest_quote.ask_price) if snapshot.latest_quote.ask_price else 0,
                                'mid': float((snapshot.latest_quote.bid_price + snapshot.latest_quote.ask_price) / 2) 
                                       if snapshot.latest_quote.bid_price and snapshot.latest_quote.ask_price else 0
                            },
                            'greeks': {
                                'delta': float(snapshot.greeks.delta) if snapshot.greeks.delta else 0,
                                'gamma': float(snapshot.greeks.gamma) if snapshot.greeks.gamma else 0,
                                'theta': float(snapshot.greeks.theta) if snapshot.greeks.theta else 0,
                                'vega': float(snapshot.greeks.vega) if snapshot.greeks.vega else 0,
                                'rho': float(snapshot.greeks.rho) if snapshot.greeks.rho else 0
                            },
                            'iv': float(snapshot.implied_volatility) if snapshot.implied_volatility else 0,
                            'volume': int(snapshot.latest_trade.size) if snapshot.latest_trade else 0,
                            'oi': int(snapshot.open_interest) if snapshot.open_interest else 0
                        }
                        result[symbol] = snapshot_dict
                        self.snapshot_cache.set(symbol, snapshot_dict)
                        
            except Exception as e:
                logger.error(f"Failed to fetch option snapshots: {e}")
        
        return result
    
    def find_best_options(self, symbol: str, expiration: datetime,
                         option_type: str, target_delta: float = 0.40) -> List[Dict]:
        """Find best options by criteria - optimized version"""
        # Get all contracts (from cache/prefetch)
        contracts = self.get_option_chain_fast(symbol, expiration, option_type)
        
        if not contracts:
            return []
        
        # Get current SPY price
        spy_quote = self.get_spy_quote()
        current_price = spy_quote['price']
        
        # Filter by strike proximity (reduce API calls)
        if option_type == 'CALL':
            # For calls, look at strikes near current price
            min_strike = current_price * 0.98
            max_strike = current_price * 1.05
        else:
            # For puts, look at strikes near current price
            min_strike = current_price * 0.95
            max_strike = current_price * 1.02
        
        filtered_contracts = [
            c for c in contracts 
            if min_strike <= c['strike'] <= max_strike
        ]
        
        # Get snapshots for filtered contracts (batch)
        symbols = [c['contract_symbol'] for c in filtered_contracts]
        if not symbols:
            return []
        
        snapshots = self.get_option_snapshot_batch(symbols[:20])  # Limit to 20 for speed
        
        # Find best matches
        candidates = []
        for contract in filtered_contracts:
            symbol = contract['contract_symbol']
            if symbol in snapshots:
                snapshot = snapshots[symbol]
                delta = abs(snapshot['greeks']['delta'])
                delta_diff = abs(delta - target_delta)
                
                if delta_diff <= 0.1:  # Within tolerance
                    candidates.append({
                        **contract,
                        **snapshot['quote'],
                        'delta': delta,
                        'delta_diff': delta_diff,
                        'iv': snapshot['iv'],
                        'volume': snapshot['volume'],
                        'oi': snapshot['oi'],
                        'greeks': snapshot['greeks']
                    })
        
        # Sort by delta match and liquidity
        candidates.sort(key=lambda x: (x['delta_diff'], -(x['volume'] + x['oi'])))
        
        return candidates[:5]  # Return top 5
    
    def get_opening_range(self, symbol: str) -> Optional[Dict]:
        """Get cached opening range"""
        return self.opening_ranges.get(symbol)
    
    def set_opening_range(self, symbol: str, or_high: float, or_low: float):
        """Cache opening range for the session"""
        self.opening_ranges[symbol] = {
            'high': or_high,
            'low': or_low,
            'range': or_high - or_low,
            'timestamp': datetime.now()
        }
    
    def get_5min_bars(self, symbol: str, lookback_days: int = 1) -> pd.DataFrame:
        """Get 5-minute bars with caching"""
        cache_key = f"{symbol}_5min_{lookback_days}"
        cached = self.bar_cache.get(cache_key)
        if cached is not None:
            return cached
        
        try:
            end = datetime.now()
            start = end - timedelta(days=lookback_days)
            
            request = StockBarsRequest(
                symbol_or_symbols=symbol,
                timeframe=TimeFrame.Minute,
                start=start,
                end=end,
                limit=1000
            )
            
            bars = self.stock_client.get_stock_bars(request)
            
            if symbol in bars and bars[symbol]:
                df = pd.DataFrame([{
                    'open': float(bar.open),
                    'high': float(bar.high),
                    'low': float(bar.low),
                    'close': float(bar.close),
                    'volume': int(bar.volume),
                    'timestamp': bar.timestamp
                } for bar in bars[symbol]])
                
                if not df.empty:
                    df.set_index('timestamp', inplace=True)
                    df = df.resample('5T').agg({
                        'open': 'first',
                        'high': 'max',
                        'low': 'min',
                        'close': 'last',
                        'volume': 'sum'
                    }).dropna()
                    
                    self.bar_cache.set(cache_key, df)
                    return df
                    
        except Exception as e:
            logger.error(f"Failed to get bars: {e}")
        
        return pd.DataFrame()
    
    def _get_weekly_expirations(self, num_weeks: int = 3) -> List[datetime]:
        """Get next N weekly option expirations including 0DTE"""
        expirations = []
        today = datetime.now()
        
        # Add today if it's a weekday and before 4 PM (0DTE)
        if today.weekday() < 5 and today.hour < 16:
            expirations.append(today)
        
        # Add weekly expirations
        for i in range(num_weeks):
            days_ahead = i * 7
            target_date = today + timedelta(days=days_ahead)
            
            # Find next Friday
            days_until_friday = (4 - target_date.weekday()) % 7
            if days_until_friday == 0 and target_date.hour >= 16:
                days_until_friday = 7
            
            expiry = target_date + timedelta(days=days_until_friday)
            if expiry.date() != today.date():  # Don't duplicate today
                expirations.append(expiry)
        
        return expirations[:num_weeks]
    
    def clear_caches(self):
        """Clear all caches - useful at session start"""
        self.quote_cache.clear()
        self.option_cache.clear()
        self.snapshot_cache.clear()
        self.bar_cache.clear()
        self.static_cache.clear()
        self.current_session_options.clear()
        self.opening_ranges.clear()
        logger.info("Cleared all caches")