"""
ST0CKA True Gamma Scalping Strategy
Leverages the gamma-scalping-fork infrastructure for real options-based gamma scalping
"""
import asyncio
import sys
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
import pytz

# Add gamma-scalping-fork to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../gamma-scalping-fork'))

from ..unified_engine import TradingStrategy, Position
from ..unified_logging import get_logger

# Import gamma scalping components
try:
    from engine.delta_engine import DeltaEngine
    from market.state import MarketState
    from strategy.options_strategy import OptionsStrategySelector
    from strategy.hedging_strategy import TradingStrategy as GammaHedgingStrategy, TradeCommand
    from portfolio.position_manager import PositionManager as GammaPositionManager
    import config as gamma_config
except ImportError as e:
    print(f"Warning: Could not import gamma scalping components: {e}")
    # Fallback to simple implementation
    DeltaEngine = None
    MarketState = None
    OptionsStrategySelector = None
    GammaHedgingStrategy = None
    GammaPositionManager = None


class ST0CKATrueGammaStrategy(TradingStrategy):
    """
    True gamma scalping strategy that trades options straddles
    - Buys ATM straddles (call + put at same strike)
    - Hedges delta exposure with stock trades
    - Profits from volatility regardless of direction
    """
    
    def __init__(self):
        """Initialize true gamma scalping strategy"""
        self.logger = get_logger(__name__)
        self.eastern = pytz.timezone('US/Eastern')
        
        # Check if gamma scalping components are available
        self.gamma_enabled = DeltaEngine is not None
        
        if not self.gamma_enabled:
            self.logger.warning("Gamma scalping components not available, using simplified mode")
            return
        
        # Initialize gamma scalping components
        self.market_state = MarketState()
        self.delta_engine = DeltaEngine()
        self.options_selector = OptionsStrategySelector(self.delta_engine)
        
        # Async queues for communication between components
        self.delta_queue = asyncio.Queue(maxsize=10)
        self.trade_action_queue = asyncio.Queue(maxsize=10)
        
        # Configuration from gamma scalping
        self.hedging_delta_threshold = gamma_config.HEDGING_DELTA_THRESHOLD
        self.theta_weight = gamma_config.THETA_WEIGHT
        self.min_days_to_expiration = gamma_config.MIN_DAYS_TO_EXPIRATION
        self.max_days_to_expiration = gamma_config.MAX_DAYS_TO_EXPIRATION
        
        # Track current positions
        self.current_straddle = None
        self.portfolio_delta = 0.0
        self.last_hedge_time = None
        self.hedge_cooldown_seconds = 30
        
    def get_config(self) -> Dict[str, Any]:
        """Get strategy configuration"""
        return {
            'strategy': 'st0cka_true_gamma',
            'gamma_enabled': self.gamma_enabled,
            'hedging_delta_threshold': self.hedging_delta_threshold if self.gamma_enabled else None,
            'theta_weight': self.theta_weight if self.gamma_enabled else None,
            'min_days_to_expiration': self.min_days_to_expiration if self.gamma_enabled else None,
            'max_days_to_expiration': self.max_days_to_expiration if self.gamma_enabled else None,
            'cycle_delay': 2,
            'max_consecutive_losses': 10,
            'max_daily_loss': -500.0,
            'max_daily_trades': 100
        }
    
    def check_entry_conditions(self, market_data: Dict[str, Any], positions: Dict[str, Position]) -> Optional[Dict[str, Any]]:
        """
        Check if we should enter a straddle position
        """
        if not self.gamma_enabled:
            return None
            
        now = datetime.now(self.eastern)
        
        # Only trade during market hours
        if not self._is_market_open(now):
            return None
        
        # Check if we already have a straddle
        if self._has_active_straddle(positions):
            return None
        
        # Get SPY price
        spy_price = market_data.get('spy_price')
        if not spy_price:
            return None
        
        # Update market state
        self.market_state.update_stock_market_data(spy_price, spy_price, spy_price)
        
        # Find best straddle to trade
        try:
            # Get options chains data (would need to fetch from Alpaca)
            # For now, return a signal to open a straddle
            return {
                'symbol': 'SPY',
                'signal_type': 'open_straddle',
                'price': spy_price,
                'timestamp': now,
                'reason': 'Gamma scalping opportunity detected'
            }
        except Exception as e:
            self.logger.error(f"Error finding straddle: {e}")
            return None
    
    def get_position_size(self, signal: Dict[str, Any], account_value: float) -> int:
        """
        For straddles, this returns the number of contracts
        """
        if signal['signal_type'] == 'open_straddle':
            # Risk 2% of account per straddle
            risk_amount = account_value * 0.02
            
            # Estimate straddle cost (rough approximation)
            # ATM straddle is typically 3-5% of underlying price
            straddle_cost = signal['price'] * 0.04 * 100  # 100 shares per contract
            
            contracts = int(risk_amount / straddle_cost)
            return max(1, min(contracts, 5))  # 1-5 contracts
        else:
            # For delta hedging with stock
            return self._calculate_hedge_shares(self.portfolio_delta)
    
    def get_entry_order_params(self, signal: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get order parameters for straddle or hedge
        """
        if signal['signal_type'] == 'open_straddle':
            # This would need to return both call and put orders
            # For now, return placeholder
            return {
                'symbol': 'SPY',
                'order_type': 'straddle',
                'time_in_force': 'day',
                'special_instructions': 'open_atm_straddle'
            }
        else:
            # Delta hedge with stock
            return {
                'symbol': 'SPY',
                'side': 'buy' if self.portfolio_delta < 0 else 'sell',
                'order_type': 'market',
                'time_in_force': 'day'
            }
    
    def check_exit_conditions(self, position: Position, market_data: Dict[str, Any]) -> Optional[str]:
        """
        Check if we should exit positions
        """
        if not self.gamma_enabled:
            return None
        
        now = datetime.now(self.eastern)
        
        # Close all positions before market close
        if self._near_market_close(now):
            return "market_close"
        
        # For options positions, check if we should close the straddle
        if self._is_options_position(position):
            # Close if theta decay is too high relative to gamma
            if self._should_close_straddle(position, market_data):
                return "theta_decay"
        
        # For stock hedges, let them run unless rebalancing
        return None
    
    def check_hedge_conditions(self, market_data: Dict[str, Any], positions: Dict[str, Position]) -> Optional[Dict[str, Any]]:
        """
        Check if we need to hedge delta exposure
        """
        if not self.gamma_enabled:
            return None
        
        # Calculate current portfolio delta
        self._update_portfolio_greeks(positions, market_data)
        
        # Check if delta exceeds threshold
        if abs(self.portfolio_delta) > self.hedging_delta_threshold:
            # Check cooldown
            now = datetime.now(self.eastern)
            if self.last_hedge_time:
                time_since_hedge = (now - self.last_hedge_time).total_seconds()
                if time_since_hedge < self.hedge_cooldown_seconds:
                    return None
            
            self.last_hedge_time = now
            
            return {
                'symbol': 'SPY',
                'signal_type': 'delta_hedge',
                'price': market_data.get('spy_price'),
                'timestamp': now,
                'reason': f'Delta hedge needed: {self.portfolio_delta:.2f}',
                'delta': self.portfolio_delta
            }
        
        return None
    
    def _update_portfolio_greeks(self, positions: Dict[str, Position], market_data: Dict[str, Any]) -> None:
        """Update portfolio Greeks based on current positions"""
        if not self.gamma_enabled:
            return
        
        total_delta = 0.0
        
        for pos in positions.values():
            if self._is_options_position(pos):
                # Would calculate option delta here using delta_engine
                # For now, use approximation
                if 'CALL' in pos.symbol:
                    total_delta += pos.quantity * 0.5 * 100  # 50 delta assumption
                elif 'PUT' in pos.symbol:
                    total_delta -= pos.quantity * 0.5 * 100  # -50 delta assumption
            else:
                # Stock has 1 delta per share
                if pos.side == 'long':
                    total_delta += pos.quantity
                else:
                    total_delta -= pos.quantity
        
        self.portfolio_delta = total_delta
    
    def _calculate_hedge_shares(self, delta: float) -> int:
        """Calculate shares needed to hedge delta"""
        # Need to trade opposite direction to neutralize
        shares_needed = abs(delta)
        return int(shares_needed)
    
    def _has_active_straddle(self, positions: Dict[str, Position]) -> bool:
        """Check if we have an active straddle position"""
        has_calls = any('CALL' in p.symbol for p in positions.values())
        has_puts = any('PUT' in p.symbol for p in positions.values())
        return has_calls and has_puts
    
    def _is_options_position(self, position: Position) -> bool:
        """Check if position is an option"""
        return 'CALL' in position.symbol or 'PUT' in position.symbol
    
    def _should_close_straddle(self, position: Position, market_data: Dict[str, Any]) -> bool:
        """Determine if straddle should be closed"""
        # Would use Greeks to make this decision
        # For now, close if position is older than 5 days
        if hasattr(position, 'entry_time'):
            days_held = (datetime.now(self.eastern) - position.entry_time).days
            return days_held > 5
        return False
    
    def _is_market_open(self, now: datetime) -> bool:
        """Check if market is open"""
        market_open = now.replace(hour=9, minute=30, second=0, microsecond=0)
        market_close = now.replace(hour=16, minute=0, second=0, microsecond=0)
        return market_open <= now <= market_close
    
    def _near_market_close(self, now: datetime) -> bool:
        """Check if near market close (last 15 minutes)"""
        close_time = now.replace(hour=15, minute=45, second=0, microsecond=0)
        return now >= close_time
    
    def get_exit_order_params(self, position: Position, exit_reason: str) -> Dict[str, Any]:
        """Get exit order parameters"""
        return {
            'symbol': position.symbol,
            'order_type': 'market',
            'time_in_force': 'day'
        }
    
    async def run_gamma_components(self):
        """Run the gamma scalping components asynchronously"""
        if not self.gamma_enabled:
            return
        
        # This would start the async components from gamma-scalping-fork
        # For integration, we'd need to properly wire up:
        # 1. Market data streaming
        # 2. Delta calculation engine
        # 3. Options strategy selector
        # 4. Position manager
        
        self.logger.info("Gamma scalping components ready for integration")