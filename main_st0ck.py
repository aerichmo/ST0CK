"""
ST0CK Enhanced Main Entry Point
Leverages Alpaca's gamma scalping infrastructure for ST0CK strategies
"""

import asyncio
import logging
import config
import os
import sys

# Add parent directory to path to import ST0CK modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import gamma scalping components
from market.state import MarketDataManager
from engine.delta_engine import DeltaEngine
from portfolio.position_manager import PositionManager

# Import strategy based on configuration
if config.STRATEGY_MODE in ["st0cka", "st0ckg", "hybrid"]:
    from strategy.st0ck_strategy import ST0CKEnhancedStrategy as TradingStrategy
else:
    from strategy.hedging_strategy import TradingStrategy

# Optionally import ST0CK components for hybrid mode
try:
    from src.unified_database import UnifiedDatabaseManager
    from src.unified_market_data import UnifiedMarketData
    from src.unified_risk_manager import UnifiedRiskManager
    ST0CK_AVAILABLE = True
except ImportError:
    logger.warning("ST0CK modules not available, running in standalone mode")
    ST0CK_AVAILABLE = False

# Strategy initialization based on mode
if config.STRATEGY_MODE == "st0cka":
    from strategy.options_strategy import open_initial_position_stocks as open_initial_position
elif config.STRATEGY_MODE == "gamma_scalping":
    from strategy.options_strategy import open_initial_straddle as open_initial_position
else:
    # For ST0CKG and hybrid, we'll create a custom initializer
    async def open_initial_position(position_manager):
        """Initialize position for ST0CK strategies"""
        logger.info(f"Initializing {config.STRATEGY_MODE} strategy")
        # For stock-based strategies, we don't need an initial position
        # For options-based ST0CKG, we would set up initial options here
        if config.STRATEGY_MODE == "st0ckg" and config.ST0CKG_CONFIG.get("use_options"):
            # Would initialize options position here
            pass
        return True

# Set up logging
logging.basicConfig(level=config.LOG_LEVEL, format=config.LOG_FORMAT)
logger = logging.getLogger(__name__)

# SSL configuration
try:
    import certifi
    os.environ['SSL_CERT_FILE'] = certifi.where()
    os.environ['SSL_CERT_DIR'] = ''
except ImportError:
    pass


class ST0CKMarketDataManager(MarketDataManager):
    """Extended market data manager with ST0CK-specific features"""
    
    def __init__(self, trigger_queue, call_option_symbol=None, put_option_symbol=None):
        # For stock-only strategies, we don't need option symbols
        if config.STRATEGY_MODE == "st0cka":
            call_option_symbol = None
            put_option_symbol = None
        
        super().__init__(trigger_queue, call_option_symbol, put_option_symbol)
        
        # Additional ST0CK data tracking
        self.vwap_tracker = {}
        self.volume_tracker = {}
        self.volatility_tracker = None
        
        if config.STRATEGY_MODE in ["st0cka", "st0ckg", "hybrid"]:
            from strategy.st0ck_strategy import VolatilityTracker
            self.volatility_tracker = VolatilityTracker()
    
    async def _on_quote_update(self, quote):
        """Override to add ST0CK-specific data"""
        await super()._on_quote_update(quote)
        
        # Track additional metrics for ST0CK
        if hasattr(quote, 'symbol') and quote.symbol == config.HEDGING_ASSET:
            # Update volatility
            if self.volatility_tracker:
                volatility = self.volatility_tracker.update(float(quote.ask_price))
                
                # Add to market state
                if hasattr(self, 'market_state'):
                    self.market_state['volatility'] = volatility
    
    def get_enhanced_market_state(self):
        """Get market state with ST0CK enhancements"""
        state = self.get_market_state()
        
        # Add ST0CK-specific data
        state['vwap'] = self.vwap_tracker.get(config.HEDGING_ASSET, state.get('underlying_price'))
        state['volume'] = self.volume_tracker.get(config.HEDGING_ASSET, 0)
        
        if self.volatility_tracker:
            state['volatility'] = self.volatility_tracker.last_volatility
        
        return state


class ST0CKDeltaEngine(DeltaEngine):
    """Extended delta engine with ST0CK features"""
    
    async def run(self):
        """Modified run loop for ST0CK strategies"""
        if config.STRATEGY_MODE in ["st0cka", "st0ckg"]:
            # For non-options strategies, we pass market data directly
            await self._run_market_data_passthrough()
        else:
            # Use original delta calculation for gamma scalping
            await super().run()
    
    async def _run_market_data_passthrough(self):
        """Pass market data directly to strategy without delta calculation"""
        logger.info("Starting market data passthrough mode")
        
        while not self.shutdown_event.is_set():
            try:
                # Wait for market data trigger
                trigger = await self.trigger_queue.get()
                
                # Get enhanced market state
                if isinstance(self.market_manager, ST0CKMarketDataManager):
                    market_state = self.market_manager.get_enhanced_market_state()
                else:
                    market_state = self.market_manager.get_market_state()
                
                # For ST0CK strategies, we don't calculate Greeks
                # Just pass the market data with a dummy delta
                market_state['portfolio_delta'] = 0.0
                
                # Send to strategy
                try:
                    self.delta_queue.put_nowait(market_state)
                except asyncio.QueueFull:
                    # Replace stale data
                    try:
                        self.delta_queue.get_nowait()
                        self.delta_queue.put_nowait(market_state)
                    except asyncio.QueueEmpty:
                        pass
                
            except Exception as e:
                logger.error(f"Error in market data passthrough: {e}", exc_info=True)


