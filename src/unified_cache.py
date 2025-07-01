"""
Unified Redis-based caching system
Replaces all custom cache implementations with Redis
"""
import os
import json
import pickle
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Union, Callable
from functools import wraps
import asyncio
import redis
from redis import asyncio as aioredis
from redis.exceptions import RedisError, ConnectionError as RedisConnectionError

from .unified_logging import get_logger, LogContext
from .memory_cache import InMemoryCache

class CacheKeyBuilder:
    """Standardized cache key generation"""
    
    @staticmethod
    def quote(symbol: str) -> str:
        return f"quote:{symbol}"
    
    @staticmethod
    def option_chain(symbol: str, expiration: str, option_type: str) -> str:
        return f"option:chain:{symbol}:{expiration}:{option_type}"
    
    @staticmethod
    def option_snapshot(symbol: str) -> str:
        return f"option:snapshot:{symbol}"
    
    @staticmethod
    def bars(symbol: str, timeframe: str) -> str:
        return f"bars:{symbol}:{timeframe}"
    
    @staticmethod
    def daily_trades(bot_id: str, date: str) -> str:
        return f"db:trades:{bot_id}:{date}"
    
    @staticmethod
    def bot_performance(bot_id: str, period: str) -> str:
        return f"db:performance:{bot_id}:{period}"
    
    @staticmethod
    def option_selection(symbol: str, signal_type: str, price_bucket: int) -> str:
        return f"option:selection:{symbol}:{signal_type}:{price_bucket}"
    
    @staticmethod
    def battle_lines(date: str) -> str:
        return f"battle:lines:{date}"
    
    @staticmethod
    def opening_range(symbol: str, date: str) -> str:
        return f"opening:range:{symbol}:{date}"

