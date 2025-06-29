"""
Base Trading Engine - Common functionality for all trading engines
Eliminates duplication across multiple engine implementations
"""
import logging
import os
from datetime import datetime
from typing import Optional, Dict, Any
from abc import ABC, abstractmethod
import pytz

from src.alpaca_broker import AlpacaBroker
from src.unified_market_data import UnifiedMarketData
from src.multi_bot_database import MultiBotDatabaseManager
from src.risk_manager import RiskManager

logger = logging.getLogger(__name__)


class BaseEngine(ABC):
    """Base class for all trading engines with common functionality"""
    
    def __init__(self, config: Dict[str, Any], capital: float, db_connection_string: str):
        """Initialize common components for all engines"""
        self.config = config
        self.capital = capital
        self.db_connection_string = db_connection_string
        self.bot_id = config.get('bot_id', 'unknown')
        
        # Initialize components
        self.broker = None
        self.market_data = None
        self.db = None
        self.risk_manager = None
        
        # Trading state
        self.is_running = False
        self.positions = {}
        self.daily_trades = 0
        self.daily_pnl = 0.0
        self.consecutive_losses = 0
        
        # Initialize all components
        self._initialize_components()
        
    def _initialize_components(self):
        """Initialize broker, market data, database, and risk manager"""
        try:
            # Initialize broker
            self.broker = self._create_broker()
            if not self.broker.connect():
                raise RuntimeError("Failed to connect to broker")
            
            # Initialize market data provider
            self.market_data = self._create_market_data()
            
            # Initialize database
            self.db = MultiBotDatabaseManager(
                connection_string=self.db_connection_string,
                bot_id=self.bot_id
            )
            
            # Initialize risk manager
            self.risk_manager = RiskManager(
                config=self.config,
                db_manager=self.db
            )
            
            logger.info(f"Initialized {self.__class__.__name__} for bot {self.bot_id}")
            
        except Exception as e:
            logger.error(f"Failed to initialize engine components: {e}")
            raise
    
    def _create_broker(self) -> AlpacaBroker:
        """Create broker instance from config"""
        alpaca_config = self.config.get('alpaca', {})
        return AlpacaBroker(
            api_key=alpaca_config.get('api_key'),
            secret_key=alpaca_config.get('secret_key'),
            base_url=alpaca_config.get('base_url'),
            paper=alpaca_config.get('paper', True)
        )
    
    def _create_market_data(self) -> UnifiedMarketData:
        """Create market data provider from config"""
        alpaca_config = self.config.get('alpaca', {})
        return UnifiedMarketData(
            api_key=alpaca_config.get('api_key'),
            secret_key=alpaca_config.get('secret_key'),
            feed='iex'  # or 'sip' based on subscription
        )
    
    def is_market_open(self) -> bool:
        """Check if market is currently open"""
        now = datetime.now(pytz.timezone('America/New_York'))
        
        # Check if it's a weekday
        if now.weekday() >= 5:  # Saturday = 5, Sunday = 6
            return False
        
        # Check market hours (9:30 AM - 4:00 PM ET)
        market_open = now.replace(hour=9, minute=30, second=0, microsecond=0)
        market_close = now.replace(hour=16, minute=0, second=0, microsecond=0)
        
        return market_open <= now <= market_close
    
    def is_within_trading_window(self) -> bool:
        """Check if we're within the configured trading window"""
        now = datetime.now(pytz.timezone('America/New_York'))
        
        # Get trading window from config
        window = self.config.get('trading_window', {})
        start_time = window.get('start', '09:30')
        end_time = window.get('end', '16:00')
        
        # Parse times
        start_hour, start_min = map(int, start_time.split(':'))
        end_hour, end_min = map(int, end_time.split(':'))
        
        # Create datetime objects for comparison
        window_start = now.replace(hour=start_hour, minute=start_min, second=0, microsecond=0)
        window_end = now.replace(hour=end_hour, minute=end_min, second=0, microsecond=0)
        
        return window_start <= now <= window_end
    
    def check_risk_limits(self) -> bool:
        """Check if we're within risk limits"""
        try:
            # Check daily loss limit
            daily_loss_limit = self.config.get('risk_management', {}).get('daily_loss_limit', 0.02)
            if self.daily_pnl < -abs(daily_loss_limit) * self.capital:
                logger.warning(f"Daily loss limit reached: ${self.daily_pnl:.2f}")
                return False
            
            # Check consecutive losses
            max_consecutive_losses = self.config.get('risk_management', {}).get('max_consecutive_losses', 3)
            if self.consecutive_losses >= max_consecutive_losses:
                logger.warning(f"Max consecutive losses reached: {self.consecutive_losses}")
                return False
            
            # Check daily trade limit
            max_daily_trades = self.config.get('risk_management', {}).get('max_daily_trades', 10)
            if self.daily_trades >= max_daily_trades:
                logger.warning(f"Max daily trades reached: {self.daily_trades}")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error checking risk limits: {e}")
            return False
    
    def update_daily_metrics(self, pnl: float, is_win: bool):
        """Update daily trading metrics"""
        self.daily_pnl += pnl
        self.daily_trades += 1
        
        if is_win:
            self.consecutive_losses = 0
        else:
            self.consecutive_losses += 1
    
    def reset_daily_metrics(self):
        """Reset daily metrics (call at start of trading day)"""
        self.daily_trades = 0
        self.daily_pnl = 0.0
        self.consecutive_losses = 0
        logger.info("Reset daily trading metrics")
    
    def shutdown(self):
        """Clean shutdown of all components"""
        logger.info(f"Shutting down {self.__class__.__name__}")
        
        # Close any open positions
        if self.positions:
            logger.warning(f"Closing {len(self.positions)} open positions")
            for position_id in list(self.positions.keys()):
                try:
                    self._close_position(position_id, "SHUTDOWN")
                except Exception as e:
                    logger.error(f"Error closing position {position_id}: {e}")
        
        # Disconnect from broker
        if self.broker:
            self.broker.disconnect()
        
        # Clean up other resources
        self.is_running = False
        logger.info("Engine shutdown complete")
    
    @abstractmethod
    def run_trading_cycle(self):
        """Main trading cycle - must be implemented by subclasses"""
        pass
    
    @abstractmethod
    def _process_signal(self, signal: Dict[str, Any]):
        """Process trading signal - must be implemented by subclasses"""
        pass
    
    @abstractmethod
    def _monitor_positions(self):
        """Monitor open positions - must be implemented by subclasses"""
        pass
    
    @abstractmethod
    def _close_position(self, position_id: str, reason: str):
        """Close a position - must be implemented by subclasses"""
        pass