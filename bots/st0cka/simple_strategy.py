"""ST0CKA - Buy SPY, Sell SPY"""
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class SimpleStrategy:
    def __init__(self):
        self.bought = False
        self.buy_price = 0
        
    def should_buy(self, price):
        """Buy between 9:30 and 10:00"""
        now = datetime.now()
        hour = now.hour
        minute = now.minute
        
        # Is it buy time?
        if hour == 9 and minute >= 30 and not self.bought:
            return True
        if hour == 10 and minute == 0 and not self.bought:
            return True
            
        return False
    
    def should_sell(self, price):
        """Sell between 10:00 and 11:00"""
        if not self.bought:
            return False, ""
            
        now = datetime.now()
        hour = now.hour
        minute = now.minute
        
        # Only sell after 10 AM
        if hour != 10:
            return False, ""
        
        # Made a penny?
        if price >= self.buy_price + 0.01:
            return True, "profit"
        
        # Almost 11 AM and not losing?
        if minute >= 55 and price >= self.buy_price:
            return True, "time"
            
        return False, ""
    
    def bought_at(self, price):
        """Remember buy price"""
        self.bought = True
        self.buy_price = price
        logger.info(f"Bought at ${price:.2f}")
    
    def sold_at(self, price):
        """Calculate profit"""
        profit = price - self.buy_price
        logger.info(f"Sold at ${price:.2f}, made ${profit:.2f}")
        self.bought = False