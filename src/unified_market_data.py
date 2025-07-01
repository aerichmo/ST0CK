"""
Unified async market data provider
Replaces ThreadPoolExecutor with native asyncio
"""
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
import pytz
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockQuotesRequest, StockBarsRequest, StockSnapshotRequest
from alpaca.data.timeframe import TimeFrame

from .unified_logging import get_logger, log_performance
from .unified_cache import UnifiedCache, CacheKeyBuilder, cache_decorator
from .error_reporter import ErrorReporter

class UnifiedMarketData:
    """
    Async market data provider with Redis caching
    Replaces the old ThreadPoolExecutor-based implementation
    """
    
    def __init__(self, broker, cache: Optional[UnifiedCache] = None):
        """
        Initialize market data provider
        
        Args:
            broker: Alpaca broker instance
            cache: Redis cache instance
        """
        self.broker = broker
        self.cache = cache or UnifiedCache()
        self.logger = get_logger(__name__)
        
        # Alpaca data client
        self.data_client = StockHistoricalDataClient(
            broker.api_key,
            broker.secret_key,
            raw_data=False
        )
        
        # Market timing
        self.eastern = pytz.timezone('US/Eastern')
        
        # Session data
        self.session_data = {
            'opening_ranges': {},
            'session_highs': {},
            'session_lows': {}
        }
        
        # Rate limiting
        self.rate_limiter = asyncio.Semaphore(10)  # Max 10 concurrent requests
        
        self.logger.info("Unified market data provider initialized")
    
    async def initialize(self):
        """Initialize market data provider"""
        # Pre-fetch opening range data
        await self._update_opening_ranges()
        
        self.logger.info("Market data initialization complete")
    
    @log_performance
    async def get_quote(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get current quote for symbol with caching
        
        Returns:
            Dict with price, bid, ask, volume
        """
        # Check cache first
        cache_key = CacheKeyBuilder.quote(symbol)
        cached = self.cache.get(cache_key)
        if cached:
            return cached
        
        try:
            async with self.rate_limiter:
                # Use asyncio.to_thread for sync API calls
                request = StockQuotesRequest(symbol_or_symbols=symbol)
                quotes = await asyncio.to_thread(
                    self.data_client.get_stock_latest_quote,
                    request
                )
                
                if symbol in quotes:
                    quote = quotes[symbol]
                    result = {
                        'symbol': symbol,
                        'price': float(quote.ask_price + quote.bid_price) / 2,
                        'bid': float(quote.bid_price),
                        'ask': float(quote.ask_price),
                        'bid_size': int(quote.bid_size),
                        'ask_size': int(quote.ask_size),
                        'timestamp': quote.timestamp
                    }
                    
                    # Cache the result
                    self.cache.set(cache_key, result, UnifiedCache.TTL_QUOTES)
                    
                    return result
                    
        except Exception as e:
            self.logger.error(f"Failed to get quote for {symbol}: {e}")
            
        return None
    
    async def get_quotes(self, symbols: List[str]) -> Dict[str, Dict[str, Any]]:
        """Get quotes for multiple symbols concurrently"""
        tasks = [self.get_quote(symbol) for symbol in symbols]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        quotes = {}
        for symbol, result in zip(symbols, results):
            if isinstance(result, dict):
                quotes[symbol] = result
            else:
                self.logger.error(f"Failed to get quote for {symbol}: {result}")
        
        return quotes
    
    @log_performance
    async def get_bars(self, 
                      symbol: str, 
                      timeframe: TimeFrame = TimeFrame.Minute,
                      limit: int = 100) -> Optional[List[Dict[str, Any]]]:
        """
        Get historical bars with caching
        
        Returns:
            List of bar dictionaries
        """
        # Check cache
        cache_key = CacheKeyBuilder.bars(symbol, str(timeframe))
        cached = self.cache.get(cache_key)
        if cached:
            return cached
        
        try:
            async with self.rate_limiter:
                now = datetime.now(self.eastern)
                start = now - timedelta(minutes=limit)
                
                request = StockBarsRequest(
                    symbol_or_symbols=symbol,
                    timeframe=timeframe,
                    start=start,
                    end=now
                )
                
                bars_data = await asyncio.to_thread(
                    self.data_client.get_stock_bars,
                    request
                )
                
                bars = []
                if symbol in bars_data:
                    for bar in bars_data[symbol]:
                        bars.append({
                            'timestamp': bar.timestamp,
                            'open': float(bar.open),
                            'high': float(bar.high),
                            'low': float(bar.low),
                            'close': float(bar.close),
                            'volume': int(bar.volume),
                            'vwap': float(bar.vwap) if hasattr(bar, 'vwap') else None
                        })
                
                # Cache the result
                if bars:
                    self.cache.set(cache_key, bars, UnifiedCache.TTL_BARS)
                
                return bars
                
        except Exception as e:
            self.logger.error(f"Failed to get bars for {symbol}: {e}")
            
        return None
    
    async def get_option_chain(self, 
                              symbol: str,
                              expiration: datetime,
                              option_type: str = 'both') -> Optional[List[Dict[str, Any]]]:
        """
        Get option chain data with caching
        
        Args:
            symbol: Underlying symbol
            expiration: Option expiration date
            option_type: 'call', 'put', or 'both'
            
        Returns:
            List of option contracts
        """
        # Check cache
        exp_str = expiration.strftime('%Y-%m-%d')
        cache_key = CacheKeyBuilder.option_chain(symbol, exp_str, option_type)
        cached = self.cache.get(cache_key)
        if cached:
            return cached
        
        try:
            async with self.rate_limiter:
                # Get option contracts from broker
                contracts = await asyncio.to_thread(
                    self.broker.get_option_contracts,
                    symbol,
                    expiration,
                    option_type
                )
                
                if contracts:
                    # Get quotes for all contracts concurrently
                    contract_symbols = [c['symbol'] for c in contracts]
                    quotes = await self.get_quotes(contract_symbols)
                    
                    # Merge contract and quote data
                    for contract in contracts:
                        if contract['symbol'] in quotes:
                            quote = quotes[contract['symbol']]
                            contract.update({
                                'bid': quote['bid'],
                                'ask': quote['ask'],
                                'mid': (quote['bid'] + quote['ask']) / 2,
                                'spread': quote['ask'] - quote['bid']
                            })
                    
                    # Cache the result
                    self.cache.set(cache_key, contracts, UnifiedCache.TTL_OPTIONS)
                    
                    return contracts
                    
        except Exception as e:
            self.logger.error(f"Failed to get option chain for {symbol}: {e}")
            
        return None
    
    async def get_option_snapshot(self, option_symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed option snapshot with Greeks
        
        Returns:
            Dict with price, Greeks, volume, OI
        """
        # Check cache
        cache_key = CacheKeyBuilder.option_snapshot(option_symbol)
        cached = self.cache.get(cache_key)
        if cached:
            return cached
        
        try:
            async with self.rate_limiter:
                # Get option snapshot from broker
                snapshot = await asyncio.to_thread(
                    self.broker.get_option_snapshot,
                    option_symbol
                )
                
                if snapshot:
                    # Cache the result
                    self.cache.set(cache_key, snapshot, UnifiedCache.TTL_SNAPSHOTS)
                    
                return snapshot
                
        except Exception as e:
            self.logger.error(f"Failed to get option snapshot for {option_symbol}: {e}")
            
        return None
    
    async def _update_opening_ranges(self):
        """Update opening range data for key symbols"""
        symbols = ['SPY', 'QQQ', 'IWM', 'VIX']
        
        try:
            # Get first 30 minutes of data
            now = datetime.now(self.eastern)
            market_open = now.replace(hour=9, minute=30, second=0, microsecond=0)
            
            if now.time() >= market_open.time():
                tasks = []
                for symbol in symbols:
                    task = self._calculate_opening_range(symbol)
                    tasks.append(task)
                
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                for symbol, result in zip(symbols, results):
                    if isinstance(result, dict):
                        self.session_data['opening_ranges'][symbol] = result
                        
                        # Cache the result
                        cache_key = CacheKeyBuilder.opening_range(symbol, now.strftime('%Y-%m-%d'))
                        self.cache.set(cache_key, result, UnifiedCache.TTL_STATIC)
                        
        except Exception as e:
            self.logger.error(f"Failed to update opening ranges: {e}")
    
    async def _calculate_opening_range(self, symbol: str) -> Optional[Dict[str, float]]:
        """Calculate opening range for a symbol"""
        try:
            # Get first 30 minutes of bars
            bars = await self.get_bars(symbol, TimeFrame.Minute, limit=30)
            
            if bars and len(bars) >= 30:
                # First 30 minutes
                opening_bars = bars[:30]
                
                high = max(bar['high'] for bar in opening_bars)
                low = min(bar['low'] for bar in opening_bars)
                
                return {
                    'high': high,
                    'low': low,
                    'range': high - low,
                    'midpoint': (high + low) / 2
                }
                
        except Exception as e:
            self.logger.error(f"Failed to calculate opening range for {symbol}: {e}")
            
        return None
    
    def get_cached_stats(self) -> Dict[str, Any]:
        """Get cache performance statistics"""
        return self.cache.get_stats()
    
    async def close(self):
        """Close connections"""
        # Nothing to close for async implementation
        self.logger.info("Market data provider closed")