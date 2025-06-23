"""
ST0CKA - Simple SPY Scalping Strategy
Buy 1 share of SPY at market open and sell with $0.01 profit GTC
"""
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import logging

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from bots.base.strategy import BaseStrategy, Signal

logger = logging.getLogger(__name__)


class ST0CKAStrategy(BaseStrategy):
    """Simple SPY scalping strategy - buy at open, sell for $0.01 profit"""
    
    def __init__(self, bot_id: str, config: Dict):
        super().__init__(bot_id, config)
        self.has_position = False
        self.position_entered_today = False
        self.entry_price = None
        logger.info(f"[{self.bot_id}] ST0CKA strategy initialized - Buy SPY at open, sell for $0.01 profit")
        
    def initialize(self, market_data_provider) -> bool:
        """Initialize strategy with market data provider"""
        try:
            self.market_data = market_data_provider
            self.is_initialized = True
            logger.info(f"[{self.bot_id}] ST0CKA strategy initialized successfully")
            return True
        except Exception as e:
            logger.error(f"[{self.bot_id}] Initialization failed: {e}")
            return False
    
    def check_entry_conditions(self, current_price: float, market_data: Dict) -> Optional[Signal]:
        """Check if we should enter - only at market open and if no position"""
        now = datetime.now()
        market_open = datetime.now().replace(hour=9, minute=30, second=0, microsecond=0)
        
        # Only enter within first minute of market open
        time_since_open = (now - market_open).total_seconds()
        
        if (not self.has_position and 
            not self.position_entered_today and 
            0 <= time_since_open <= 60):  # Within first minute
            logger.info(f"[{self.bot_id}] Market open detected, generating BUY signal for SPY")
            return Signal('LONG', strength=1.0, metadata={'symbol': 'SPY', 'reason': 'market_open'})
        
        return None
    
    def calculate_position_size(self, signal: Signal, account_balance: float, 
                              current_price: float) -> int:
        """Always return 1 share"""
        return 1
    
    def get_exit_levels(self, signal: Signal, entry_price: float) -> Dict:
        """Set exit at entry + $0.01"""
        return {
            'stop_loss': entry_price - 1.00,  # $1 stop loss for safety
            'target_1': entry_price + 0.01,   # $0.01 profit target
            'target_2': None  # No second target
        }
    
    def check_exit_conditions(self, position: Dict, current_price: float, 
                            market_data: Dict) -> Tuple[bool, str]:
        """Check if we should exit - handled by GTC limit order"""
        # The GTC sell order handles the exit automatically
        # Only check for stop loss in case of significant drop
        if self.entry_price and current_price <= self.entry_price - 1.00:
            return True, "stop_loss"
        
        return False, ""
    
    def get_option_selection_criteria(self, signal: Signal) -> Dict:
        """Not used - this strategy trades shares, not options"""
        return {}
    
    def on_position_opened(self, position: Dict):
        """Track when position is opened"""
        super().on_position_opened(position)
        self.has_position = True
        self.position_entered_today = True
        self.entry_price = position.get('entry_price')
        logger.info(f"[{self.bot_id}] Entered SPY at ${self.entry_price:.2f}")
    
    def on_position_closed(self, position: Dict, pnl: float, reason: str):
        """Track when position is closed"""
        super().on_position_closed(position, pnl, reason)
        self.has_position = False
        logger.info(f"[{self.bot_id}] Exited SPY, PnL: ${pnl:.2f}")
    
    def should_trade_today(self) -> bool:
        """Trade every market day"""
        return True
    
    def reset_daily_state(self):
        """Reset state for new trading day"""
        self.position_entered_today = False
        self.entry_price = None
        logger.info(f"[{self.bot_id}] Daily state reset")