class UnifiedCache:
    """
    Unified Redis cache manager with sync and async support
    Replaces all custom cache implementations
    """
    
    # Default TTL values (in seconds)
    TTL_QUOTES = 5
    TTL_OPTIONS = 60
    TTL_SNAPSHOTS = 30
    TTL_BARS = 300
    TTL_STATIC = 3600
    TTL_DB_QUERY = 60
    TTL_SELECTION = 60
    
    def __init__(self, 
                 redis_url: Optional[str] = None,
                 bot_id: Optional[str] = None,
                 use_pickle: bool = True):
        """
        Initialize Redis cache manager
        
        Args:
            redis_url: Redis connection URL (default: redis://localhost:6379)
            bot_id: Bot identifier for logging context
            use_pickle: Use pickle for complex objects (vs JSON)
        """
        self.bot_id = bot_id
        self.logger = get_logger(__name__, bot_id)
        self.use_pickle = use_pickle
        
        # Get Redis URL
        self.redis_url = redis_url or os.getenv('REDIS_URL', 'redis://localhost:6379')
        
        # Initialize sync Redis client
        self.redis_client = self._create_redis_client()
        
        # Initialize async Redis client (lazy)
        self._async_client = None
        
        # Use in-memory fallback if Redis not available
        self.use_memory_fallback = self.redis_client is None
        if self.use_memory_fallback:
            self.memory_cache = InMemoryCache()
            self.logger.info(f"[{self.bot_id}] Using in-memory cache fallback")
        
        # Cache statistics
        self.stats = {
            'hits': 0,
            'misses': 0,
            'errors': 0
        }
        
        self.logger.info(f"[{bot_id}] Redis cache initialized with URL: {self._safe_url()}")
    
    def _create_redis_client(self) -> redis.Redis:
        """Create sync Redis client with connection pooling"""
        try:
            # Parse Redis URL
            pool = redis.ConnectionPool.from_url(
                self.redis_url,
                max_connections=50,
                socket_keepalive=True,
                socket_keepalive_options={
                    1: 1,   # TCP_KEEPIDLE
                    2: 3,   # TCP_KEEPINTVL
                    3: 5    # TCP_KEEPCNT
                }
            )
            
            client = redis.Redis(
                connection_pool=pool,
                decode_responses=False,  # Handle encoding ourselves
                retry_on_timeout=True,
                retry_on_error=[RedisConnectionError],
                health_check_interval=30
            )
            
            # Test connection
            client.ping()
            
            return client
            
        except RedisError as e:
            self.logger.warning(f"[{self.bot_id}] Redis not available, using in-memory cache: {e}")
            # Return None to use in-memory fallback
            return None
    
    @property
    async def async_client(self):
        """Get or create async Redis client"""
        if self.use_memory_fallback:
            return self.memory_cache
            
        if self._async_client is None:
            try:
                self._async_client = aioredis.from_url(
                    self.redis_url,
                    max_connections=50,
                    decode_responses=False,
                    retry_on_timeout=True,
                    health_check_interval=30
                )
            except Exception:
                # Fallback to memory cache for async too
                return self.memory_cache
        return self._async_client
    
    def _safe_url(self) -> str:
        """Return Redis URL with password masked"""
        if '@' in self.redis_url:
            parts = self.redis_url.split('@')
            return parts[0].split('//')[0] + '//***@' + parts[1]
        return self.redis_url
    
    def _serialize(self, value: Any) -> bytes:
        """Serialize value for storage"""
        if self.use_pickle:
            return pickle.dumps(value)
        else:
            return json.dumps(value).encode('utf-8')
    
    def _deserialize(self, data: bytes) -> Any:
        """Deserialize value from storage"""
        if self.use_pickle:
            return pickle.loads(data)
        else:
            return json.loads(data.decode('utf-8'))
    
    # Synchronous methods
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        client = self.memory_cache if self.use_memory_fallback else self.redis_client
        if not client:
            return None
        
        try:
            data = client.get(key)
            if data:
                self.stats['hits'] += 1
                return self._deserialize(data)
            else:
                self.stats['misses'] += 1
                return None
                
        except Exception as e:
            self.stats['errors'] += 1
            self.logger.error(f"[{self.bot_id}] Cache get error for {key}: {e}")
            return None
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set value in cache with optional TTL"""
        client = self.memory_cache if self.use_memory_fallback else self.redis_client
        if not client:
            return False
        
        try:
            data = self._serialize(value)
            if ttl:
                client.setex(key, ttl, data) if hasattr(client, 'setex') else client.set(key, data, ex=ttl)
            else:
                client.set(key, data)
            return True
            
        except Exception as e:
            self.stats['errors'] += 1
            self.logger.error(f"[{self.bot_id}] Cache set error for {key}: {e}")
            return False
    
    def delete(self, key: str) -> bool:
        """Delete key from cache"""
        if not self.redis_client:
            return False
        
        try:
            return bool(self.redis_client.delete(key))
        except RedisError as e:
            self.stats['errors'] += 1
            self.logger.error(f"[{self.bot_id}] Cache delete error for {key}: {e}")
            return False
    
    def exists(self, key: str) -> bool:
        """Check if key exists"""
        if not self.redis_client:
            return False
        
        try:
            return bool(self.redis_client.exists(key))
        except RedisError:
            return False
    
    def expire(self, key: str, ttl: int) -> bool:
        """Set TTL on existing key"""
        if not self.redis_client:
            return False
        
        try:
            return bool(self.redis_client.expire(key, ttl))
        except RedisError:
            return False
    
    def get_many(self, keys: List[str]) -> Dict[str, Any]:
        """Get multiple values at once"""
        if not self.redis_client:
            return {}
        
        try:
            pipeline = self.redis_client.pipeline()
            for key in keys:
                pipeline.get(key)
            
            results = pipeline.execute()
            
            output = {}
            for key, data in zip(keys, results):
                if data:
                    self.stats['hits'] += 1
                    output[key] = self._deserialize(data)
                else:
                    self.stats['misses'] += 1
            
            return output
            
        except RedisError as e:
            self.stats['errors'] += 1
            self.logger.error(f"[{self.bot_id}] Cache get_many error: {e}")
            return {}
    
    def set_many(self, items: Dict[str, Any], ttl: Optional[int] = None) -> bool:
        """Set multiple values at once"""
        if not self.redis_client:
            return False
        
        try:
            pipeline = self.redis_client.pipeline()
            
            for key, value in items.items():
                data = self._serialize(value)
                if ttl:
                    pipeline.setex(key, ttl, data)
                else:
                    pipeline.set(key, data)
            
            pipeline.execute()
            return True
            
        except RedisError as e:
            self.stats['errors'] += 1
            self.logger.error(f"[{self.bot_id}] Cache set_many error: {e}")
            return False
    
    # Asynchronous methods
    
    async def aget(self, key: str) -> Optional[Any]:
        """Async get value from cache"""
        client = await self.async_client
        if not client:
            return None
        
        try:
            data = await client.get(key)
            if data:
                self.stats['hits'] += 1
                return self._deserialize(data)
            else:
                self.stats['misses'] += 1
                return None
                
        except RedisError as e:
            self.stats['errors'] += 1
            self.logger.error(f"[{self.bot_id}] Async cache get error for {key}: {e}")
            return None
    
    async def aset(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Async set value in cache"""
        client = await self.async_client
        if not client:
            return False
        
        try:
            data = self._serialize(value)
            if ttl:
                await client.setex(key, ttl, data)
            else:
                await client.set(key, data)
            return True
            
        except RedisError as e:
            self.stats['errors'] += 1
            self.logger.error(f"[{self.bot_id}] Async cache set error for {key}: {e}")
            return False
    
    # Specialized methods for common patterns
    
    def cache_quote(self, symbol: str, quote_data: Dict[str, Any]) -> bool:
        """Cache market quote with standard TTL"""
        key = CacheKeyBuilder.quote(symbol)
        return self.set(key, quote_data, self.TTL_QUOTES)
    
    def get_quote(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get cached market quote"""
        key = CacheKeyBuilder.quote(symbol)
        return self.get(key)
    
    def cache_option_chain(self, symbol: str, expiration: str, option_type: str, 
                          chain_data: List[Dict[str, Any]]) -> bool:
        """Cache option chain data"""
        key = CacheKeyBuilder.option_chain(symbol, expiration, option_type)
        return self.set(key, chain_data, self.TTL_OPTIONS)
    
    def get_option_chain(self, symbol: str, expiration: str, option_type: str) -> Optional[List[Dict[str, Any]]]:
        """Get cached option chain"""
        key = CacheKeyBuilder.option_chain(symbol, expiration, option_type)
        return self.get(key)
    
    def invalidate_pattern(self, pattern: str) -> int:
        """Delete all keys matching pattern"""
        if not self.redis_client:
            return 0
        
        try:
            keys = self.redis_client.keys(pattern)
            if keys:
                return self.redis_client.delete(*keys)
            return 0
        except RedisError as e:
            self.logger.error(f"[{self.bot_id}] Pattern invalidation error: {e}")
            return 0
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        total = self.stats['hits'] + self.stats['misses']
        hit_rate = self.stats['hits'] / total if total > 0 else 0.0
        
        return {
            'hits': self.stats['hits'],
            'misses': self.stats['misses'],
            'errors': self.stats['errors'],
            'hit_rate': hit_rate,
            'total_requests': total
        }
    
    def reset_stats(self):
        """Reset cache statistics"""
        self.stats = {
            'hits': 0,
            'misses': 0,
            'errors': 0
        }
    
    def close(self):
        """Close Redis connections"""
        if self.redis_client:
            self.redis_client.close()
        
        if self._async_client:
            asyncio.create_task(self._async_client.close())
        
        self.logger.info(f"[{self.bot_id}] Cache manager closed")

def cache_decorator(ttl: int = 60, key_prefix: str = ""):
    """
    Decorator for caching function results
    
    Args:
        ttl: Time to live in seconds
        key_prefix: Optional key prefix
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            # Build cache key from function name and arguments
            cache_key = f"{key_prefix}:{func.__name__}:{str(args)}:{str(kwargs)}"
            
            # Try to get from cache
            if hasattr(self, 'cache'):
                cached = self.cache.get(cache_key)
                if cached is not None:
                    return cached
            
            # Execute function
            result = func(self, *args, **kwargs)
            
            # Cache result
            if hasattr(self, 'cache') and result is not None:
                self.cache.set(cache_key, result, ttl)
            
            return result
        
        return wrapper
    return decorator

async def acache_decorator(ttl: int = 60, key_prefix: str = ""):
    """
    Async decorator for caching function results
    
    Args:
        ttl: Time to live in seconds
        key_prefix: Optional key prefix
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(self, *args, **kwargs):
            # Build cache key from function name and arguments
            cache_key = f"{key_prefix}:{func.__name__}:{str(args)}:{str(kwargs)}"
            
            # Try to get from cache
            if hasattr(self, 'cache'):
                cached = await self.cache.aget(cache_key)
                if cached is not None:
                    return cached
            
            # Execute function
            result = await func(self, *args, **kwargs)
            
            # Cache result
            if hasattr(self, 'cache') and result is not None:
                await self.cache.aset(cache_key, result, ttl)
            
            return result
        
        return wrapper
    return decorator