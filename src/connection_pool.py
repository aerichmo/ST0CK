"""
Connection Pool Manager for Alpaca API
Implements connection pooling and rate limiting for optimal API usage
"""
import logging
import threading
import time
from collections import deque
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Callable
import asyncio
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)


class RateLimiter:
    """Rate limiter to prevent API throttling"""
    
    def __init__(self, max_requests: int = 200, window_seconds: int = 60):
        """
        Initialize rate limiter
        
        Args:
            max_requests: Maximum requests allowed in the window
            window_seconds: Time window in seconds
        """
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests = deque()
        self.lock = threading.Lock()
        
    def acquire(self) -> bool:
        """
        Try to acquire a rate limit slot
        
        Returns:
            True if request can proceed, False if rate limited
        """
        with self.lock:
            now = time.time()
            
            # Remove old requests outside the window
            while self.requests and self.requests[0] < now - self.window_seconds:
                self.requests.popleft()
            
            # Check if we can make a request
            if len(self.requests) < self.max_requests:
                self.requests.append(now)
                return True
            
            return False
    
    def wait_if_needed(self) -> float:
        """
        Calculate wait time if rate limited
        
        Returns:
            Seconds to wait before next request can be made
        """
        with self.lock:
            if not self.requests:
                return 0.0
            
            oldest_request = self.requests[0]
            wait_time = (oldest_request + self.window_seconds) - time.time()
            return max(0.0, wait_time)


class ConnectionPool:
    """
    Connection pool for Alpaca API clients
    Manages client instances and provides thread-safe access
    """
    
    def __init__(self, factory: Callable, size: int = 5):
        """
        Initialize connection pool
        
        Args:
            factory: Function to create new client instances
            size: Maximum pool size
        """
        self.factory = factory
        self.size = size
        self.pool = deque()
        self.active = set()
        self.lock = threading.Lock()
        self.condition = threading.Condition(self.lock)
        
        # Pre-populate pool
        for _ in range(size):
            self.pool.append(self.factory())
    
    def acquire(self, timeout: Optional[float] = None):
        """
        Acquire a client from the pool
        
        Args:
            timeout: Maximum time to wait for available connection
            
        Returns:
            Client instance
        """
        with self.condition:
            end_time = None
            if timeout is not None:
                end_time = time.time() + timeout
            
            while not self.pool:
                if end_time is not None:
                    remaining = end_time - time.time()
                    if remaining <= 0:
                        raise TimeoutError("No connections available")
                    self.condition.wait(remaining)
                else:
                    self.condition.wait()
            
            client = self.pool.popleft()
            self.active.add(id(client))
            return client
    
    def release(self, client):
        """Release a client back to the pool"""
        with self.condition:
            if id(client) in self.active:
                self.active.remove(id(client))
                self.pool.append(client)
                self.condition.notify()
    
    def close_all(self):
        """Close all connections in the pool"""
        with self.lock:
            # Close pooled connections
            while self.pool:
                client = self.pool.popleft()
                try:
                    if hasattr(client, 'close'):
                        client.close()
                except Exception as e:
                    logger.error("Error closing client: %s", e)
            
            # Note: Active connections should be released by their users


