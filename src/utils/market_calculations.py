"""
Market calculation utilities without pandas dependency
Efficient implementations for small datasets
"""
from typing import List, Dict, Optional, Tuple, Any
import math
from datetime import datetime

def calculate_sma(values: List[float], period: int) -> Optional[float]:
    """Simple moving average"""
    if len(values) < period:
        return None
    return sum(values[-period:]) / period

def calculate_ema(values: List[float], period: int) -> List[float]:
    """Exponential moving average"""
    if len(values) < period:
        return []
    
    ema_values = []
    multiplier = 2 / (period + 1)
    
    # Start with SMA
    sma = sum(values[:period]) / period
    ema_values.append(sma)
    
    # Calculate EMA
    for i in range(period, len(values)):
        ema = (values[i] - ema_values[-1]) * multiplier + ema_values[-1]
        ema_values.append(ema)
    
    return ema_values

def calculate_rsi(values: List[float], period: int = 14) -> Optional[float]:
    """Relative Strength Index"""
    if len(values) < period + 1:
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
    
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    
    if avg_loss == 0:
        return 100.0
    
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    
    return rsi

def calculate_atr(highs: List[float], lows: List[float], closes: List[float], period: int = 14) -> Optional[float]:
    """Average True Range"""
    if len(highs) < period + 1:
        return None
    
    true_ranges = []
    
    for i in range(1, len(highs)):
        true_range = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i-1]),
            abs(lows[i] - closes[i-1])
        )
        true_ranges.append(true_range)
    
    return sum(true_ranges[-period:]) / period

def calculate_adx(highs: List[float], lows: List[float], closes: List[float], period: int = 14) -> Optional[float]:
    """Average Directional Index"""
    if len(highs) < period * 2:
        return None
    
    # Calculate +DM and -DM
    plus_dm = []
    minus_dm = []
    tr_list = []
    
    for i in range(1, len(highs)):
        high_diff = highs[i] - highs[i-1]
        low_diff = lows[i-1] - lows[i]
        
        if high_diff > low_diff and high_diff > 0:
            plus_dm.append(high_diff)
        else:
            plus_dm.append(0)
        
        if low_diff > high_diff and low_diff > 0:
            minus_dm.append(low_diff)
        else:
            minus_dm.append(0)
        
        true_range = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i-1]),
            abs(lows[i] - closes[i-1])
        )
        tr_list.append(true_range)
    
    # Calculate smoothed values
    atr = sum(tr_list[:period]) / period
    plus_di_sum = sum(plus_dm[:period])
    minus_di_sum = sum(minus_dm[:period])
    
    # Smooth the values
    dx_list = []
    
    for i in range(period, len(tr_list)):
        atr = (atr * (period - 1) + tr_list[i]) / period
        plus_di_sum = (plus_di_sum * (period - 1) + plus_dm[i]) / period
        minus_di_sum = (minus_di_sum * (period - 1) + minus_dm[i]) / period
        
        plus_di = (plus_di_sum / atr) * 100 if atr > 0 else 0
        minus_di = (minus_di_sum / atr) * 100 if atr > 0 else 0
        
        di_sum = plus_di + minus_di
        if di_sum > 0:
            dx = abs(plus_di - minus_di) / di_sum * 100
            dx_list.append(dx)
    
    if len(dx_list) >= period:
        adx = sum(dx_list[-period:]) / period
        return adx
    
    return None

def calculate_bollinger_bands(values: List[float], period: int = 20, std_dev: int = 2) -> Tuple[Optional[float], Optional[float], Optional[float]]:
    """Bollinger Bands (middle, upper, lower)"""
    if len(values) < period:
        return None, None, None
    
    sma = calculate_sma(values, period)
    if sma is None:
        return None, None, None
    
    # Calculate standard deviation
    variance = sum((x - sma) ** 2 for x in values[-period:]) / period
    std = math.sqrt(variance)
    
    upper = sma + (std_dev * std)
    lower = sma - (std_dev * std)
    
    return sma, upper, lower

def find_support_resistance(prices: List[float], window: int = 20) -> Dict[str, float]:
    """Find support and resistance levels"""
    if len(prices) < window:
        return {'support': 0, 'resistance': 0}
    
    recent_prices = prices[-window:]
    
    # Simple approach: use recent highs and lows
    support = min(recent_prices)
    resistance = max(recent_prices)
    
    # Find stronger levels by looking for price clusters
    price_levels = {}
    for price in recent_prices:
        rounded_price = round(price, 2)
        price_levels[rounded_price] = price_levels.get(rounded_price, 0) + 1
    
    # Sort by frequency
    sorted_levels = sorted(price_levels.items(), key=lambda x: x[1], reverse=True)
    
    if len(sorted_levels) >= 2:
        # Use most frequent levels as support/resistance
        levels = [level[0] for level in sorted_levels[:2]]
        support = min(levels)
        resistance = max(levels)
    
    return {
        'support': support,
        'resistance': resistance,
        'mid_point': (support + resistance) / 2
    }

def calculate_vwap(prices: List[float], volumes: List[float]) -> Optional[float]:
    """Volume Weighted Average Price"""
    if not prices or not volumes or len(prices) != len(volumes):
        return None
    
    total_value = sum(p * v for p, v in zip(prices, volumes))
    total_volume = sum(volumes)
    
    if total_volume == 0:
        return None
    
    return total_value / total_volume

def detect_trend(prices: List[float], period: int = 20) -> str:
    """Simple trend detection"""
    if len(prices) < period:
        return 'neutral'
    
    # Linear regression slope
    n = len(prices[-period:])
    x_sum = n * (n - 1) / 2
    y_sum = sum(prices[-period:])
    xy_sum = sum(i * p for i, p in enumerate(prices[-period:]))
    x_squared_sum = n * (n - 1) * (2 * n - 1) / 6
    
    slope = (n * xy_sum - x_sum * y_sum) / (n * x_squared_sum - x_sum ** 2)
    
    # Normalize slope by average price
    avg_price = y_sum / n
    normalized_slope = slope / avg_price if avg_price > 0 else 0
    
    # Determine trend
    if normalized_slope > 0.001:
        return 'bullish'
    elif normalized_slope < -0.001:
        return 'bearish'
    else:
        return 'neutral'

def calculate_pivot_points(high: float, low: float, close: float) -> Dict[str, float]:
    """Calculate pivot points"""
    pivot = (high + low + close) / 3
    
    r1 = 2 * pivot - low
    s1 = 2 * pivot - high
    
    r2 = pivot + (high - low)
    s2 = pivot - (high - low)
    
    r3 = high + 2 * (pivot - low)
    s3 = low - 2 * (high - pivot)
    
    return {
        'pivot': pivot,
        'r1': r1,
        'r2': r2,
        'r3': r3,
        's1': s1,
        's2': s2,
        's3': s3
    }

def find_opening_range(bars: List[Dict[str, Any]], start_minutes: int = 30) -> Dict[str, float]:
    """Calculate opening range from first N minutes of bars"""
    if not bars or len(bars) < start_minutes:
        return {'high': 0, 'low': 0, 'range': 0}
    
    or_bars = bars[:start_minutes]
    
    high = max(bar['high'] for bar in or_bars)
    low = min(bar['low'] for bar in or_bars)
    
    return {
        'high': high,
        'low': low,
        'range': high - low,
        'midpoint': (high + low) / 2
    }