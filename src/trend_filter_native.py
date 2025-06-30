"""
Trend Filter - Native Python implementation without pandas
Advanced trend detection and regime identification
"""
import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
import statistics

logger = logging.getLogger(__name__)

class TrendFilter:
    """
    Trend filter to improve signal quality
    Uses multiple indicators without pandas dependency
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def is_trend_favorable(self, signal_type: str, market_data: Dict[str, Any]) -> bool:
        """
        Check if trend is favorable for the signal
        
        Args:
            signal_type: Type of signal (e.g., 'OPENING_DRIVE_LONG')
            market_data: Current market data
            
        Returns:
            True if trend supports signal, False otherwise
        """
        # For now, simplified trend check
        # In production, would use more sophisticated analysis
        
        if 'LONG' in signal_type or 'CALL' in signal_type:
            # Bullish signals need uptrend
            return self._check_uptrend(market_data)
        elif 'SHORT' in signal_type or 'PUT' in signal_type:
            # Bearish signals need downtrend
            return self._check_downtrend(market_data)
        
        return True  # Neutral signals always pass
    
    def _check_uptrend(self, market_data: Dict[str, Any]) -> bool:
        """Check for uptrend conditions"""
        spy_price = market_data.get('spy_price')
        if not spy_price:
            return True  # Default to allowing trade if no data
        
        # Simple trend check - would be more complex in production
        # Check if price is above key moving averages
        return True  # Placeholder
    
    def _check_downtrend(self, market_data: Dict[str, Any]) -> bool:
        """Check for downtrend conditions"""
        spy_price = market_data.get('spy_price')
        if not spy_price:
            return True  # Default to allowing trade if no data
        
        # Simple trend check - would be more complex in production
        # Check if price is below key moving averages
        return True  # Placeholder
    
    def calculate_ema(self, values: List[float], period: int) -> Optional[float]:
        """Calculate Exponential Moving Average"""
        if not values or len(values) < period:
            return None
        
        # EMA calculation
        alpha = 2 / (period + 1)
        ema = values[0]
        
        for value in values[1:]:
            ema = value * alpha + ema * (1 - alpha)
        
        return ema
    
    def calculate_sma(self, values: List[float], period: int) -> Optional[float]:
        """Calculate Simple Moving Average"""
        if not values or len(values) < period:
            return None
        
        return sum(values[-period:]) / period
    
    def calculate_atr(self, bars: List[Dict[str, float]], period: int = 14) -> Optional[float]:
        """Calculate Average True Range"""
        if not bars or len(bars) < period + 1:
            return None
        
        true_ranges = []
        for i in range(1, len(bars)):
            high = bars[i].get('high', 0)
            low = bars[i].get('low', 0)
            prev_close = bars[i-1].get('close', 0)
            
            tr = max(
                high - low,
                abs(high - prev_close),
                abs(low - prev_close)
            )
            true_ranges.append(tr)
        
        if len(true_ranges) < period:
            return None
        
        # Simple moving average of true ranges
        return sum(true_ranges[-period:]) / period
    
    def calculate_rsi(self, values: List[float], period: int = 14) -> Optional[float]:
        """Calculate Relative Strength Index"""
        if not values or len(values) < period + 1:
            return None
        
        gains = []
        losses = []
        
        for i in range(1, len(values)):
            change = values[i] - values[i-1]
            if change > 0:
                gains.append(change)
                losses.append(0)
            else:
                gains.append(0)
                losses.append(abs(change))
        
        if len(gains) < period:
            return None
        
        avg_gain = sum(gains[-period:]) / period
        avg_loss = sum(losses[-period:]) / period
        
        if avg_loss == 0:
            return 100  # Max RSI
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi
    
    def get_trend_strength(self, bars: List[Dict[str, float]]) -> Dict[str, Any]:
        """
        Calculate trend strength indicators
        
        Args:
            bars: List of bar dictionaries with OHLC data
            
        Returns:
            Dictionary with trend indicators
        """
        if not bars or len(bars) < 50:
            return {
                'trend': 'neutral',
                'strength': 0,
                'ema_alignment': False,
                'momentum': 0
            }
        
        # Extract close prices
        closes = [bar.get('close', 0) for bar in bars]
        
        # Calculate EMAs
        ema_8 = self.calculate_ema(closes, 8)
        ema_21 = self.calculate_ema(closes, 21)
        ema_50 = self.calculate_ema(closes, 50)
        
        current_price = closes[-1]
        
        # Determine trend
        trend = 'neutral'
        if ema_8 and ema_21 and ema_50:
            if ema_8 > ema_21 > ema_50 and current_price > ema_8:
                trend = 'bullish'
            elif ema_8 < ema_21 < ema_50 and current_price < ema_8:
                trend = 'bearish'
        
        # Calculate trend strength (0-100)
        strength = 0
        if trend != 'neutral' and ema_8 and ema_50:
            # Distance from EMAs as strength indicator
            distance = abs(ema_8 - ema_50) / ema_50 * 100
            strength = min(100, distance * 10)  # Scale to 0-100
        
        # Calculate momentum (rate of change)
        momentum = 0
        if len(closes) >= 10:
            momentum = ((closes[-1] - closes[-10]) / closes[-10]) * 100
        
        return {
            'trend': trend,
            'strength': strength,
            'ema_alignment': trend != 'neutral',
            'momentum': momentum,
            'ema_8': ema_8,
            'ema_21': ema_21,
            'ema_50': ema_50
        }
    
    def get_market_regime(self, bars: List[Dict[str, float]]) -> str:
        """
        Identify market regime
        
        Returns:
            'trending', 'ranging', or 'volatile'
        """
        if not bars or len(bars) < 20:
            return 'unknown'
        
        # Calculate ATR for volatility
        atr = self.calculate_atr(bars)
        closes = [bar.get('close', 0) for bar in bars]
        
        if not atr or not closes:
            return 'unknown'
        
        # Calculate average close price
        avg_close = sum(closes[-20:]) / 20
        
        # Volatility as percentage of price
        volatility = (atr / avg_close) * 100 if avg_close > 0 else 0
        
        # Price range over period
        high_20 = max(bar.get('high', 0) for bar in bars[-20:])
        low_20 = min(bar.get('low', 0) for bar in bars[-20:])
        range_pct = ((high_20 - low_20) / low_20 * 100) if low_20 > 0 else 0
        
        # Determine regime
        if volatility > 2:
            return 'volatile'
        elif range_pct < 1:
            return 'ranging'
        else:
            return 'trending'
    
    def filter_signal_by_trend(self, 
                              signal_type: str,
                              signal_strength: float,
                              bars: List[Dict[str, float]]) -> Tuple[bool, str]:
        """
        Filter signal based on trend analysis
        
        Args:
            signal_type: Type of signal
            signal_strength: Signal strength (0-100)
            bars: Historical price bars
            
        Returns:
            (should_trade, reason)
        """
        # Get trend indicators
        trend_data = self.get_trend_strength(bars)
        regime = self.get_market_regime(bars)
        
        # Extract signal direction
        is_bullish_signal = 'LONG' in signal_type or 'CALL' in signal_type
        is_bearish_signal = 'SHORT' in signal_type or 'PUT' in signal_type
        
        # Check trend alignment
        if is_bullish_signal and trend_data['trend'] == 'bearish':
            return False, "Bullish signal against bearish trend"
        
        if is_bearish_signal and trend_data['trend'] == 'bullish':
            return False, "Bearish signal against bullish trend"
        
        # Check regime suitability
        if regime == 'volatile' and signal_strength < 70:
            return False, "Signal too weak for volatile regime"
        
        if regime == 'ranging' and 'BREAKOUT' not in signal_type:
            return False, "Non-breakout signal in ranging market"
        
        # Check momentum
        if is_bullish_signal and trend_data['momentum'] < -2:
            return False, "Negative momentum for bullish signal"
        
        if is_bearish_signal and trend_data['momentum'] > 2:
            return False, "Positive momentum for bearish signal"
        
        return True, "Signal passes trend filter"