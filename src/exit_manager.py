import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)

class ExitManager:
    def __init__(self, config: dict):
        self.config = config
        self.stop_loss_r = config["exit_strategy"]["stop_loss_r"]
        self.target_1_r = config["exit_strategy"]["target_1_r"]
        self.target_1_size_pct = config["exit_strategy"]["target_1_size_pct"]
        self.target_2_r = config["exit_strategy"]["target_2_r"]
        self.time_stop_minutes = config["exit_strategy"]["time_stop_minutes"]
        
        self.oco_orders = {}
    
    def calculate_exit_levels(self, entry_price: float, option_type: str) -> Dict:
        """Calculate stop loss and target levels based on R multiples"""
        risk_per_contract = entry_price
        
        stop_loss = entry_price * (1 + self.stop_loss_r)
        target_1 = entry_price * (1 + self.target_1_r)
        target_2 = entry_price * (1 + self.target_2_r)
        
        return {
            'stop_loss': max(0, stop_loss),
            'target_1': target_1,
            'target_2': target_2,
            'risk_per_contract': risk_per_contract
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