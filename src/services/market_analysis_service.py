"""
Market analysis service - Handles technical analysis and market data processing
"""
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
import numpy as np

from ..unified_logging import get_logger
from ..unified_cache import UnifiedCache, CacheKeyBuilder
from ..unified_market_data import UnifiedMarketData

class MarketAnalysisService:
    """
    Provides market analysis functionality
    Separates analysis logic from data retrieval
    """
    
    def __init__(self, 
                 market_data: UnifiedMarketData,
                 cache: UnifiedCache):
        """
        Initialize market analysis service
        
        Args:
            market_data: Market data provider
            cache: Cache manager
        """
        self.market_data = market_data
        self.cache = cache
        self.logger = get_logger(__name__)
    
    async def calculate_indicators(self, 
                                 symbol: str,
                                 period: int = 20) -> Dict[str, Any]:
        """
        Calculate technical indicators for a symbol
        
        Args:
            symbol: Stock symbol
            period: Period for indicators
            
        Returns:
            Dict with indicator values
        """
        # Check cache first
        cache_key = f"indicators:{symbol}:{period}"
        cached = self.cache.get(cache_key)
        if cached:
            return cached
        
        try:
            # Get historical data
            bars = await self.market_data.get_bars(symbol, limit=period * 2)
            if not bars or len(bars) < period:
                return {}
            
            # Extract price arrays
            closes = np.array([bar['close'] for bar in bars])
            highs = np.array([bar['high'] for bar in bars])
            lows = np.array([bar['low'] for bar in bars])
            volumes = np.array([bar['volume'] for bar in bars])
            
            # Calculate indicators
            indicators = {
                'sma': self._calculate_sma(closes, period),
                'ema': self._calculate_ema(closes, period),
                'rsi': self._calculate_rsi(closes, 14),
                'atr': self._calculate_atr(highs, lows, closes, 14),
                'volume_avg': np.mean(volumes[-period:]),
                'price': closes[-1],
                'change': closes[-1] - closes[-2],
                'change_pct': ((closes[-1] - closes[-2]) / closes[-2]) * 100
            }
            
            # Add VWAP
            vwaps = [bar.get('vwap') for bar in bars if bar.get('vwap')]
            if vwaps:
                indicators['vwap'] = vwaps[-1]
            
            # Cache results
            self.cache.set(cache_key, indicators, 60)  # 1 minute cache
            
            return indicators
            
        except Exception as e:
            self.logger.error(f"Failed to calculate indicators for {symbol}: {e}")
            return {}
    
    async def detect_patterns(self, symbol: str) -> Dict[str, Any]:
        """
        Detect chart patterns
        
        Returns:
            Dict with detected patterns
        """
        try:
            # Get recent bars
            bars = await self.market_data.get_bars(symbol, limit=50)
            if not bars or len(bars) < 20:
                return {}
            
            closes = [bar['close'] for bar in bars]
            highs = [bar['high'] for bar in bars]
            lows = [bar['low'] for bar in bars]
            
            patterns = {
                'trend': self._detect_trend(closes),
                'support': self._find_support_resistance(lows, closes)['support'],
                'resistance': self._find_support_resistance(highs, closes)['resistance'],
                'breakout': self._detect_breakout(closes, highs, lows)
            }
            
            return patterns
            
        except Exception as e:
            self.logger.error(f"Failed to detect patterns for {symbol}: {e}")
            return {}
    
    async def get_market_breadth(self) -> Dict[str, Any]:
        """
        Calculate market breadth indicators (SPY only)
        """
        try:
            # Get quote for SPY only
            quote = await self.market_data.get_quote('SPY')
            
            if not quote:
                return {}
            
            # Simple breadth based on SPY movement
            change = quote.get('change', 0)
            change_pct = quote.get('change_percent', 0)
            
            breadth = {
                'spy_change': change,
                'spy_change_pct': change_pct,
                'sentiment': 'bullish' if change > 0 else 'bearish' if change < 0 else 'neutral',
                'strength': 'strong' if abs(change_pct) > 0.5 else 'moderate' if abs(change_pct) > 0.2 else 'weak'
            }
            
            return breadth
            
        except Exception as e:
            self.logger.error(f"Failed to calculate market breadth: {e}")
            return {}
    
    def _calculate_sma(self, prices: np.ndarray, period: int) -> float:
        """Simple moving average"""
        if len(prices) < period:
            return 0.0
        return float(np.mean(prices[-period:]))
    
    def _calculate_ema(self, prices: np.ndarray, period: int) -> float:
        """Exponential moving average"""
        if len(prices) < period:
            return 0.0
        
        alpha = 2 / (period + 1)
        ema = prices[0]
        
        for price in prices[1:]:
            ema = alpha * price + (1 - alpha) * ema
        
        return float(ema)
    
    def _calculate_rsi(self, prices: np.ndarray, period: int = 14) -> float:
        """Relative Strength Index"""
        if len(prices) < period + 1:
            return 50.0
        
        deltas = np.diff(prices)
        gains = deltas.copy()
        losses = deltas.copy()
        
        gains[gains < 0] = 0
        losses[losses > 0] = 0
        losses = np.abs(losses)
        
        avg_gain = np.mean(gains[-period:])
        avg_loss = np.mean(losses[-period:])
        
        if avg_loss == 0:
            return 100.0
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        return float(rsi)
    
    def _calculate_atr(self, highs: np.ndarray, lows: np.ndarray, 
                      closes: np.ndarray, period: int = 14) -> float:
        """Average True Range"""
        if len(highs) < period + 1:
            return 0.0
        
        tr_list = []
        for i in range(1, len(highs)):
            tr = max(
                highs[i] - lows[i],
                abs(highs[i] - closes[i-1]),
                abs(lows[i] - closes[i-1])
            )
            tr_list.append(tr)
        
        if len(tr_list) >= period:
            return float(np.mean(tr_list[-period:]))
        return 0.0
    
    def _detect_trend(self, prices: List[float]) -> str:
        """Detect price trend"""
        if len(prices) < 20:
            return 'neutral'
        
        # Simple trend detection using linear regression
        x = np.arange(len(prices))
        slope = np.polyfit(x, prices, 1)[0]
        
        # Normalize slope by price
        normalized_slope = slope / np.mean(prices)
        
        if normalized_slope > 0.001:
            return 'bullish'
        elif normalized_slope < -0.001:
            return 'bearish'
        else:
            return 'neutral'
    
    def _find_support_resistance(self, lows: List[float], 
                               highs: List[float]) -> Dict[str, float]:
        """Find support and resistance levels"""
        if len(lows) < 10:
            return {'support': 0, 'resistance': 0}
        
        # Simple approach: use recent lows/highs
        support = min(lows[-10:])
        resistance = max(highs[-10:])
        
        return {
            'support': round(support, 2),
            'resistance': round(resistance, 2)
        }
    
    def _detect_breakout(self, closes: List[float], 
                        highs: List[float], 
                        lows: List[float]) -> Optional[str]:
        """Detect breakout patterns"""
        if len(closes) < 20:
            return None
        
        # Check if current price breaks recent range
        recent_high = max(highs[-20:-1])
        recent_low = min(lows[-20:-1])
        current_price = closes[-1]
        
        if current_price > recent_high * 1.01:  # 1% above high
            return 'bullish_breakout'
        elif current_price < recent_low * 0.99:  # 1% below low
            return 'bearish_breakout'
        
        return None