class AlpacaConnectionManager:
    """
    Centralized connection manager for all Alpaca API operations
    Provides connection pooling, rate limiting, and retry logic
    """
    
    def __init__(self, api_key: str, api_secret: str, base_url: str = None):
        """Initialize connection manager"""
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = base_url
        
        # Rate limiters for different API endpoints
        self.rate_limiters = {
            'quotes': RateLimiter(max_requests=200, window_seconds=60),
            'trades': RateLimiter(max_requests=200, window_seconds=60),
            'options': RateLimiter(max_requests=100, window_seconds=60),
            'orders': RateLimiter(max_requests=200, window_seconds=60),
            'account': RateLimiter(max_requests=100, window_seconds=60)
        }
        
        # Connection pools
        self.stock_data_pool = None
        self.option_data_pool = None
        self.trading_pool = None
        
        # Thread pool for async operations
        self.executor = ThreadPoolExecutor(max_workers=10, thread_name_prefix='alpaca')
        
        # Statistics
        self.stats = {
            'requests': 0,
            'rate_limited': 0,
            'errors': 0,
            'pool_timeouts': 0
        }
        
        self._initialize_pools()
    
    def _initialize_pools(self):
        """Initialize connection pools"""
        try:
            from alpaca.data.historical.stock import StockHistoricalDataClient
            from alpaca.data.historical.option import OptionHistoricalDataClient
            from alpaca.trading.client import TradingClient
            
            # Stock data pool
            self.stock_data_pool = ConnectionPool(
                lambda: StockHistoricalDataClient(self.api_key, self.api_secret),
                size=3
            )
            
            # Option data pool
            self.option_data_pool = ConnectionPool(
                lambda: OptionHistoricalDataClient(self.api_key, self.api_secret),
                size=3
            )
            
            # Trading pool
            self.trading_pool = ConnectionPool(
                lambda: TradingClient(
                    self.api_key, 
                    self.api_secret,
                    paper=self.base_url and 'paper' in self.base_url
                ),
                size=2
            )
            
            logger.info("Initialized Alpaca connection pools")
            
        except Exception as e:
            logger.error("Failed to initialize connection pools: %s", e)
            raise
    
    def execute_with_retry(self, 
                          pool: ConnectionPool,
                          rate_limiter_key: str,
                          operation: Callable,
                          *args,
                          max_retries: int = 3,
                          **kwargs) -> Any:
        """
        Execute an operation with connection pooling, rate limiting, and retry logic
        
        Args:
            pool: Connection pool to use
            rate_limiter_key: Key for rate limiter
            operation: Function to execute with client
            max_retries: Maximum number of retries
            
        Returns:
            Operation result
        """
        self.stats['requests'] += 1
        
        # Check rate limit
        rate_limiter = self.rate_limiters.get(rate_limiter_key)
        if rate_limiter:
            wait_time = 0
            while not rate_limiter.acquire():
                if wait_time == 0:
                    wait_time = rate_limiter.wait_if_needed()
                    logger.warning("Rate limited on %s, waiting %.2f seconds", rate_limiter_key, wait_time)
                    self.stats['rate_limited'] += 1
                time.sleep(min(wait_time, 1.0))  # Check every second
        
        # Execute with retry
        last_error = None
        for attempt in range(max_retries):
            client = None
            try:
                # Acquire client from pool
                client = pool.acquire(timeout=5.0)
                
                # Execute operation
                result = operation(client, *args, **kwargs)
                return result
                
            except TimeoutError:
                self.stats['pool_timeouts'] += 1
                logger.warning("Connection pool timeout on attempt %d", attempt + 1)
                last_error = TimeoutError("Connection pool timeout")
                
            except Exception as e:
                self.stats['errors'] += 1
                logger.warning("API error on attempt %d: %s", attempt + 1, e)
                last_error = e
                
                # Exponential backoff
                if attempt < max_retries - 1:
                    wait_time = (2 ** attempt) * 0.5
                    time.sleep(wait_time)
                    
            finally:
                # Always release client back to pool
                if client:
                    pool.release(client)
        
        # All retries failed
        raise last_error or Exception("Operation failed after all retries")
    
    def get_stock_quote(self, symbol: str) -> Dict:
        """Get stock quote with pooling and rate limiting"""
        def _get_quote(client, symbol):
            from alpaca.data.requests import StockQuotesRequest
            request = StockQuotesRequest(symbol_or_symbols=symbol, limit=1, feed='iex')
            quotes = client.get_stock_quotes(request)
            return quotes[symbol][0] if symbol in quotes else None
        
        return self.execute_with_retry(
            self.stock_data_pool,
            'quotes',
            _get_quote,
            symbol
        )
    
    def get_option_chain(self, underlying: str, expiration: str, option_type: str) -> list:
        """Get option chain with pooling and rate limiting"""
        def _get_chain(client, underlying, expiration, option_type):
            from alpaca.data.requests import OptionChainRequest
            request = OptionChainRequest(
                underlying_symbol=underlying,
                expiration_date=expiration,
                option_type=option_type
            )
            return client.get_option_chain(request)
        
        return self.execute_with_retry(
            self.option_data_pool,
            'options',
            _get_chain,
            underlying,
            expiration,
            option_type
        )
    
    def place_order(self, order_data: Dict) -> Dict:
        """Place order with pooling and rate limiting"""
        def _place_order(client, order_data):
            return client.submit_order(**order_data)
        
        return self.execute_with_retry(
            self.trading_pool,
            'orders',
            _place_order,
            order_data
        )
    
    async def get_multiple_quotes_async(self, symbols: list) -> Dict[str, Any]:
        """Get multiple quotes concurrently"""
        loop = asyncio.get_event_loop()
        
        # Create tasks for each symbol
        tasks = []
        for symbol in symbols:
            task = loop.run_in_executor(
                self.executor,
                self.get_stock_quote,
                symbol
            )
            tasks.append(task)
        
        # Wait for all tasks to complete
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Build result dict
        quote_dict = {}
        for symbol, result in zip(symbols, results):
            if isinstance(result, Exception):
                logger.warning("Failed to get quote for %s: %s", symbol, result)
                quote_dict[symbol] = None
            else:
                quote_dict[symbol] = result
        
        return quote_dict
    
    def get_statistics(self) -> Dict:
        """Get connection manager statistics"""
        return {
            **self.stats,
            'pools': {
                'stock_data': {
                    'available': len(self.stock_data_pool.pool),
                    'active': len(self.stock_data_pool.active)
                },
                'option_data': {
                    'available': len(self.option_data_pool.pool),
                    'active': len(self.option_data_pool.active)
                },
                'trading': {
                    'available': len(self.trading_pool.pool),
                    'active': len(self.trading_pool.active)
                }
            }
        }
    
    def close(self):
        """Close all connections and cleanup resources"""
        logger.info("Closing Alpaca connection manager")
        
        # Close connection pools
        if self.stock_data_pool:
            self.stock_data_pool.close_all()
        if self.option_data_pool:
            self.option_data_pool.close_all()
        if self.trading_pool:
            self.trading_pool.close_all()
        
        # Shutdown thread pool
        self.executor.shutdown(wait=True)
        
        logger.info("Connection manager closed. Stats: %s", self.stats)