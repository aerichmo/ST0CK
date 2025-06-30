"""
Optimized trend filter without pandas dependency
Uses native Python for better performance on small datasets
"""
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime

from .utils.market_calculations import (
    calculate_ema, calculate_adx, calculate_atr,
    detect_trend, find_support_resistance
)
from .unified_logging import get_logger

class TrendFilter:
    """
    Filters trades based on market trend conditions
    Optimized version without pandas overhead
    """
    
    def __init__(self):
        self.logger = get_logger(__name__)
        
        # Trend parameters
        self.ema_fast = 8
        self.ema_slow = 21
        self.adx_threshold = 25
        self.atr_multiplier = 1.5
        
        # Cache for calculations
        self._trend_cache = {}
        self._cache_expiry = 60  # seconds
        self._last_cache_time = {}
    
    def get_trend_bias(self, market_data: Dict[str, Any]) -> str:
        """
        Determine overall trend bias
        Returns: 'bullish', 'bearish', or 'neutral'
        """
        try:
            # Extract price data
            bars = market_data.get('bars', [])
            if not bars or len(bars) < self.ema_slow:
                return 'neutral'
            
            # Get closing prices
            closes = [bar['close'] for bar in bars]
            
            # Calculate EMAs
            ema_fast_values = calculate_ema(closes, self.ema_fast)
            ema_slow_values = calculate_ema(closes, self.ema_slow)
            
            if not ema_fast_values or not ema_slow_values:
                return 'neutral'
            
            # Current EMA values
            current_ema_fast = ema_fast_values[-1]
            current_ema_slow = ema_slow_values[-1]
            
            # Previous EMA values for trend confirmation
            prev_ema_fast = ema_fast_values[-2] if len(ema_fast_values) > 1 else current_ema_fast
            prev_ema_slow = ema_slow_values[-2] if len(ema_slow_values) > 1 else current_ema_slow
            
            # Determine bias
            if current_ema_fast > current_ema_slow and prev_ema_fast > prev_ema_slow:
                # Check trend strength
                separation = (current_ema_fast - current_ema_slow) / current_ema_slow * 100
                if separation > 0.1:  # 0.1% separation minimum
                    return 'bullish'
            elif current_ema_fast < current_ema_slow and prev_ema_fast < prev_ema_slow:
                separation = (current_ema_slow - current_ema_fast) / current_ema_slow * 100
                if separation > 0.1:
                    return 'bearish'
            
            return 'neutral'
            
        except Exception as e:
            self.logger.error(f"Error calculating trend bias: {e}")
            return 'neutral'
    
    def check_entry_trigger(self, signal_type: str, market_data: Dict[str, Any]) -> bool:
        """
        Check if trend conditions support entry
        """
        try:
            # Get trend bias
            trend_bias = self.get_trend_bias(market_data)
            
            # Get current bar
            bars = market_data.get('bars', [])
            if not bars:
                return False
            
            current_bar = bars[-1]
            
            # Bullish signals need bullish or neutral trend
            if 'CALL' in signal_type.upper() or 'LONG' in signal_type.upper():
                if trend_bias == 'bearish':
                    self.logger.info(f"Bullish signal {signal_type} filtered by bearish trend")
                    return False
                
                # Additional bullish checks
                if len(bars) > 1:
                    # Price should be above previous close
                    if current_bar['close'] < bars[-2]['close']:
                        return False
            
            # Bearish signals need bearish or neutral trend
            elif 'PUT' in signal_type.upper() or 'SHORT' in signal_type.upper():
                if trend_bias == 'bullish':
                    self.logger.info(f"Bearish signal {signal_type} filtered by bullish trend")
                    return False
                
                # Additional bearish checks
                if len(bars) > 1:
                    # Price should be below previous close
                    if current_bar['close'] > bars[-2]['close']:
                        return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error checking entry trigger: {e}")
            return True  # Don't filter on error
    
    def validate_market_conditions(self, market_data: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Validate overall market conditions
        Returns: (is_valid, reason)
        """
        try:
            bars = market_data.get('bars', [])
            if not bars or len(bars) < 20:
                return True, "Insufficient data"
            
            # Extract data
            closes = [bar['close'] for bar in bars]
            highs = [bar['high'] for bar in bars]
            lows = [bar['low'] for bar in bars]
            
            # Check volatility
            atr = calculate_atr(highs, lows, closes, 14)
            if atr:
                avg_price = sum(closes[-20:]) / 20
                volatility_pct = (atr / avg_price) * 100
                
                # High volatility check
                if volatility_pct > 5.0:  # 5% ATR
                    return False, f"High volatility: {volatility_pct:.1f}%"
                
                # Low volatility check
                if volatility_pct < 0.1:  # 0.1% ATR
                    return False, f"Low volatility: {volatility_pct:.1f}%"
            
            return True, "Conditions valid"
            
        except Exception as e:
            self.logger.error(f"Error validating market conditions: {e}")
            return True, "Validation error"
    
    def calculate_market_regime(self, market_data: Dict[str, Any]) -> str:
        """
        Determine market regime: trending, ranging, or volatile
        """
        try:
            bars = market_data.get('bars', [])
            if not bars or len(bars) < 30:
                return 'unknown'
            
            # Extract data
            closes = [bar['close'] for bar in bars]
            highs = [bar['high'] for bar in bars]
            lows = [bar['low'] for bar in bars]
            
            # Calculate ADX for trend strength
            adx = calculate_adx(highs, lows, closes, 14)
            
            # Calculate volatility
            atr = calculate_atr(highs, lows, closes, 14)
            avg_price = sum(closes[-20:]) / 20
            volatility_pct = (atr / avg_price) * 100 if atr and avg_price > 0 else 0
            
            # Determine regime
            if adx and adx > self.adx_threshold:
                return 'trending'
            elif volatility_pct > 3.0:
                return 'volatile'
            else:
                return 'ranging'
                
        except Exception as e:
            self.logger.error(f"Error calculating market regime: {e}")
            return 'unknown'
    
    def is_trend_favorable(self, signal_type: str, market_data: Dict[str, Any]) -> bool:
        """
        Main method to check if trend conditions are favorable
        """
        # Check entry trigger
        if not self.check_entry_trigger(signal_type, market_data):
            return False
        
        # Validate market conditions
        is_valid, reason = self.validate_market_conditions(market_data)
        if not is_valid:
            self.logger.info(f"Market conditions unfavorable: {reason}")
            return False
        
        # Check market regime
        regime = self.calculate_market_regime(market_data)
        if regime == 'volatile':
            self.logger.info("Market regime too volatile")
            return False
        
        return True
    
    def get_trend_levels(self, market_data: Dict[str, Any]) -> Dict[str, float]:
        """
        Get key trend levels for position management
        """
        try:
            bars = market_data.get('bars', [])
            if not bars or len(bars) < 20:
                return {}
            
            closes = [bar['close'] for bar in bars]
            
            # Calculate EMAs
            ema_fast_values = calculate_ema(closes, self.ema_fast)
            ema_slow_values = calculate_ema(closes, self.ema_slow)
            
            # Find support/resistance
            levels = find_support_resistance(closes, 20)
            
            trend_levels = {
                'ema_fast': ema_fast_values[-1] if ema_fast_values else 0,
                'ema_slow': ema_slow_values[-1] if ema_slow_values else 0,
                'support': levels['support'],
                'resistance': levels['resistance'],
                'midpoint': levels['mid_point']
            }
            
            return trend_levels
            
        except Exception as e:
            self.logger.error(f"Error getting trend levels: {e}")
            return {}
    
    def check_breakout(self, current_price: float, market_data: Dict[str, Any]) -> Optional[str]:
        """
        Check for trend breakouts
        """
        try:
            levels = self.get_trend_levels(market_data)
            if not levels:
                return None
            
            # Breakout thresholds
            breakout_pct = 0.002  # 0.2%
            
            # Check resistance breakout
            if levels['resistance'] > 0:
                if current_price > levels['resistance'] * (1 + breakout_pct):
                    return 'resistance_break'
            
            # Check support breakdown
            if levels['support'] > 0:
                if current_price < levels['support'] * (1 - breakout_pct):
                    return 'support_break'
            
            # Check EMA crossovers
            if levels['ema_fast'] > 0 and levels['ema_slow'] > 0:
                fast_above = current_price > levels['ema_fast']
                slow_above = current_price > levels['ema_slow']
                
                if fast_above and not slow_above:
                    return 'ema_fast_cross'
                elif not fast_above and slow_above:
                    return 'ema_slow_cross'
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error checking breakout: {e}")
            return None