"""
ST0CKA Smart Entry Strategy
Waits for optimal entry conditions instead of buying immediately
"""
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import pytz
from collections import deque

from ..unified_engine import TradingStrategy, Position
from ..unified_logging import get_logger

class ST0CKAStrategy(TradingStrategy):
    """
    Enhanced ST0CKA that waits for optimal entry conditions:
    - RSI oversold bounces
    - VWAP pullbacks
    - Support level tests
    - Volatility expansions
    """
    
    def __init__(self, mode: str = "smart"):
        """Initialize smart entry strategy"""
        self.mode = mode
        self.logger = get_logger(__name__)
        self.eastern = pytz.timezone('US/Eastern')
        
        # Trading parameters
        self.profit_target_pct = 0.0013
        self.min_profit_target = 0.65
        self.max_profit_target = 1.50
        self.position_size = 1
        
        # Entry criteria thresholds
        self.rsi_oversold = 30
        self.rsi_overbought = 70
        self.vwap_distance_pct = 0.002  # 0.2% below VWAP
        self.min_volatility_spike = 1.2  # 20% above average
        self.pullback_pct = 0.003  # 0.3% pullback from high
        
        # Trading windows
        self.morning_buy_start = "09:30"
        self.morning_buy_end = "10:00"
        self.morning_sell_start = "10:00"
        self.morning_sell_end = "11:00"
        self.power_buy_start = "15:00"
        self.power_buy_end = "15:30"
        self.power_sell_start = "15:30"
        self.power_sell_end = "15:45"
        
        # State tracking
        self.session_high = None
        self.session_low = None
        self.last_rsi = None
        self.last_entry_time = None
        self.entry_cooldown = 60  # seconds between entries
        self.max_positions = 1
        
        # Real-time price tracking
        self.price_history = deque(maxlen=20)  # Track last 20 quotes
        self.last_price = None
        self.price_momentum = 0
    
    def check_entry_conditions(self, market_data: Dict[str, Any], positions: Dict[str, Position]) -> Optional[Dict[str, Any]]:
        """
        Smart entry conditions - wait for optimal setup
        """
        now = datetime.now(self.eastern)
        
        # Basic checks first
        if not self._in_buy_window(now):
            return None
            
        if len([p for p in positions.values() if p.symbol == 'SPY']) >= self.max_positions:
            return None
            
        # Check cooldown
        if self.last_entry_time:
            if (now - self.last_entry_time).total_seconds() < self.entry_cooldown:
                return None
        
        # Get quote and technical data
        quote = market_data.get('quote', {})
        technicals = market_data.get('technicals', {})
        
        spy_price = technicals.get('current_price') or market_data.get('spy_price')
        if not spy_price:
            return None
            
        # Get real-time indicators
        price_momentum = technicals.get('price_momentum', 0)
        volatility = technicals.get('volatility', 0)
        session_high = technicals.get('session_high')
        session_low = technicals.get('session_low')
        spread = technicals.get('spread', 0)
        
        # Check for entry signals based on real-time data
        entry_signals = []
        signal_strength = 0
        
        # 1. Pullback from session high
        if session_high and session_high > spy_price:
            pullback_pct = (session_high - spy_price) / session_high
            if pullback_pct >= self.pullback_pct:
                entry_signals.append(f"Pullback from high ({pullback_pct:.2%})")
                signal_strength += 3
        
        # 2. Momentum reversal (using real-time price momentum)
        if price_momentum < -0.0005 and volatility > 0.1:
            entry_signals.append(f"Momentum reversal (momentum: {price_momentum:.4f})")
            signal_strength += 2
        
        # 3. Support Test
        if session_low and spy_price <= session_low * 1.001:  # Within 0.1% of low
            entry_signals.append("Testing session low support")
            signal_strength += 2
        
        # 4. Volatility with positive momentum
        if volatility > 0.2 and price_momentum > 0:
            entry_signals.append(f"High volatility with positive momentum (vol: {volatility:.2f}%)")
            signal_strength += 1
        
        # 5. Support bounce (price near session low with positive momentum)
        if session_low and spy_price <= session_low * 1.005 and price_momentum > 0:
            entry_signals.append(f"Support bounce (momentum: {price_momentum:.4f})")
            signal_strength += 2
        
        # Need at least 2 signals or strength >= 3
        if len(entry_signals) >= 2 or signal_strength >= 3:
            self.logger.info(f"Entry signals detected: {', '.join(entry_signals)} (strength: {signal_strength})")
            self.last_entry_time = now
            
            return {
                'symbol': 'SPY',
                'signal_type': 'buy',
                'price': spy_price,
                'timestamp': now,
                'reason': f"Smart entry: {', '.join(entry_signals[:2])}",  # Top 2 signals
                'signals': entry_signals,
                'signal_strength': signal_strength
            }
        
        # Log why we're not entering (helpful for debugging)
        if now.second % 30 == 0:  # Log every 30 seconds
            self.logger.debug(f"Waiting for entry: Price=${spy_price:.2f}, Momentum={price_momentum:.4f}, Vol={volatility:.2f}%, Signals={len(entry_signals)}")
        
        return None
    
    async def get_required_market_data(self, market_data_provider) -> Dict[str, Any]:
        """Get real-time quote data for smart entry"""
        data = {}
        
        try:
            # Get current quote for SPY
            quote = await market_data_provider.get_quote('SPY')
            
            if quote:
                current_price = quote.get('price', 0)
                bid = quote.get('bid_price', current_price)
                ask = quote.get('ask_price', current_price)
                spread = ask - bid
                
                # Update price history
                if current_price > 0:
                    self.price_history.append(current_price)
                    
                    # Update session high/low
                    if self.session_high is None or current_price > self.session_high:
                        self.session_high = current_price
                    if self.session_low is None or current_price < self.session_low:
                        self.session_low = current_price
                    
                    # Calculate price momentum
                    if self.last_price:
                        self.price_momentum = (current_price - self.last_price) / self.last_price
                    self.last_price = current_price
                
                # Calculate simple technical indicators from price history
                volatility = 0
                if len(self.price_history) > 1:
                    price_changes = [(self.price_history[i] - self.price_history[i-1]) / self.price_history[i-1] 
                                   for i in range(1, len(self.price_history))]
                    if price_changes:
                        volatility = sum(abs(pc) for pc in price_changes) / len(price_changes) * 100
                
                data['quote'] = quote
                data['technicals'] = {
                    'current_price': current_price,
                    'bid': bid,
                    'ask': ask,
                    'spread': spread,
                    'session_high': self.session_high,
                    'session_low': self.session_low,
                    'price_momentum': self.price_momentum,
                    'volatility': volatility,
                    'price_history_len': len(self.price_history)
                }
                
                self.logger.info(f"ST0CKA: Price ${current_price:.2f}, Momentum: {self.price_momentum:.4f}, Vol: {volatility:.2f}%, History: {len(self.price_history)} quotes")
                
        except Exception as e:
            self.logger.error(f"Error getting quote data: {e}")
            
        return data
    
    def _calculate_rsi(self, prices: List[float], period: int = 14) -> float:
        """Calculate RSI indicator"""
        if len(prices) < period + 1:
            return 50  # Neutral
            
        gains = []
        losses = []
        
        for i in range(1, len(prices)):
            change = prices[i] - prices[i-1]
            if change > 0:
                gains.append(change)
                losses.append(0)
            else:
                gains.append(0)
                losses.append(abs(change))
        
        avg_gain = sum(gains[-period:]) / period
        avg_loss = sum(losses[-period:]) / period
        
        if avg_loss == 0:
            return 100
            
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi
    
    def _calculate_volatility(self, returns: List[float]) -> float:
        """Calculate annualized volatility"""
        import numpy as np
        if not returns:
            return 15
        std = np.std(returns)
        # Annualize: sqrt(252 * 6.5 * 60) for 1-min bars
        return std * np.sqrt(252 * 6.5 * 60) * 100
    
    def get_position_size(self, signal: Dict[str, Any], account_value: float) -> int:
        """Size position based on signal strength"""
        base_size = self.position_size
        
        # Scale with signal strength
        signal_strength = signal.get('signal_strength', 0)
        if signal_strength >= 5:
            return base_size * 2  # Double size for very strong signals
        elif signal_strength >= 3:
            return base_size
        else:
            return base_size  # Minimum size
    
    def check_exit_conditions(self, position: Position, market_data: Dict[str, Any]) -> Optional[str]:
        """Smart exit conditions"""
        if position.symbol != 'SPY':
            return None
            
        now = datetime.now(self.eastern)
        
        # Get current indicators
        technicals = market_data.get('technicals', {})
        current_price = technicals.get('current_price', 0)
        price_momentum = technicals.get('price_momentum', 0)
        
        # Dynamic profit target
        profit_target = self._calculate_profit_target(position.avg_price)
        
        # 1. Profit target reached
        if position.unrealized_pnl and position.unrealized_pnl >= profit_target:
            return "profit_target"
        
        # 2. Momentum reversal (take profits on negative momentum)
        if price_momentum < -0.001 and position.unrealized_pnl > 0:
            return "momentum_reversal"
        
        # 3. Stop loss
        stop_loss = -profit_target * 1.5
        if position.unrealized_pnl and position.unrealized_pnl <= stop_loss:
            return "stop_loss"
        
        # 4. Time exit
        if self._in_sell_window(now):
            return "time_exit"
        
        return None
    
    def get_config(self) -> Dict[str, Any]:
        """Get strategy configuration"""
        return {
            'strategy': 'st0cka_smart_entry',
            'mode': self.mode,
            'profit_target_pct': self.profit_target_pct,
            'position_size': self.position_size,
            'entry_criteria': {
                'rsi_oversold': self.rsi_oversold,
                'vwap_distance': self.vwap_distance_pct,
                'min_signals': 2
            },
            'trading_sessions': {
                'morning': f"{self.morning_buy_start}-{self.morning_sell_end}",
                'power_hour': f"{self.power_buy_start}-{self.power_sell_end}"
            },
            'cycle_delay': 2,  # Faster checking for entry conditions
            'max_consecutive_losses': 3,
            'max_daily_loss': -200.0,
            'max_daily_trades': 10
        }
    
    def get_exit_order_params(self, position: Position, exit_reason: str) -> Dict[str, Any]:
        """Get exit order parameters"""
        if exit_reason in ["profit_target", "momentum_reversal"]:
            # Use limit order for profit taking
            target_price = position.avg_price + self._calculate_profit_target(position.avg_price)
            return {
                'symbol': 'SPY',
                'side': 'sell',
                'order_type': 'limit',
                'limit_price': round(target_price, 2),
                'time_in_force': 'day'
            }
        else:
            # Market order for stops and time exits
            return {
                'symbol': 'SPY',
                'side': 'sell',
                'order_type': 'market',
                'time_in_force': 'day'
            }
    
    def get_entry_order_params(self, signal: Dict[str, Any]) -> Dict[str, Any]:
        """Get entry order parameters"""
        return {
            'symbol': 'SPY',
            'side': 'buy',
            'order_type': 'market',
            'time_in_force': 'day'
        }
    
    def _calculate_profit_target(self, entry_price: float) -> float:
        """Calculate profit target"""
        target = entry_price * self.profit_target_pct
        return max(self.min_profit_target, min(target, self.max_profit_target))
    
    def _in_buy_window(self, now: datetime) -> bool:
        """Check if in buy window"""
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
        """Check if in sell window"""
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