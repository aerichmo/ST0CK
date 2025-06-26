"""
ST0CKA - Super Simple SPY Trading
Buy 1 share between 9:30-12:00
Sell 1 share between 12:00-3:00 for 1 cent profit
"""
from datetime import datetime
import logging
import pytz

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from bots.base.strategy import BaseStrategy, Signal

logger = logging.getLogger(__name__)


class ST0CKAStrategy(BaseStrategy):
    """The simplest possible trading strategy"""
    
    def __init__(self, bot_id: str, config: dict):
        super().__init__(bot_id, config)
        self.bought_today = False
        self.buy_price = None
        
    def initialize(self, market_data_provider) -> bool:
        """Start up the strategy"""
        self.market_data = market_data_provider
        self.is_initialized = True
        logger.info(f"[{self.bot_id}] Ready to trade!")
        return True
    
    def check_entry_conditions(self, current_price: float, market_data: dict):
        """Should we buy? Only between 9:30-12:00 ET"""
        # What time is it in Eastern Time?
        et_tz = pytz.timezone('America/New_York')
        current_time = datetime.now(et_tz)
        hour = current_time.hour
        minute = current_time.minute
        
        # Is it between 9:30 and 12:00 ET?
        is_buy_time = (hour == 9 and minute >= 30) or (hour == 10) or (hour == 11)
        
        logger.info(f"[{self.bot_id}] Check entry - ET Time: {hour:02d}:{minute:02d}, is_buy_time: {is_buy_time}, bought_today: {self.bought_today}")
        
        # Did we already buy today?
        if not self.bought_today and is_buy_time:
            logger.info(f"[{self.bot_id}] Time to buy SPY! (ET: {current_time.strftime('%I:%M %p')})")
            return Signal('LONG', strength=1.0, metadata={'symbol': 'SPY'})
            
        return None
    
    def calculate_position_size(self, signal, account_balance: float, current_price: float) -> int:
        """How many shares? Always 1"""
        return 1
    
    def get_exit_levels(self, signal, entry_price: float) -> dict:
        """Where to exit? Not used in our simple strategy"""
        return {
            'stop_loss': entry_price - 5.00,  # Emergency only
            'target_1': entry_price + 0.01,
            'target_2': None
        }
    
    def check_exit_conditions(self, position: dict, current_price: float, market_data: dict):
        """Should we sell? Only between 12:00-3:00 ET"""
        # What time is it in Eastern Time?
        et_tz = pytz.timezone('America/New_York')
        current_time = datetime.now(et_tz)
        hour = current_time.hour
        minute = current_time.minute
        
        # Is it between 12:00 and 3:00 ET?
        is_sell_time = (hour == 12) or (hour == 13) or (hour == 14)
        
        if is_sell_time and self.buy_price:
            # Did we make our penny?
            if current_price >= self.buy_price + 0.01:
                logger.info(f"[{self.bot_id}] Made our penny! Selling!")
                return True, "profit"
            
            # Is it almost 3:00 and we're not losing money?
            if hour == 14 and minute >= 55 and current_price >= self.buy_price:
                logger.info(f"[{self.bot_id}] Time's up, selling at break-even or small profit")
                return True, "time_up"
        
        # Emergency stop loss
        if self.buy_price and current_price < self.buy_price - 5.00:
            logger.warning(f"[{self.bot_id}] Big loss! Emergency sell!")
            return True, "stop_loss"
            
        return False, ""
    
    def get_option_selection_criteria(self, signal) -> dict:
        """We don't trade options"""
        return {}
    
    def on_position_opened(self, position: dict):
        """We just bought!"""
        self.bought_today = True
        self.buy_price = position.get('entry_price')
        logger.info(f"[{self.bot_id}] Bought 1 SPY at ${self.buy_price:.2f}")
    
    def on_position_closed(self, position: dict, pnl: float, reason: str):
        """We just sold!"""
        logger.info(f"[{self.bot_id}] Sold SPY! Made ${pnl:.2f}")
    
    def should_trade_today(self) -> bool:
        """Trade every day the market is open"""
        return True
    
    def reset_daily_state(self):
        """New day, fresh start"""
        self.bought_today = False
        self.buy_price = None
        logger.info(f"[{self.bot_id}] Ready for a new day!")