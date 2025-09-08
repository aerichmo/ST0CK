"""
In-memory cache fallback for when Redis is not available
Provides the same interface as Redis but stores in memory
"""
from typing import Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from cachetools import TTLCache
import threading
import pickle
import json
import time


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
        # Store data as dict with (value, expiration_time) tuples
        self.data: Dict[str, Tuple[Any, float]] = {}
        self.max_size = max_size
        self.lock = threading.RLock()
        
    def ping(self) -> bool:
        """Mimic Redis ping - always returns True"""
        return True
    
    def get(self, key: str) -> Optional[bytes]:
        """Get value from cache"""
        with self.lock:
            if key in self.data:
                value, expiration = self.data[key]
                # Check if expired
                if expiration > 0 and time.time() > expiration:
                    del self.data[key]
                    return None
                return value if isinstance(value, bytes) else str(value).encode()
            return None
    
    def set(self, key: str, value: Any, ex: Optional[int] = None) -> bool:
        """Set value in cache with optional expiration"""
        with self.lock:
            # Calculate expiration time
            ttl = ex if ex is not None else self.default_ttl
            expiration = time.time() + ttl if ttl > 0 else 0
            
            # Convert to bytes if needed
            if isinstance(value, bytes):
                stored_value = value
            else:
                stored_value = str(value).encode()
            
            # Store with expiration
            self.data[key] = (stored_value, expiration)
            
            # Simple LRU: remove oldest if over max size
            if len(self.data) > self.max_size:
                # Remove expired entries first
                current_time = time.time()
                expired_keys = [k for k, (_, exp) in self.data.items() 
                               if exp > 0 and current_time > exp]
                for k in expired_keys:
                    del self.data[k]
                
                # If still over limit, remove oldest
                if len(self.data) > self.max_size:
                    oldest_key = min(self.data.keys(), 
                                   key=lambda k: self.data[k][1] if self.data[k][1] > 0 else float('inf'))
                    del self.data[oldest_key]
            
            return True
    
    def setex(self, key: str, seconds: int, value: Any) -> bool:
        """Set with expiration (for Redis compatibility)"""
        return self.set(key, value, ex=seconds)
    
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
            if key in self.data:
                _, expiration = self.data[key]
                # Check if expired
                if expiration > 0 and time.time() > expiration:
                    del self.data[key]
                    return 0
                return 1
            return 0
    
    def expire(self, key: str, seconds: int) -> bool:
        """Set expiration on key - not fully supported in memory"""
        with self.lock:
            if key in self.data:
                value, _ = self.data[key]
                expiration = time.time() + seconds if seconds > 0 else 0
                self.data[key] = (value, expiration)
                return True
            return False
    
    def ttl(self, key: str) -> int:
        """Get TTL of key - returns -1 if no TTL or -2 if not exists"""
        with self.lock:
            if key in self.data:
                _, expiration = self.data[key]
                if expiration > 0:
                    ttl = int(expiration - time.time())
                    return max(ttl, 0)
                return -1  # No expiration
            return -2  # Key doesn't exist
    
    def flushall(self) -> bool:
        """Clear all data"""
        with self.lock:
            self.data = {}
            return True
    
    def keys(self, pattern: str = "*") -> list:
        """Get keys matching pattern"""
        with self.lock:
            # Clean up expired keys first
            current_time = time.time()
            expired_keys = [k for k, (_, exp) in self.data.items() 
                           if exp > 0 and current_time > exp]
            for k in expired_keys:
                del self.data[k]
            
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
    
    async def asetex(self, key: str, seconds: int, value: Any) -> bool:
        return self.setex(key, seconds, value)
    
    async def adelete(self, key: str) -> int:
        return self.delete(key)
    
    async def aexists(self, key: str) -> int:
        return self.exists(key)