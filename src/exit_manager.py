from datetime import datetime, time
from typing import Dict, List, Optional
import logging
import pytz

logger = logging.getLogger(__name__)

class ExitManager:
    def __init__(self, config: dict):
        self.config = config
        self.stop_loss_r = config["exit_strategy"]["stop_loss_r"]
        self.target_1_r = config["exit_strategy"]["target_1_r"]
        self.target_1_size_pct = config["exit_strategy"]["target_1_size_pct"]
        self.target_2_r = config["exit_strategy"]["target_2_r"]
        self.time_stop_minutes = config["exit_strategy"]["time_stop_minutes"]
        self.timezone = config["session"]["timezone"]
        
        self.oco_orders = {}
    
    def calculate_exit_levels(self, entry_price: float, stop_level: float, 
                            signal_type: str, market_data: Optional[Dict] = None) -> Dict:
        """Calculate volatility-adjusted stop loss and target levels"""
        # Base calculations
        risk_per_contract = entry_price
        
        # Get ATR and market regime if available
        atr = market_data.get('atr', 0) if market_data else 0
        market_regime = market_data.get('market_regime', {}) if market_data else {}
        regime_type = market_regime.get('regime', 'NORMAL')
        
        # Calculate dynamic stop loss
        base_stop_mult = abs(self.stop_loss_r)
        
        # Adjust stop based on market regime
        if regime_type == "HIGH_VOLATILITY":
            stop_mult = base_stop_mult * 1.5  # Wider stop in high vol
            logger.info("Widening stop loss due to high volatility regime")
        elif regime_type == "CHOPPY":
            stop_mult = base_stop_mult * 1.25  # Slightly wider in choppy markets
        else:
            stop_mult = base_stop_mult
        
        # Calculate stop loss
        stop_loss = entry_price * (1 - stop_mult)
        
        # Ensure minimum stop based on ATR if available
        if atr > 0 and stop_level > 0:
            # Use at least 0.5 ATR as stop distance
            min_stop_distance = 0.5 * atr
            price_based_stop = stop_level - (0.5 * atr) if signal_type == 'LONG' else stop_level + (0.5 * atr)
            
            # For options, convert to percentage
            price_stop_pct = abs(price_based_stop - stop_level) / stop_level
            option_stop = entry_price * (1 - price_stop_pct)
            
            # Use wider of the two stops
            if signal_type == 'LONG':
                stop_loss = min(stop_loss, max(0, option_stop))
            else:
                stop_loss = max(stop_loss, option_stop)
        
        # Calculate dynamic targets based on volatility
        if regime_type == "TRENDING":
            # Extended targets in trending markets
            target_1_mult = self.target_1_r * 1.25
            target_2_mult = self.target_2_r * 1.5
            logger.info("Extending profit targets due to trending regime")
        elif regime_type == "HIGH_VOLATILITY":
            # Closer targets in high volatility
            target_1_mult = self.target_1_r * 0.8
            target_2_mult = self.target_2_r * 0.9
        else:
            target_1_mult = self.target_1_r
            target_2_mult = self.target_2_r
        
        target_1 = entry_price * (1 + target_1_mult)
        target_2 = entry_price * (1 + target_2_mult)
        
        return {
            'stop_loss': max(0, stop_loss),
            'target_1': target_1,
            'target_2': target_2,
            'risk_per_contract': risk_per_contract,
            'stop_mult_used': stop_mult,
            'regime_adjusted': regime_type != 'NORMAL'
        }
    
    def create_oco_order(self, position: Dict) -> Dict:
        """Create OCO (One-Cancels-Other) order structure"""
        position_id = position['position_id']
        entry_price = position['entry_price']
        contracts = position['contracts']
        option_type = position['option_type']
        
        exit_levels = self.calculate_exit_levels(entry_price, option_type)
        
        target_1_contracts = int(contracts * self.target_1_size_pct)
        target_2_contracts = contracts - target_1_contracts
        
        oco_order = {
            'position_id': position_id,
            'symbol': position['symbol'],
            'contract_symbol': position['contract_symbol'],
            'entry_price': entry_price,
            'total_contracts': contracts,
            'option_type': option_type,
            'orders': {
                'stop_loss': {
                    'type': 'STOP',
                    'price': exit_levels['stop_loss'],
                    'contracts': contracts,
                    'status': 'PENDING',
                    'triggered_at': None
                },
                'target_1': {
                    'type': 'LIMIT',
                    'price': exit_levels['target_1'],
                    'contracts': target_1_contracts,
                    'status': 'PENDING',
                    'triggered_at': None
                },
                'target_2': {
                    'type': 'LIMIT',
                    'price': exit_levels['target_2'],
                    'contracts': target_2_contracts,
                    'status': 'PENDING',
                    'triggered_at': None
                }
            },
            'stop_adjusted': False,
            'created_at': datetime.now()
        }
        
        self.oco_orders[position_id] = oco_order
        logger.info(f"Created OCO order for {position_id}: SL={exit_levels['stop_loss']:.2f}, "
                   f"T1={exit_levels['target_1']:.2f}, T2={exit_levels['target_2']:.2f}")
        
        return oco_order
    
    def check_exit_conditions(self, position_id: str, current_price: float) -> List[Dict]:
        """Check if any exit conditions are triggered"""
        if position_id not in self.oco_orders:
            return []
        
        oco = self.oco_orders[position_id]
        triggered_orders = []
        
        if oco['orders']['stop_loss']['status'] == 'PENDING':
            if current_price <= oco['orders']['stop_loss']['price']:
                triggered_orders.append({
                    'position_id': position_id,
                    'order_type': 'stop_loss',
                    'exit_price': current_price,
                    'contracts': oco['orders']['stop_loss']['contracts'],
                    'reason': 'Stop loss triggered'
                })
                oco['orders']['stop_loss']['status'] = 'TRIGGERED'
                oco['orders']['stop_loss']['triggered_at'] = datetime.now()
                
                for order_type in ['target_1', 'target_2']:
                    oco['orders'][order_type]['status'] = 'CANCELLED'
        
        else:
            if (oco['orders']['target_1']['status'] == 'PENDING' and 
                current_price >= oco['orders']['target_1']['price']):
                triggered_orders.append({
                    'position_id': position_id,
                    'order_type': 'target_1',
                    'exit_price': oco['orders']['target_1']['price'],
                    'contracts': oco['orders']['target_1']['contracts'],
                    'reason': 'Target 1 reached'
                })
                oco['orders']['target_1']['status'] = 'TRIGGERED'
                oco['orders']['target_1']['triggered_at'] = datetime.now()
                
                if not oco['stop_adjusted']:
                    oco['orders']['stop_loss']['price'] = oco['entry_price']
                    oco['stop_adjusted'] = True
                    logger.info(f"Adjusted stop to breakeven for {position_id}")
            
            if (oco['orders']['target_2']['status'] == 'PENDING' and 
                current_price >= oco['orders']['target_2']['price']):
                triggered_orders.append({
                    'position_id': position_id,
                    'order_type': 'target_2',
                    'exit_price': oco['orders']['target_2']['price'],
                    'contracts': oco['orders']['target_2']['contracts'],
                    'reason': 'Target 2 reached'
                })
                oco['orders']['target_2']['status'] = 'TRIGGERED'
                oco['orders']['target_2']['triggered_at'] = datetime.now()
                oco['orders']['stop_loss']['status'] = 'CANCELLED'
        
        return triggered_orders
    
    def get_active_orders(self) -> List[Dict]:
        """Get all active OCO orders"""
        active_orders = []
        
        for position_id, oco in self.oco_orders.items():
            pending_orders = [
                {
                    'position_id': position_id,
                    'symbol': oco['symbol'],
                    'order_type': order_type,
                    'price': order_data['price'],
                    'contracts': order_data['contracts']
                }
                for order_type, order_data in oco['orders'].items()
                if order_data['status'] == 'PENDING'
            ]
            active_orders.extend(pending_orders)
        
        return active_orders
    
    def cancel_oco_order(self, position_id: str):
        """Cancel all pending orders for a position"""
        if position_id in self.oco_orders:
            oco = self.oco_orders[position_id]
            for order_type, order_data in oco['orders'].items():
                if order_data['status'] == 'PENDING':
                    order_data['status'] = 'CANCELLED'
            logger.info(f"Cancelled OCO orders for {position_id}")
    
    def get_exit_statistics(self) -> Dict:
        """Get statistics on exit performance"""
        total_exits = 0
        stop_losses = 0
        target_1_hits = 0
        target_2_hits = 0
        
        for oco in self.oco_orders.values():
            if oco['orders']['stop_loss']['status'] == 'TRIGGERED':
                stop_losses += 1
                total_exits += 1
            if oco['orders']['target_1']['status'] == 'TRIGGERED':
                target_1_hits += 1
                total_exits += 1
            if oco['orders']['target_2']['status'] == 'TRIGGERED':
                target_2_hits += 1
        
        return {
            'total_exits': total_exits,
            'stop_losses': stop_losses,
            'target_1_hits': target_1_hits,
            'target_2_hits': target_2_hits,
            'win_rate': (target_1_hits + target_2_hits) / total_exits if total_exits > 0 else 0
        }
    
    def check_time_stop(self, entry_time: datetime) -> bool:
        """Check if position should be closed based on time"""
        current_time = datetime.now(self.timezone)
        minutes_in_position = (current_time - entry_time).total_seconds() / 60
        
        # Dynamic time stops based on time of day
        current_hour = current_time.time()
        
        # Tighter time stops after 10:30 AM
        if current_hour > time(10, 30):
            adjusted_time_stop = self.time_stop_minutes * 0.75
        else:
            adjusted_time_stop = self.time_stop_minutes
        
        return minutes_in_position >= adjusted_time_stop
    
    def update_trailing_stop(self, position_id: str, current_price: float, 
                           high_water_mark: float) -> Optional[float]:
        """Update trailing stop based on profit level"""
        if position_id not in self.oco_orders:
            return None
        
        oco = self.oco_orders[position_id]
        entry_price = oco['entry_price']
        current_stop = oco['orders']['stop_loss']['price']
        
        # Calculate profit percentage
        profit_pct = (current_price - entry_price) / entry_price
        
        # Trailing stop logic
        new_stop = None
        
        if profit_pct > 0.5:  # 50% profit
            # Trail at 25% below high water mark
            new_stop = high_water_mark * 0.75
        elif profit_pct > 0.3:  # 30% profit
            # Trail at 15% below high water mark
            new_stop = high_water_mark * 0.85
        elif profit_pct > 0.15:  # 15% profit
            # Move stop to breakeven
            new_stop = entry_price
        
        # Only update if new stop is higher than current
        if new_stop and new_stop > current_stop:
            oco['orders']['stop_loss']['price'] = new_stop
            logger.info(f"Updated trailing stop for {position_id} to ${new_stop:.2f}")
            return new_stop
        
        return None
    
    def suggest_exit_action(self, position: Dict, current_market: Dict) -> Optional[str]:
        """Suggest exit action based on market conditions"""
        position_id = position['position_id']
        if position_id not in self.oco_orders:
            return None
        
        current_time = datetime.now(self.timezone).time()
        entry_time = position['entry_time']
        minutes_in_position = (datetime.now(self.timezone) - entry_time).total_seconds() / 60
        
        # Market regime
        regime = current_market.get('regime', 'NORMAL')
        
        # Time-based suggestions
        if current_time > time(15, 45):  # Last 15 minutes
            return "CLOSE_END_OF_DAY"
        
        if current_time > time(10, 30) and minutes_in_position > 30:
            if position.get('unrealized_pnl', 0) < 0:
                return "CLOSE_TIME_STOP"
        
        # Regime-based suggestions
        if regime == 'HIGH_VOLATILITY' and position.get('unrealized_pnl', 0) > 0:
            return "CONSIDER_PARTIAL_PROFIT"
        
        return None