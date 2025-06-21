"""
ST0CKG - Opening Range Breakout Strategy Implementation
"""
from datetime import datetime, time, timedelta
from typing import Dict, List, Optional, Tuple
import logging
import numpy as np
import pandas as pd

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from bots.base.strategy import BaseStrategy, Signal

logger = logging.getLogger(__name__)


class OpeningRangeBreakoutStrategy(BaseStrategy):
    """Opening Range Breakout strategy for SPY options"""
    
    def __init__(self, bot_id: str, config: Dict):
        super().__init__(bot_id, config)
        
        # Market data provider (will be set during initialization)
        self.market_data = None
        
        # Opening range data
        self.opening_range_high = None
        self.opening_range_low = None
        self.opening_range_calculated = False
        
        # Technical indicators
        self.current_atr = None
        self.current_ema_fast = None
        self.current_ema_slow = None
        self.current_volume_ratio = None
        
        # Signal tracking
        self.last_breakout_time = None
        self.breakout_confirmed = False
    
    def initialize(self, market_data_provider) -> bool:
        """Initialize strategy with market data provider"""
        try:
            self.market_data = market_data_provider
            self.is_initialized = True
            logger.info(f"[{self.bot_id}] Opening Range Breakout strategy initialized")
            return True
        except Exception as e:
            logger.error(f"[{self.bot_id}] Failed to initialize strategy: {e}")
            return False
    
    def check_entry_conditions(self, current_price: float, market_data: Dict) -> Optional[Signal]:
        """Check for opening range breakout signals"""
        current_time = datetime.now().time()
        
        # Calculate opening range if not done
        if not self.opening_range_calculated and current_time >= self.config['opening_range_end']:
            self._calculate_opening_range()
        
        # Can't trade without opening range
        if not self.opening_range_calculated:
            return None
        
        # Update technical indicators
        self._update_indicators(market_data)
        
        # Check for breakouts
        signal = None
        
        # Long breakout
        if current_price > self.opening_range_high * (1 + self.config['breakout_threshold']):
            if self._confirm_breakout('LONG', current_price, market_data):
                signal = Signal(
                    signal_type='LONG',
                    strength=self._calculate_signal_strength('LONG', current_price),
                    metadata={
                        'or_high': self.opening_range_high,
                        'or_low': self.opening_range_low,
                        'breakout_price': current_price,
                        'atr': self.current_atr,
                        'ema_fast': self.current_ema_fast,
                        'ema_slow': self.current_ema_slow,
                        'volume_ratio': self.current_volume_ratio
                    }
                )
        
        # Short breakout
        elif current_price < self.opening_range_low * (1 - self.config['breakout_threshold']):
            if self._confirm_breakout('SHORT', current_price, market_data):
                signal = Signal(
                    signal_type='SHORT',
                    strength=self._calculate_signal_strength('SHORT', current_price),
                    metadata={
                        'or_high': self.opening_range_high,
                        'or_low': self.opening_range_low,
                        'breakout_price': current_price,
                        'atr': self.current_atr,
                        'ema_fast': self.current_ema_fast,
                        'ema_slow': self.current_ema_slow,
                        'volume_ratio': self.current_volume_ratio
                    }
                )
        
        # Avoid duplicate signals
        if signal and self.last_breakout_time:
            if (datetime.now() - self.last_breakout_time).seconds < 300:  # 5 min cooldown
                return None
        
        if signal:
            self.last_breakout_time = datetime.now()
            logger.info(f"[{self.bot_id}] {signal.type} signal generated at ${current_price:.2f}")
        
        return signal
    
    def _calculate_opening_range(self):
        """Calculate the opening range"""
        try:
            # Get 1-minute bars for opening range period
            bars = self.market_data.get_bars(
                'SPY', 
                '1Min',
                start=datetime.combine(datetime.now().date(), self.config['opening_range_start']),
                end=datetime.combine(datetime.now().date(), self.config['opening_range_end'])
            )
            
            if bars is not None and not bars.empty:
                self.opening_range_high = float(bars['high'].max())
                self.opening_range_low = float(bars['low'].min())
                
                # Validate range
                range_size = self.opening_range_high - self.opening_range_low
                if range_size >= self.config['min_opening_range']:
                    self.opening_range_calculated = True
                    logger.info(f"[{self.bot_id}] Opening Range: ${self.opening_range_low:.2f} - ${self.opening_range_high:.2f}")
                else:
                    logger.warning(f"[{self.bot_id}] Opening range too small: ${range_size:.2f}")
            
        except Exception as e:
            logger.error(f"[{self.bot_id}] Error calculating opening range: {e}")
    
    def _update_indicators(self, market_data: Dict):
        """Update technical indicators"""
        try:
            # Get recent bars for indicators
            bars = self.market_data.get_bars('SPY', '5Min', lookback_periods=50)
            
            if bars is not None and len(bars) >= 20:
                # Calculate EMAs
                self.current_ema_fast = bars['close'].ewm(span=self.config['ema_fast']).mean().iloc[-1]
                self.current_ema_slow = bars['close'].ewm(span=self.config['ema_slow']).mean().iloc[-1]
                
                # Calculate ATR
                high_low = bars['high'] - bars['low']
                high_close = np.abs(bars['high'] - bars['close'].shift())
                low_close = np.abs(bars['low'] - bars['close'].shift())
                ranges = pd.concat([high_low, high_close, low_close], axis=1)
                true_range = ranges.max(axis=1)
                self.current_atr = true_range.rolling(self.config['atr_period']).mean().iloc[-1]
                
                # Calculate volume ratio
                avg_volume = bars['volume'].rolling(self.config['volume_ma_period']).mean().iloc[-1]
                current_volume = bars['volume'].iloc[-1]
                self.current_volume_ratio = current_volume / avg_volume if avg_volume > 0 else 0
                
        except Exception as e:
            logger.error(f"[{self.bot_id}] Error updating indicators: {e}")
    
    def _confirm_breakout(self, direction: str, current_price: float, market_data: Dict) -> bool:
        """Confirm breakout with additional filters"""
        # Volume confirmation
        if self.current_volume_ratio and self.current_volume_ratio < self.config['min_volume_ratio']:
            return False
        
        # Trend filter
        if self.config['use_trend_filter'] and self.current_ema_fast and self.current_ema_slow:
            if direction == 'LONG' and self.current_ema_fast < self.current_ema_slow:
                return False
            elif direction == 'SHORT' and self.current_ema_fast > self.current_ema_slow:
                return False
        
        # ATR filter
        if self.current_atr:
            if self.current_atr < self.config['min_atr'] or self.current_atr > self.config['max_atr']:
                return False
        
        return True
    
    def _calculate_signal_strength(self, direction: str, current_price: float) -> float:
        """Calculate signal strength based on breakout magnitude and indicators"""
        base_strength = 0.5
        
        # Breakout magnitude
        if direction == 'LONG':
            breakout_pct = (current_price - self.opening_range_high) / self.opening_range_high
        else:
            breakout_pct = (self.opening_range_low - current_price) / self.opening_range_low
        
        base_strength += min(breakout_pct * 10, 0.3)  # Max 0.3 from breakout
        
        # Volume confirmation
        if self.current_volume_ratio and self.current_volume_ratio > 2.0:
            base_strength += 0.1
        
        # Trend alignment
        if self.current_ema_fast and self.current_ema_slow:
            if direction == 'LONG' and self.current_ema_fast > self.current_ema_slow:
                base_strength += 0.1
            elif direction == 'SHORT' and self.current_ema_fast < self.current_ema_slow:
                base_strength += 0.1
        
        return min(base_strength, 1.0)
    
    def calculate_position_size(self, signal: Signal, account_balance: float, 
                              current_price: float) -> int:
        """Calculate position size based on risk management rules"""
        # Risk per trade
        risk_amount = account_balance * self.config['max_risk_per_trade']
        
        # Calculate stop distance
        if signal.type == 'LONG':
            stop_distance = current_price - self.opening_range_low
        else:
            stop_distance = self.opening_range_high - current_price
        
        # Position size based on risk
        if stop_distance > 0:
            # Assuming $1 per contract per dollar move (simplified)
            position_size = int(risk_amount / (stop_distance * 100))
        else:
            position_size = 1
        
        # Apply maximum position size limit
        max_position_value = account_balance * self.config['max_position_size']
        max_contracts = int(max_position_value / (current_price * 100))
        
        return min(position_size, max_contracts, 10)  # Cap at 10 contracts
    
    def get_exit_levels(self, signal: Signal, entry_price: float) -> Dict:
        """Calculate exit levels for the position"""
        exit_levels = {}
        
        # Stop loss
        if signal.type == 'LONG':
            exit_levels['stop_loss'] = self.opening_range_low
        else:
            exit_levels['stop_loss'] = self.opening_range_high
        
        # Targets based on ATR
        if self.current_atr:
            if signal.type == 'LONG':
                exit_levels['target_1'] = entry_price + (self.current_atr * self.config['target_1_atr_multiplier'])
                exit_levels['target_2'] = entry_price + (self.current_atr * self.config['target_2_atr_multiplier'])
            else:
                exit_levels['target_1'] = entry_price - (self.current_atr * self.config['target_1_atr_multiplier'])
                exit_levels['target_2'] = entry_price - (self.current_atr * self.config['target_2_atr_multiplier'])
        else:
            # Fallback to percentage-based targets
            if signal.type == 'LONG':
                exit_levels['target_1'] = entry_price * 1.005  # 0.5%
                exit_levels['target_2'] = entry_price * 1.010  # 1.0%
            else:
                exit_levels['target_1'] = entry_price * 0.995
                exit_levels['target_2'] = entry_price * 0.990
        
        return exit_levels
    
    def check_exit_conditions(self, position: Dict, current_price: float, 
                            market_data: Dict) -> Tuple[bool, str]:
        """Check if position should be exited"""
        signal_type = position['signal']['type']
        
        # Time stop
        if datetime.now().time() >= self.config['time_stop']:
            return True, 'TIME_STOP'
        
        # Stop loss
        if signal_type == 'LONG' and current_price <= position['stop_loss']:
            return True, 'STOP_LOSS'
        elif signal_type == 'SHORT' and current_price >= position['stop_loss']:
            return True, 'STOP_LOSS'
        
        # Target exits (would need option price, not underlying price)
        # This is simplified - real implementation would check option prices
        
        # Trailing stop if activated
        if 'trailing_stop' in position:
            if signal_type == 'LONG' and current_price <= position['trailing_stop']:
                return True, 'TRAILING_STOP'
            elif signal_type == 'SHORT' and current_price >= position['trailing_stop']:
                return True, 'TRAILING_STOP'
        
        return False, ''
    
    def get_option_selection_criteria(self, signal: Signal) -> Dict:
        """Get criteria for option selection"""
        return {
            'dte_min': self.config['target_dte_min'],
            'dte_max': self.config['target_dte_max'],
            'target_delta': self.config['target_delta'],
            'delta_range': self.config['delta_range'],
            'min_volume': self.config['min_volume'],
            'max_spread_pct': self.config['max_spread_pct'],
            'option_type': 'CALL' if signal.type == 'LONG' else 'PUT'
        }
    
    def should_trade_today(self) -> bool:
        """Check if should trade today"""
        # Skip weekends
        if datetime.now().weekday() >= 5:
            return False
        
        # Could add holiday calendar check here
        
        # Reset daily state
        if datetime.now().time() < time(9, 0):
            self.opening_range_calculated = False
            self.opening_range_high = None
            self.opening_range_low = None
            self.last_breakout_time = None
        
        return True