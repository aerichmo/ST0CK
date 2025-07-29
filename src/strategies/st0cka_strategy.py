"""
ST0CKA Smart Entry Strategy
Waits for optimal entry conditions instead of buying immediately
"""
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import pytz
from alpaca.data.timeframe import TimeFrame

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
        
        spy_price = market_data.get('spy_price')
        if not spy_price:
            return None
            
        # Get technical indicators
        technicals = market_data.get('technicals', {})
        rsi = technicals.get('rsi')
        vwap = technicals.get('vwap')
        volatility = technicals.get('volatility', {})
        intraday_high = technicals.get('high')
        intraday_low = technicals.get('low')
        
        # Track session extremes
        if intraday_high:
            self.session_high = max(self.session_high or 0, intraday_high)
        if intraday_low:
            self.session_low = min(self.session_low or float('inf'), intraday_low)
        
        # Check for entry signals
        entry_signals = []
        signal_strength = 0
        
        # 1. RSI Oversold Bounce
        if rsi and self.last_rsi:
            if self.last_rsi < self.rsi_oversold and rsi > self.rsi_oversold:
                entry_signals.append("RSI oversold bounce")
                signal_strength += 3
        
        # 2. VWAP Pullback
        if vwap and spy_price < vwap * (1 - self.vwap_distance_pct):
            distance_pct = (vwap - spy_price) / vwap
            entry_signals.append(f"VWAP pullback ({distance_pct:.2%} below)")
            signal_strength += 2
        
        # 3. Support Test
        if self.session_low and spy_price <= self.session_low * 1.001:  # Within 0.1% of low
            entry_signals.append("Testing session low support")
            signal_strength += 2
        
        # 4. Volatility Spike
        current_vol = volatility.get('realized', 0)
        avg_vol = volatility.get('average', 15)
        if current_vol > avg_vol * self.min_volatility_spike:
            entry_signals.append(f"Volatility spike ({current_vol:.1f}% vs {avg_vol:.1f}%)")
            signal_strength += 1
        
        # 5. Pullback from High
        if self.session_high and spy_price < self.session_high * (1 - self.pullback_pct):
            pullback = (self.session_high - spy_price) / self.session_high
            entry_signals.append(f"Pullback from high ({pullback:.2%})")
            signal_strength += 1
        
        # Store current RSI for next check
        self.last_rsi = rsi
        
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
            self.logger.debug(f"Waiting for entry: Price=${spy_price:.2f}, RSI={rsi}, Signals={len(entry_signals)}")
        
        return None
    
    async def get_required_market_data(self, market_data_provider) -> Dict[str, Any]:
        """Get technical indicators for smart entry"""
        data = {}
        
        try:
            self.logger.info("ST0CKA: Starting to get market data")
            # Get recent bars for calculations
            self.logger.info("ST0CKA: Calling get_bars for SPY")
            bars = await market_data_provider.get_bars('SPY', timeframe=TimeFrame.Minute, limit=20)
            self.logger.info(f"ST0CKA: get_bars returned {len(bars) if bars else 0} bars")
            
            if bars and len(bars) >= 14:
                # Calculate RSI
                data['technicals'] = {
                    'rsi': self._calculate_rsi([b['close'] for b in bars]),
                    'vwap': bars[-1].get('vwap'),
                    'high': max(b['high'] for b in bars[-20:]),
                    'low': min(b['low'] for b in bars[-20:])
                }
                
                # Get volatility
                returns = [(bars[i]['close'] - bars[i-1]['close']) / bars[i-1]['close'] 
                          for i in range(1, len(bars))]
                data['technicals']['volatility'] = {
                    'realized': self._calculate_volatility(returns),
                    'average': 15  # Baseline
                }
        except Exception as e:
            self.logger.error(f"Error getting technical data: {e}")
            
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
        rsi = technicals.get('rsi')
        
        # Dynamic profit target
        profit_target = self._calculate_profit_target(position.avg_price)
        
        # 1. Profit target reached
        if position.unrealized_pnl and position.unrealized_pnl >= profit_target:
            return "profit_target"
        
        # 2. RSI overbought (take profits early)
        if rsi and rsi > self.rsi_overbought and position.unrealized_pnl > 0:
            return "rsi_overbought"
        
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
        if exit_reason in ["profit_target", "rsi_overbought"]:
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