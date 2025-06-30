"""
ST0CKG - Battle Lines Strategy
Trade SPY 0-DTE options at key levels
"""
from datetime import datetime, time
from typing import Dict, Optional
import logging
import pytz

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from bots.base.strategy import BaseStrategy, Signal
from src.battle_lines_manager import BattleLinesManager
from src.st0ckg_signals import ST0CKGSignalDetector

logger = logging.getLogger(__name__)


class ST0CKGStrategy(BaseStrategy):
    """Battle Lines 0-DTE Strategy with Advanced Signal Detection"""
    
    def __init__(self, bot_id: str, config: Dict):
        super().__init__(bot_id, config)
        
        # Battle lines (set each morning)
        self.battle_lines = {
            'pdh': 0,
            'pdl': 0,
            'overnight_high': 0,
            'overnight_low': 0,
            'premarket_high': 0,
            'premarket_low': 0
        }
        
        # Trading state
        self.bias = None  # 'long', 'short', or None
        self.position_open = False
        self.entry_price = 0
        self.entry_level = 0  # Which battle line we entered at
        self.stop_price = 0
        self.position_size = 'full'  # 'full' or 'half'
        self.wins = 0
        self.losses = 0
        self.daily_pnl = 0
        
        # Signal tracking
        self.last_signal_time = None
        self.signal_cooldown = 60  # seconds between signals
        
        # Wait for first 5-min bar
        self.first_bar_done = False
        self.et_tz = pytz.timezone('America/New_York')
        
        # Components
        self.battle_lines_manager = None
        self.signal_detector = None
        self.db_manager = None
        
        logger.info(f"[{self.bot_id}] Battle Lines strategy initialized")
        
    def initialize(self, market_data_provider, db_manager=None) -> bool:
        """Initialize strategy with market data and database"""
        self.market_data = market_data_provider
        self.db_manager = db_manager
        
        # Initialize battle lines - MUST succeed
        if self.db_manager:
            self.battle_lines_manager = BattleLinesManager(self.db_manager, self.market_data)
            try:
                self.battle_lines = self.battle_lines_manager.calculate_battle_lines('SPY', self.bot_id)
                logger.info(f"[{self.bot_id}] Battle lines successfully calculated: {self.battle_lines}")
            except Exception as e:
                error_msg = f"[{self.bot_id}] CRITICAL: Failed to calculate battle lines: {str(e)}"
                logger.error(error_msg)
                raise RuntimeError(error_msg)
        else:
            error_msg = f"[{self.bot_id}] CRITICAL: No database manager provided - cannot calculate battle lines"
            logger.error(error_msg)
            raise RuntimeError(error_msg)
        
        # Initialize signal detector - MUST succeed
        try:
            self.signal_detector = ST0CKGSignalDetector(self.market_data)
            logger.info(f"[{self.bot_id}] Signal detector initialized")
        except Exception as e:
            error_msg = f"[{self.bot_id}] CRITICAL: Failed to initialize signal detector: {str(e)}"
            logger.error(error_msg)
            raise RuntimeError(error_msg)
        
        # Validate battle lines one more time
        validation_errors = []
        for key in ['pdh', 'pdl', 'overnight_high', 'overnight_low', 'premarket_high', 'premarket_low']:
            if key not in self.battle_lines:
                validation_errors.append(f"Missing {key}")
            elif self.battle_lines[key] is None:
                validation_errors.append(f"{key} is None")
            elif not isinstance(self.battle_lines[key], (int, float)):
                validation_errors.append(f"{key} is not a number: {type(self.battle_lines[key])}")
        
        if validation_errors:
            error_msg = f"[{self.bot_id}] CRITICAL: Battle lines validation failed: {', '.join(validation_errors)}"
            logger.error(error_msg)
            raise RuntimeError(error_msg)
        
        self.is_initialized = True
        logger.info(f"[{self.bot_id}] Strategy initialized successfully with validated battle lines")
        return True
    
    
    def set_battle_lines(self, pdh, pdl, es_high, es_low, pre_high, pre_low):
        """Set the 6 battle lines before market open (legacy method)"""
        self.battle_lines = {
            'pdh': pdh,
            'pdl': pdl,
            'overnight_high': es_high,
            'overnight_low': es_low,
            'premarket_high': pre_high,
            'premarket_low': pre_low
        }
        
        logger.info(f"[{self.bot_id}] Battle lines set: PDH={pdh:.2f}, PDL={pdl:.2f}, "
                   f"ES={es_low:.2f}-{es_high:.2f}, PRE={pre_low:.2f}-{pre_high:.2f}")
    
    def check_entry_conditions(self, current_price: float, market_data: Dict) -> Optional[Signal]:
        """Check for entry using advanced signal detection"""
        current_time = datetime.now(self.et_tz)
        
        # Log entry check
        if not hasattr(self, '_last_entry_log') or (datetime.now() - self._last_entry_log).seconds >= 60:
            logger.info(f"[{self.bot_id}] Checking entry at {current_time.strftime('%H:%M:%S')}, SPY: ${current_price:.2f}")
            self._last_entry_log = datetime.now()
        
        # Wait for first 5-min bar (9:35) or if we're past that time
        if not self.first_bar_done:
            if (current_time.hour == 9 and current_time.minute >= 35) or current_time.hour >= 10:
                self.first_bar_done = True
                logger.info(f"[{self.bot_id}] First bar check at {current_time.strftime('%I:%M %p')}")
                
                # Set bias based on close relative to battle lines
                pdh = self.battle_lines['pdh']
                pdl = self.battle_lines['pdl']
                
                if current_price > pdh + 0.10:
                    self.bias = 'long'
                    logger.info(f"[{self.bot_id}] LONG bias: SPY {current_price:.2f} > PDH+0.10 {pdh+0.10:.2f}")
                elif current_price < pdl - 0.10:
                    self.bias = 'short'
                    logger.info(f"[{self.bot_id}] SHORT bias: SPY {current_price:.2f} < PDL-0.10 {pdl-0.10:.2f}")
                else:
                    self.bias = None
                    logger.info(f"[{self.bot_id}] No bias - price {current_price:.2f} inside band")
            return None
        
        # Check if we should trade
        if self.position_open:
            return None
            
        # Check time restriction - no new buys after 11:00 AM ET
        if current_time.hour >= 11:
            logger.info(f"[{self.bot_id}] No new positions after 11:00 AM ET")
            return None
            
        # Check daily limits
        if self.wins >= 2:
            logger.info(f"[{self.bot_id}] Daily win limit reached (2 wins)")
            return None
        if self.losses >= 2:
            logger.info(f"[{self.bot_id}] Daily loss limit reached (-2R)")
            return None
        
        # Check signal cooldown
        if self.last_signal_time:
            elapsed = (datetime.now() - self.last_signal_time).seconds
            if elapsed < self.signal_cooldown:
                return None
        
        # Prepare market context for signal detection
        market_context = self._build_market_context(current_price, market_data)
        
        # Detect signals - MUST work properly
        try:
            signals = self.signal_detector.detect_all_signals(
                'SPY', current_price, self.battle_lines, market_context
            )
        except Exception as e:
            error_msg = f"[{self.bot_id}] CRITICAL: Signal detection failed: {str(e)}"
            logger.error(error_msg)
            raise RuntimeError(error_msg)
        
        if not signals:
            return None
        
        # Calculate composite signal
        total_score, primary_signal = self.signal_detector.calculate_composite_signal(signals)
        
        # Need minimum score to trade
        min_score_threshold = 4.0
        if total_score < min_score_threshold:
            return None
        
        # Log detected signals
        logger.info(f"[{self.bot_id}] Signals detected: {', '.join([f'{k}:{v['score']:.1f}' for k,v in signals.items()])}")
        logger.info(f"[{self.bot_id}] Total score: {total_score:.2f}, Primary: {primary_signal}")
        
        # Determine direction based on bias and signals
        direction = self._determine_direction(signals, primary_signal)
        if not direction:
            return None
        
        # Check break-and-retest for battle line confirmation
        if self._check_break_retest(current_price, market_data):
            self.last_signal_time = datetime.now()
            
            return Signal(
                signal_type=direction.upper(),
                strength=min(total_score / 10.0, 1.0),  # Normalize to 0-1
                metadata={
                    'primary_signal': primary_signal,
                    'all_signals': signals,
                    'total_score': total_score,
                    'entry_level': self.entry_level,
                    'bias': self.bias
                }
            )
            
        return None
    
    def _build_market_context(self, current_price: float, market_data: Dict) -> Dict:
        """Build market context for signal detection"""
        context = {
            'current_price': current_price,
            'recent_bars': market_data.get('recent_bars', []),
            'volume_ratio': market_data.get('volume_ratio', 1.0),
            'avg_volume': market_data.get('avg_volume', 0),
            'vwap': market_data.get('vwap', 0),
            'opening_range': market_data.get('opening_range', {}),
            'opening_volume_ratio': market_data.get('opening_volume_ratio', 1.0),
            'spread_widening': market_data.get('spread_widening', False),
            'hours_to_expiry': self._get_hours_to_expiry(),
            'volume_trend': market_data.get('volume_trend', 'neutral')
        }
        return context
    
    def _get_hours_to_expiry(self) -> float:
        """Calculate hours until market close"""
        now = datetime.now(self.et_tz)
        close_time = now.replace(hour=16, minute=0, second=0)
        delta = close_time - now
        return delta.total_seconds() / 3600
    
    def _determine_direction(self, signals: Dict, primary_signal: str) -> Optional[str]:
        """Determine trade direction based on signals and bias"""
        # If we have a bias, use it
        if self.bias:
            return 'LONG' if self.bias == 'long' else 'SHORT'
        
        # Otherwise, try to infer from signals
        if primary_signal in ['OPENING_DRIVE', 'GAMMA_SQUEEZE']:
            # These signals have inherent direction
            signal_data = signals.get(primary_signal, {})
            direction = signal_data.get('direction')
            if direction == 'bullish':
                return 'LONG'
            elif direction == 'bearish':
                return 'SHORT'
        
        # For other signals, we need bias to be set
        return None
    
    def _check_break_retest(self, price: float, market_data: Dict) -> bool:
        """Check for break-and-retest of battle lines"""
        # Get battle lines as list
        lines = [
            self.battle_lines['pdh'], 
            self.battle_lines['pdl'], 
            self.battle_lines['overnight_high'],
            self.battle_lines['overnight_low'], 
            self.battle_lines['premarket_high'], 
            self.battle_lines['premarket_low']
        ]
        
        # For simplicity, just check if we're near a level
        # In real implementation, would track candle patterns
        
        if self.bias == 'long':
            # Find resistance lines just above current price
            resist_lines = [l for l in lines if price < l < price + 0.50]
            if resist_lines:
                self.entry_level = min(resist_lines)
                logger.info(f"[{self.bot_id}] Potential long entry at battle line {self.entry_level:.2f}")
                return True
                
        else:  # short bias
            # Find support lines just below current price
            support_lines = [l for l in lines if price - 0.50 < l < price]
            if support_lines:
                self.entry_level = max(support_lines)
                logger.info(f"[{self.bot_id}] Potential short entry at battle line {self.entry_level:.2f}")
                return True
                
        return False
    
    def calculate_position_size(self, signal: Signal, account_balance: float, 
                              current_price: float) -> int:
        """Size for 1% risk on stop"""
        # Stop is 0.05-0.15 past structure
        stop_distance = 0.10  # Default SPY stop distance
        
        # Option delta ≈ 0.30
        option_delta = 0.30
        
        # 1% risk
        max_risk = account_balance * 0.01
        
        # Assuming $5 option price for calculation
        option_price = 5.00
        option_risk_per_contract = stop_distance * option_delta * 100
        
        # Contracts = risk / option_risk
        contracts = int(max_risk / option_risk_per_contract)
        
        return max(1, min(contracts, 10))  # 1-10 contracts
    
    def get_exit_levels(self, signal: Signal, entry_price: float) -> Dict:
        """Set exit levels"""
        if signal.metadata['bias'] == 'long':
            stop = entry_price - 0.10
        else:
            stop = entry_price + 0.10
            
        return {
            'stop_loss': stop,
            'target_1': None,  # Managed dynamically
            'target_2': None
        }
    
    def check_exit_conditions(self, position: Dict, current_price: float, 
                            market_data: Dict):
        """Manage stops and targets"""
        if not self.position_open:
            return False, ""
        
        # Calculate R-multiple
        if self.bias == 'long':
            spy_move = current_price - self.entry_price
        else:
            spy_move = self.entry_price - current_price
            
        # Rough R calculation
        r_multiple = spy_move / 0.10  # Using 0.10 as stop distance
        
        # Stop loss hit?
        if self.bias == 'long' and current_price <= self.stop_price:
            return True, "stop_loss"
        elif self.bias == 'short' and current_price >= self.stop_price:
            return True, "stop_loss"
            
        # Move stop to breakeven at 1R
        if r_multiple >= 1.0 and self.stop_price != self.entry_price:
            self.stop_price = self.entry_price
            logger.info(f"[{self.bot_id}] Stop moved to breakeven")
            
        # Scale half at 1.5R
        if r_multiple >= 1.5 and self.position_size == 'full':
            self.position_size = 'half'
            logger.info(f"[{self.bot_id}] Scaling out half at 1.5R")
            return True, "scale_half"
            
        # Full exit at 3R
        if r_multiple >= 3.0:
            return True, "target_3r"
            
        # Price re-entered level after breakeven?
        if self.stop_price == self.entry_price:
            if self.bias == 'long' and current_price < self.entry_level:
                return True, "reentry_exit"
            elif self.bias == 'short' and current_price > self.entry_level:
                return True, "reentry_exit"
                
        return False, ""
    
    def get_option_selection_criteria(self, signal: Signal) -> Dict:
        """Select 0-DTE ATM options"""
        return {
            'target_delta': 0.30,
            'max_dte': 0,
            'option_type': 'CALL' if signal.direction == 'BUY' else 'PUT'
        }
    
    def on_position_opened(self, position: Dict):
        """Track position entry"""
        super().on_position_opened(position)
        self.position_open = True
        self.entry_price = position.get('entry_price', 0)
        self.stop_price = self.entry_price - 0.10 if self.bias == 'long' else self.entry_price + 0.10
        self.position_size = 'full'
        
        logger.info(f"[{self.bot_id}] Position opened at {self.entry_price:.2f}, stop at {self.stop_price:.2f}")
    
    def on_position_closed(self, position: Dict, pnl: float, reason: str):
        """Track wins/losses"""
        super().on_position_closed(position, pnl, reason)
        
        if pnl > 0:
            self.wins += 1
            logger.info(f"[{self.bot_id}] WIN #{self.wins}, PnL: ${pnl:.2f}")
        else:
            self.losses += 1
            logger.info(f"[{self.bot_id}] LOSS #{self.losses}, PnL: ${pnl:.2f}")
            
        self.position_open = False
        self.daily_pnl += pnl
        
        logger.info(f"[{self.bot_id}] Daily: {self.wins}W-{self.losses}L, PnL: ${self.daily_pnl:.2f}")
    
    def should_trade_today(self) -> bool:
        """Trade every market day until limits hit"""
        return self.wins < 2 and self.losses < 2
    
    def reset_daily_state(self):
        """Reset for new day"""
        self.bias = None
        self.first_bar_done = False
        self.position_open = False
        self.wins = 0
        self.losses = 0
        self.daily_pnl = 0
        logger.info(f"[{self.bot_id}] Daily state reset for new trading day")