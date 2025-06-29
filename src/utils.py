"""
Utility functions for the ST0CK trading system
"""
import logging
from typing import Dict, Optional, Any
from datetime import datetime
from contextlib import contextmanager
from functools import wraps
import time
import pytz

logger = logging.getLogger(__name__)


def calculate_pnl(entry_price: float, current_price: float, quantity: int, 
                  is_call: bool, is_long: bool = True) -> float:
    """
    Calculate P&L for an option position
    
    Args:
        entry_price: Entry price of the option
        current_price: Current price of the option
        quantity: Number of contracts
        is_call: True for call options, False for puts
        is_long: True for long positions, False for short
        
    Returns:
        P&L in dollars
    """
    if is_long:
        return (current_price - entry_price) * quantity * 100
    else:
        return (entry_price - current_price) * quantity * 100


def calculate_pnl_percentage(entry_price: float, current_price: float) -> float:
    """Calculate P&L percentage"""
    if entry_price == 0:
        return 0.0
    return ((current_price - entry_price) / entry_price) * 100


def retry_with_backoff(max_retries: int = 3, backoff_factor: float = 2.0):
    """
    Decorator for retrying functions with exponential backoff
    
    Args:
        max_retries: Maximum number of retry attempts
        backoff_factor: Factor to multiply wait time by on each retry
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            wait_time = 1.0
            
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        logger.warning(f"{func.__name__} failed (attempt {attempt + 1}/{max_retries}): {e}")
                        time.sleep(wait_time)
                        wait_time *= backoff_factor
                    else:
                        logger.error(f"{func.__name__} failed after {max_retries} attempts: {e}")
            
            raise last_exception
        return wrapper
    return decorator


def format_currency(amount: float) -> str:
    """Format amount as currency string"""
    return f"${amount:,.2f}"


def format_percentage(value: float) -> str:
    """Format value as percentage string"""
    return f"{value:.2f}%"


class PerformanceTimer:
    """Context manager for timing code execution"""
    
    def __init__(self, name: str, log_level: int = logging.DEBUG):
        self.name = name
        self.log_level = log_level
        self.start_time = None
        
    def __enter__(self):
        self.start_time = time.time()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        elapsed = time.time() - self.start_time
        logger.log(self.log_level, f"{self.name} took {elapsed:.3f} seconds")


def validate_market_hours(current_time: datetime, timezone) -> bool:
    """
    Check if current time is within market hours
    
    Args:
        current_time: Current datetime
        timezone: Market timezone
        
    Returns:
        True if within market hours
    """
    market_time = current_time.astimezone(timezone)
    
    # Check if weekday (Monday = 0, Sunday = 6)
    if market_time.weekday() > 4:
        return False
        
    # Check if within regular trading hours (9:30 AM - 4:00 PM ET)
    market_open = market_time.replace(hour=9, minute=30, second=0, microsecond=0)
    market_close = market_time.replace(hour=16, minute=0, second=0, microsecond=0)
    
    return market_open <= market_time <= market_close


def is_market_open() -> bool:
    """
    Simple check if market is currently open
    
    Returns:
        True if market is open, False otherwise
    """
    now = datetime.now(pytz.timezone('America/New_York'))
    
    # Weekend check
    if now.weekday() >= 5:  # Saturday = 5, Sunday = 6
        return False
    
    # Time check
    market_open = now.replace(hour=9, minute=30, second=0, microsecond=0)
    market_close = now.replace(hour=16, minute=0, second=0, microsecond=0)
    
    return market_open <= now <= market_close


def safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    """Safely divide two numbers, returning default if denominator is zero"""
    if denominator == 0:
        return default
    return numerator / denominator


def clamp(value: float, min_value: float, max_value: float) -> float:
    """Clamp a value between min and max"""
    return max(min_value, min(value, max_value))