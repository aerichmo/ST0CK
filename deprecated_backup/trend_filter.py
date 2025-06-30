import pandas as pd
import numpy as np
from typing import Optional, Dict, Tuple
import logging
from datetime import datetime, time
import pytz

logger = logging.getLogger(__name__)

class TrendFilter:
    def __init__(self, config: dict):
        self.config = config
        self.ema_fast = config["trend_filter"]["ema_fast"]
        self.ema_slow = config["trend_filter"]["ema_slow"]
        self.timezone = config["session"]["timezone"]
        self.market_data = None  # Will be set by trading engine
        self.opening_ranges = {}  # Will be set by trading engine
        
    def get_trend_bias(self, data: pd.DataFrame) -> Optional[str]:
        """
        Determine trend bias based on EMA configuration
        Returns: 'LONG', 'SHORT', or None
        """
        if data.empty or len(data) < self.ema_slow:
            return None
            
        try:
            current_ema_fast = data['EMA_8'].iloc[-1]
            current_ema_slow = data['EMA_21'].iloc[-1]
            prev_ema_fast = data['EMA_8'].iloc[-2]
            prev_ema_slow = data['EMA_21'].iloc[-2]
            
            fast_rising = current_ema_fast > prev_ema_fast
            slow_rising = current_ema_slow > prev_ema_slow
            fast_falling = current_ema_fast < prev_ema_fast
            slow_falling = current_ema_slow < prev_ema_slow
            
            if current_ema_fast > current_ema_slow and fast_rising and slow_rising:
                return 'LONG'
            elif current_ema_fast < current_ema_slow and fast_falling and slow_falling:
                return 'SHORT'
            else:
                return None
                
        except Exception as e:
            logger.error(f"Error calculating trend bias: {e}")
            return None
    
    def check_entry_trigger(self, data: pd.DataFrame, orh: float, orl: float, 
                          trend_bias: str) -> Optional[dict]:
        """
        Check if entry conditions are met
        Returns: Entry signal details or None
        """
        if data.empty or orh is None or orl is None:
            return None
            
        try:
            current_bar = data.iloc[-1]
            current_close = current_bar['Close']
            current_volume = current_bar['Volume']
            current_atr = current_bar['ATR']
            avg_volume = current_bar['Volume_MA']
            
            atr_threshold = self.config["entry"]["atr_multiplier"] * current_atr
            volume_threshold = self.config["entry"]["volume_multiplier"] * avg_volume
            
            signal = None
            
            if trend_bias == 'LONG':
                if (current_close > orh + atr_threshold and 
                    current_volume >= volume_threshold):
                    signal = {
                        'type': 'LONG',
                        'entry_price': current_close,
                        'or_level': orh,
                        'atr': current_atr,
                        'volume_ratio': current_volume / avg_volume,
                        'timestamp': data.index[-1],
                        'ema_8': current_bar['EMA_8'],
                        'ema_21': current_bar['EMA_21']
                    }
                    
            elif trend_bias == 'SHORT':
                if (current_close < orl - atr_threshold and 
                    current_volume >= volume_threshold):
                    signal = {
                        'type': 'SHORT',
                        'entry_price': current_close,
                        'or_level': orl,
                        'atr': current_atr,
                        'volume_ratio': current_volume / avg_volume,
                        'timestamp': data.index[-1],
                        'ema_8': current_bar['EMA_8'],
                        'ema_21': current_bar['EMA_21']
                    }
            
            return signal
            
        except Exception as e:
            logger.error(f"Error checking entry trigger: {e}")
            return None
    
    def validate_market_conditions(self, data: pd.DataFrame) -> bool:
        """Additional market condition validations"""
        if data.empty or len(data) < 50:
            return False
            
        try:
            recent_volatility = data['ATR'].iloc[-1] / data['Close'].iloc[-1]
            
            if recent_volatility < 0.001:
                logger.info("Market volatility too low")
                return False
            
            if recent_volatility > 0.05:
                logger.info("Market volatility too high")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error validating market conditions: {e}")
            return False
    
    def calculate_market_regime(self, data: pd.DataFrame) -> Dict:
        """Calculate current market regime using multiple indicators"""
        if len(data) < 50:
            return {"regime": "UNKNOWN", "confidence": 0}
        
        try:
            # 1. Volatility regime using ATR/Price ratio
            recent_volatility = data['ATR'].iloc[-20:].mean() / data['Close'].iloc[-20:].mean()
            
            # Calculate volatility percentile
            vol_series = data['ATR'].rolling(20).mean() / data['Close'].rolling(20).mean()
            vol_series = vol_series.dropna()
            if len(vol_series) >= 200:
                volatility_percentile = (recent_volatility > vol_series.iloc[-200:]).sum() / 200
            else:
                volatility_percentile = 0.5
            
            # 2. Trend strength using price momentum
            price_momentum = (data['Close'].iloc[-1] - data['Close'].iloc[-20]) / data['Close'].iloc[-20]
            
            # 3. Volume regime
            volume_ratio = data['Volume'].iloc[-5:].mean() / data['Volume'].iloc[-50:].mean()
            
            # 4. Opening range analysis (if available)
            or_width = 0
            or_quality = "UNKNOWN"
            if 'SPY' in self.opening_ranges and data['ATR'].iloc[-1] > 0:
                or_high = self.opening_ranges['SPY']['high']
                or_low = self.opening_ranges['SPY']['low']
                or_width = (or_high - or_low) / data['ATR'].iloc[-1]
                or_quality = "TIGHT" if or_width < 0.5 else ("NORMAL" if or_width < 1.0 else "WIDE")
            
            # 5. Calculate ADX for trend strength
            adx = self._calculate_adx(data)
            
            # Classify regime
            if recent_volatility > 0.03 or volatility_percentile > 0.8:
                regime = "HIGH_VOLATILITY"
            elif adx > 25 and or_width < 0.5:
                regime = "TRENDING"
            elif adx < 20 and or_width > 1.5:
                regime = "CHOPPY"
            else:
                regime = "NORMAL"
            
            return {
                "regime": regime,
                "volatility": recent_volatility,
                "volatility_percentile": volatility_percentile,
                "adx": adx,
                "volume_surge": volume_ratio > 1.5,
                "or_quality": or_quality,
                "or_width": or_width,
                "price_momentum": price_momentum,
                "confidence": min(adx / 40, 1.0)  # Higher ADX = higher confidence
            }
            
        except Exception as e:
            logger.error(f"Error calculating market regime: {e}")
            return {"regime": "UNKNOWN", "confidence": 0}
    
    def _calculate_adx(self, data: pd.DataFrame, period: int = 14) -> float:
        """Calculate Average Directional Index (ADX)"""
        try:
            high = data['High']
            low = data['Low']
            close = data['Close']
            
            # Calculate True Range
            tr1 = high - low
            tr2 = abs(high - close.shift(1))
            tr3 = abs(low - close.shift(1))
            tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            atr = tr.rolling(period).mean()
            
            # Calculate directional movements
            up_move = high - high.shift(1)
            down_move = low.shift(1) - low
            
            pos_dm = pd.Series(0.0, index=data.index)
            neg_dm = pd.Series(0.0, index=data.index)
            
            pos_dm[(up_move > down_move) & (up_move > 0)] = up_move
            neg_dm[(down_move > up_move) & (down_move > 0)] = down_move
            
            # Calculate directional indicators
            pos_di = 100 * (pos_dm.rolling(period).mean() / atr)
            neg_di = 100 * (neg_dm.rolling(period).mean() / atr)
            
            # Calculate ADX
            dx = 100 * abs(pos_di - neg_di) / (pos_di + neg_di)
            adx = dx.rolling(period).mean()
            
            return adx.iloc[-1] if not pd.isna(adx.iloc[-1]) else 0
            
        except Exception as e:
            logger.error(f"Error calculating ADX: {e}")
            return 0
    
    def analyze_premarket_gap(self, symbol: str, current_price: float) -> Dict:
        """Analyze pre-market gap and its implications"""
        try:
            if self.market_data is None:
                return {"gap_pct": 0, "gap_type": "NONE", "trade_bias": "NEUTRAL"}
            
            # Get previous close
            yesterday_close = self.market_data.get_previous_close(symbol)
            if not yesterday_close or yesterday_close <= 0:
                return {"gap_pct": 0, "gap_type": "NONE", "trade_bias": "NEUTRAL"}
            
            gap_pct = (current_price - yesterday_close) / yesterday_close
            
            # Historical gap fill probability (simplified)
            gap_fill_probability = 0.68 if abs(gap_pct) < 0.01 else 0.45
            
            # Determine gap type and trading bias
            if abs(gap_pct) < 0.002:
                gap_type = "NONE"
                gap_size = "NONE"
                trade_bias = "NEUTRAL"
            else:
                gap_type = "UP" if gap_pct > 0 else "DOWN"
                gap_size = "LARGE" if abs(gap_pct) > 0.015 else "SMALL"
                # Fade large gaps, follow small gaps
                trade_bias = "FADE" if abs(gap_pct) > 0.02 else "FOLLOW"
            
            return {
                "gap_pct": gap_pct,
                "gap_type": gap_type,
                "gap_size": gap_size,
                "fill_probability": gap_fill_probability,
                "trade_bias": trade_bias,
                "yesterday_close": yesterday_close,
                "current_price": current_price
            }
            
        except Exception as e:
            logger.error(f"Error analyzing premarket gap: {e}")
            return {"gap_pct": 0, "gap_type": "NONE", "trade_bias": "NEUTRAL"}
    
    def check_breakout(self, symbol: str, latest_bar: pd.Series, 
                      opening_range: Dict) -> Optional[Dict]:
        """Enhanced breakout detection with regime awareness"""
        try:
            # Get full data for regime calculation
            data = self.market_data.get_5min_bars(symbol, lookback_days=2)
            if data.empty:
                return None
            
            # Calculate market regime
            regime = self.calculate_market_regime(data)
            
            # Get pre-market gap analysis
            gap_analysis = self.analyze_premarket_gap(symbol, latest_bar['Close'])
            
            # Get trend bias
            trend_bias = self.get_trend_bias(data)
            
            # Check basic entry conditions
            signal = self.check_entry_trigger(
                data, 
                opening_range['high'], 
                opening_range['low'],
                trend_bias
            )
            
            if signal:
                # Enhance signal with regime and gap data
                signal['market_regime'] = regime
                signal['gap_analysis'] = gap_analysis
                
                # Calculate signal strength based on multiple factors
                strength = self._calculate_signal_strength(signal, regime, gap_analysis)
                signal['strength'] = strength
                
                # Add stop level for risk management
                if signal['type'] == 'LONG':
                    signal['stop_level'] = opening_range['low']
                else:
                    signal['stop_level'] = opening_range['high']
                
                # Filter weak signals in unfavorable regimes
                if regime['regime'] == 'HIGH_VOLATILITY' and strength < 0.7:
                    logger.info(f"Filtering weak signal in high volatility regime: {strength:.2f}")
                    return None
                elif regime['regime'] == 'CHOPPY' and strength < 0.6:
                    logger.info(f"Filtering weak signal in choppy regime: {strength:.2f}")
                    return None
                
                logger.info(f"Signal detected: {signal['type']} with strength {strength:.2f} in {regime['regime']} regime")
                
            return signal
            
        except Exception as e:
            logger.error(f"Error in breakout detection: {e}")
            return None
    
    def _calculate_signal_strength(self, signal: Dict, regime: Dict, gap_analysis: Dict) -> float:
        """Calculate signal strength based on multiple factors"""
        strength = 0.5  # Base strength
        
        # Volume confirmation
        if signal['volume_ratio'] > 2.0:
            strength += 0.2
        elif signal['volume_ratio'] > 1.5:
            strength += 0.1
        
        # Regime bonus/penalty
        regime_adjustments = {
            'TRENDING': 0.2,
            'NORMAL': 0.0,
            'CHOPPY': -0.2,
            'HIGH_VOLATILITY': -0.1
        }
        strength += regime_adjustments.get(regime['regime'], 0)
        
        # Gap analysis
        if gap_analysis['trade_bias'] == 'FOLLOW' and (
            (signal['type'] == 'LONG' and gap_analysis['gap_type'] == 'UP') or
            (signal['type'] == 'SHORT' and gap_analysis['gap_type'] == 'DOWN')
        ):
            strength += 0.1
        elif gap_analysis['trade_bias'] == 'FADE' and (
            (signal['type'] == 'LONG' and gap_analysis['gap_type'] == 'DOWN') or
            (signal['type'] == 'SHORT' and gap_analysis['gap_type'] == 'UP')
        ):
            strength += 0.15
        
        # Opening range quality
        if regime['or_quality'] == 'TIGHT':
            strength += 0.1
        elif regime['or_quality'] == 'WIDE':
            strength -= 0.1
        
        # ADX strength
        if regime['adx'] > 25:
            strength += 0.1
        elif regime['adx'] < 20:
            strength -= 0.1
        
        return max(0.0, min(1.0, strength))