import pandas as pd
import numpy as np
from typing import Tuple, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class TrendFilter:
    def __init__(self, config: dict):
        self.config = config
        self.ema_fast = config["trend_filter"]["ema_fast"]
        self.ema_slow = config["trend_filter"]["ema_slow"]
        
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