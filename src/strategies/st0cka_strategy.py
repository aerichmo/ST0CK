"""
ST0CKA Strategy Implementation
Preserves exact trading logic: Buy 1 share SPY, sell for $0.01 profit
"""
from datetime import datetime
from typing import Dict, List, Optional, Any
import pytz

from ..unified_engine import TradingStrategy, Position
from ..unified_logging import get_logger

class ST0CKAStrategy(TradingStrategy):
    """
    Simple SPY scalping strategy with dual-session trading
    - Morning: Buy 9:30-10:00, Sell 10:00-11:00
    - Power Hour: Buy 3:00-3:30, Sell 3:30-3:45
    - Target: $0.01 profit per share
    - Based on high-volatility periods research
    """
    
    def __init__(self, mode: str = "simple"):
        """
        Initialize ST0CKA strategy
        
        Args:
            mode: "simple" (single position) or "advanced" (multi-position)
        """
        self.mode = mode
        self.logger = get_logger(__name__)
        self.eastern = pytz.timezone('US/Eastern')
        
        # Strategy parameters (DO NOT CHANGE - core strategy logic)
        self.profit_target = 0.01  # $0.01 profit per share
        self.position_size = 1     # Always 1 share
        
        # Trading windows - Morning and Power Hour sessions
        # Morning session (highest volatility)
        self.morning_buy_start = "09:30"
        self.morning_buy_end = "10:00"
        self.morning_sell_start = "10:00"
        self.morning_sell_end = "11:00"
        
        # Power hour session (second volatility spike)
        self.power_buy_start = "15:00"  # 3:00 PM
        self.power_buy_end = "15:30"    # 3:30 PM
        self.power_sell_start = "15:30"  # 3:30 PM
        self.power_sell_end = "15:45"    # 3:45 PM
        
        # Legacy compatibility
        self.buy_window_start = self.morning_buy_start
        self.buy_window_end = self.morning_buy_end
        self.sell_window_start = self.morning_sell_start
        self.sell_window_end = self.morning_sell_end
        
        # Advanced mode parameters
        self.max_positions = 5 if mode == "advanced" else 1
        self.entry_interval_seconds = 30  # Seconds between entries in advanced mode
        self.last_entry_time = None
    
    def get_config(self) -> Dict[str, Any]:
        """Get strategy configuration"""
        return {
            'strategy': 'st0cka',
            'mode': self.mode,
            'profit_target': self.profit_target,
            'position_size': self.position_size,
            'max_positions': self.max_positions,
            'trading_sessions': {
                'morning': f"{self.morning_buy_start}-{self.morning_sell_end}",
                'power_hour': f"{self.power_buy_start}-{self.power_sell_end}"
            },
            'cycle_delay': 5,  # 5 second cycle delay
            'max_consecutive_losses': 3,
            'max_daily_loss': -100.0,
            'max_daily_trades': 20
        }
    
    def check_entry_conditions(self, market_data: Dict[str, Any], positions: Dict[str, Position]) -> Optional[Dict[str, Any]]:
        """
        Check if we should enter a position
        
        Conditions:
        - Within buy windows (9:30-10:00 or 3:00-3:30)
        - Have less than max positions
        - SPY price available
        - In advanced mode: wait entry_interval_seconds between entries
        """
        now = datetime.now(self.eastern)
        
        # Check if within any buy window
        if not self._in_buy_window(now):
            return None
        
        # Check position limit
        spy_positions = [p for p in positions.values() if p.symbol == 'SPY']
        if len(spy_positions) >= self.max_positions:
            return None
        
        # Check SPY price
        spy_price = market_data.get('spy_price')
        if not spy_price:
            self.logger.warning("No SPY price available")
            return None
        
        # In advanced mode, check entry interval
        if self.mode == "advanced" and self.last_entry_time:
            seconds_since_last = (now - self.last_entry_time).total_seconds()
            if seconds_since_last < self.entry_interval_seconds:
                return None
        
        # All conditions met - return signal
        self.last_entry_time = now
        
        return {
            'symbol': 'SPY',
            'signal_type': 'buy',
            'price': spy_price,
            'timestamp': now,
            'reason': f'ST0CKA entry signal in {self.mode} mode'
        }
    
    def get_position_size(self, signal: Dict[str, Any], account_value: float) -> int:
        """
        ST0CKA always trades 1 share
        """
        return self.position_size
    
    def get_entry_order_params(self, signal: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get entry order parameters
        ST0CKA uses market orders for immediate fills
        """
        return {
            'symbol': 'SPY',
            'side': 'buy',
            'order_type': 'market',
            'time_in_force': 'day'
        }
    
    def check_exit_conditions(self, position: Position, market_data: Dict[str, Any]) -> Optional[str]:
        """
        Check if we should exit a position
        
        Exit conditions:
        1. Profit target reached ($0.01 profit)
        2. Force exit if in sell window (10:00-11:00 or 3:30-3:45)
        """
        if position.symbol != 'SPY':
            return None
        
        now = datetime.now(self.eastern)
        
        # Check profit target
        if position.unrealized_pnl and position.unrealized_pnl >= self.profit_target:
            return "profit_target"
        
        # Check force exit window
        if self._in_sell_window(now):
            return "time_exit"
        
        return None
    
    def get_exit_order_params(self, position: Position, exit_reason: str) -> Dict[str, Any]:
        """
        Get exit order parameters based on exit reason
        """
        if exit_reason == "profit_target":
            # Use limit order at profit target
            target_price = position.entry_price + self.profit_target
            return {
                'symbol': 'SPY',
                'order_type': 'limit',
                'limit_price': round(target_price, 2),
                'time_in_force': 'gtc'  # Good till canceled for profit target
            }
        else:
            # Use market order for time exits or shutdown
            return {
                'symbol': 'SPY',
                'order_type': 'market',
                'time_in_force': 'day'
            }
    
    def _in_buy_window(self, now: datetime) -> bool:
        """Check if within any buy window"""
        # Morning buy window
        morning_start_hour, morning_start_min = map(int, self.morning_buy_start.split(':'))
        morning_end_hour, morning_end_min = map(int, self.morning_buy_end.split(':'))
        
        morning_start = now.replace(hour=morning_start_hour, minute=morning_start_min, second=0, microsecond=0)
        morning_end = now.replace(hour=morning_end_hour, minute=morning_end_min, second=0, microsecond=0)
        
        # Power hour buy window
        power_start_hour, power_start_min = map(int, self.power_buy_start.split(':'))
        power_end_hour, power_end_min = map(int, self.power_buy_end.split(':'))
        
        power_start = now.replace(hour=power_start_hour, minute=power_start_min, second=0, microsecond=0)
        power_end = now.replace(hour=power_end_hour, minute=power_end_min, second=0, microsecond=0)
        
        return (morning_start <= now <= morning_end) or (power_start <= now <= power_end)
    
    def _in_sell_window(self, now: datetime) -> bool:
        """Check if within any sell window"""
        # Morning sell window
        morning_start_hour, morning_start_min = map(int, self.morning_sell_start.split(':'))
        morning_end_hour, morning_end_min = map(int, self.morning_sell_end.split(':'))
        
        morning_start = now.replace(hour=morning_start_hour, minute=morning_start_min, second=0, microsecond=0)
        morning_end = now.replace(hour=morning_end_hour, minute=morning_end_min, second=0, microsecond=0)
        
        # Power hour sell window
        power_start_hour, power_start_min = map(int, self.power_sell_start.split(':'))
        power_end_hour, power_end_min = map(int, self.power_sell_end.split(':'))
        
        power_start = now.replace(hour=power_start_hour, minute=power_start_min, second=0, microsecond=0)
        power_end = now.replace(hour=power_end_hour, minute=power_end_min, second=0, microsecond=0)
        
        return (morning_start <= now <= morning_end) or (power_start <= now <= power_end)