"""
ST0CKG - Battle Lines Strategy
Trade SPY 0-DTE options at key levels
"""
from datetime import datetime, time
from typing import Dict, Optional
import logging

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from bots.base.strategy import BaseStrategy, Signal

logger = logging.getLogger(__name__)


class ST0CKGStrategy(BaseStrategy):
    """Battle Lines 0-DTE Strategy"""
    
    def __init__(self, bot_id: str, config: Dict):
        super().__init__(bot_id, config)
        
        # Battle lines (set each morning)
        self.pdh = 0  # Previous Day High
        self.pdl = 0  # Previous Day Low
        self.overnight_high = 0  # ES overnight high
        self.overnight_low = 0   # ES overnight low
        self.premarket_high = 0  # Pre-market high
        self.premarket_low = 0   # Pre-market low
        
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
        
        # Wait for first 5-min bar
        self.first_bar_done = False
        
        logger.info(f"[{self.bot_id}] Battle Lines strategy initialized")
        
    def initialize(self, market_data_provider) -> bool:
        """Initialize strategy"""
        self.market_data = market_data_provider
        self.is_initialized = True
        
        # TODO: Set battle lines from market data
        # For now, use dummy values
        self.set_battle_lines(580, 576, 579, 577, 580.5, 576.5)
        
        return True
    
    def set_battle_lines(self, pdh, pdl, es_high, es_low, pre_high, pre_low):
        """Set the 6 battle lines before market open"""
        self.pdh = pdh
        self.pdl = pdl
        self.overnight_high = es_high
        self.overnight_low = es_low
        self.premarket_high = pre_high
        self.premarket_low = pre_low
        
        logger.info(f"[{self.bot_id}] Battle lines: PDH={pdh:.2f}, PDL={pdl:.2f}, "
                   f"ES={es_low:.2f}-{es_high:.2f}, PRE={pre_low:.2f}-{pre_high:.2f}")
    
    def check_entry_conditions(self, current_price: float, market_data: Dict) -> Optional[Signal]:
        """Check for break-and-retest entry"""
        current_time = datetime.now()
        
        # Log entry check
        if not hasattr(self, '_last_entry_log') or (datetime.now() - self._last_entry_log).seconds >= 60:
            logger.info(f"[{self.bot_id}] Checking entry at {current_time.strftime('%H:%M:%S')}, SPY: ${current_price:.2f}")
            self._last_entry_log = datetime.now()
        
        # Wait for first 5-min bar (9:35) or if we're past that time
        if not self.first_bar_done:
            if (current_time.hour == 9 and current_time.minute >= 35) or current_time.hour >= 10:
                self.first_bar_done = True
                logger.info(f"[{self.bot_id}] First bar check at {current_time.strftime('%I:%M %p')}")
                
                # Set bias based on close
                if current_price > self.pdh + 0.10:
                    self.bias = 'long'
                    logger.info(f"[{self.bot_id}] LONG bias: SPY {current_price:.2f} > PDH+0.10 {self.pdh+0.10:.2f}")
                elif current_price < self.pdl - 0.10:
                    self.bias = 'short'
                    logger.info(f"[{self.bot_id}] SHORT bias: SPY {current_price:.2f} < PDL-0.10 {self.pdl-0.10:.2f}")
                else:
                    self.bias = None
                    logger.info(f"[{self.bot_id}] No bias - price {current_price:.2f} inside band")
            return None
        
        # Check if we should trade
        if not self.bias or self.position_open:
            return None
            
        # Check daily limits
        if self.wins >= 2:
            logger.info(f"[{self.bot_id}] Daily win limit reached (2 wins)")
            return None
        if self.losses >= 2:
            logger.info(f"[{self.bot_id}] Daily loss limit reached (-2R)")
            return None
        
        # Check for break-and-retest setup
        if self._check_break_retest(current_price, market_data):
            direction = 'buy' if self.bias == 'long' else 'sell'
            return Signal(
                direction=direction.upper(),
                strength=1.0,
                metadata={
                    'entry_level': self.entry_level,
                    'bias': self.bias
                }
            )
            
        return None
    
    def _check_break_retest(self, price: float, market_data: Dict) -> bool:
        """Check for break-and-retest of battle lines"""
        # Get battle lines as list
        lines = [self.pdh, self.pdl, self.overnight_high, 
                self.overnight_low, self.premarket_high, self.premarket_low]
        
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