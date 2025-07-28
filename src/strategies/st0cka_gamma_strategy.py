"""
ST0CKA Gamma Strategy Implementation
Combines simple scalping with gamma scalping concepts for volatility-based trading
"""
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import pytz
import numpy as np

from ..unified_engine import TradingStrategy, Position
from ..unified_logging import get_logger

class ST0CKAGammaStrategy(TradingStrategy):
    """
    Enhanced SPY scalping strategy with gamma scalping concepts
    - Trades based on volatility rather than fixed profit targets
    - Dynamic position sizing based on market conditions
    - Hedges against directional risk by taking both sides
    """
    
    def __init__(self, mode: str = "gamma"):
        """
        Initialize ST0CKA Gamma strategy
        
        Args:
            mode: "gamma" (volatility-based) or "simple" (original)
        """
        self.mode = mode
        self.logger = get_logger(__name__)
        self.eastern = pytz.timezone('US/Eastern')
        
        # Core parameters
        self.base_profit_target = 0.01  # Base $0.01 profit
        self.base_position_size = 1     # Base 1 share
        
        # Gamma scalping parameters
        self.volatility_lookback = 20   # Minutes for volatility calculation
        self.delta_threshold = 0.02     # 2% portfolio delta before hedging
        self.gamma_multiplier = 1.5     # Scale positions by gamma exposure
        
        # Trading windows
        self.buy_window_start = "09:30"
        self.buy_window_end = "15:30"   # Extended for gamma scalping
        self.force_exit_time = "15:45"
        
        # Market data tracking
        self.price_history = []
        self.last_volatility = 0.15     # Default 15% annualized
        self.portfolio_delta = 0.0
        self.vwap = None
        
        # Position tracking for hedging
        self.long_positions = 0
        self.short_positions = 0
        self.net_delta = 0.0
        
    def get_config(self) -> Dict[str, Any]:
        """Get strategy configuration"""
        return {
            'strategy': 'st0cka_gamma',
            'mode': self.mode,
            'base_profit_target': self.base_profit_target,
            'base_position_size': self.base_position_size,
            'delta_threshold': self.delta_threshold,
            'gamma_multiplier': self.gamma_multiplier,
            'trading_window_start': self.buy_window_start,
            'trading_window_end': self.buy_window_end,
            'cycle_delay': 2,  # Faster cycles for gamma scalping
            'max_consecutive_losses': 5,
            'max_daily_loss': -200.0,
            'max_daily_trades': 50  # More trades for scalping
        }
    
    def update_market_data(self, market_data: Dict[str, Any]) -> None:
        """Update internal market data and calculate volatility"""
        spy_price = market_data.get('spy_price')
        if spy_price:
            self.price_history.append({
                'price': spy_price,
                'timestamp': datetime.now(self.eastern)
            })
            
            # Keep only recent history
            cutoff_time = datetime.now(self.eastern) - timedelta(minutes=self.volatility_lookback)
            self.price_history = [p for p in self.price_history if p['timestamp'] > cutoff_time]
            
            # Calculate volatility
            if len(self.price_history) >= 2:
                self._calculate_volatility()
        
        # Update VWAP if available
        self.vwap = market_data.get('vwap', spy_price)
        
        # Update portfolio delta
        self.portfolio_delta = market_data.get('portfolio_delta', 0.0)
    
    def check_entry_conditions(self, market_data: Dict[str, Any], positions: Dict[str, Position]) -> Optional[Dict[str, Any]]:
        """
        Check if we should enter a position based on gamma scalping logic
        """
        # Update market data first
        self.update_market_data(market_data)
        
        now = datetime.now(self.eastern)
        
        # Check if within trading window
        if not self._in_trading_window(now):
            return None
        
        # Get current SPY price
        spy_price = market_data.get('spy_price')
        if not spy_price:
            return None
        
        # Calculate current position delta
        self._update_position_delta(positions)
        
        # Determine trade direction based on hedging needs
        signal = None
        
        if self.mode == "gamma":
            # Gamma scalping mode - hedge based on delta
            if abs(self.net_delta) > self.delta_threshold:
                # Need to hedge
                direction = "sell" if self.net_delta > 0 else "buy"
                signal = {
                    'symbol': 'SPY',
                    'signal_type': direction,
                    'price': spy_price,
                    'timestamp': now,
                    'reason': f'Gamma hedge: net delta {self.net_delta:.3f}',
                    'volatility': self.last_volatility
                }
            elif self._check_volatility_opportunity():
                # Volatility play
                direction = self._get_volatility_direction()
                if direction:
                    signal = {
                        'symbol': 'SPY',
                        'signal_type': direction,
                        'price': spy_price,
                        'timestamp': now,
                        'reason': f'Volatility play: {self.last_volatility:.1%} annualized',
                        'volatility': self.last_volatility
                    }
        else:
            # Simple mode - original ST0CKA logic
            if self._in_buy_window(now) and len(positions) == 0:
                signal = {
                    'symbol': 'SPY',
                    'signal_type': 'buy',
                    'price': spy_price,
                    'timestamp': now,
                    'reason': 'ST0CKA simple entry',
                    'volatility': self.last_volatility
                }
        
        return signal
    
    def get_position_size(self, signal: Dict[str, Any], account_value: float) -> int:
        """
        Calculate position size based on volatility and gamma exposure
        """
        if self.mode != "gamma":
            return self.base_position_size
        
        # Base size
        size = self.base_position_size
        
        # Scale by volatility (higher vol = larger positions for gamma scalping)
        vol_multiplier = self.last_volatility / 0.15  # 15% is baseline
        vol_multiplier = max(0.5, min(3.0, vol_multiplier))  # Cap between 0.5x and 3x
        
        # Scale by gamma multiplier
        size = int(size * vol_multiplier * self.gamma_multiplier)
        
        # Risk management - limit based on account value
        max_position_value = account_value * 0.10  # Max 10% per position
        max_shares = int(max_position_value / signal['price'])
        
        return max(1, min(size, max_shares))
    
    def get_entry_order_params(self, signal: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get entry order parameters
        """
        return {
            'symbol': 'SPY',
            'side': signal['signal_type'],  # 'buy' or 'sell'
            'order_type': 'market',
            'time_in_force': 'day'
        }
    
    def check_exit_conditions(self, position: Position, market_data: Dict[str, Any]) -> Optional[str]:
        """
        Check if we should exit a position
        """
        if position.symbol != 'SPY':
            return None
        
        now = datetime.now(self.eastern)
        
        # Force exit near close
        if self._past_force_exit_time(now):
            return "time_exit"
        
        if self.mode == "gamma":
            # Gamma scalping exits
            
            # Exit if delta is neutralized
            if position.side == 'long' and self.net_delta < -self.delta_threshold:
                return "delta_neutralized"
            elif position.side == 'short' and self.net_delta > self.delta_threshold:
                return "delta_neutralized"
            
            # Dynamic profit target based on volatility
            profit_target = self._calculate_dynamic_profit_target()
            if position.unrealized_pnl and position.unrealized_pnl >= profit_target:
                return "profit_target"
            
            # Stop loss based on volatility
            stop_loss = -profit_target * 2  # 2:1 risk/reward
            if position.unrealized_pnl and position.unrealized_pnl <= stop_loss:
                return "stop_loss"
        else:
            # Simple mode exits
            if position.unrealized_pnl and position.unrealized_pnl >= self.base_profit_target:
                return "profit_target"
            
            # Force exit in sell window
            if self._in_sell_window(now):
                return "time_exit"
        
        return None
    
    def get_exit_order_params(self, position: Position, exit_reason: str) -> Dict[str, Any]:
        """
        Get exit order parameters based on exit reason
        """
        if exit_reason == "profit_target" and self.mode == "simple":
            # Use limit order for simple mode profit targets
            target_price = position.entry_price + self.base_profit_target
            if position.side == 'short':
                target_price = position.entry_price - self.base_profit_target
            
            return {
                'symbol': 'SPY',
                'order_type': 'limit',
                'limit_price': round(target_price, 2),
                'time_in_force': 'gtc'
            }
        else:
            # Use market order for all other exits
            return {
                'symbol': 'SPY',
                'order_type': 'market',
                'time_in_force': 'day'
            }
    
    def _calculate_volatility(self) -> None:
        """Calculate realized volatility from price history"""
        if len(self.price_history) < 2:
            return
        
        # Calculate returns
        prices = [p['price'] for p in self.price_history]
        returns = []
        for i in range(1, len(prices)):
            ret = (prices[i] - prices[i-1]) / prices[i-1]
            returns.append(ret)
        
        if returns:
            # Calculate annualized volatility
            # Assuming 390 minutes in trading day, 252 trading days
            minutes_per_year = 390 * 252
            volatility = np.std(returns) * np.sqrt(minutes_per_year)
            self.last_volatility = volatility
    
    def _update_position_delta(self, positions: Dict[str, Position]) -> None:
        """Update net delta based on current positions"""
        self.long_positions = 0
        self.short_positions = 0
        
        for pos in positions.values():
            if pos.symbol == 'SPY':
                if pos.side == 'long':
                    self.long_positions += pos.quantity
                else:
                    self.short_positions += pos.quantity
        
        # Simple delta calculation (1 delta per share for stocks)
        self.net_delta = (self.long_positions - self.short_positions) / 100.0
    
    def _check_volatility_opportunity(self) -> bool:
        """Check if volatility conditions favor a trade"""
        # High volatility is good for gamma scalping
        return self.last_volatility > 0.20  # 20% annualized
    
    def _get_volatility_direction(self) -> Optional[str]:
        """Determine trade direction based on mean reversion"""
        if not self.vwap or not self.price_history:
            return None
        
        current_price = self.price_history[-1]['price']
        deviation = (current_price - self.vwap) / self.vwap
        
        # Mean reversion trades
        if deviation > 0.005:  # 0.5% above VWAP
            return "sell"  # Expect reversion down
        elif deviation < -0.005:  # 0.5% below VWAP
            return "buy"   # Expect reversion up
        
        return None
    
    def _calculate_dynamic_profit_target(self) -> float:
        """Calculate profit target based on current volatility"""
        # Higher volatility = larger profit targets
        base_target = self.base_profit_target
        vol_multiplier = self.last_volatility / 0.15  # 15% baseline
        
        return base_target * max(1.0, vol_multiplier)
    
    def _in_trading_window(self, now: datetime) -> bool:
        """Check if within trading window"""
        start_hour, start_min = map(int, self.buy_window_start.split(':'))
        end_hour, end_min = map(int, self.buy_window_end.split(':'))
        
        window_start = now.replace(hour=start_hour, minute=start_min, second=0, microsecond=0)
        window_end = now.replace(hour=end_hour, minute=end_min, second=0, microsecond=0)
        
        return window_start <= now <= window_end
    
    def _in_buy_window(self, now: datetime) -> bool:
        """Check if within original buy window (for simple mode)"""
        window_end = now.replace(hour=10, minute=0, second=0, microsecond=0)
        return now <= window_end
    
    def _in_sell_window(self, now: datetime) -> bool:
        """Check if within sell window (for simple mode)"""
        window_start = now.replace(hour=10, minute=0, second=0, microsecond=0)
        window_end = now.replace(hour=11, minute=0, second=0, microsecond=0)
        return window_start <= now <= window_end
    
    def _past_force_exit_time(self, now: datetime) -> bool:
        """Check if past force exit time"""
        exit_hour, exit_min = map(int, self.force_exit_time.split(':'))
        exit_time = now.replace(hour=exit_hour, minute=exit_min, second=0, microsecond=0)
        return now >= exit_time