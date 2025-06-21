"""
Abstract base trading engine for all bots
"""
from abc import ABC, abstractmethod
from datetime import datetime, time
from typing import Dict, List, Optional
import logging
import os

from .strategy import BaseStrategy

logger = logging.getLogger(__name__)


class BaseTradingEngine(ABC):
    """Base trading engine that all bot engines inherit from"""
    
    def __init__(self, bot_id: str, strategy: BaseStrategy, broker, 
                 database, config: Dict):
        self.bot_id = bot_id
        self.strategy = strategy
        self.broker = broker
        self.database = database
        self.config = config
        
        # Trading state
        self.positions = {}
        self.is_running = False
        self.last_signal_time = None
        
        # Performance tracking
        self.trades_today = 0
        self.daily_pnl = 0.0
        self.consecutive_losses = 0
        
        # Get trading window from strategy
        trading_hours = strategy.get_trading_hours()
        self.window_start = trading_hours.get('start', time(9, 30))
        self.window_end = trading_hours.get('end', time(16, 0))
        
        logger.info(f"Initialized {bot_id} engine with {strategy.name}")
    
    def initialize(self) -> bool:
        """Initialize the trading engine"""
        try:
            # Connect to broker
            if not self.broker.connect():
                logger.error(f"[{self.bot_id}] Failed to connect to broker")
                return False
            
            # Initialize strategy
            if not self.strategy.initialize(self.get_market_data_provider()):
                logger.error(f"[{self.bot_id}] Failed to initialize strategy")
                return False
            
            # Register bot in database
            self.database.register_bot(
                bot_id=self.bot_id,
                bot_name=f"{self.bot_id.upper()} - {self.strategy.name}",
                strategy_type=self.strategy.__class__.__name__,
                alpaca_account=os.getenv(f'{self.bot_id.upper()}_ALPACA_ACCOUNT', 'default'),
                config=self.config
            )
            
            self.is_running = True
            logger.info(f"[{self.bot_id}] Engine initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"[{self.bot_id}] Initialization error: {e}")
            return False
    
    @abstractmethod
    def get_market_data_provider(self):
        """Get the market data provider for the strategy"""
        pass
    
    def run_trading_cycle(self):
        """Execute one trading cycle"""
        if not self.is_running:
            return
        
        try:
            current_time = datetime.now().time()
            
            # Check if in trading window
            if not self.is_in_trading_window(current_time):
                return
            
            # Check if should trade today
            if not self.strategy.should_trade_today():
                return
            
            # Check risk limits
            if not self.check_risk_limits():
                return
            
            # Get current market data
            market_data = self.get_current_market_data()
            if not market_data:
                return
            
            # Check for new signals
            signal = self.strategy.check_entry_conditions(
                market_data['price'], 
                market_data
            )
            
            if signal and self.strategy.validate_signal(signal):
                self.process_signal(signal, market_data)
            
            # Monitor existing positions
            self.monitor_positions(market_data)
            
        except Exception as e:
            logger.error(f"[{self.bot_id}] Error in trading cycle: {e}")
    
    def is_in_trading_window(self, current_time: time) -> bool:
        """Check if current time is within trading window"""
        return self.window_start <= current_time <= self.window_end
    
    def check_risk_limits(self) -> bool:
        """Check if trading is allowed based on risk limits"""
        # Daily loss limit
        max_daily_loss = self.config.get('max_daily_loss', 1000)
        if self.daily_pnl <= -max_daily_loss:
            logger.warning(f"[{self.bot_id}] Daily loss limit reached: ${self.daily_pnl:.2f}")
            return False
        
        # Consecutive losses
        max_consecutive_losses = self.config.get('max_consecutive_losses', 3)
        if self.consecutive_losses >= max_consecutive_losses:
            logger.warning(f"[{self.bot_id}] Consecutive loss limit reached: {self.consecutive_losses}")
            return False
        
        # Max trades per day
        max_trades_per_day = self.config.get('max_trades_per_day', 10)
        if self.trades_today >= max_trades_per_day:
            logger.warning(f"[{self.bot_id}] Daily trade limit reached: {self.trades_today}")
            return False
        
        return True
    
    @abstractmethod
    def get_current_market_data(self) -> Optional[Dict]:
        """Get current market data"""
        pass
    
    @abstractmethod
    def process_signal(self, signal, market_data: Dict):
        """Process a trading signal"""
        pass
    
    @abstractmethod
    def monitor_positions(self, market_data: Dict):
        """Monitor open positions"""
        pass
    
    def close_position(self, position_id: str, reason: str):
        """Close a position"""
        position = self.positions.get(position_id)
        if not position:
            return
        
        try:
            # Place sell order
            order = self.broker.place_option_order(
                position['symbol'],
                'SELL',
                position['quantity'],
                'MARKET'
            )
            
            if order:
                # Calculate P&L (will be updated with actual fill price)
                pnl = 0  # Placeholder
                
                # Update tracking
                if pnl < 0:
                    self.consecutive_losses += 1
                else:
                    self.consecutive_losses = 0
                
                self.daily_pnl += pnl
                
                # Log to database
                self.database.log_trade_exit(
                    position_id=position_id,
                    exit_price=0,  # Will be updated
                    contracts=position['quantity'],
                    reason=reason,
                    pnl=pnl,
                    bot_id=self.bot_id
                )
                
                # Notify strategy
                self.strategy.on_position_closed(position, pnl, reason)
                
                # Remove from positions
                del self.positions[position_id]
                
                logger.info(f"[{self.bot_id}] Closed position {position_id} - Reason: {reason}")
                
        except Exception as e:
            logger.error(f"[{self.bot_id}] Failed to close position: {e}")
    
    def shutdown(self):
        """Shutdown the trading engine"""
        logger.info(f"[{self.bot_id}] Shutting down engine...")
        
        # Close all positions
        for position_id in list(self.positions.keys()):
            self.close_position(position_id, "SHUTDOWN")
        
        # Disconnect broker
        self.broker.disconnect()
        
        # Log final metrics
        self.database.log_risk_metrics({
            'current_equity': self.broker.get_account_balance(),
            'daily_pnl': self.daily_pnl,
            'daily_pnl_pct': (self.daily_pnl / self.config.get('capital', 10000)) * 100,
            'consecutive_losses': self.consecutive_losses,
            'active_positions': len(self.positions),
            'trades_today': self.trades_today,
            'trading_enabled': False
        }, bot_id=self.bot_id)
        
        self.is_running = False
        logger.info(f"[{self.bot_id}] Engine shutdown complete")
    
    def get_status(self) -> Dict:
        """Get current engine status"""
        return {
            'bot_id': self.bot_id,
            'is_running': self.is_running,
            'positions': len(self.positions),
            'trades_today': self.trades_today,
            'daily_pnl': self.daily_pnl,
            'consecutive_losses': self.consecutive_losses,
            'strategy_status': self.strategy.get_status()
        }