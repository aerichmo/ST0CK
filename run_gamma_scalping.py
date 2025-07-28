#!/usr/bin/env python3
"""
Run ST0CKA with true gamma scalping using Alpaca's infrastructure
This properly integrates the gamma-scalping-fork components
"""
import os
import sys
import asyncio
import signal
from datetime import datetime
import logging

# Add gamma-scalping-fork to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'gamma-scalping-fork'))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import gamma scalping components
try:
    from main import main as gamma_main
    from main import parse_args
    import config
    
    # Import ST0CK components for integration
    from src.unified_database import UnifiedDatabaseManager
    from src.unified_logging import get_logger
    
except ImportError as e:
    logger.error(f"Failed to import required modules: {e}")
    logger.error("Make sure you have both ST0CK and gamma-scalping-fork properly installed")
    sys.exit(1)


class ST0CKGammaIntegration:
    """
    Integrates ST0CK infrastructure with Alpaca's gamma scalping
    """
    
    def __init__(self):
        self.logger = get_logger(__name__)
        self.db_manager = None
        self.shutdown_event = asyncio.Event()
        
    async def initialize(self):
        """Initialize ST0CK components for gamma scalping"""
        # Initialize database
        database_url = os.getenv('DATABASE_URL')
        if database_url:
            self.db_manager = UnifiedDatabaseManager(database_url)
            await self.db_manager.initialize()
            self.logger.info("Database initialized for gamma scalping")
        
        # Override gamma config with ST0CK settings
        self._configure_gamma_settings()
        
    def _configure_gamma_settings(self):
        """Configure gamma scalping with ST0CK preferences"""
        # Use ST0CK API credentials
        config.TRADING_API_KEY = os.getenv('ST0CKAKEY', config.TRADING_API_KEY)
        config.TRADING_API_SECRET = os.getenv('ST0CKASECRET', config.TRADING_API_SECRET)
        
        # Adjust for ST0CK risk preferences
        config.HEDGING_DELTA_THRESHOLD = 5.0  # More aggressive hedging
        config.STRATEGY_MULTIPLIER = 2  # Trade 2x size
        
        # Use shorter expiration for more gamma
        config.MIN_DAYS_TO_EXPIRATION = 0  # Allow 0DTE
        config.MAX_DAYS_TO_EXPIRATION = 7  # Max 1 week
        
        # Tighter heartbeat for scalping
        config.HEARTBEAT_TRIGGER_SECONDS = 1.0
        config.PRICE_CHANGE_THRESHOLD = 0.01  # $0.01 moves trigger updates
        
        self.logger.info("Configured gamma scalping for ST0CK preferences")
        
    async def run_with_monitoring(self):
        """Run gamma scalping with ST0CK monitoring"""
        try:
            # Parse command line args for gamma scalping
            args = parse_args()
            
            # Add ST0CK specific args
            args.symbol = 'SPY'  # Always trade SPY
            args.track_opts = True  # Enable options tracking
            
            # Create tasks for both gamma scalping and monitoring
            tasks = []
            
            # Main gamma scalping task
            gamma_task = asyncio.create_task(gamma_main(args))
            tasks.append(gamma_task)
            
            # ST0CK monitoring task
            if self.db_manager:
                monitor_task = asyncio.create_task(self._monitor_performance())
                tasks.append(monitor_task)
            
            # Wait for shutdown or task completion
            done, pending = await asyncio.wait(
                tasks,
                return_when=asyncio.FIRST_COMPLETED
            )
            
            # Cancel remaining tasks
            for task in pending:
                task.cancel()
                
        except Exception as e:
            self.logger.error(f"Error running gamma scalping: {e}", exc_info=True)
            raise
            
    async def _monitor_performance(self):
        """Monitor gamma scalping performance"""
        while not self.shutdown_event.is_set():
            try:
                # Log performance metrics every 60 seconds
                await asyncio.sleep(60)
                
                # Would integrate with position manager to get metrics
                self.logger.info("Gamma scalping performance check")
                
            except Exception as e:
                self.logger.error(f"Error in monitoring: {e}")
                
    def handle_shutdown(self, signum, frame):
        """Handle shutdown signals"""
        self.logger.info(f"Received signal {signum}, shutting down...")
        self.shutdown_event.set()
        

async def main():
    """Main entry point"""
    integration = ST0CKGammaIntegration()
    
    # Setup signal handlers
    signal.signal(signal.SIGINT, integration.handle_shutdown)
    signal.signal(signal.SIGTERM, integration.handle_shutdown)
    
    try:
        # Initialize
        await integration.initialize()
        
        # Run gamma scalping
        logger.info("Starting ST0CK Gamma Scalping Integration")
        logger.info("This will trade SPY options using Alpaca's gamma scalping strategy")
        logger.info("Press Ctrl+C to stop")
        
        await integration.run_with_monitoring()
        
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
    finally:
        if integration.db_manager:
            await integration.db_manager.close()
        logger.info("Shutdown complete")


if __name__ == '__main__':
    # Make script executable
    os.chmod(__file__, 0o755)
    
    # Run async main
    asyncio.run(main())