async def initialize_st0ck_components():
    """Initialize ST0CK-specific components if available"""
    components = {}
    
    if ST0CK_AVAILABLE and config.DASHBOARD_ENABLED:
        try:
            # Initialize database
            db_manager = UnifiedDatabaseManager(
                config.DATABASE_URL,
                bot_id=f"gamma_scalping_{config.STRATEGY_MODE}"
            )
            components['db'] = db_manager
            
            # Initialize risk manager
            risk_manager = UnifiedRiskManager(
                db_manager,
                max_daily_loss=config.RISK_MANAGEMENT['max_daily_loss']
            )
            components['risk'] = risk_manager
            
            logger.info("ST0CK components initialized successfully")
        except Exception as e:
            logger.warning(f"Failed to initialize ST0CK components: {e}")
    
    return components


async def main():
    """
    Main orchestration function for ST0CK Enhanced trading
    """
    logger.info(f"Starting ST0CK Enhanced in {config.STRATEGY_MODE} mode")
    
    # Initialize ST0CK components if available
    st0ck_components = await initialize_st0ck_components()
    
    # Create shutdown event
    shutdown_event = asyncio.Event()
    
    # Create communication queues
    trade_action_queue = asyncio.Queue(maxsize=1)
    trigger_queue = asyncio.Queue(maxsize=1)
    delta_queue = asyncio.Queue(maxsize=1)
    
    # Get API credentials
    api_key, api_secret = config.get_api_credentials()
    
    # Initialize position manager with ST0CK credentials
    position_manager = PositionManager(trade_action_queue, shutdown_event)
    # Override API credentials
    position_manager.api_key = api_key
    position_manager.api_secret = api_secret
    
    # Initialize position based on mode
    await position_manager.initialize_position()
    await asyncio.sleep(5)
    
    # Start fill listener
    fill_listener_task = asyncio.create_task(position_manager.fill_listener_loop())
    await asyncio.sleep(5)
    
    # Initialize based on strategy mode
    if config.INITIALIZATION_MODE == 'init' and config.STRATEGY_MODE != "st0cka":
        success = await open_initial_position(position_manager)
        if not success and config.STRATEGY_MODE == "gamma_scalping":
            logger.critical("Failed to initialize position. Exiting.")
            fill_listener_task.cancel()
            return
    
    # For ST0CKA, we don't need initial options
    if config.STRATEGY_MODE == "st0cka":
        position_manager.call_option_symbol = None
        position_manager.put_option_symbol = None
    
    logger.info("Initializing application components...")
    
    # Initialize market data manager
    market_manager = ST0CKMarketDataManager(
        trigger_queue,
        position_manager.call_option_symbol,
        position_manager.put_option_symbol
    )
    
    # Initialize delta engine (or passthrough for ST0CK)
    delta_engine = ST0CKDeltaEngine(
        market_manager, 
        trigger_queue, 
        delta_queue, 
        shutdown_event
    )
    
    # Initialize trading strategy
    trading_strategy = TradingStrategy(
        position_manager, 
        delta_queue, 
        trade_action_queue, 
        shutdown_event
    )
    
    # Inject ST0CK components if available
    if st0ck_components:
        if hasattr(trading_strategy, 'db_manager'):
            trading_strategy.db_manager = st0ck_components.get('db')
        if hasattr(trading_strategy, 'risk_manager'):
            trading_strategy.risk_manager = st0ck_components.get('risk')
    
    # Create tasks
    tasks = [
        market_manager.run(),
        position_manager.trade_executor_loop(),
        delta_engine.run(),
        trading_strategy.run(),
        fill_listener_task
    ]
    
    # Add performance monitoring if ST0CK components available
    if st0ck_components and config.PERFORMANCE_CONFIG['track_metrics']:
        async def performance_monitor():
            """Monitor and log performance metrics"""
            while not shutdown_event.is_set():
                try:
                    await asyncio.sleep(config.PERFORMANCE_CONFIG['metrics_interval_seconds'])
                    
                    # Log current metrics
                    if hasattr(trading_strategy, 'daily_pnl'):
                        logger.info(f"Performance update - Daily P&L: ${trading_strategy.daily_pnl:.2f}, "
                                  f"Positions today: {trading_strategy.positions_today}")
                except Exception as e:
                    logger.error(f"Error in performance monitor: {e}")
        
        tasks.append(performance_monitor())
    
    logger.info("Application starting. Press Ctrl+C to shut down gracefully.")
    
    # Run until interrupted
    try:
        await asyncio.gather(*tasks)
    except KeyboardInterrupt:
        logger.info("Shutdown signal received. Cleaning up...")
        shutdown_event.set()
        await asyncio.gather(*tasks, return_exceptions=True)
        
        # Close ST0CK components
        if st0ck_components:
            if 'db' in st0ck_components:
                st0ck_components['db'].close()
    
    logger.info("Application has shut down.")


if __name__ == "__main__":
    # Check for required configuration
    api_key, api_secret = config.get_api_credentials()
    if not api_key or not api_secret:
        logger.error("API credentials not found. Please check your .env file.")
        sys.exit(1)
    
    # Run the main async function
    asyncio.run(main())