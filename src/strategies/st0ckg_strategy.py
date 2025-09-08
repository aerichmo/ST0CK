"""
ST0CKG Strategy Implementation
Preserves exact Battle Lines 0-DTE options trading logic
"""
from datetime import datetime, time, timedelta
from typing import Dict, List, Optional, Any, Tuple
import pytz

from ..unified_engine import TradingStrategy, Position
from ..unified_logging import get_logger
from ..unified_database import get_latest_battle_lines, save_battle_lines
from ..st0ckg_signals import ST0CKGSignalDetector
from ..options_selector import FastOptionsSelector
from ..trend_filter_native import TrendFilter
from ..data_quality_manager import DataQualityManager

class ST0CKGStrategy(TradingStrategy):
    """
    Battle Lines 0-DTE Options Strategy
    - Trades SPY options at key price levels
    - Uses advanced signal detection
    - Dynamic position management with R-based targets
    """
    
    def __init__(self, 
                 db_manager=None,
                 market_data_provider=None,
                 start_time: str = "09:40",
                 end_time: str = "10:30",
                 max_positions: int = 2):
        """
        Initialize ST0CKG strategy
        
        Args:
            db_manager: Database manager for battle lines
            market_data_provider: Market data provider
            start_time: Trading window start
            end_time: Trading window end
            max_positions: Maximum concurrent positions
        """
        self.logger = get_logger(__name__)
        self.eastern = pytz.timezone('US/Eastern')
        
        # Components
        self.db_manager = db_manager
        self.market_data = market_data_provider
        self.signal_detector = ST0CKGSignalDetector(market_data_provider)
        # Options configuration
        options_config = {
            "options": {
                "target_delta": 0.30,  # Target delta for options
                "delta_tolerance": 0.10,  # Delta tolerance range
                "max_spread_pct": 0.10  # Maximum bid-ask spread (10%)
            }
        }
        self.options_selector = FastOptionsSelector(options_config, market_data_provider)
        self.trend_filter = TrendFilter()
        
        # Data quality manager for IEX feed handling
        self.data_quality = DataQualityManager(market_data_provider) if market_data_provider else None
        
        # Trading parameters (DO NOT CHANGE - core strategy logic)
        self.start_time = start_time
        self.end_time = end_time
        self.max_positions = max_positions
        self.risk_per_trade = 0.01  # 1% risk per trade
        
        # Position management parameters
        self.breakeven_r = 1.0    # Move stop to breakeven at 1R
        self.scale_r = 1.5        # Scale out 50% at 1.5R
        self.final_target_r = 3.0 # Final target at 3R
        
        # State tracking
        self.battle_lines = None
        self.last_battle_lines_update = None
        self.daily_trades = 0
        self.last_signal_time = {}  # Track last signal time by type
        self.signal_cooldown = 300  # 5 minute cooldown between same signal type
    
    def get_config(self) -> Dict[str, Any]:
        """Get strategy configuration"""
        return {
            'strategy': 'st0ckg',
            'trading_window_start': 'Any time',
            'trading_window_end': 'Market hours',
            'max_positions': self.max_positions,
            'risk_per_trade': self.risk_per_trade,
            'cycle_delay': 2,  # 2 second cycle for options
            'max_consecutive_losses': 3,
            'max_daily_loss': -500.0,
            'max_daily_trades': 10
        }
    
    async def get_required_market_data(self, market_data_provider) -> Dict[str, Any]:
        """Get additional market data required by strategy"""
        # Update battle lines if needed
        await self._update_battle_lines()
        
        # Get market internals (SPY only)
        data = {
            'battle_lines': self.battle_lines,
            'spy_quote': None,
            'market_breadth': None,
            'option_chains': {}  # Pre-fetch option chains
        }
        
        # Get fresh SPY quote
        try:
            spy_quote = await market_data_provider.get_quote('SPY')
            if spy_quote:
                data['spy_quote'] = spy_quote
                
                # Pre-fetch option chains for common price ranges
                price = spy_quote['price']
                
                # Get option chain snapshot for current price range
                lower_bound = price - 5
                upper_bound = price + 5
                
                option_snapshot = await market_data_provider.get_option_chain_snapshot_async(
                    'SPY', lower_bound, upper_bound
                )
                
                if option_snapshot:
                    data['option_chains']['snapshot'] = option_snapshot
                    
                # Pre-fetch 0-DTE options for intraday trading
                expiry = self._get_0dte_expiry_date()
                expiry_str = expiry.strftime('%Y-%m-%d')
                
                target_delta = 0.30  # Default target delta
                calls = await market_data_provider.find_best_options_async(
                    'SPY', expiry_str, 'CALL', target_delta
                )
                puts = await market_data_provider.find_best_options_async(
                    'SPY', expiry_str, 'PUT', target_delta
                )
                
                data['option_chains']['calls'] = calls or []
                data['option_chains']['puts'] = puts or []
                
        except Exception as e:
            self.logger.warning(f"Failed to get SPY quote: {str(e)}", 
                              extra={"symbol": "SPY"})
        
        return data
    
    def check_entry_conditions(self, market_data: Dict[str, Any], positions: Dict[str, Position]) -> Optional[Dict[str, Any]]:
        """
        Check for Battle Lines entry signals
        """
        now = datetime.now(self.eastern)
        
        # Trading window check removed - bot can trade at any time
        
        # Check position limit
        if len(positions) >= self.max_positions:
            return None
        
        # Check battle lines
        if not self.battle_lines:
            self.logger.warning("No battle lines available", 
                              extra={"symbol": "SPY"})
            return None
        
        spy_price = market_data.get('spy_price')
        if not spy_price:
            return None
        
        # Get quality-adjusted quote if using IEX data
        # Note: Quality adjustment is handled in the data_quality_manager if enabled
        
        # Set pre-fetched options if available
        if 'option_chains' in market_data:
            self.options_selector.set_prefetched_options(market_data['option_chains'])
        
        # Detect signals
        signals = self.signal_detector.detect_all_signals(
            symbol='SPY',
            current_price=spy_price,
            battle_lines=self.battle_lines,
            market_context=market_data
        )
        
        if not signals:
            # Log periodically when no signals
            if not hasattr(self, '_last_no_signal_log') or (now - self._last_no_signal_log).seconds > 300:
                self.logger.info(f"No signals detected. SPY: ${spy_price:.2f}, Time: {now.strftime('%H:%M')}")
                self._last_no_signal_log = now
            return None
        
        # Get the highest scoring signal
        best_signal = max(signals.items(), key=lambda x: x[1].get('score', 0))
        signal_type, signal_data = best_signal
        
        # Check signal cooldown
        last_signal = self.last_signal_time.get(signal_type)
        if last_signal:
            seconds_since = (now - last_signal).total_seconds()
            if seconds_since < self.signal_cooldown:
                return None
        
        # Check trend filter
        if not self.trend_filter.is_trend_favorable(signal_type, market_data):
            self.logger.info(f"Signal {signal_type} filtered by trend")
            return None
        
        # Select option contract
        contract = self.options_selector.select_best_option(
            'SPY',
            signal_type,
            spy_price
        )
        
        if not contract:
            self.logger.warning(f"No suitable option contract for {signal_type}", 
                              extra={"signal_type": signal_type, "current_price": spy_price})
            return None
        
        # Update last signal time
        self.last_signal_time[signal_type] = now
        
        # Return comprehensive signal
        return {
            'symbol': contract['symbol'],
            'signal_type': signal_type,
            'signal_score': signal_data.get('score', 0),
            'price': spy_price,
            'option_contract': contract,
            'battle_line': signal_data.get('battle_line'),
            'entry_price': contract['ask'],
            'timestamp': now,
            'risk_amount': None  # Will be calculated in position sizing
        }
    
    def get_position_size(self, signal: Dict[str, Any], account_value: float) -> int:
        """
        Calculate position size based on 1% risk
        """
        risk_amount = account_value * self.risk_per_trade
        contract = signal['option_contract']
        
        # For options, risk is the premium paid
        premium_per_contract = contract['ask'] * 100  # Options are 100 shares
        
        # Calculate number of contracts
        contracts = int(risk_amount / premium_per_contract)
        
        # Minimum 1 contract, maximum based on liquidity
        contracts = max(1, min(contracts, 10))
        
        # Store risk amount in signal for position tracking
        signal['risk_amount'] = contracts * premium_per_contract
        
        return contracts
    
    def get_entry_order_params(self, signal: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get entry order parameters for options
        """
        contract = signal['option_contract']
        
        # Base limit price
        base_limit = contract['ask'] * 1.02  # 2% above ask
        
        # Apply data quality adjustments if using IEX
        if self.data_quality:
            adjustments = self.data_quality.get_execution_adjustments(signal['signal_type'])
            # Add extra buffer for IEX's wider spreads
            limit_price = base_limit + adjustments['limit_price_buffer']
        else:
            limit_price = base_limit
        
        return {
            'symbol': contract['symbol'],
            'side': 'buy',
            'order_type': 'limit',
            'limit_price': round(limit_price, 2),
            'time_in_force': 'day'
        }
    
    def check_exit_conditions(self, position: Position, market_data: Dict[str, Any]) -> Optional[str]:
        """
        Check exit conditions for options positions
        
        Exit conditions:
        1. Stop loss hit (option loses 50% of value)
        2. Breakeven management at 1R
        3. Scale out at 1.5R
        4. Final target at 3R
        5. Time exit near market close
        6. Signal invalidation
        """
        now = datetime.now(self.eastern)
        
        # Time exit - close all positions 10 minutes before market close
        if now.time() >= time(15, 50):
            return "time_exit"
        
        # Check if we have price data
        if not position.current_price:
            return None
        
        # Get position metadata
        entry_price = position.entry_price
        current_price = position.current_price
        risk_amount = position.strategy_data.get('risk_amount', entry_price * position.quantity * 100)
        
        # Calculate R-multiple
        pnl = (current_price - entry_price) * position.quantity * 100
        r_multiple = pnl / risk_amount if risk_amount > 0 else 0
        
        # Stop loss - option loses 50% of value
        if current_price <= entry_price * 0.5:
            return "stop_loss"
        
        # Check R-based exits
        if r_multiple >= self.final_target_r:
            return "final_target"
        elif r_multiple >= self.scale_r and not position.strategy_data.get('scaled', False):
            return "scale_out"
        elif r_multiple >= self.breakeven_r and not position.strategy_data.get('breakeven_set', False):
            # Just update stop, don't exit
            self._update_breakeven_stop(position)
            return None
        
        # Check signal invalidation
        signal_type = position.strategy_data.get('signal_type')
        if signal_type and self._is_signal_invalidated(signal_type, market_data):
            return "signal_invalidated"
        
        return None
    
    def get_exit_order_params(self, position: Position, exit_reason: str) -> Dict[str, Any]:
        """
        Get exit order parameters based on exit reason
        """
        # For scale out, only exit half position
        quantity = position.quantity
        if exit_reason == "scale_out":
            quantity = position.quantity // 2
            # Mark position as scaled
            position.strategy_data['scaled'] = True
            position.quantity -= quantity  # Update remaining quantity
        
        # Use market orders for all exits (options need quick fills)
        return {
            'symbol': position.symbol,
            'order_type': 'market',
            'time_in_force': 'day',
            'quantity': quantity  # Override default quantity for scale outs
        }
    
    async def _update_battle_lines(self):
        """Update battle lines if needed"""
        now = datetime.now(self.eastern)
        
        # Update once per day at market open
        if (not self.last_battle_lines_update or 
            self.last_battle_lines_update.date() != now.date()):
            
            # Try to get from database first
            if self.db_manager:
                saved_lines = get_latest_battle_lines(self.db_manager)
                if saved_lines:
                    # Battle lines from DB are already for today (filtered by date in query)
                    self.battle_lines = saved_lines
                    self.last_battle_lines_update = now
                    return
            
            # Calculate new battle lines
            if self.market_data:
                battle_lines = await self._calculate_battle_lines()
                if battle_lines:
                    self.battle_lines = battle_lines
                    self.last_battle_lines_update = now
                    
                    # Save to database
                    if self.db_manager:
                        save_battle_lines(self.db_manager, 'st0ckg', 'SPY', battle_lines)
    
    async def _calculate_battle_lines(self) -> Optional[Dict[str, float]]:
        """Calculate battle lines from market data"""
        try:
            # This would normally calculate from historical data
            # For now, return placeholder
            spy_quote = await self.market_data.get_quote('SPY')
            if not spy_quote:
                return None
            
            current = spy_quote['price']
            
            # Placeholder calculation (would use real historical data)
            return {
                'pdh': current + 2.0,  # Previous day high
                'pdl': current - 2.0,  # Previous day low
                'overnight_high': current + 1.0,
                'overnight_low': current - 1.0,
                'premarket_high': current + 0.5,
                'premarket_low': current - 0.5,
                'rth_high': current + 3.0,
                'rth_low': current - 3.0
            }
            
        except Exception as e:
            self.logger.error(f"Failed to calculate battle lines: {str(e)}", 
                            extra={"symbol": "SPY", "error_type": type(e).__name__})
            return None
    
    def _get_weekly_expiry_date(self) -> datetime:
        """Get next weekly expiry date for SPY options"""
        today = datetime.now(self.eastern)
        days_until_friday = (4 - today.weekday()) % 7
        
        # If it's Friday after market close, use next Friday
        if days_until_friday == 0 and today.hour >= 16:
            days_until_friday = 7
        
        # If less than 2 days to expiry, use next week
        if days_until_friday < 2:
            days_until_friday += 7
        
        expiry = today + timedelta(days=days_until_friday)
        return expiry.replace(hour=16, minute=0, second=0, microsecond=0)
    
    def _get_0dte_expiry_date(self) -> datetime:
        """Get 0-DTE (same day) expiry date for SPY options"""
        now = datetime.now(self.eastern)
        today = now.date()
        
        # Check if today is a weekday (Monday=0, Friday=4)
        if today.weekday() <= 4:
            # For 0-DTE, use today's date
            expiry = now.replace(hour=16, minute=0, second=0, microsecond=0)
            self.logger.info(f"0-DTE expiry date: {expiry.strftime('%Y-%m-%d')} (today, weekday)")
            return expiry
        else:
            # If weekend, use next Monday for 0-DTE
            if today.weekday() == 6:  # Sunday
                days_until_monday = 1
            else:  # Saturday
                days_until_monday = 2
            next_trading_day = now + timedelta(days=days_until_monday)
            expiry = next_trading_day.replace(hour=16, minute=0, second=0, microsecond=0)
            self.logger.info(f"0-DTE expiry date: {expiry.strftime('%Y-%m-%d')} (next Monday, weekend adjustment)")
            return expiry
    
    def _in_trading_window(self, now: datetime) -> bool:
        """Check if within trading window"""
        start_hour, start_min = map(int, self.start_time.split(':'))
        end_hour, end_min = map(int, self.end_time.split(':'))
        
        window_start = now.replace(hour=start_hour, minute=start_min, second=0, microsecond=0)
        window_end = now.replace(hour=end_hour, minute=end_min, second=0, microsecond=0)
        
        return window_start <= now <= window_end
    
    def _update_breakeven_stop(self, position: Position):
        """Update position to breakeven stop"""
        position.strategy_data['breakeven_set'] = True
        position.strategy_data['stop_price'] = position.entry_price
        self.logger.info(f"Updated position {position.id} to breakeven stop")
    
    def _is_signal_invalidated(self, signal_type: str, market_data: Dict[str, Any]) -> bool:
        """Check if signal has been invalidated"""
        spy_price = market_data.get('spy_price')
        if not spy_price or not self.battle_lines:
            return False
        
        # Signal-specific invalidation logic
        if 'CALL' in signal_type.upper():
            # Bullish signals invalidated if price breaks below key support
            key_support = min(self.battle_lines['pdl'], self.battle_lines['overnight_low'])
            return spy_price < key_support
        elif 'PUT' in signal_type.upper():
            # Bearish signals invalidated if price breaks above key resistance
            key_resistance = max(self.battle_lines['pdh'], self.battle_lines['overnight_high'])
            return spy_price > key_resistance
        
        return False