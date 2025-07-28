"""
ST0CKA Enhanced Strategy Implementation
Incorporates volatility-based trading inspired by Alpaca's gamma scalping
Supports stock scalping, volatility-based sizing, and options straddles
"""
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
import pytz
import numpy as np
from math import sqrt

from ..unified_engine import TradingStrategy, Position
from ..unified_logging import get_logger

class ST0CKAEnhancedStrategy(TradingStrategy):
    """
    Enhanced SPY trading strategy with multiple modes:
    - 'simple': Original single-share scalping
    - 'volatility': Dynamic position sizing based on volatility
    - 'straddle': Options straddles for volatility harvesting (like Alpaca)
    - 'adaptive': Switches between strategies based on market conditions
    """
    
    def __init__(self, mode: str = "volatility"):
        """
        Initialize ST0CKA Enhanced strategy
        
        Args:
            mode: Trading mode - 'simple', 'volatility', 'straddle', or 'adaptive'
        """
        self.mode = mode
        self.logger = get_logger(__name__)
        self.eastern = pytz.timezone('US/Eastern')
        
        # Core parameters
        self.symbol = 'SPY'
        self.profit_target_pct = 0.0013  # 0.13% base target
        self.min_profit_target = 0.65
        self.max_profit_target = 1.50
        
        # Volatility parameters (inspired by Alpaca)
        self.volatility_lookback = 20  # bars for realized vol
        self.volatility_threshold = 1.1  # realized/implied ratio to enter
        self.base_position_size = 1
        self.max_position_size = 10
        self.volatility_baseline = 15  # 15% annual vol as baseline
        
        # Straddle parameters (from Alpaca's approach)
        self.delta_threshold = 2.0  # Rebalance when portfolio delta exceeds this
        self.min_days_to_expiry = 0  # 0DTE for ST0CKA
        self.max_days_to_expiry = 5  # Up to 5 DTE
        self.min_open_interest = 100
        self.max_spread_pct = 0.02  # 2% max bid-ask spread
        
        # Trading windows (unchanged)
        self.morning_buy_start = "09:30"
        self.morning_buy_end = "10:00"
        self.morning_sell_start = "10:00"
        self.morning_sell_end = "11:00"
        self.power_buy_start = "15:00"
        self.power_buy_end = "15:30"
        self.power_sell_start = "15:30"
        self.power_sell_end = "15:45"
        
        # State tracking
        self.last_volatility_check = None
        self.current_realized_vol = None
        self.current_implied_vol = None
        self.portfolio_delta = 0.0
        self.last_entry_time = None
        self.entry_interval_seconds = 30
        
        # Mode-specific settings
        if mode == 'straddle':
            self.max_positions = 3  # Multiple straddles
        elif mode == 'volatility':
            self.max_positions = 10  # Scale with volatility
        else:
            self.max_positions = 1  # Simple mode
    
    def get_config(self) -> Dict[str, Any]:
        """Get strategy configuration"""
        config = {
            'strategy': 'st0cka_enhanced',
            'mode': self.mode,
            'profit_target_pct': self.profit_target_pct,
            'min_profit_target': self.min_profit_target,
            'max_profit_target': self.max_profit_target,
            'base_position_size': self.base_position_size,
            'max_position_size': self.max_position_size,
            'max_positions': self.max_positions,
            'trading_sessions': {
                'morning': f"{self.morning_buy_start}-{self.morning_sell_end}",
                'power_hour': f"{self.power_buy_start}-{self.power_sell_end}"
            },
            'cycle_delay': 3 if self.mode == 'straddle' else 5,
            'max_consecutive_losses': 3,
            'max_daily_loss': -500.0,
            'max_daily_trades': 20
        }
        
        if self.mode in ['volatility', 'straddle', 'adaptive']:
            config['volatility_params'] = {
                'lookback': self.volatility_lookback,
                'threshold': self.volatility_threshold,
                'baseline': self.volatility_baseline
            }
        
        return config
    
    async def get_required_market_data(self, market_data_provider) -> Dict[str, Any]:
        """Get additional market data required by strategy"""
        data = {}
        
        # Get volatility data if needed
        if self.mode in ['volatility', 'straddle', 'adaptive']:
            data['volatility'] = await self._calculate_volatility(market_data_provider)
        
        # Get options data for straddle mode
        if self.mode == 'straddle':
            data['options_chain'] = await self._get_options_data(market_data_provider)
            data['portfolio_delta'] = self._calculate_portfolio_delta()
        
        return data
    
    def check_entry_conditions(self, market_data: Dict[str, Any], positions: Dict[str, Position]) -> Optional[Dict[str, Any]]:
        """
        Enhanced entry conditions based on mode
        """
        now = datetime.now(self.eastern)
        
        # Check trading windows
        if not self._in_buy_window(now):
            return None
        
        # Check position limits
        if self._count_positions(positions) >= self.max_positions:
            return None
        
        # Check entry interval
        if self.last_entry_time:
            seconds_since_last = (now - self.last_entry_time).total_seconds()
            if seconds_since_last < self.entry_interval_seconds:
                return None
        
        # Mode-specific entry logic
        if self.mode == 'simple':
            return self._simple_entry_logic(market_data, now)
        elif self.mode == 'volatility':
            return self._volatility_entry_logic(market_data, now)
        elif self.mode == 'straddle':
            return self._straddle_entry_logic(market_data, now)
        elif self.mode == 'adaptive':
            return self._adaptive_entry_logic(market_data, now)
    
    def _simple_entry_logic(self, market_data: Dict[str, Any], now: datetime) -> Optional[Dict[str, Any]]:
        """Original simple entry logic"""
        spy_price = market_data.get('spy_price')
        if not spy_price:
            return None
        
        self.last_entry_time = now
        return {
            'symbol': 'SPY',
            'signal_type': 'buy',
            'price': spy_price,
            'timestamp': now,
            'reason': 'ST0CKA simple mode entry'
        }
    
    def _volatility_entry_logic(self, market_data: Dict[str, Any], now: datetime) -> Optional[Dict[str, Any]]:
        """Volatility-based entry (Alpaca-inspired)"""
        spy_price = market_data.get('spy_price')
        volatility_data = market_data.get('volatility', {})
        
        if not spy_price or not volatility_data:
            return None
        
        realized_vol = volatility_data.get('realized')
        implied_vol = volatility_data.get('implied')
        
        if not realized_vol or not implied_vol:
            return None
        
        # Enter when realized > implied (Alpaca's key insight)
        vol_ratio = realized_vol / implied_vol if implied_vol > 0 else 0
        
        if vol_ratio >= self.volatility_threshold:
            self.logger.info(f"Volatility opportunity: Realized={realized_vol:.1f}%, Implied={implied_vol:.1f}%, Ratio={vol_ratio:.2f}")
            self.last_entry_time = now
            
            return {
                'symbol': 'SPY',
                'signal_type': 'buy',
                'price': spy_price,
                'timestamp': now,
                'reason': f'Volatility arbitrage - RV/IV ratio: {vol_ratio:.2f}',
                'volatility': realized_vol,
                'vol_ratio': vol_ratio
            }
        
        return None
    
    def _straddle_entry_logic(self, market_data: Dict[str, Any], now: datetime) -> Optional[Dict[str, Any]]:
        """Options straddle entry (pure Alpaca approach)"""
        spy_price = market_data.get('spy_price')
        options_chain = market_data.get('options_chain', {})
        volatility_data = market_data.get('volatility', {})
        
        if not spy_price or not options_chain:
            return None
        
        # Find best straddle using Alpaca's scoring
        best_straddle = self._find_best_straddle(spy_price, options_chain, volatility_data)
        
        if best_straddle:
            self.last_entry_time = now
            return {
                'symbol': 'SPY',
                'signal_type': 'straddle',
                'price': spy_price,
                'timestamp': now,
                'reason': 'Options straddle for volatility harvesting',
                'strike': best_straddle['strike'],
                'expiry': best_straddle['expiry'],
                'contracts': best_straddle
            }
        
        return None
    
    def _adaptive_entry_logic(self, market_data: Dict[str, Any], now: datetime) -> Optional[Dict[str, Any]]:
        """Adaptive mode - choose best strategy for current conditions"""
        volatility_data = market_data.get('volatility', {})
        realized_vol = volatility_data.get('realized', 0)
        
        # High volatility -> use straddles
        if realized_vol > 25:
            return self._straddle_entry_logic(market_data, now)
        # Medium volatility -> use volatility sizing
        elif realized_vol > 15:
            return self._volatility_entry_logic(market_data, now)
        # Low volatility -> use simple mode
        else:
            return self._simple_entry_logic(market_data, now)
    
    def get_position_size(self, signal: Dict[str, Any], account_value: float) -> int:
        """
        Dynamic position sizing based on volatility
        """
        if self.mode == 'simple':
            return self.base_position_size
        
        # Get volatility from signal
        volatility = signal.get('volatility', self.volatility_baseline)
        vol_ratio = signal.get('vol_ratio', 1.0)
        
        # Scale position size with volatility
        if self.mode == 'volatility' or self.mode == 'adaptive':
            # Higher volatility = larger positions (more opportunity)
            vol_multiplier = volatility / self.volatility_baseline
            vol_multiplier = max(0.5, min(3.0, vol_multiplier))  # Cap at 0.5x-3x
            
            # Also scale by vol ratio (realized/implied)
            ratio_multiplier = max(1.0, vol_ratio - 1.0)  # Extra size for high ratio
            
            position_size = int(self.base_position_size * vol_multiplier * ratio_multiplier)
            position_size = min(position_size, self.max_position_size)
            
            self.logger.debug(f"Position size: {position_size} (vol={volatility:.1f}%, multiplier={vol_multiplier:.1f})")
            return position_size
        
        return self.base_position_size
    
    def get_entry_order_params(self, signal: Dict[str, Any]) -> Dict[str, Any]:
        """Get entry order parameters"""
        if signal.get('signal_type') == 'straddle':
            # Return params for options straddle
            return {
                'symbol': 'SPY',
                'order_type': 'straddle',
                'strike': signal['strike'],
                'expiry': signal['expiry'],
                'contracts': signal.get('contracts', 1)
            }
        else:
            # Regular stock order
            return {
                'symbol': 'SPY',
                'side': 'buy',
                'order_type': 'market',
                'time_in_force': 'day'
            }
    
    def check_exit_conditions(self, position: Position, market_data: Dict[str, Any]) -> Optional[str]:
        """
        Enhanced exit conditions
        """
        if position.symbol != 'SPY':
            return None
        
        now = datetime.now(self.eastern)
        
        # Straddle positions have different exit logic
        if hasattr(position, 'position_type') and position.position_type == 'straddle':
            return self._check_straddle_exit(position, market_data)
        
        # Calculate dynamic profit target
        profit_target = self._calculate_profit_target(position.avg_price)
        
        # Volatility-adjusted target
        if self.mode in ['volatility', 'adaptive']:
            volatility_data = market_data.get('volatility', {})
            current_vol = volatility_data.get('realized', self.volatility_baseline)
            vol_multiplier = current_vol / self.volatility_baseline
            profit_target *= vol_multiplier
        
        # Check profit target
        if position.unrealized_pnl and position.unrealized_pnl >= profit_target:
            return "profit_target"
        
        # Check stop loss (new for volatility mode)
        if self.mode in ['volatility', 'adaptive']:
            stop_loss = -profit_target * 1.5  # 1.5x risk
            if position.unrealized_pnl and position.unrealized_pnl <= stop_loss:
                return "stop_loss"
        
        # Check force exit window
        if self._in_sell_window(now):
            return "time_exit"
        
        return None
    
    def _check_straddle_exit(self, position: Position, market_data: Dict[str, Any]) -> Optional[str]:
        """Check exit conditions for straddle positions"""
        # Exit if delta exceeds threshold (needs rebalancing)
        portfolio_delta = market_data.get('portfolio_delta', 0)
        if abs(portfolio_delta) > self.delta_threshold:
            return "delta_rebalance"
        
        # Exit if near expiry
        if hasattr(position, 'expiry'):
            time_to_expiry = position.expiry - datetime.now()
            if time_to_expiry.total_seconds() < 3600:  # Less than 1 hour
                return "expiry_close"
        
        # Exit on profit target (different calculation for options)
        if position.unrealized_pnl:
            # Target 20% of premium paid
            premium_paid = getattr(position, 'premium_paid', position.avg_price * 100)
            if position.unrealized_pnl >= premium_paid * 0.20:
                return "profit_target"
        
        return None
    
    async def _calculate_volatility(self, market_data_provider) -> Dict[str, float]:
        """Calculate realized and implied volatility"""
        try:
            # Get historical data for realized vol
            bars = await market_data_provider.get_bars(
                self.symbol,
                timeframe='5Min',
                limit=self.volatility_lookback * 12  # 12 5-min bars per hour
            )
            
            if not bars or len(bars) < 10:
                return {'realized': self.volatility_baseline, 'implied': self.volatility_baseline}
            
            # Calculate realized volatility
            returns = []
            for i in range(1, len(bars)):
                ret = (bars[i].close - bars[i-1].close) / bars[i-1].close
                returns.append(ret)
            
            # Annualized volatility
            std_dev = np.std(returns) if returns else 0
            periods_per_year = 252 * 6.5 * 12  # Trading days * hours * periods/hour
            realized_vol = std_dev * sqrt(periods_per_year) * 100
            
            # Get implied volatility from options
            implied_vol = await self._get_implied_volatility(market_data_provider)
            
            self.current_realized_vol = realized_vol
            self.current_implied_vol = implied_vol
            
            return {
                'realized': realized_vol,
                'implied': implied_vol,
                'ratio': realized_vol / implied_vol if implied_vol > 0 else 0
            }
            
        except Exception as e:
            self.logger.error(f"Error calculating volatility: {e}")
            return {'realized': self.volatility_baseline, 'implied': self.volatility_baseline}
    
    async def _get_implied_volatility(self, market_data_provider) -> float:
        """Get implied volatility from ATM options"""
        try:
            # Get current price
            quote = await market_data_provider.get_quote(self.symbol)
            if not quote:
                return self.volatility_baseline
            
            spot_price = (quote.ask + quote.bid) / 2
            
            # Get nearest ATM option
            options = await market_data_provider.get_option_chain(
                self.symbol,
                expiry_days=1  # Use 1DTE for short-term IV
            )
            
            if not options:
                return self.volatility_baseline
            
            # Find ATM strike
            atm_strike = round(spot_price)
            atm_call = next((opt for opt in options if opt.strike == atm_strike and opt.type == 'CALL'), None)
            
            if atm_call and hasattr(atm_call, 'implied_volatility'):
                return atm_call.implied_volatility * 100
            
            return self.volatility_baseline
            
        except Exception as e:
            self.logger.error(f"Error getting implied volatility: {e}")
            return self.volatility_baseline
    
    async def _get_options_data(self, market_data_provider) -> Dict[str, Any]:
        """Get options chain data for straddle trading"""
        try:
            options = await market_data_provider.get_option_chain(
                self.symbol,
                min_expiry_days=self.min_days_to_expiry,
                max_expiry_days=self.max_days_to_expiry
            )
            
            if not options:
                return {}
            
            # Filter by liquidity
            liquid_options = [
                opt for opt in options
                if opt.open_interest >= self.min_open_interest
                and opt.bid_ask_spread_pct <= self.max_spread_pct
            ]
            
            return {
                'all_options': options,
                'liquid_options': liquid_options
            }
            
        except Exception as e:
            self.logger.error(f"Error getting options data: {e}")
            return {}
    
    def _find_best_straddle(self, spot_price: float, options_chain: Dict, volatility_data: Dict) -> Optional[Dict]:
        """Find best straddle using Alpaca's scoring method"""
        liquid_options = options_chain.get('liquid_options', [])
        if not liquid_options:
            return None
        
        best_score = float('inf')
        best_straddle = None
        
        # Group by strike and expiry
        straddles = {}
        for opt in liquid_options:
            key = (opt.strike, opt.expiry)
            if key not in straddles:
                straddles[key] = {}
            straddles[key][opt.type] = opt
        
        # Score each straddle
        for (strike, expiry), legs in straddles.items():
            if 'CALL' not in legs or 'PUT' not in legs:
                continue
            
            call = legs['CALL']
            put = legs['PUT']
            
            # Calculate score (from Alpaca)
            # Score = (abs(Theta) * THETA_WEIGHT + Transaction Cost) / Gamma
            theta = abs(call.theta + put.theta) if hasattr(call, 'theta') else 0.01
            gamma = (call.gamma + put.gamma) if hasattr(call, 'gamma') else 0.01
            
            # Transaction cost = spread
            trans_cost = (call.ask - call.bid) + (put.ask - put.bid)
            
            # Alpaca uses THETA_WEIGHT = 0.1
            score = (theta * 0.1 + trans_cost) / gamma if gamma > 0 else float('inf')
            
            if score < best_score:
                best_score = score
                best_straddle = {
                    'strike': strike,
                    'expiry': expiry,
                    'call': call,
                    'put': put,
                    'score': score
                }
        
        return best_straddle
    
    def _calculate_portfolio_delta(self) -> float:
        """Calculate total portfolio delta"""
        # This would need access to all positions
        # For now, return 0 (will be implemented with position tracking)
        return 0.0
    
    def _count_positions(self, positions: Dict[str, Position]) -> int:
        """Count relevant positions"""
        if self.mode == 'straddle':
            # Count straddle positions
            return sum(1 for p in positions.values() 
                      if hasattr(p, 'position_type') and p.position_type == 'straddle')
        else:
            # Count SPY stock positions
            return sum(1 for p in positions.values() if p.symbol == 'SPY')
    
    def _in_buy_window(self, now: datetime) -> bool:
        """Check if within any buy window"""
        # Morning buy window
        morning_start_hour, morning_start_min = map(int, self.morning_buy_start.split(':'))
        morning_end_hour, morning_end_min = map(int, self.morning_buy_end.split(':'))
        
        morning_start = now.replace(hour=morning_start_hour, minute=morning_start_min, second=0, microsecond=0)
        morning_end = now.replace(hour=morning_end_hour, minute=morning_end_min, second=0, microsecond=0)
        
        # Power hour buy window
        power_start_hour, power_start_min = map(int, self.power_buy_start.split(':'))
        power_end_hour, power_end_min = map(int, self.power_buy_end.split(':'))
        
        power_start = now.replace(hour=power_start_hour, minute=power_start_min, second=0, microsecond=0)
        power_end = now.replace(hour=power_end_hour, minute=power_end_min, second=0, microsecond=0)
        
        return (morning_start <= now <= morning_end) or (power_start <= now <= power_end)
    
    def _in_sell_window(self, now: datetime) -> bool:
        """Check if within any sell window"""
        # Morning sell window
        morning_start_hour, morning_start_min = map(int, self.morning_sell_start.split(':'))
        morning_end_hour, morning_end_min = map(int, self.morning_sell_end.split(':'))
        
        morning_start = now.replace(hour=morning_start_hour, minute=morning_start_min, second=0, microsecond=0)
        morning_end = now.replace(hour=morning_end_hour, minute=morning_end_min, second=0, microsecond=0)
        
        # Power hour sell window
        power_start_hour, power_start_min = map(int, self.power_sell_start.split(':'))
        power_end_hour, power_end_min = map(int, self.power_sell_end.split(':'))
        
        power_start = now.replace(hour=power_start_hour, minute=power_start_min, second=0, microsecond=0)
        power_end = now.replace(hour=power_end_hour, minute=power_end_min, second=0, microsecond=0)
        
        return (morning_start <= now <= morning_end) or (power_start <= now <= power_end)
    
    def _calculate_profit_target(self, entry_price: float) -> float:
        """Calculate dynamic profit target based on entry price"""
        # Calculate percentage-based target
        target = entry_price * self.profit_target_pct
        
        # Apply min/max bounds
        target = max(self.min_profit_target, min(target, self.max_profit_target))
        
        return target