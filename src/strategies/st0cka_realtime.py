"""
ST0CKA Real-time Strategy
Following Alpaca gamma-scalping patterns for better real-time trading
"""
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import pytz
from collections import deque
import asyncio

from ..unified_engine import TradingStrategy, Position
from ..unified_logging import get_logger

class ST0CKARealtimeStrategy(TradingStrategy):
    """
    Enhanced ST0CKA using real-time streaming patterns from gamma-scalping
    Key improvements:
    - Event-driven instead of polling
    - Spread-based liquidity filtering
    - Threshold-based entry triggers
    - Better momentum detection
    """
    
    def __init__(self, mode: str = "realtime"):
        """Initialize real-time strategy"""
        self.mode = mode
        self.logger = get_logger(__name__)
        self.eastern = pytz.timezone('US/Eastern')
        
        # Trading parameters
        self.profit_target_pct = 0.0013
        self.min_profit_target = 0.65
        self.max_profit_target = 1.50
        self.position_size = 1
        
        # Entry thresholds (inspired by gamma-scalping)
        self.delta_threshold = 0.002  # 0.2% price movement threshold
        self.spread_threshold = 0.05  # Maximum 5 cent spread for liquidity
        self.momentum_threshold = 0.0003  # 0.03% momentum threshold
        self.volatility_threshold = 0.15  # 0.15% volatility threshold
        
        # Trading windows - all day
        self.trading_start = "09:30"
        self.trading_end = "15:30"
        self.exit_cutoff = "15:55"
        
        # State tracking with moving windows
        self.price_window = deque(maxlen=60)  # 60 quotes (~1 minute)
        self.spread_window = deque(maxlen=20)  # Track spread quality
        self.last_trade_time = None
        self.trade_cooldown = 30  # 30 seconds between trades
        
        # Real-time metrics
        self.last_price = None
        self.last_update = None
        self.consecutive_tight_spreads = 0
        self.price_velocity = 0
        self.price_acceleration = 0
        
    def process_quote(self, quote: Dict[str, Any]) -> None:
        """
        Process real-time quote update (event-driven)
        This is called whenever a new quote arrives
        """
        current_price = quote.get('price', 0)
        bid = quote.get('bid', 0)
        ask = quote.get('ask', 0)
        spread = ask - bid
        
        # Update windows
        self.price_window.append(current_price)
        self.spread_window.append(spread)
        
        # Calculate real-time metrics
        if len(self.price_window) > 2:
            # Price velocity (rate of change)
            recent_prices = list(self.price_window)[-10:]
            if len(recent_prices) > 1:
                self.price_velocity = (recent_prices[-1] - recent_prices[0]) / recent_prices[0]
            
            # Price acceleration (change in velocity)
            if len(self.price_window) > 20:
                older_prices = list(self.price_window)[-20:-10]
                older_velocity = (older_prices[-1] - older_prices[0]) / older_prices[0] if older_prices else 0
                self.price_acceleration = self.price_velocity - older_velocity
        
        # Track spread quality
        if spread <= self.spread_threshold:
            self.consecutive_tight_spreads += 1
        else:
            self.consecutive_tight_spreads = 0
        
        self.last_price = current_price
        self.last_update = datetime.now(self.eastern)
        
    def check_entry_conditions(self, market_data: Dict[str, Any], positions: Dict[str, Position]) -> Optional[Dict[str, Any]]:
        """
        Check for entry signals using real-time metrics
        """
        now = datetime.now(self.eastern)
        
        # Basic checks
        if not self._in_trading_window(now):
            return None
            
        if len(positions) > 0:
            return None
            
        # Check cooldown
        if self.last_trade_time:
            if (now - self.last_trade_time).total_seconds() < self.trade_cooldown:
                return None
        
        # Need recent quote data
        if not self.last_price or not self.last_update:
            return None
            
        # Check data freshness (must be within 2 seconds)
        if (now - self.last_update).total_seconds() > 2:
            return None
        
        # Get current metrics
        quote = market_data.get('quote', {})
        if not quote:
            return None
            
        current_price = quote.get('price', 0)
        spread = quote.get('ask', 0) - quote.get('bid', 0)
        
        # Entry signals based on gamma-scalping patterns
        entry_signals = []
        signal_strength = 0
        
        # 1. Liquidity check - must have tight spreads
        if self.consecutive_tight_spreads < 5:
            return None  # Need consistent liquidity
            
        # 2. Delta threshold - significant price movement
        if len(self.price_window) > 10:
            price_range = max(self.price_window) - min(self.price_window)
            price_delta = price_range / current_price
            
            if price_delta >= self.delta_threshold:
                entry_signals.append(f"Delta threshold met ({price_delta:.3%})")
                signal_strength += 3
        
        # 3. Momentum reversal
        if abs(self.price_velocity) > self.momentum_threshold:
            if self.price_acceleration * self.price_velocity < 0:  # Opposite signs = reversal
                entry_signals.append(f"Momentum reversal (vel: {self.price_velocity:.4f})")
                signal_strength += 4
        
        # 4. Volatility expansion
        if len(self.price_window) > 30:
            recent_vol = self._calculate_volatility(list(self.price_window)[-30:])
            if recent_vol > self.volatility_threshold:
                entry_signals.append(f"Volatility expansion ({recent_vol:.2%})")
                signal_strength += 2
        
        # 5. Mean reversion opportunity
        if len(self.price_window) > 20:
            mean_price = sum(list(self.price_window)[-20:]) / 20
            deviation = (current_price - mean_price) / mean_price
            
            if abs(deviation) > 0.001:  # 0.1% deviation
                direction = "below" if deviation < 0 else "above"
                entry_signals.append(f"Mean reversion ({direction} by {abs(deviation):.2%})")
                signal_strength += 2
        
        # Need strong signals to enter
        if signal_strength >= 5:
            self.logger.info(f"Entry signals: {', '.join(entry_signals)} (strength: {signal_strength})")
            self.last_trade_time = now
            
            return {
                'symbol': 'SPY',
                'signal_type': 'buy',
                'price': current_price,
                'timestamp': now,
                'reason': f"Real-time entry: {', '.join(entry_signals[:2])}",
                'signals': entry_signals,
                'signal_strength': signal_strength,
                'metrics': {
                    'velocity': self.price_velocity,
                    'acceleration': self.price_acceleration,
                    'spread': spread,
                    'liquidity_score': self.consecutive_tight_spreads
                }
            }
        
        return None
    
    async def get_required_market_data(self, market_data_provider) -> Dict[str, Any]:
        """Get real-time quote data"""
        data = {}
        
        try:
            # Get current quote
            quote = await market_data_provider.get_quote('SPY')
            
            if quote:
                # Process the quote through our event handler
                self.process_quote(quote)
                
                # Return enriched data
                data['quote'] = quote
                data['realtime_metrics'] = {
                    'price_velocity': self.price_velocity,
                    'price_acceleration': self.price_acceleration,
                    'consecutive_tight_spreads': self.consecutive_tight_spreads,
                    'window_size': len(self.price_window),
                    'avg_spread': sum(self.spread_window) / len(self.spread_window) if self.spread_window else 0
                }
                
                # Log key metrics
                if self.last_update and (datetime.now(self.eastern) - self.last_update).total_seconds() < 5:
                    self.logger.debug(
                        f"RT Metrics - Price: ${quote.get('price', 0):.2f}, "
                        f"Velocity: {self.price_velocity:.5f}, "
                        f"Spreads OK: {self.consecutive_tight_spreads}, "
                        f"Window: {len(self.price_window)}"
                    )
                
        except Exception as e:
            self.logger.error(f"Error getting real-time data: {e}")
            
        return data
    
    def _calculate_volatility(self, prices: List[float]) -> float:
        """Calculate realized volatility from price series"""
        if len(prices) < 2:
            return 0
            
        returns = [(prices[i] - prices[i-1]) / prices[i-1] for i in range(1, len(prices))]
        if not returns:
            return 0
            
        avg_return = sum(returns) / len(returns)
        variance = sum((r - avg_return) ** 2 for r in returns) / len(returns)
        return variance ** 0.5
    
    def check_exit_conditions(self, position: Position, market_data: Dict[str, Any]) -> Optional[str]:
        """Check exit conditions with real-time focus"""
        if position.symbol != 'SPY':
            return None
            
        now = datetime.now(self.eastern)
        
        # Time-based exit
        if now.time() >= datetime.strptime(self.exit_cutoff, "%H:%M").time():
            return "time_exit"
        
        # Profit target
        profit_target = self._calculate_profit_target(position.avg_price)
        if position.unrealized_pnl and position.unrealized_pnl >= profit_target:
            return "profit_target"
        
        # Stop loss
        stop_loss = -profit_target * 1.5
        if position.unrealized_pnl and position.unrealized_pnl <= stop_loss:
            return "stop_loss"
        
        # Momentum-based exit
        if abs(self.price_velocity) > self.momentum_threshold * 2:
            # Strong momentum against position
            if position.unrealized_pnl > 0:  # In profit
                return "momentum_exit"
        
        return None
    
    def get_config(self) -> Dict[str, Any]:
        """Get strategy configuration"""
        return {
            'strategy': 'st0cka_realtime',
            'mode': self.mode,
            'profit_target_pct': self.profit_target_pct,
            'position_size': self.position_size,
            'thresholds': {
                'delta': self.delta_threshold,
                'spread': self.spread_threshold,
                'momentum': self.momentum_threshold,
                'volatility': self.volatility_threshold
            },
            'trading_window': f"{self.trading_start}-{self.trading_end}",
            'cycle_delay': 1,  # Faster for real-time
            'max_consecutive_losses': 3,
            'max_daily_loss': -200.0,
            'max_daily_trades': 15
        }
    
    def get_position_size(self, signal: Dict[str, Any], account_value: float) -> int:
        """Size position based on signal strength and liquidity"""
        base_size = self.position_size
        
        # Scale with signal strength
        signal_strength = signal.get('signal_strength', 0)
        metrics = signal.get('metrics', {})
        
        # Boost size for high liquidity
        if metrics.get('liquidity_score', 0) > 20:
            base_size = int(base_size * 1.5)
        
        return max(1, base_size)
    
    def get_entry_order_params(self, signal: Dict[str, Any]) -> Dict[str, Any]:
        """Get entry order parameters"""
        return {
            'symbol': 'SPY',
            'side': 'buy',
            'order_type': 'market',  # Use market for real-time execution
            'time_in_force': 'day'
        }
    
    def get_exit_order_params(self, position: Position, exit_reason: str) -> Dict[str, Any]:
        """Get exit order parameters"""
        return {
            'symbol': 'SPY',
            'side': 'sell',
            'order_type': 'market',  # Always market for exits
            'time_in_force': 'day'
        }
    
    def _calculate_profit_target(self, entry_price: float) -> float:
        """Calculate profit target"""
        target = entry_price * self.profit_target_pct
        return max(self.min_profit_target, min(target, self.max_profit_target))
    
    def _in_trading_window(self, now: datetime) -> bool:
        """Check if in trading window"""
        start_hour, start_min = map(int, self.trading_start.split(':'))
        end_hour, end_min = map(int, self.trading_end.split(':'))
        
        start_time = now.replace(hour=start_hour, minute=start_min, second=0, microsecond=0)
        end_time = now.replace(hour=end_hour, minute=end_min, second=0, microsecond=0)
        
        return start_time <= now <= end_time