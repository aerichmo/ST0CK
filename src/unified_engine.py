"""
Unified trading engine that supports multiple strategies
Preserves core ST0CKA and ST0CKG strategies while eliminating duplication
"""
import asyncio
import time
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
import pytz

from .unified_logging import get_logger, LogContext, log_performance
from .unified_database import UnifiedDatabaseManager
from .unified_cache import UnifiedCache, CacheKeyBuilder
from .unified_market_data import UnifiedMarketData
from .alpaca_broker import AlpacaBroker
from .unified_risk_manager import UnifiedRiskManager
from .error_reporter import ErrorReporter

@dataclass
class Position:
    """Unified position tracking with strategy-specific metadata"""
    id: str
    symbol: str
    entry_price: float
    entry_time: datetime
    quantity: int
    side: str  # 'long' or 'short'
    strategy_data: Dict[str, Any] = field(default_factory=dict)
    
    # Common fields
    current_price: Optional[float] = None
    unrealized_pnl: Optional[float] = None
    unrealized_pnl_pct: Optional[float] = None
    
    # Order tracking
    order_id: Optional[str] = None
    stop_order_id: Optional[str] = None
    target_order_id: Optional[str] = None
    
    def update_price(self, price: float):
        """Update current price and P&L calculations"""
        self.current_price = price
        if self.side == 'long':
            self.unrealized_pnl = (price - self.entry_price) * self.quantity
        else:
            self.unrealized_pnl = (self.entry_price - price) * self.quantity
        
        self.unrealized_pnl_pct = (self.unrealized_pnl / (self.entry_price * self.quantity)) * 100

class TradingStrategy(ABC):
    """Abstract base for trading strategies"""
    
    @abstractmethod
    def get_config(self) -> Dict[str, Any]:
        """Get strategy configuration"""
        pass
    
    @abstractmethod
    def check_entry_conditions(self, market_data: Dict[str, Any], positions: Dict[str, Position]) -> Optional[Dict[str, Any]]:
        """Check if entry conditions are met, return signal data if yes"""
        pass
    
    @abstractmethod
    def get_position_size(self, signal: Dict[str, Any], account_value: float) -> int:
        """Calculate position size based on signal and account"""
        pass
    
    @abstractmethod
    def get_entry_order_params(self, signal: Dict[str, Any]) -> Dict[str, Any]:
        """Get parameters for entry order"""
        pass
    
    @abstractmethod
    def check_exit_conditions(self, position: Position, market_data: Dict[str, Any]) -> Optional[str]:
        """Check if exit conditions are met, return exit reason if yes"""
        pass
    
    @abstractmethod
    def get_exit_order_params(self, position: Position, exit_reason: str) -> Dict[str, Any]:
        """Get parameters for exit order"""
        pass

