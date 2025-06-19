from abc import ABC, abstractmethod
from typing import Dict, List, Optional
import logging
from datetime import datetime
import uuid
import numpy as np

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
    """Paper trading implementation with realistic market simulation"""
    
    def __init__(self, initial_capital: float = 100000):
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        self.orders = {}
        self.positions = {}
        self.fills = []
        self.connected = False
        
        # Realistic market simulation parameters
        self.base_spread_percent = 0.02  # 2% base spread
        self.volatility_factor = 0.3     # 30% volatility impact on spreads
        self.liquidity_impact = 0.5      # 50% impact based on order size
        self.market_impact = 0.001       # 0.1% market impact per standard lot
        
    def connect(self) -> bool:
        self.connected = True
        logger.info("Connected to paper trading broker")
        return True
    
    def disconnect(self) -> None:
        self.connected = False
        logger.info("Disconnected from paper trading broker")
    
    def _calculate_realistic_spread(self, base_price: float, volatility: float = 0.2, 
                                   volume: int = 1000, order_size: int = 1) -> tuple:
        """Calculate realistic bid-ask spread based on market conditions"""
        # Base spread increases with volatility
        vol_adjusted_spread = self.base_spread_percent * (1 + volatility * self.volatility_factor)
        
        # Spread widens with larger order sizes (liquidity impact)
        size_impact = 1 + (order_size / 10) * self.liquidity_impact * vol_adjusted_spread
        
        # Low volume means wider spreads
        volume_factor = max(0.5, min(2.0, 1000 / max(volume, 100)))
        
        # Calculate final spread
        total_spread_percent = vol_adjusted_spread * size_impact * volume_factor
        spread_dollars = base_price * total_spread_percent
        
        # Add market impact for the order
        market_impact = base_price * self.market_impact * order_size
        
        # Calculate bid and ask
        mid_price = base_price
        half_spread = spread_dollars / 2
        
        bid = mid_price - half_spread
        ask = mid_price + half_spread + market_impact
        
        return round(bid, 2), round(ask, 2)
    
    def _add_realistic_slippage(self, price: float, is_buy: bool, urgency: str = 'normal') -> float:
        """Add realistic slippage to execution price"""
        # Base slippage depends on urgency
        slippage_map = {
            'passive': -0.001,   # Might get price improvement
            'normal': 0.001,     # Small slippage
            'aggressive': 0.003, # Higher slippage for immediate fill
            'urgent': 0.005      # Maximum slippage for must-fill orders
        }
        
        base_slippage = slippage_map.get(urgency, 0.001)
        
        # Add random component
        random_slippage = np.random.normal(0, 0.0005)
        
        total_slippage = base_slippage + random_slippage
        
        # Apply slippage (negative for sells, positive for buys)
        if is_buy:
            return price * (1 + total_slippage)
        else:
            return price * (1 - total_slippage)
    
    def place_option_order(self, contract: Dict, quantity: int, 
                          order_type: str = 'MARKET') -> Optional[str]:
        if not self.connected:
            return None
            
        order_id = str(uuid.uuid4())
        
        # Get realistic bid-ask based on contract details
        base_price = contract.get('last', contract.get('mid_price', 2.5))
        volatility = contract.get('implied_volatility', 0.3)
        volume = contract.get('volume', 1000)
        
        bid, ask = self._calculate_realistic_spread(base_price, volatility, volume, quantity)
        
        # Determine fill price based on order type
        if order_type == 'MARKET':
            # Market orders fill at ask (for buys)
            fill_price = self._add_realistic_slippage(ask, is_buy=True, urgency='normal')
        else:
            # Limit orders might get better fill
            fill_price = self._add_realistic_slippage((bid + ask) / 2, is_buy=True, urgency='passive')
        
        # Realistic commission structure
        commission = self._calculate_commission(quantity)
        
        order = {
            'order_id': order_id,
            'contract_symbol': contract['contract_symbol'],
            'quantity': quantity,
            'order_type': order_type,
            'status': 'FILLED',
            'fill_price': round(fill_price, 2),
            'fill_time': datetime.now(),
            'commission': commission,
            'bid_at_fill': bid,
            'ask_at_fill': ask,
            'spread_paid': round(fill_price - (bid + ask) / 2, 2)
        }
        
        self.orders[order_id] = order
        
        cost = (fill_price * quantity * 100) + commission
        self.current_capital -= cost
        
        # Track position
        if contract['contract_symbol'] not in self.positions:
            self.positions[contract['contract_symbol']] = {
                'quantity': 0,
                'avg_price': 0,
                'total_cost': 0
            }
        
        pos = self.positions[contract['contract_symbol']]
        total_quantity = pos['quantity'] + quantity
        total_cost = pos['total_cost'] + (fill_price * quantity * 100)
        pos['quantity'] = total_quantity
        pos['avg_price'] = total_cost / (total_quantity * 100) if total_quantity > 0 else 0
        pos['total_cost'] = total_cost
        
        self.fills.append({
            'order_id': order_id,
            'timestamp': datetime.now(),
            'action': 'BUY',
            'quantity': quantity,
            'price': fill_price,
            'cost': cost,
            'spread_cost': round((fill_price - bid) * quantity * 100, 2)
        })
        
        logger.info(f"Paper order filled: {order_id} - {quantity} contracts at ${fill_price} (spread: ${ask - bid:.2f})")
        
        return order_id
    
    def _calculate_commission(self, quantity: int) -> float:
        """Calculate realistic commission based on quantity"""
        # Tiered commission structure
        base_rate = 0.65
        if quantity >= 10:
            base_rate = 0.50
        if quantity >= 100:
            base_rate = 0.35
            
        commission = quantity * base_rate
        
        # Add regulatory fees
        regulatory_fees = quantity * 0.05
        
        return round(commission + regulatory_fees, 2)
    
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
        # Calculate unrealized P&L
        unrealized_pnl = 0
        for symbol, pos in self.positions.items():
            if pos['quantity'] > 0:
                # Simulate current market price
                current_price = self._simulate_current_price(pos['avg_price'])
                unrealized = (current_price - pos['avg_price']) * pos['quantity'] * 100
                unrealized_pnl += unrealized
        
        return {
            'account_value': self.current_capital + unrealized_pnl,
            'buying_power': self.current_capital,
            'initial_capital': self.initial_capital,
            'realized_pnl': self.current_capital - self.initial_capital,
            'unrealized_pnl': unrealized_pnl,
            'open_positions': len([p for p in self.positions.values() if p['quantity'] > 0]),
            'total_trades': len(self.fills),
            'commission_paid': sum(f.get('commission', 0) for f in self.fills if 'commission' in f)
        }
    
    def _simulate_current_price(self, avg_price: float) -> float:
        """Simulate current market price with realistic movement"""
        # Random walk with slight mean reversion
        drift = np.random.normal(0, 0.02)  # 2% standard deviation
        mean_reversion = -0.1 * drift       # 10% mean reversion
        
        price_change = drift + mean_reversion
        return avg_price * (1 + price_change)
    
    def get_option_quote(self, contract_symbol: str) -> Optional[Dict]:
        """Generate realistic option quote"""
        # Extract details from contract symbol if possible
        # Format: SYMBOL_MMDDYY_TYPE_STRIKE
        parts = contract_symbol.split('_')
        
        # Base price with some persistence (use position avg price if available)
        if contract_symbol in self.positions and self.positions[contract_symbol]['quantity'] > 0:
            base_price = self.positions[contract_symbol]['avg_price']
        else:
            base_price = np.random.lognormal(0.8, 0.5)  # Log-normal distribution for option prices
        
        # Simulate market conditions
        volatility = np.random.uniform(0.2, 0.6)
        volume = np.random.randint(50, 5000)
        
        # Calculate realistic bid-ask
        bid, ask = self._calculate_realistic_spread(base_price, volatility, volume)
        
        # Last trade might be anywhere in the spread
        last = bid + (ask - bid) * np.random.beta(2, 2)  # Beta distribution favors mid-price
        
        return {
            'contract_symbol': contract_symbol,
            'bid': round(bid, 2),
            'ask': round(ask, 2),
            'last': round(last, 2),
            'mid_price': round((bid + ask) / 2, 2),
            'volume': volume,
            'open_interest': np.random.randint(100, 10000),
            'implied_volatility': round(volatility, 3),
            'timestamp': datetime.now(),
            'spread': round(ask - bid, 2),
            'spread_percent': round((ask - bid) / ((ask + bid) / 2) * 100, 2)
        }
    
    def simulate_fill(self, order_id: str, fill_price: float = None) -> bool:
        """Simulate order fill for paper trading with realistic execution"""
        if order_id not in self.orders:
            return False
            
        order = self.orders[order_id]
        if order['status'] != 'PENDING':
            return False
        
        # If no fill price provided, simulate one
        if fill_price is None:
            quote = self.get_option_quote(order['contract_symbol'])
            if order['order_type'] == 'STOP':
                # Stop orders fill with slippage
                fill_price = self._add_realistic_slippage(quote['bid'], is_buy=False, urgency='urgent')
            else:
                # Limit orders fill at limit or better
                fill_price = self._add_realistic_slippage(quote['bid'], is_buy=False, urgency='passive')
        
        order['status'] = 'FILLED'
        order['fill_price'] = round(fill_price, 2)
        order['fill_time'] = datetime.now()
        
        commission = self._calculate_commission(order['quantity'])
        revenue = fill_price * order['quantity'] * 100
        net_proceeds = revenue - commission
        
        self.current_capital += net_proceeds
        
        # Update position
        symbol = order['contract_symbol']
        if symbol in self.positions:
            self.positions[symbol]['quantity'] -= order['quantity']
            if self.positions[symbol]['quantity'] == 0:
                del self.positions[symbol]
        
        self.fills.append({
            'order_id': order_id,
            'timestamp': datetime.now(),
            'action': 'SELL',
            'quantity': order['quantity'],
            'price': fill_price,
            'revenue': net_proceeds,
            'commission': commission
        })
        
        # Cancel other orders in OCO group
        if 'parent_id' in order:
            for oid, o in self.orders.items():
                if o.get('parent_id') == order['parent_id'] and o['status'] == 'PENDING':
                    o['status'] = 'CANCELLED'
        
        logger.info(f"Paper order filled: {order_id} - SELL {order['quantity']} at ${fill_price}")
        
        return True