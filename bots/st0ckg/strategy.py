"""
APEX Simplified - Lean SPY Options Strategy
Focus on execution, not complexity
"""
from datetime import datetime, time, timedelta
from typing import Dict, List, Optional, Tuple
import logging
import numpy as np

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from bots.base.strategy import BaseStrategy, Signal

logger = logging.getLogger(__name__)


class APEXSimplifiedStrategy(BaseStrategy):
    """Simplified APEX strategy - momentum breakout + VWAP mean reversion"""
    
    def __init__(self, bot_id: str, config: Dict):
        super().__init__(bot_id, config)
        
        # Market data
        self.market_data = None
        
        # Technical indicators
        self.current_ema = None
        self.current_atr = None
        self.current_vwap = None
        self.avg_volume = None
        
        # Track daily stats
        self.trades_today = 0
        self.consecutive_losses = 0
        self.daily_pnl = 0
        
    def initialize(self, market_data_provider) -> bool:
        """Initialize strategy with market data provider"""
        try:
            self.market_data = market_data_provider
            self.is_initialized = True
            logger.info(f"[{self.bot_id}] APEX Simplified initialized")
            return True
        except Exception as e:
            logger.error(f"[{self.bot_id}] Initialization failed: {e}")
            return False
    
    async def should_generate_signals(self) -> bool:
        """Check if we should look for signals"""
        now = datetime.now()
        current_time = now.time()
        
        # Check trading window
        if not (self.config['trading_window']['start'] <= current_time <= 
                self.config['trading_window']['end']):
            return False
            
        # Check daily limits
        if self.trades_today >= self.config['max_trades_per_day']:
            return False
            
        if self.consecutive_losses >= self.config['max_consecutive_losses']:
            logger.warning(f"[{self.bot_id}] Max consecutive losses reached")
            return False
            
        if abs(self.daily_pnl) >= self.config['max_daily_loss']:
            logger.warning(f"[{self.bot_id}] Daily loss limit reached")
            return False
            
        return True
    
    async def generate_signals(self) -> List[Signal]:
        """Generate trading signals - simplified approach"""
        try:
            if not await self.should_generate_signals():
                return []
                
            # Update indicators
            await self._update_indicators()
            
            # Check basic filters
            if not self._check_filters():
                return []
                
            signals = []
            
            # Check momentum breakout
            momentum_signal = await self._check_momentum_breakout()
            if momentum_signal:
                signals.append(momentum_signal)
                
            # Check VWAP mean reversion
            vwap_signal = await self._check_vwap_reversion()
            if vwap_signal:
                signals.append(vwap_signal)
                
            # Limit concurrent positions
            max_new = self.config['max_concurrent_positions'] - len(self.active_positions)
            return signals[:max_new]
            
        except Exception as e:
            logger.error(f"[{self.bot_id}] Signal generation failed: {e}")
            return []
    
    async def _update_indicators(self):
        """Update technical indicators"""
        try:
            # Get recent bars
            bars = await self.market_data.get_bars('SPY', '1Min', limit=30)
            if len(bars) < 20:
                return
                
            # Calculate indicators
            closes = [bar.close for bar in bars]
            volumes = [bar.volume for bar in bars]
            
            # EMA
            self.current_ema = self._calculate_ema(closes, self.config['indicators']['ema_period'])
            
            # ATR
            self.current_atr = self._calculate_atr(bars, self.config['indicators']['atr_period'])
            
            # Average volume
            self.avg_volume = np.mean(volumes[-self.config['indicators']['volume_period']:])
            
            # VWAP (simplified - just for current day)
            if self.config['indicators']['vwap_enabled']:
                self.current_vwap = await self._calculate_vwap()
                
        except Exception as e:
            logger.error(f"[{self.bot_id}] Indicator update failed: {e}")
    
    def _check_filters(self) -> bool:
        """Check if market conditions allow trading"""
        try:
            # Check ATR
            if self.current_atr and self.current_atr < self.config['filters']['min_atr']:
                return False
                
            # Would check VIX here if needed
            # For now, assume conditions are ok
            return True
            
        except Exception as e:
            logger.error(f"[{self.bot_id}] Filter check failed: {e}")
            return False
    
    async def _check_momentum_breakout(self) -> Optional[Signal]:
        """Simple momentum breakout signal"""
        try:
            config = self.config['entry_signals']['momentum_breakout']
            if not config['enabled']:
                return None
                
            # Get recent price action
            bars = await self.market_data.get_bars('SPY', '1Min', limit=5)
            if len(bars) < config['confirmation_bars'] + 1:
                return None
                
            current_price = bars[-1].close
            
            # Check for momentum move
            price_change = (current_price - bars[-3].close) / bars[-3].close
            
            # Need significant move
            if abs(price_change) < config['min_move']:
                return None
                
            # Check volume confirmation
            current_volume = bars[-1].volume
            if current_volume < self.avg_volume * config['volume_confirmation']:
                return None
                
            # Determine direction
            direction = 'buy' if price_change > 0 else 'sell'
            
            # Check trend filter
            if self.config['filters']['trend_filter'] and self.current_ema:
                if direction == 'buy' and current_price < self.current_ema:
                    return None
                elif direction == 'sell' and current_price > self.current_ema:
                    return None
                    
            # Calculate stops and targets
            stop_distance = self.current_atr * self.config['exit_rules']['stop_loss_atr']
            target_distance = self.current_atr * self.config['exit_rules']['profit_target_atr']
            
            if direction == 'buy':
                stop_price = current_price - stop_distance
                target_price = current_price + target_distance
            else:
                stop_price = current_price + stop_distance
                target_price = current_price - target_distance
                
            return Signal(
                symbol='SPY',
                direction=direction,
                strength=0.7,  # Fixed strength for simplicity
                metadata={
                    'signal_type': 'momentum_breakout',
                    'entry_price': current_price,
                    'stop_price': stop_price,
                    'target_price': target_price,
                    'atr': self.current_atr
                }
            )
            
        except Exception as e:
            logger.error(f"[{self.bot_id}] Momentum check failed: {e}")
            return None
    
    async def _check_vwap_reversion(self) -> Optional[Signal]:
        """Simple VWAP mean reversion signal"""
        try:
            config = self.config['entry_signals']['vwap_mean_reversion']
            if not config['enabled'] or not self.current_vwap:
                return None
                
            # Get current price
            quote = await self.market_data.get_quote('SPY')
            if not quote:
                return None
                
            current_price = quote.last
            
            # Calculate distance from VWAP
            vwap_distance = abs(current_price - self.current_vwap) / self.current_vwap
            
            # Check if within range
            if vwap_distance < config['min_distance'] or vwap_distance > config['max_distance']:
                return None
                
            # Check volume
            bars = await self.market_data.get_bars('SPY', '1Min', limit=1)
            if bars and bars[0].volume < self.avg_volume * config['volume_confirmation']:
                return None
                
            # Mean reversion direction (opposite of stretch)
            direction = 'buy' if current_price < self.current_vwap else 'sell'
            
            # VWAP acts as target, stop beyond stretch
            stop_distance = self.current_atr * self.config['exit_rules']['stop_loss_atr']
            
            if direction == 'buy':
                stop_price = current_price - stop_distance
                target_price = self.current_vwap  # Revert to VWAP
            else:
                stop_price = current_price + stop_distance
                target_price = self.current_vwap
                
            return Signal(
                symbol='SPY',
                direction=direction,
                strength=0.6,
                metadata={
                    'signal_type': 'vwap_reversion',
                    'entry_price': current_price,
                    'stop_price': stop_price,
                    'target_price': target_price,
                    'vwap': self.current_vwap,
                    'atr': self.current_atr
                }
            )
            
        except Exception as e:
            logger.error(f"[{self.bot_id}] VWAP check failed: {e}")
            return None
    
    def calculate_position_size(self, signal: Signal, entry_price: float) -> int:
        """Simple position sizing - flat risk percentage"""
        try:
            account_value = self.config['capital']  # In production, get from broker
            risk_amount = account_value * self.config['risk_per_trade']
            
            # Get stop distance from signal
            stop_price = signal.metadata.get('stop_price', entry_price * 0.99)
            stop_distance = abs(entry_price - stop_price)
            
            if stop_distance <= 0:
                return 0
                
            # Calculate contracts
            contracts = int(risk_amount / (stop_distance * 100))
            
            # Apply position size limit
            max_contracts = int(account_value * self.config['max_position_size'] / (entry_price * 100))
            contracts = min(contracts, max_contracts)
            
            logger.info(f"[{self.bot_id}] Position size: {contracts} contracts, "
                       f"Risk: ${risk_amount:.0f}")
                       
            return contracts
            
        except Exception as e:
            logger.error(f"[{self.bot_id}] Position sizing failed: {e}")
            return 0
    
    def should_exit_position(self, position: Dict) -> Tuple[bool, str]:
        """Simple exit logic"""
        try:
            entry_price = position['entry_price']
            current_price = position['current_price']
            stop_price = position.get('stop_price')
            target_price = position.get('target_price')
            entry_time = position.get('entry_time', datetime.now())
            
            # Stop loss
            if stop_price:
                if position['direction'] == 'buy' and current_price <= stop_price:
                    return True, "stop_loss"
                elif position['direction'] == 'sell' and current_price >= stop_price:
                    return True, "stop_loss"
                    
            # Profit target
            if target_price:
                if position['direction'] == 'buy' and current_price >= target_price:
                    return True, "profit_target"
                elif position['direction'] == 'sell' and current_price <= target_price:
                    return True, "profit_target"
                    
            # Time stop
            minutes_held = (datetime.now() - entry_time).total_seconds() / 60
            if minutes_held > self.config['exit_rules']['time_stop_minutes']:
                return True, "time_stop"
                
            # Trailing stop
            if self.config['exit_rules']['trailing_stop_activation']:
                self._check_trailing_stop(position)
                
            return False, ""
            
        except Exception as e:
            logger.error(f"[{self.bot_id}] Exit check failed: {e}")
            return False, ""
    
    def _check_trailing_stop(self, position: Dict) -> bool:
        """Simple trailing stop logic"""
        entry_price = position['entry_price']
        current_price = position['current_price']
        stop_price = position.get('stop_price', entry_price)
        
        # Calculate profit in R
        risk = abs(entry_price - stop_price)
        profit = abs(current_price - entry_price)
        r_multiple = profit / risk if risk > 0 else 0
        
        # Activate trailing stop
        if r_multiple >= self.config['exit_rules']['trailing_stop_activation']:
            trail_distance = risk * self.config['exit_rules']['trailing_stop_distance']
            
            if position['direction'] == 'buy':
                new_stop = current_price - trail_distance
                position['stop_price'] = max(position.get('stop_price', 0), new_stop)
            else:
                new_stop = current_price + trail_distance
                position['stop_price'] = min(position.get('stop_price', float('inf')), new_stop)
                
        return False
    
    def update_position_tracking(self, position: Dict, fill_price: float, action: str):
        """Update tracking after position changes"""
        try:
            if action == "exit":
                pnl = position.get('realized_pnl', 0)
                self.daily_pnl += pnl
                
                if pnl > 0:
                    self.consecutive_losses = 0
                else:
                    self.consecutive_losses += 1
                    
                self.trades_today += 1
                
        except Exception as e:
            logger.error(f"[{self.bot_id}] Tracking update failed: {e}")
    
    # Helper methods
    
    def _calculate_ema(self, prices: List[float], period: int) -> float:
        """Calculate exponential moving average"""
        if len(prices) < period:
            return prices[-1]
            
        multiplier = 2 / (period + 1)
        ema = prices[-period]  # Start with SMA
        
        for price in prices[-period+1:]:
            ema = (price - ema) * multiplier + ema
            
        return ema
    
    def _calculate_atr(self, bars: List, period: int) -> float:
        """Calculate Average True Range"""
        if len(bars) < 2:
            return 1.0
            
        true_ranges = []
        for i in range(1, len(bars)):
            high = bars[i].high
            low = bars[i].low
            prev_close = bars[i-1].close
            
            tr = max(
                high - low,
                abs(high - prev_close),
                abs(low - prev_close)
            )
            true_ranges.append(tr)
            
        return np.mean(true_ranges[-period:]) if true_ranges else 1.0
    
    async def _calculate_vwap(self) -> float:
        """Calculate simple VWAP for the day"""
        try:
            # Get today's bars
            bars = await self.market_data.get_bars('SPY', '1Min', limit=390)
            if not bars:
                return 0
                
            cum_volume = 0
            cum_pv = 0
            
            for bar in bars:
                cum_volume += bar.volume
                cum_pv += bar.close * bar.volume
                
            return cum_pv / cum_volume if cum_volume > 0 else bars[-1].close
            
        except Exception as e:
            logger.error(f"[{self.bot_id}] VWAP calculation failed: {e}")
            return 0