class UnifiedTradingEngine:
    """
    Unified engine that handles all common functionality
    Delegates strategy-specific logic to strategy implementations
    """
    
    def __init__(self, 
                 bot_id: str,
                 strategy: TradingStrategy,
                 api_key: str,
                 api_secret: str,
                 database_url: Optional[str] = None,
                 redis_url: Optional[str] = None,
                 paper_trading: bool = True):
        """
        Initialize unified trading engine
        
        Args:
            bot_id: Unique bot identifier
            strategy: Trading strategy implementation
            api_key: Alpaca API key
            api_secret: Alpaca API secret
            database_url: Database connection URL
            redis_url: Redis connection URL
            paper_trading: Use paper trading account
        """
        self.bot_id = bot_id
        self.strategy = strategy
        self.logger = get_logger(__name__, bot_id)
        
        # Initialize components
        self.db = UnifiedDatabaseManager(database_url, bot_id)
        self.cache = UnifiedCache(redis_url, bot_id)
        self.broker = AlpacaBroker(api_key, api_secret, paper=paper_trading)
        self.market_data = UnifiedMarketData(self.broker, cache=self.cache)
        self.risk_manager = UnifiedRiskManager(self.db, self.broker)
        
        # Position tracking
        self.positions: Dict[str, Position] = {}
        
        # State tracking
        self.running = False
        self.shutdown_requested = False
        self.daily_metrics = {
            'trades': 0,
            'pnl': 0.0,
            'consecutive_losses': 0,
            'max_trades': 10,
            'max_loss': -500.0
        }
        
        # Strategy configuration
        self.config = self.strategy.get_config()
        
        # Market timing
        self.eastern = pytz.timezone('US/Eastern')
        
        self.logger.info(f"[{bot_id}] Unified engine initialized with strategy: {strategy.__class__.__name__}")
    
    async def initialize(self):
        """Initialize all components"""
        try:
            # Connect to broker
            self.broker.connect()
            
            # Initialize market data
            await self.market_data.initialize()
            
            # Register bot in database
            self.db.register_bot(self.bot_id, self.config)
            
            # Load daily metrics
            self._load_daily_metrics()
            
            self.logger.info(f"[{self.bot_id}] Engine initialization complete")
            
        except Exception as e:
            self.logger.error(f"[{self.bot_id}] Failed to initialize engine: {e}", exc_info=True)
            raise
    
    def _load_daily_metrics(self):
        """Load today's trading metrics from database"""
        today_trades = self.db.get_trades(self.bot_id, limit=50)
        today_start = datetime.now(self.eastern).replace(hour=0, minute=0, second=0, microsecond=0)
        
        daily_trades = [t for t in today_trades if t.entry_time >= today_start]
        
        self.daily_metrics['trades'] = len(daily_trades)
        self.daily_metrics['pnl'] = sum(t.pnl or 0 for t in daily_trades)
        
        # Count consecutive losses
        consecutive_losses = 0
        for trade in reversed(daily_trades):
            if trade.pnl and trade.pnl < 0:
                consecutive_losses += 1
            else:
                break
        
        self.daily_metrics['consecutive_losses'] = consecutive_losses
    
    async def run(self):
        """Main trading loop"""
        self.running = True
        self.logger.info(f"[{self.bot_id}] Starting trading engine")
        
        try:
            while self.running and not self.shutdown_requested:
                try:
                    # Check market hours
                    if not self._is_market_open():
                        await asyncio.sleep(60)
                        continue
                    
                    # Check risk limits
                    if not self._check_risk_limits():
                        self.logger.warning(f"[{self.bot_id}] Risk limits exceeded, halting trading")
                        await asyncio.sleep(300)  # Wait 5 minutes
                        continue
                    
                    # Run trading cycle
                    await self._run_trading_cycle()
                    
                    # Sleep between cycles
                    await asyncio.sleep(self.config.get('cycle_delay', 5))
                    
                except Exception as e:
                    self.logger.error(f"[{self.bot_id}] Error in trading loop: {e}", exc_info=True)
                    ErrorReporter.report_failure(self.bot_id, e, {'positions': self.positions})
                    await asyncio.sleep(30)  # Wait before retrying
            
        except KeyboardInterrupt:
            self.logger.info(f"[{self.bot_id}] Received shutdown signal")
        finally:
            await self.shutdown()
    
    async def _run_trading_cycle(self):
        """Run one trading cycle"""
        with LogContext(self.logger, bot_id=self.bot_id, cycle_start=datetime.now()):
            # Update positions
            await self._update_positions()
            
            # Check exits first (priority over entries)
            await self._check_exits()
            
            # Check entries if within trading window
            if self._in_trading_window():
                await self._check_entries()
            
            # Monitor open positions
            await self._monitor_positions()
    
    async def _update_positions(self):
        """Update position data with latest prices"""
        if not self.positions:
            return
        
        # Get current prices for all positions
        symbols = list(set(p.symbol for p in self.positions.values()))
        
        for symbol in symbols:
            try:
                quote = await self.market_data.get_quote(symbol)
                if quote:
                    # Update all positions for this symbol
                    for position in self.positions.values():
                        if position.symbol == symbol:
                            position.update_price(quote['price'])
                            
            except Exception as e:
                self.logger.error(f"[{self.bot_id}] Failed to update price for {symbol}: {e}")
    
    async def _check_entries(self):
        """Check for entry opportunities"""
        # Get market data
        market_data = await self._get_market_snapshot()
        
        # Let strategy check entry conditions
        signal = self.strategy.check_entry_conditions(market_data, self.positions)
        
        if signal:
            await self._process_entry_signal(signal)
    
    async def _check_exits(self):
        """Check exit conditions for all positions"""
        market_data = await self._get_market_snapshot()
        
        for position_id, position in list(self.positions.items()):
            try:
                # Let strategy check exit conditions
                exit_reason = self.strategy.check_exit_conditions(position, market_data)
                
                if exit_reason:
                    await self._exit_position(position, exit_reason)
                    
            except Exception as e:
                self.logger.error(f"[{self.bot_id}] Error checking exit for {position_id}: {e}")
    
    async def _monitor_positions(self):
        """Monitor and update position orders"""
        # This is a hook for strategies that need continuous position monitoring
        # The default implementation just logs position status
        if self.positions:
            total_pnl = sum(p.unrealized_pnl or 0 for p in self.positions.values())
            self.logger.info(f"[{self.bot_id}] Open positions: {len(self.positions)}, Total P&L: ${total_pnl:.2f}")
    
    async def _process_entry_signal(self, signal: Dict[str, Any]):
        """Process entry signal from strategy"""
        try:
            # Get account value for position sizing
            account = await self.broker.get_account()
            account_value = float(account.equity)
            
            # Get position size from strategy
            position_size = self.strategy.get_position_size(signal, account_value)
            
            if position_size <= 0:
                self.logger.warning(f"[{self.bot_id}] Invalid position size: {position_size}")
                return
            
            # Get order parameters from strategy
            order_params = self.strategy.get_entry_order_params(signal)
            
            # Place order
            order = await self.broker.place_order(
                symbol=order_params['symbol'],
                qty=position_size,
                side=order_params['side'],
                order_type=order_params['order_type'],
                time_in_force=order_params.get('time_in_force', 'day'),
                limit_price=order_params.get('limit_price'),
                stop_price=order_params.get('stop_price')
            )
            
            if order:
                # Create position entry
                position = Position(
                    id=order.id,
                    symbol=order_params['symbol'],
                    entry_price=order_params.get('limit_price') or signal.get('price'),
                    entry_time=datetime.now(self.eastern),
                    quantity=position_size,
                    side=order_params['side'],
                    strategy_data=signal,
                    order_id=order.id
                )
                
                self.positions[order.id] = position
                
                # Log to database
                self.db.log_trade({
                    'symbol': position.symbol,
                    'action': f'BUY_{position.side.upper()}',
                    'quantity': position.quantity,
                    'entry_price': position.entry_price,
                    'entry_time': position.entry_time,
                    'strategy_details': signal
                })
                
                self.logger.info(f"[{self.bot_id}] Entered position: {position.symbol} x{position.quantity} @ ${position.entry_price}")
                
        except Exception as e:
            self.logger.error(f"[{self.bot_id}] Failed to process entry signal: {e}", exc_info=True)
            ErrorReporter.report_failure(self.bot_id, e, {'signal': signal})
    
    async def _exit_position(self, position: Position, exit_reason: str):
        """Exit a position"""
        try:
            # Get exit order parameters from strategy
            order_params = self.strategy.get_exit_order_params(position, exit_reason)
            
            # Place exit order
            order = await self.broker.place_order(
                symbol=position.symbol,
                qty=position.quantity,
                side='sell' if position.side == 'long' else 'buy',
                order_type=order_params['order_type'],
                time_in_force=order_params.get('time_in_force', 'day'),
                limit_price=order_params.get('limit_price'),
                stop_price=order_params.get('stop_price')
            )
            
            if order:
                # Wait for fill
                filled_order = await self.broker.wait_for_fill(order.id, timeout=30)
                
                if filled_order:
                    exit_price = float(filled_order.filled_avg_price)
                    exit_time = datetime.now(self.eastern)
                    
                    # Calculate P&L
                    if position.side == 'long':
                        pnl = (exit_price - position.entry_price) * position.quantity
                    else:
                        pnl = (position.entry_price - exit_price) * position.quantity
                    
                    pnl_pct = (pnl / (position.entry_price * position.quantity)) * 100
                    
                    # Update database
                    self.db.update_trade_exit(
                        position.id,
                        exit_price,
                        exit_time,
                        pnl,
                        pnl_pct
                    )
                    
                    # Update daily metrics
                    self.daily_metrics['trades'] += 1
                    self.daily_metrics['pnl'] += pnl
                    
                    if pnl < 0:
                        self.daily_metrics['consecutive_losses'] += 1
                    else:
                        self.daily_metrics['consecutive_losses'] = 0
                    
                    # Remove position
                    del self.positions[position.id]
                    
                    self.logger.info(
                        f"[{self.bot_id}] Exited position: {position.symbol} @ ${exit_price:.2f}, "
                        f"P&L: ${pnl:.2f} ({pnl_pct:.2f}%), Reason: {exit_reason}"
                    )
                    
        except Exception as e:
            self.logger.error(f"[{self.bot_id}] Failed to exit position: {e}", exc_info=True)
            ErrorReporter.report_failure(self.bot_id, e, {'position': position, 'exit_reason': exit_reason})
    
    async def _get_market_snapshot(self) -> Dict[str, Any]:
        """Get current market data snapshot"""
        # Get SPY quote (used by most strategies)
        spy_quote = await self.market_data.get_quote('SPY')
        
        # Get any additional data needed by strategies
        snapshot = {
            'timestamp': datetime.now(self.eastern),
            'spy_price': spy_quote['price'] if spy_quote else None,
            'spy_quote': spy_quote
        }
        
        # Add strategy-specific data
        if hasattr(self.strategy, 'get_required_market_data'):
            additional_data = await self.strategy.get_required_market_data(self.market_data)
            snapshot.update(additional_data)
        
        return snapshot
    
    def _is_market_open(self) -> bool:
        """Check if market is open"""
        now = datetime.now(self.eastern)
        
        # Check weekday (Monday = 0, Friday = 4)
        if now.weekday() > 4:
            return False
        
        # Market hours: 9:30 AM - 4:00 PM ET
        market_open = now.replace(hour=9, minute=30, second=0, microsecond=0)
        market_close = now.replace(hour=16, minute=0, second=0, microsecond=0)
        
        return market_open <= now <= market_close
    
    def _in_trading_window(self) -> bool:
        """Check if within strategy's trading window"""
        now = datetime.now(self.eastern)
        
        # Get trading window from strategy config
        start_time = self.config.get('trading_window_start', '09:30')
        end_time = self.config.get('trading_window_end', '15:30')
        
        # Parse times
        start_hour, start_min = map(int, start_time.split(':'))
        end_hour, end_min = map(int, end_time.split(':'))
        
        window_start = now.replace(hour=start_hour, minute=start_min, second=0, microsecond=0)
        window_end = now.replace(hour=end_hour, minute=end_min, second=0, microsecond=0)
        
        return window_start <= now <= window_end
    
    def _check_risk_limits(self) -> bool:
        """Check if risk limits are exceeded"""
        # Daily loss limit
        if self.daily_metrics['pnl'] <= self.daily_metrics['max_loss']:
            self.logger.warning(f"[{self.bot_id}] Daily loss limit reached: ${self.daily_metrics['pnl']:.2f}")
            return False
        
        # Max trades limit
        if self.daily_metrics['trades'] >= self.daily_metrics['max_trades']:
            self.logger.warning(f"[{self.bot_id}] Max trades limit reached: {self.daily_metrics['trades']}")
            return False
        
        # Consecutive losses limit
        max_consecutive_losses = self.config.get('max_consecutive_losses', 3)
        if self.daily_metrics['consecutive_losses'] >= max_consecutive_losses:
            self.logger.warning(f"[{self.bot_id}] Consecutive losses limit reached: {self.daily_metrics['consecutive_losses']}")
            return False
        
        return True
    
    async def shutdown(self):
        """Graceful shutdown"""
        self.logger.info(f"[{self.bot_id}] Shutting down engine")
        self.running = False
        
        try:
            # Close all positions
            if self.positions:
                self.logger.info(f"[{self.bot_id}] Closing {len(self.positions)} open positions")
                
                for position in list(self.positions.values()):
                    await self._exit_position(position, "shutdown")
            
            # Close connections
            self.db.close()
            self.cache.close()
            self.broker.disconnect()
            
            self.logger.info(f"[{self.bot_id}] Engine shutdown complete")
            
        except Exception as e:
            self.logger.error(f"[{self.bot_id}] Error during shutdown: {e}", exc_info=True)