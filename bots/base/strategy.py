"""
Abstract base strategy class for all trading bots
"""
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class Signal:
    """Trading signal data class"""
    def __init__(self, signal_type: str, strength: float, metadata: Dict = None):
        self.type = signal_type  # 'LONG' or 'SHORT'
        self.strength = strength  # 0.0 to 1.0
        self.timestamp = datetime.now()
        self.metadata = metadata or {}
    
    def __repr__(self):
        return f"Signal({self.type}, strength={self.strength:.2f})"


class BaseStrategy(ABC):
    """Abstract base class for all trading strategies"""
    
    def __init__(self, bot_id: str, config: Dict):
        self.bot_id = bot_id
        self.config = config
        self.name = config.get('strategy_name', 'Unknown Strategy')
        self.is_initialized = False
        
    @abstractmethod
    def initialize(self, market_data_provider) -> bool:
        """
        Initialize the strategy with market data provider
        Returns True if initialization successful
        """
        pass
    
    @abstractmethod
    def check_entry_conditions(self, current_price: float, market_data: Dict) -> Optional[Signal]:
        """
        Check if entry conditions are met
        Returns Signal if conditions met, None otherwise
        """
        pass
    
    @abstractmethod
    def calculate_position_size(self, signal: Signal, account_balance: float, 
                              current_price: float) -> int:
        """
        Calculate the number of contracts to trade
        """
        pass
    
    @abstractmethod
    def get_exit_levels(self, signal: Signal, entry_price: float) -> Dict:
        """
        Calculate exit levels (stop loss, targets)
        Returns dict with 'stop_loss', 'target_1', 'target_2'
        """
        pass
    
    @abstractmethod
    def check_exit_conditions(self, position: Dict, current_price: float, 
                            market_data: Dict) -> Tuple[bool, str]:
        """
        Check if position should be exited
        Returns (should_exit, reason)
        """
        pass
    
    @abstractmethod
    def get_option_selection_criteria(self, signal: Signal) -> Dict:
        """
        Get criteria for option selection
        Returns dict with selection parameters like DTE range, delta range, etc.
        """
        pass
    
    def validate_signal(self, signal: Signal) -> bool:
        """
        Validate signal before execution (can be overridden)
        """
        if signal.strength < self.config.get('min_signal_strength', 0.5):
            logger.debug(f"Signal strength {signal.strength} below minimum")
            return False
        return True
    
    def on_position_opened(self, position: Dict):
        """
        Called when a position is opened (can be overridden)
        """
        logger.info(f"[{self.bot_id}] Position opened: {position['position_id']}")
    
    def on_position_closed(self, position: Dict, pnl: float, reason: str):
        """
        Called when a position is closed (can be overridden)
        """
        logger.info(f"[{self.bot_id}] Position closed: {position['position_id']}, "
                   f"PnL: ${pnl:.2f}, Reason: {reason}")
    
    def get_trading_hours(self) -> Dict:
        """
        Get trading hours for this strategy
        Returns dict with 'start' and 'end' time objects
        """
        return {
            'start': self.config.get('trading_start_time'),
            'end': self.config.get('trading_end_time')
        }
    
    def should_trade_today(self) -> bool:
        """
        Check if strategy should trade today (can be overridden)
        """
        return True
    
    def get_status(self) -> Dict:
        """
        Get current strategy status
        """
        return {
            'bot_id': self.bot_id,
            'strategy_name': self.name,
            'is_initialized': self.is_initialized,
            'config': self.config
        }