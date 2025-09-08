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
            # Log cache hit for debugging
            self.logger.debug(f"Using cached quote for {symbol}")
            return cached
        
        # Check if this is an option symbol (contains numbers after letter indicating strike)
        is_option = any(char.isdigit() for char in symbol[3:]) if len(symbol) > 3 else False
        
        if is_option:
            # For options, use the broker's get_option_quote method
            try:
                async with self.rate_limiter:
                    loop = asyncio.get_event_loop()
                    quote_data = await loop.run_in_executor(
                        None,
                        self.broker.get_option_quote,
                        symbol
                    )
                    
                    if quote_data:
                        # Handle both 'last' and 'last_price' fields for compatibility
                        last_price = quote_data.get('last', quote_data.get('last_price', 0))
                        if last_price == 0:
                            # Calculate from bid/ask if last price not available
                            last_price = (quote_data.get('bid', 0) + quote_data.get('ask', 0)) / 2
                        
                        result = {
                            'symbol': symbol,
                            'price': last_price,
                            'bid': quote_data.get('bid', 0),
                            'ask': quote_data.get('ask', 0),
                            'bid_size': quote_data.get('bid_size', 0),
                            'ask_size': quote_data.get('ask_size', 0),
                            'timestamp': quote_data.get('timestamp', datetime.now())
                        }
                        
                        # Log option quote details for debugging (use info level for visibility)
                        self.logger.info(f"Option quote for {symbol}: price=${last_price:.2f}, bid=${quote_data.get('bid', 0):.2f}, ask=${quote_data.get('ask', 0):.2f}, last=${quote_data.get('last', 'N/A')}")
                        
                        # Cache the result
                        self.cache.set(cache_key, result, UnifiedCache.TTL_QUOTES)
                        
                        return result
                        
            except Exception as e:
                # Option quotes may fail for various reasons - this is not critical
                self.logger.debug(f"Failed to get option quote for {symbol}: {e}")
                return None
        
        # Stock quotes
        try:
            async with self.rate_limiter:
                # Use run_in_executor for sync API calls
                request = StockQuotesRequest(symbol_or_symbols=symbol)
                loop = asyncio.get_event_loop()
                quotes = await loop.run_in_executor(
                    None,
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
                        'bid_price': float(quote.bid_price),  # Add both formats
                        'ask_price': float(quote.ask_price),  # Add both formats
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
        self.logger.info(f"get_bars called for {symbol}, timeframe={timeframe}, limit={limit}")
        
        # Check cache
        cache_key = CacheKeyBuilder.bars(symbol, str(timeframe))
        cached = self.cache.get(cache_key)
        if cached:
            self.logger.info(f"Returning cached bars for {symbol}")
            return cached
        
        try:
            self.logger.info(f"Acquiring rate limiter for {symbol} bars")
            async with self.rate_limiter:
                self.logger.info(f"Rate limiter acquired, preparing request for {symbol}")
                now = datetime.now(self.eastern)
                start = now - timedelta(minutes=limit)
                
                self.logger.info(f"Time range: {start} to {now} (Eastern)")
                self.logger.info(f"Feed: iex, Timeframe: {timeframe}")
                
                # Try IEX feed first (free tier)
                request = StockBarsRequest(
                    symbol_or_symbols=symbol,
                    timeframe=timeframe,
                    start=start,
                    end=now,
                    feed="iex"
                )
                
                self.logger.info(f"Calling get_stock_bars for {symbol} via run_in_executor")
                loop = asyncio.get_event_loop()
                bars_data = await loop.run_in_executor(
                    None,
                    self.data_client.get_stock_bars,
                    request
                )
                self.logger.info(f"get_stock_bars returned for {symbol}")
                
                # Log the raw response
                self.logger.info(f"Raw bars_data type: {type(bars_data)}")
                self.logger.info(f"Raw bars_data keys: {bars_data.keys() if hasattr(bars_data, 'keys') else 'No keys'}")
                
                bars = []
                if symbol in bars_data:
                    raw_bars = bars_data[symbol]
                    self.logger.info(f"Found {len(raw_bars)} bars for {symbol}")
                    for bar in raw_bars:
                        bars.append({
                            'timestamp': bar.timestamp,
                            'open': float(bar.open),
                            'high': float(bar.high),
                            'low': float(bar.low),
                            'close': float(bar.close),
                            'volume': int(bar.volume),
                            'vwap': float(bar.vwap) if hasattr(bar, 'vwap') else None
                        })
                else:
                    self.logger.warning(f"Symbol {symbol} not found in bars_data")
                
                self.logger.info(f"Returning {len(bars)} processed bars for {symbol}")
                
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
            self.logger.debug(f"Using cached option chain for {symbol} {exp_str} {option_type}")
            return cached
        
        try:
            async with self.rate_limiter:
                # Get option contracts from broker
                loop = asyncio.get_event_loop()
                contracts = await loop.run_in_executor(
                    None, 
                    self.broker.get_option_contracts,
                    symbol,
                    expiration,
                    option_type
                )
                
                if contracts:
                    # Log that we got contracts with expiration details
                    self.logger.info(f"Got {len(contracts)} {option_type} contracts from broker for {symbol} expiring {exp_str}")
                    
                    # Log sample contract to see actual expiration dates
                    if contracts:
                        sample = contracts[0]
                        self.logger.info(f"Sample contract: {sample.get('symbol', 'N/A')} - Strike: {sample.get('strike', 'N/A')} - Type: {sample.get('type', 'N/A')}")
                    
                    # Get current stock price for filtering
                    stock_quote = await self.get_quote(symbol)
                    if not stock_quote:
                        self.logger.error(f"Failed to get stock quote for {symbol}")
                        return None
                    
                    current_price = stock_quote['price']
                    
                    # Filter contracts to only relevant strikes (within 5% of current price)
                    # This dramatically reduces API calls from 100+ to ~10-20
                    lower_bound = current_price * 0.95
                    upper_bound = current_price * 1.05
                    
                    filtered_contracts = [
                        c for c in contracts 
                        if lower_bound <= c['strike'] <= upper_bound
                    ]
                    
                    self.logger.info(f"Filtered {len(contracts)} contracts to {len(filtered_contracts)} near-the-money options (price: ${current_price:.2f}, range: ${lower_bound:.2f}-${upper_bound:.2f})")
                    
                    # Get quotes only for filtered contracts
                    if filtered_contracts:
                        contract_symbols = [c['symbol'] for c in filtered_contracts]
                        quotes = await self.get_option_quotes(contract_symbols)
                        
                        # Merge contract and quote data
                        for contract in filtered_contracts:
                            if contract['symbol'] in quotes:
                                quote = quotes[contract['symbol']]
                                contract.update({
                                    'bid': quote.get('bid', 0),
                                    'ask': quote.get('ask', 0),
                                    'mid': (quote.get('bid', 0) + quote.get('ask', 0)) / 2 if quote.get('bid') and quote.get('ask') else 0,
                                    'spread': quote.get('ask', 0) - quote.get('bid', 0) if quote.get('bid') and quote.get('ask') else 0,
                                    'volume': quote.get('volume', 0),
                                    'open_interest': quote.get('open_interest', 0),
                                    'iv': quote.get('iv', 0.25),  # Default IV if not provided
                                    'delta': quote.get('delta', 0.5),  # Default delta
                                    'underlying_price': quote.get('underlying_price', 0)
                                })
                    
                    # Cache the result
                    self.cache.set(cache_key, filtered_contracts, UnifiedCache.TTL_OPTIONS)
                    
                    return filtered_contracts
                    
        except Exception as e:
            self.logger.error(f"Failed to get option chain for {symbol}: {e}")
            
        return None
    
    async def get_option_quotes(self, symbols: List[str]) -> Dict[str, Dict[str, Any]]:
        """
        Get quotes for multiple option contracts
        
        Returns:
            Dict mapping symbol to quote data
        """
        quotes = {}
        
        try:
            # Limit concurrent requests to avoid overwhelming the API
            # Process in batches of 10
            batch_size = 10
            for i in range(0, len(symbols), batch_size):
                batch = symbols[i:i + batch_size]
                
                # Get quotes concurrently for this batch
                tasks = []
                for symbol in batch:
                    loop = asyncio.get_event_loop()
                    task = loop.run_in_executor(None, self.broker.get_option_quote, symbol)
                    tasks.append(task)
                
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # Process results
                for symbol, result in zip(batch, results):
                    if isinstance(result, dict) and result:
                        quotes[symbol] = result
                    elif isinstance(result, Exception):
                        self.logger.warning(f"Failed to get quote for {symbol}: {result}")
                
                # Small delay between batches to avoid rate limiting
                if i + batch_size < len(symbols):
                    await asyncio.sleep(0.1)
                    
        except Exception as e:
            self.logger.error(f"Error getting option quotes: {e}")
            
        return quotes
    
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
                loop = asyncio.get_event_loop()
                snapshot = await loop.run_in_executor(
                    None, 
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
    
    def find_best_options(self, symbol: str, expiration: str, option_type: str, 
                         target_delta: float = 0.30) -> Optional[List[Dict[str, Any]]]:
        """
        Find best option contracts based on target delta
        Synchronous wrapper for async get_option_chain
        """
        try:
            # Convert expiration string to datetime
            exp_date = datetime.strptime(expiration, '%Y-%m-%d')
            
            # Check if we're already in an event loop
            try:
                loop = asyncio.get_running_loop()
                # We're in an async context, can't use run_until_complete
                self.logger.warning("find_best_options called from async context, returning None")
                return None
            except RuntimeError:
                # No event loop running, create one
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                contracts = loop.run_until_complete(self.get_option_chain(symbol, exp_date, option_type))
                loop.close()
            
            if not contracts:
                return None
                
            # Filter by liquidity and spread
            viable_contracts = []
            for contract in contracts:
                # Skip if no bid/ask
                if not contract.get('bid') or not contract.get('ask'):
                    continue
                    
                # Skip if spread too wide (> 10% of mid)
                spread = contract['ask'] - contract['bid']
                mid = (contract['ask'] + contract['bid']) / 2
                if spread > mid * 0.10:
                    continue
                
                # Add calculated fields for scoring
                contract['delta_diff'] = abs(contract.get('delta', 0.5) - target_delta)
                contract['oi'] = contract.get('open_interest', 0)
                contract['contract_symbol'] = contract['symbol']  # Alias for compatibility
                    
                viable_contracts.append(contract)
            
            return viable_contracts[:5]  # Return top 5 options
            
        except Exception as e:
            self.logger.error(f"Error finding best options: {e}")
            return None
    
    async def get_option_chain_snapshot_async(self, symbol: str, lower_bound: float, upper_bound: float) -> Optional[List[Dict[str, Any]]]:
        """
        Async version of get option chain snapshot for a price range
        """
        try:
            # Get nearest expiration - for 0-DTE trading, use today if it's a weekday
            now = datetime.now(self.eastern)
            today = now.date()
            
            # For 0-DTE strategy, prefer same-day expiration if it's a trading day
            if today.weekday() < 5:  # Monday = 0, Friday = 4
                # Use today's date with timezone info for 0-DTE
                expiration = now.replace(hour=0, minute=0, second=0, microsecond=0)
                self.logger.info(f"Using 0-DTE expiration: {expiration.strftime('%Y-%m-%d')} for {symbol}")
            else:
                # If weekend, get next Monday for 0-DTE
                days_until_monday = (7 - today.weekday()) % 7
                expiration = now + timedelta(days=days_until_monday)
                expiration = expiration.replace(hour=0, minute=0, second=0, microsecond=0)
                self.logger.info(f"Weekend - using Monday expiration: {expiration.strftime('%Y-%m-%d')} for {symbol}")
            
            # Get both calls and puts concurrently
            calls_task = self.get_option_chain(symbol, expiration, 'CALL')
            puts_task = self.get_option_chain(symbol, expiration, 'PUT')
            
            calls, puts = await asyncio.gather(calls_task, puts_task)
            
            # Filter by strike price range
            all_options = []
            
            if calls:
                filtered_calls = [c for c in calls if lower_bound <= c.get('strike', 0) <= upper_bound]
                all_options.extend(filtered_calls)
                
            if puts:
                filtered_puts = [p for p in puts if lower_bound <= p.get('strike', 0) <= upper_bound]
                all_options.extend(filtered_puts)
            
            return all_options
            
        except Exception as e:
            self.logger.error(f"Error getting option chain snapshot: {e}")
            return None
    
    async def find_best_options_async(self, symbol: str, expiration: str, option_type: str, 
                         target_delta: float = 0.30) -> Optional[List[Dict[str, Any]]]:
        """
        Async version to find best option contracts based on target delta
        """
        try:
            # Convert expiration string to datetime
            exp_date = datetime.strptime(expiration, '%Y-%m-%d')
            
            # Get option chain
            contracts = await self.get_option_chain(symbol, exp_date, option_type)
            
            if not contracts:
                return None
                
            # Filter by liquidity and spread
            viable_contracts = []
            for contract in contracts:
                # Skip if no bid/ask
                if not contract.get('bid') or not contract.get('ask'):
                    continue
                    
                # Skip if spread too wide (> 10% of mid)
                spread = contract['ask'] - contract['bid']
                mid = (contract['ask'] + contract['bid']) / 2
                if spread > mid * 0.10:
                    continue
                
                # Add calculated fields for scoring
                contract['delta_diff'] = abs(contract.get('delta', 0.5) - target_delta)
                contract['oi'] = contract.get('open_interest', 0)
                contract['contract_symbol'] = contract['symbol']  # Alias for compatibility
                    
                viable_contracts.append(contract)
            
            return viable_contracts[:5]  # Return top 5 options
            
        except Exception as e:
            self.logger.error(f"Error finding best options: {e}")
            return None
    
    def get_option_chain_snapshot(self, symbol: str, lower_bound: float, upper_bound: float) -> Optional[List[Dict[str, Any]]]:
        """
        Get option chain snapshot for a price range
        Synchronous wrapper for compatibility
        """
        try:
            # Get nearest expiration
            today = datetime.now(self.eastern).date()
            friday = today + timedelta(days=(4 - today.weekday()) % 7)
            if friday == today:
                friday = today + timedelta(days=7)
            expiration = datetime.combine(friday, datetime.min.time())
            
            # Check if we're already in an event loop
            try:
                loop = asyncio.get_running_loop()
                # We're in an async context, can't use run_until_complete
                self.logger.warning("get_option_chain_snapshot called from async context, returning None")
                return None
            except RuntimeError:
                # No event loop running, create one
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                calls_task = self.get_option_chain(symbol, expiration, 'CALL')
                puts_task = self.get_option_chain(symbol, expiration, 'PUT')
                
                calls, puts = loop.run_until_complete(asyncio.gather(calls_task, puts_task))
                loop.close()
            
            # Filter by strike price range
            all_options = []
            
            if calls:
                filtered_calls = [c for c in calls if lower_bound <= c.get('strike', 0) <= upper_bound]
                all_options.extend(filtered_calls)
                
            if puts:
                filtered_puts = [p for p in puts if lower_bound <= p.get('strike', 0) <= upper_bound]
                all_options.extend(filtered_puts)
            
            return all_options
            
        except Exception as e:
            self.logger.error(f"Error getting option chain snapshot: {e}")
            return None
    
    async def _update_opening_ranges(self):
        """Update opening range data for key symbols"""
        symbols = ['SPY']  # Only track SPY
        
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