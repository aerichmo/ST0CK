from abc import ABC, abstractmethod
from typing import Dict, List, Optional
import logging
from datetime import datetime
import uuid

logger = logging.getLogger(__name__)

class BrokerInterface(ABC):
    """Abstract base class for broker integration"""
    
    @abstractmethod
    def connect(self) -> bool:
        pass
    
    @abstractmethod
    def disconnect(self) -> None:
        pass
    
    @abstractmethod
    def place_option_order(self, contract: Dict, quantity: int, 
                          order_type: str = 'MARKET') -> Optional[str]:
        pass
    
    @abstractmethod
    def place_oco_order(self, contract: Dict, quantity: int, 
                       stop_price: float, target_prices: List[float]) -> Optional[str]:
        pass
    
    @abstractmethod
    def cancel_order(self, order_id: str) -> bool:
        pass
    
    @abstractmethod
    def get_order_status(self, order_id: str) -> Optional[Dict]:
        pass
    
    @abstractmethod
    def get_account_info(self) -> Optional[Dict]:
        pass
    
    @abstractmethod
    def get_option_quote(self, contract_symbol: str) -> Optional[Dict]:
        pass

class PaperTradingBroker(BrokerInterface):
    """Paper trading implementation for testing"""
    
    def __init__(self, initial_capital: float = 100000):
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        self.orders = {}
        self.positions = {}
        self.fills = []
        self.connected = False
        
    def connect(self) -> bool:
        self.connected = True
        logger.info("Connected to paper trading broker")
        return True
    
    def disconnect(self) -> None:
        self.connected = False
        logger.info("Disconnected from paper trading broker")
    
    def place_option_order(self, contract: Dict, quantity: int, 
                          order_type: str = 'MARKET') -> Optional[str]:
        if not self.connected:
            return None
            
        order_id = str(uuid.uuid4())
        fill_price = contract['ask'] if order_type == 'MARKET' else contract['mid_price']
        
        order = {
            'order_id': order_id,
            'contract_symbol': contract['contract_symbol'],
            'quantity': quantity,
            'order_type': order_type,
            'status': 'FILLED',
            'fill_price': fill_price,
            'fill_time': datetime.now(),
            'commission': quantity * 0.65
        }
        
        self.orders[order_id] = order
        
        cost = (fill_price * quantity * 100) + order['commission']
        self.current_capital -= cost
        
        self.fills.append({
            'order_id': order_id,
            'timestamp': datetime.now(),
            'action': 'BUY',
            'quantity': quantity,
            'price': fill_price,
            'cost': cost
        })
        
        logger.info(f"Paper order filled: {order_id} - {quantity} contracts at ${fill_price}")
        
        return order_id
    
    def place_oco_order(self, contract: Dict, quantity: int, 
                       stop_price: float, target_prices: List[float]) -> Optional[str]:
        if not self.connected:
            return None
            
        oco_id = str(uuid.uuid4())
        
        stop_order = {
            'order_id': f"{oco_id}_STOP",
            'parent_id': oco_id,
            'contract_symbol': contract['contract_symbol'],
            'quantity': quantity,
            'order_type': 'STOP',
            'stop_price': stop_price,
            'status': 'PENDING'
        }
        
        target_orders = []
        for i, target_price in enumerate(target_prices):
            target_quantity = quantity // 2 if i == 0 else quantity - (quantity // 2)
            target_order = {
                'order_id': f"{oco_id}_TARGET_{i+1}",
                'parent_id': oco_id,
                'contract_symbol': contract['contract_symbol'],
                'quantity': target_quantity,
                'order_type': 'LIMIT',
                'limit_price': target_price,
                'status': 'PENDING'
            }
            target_orders.append(target_order)
        
        self.orders[stop_order['order_id']] = stop_order
        for order in target_orders:
            self.orders[order['order_id']] = order
        
        logger.info(f"Paper OCO order placed: {oco_id}")
        
        return oco_id
    
    def cancel_order(self, order_id: str) -> bool:
        if order_id in self.orders:
            self.orders[order_id]['status'] = 'CANCELLED'
            logger.info(f"Paper order cancelled: {order_id}")
            return True
        return False
    
    def get_order_status(self, order_id: str) -> Optional[Dict]:
        return self.orders.get(order_id)
    
    def get_account_info(self) -> Optional[Dict]:
        return {
            'account_value': self.current_capital,
            'buying_power': self.current_capital,
            'initial_capital': self.initial_capital,
            'realized_pnl': self.current_capital - self.initial_capital,
            'open_positions': len(self.positions)
        }
    
    def get_option_quote(self, contract_symbol: str) -> Optional[Dict]:
        import random
        base_price = 2.50
        spread = 0.05
        
        bid = base_price + random.uniform(-0.5, 0.5)
        ask = bid + spread
        
        return {
            'contract_symbol': contract_symbol,
            'bid': bid,
            'ask': ask,
            'last': (bid + ask) / 2,
            'volume': random.randint(100, 10000),
            'timestamp': datetime.now()
        }
    
    def simulate_fill(self, order_id: str, fill_price: float) -> bool:
        """Simulate order fill for paper trading"""
        if order_id not in self.orders:
            return False
            
        order = self.orders[order_id]
        if order['status'] != 'PENDING':
            return False
        
        order['status'] = 'FILLED'
        order['fill_price'] = fill_price
        order['fill_time'] = datetime.now()
        
        revenue = fill_price * order['quantity'] * 100
        commission = order['quantity'] * 0.65
        self.current_capital += revenue - commission
        
        self.fills.append({
            'order_id': order_id,
            'timestamp': datetime.now(),
            'action': 'SELL',
            'quantity': order['quantity'],
            'price': fill_price,
            'revenue': revenue - commission
        })
        
        if 'parent_id' in order:
            for oid, o in self.orders.items():
                if o.get('parent_id') == order['parent_id'] and o['status'] == 'PENDING':
                    o['status'] = 'CANCELLED'
        
        logger.info(f"Paper order filled: {order_id} - SELL {order['quantity']} at ${fill_price}")
        
        return True