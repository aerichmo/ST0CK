from datetime import datetime, time
from typing import Dict, List, Optional
import logging
import pytz

logger = logging.getLogger(__name__)

class RiskManager:
    def __init__(self, config: dict, initial_equity: float):
        self.config = config
        self.initial_equity = initial_equity
        self.current_equity = initial_equity
        self.position_risk_pct = config["risk_management"]["position_risk_pct"]
        self.daily_loss_limit_pct = config["risk_management"]["daily_loss_limit_pct"]
        self.consecutive_loss_limit = config["risk_management"]["consecutive_loss_limit"]
        self.max_positions = config["risk_management"]["max_positions"]
        self.account_size_tiers = config["risk_management"]["account_size_tiers"]
        
        self.daily_pnl = 0.0
        self.consecutive_losses = 0
        self.trades_today = []
        self.active_positions = {}
        self.trading_enabled = True
        self.timezone = config["session"]["timezone"]
        
    def get_dynamic_risk_percentage(self) -> float:
        """Get risk percentage based on account size (Antiles approach)"""
        for tier_name, tier_info in self.account_size_tiers.items():
            if self.current_equity <= tier_info["max"]:
                logger.info(f"Account tier: {tier_name} (${self.current_equity:.0f}), Risk: {tier_info['risk_pct']*100:.0f}%")
                return tier_info["risk_pct"]
        
        # Default to most conservative if somehow above all tiers
        return 0.03
    
    def calculate_position_size(self, option_price: float, stop_level: float, 
                              market_regime: Optional[Dict] = None) -> int:
        """Dynamic position sizing based on market conditions and account size"""
        # Get dynamic risk percentage based on account size
        dynamic_risk_pct = self.get_dynamic_risk_percentage()
        base_risk = self.current_equity * dynamic_risk_pct
        
        # Default regime if not provided
        if market_regime is None:
            market_regime = {'regime': 'NORMAL'}
        
        # Adjust risk based on market regime
        regime_multipliers = {
            "HIGH_VOLATILITY": 0.5,    # Half size in high vol
            "CHOPPY": 0.75,            # Reduced size in choppy markets
            "TRENDING": 1.25,          # Increase size in trending markets
            "NORMAL": 1.0,
            "UNKNOWN": 0.75            # Conservative if unknown
        }
        
        regime_mult = regime_multipliers.get(market_regime['regime'], 1.0)
        
        # Adjust for time of day (reduce size after first hour)
        current_time = datetime.now(self.timezone).time()
        time_mult = 0.75 if current_time > time(10, 30) else 1.0
        
        # Adjust for consecutive losses
        loss_mult = max(0.5, 1.0 - (self.consecutive_losses * 0.25))
        
        # Adjust for signal strength if available
        signal_mult = 1.0
        if market_regime.get('confidence', 0) > 0:
            # Scale based on confidence (0.5 to 1.5x)
            signal_mult = 0.5 + market_regime['confidence']
        
        # Calculate adjusted risk amount
        adjusted_risk = base_risk * regime_mult * time_mult * loss_mult * signal_mult
        
        # Calculate contracts
        contracts = int(adjusted_risk / (option_price * 100))
        
        # Apply min/max limits
        min_contracts = 1
        max_contracts = 10  # Cap at 10 contracts
        
        final_contracts = max(min_contracts, min(contracts, max_contracts))
        
        logger.info(f"Position sizing: Equity=${self.current_equity:.0f}, Risk%={dynamic_risk_pct*100:.0f}%, "
                   f"Base=${base_risk:.0f}, Regime={regime_mult:.2f}, "
                   f"Time={time_mult:.2f}, Loss={loss_mult:.2f}, "
                   f"Contracts={final_contracts}")
        
        return final_contracts
    
    def check_trade_allowed(self) -> tuple[bool, str]:
        """Check if new trades are allowed based on risk guards"""
        if not self.trading_enabled:
            return False, "Trading disabled by risk guard"
        
        if self.consecutive_losses >= self.consecutive_loss_limit:
            self.trading_enabled = False
            return False, f"Consecutive loss limit ({self.consecutive_loss_limit}) reached"
        
        daily_loss_pct = abs(self.daily_pnl / self.initial_equity)
        if self.daily_pnl < 0 and daily_loss_pct >= self.daily_loss_limit_pct:
            self.trading_enabled = False
            return False, f"Daily loss limit ({self.daily_loss_limit_pct*100}%) reached"
        
        if len(self.active_positions) >= self.max_positions:
            return False, f"Maximum positions ({self.max_positions}) reached"
        
        return True, "OK"
    
    def add_position(self, position: Dict) -> bool:
        """Add new position to tracking"""
        allowed, reason = self.check_trade_allowed()
        if not allowed:
            logger.warning(f"Trade rejected: {reason}")
            return False
        
        position_id = position['position_id']
        self.active_positions[position_id] = {
            **position,
            'entry_time': datetime.now(),
            'status': 'OPEN',
            'realized_pnl': 0.0,
            'remaining_contracts': position['contracts']
        }
        
        self.trades_today.append({
            'position_id': position_id,
            'entry_time': datetime.now(),
            'symbol': position['symbol']
        })
        
        return True
    
    def update_position_pnl(self, position_id: str, current_price: float):
        """Update unrealized P&L for position"""
        if position_id not in self.active_positions:
            return
        
        position = self.active_positions[position_id]
        entry_price = position['entry_price']
        contracts = position['remaining_contracts']
        
        if position['option_type'] == 'CALL':
            pnl = (current_price - entry_price) * contracts * 100
        else:
            pnl = (entry_price - current_price) * contracts * 100
        
        position['unrealized_pnl'] = pnl
    
    def close_position(self, position_id: str, exit_price: float, 
                      contracts_closed: int = None) -> Dict:
        """Close position or partial position"""
        if position_id not in self.active_positions:
            logger.error(f"Position {position_id} not found")
            return None
        
        position = self.active_positions[position_id]
        
        if contracts_closed is None:
            contracts_closed = position['remaining_contracts']
        
        entry_price = position['entry_price']
        
        if position['option_type'] == 'CALL':
            trade_pnl = (exit_price - entry_price) * contracts_closed * 100
        else:
            trade_pnl = (entry_price - exit_price) * contracts_closed * 100
        
        position['realized_pnl'] += trade_pnl
        position['remaining_contracts'] -= contracts_closed
        
        self.daily_pnl += trade_pnl
        self.current_equity += trade_pnl
        
        if trade_pnl < 0:
            self.consecutive_losses += 1
        else:
            self.consecutive_losses = 0
        
        if position['remaining_contracts'] == 0:
            position['status'] = 'CLOSED'
            position['exit_time'] = datetime.now()
            position['exit_price'] = exit_price
        
        return {
            'position_id': position_id,
            'trade_pnl': trade_pnl,
            'contracts_closed': contracts_closed,
            'remaining_contracts': position['remaining_contracts'],
            'consecutive_losses': self.consecutive_losses,
            'daily_pnl': self.daily_pnl,
            'current_equity': self.current_equity
        }
    
    def check_time_stops(self) -> List[str]:
        """Check for positions that need time-based exit"""
        positions_to_close = []
        time_stop_minutes = self.config["exit_strategy"]["time_stop_minutes"]
        current_time = datetime.now()
        
        for position_id, position in self.active_positions.items():
            if position['status'] != 'OPEN':
                continue
                
            time_in_trade = (current_time - position['entry_time']).total_seconds() / 60
            
            if time_in_trade >= time_stop_minutes:
                positions_to_close.append(position_id)
        
        return positions_to_close
    
    def reset_daily_stats(self):
        """Reset daily statistics at start of new trading day"""
        self.daily_pnl = 0.0
        self.trades_today = []
        self.trading_enabled = True
        if self.consecutive_losses > 0:
            logger.info(f"Carrying over {self.consecutive_losses} consecutive losses")
    
    def get_risk_metrics(self) -> Dict:
        """Get current risk metrics"""
        return {
            'current_equity': self.current_equity,
            'daily_pnl': self.daily_pnl,
            'daily_pnl_pct': self.daily_pnl / self.initial_equity * 100,
            'consecutive_losses': self.consecutive_losses,
            'active_positions': len([p for p in self.active_positions.values() 
                                   if p['status'] == 'OPEN']),
            'trades_today': len(self.trades_today),
            'trading_enabled': self.trading_enabled,
            'total_realized_pnl': sum(p['realized_pnl'] for p in self.active_positions.values()),
            'total_unrealized_pnl': sum(p.get('unrealized_pnl', 0) for p in self.active_positions.values() 
                                      if p['status'] == 'OPEN')
        }
    
    def log_current_state(self):
        """Log current risk management state"""
        metrics = self.get_risk_metrics()
        logger.info(f"Risk State: Equity=${metrics['current_equity']:,.0f}, "
                   f"Daily P&L=${metrics['daily_pnl']:+,.0f} ({metrics['daily_pnl_pct']:+.1f}%), "
                   f"Positions={metrics['active_positions']}, "
                   f"Consecutive Losses={metrics['consecutive_losses']}, "
                   f"Trading={'ENABLED' if metrics['trading_enabled'] else 'DISABLED'}")
    
    def get_open_positions(self) -> List[Dict]:
        """Get list of open positions"""
        return [p for p in self.active_positions.values() if p['status'] == 'OPEN']
    
    def remove_position(self, position_id: str):
        """Remove position from tracking"""
        if position_id in self.active_positions:
            self.active_positions[position_id]['status'] = 'CLOSED'
    
    def update_daily_pnl(self, pnl: float):
        """Update daily P&L"""
        self.daily_pnl += pnl
        self.current_equity += pnl
    
    def calculate_pnl(self, entry_price: float, exit_price: float, contracts: int) -> float:
        """Calculate P&L for a position"""
        return (exit_price - entry_price) * contracts * 100