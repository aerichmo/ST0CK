"""Tiny Engine - Just Buy and Sell SPY"""
import logging
import time

logger = logging.getLogger(__name__)


class TinyEngine:
    def __init__(self, broker):
        self.broker = broker
        self.strategy = None
        self.have_spy = False
        self.order_id = None
        
    def set_strategy(self, strategy):
        self.strategy = strategy
        
    def run(self):
        """Main loop"""
        # Get SPY price
        price = self.broker.get_price('SPY')
        if not price:
            return
            
        # Buy?
        if not self.have_spy and self.strategy.should_buy(price):
            self.buy_spy()
            
        # Sell?
        if self.have_spy:
            should_sell, why = self.strategy.should_sell(price)
            if should_sell:
                self.sell_spy(why)
    
    def buy_spy(self):
        """Buy 1 SPY"""
        order = self.broker.buy('SPY', 1)
        if order:
            self.have_spy = True
            self.strategy.bought_at(order['price'])
            
    def sell_spy(self, reason):
        """Sell 1 SPY"""  
        order = self.broker.sell('SPY', 1)
        if order:
            self.have_spy = False
            self.strategy.sold_at(order['price'])