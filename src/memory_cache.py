"""
In-memory cache fallback for when Redis is not available
Provides the same interface as Redis but stores in memory
"""
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from cachetools import TTLCache
import threading
import pickle
import json


class InMemoryCache:
    """
    In-memory cache that mimics Redis interface
    Used as fallback when Redis is not available
    """
    
    def __init__(self, max_size: int = 10000, default_ttl: int = 300):
        """
        Initialize in-memory cache
        
        Args:
            max_size: Maximum number of items to store
            default_ttl: Default TTL in seconds
        """
        self.default_ttl = default_ttl
        self.data = TTLCache(maxsize=max_size, ttl=default_ttl)
        self.lock = threading.RLock()
        
    def ping(self) -> bool:
        """Mimic Redis ping - always returns True"""
        return True
    
    def get(self, key: str) -> Optional[bytes]:
        """Get value from cache"""
        with self.lock:
            value = self.data.get(key)
            if value is not None:
                return value if isinstance(value, bytes) else str(value).encode()
            return None
    
    def set(self, key: str, value: Any, ex: Optional[int] = None) -> bool:
        """Set value in cache with optional expiration"""
        with self.lock:
            # Convert to bytes if needed
            if isinstance(value, bytes):
                self.data[key] = value
            else:
                self.data[key] = str(value).encode()
            
            # Note: TTLCache handles expiration automatically
            return True
    
    def delete(self, key: str) -> int:
        """Delete key from cache"""
        with self.lock:
            if key in self.data:
                del self.data[key]
                return 1
            return 0
    
    def exists(self, key: str) -> int:
        """Check if key exists"""
        with self.lock:
            return 1 if key in self.data else 0
    
    def expire(self, key: str, seconds: int) -> bool:
        """Set expiration on key - not fully supported in memory"""
        # TTLCache doesn't support per-key TTL, so we just return True
        return self.exists(key) == 1
    
    def ttl(self, key: str) -> int:
        """Get TTL of key - returns -1 if no TTL or -2 if not exists"""
        with self.lock:
            if key in self.data:
                return self.default_ttl  # Approximate
            return -2
    
    def flushall(self) -> bool:
        """Clear all data"""
        with self.lock:
            self.data.clear()
            return True
    
    def keys(self, pattern: str = "*") -> list:
        """Get keys matching pattern"""
        with self.lock:
            if pattern == "*":
                return list(self.data.keys())
            # Simple pattern matching
            import fnmatch
            return [k for k in self.data.keys() if fnmatch.fnmatch(k, pattern)]
    
    def mget(self, keys: list) -> list:
        """Get multiple values"""
        with self.lock:
            return [self.get(k) for k in keys]
    
    def mset(self, mapping: dict) -> bool:
        """Set multiple values"""
        with self.lock:
            for k, v in mapping.items():
                self.set(k, v)
            return True
    
    def incr(self, key: str) -> int:
        """Increment integer value"""
        with self.lock:
            val = self.get(key)
            if val is None:
                new_val = 1
            else:
                new_val = int(val) + 1
            self.set(key, str(new_val))
            return new_val
    
    def decr(self, key: str) -> int:
        """Decrement integer value"""
        with self.lock:
            val = self.get(key)
            if val is None:
                new_val = -1
            else:
                new_val = int(val) - 1
            self.set(key, str(new_val))
            return new_val
    
    # Async methods (just wrap sync for compatibility)
    async def aget(self, key: str) -> Optional[bytes]:
        return self.get(key)
    
    async def aset(self, key: str, value: Any, ex: Optional[int] = None) -> bool:
        return self.set(key, value, ex)
    
    async def adelete(self, key: str) -> int:
        return self.delete(key)
    
    async def aexists(self, key: str) -> int:
        return self.exists(key)