"""
PDT Override Configuration
Allows bypassing PDT restrictions for paper trading accounts
"""
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)

class PDTManager:
    """Manages Pattern Day Trading rules and overrides"""
    
    def __init__(self, 
                 min_account_value: float = 2500.0,
                 paper_trading_override: bool = True):
        """
        Initialize PDT manager
        
        Args:
            min_account_value: Minimum account value to allow day trading (default $2,500)
            paper_trading_override: Allow PDT override for paper accounts
        """
        self.min_account_value = min_account_value
        self.paper_trading_override = paper_trading_override
        self.day_trades_count = 0
        self.last_reset_date = None
        
    def check_pdt_restriction(self, account_value: float, is_paper: bool = True) -> bool:
        """
        Check if account is subject to PDT restrictions
        
        Returns:
            True if trading is allowed, False if restricted
        """
        # For paper trading, use our custom threshold
        if is_paper and self.paper_trading_override:
            if account_value >= self.min_account_value:
                logger.info(f"PDT check passed for paper account: ${account_value:.2f} >= ${self.min_account_value:.2f}")
                return True
            else:
                logger.warning(f"PDT restriction for paper account: ${account_value:.2f} < ${self.min_account_value:.2f}")
                return False
        
        # For live trading, use standard $25,000 threshold
        standard_pdt_minimum = 25000.0
        if account_value >= standard_pdt_minimum:
            return True
        
        # Check day trade count for accounts under threshold
        if self.day_trades_count >= 3:
            logger.warning(f"PDT restriction: {self.day_trades_count} day trades in 5 days")
            return False
            
        return True
    
    def record_day_trade(self):
        """Record a day trade"""
        self.day_trades_count += 1
        logger.info(f"Day trade recorded. Total: {self.day_trades_count}")
    
    def can_exit_position(self, entry_time, current_time) -> bool:
        """
        Check if exiting position would count as day trade
        
        Args:
            entry_time: When position was entered
            current_time: Current time
            
        Returns:
            True if exit is allowed
        """
        # Same day exit = day trade
        if entry_time.date() == current_time.date():
            return self.day_trades_count < 3
        
        # Different day = not a day trade
        return True