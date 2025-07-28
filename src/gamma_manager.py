"""
Gamma Scalping Manager for ST0CK
Integrates Alpaca's gamma scalping with ST0CK infrastructure
"""
import asyncio
import sys
import os
from datetime import datetime
from typing import Dict, List, Optional, Any
import signal

# Add gamma-scalping-fork to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../gamma-scalping-fork'))

# Import gamma scalping components with ST0CK config
os.environ['GAMMA_CONFIG'] = 'config_st0ck'
import config_st0ck as config

from market.state import MarketDataManager
from engine.delta_engine import DeltaEngine
from portfolio.position_manager import PositionManager
from strategy.hedging_strategy import TradingStrategy
from strategy.options_strategy import open_initial_straddle

from .unified_logging import get_logger
from .unified_database import UnifiedDatabaseManager
from .options_broker import OptionsBroker
from .unified_cache import UnifiedCacheManager


class GammaScalpingManager:
    """
    Manages gamma scalping strategy execution
    Bridges between Alpaca's implementation and ST0CK
    """
    
    def __init__(self, bot_id: str = "st0cka_gamma"):
        self.bot_id = bot_id
        self.logger = get_logger(__name__)
        
        # Import optimal hours configuration
        try:
            from ..config.gamma_scalping_hours import (
                get_optimal_sessions,
                get_current_volatility_multiplier,
                should_trade_gamma,
                GAMMA_SCALPING_SESSIONS,
                ORDER_CUTOFFS
            )
            self.get_optimal_sessions = get_optimal_sessions
            self.get_volatility_multiplier = get_current_volatility_multiplier
            self.should_trade_gamma = should_trade_gamma
            self.gamma_sessions = GAMMA_SCALPING_SESSIONS
            self.order_cutoffs = ORDER_CUTOFFS
        except ImportError:
            self.logger.warning("Gamma scalping hours config not found, using defaults")
            self.get_optimal_sessions = lambda x: []
            self.get_volatility_multiplier = lambda x: 1.0
            self.should_trade_gamma = lambda x, y: True
            self.gamma_sessions = {}
            self.order_cutoffs = {}
        
        # ST0CK components
        self.db_manager = None
        self.cache_manager = None
        self.options_broker = None
        
        # Gamma scalping components
        self.position_manager = None
        self.market_data_manager = None
        self.delta_engine = None
        self.trading_strategy = None
        
        # Async queues for communication
        self.trade_action_queue = asyncio.Queue(maxsize=1)
        self.trigger_queue = asyncio.Queue(maxsize=1)
        self.delta_queue = asyncio.Queue(maxsize=1)
        
        # Control
        self.shutdown_event = asyncio.Event()
        self.tasks = []
        
        # Performance tracking
        self.start_time = datetime.now()
        self.total_trades = 0
        self.total_pnl = 0.0
        
        # Current session tracking
        self.current_session = None
        self.session_stats = {}
        
    async def initialize(self):
        """Initialize all components"""
        self.logger.info(f"Initializing Gamma Scalping Manager for {self.bot_id}")
        
        try:
            # Initialize ST0CK components
            await self._init_st0ck_components()
            
            # Initialize gamma scalping components
            await self._init_gamma_components()
            
            # Perform initialization based on mode
            if config.INITIALIZATION_MODE == 'init':
                await self._init_mode_setup()
            else:
                await self._resume_mode_setup()
            
            self.logger.info("Gamma Scalping Manager initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize: {e}", exc_info=True)
            raise
    
    async def _init_st0ck_components(self):
        """Initialize ST0CK infrastructure"""
        # Database
        if config.DATABASE_URL:
            self.db_manager = UnifiedDatabaseManager(config.DATABASE_URL)
            await self.db_manager.initialize()
        
        # Cache
        redis_url = os.getenv('REDIS_URL')
        self.cache_manager = UnifiedCacheManager(self.bot_id, redis_url)
        
        # Options broker
        self.options_broker = OptionsBroker(
            api_key=config.TRADING_API_KEY,
            api_secret=config.TRADING_API_SECRET,
            paper=config.IS_PAPER_TRADING,
            bot_id=self.bot_id
        )
        
    async def _init_gamma_components(self):
        """Initialize gamma scalping components"""
        # Position Manager with ST0CK's broker
        self.position_manager = PositionManager(self.shutdown_event)
        # Override with our options broker
        self.position_manager.broker = self.options_broker
        
        # Market Data Manager
        self.market_data_manager = MarketDataManager(
            self.trigger_queue,
            self.shutdown_event
        )
        
        # Delta Engine
        self.delta_engine = DeltaEngine(
            self.trigger_queue,
            self.delta_queue,
            self.shutdown_event,
            track_options=True  # Always track options for gamma scalping
        )
        
        # Trading Strategy
        self.trading_strategy = TradingStrategy(
            self.position_manager,
            self.delta_queue,
            self.trade_action_queue,
            self.shutdown_event
        )
    
    async def _init_mode_setup(self):
        """Setup for init mode - start fresh"""
        self.logger.info("Starting in INIT mode - closing existing positions")
        
        # Close all existing positions
        await self.position_manager.initialize()
        
        # Open initial straddle
        await self._open_initial_straddle()
        
    async def _resume_mode_setup(self):
        """Setup for resume mode - continue with existing positions"""
        self.logger.info("Starting in RESUME mode - keeping existing positions")
        
        # Just initialize position manager
        await self.position_manager.initialize()
        
        # Log current positions
        positions = self.options_broker.get_option_positions()
        if positions:
            self.logger.info(f"Found {len(positions)} existing option positions")
        else:
            self.logger.warning("No existing positions found - opening initial straddle")
            await self._open_initial_straddle()
    
    async def _open_initial_straddle(self):
        """Open the initial straddle position"""
        try:
            # Find best straddle
            straddle = await self.options_broker.find_atm_straddle(
                symbol=config.HEDGING_ASSET,
                target_dte=config.MIN_DAYS_TO_EXPIRATION
            )
            
            if not straddle:
                raise ValueError("Could not find suitable straddle")
            
            # Calculate position size
            account = self.options_broker.get_account()
            buying_power = float(account.buying_power)
            
            # Use 10% of buying power for initial straddle
            position_value = min(buying_power * 0.10, config.MAX_POSITION_VALUE)
            contracts = int(position_value / (straddle['total_cost'] * 100))
            contracts = max(1, min(contracts, config.MAX_CONTRACTS))
            
            self.logger.info(
                f"Opening initial straddle: {contracts} contracts at "
                f"${straddle['strike']} strike, cost ${straddle['total_cost']:.2f}"
            )
            
            # Place straddle orders
            call_id, put_id = await self.options_broker.place_straddle_order(
                straddle, contracts
            )
            
            if call_id and put_id:
                self.logger.info("Initial straddle opened successfully")
                
                # Log to database
                if self.db_manager:
                    await self._log_trade({
                        'type': 'open_straddle',
                        'strike': straddle['strike'],
                        'contracts': contracts,
                        'cost': straddle['total_cost'] * contracts * 100,
                        'call_order': call_id,
                        'put_order': put_id
                    })
            else:
                raise ValueError("Failed to open initial straddle")
                
        except Exception as e:
            self.logger.error(f"Failed to open initial straddle: {e}")
            raise
    
    async def run(self):
        """Run the gamma scalping strategy"""
        self.logger.info("Starting gamma scalping strategy")
        
        try:
            # Create tasks for each component
            self.tasks = [
                asyncio.create_task(
                    self.market_data_manager.start_market_data_streaming(),
                    name="market_data"
                ),
                asyncio.create_task(
                    self.delta_engine.run(),
                    name="delta_engine"
                ),
                asyncio.create_task(
                    self.trading_strategy.run(),
                    name="trading_strategy"
                ),
                asyncio.create_task(
                    self.position_manager.start_order_management(),
                    name="position_manager"
                ),
                asyncio.create_task(
                    self._monitor_performance(),
                    name="performance_monitor"
                ),
                asyncio.create_task(
                    self._process_trade_actions(),
                    name="trade_processor"
                )
            ]
            
            # Wait for shutdown
            await self.shutdown_event.wait()
            
        except Exception as e:
            self.logger.error(f"Error in gamma scalping: {e}", exc_info=True)
            raise
        finally:
            await self.cleanup()
    
    async def _process_trade_actions(self):
        """Process trade actions from the strategy"""
        while not self.shutdown_event.is_set():
            try:
                # Get trade command with timeout
                trade_command = await asyncio.wait_for(
                    self.trade_action_queue.get(),
                    timeout=1.0
                )
                
                # Execute trade
                await self._execute_trade(trade_command)
                
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                self.logger.error(f"Error processing trade action: {e}")
    
    async def _execute_trade(self, trade_command):
        """Execute a trade command"""
        try:
            symbol = trade_command.symbol
            quantity = abs(trade_command.quantity)
            side = 'buy' if trade_command.quantity > 0 else 'sell'
            
            # Place order through options broker
            order = await self.options_broker.place_stock_order(
                symbol=symbol,
                quantity=quantity,
                side=side
            )
            
            if order:
                self.total_trades += 1
                self.logger.info(
                    f"Executed hedge trade: {side} {quantity} {symbol} "
                    f"(Total trades: {self.total_trades})"
                )
                
                # Log to database
                if self.db_manager:
                    await self._log_trade({
                        'type': 'hedge',
                        'symbol': symbol,
                        'quantity': quantity,
                        'side': side,
                        'order_id': order.id
                    })
                    
        except Exception as e:
            self.logger.error(f"Failed to execute trade: {e}")
    
    async def _monitor_performance(self):
        """Monitor and log performance metrics"""
        while not self.shutdown_event.is_set():
            try:
                await asyncio.sleep(config.MONITOR_INTERVAL)
                
                # Get current positions
                option_positions = self.options_broker.get_option_positions()
                stock_positions = self.options_broker.get_positions()
                
                # Calculate P&L
                straddle_pnl = self.options_broker.calculate_straddle_pnl(option_positions)
                stock_pnl = sum(p.get('unrealized_pnl', 0) for p in stock_positions.values())
                
                total_pnl = sum(s['pnl'] for s in straddle_pnl.values()) + stock_pnl
                
                # Log metrics
                runtime = (datetime.now() - self.start_time).total_seconds() / 3600
                self.logger.info(
                    f"Performance Update - Runtime: {runtime:.1f}h, "
                    f"Trades: {self.total_trades}, "
                    f"Options P&L: ${sum(s['pnl'] for s in straddle_pnl.values()):.2f}, "
                    f"Stock P&L: ${stock_pnl:.2f}, "
                    f"Total P&L: ${total_pnl:.2f}"
                )
                
                # Check risk limits
                if total_pnl < -config.MAX_DAILY_LOSS:
                    self.logger.error(f"Daily loss limit reached: ${total_pnl:.2f}")
                    self.shutdown_event.set()
                
                # Alert on large losses
                if config.ALERT_ON_LARGE_LOSS:
                    for straddle_id, metrics in straddle_pnl.items():
                        if metrics['pnl'] < -100:
                            self.logger.warning(
                                f"Large loss on straddle {straddle_id}: "
                                f"${metrics['pnl']:.2f}"
                            )
                
            except Exception as e:
                self.logger.error(f"Error in performance monitoring: {e}")
    
    async def _log_trade(self, trade_data: Dict[str, Any]):
        """Log trade to database"""
        if not self.db_manager:
            return
            
        try:
            trade_data.update({
                'bot_id': self.bot_id,
                'timestamp': datetime.now(),
                'strategy': 'gamma_scalping'
            })
            
            await self.db_manager.log_trade(trade_data)
            
        except Exception as e:
            self.logger.error(f"Failed to log trade: {e}")
    
    async def cleanup(self):
        """Clean up resources"""
        self.logger.info("Cleaning up gamma scalping manager")
        
        # Cancel all tasks
        for task in self.tasks:
            if not task.done():
                task.cancel()
        
        # Wait for tasks to complete
        if self.tasks:
            await asyncio.gather(*self.tasks, return_exceptions=True)
        
        # Close connections
        if self.db_manager:
            await self.db_manager.close()
        
        self.logger.info("Cleanup complete")
    
    def handle_shutdown(self, signum, frame):
        """Handle shutdown signals"""
        self.logger.info(f"Received signal {signum}, initiating shutdown...")
        self.shutdown_event.set()


async def run_gamma_scalping():
    """Main entry point for gamma scalping"""
    manager = GammaScalpingManager()
    
    # Setup signal handlers
    signal.signal(signal.SIGINT, manager.handle_shutdown)
    signal.signal(signal.SIGTERM, manager.handle_shutdown)
    
    try:
        # Initialize
        await manager.initialize()
        
        # Run strategy
        await manager.run()
        
    except Exception as e:
        logger = get_logger(__name__)
        logger.error(f"Fatal error in gamma scalping: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    asyncio.run(run_gamma_scalping())