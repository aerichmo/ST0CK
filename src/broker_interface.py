"""
Abstract broker interface for all broker implementations
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Optional
from datetime import datetime


class BrokerInterface(ABC):
    """Abstract base class for all broker implementations"""
    
    @abstractmethod
    def connect(self) -> bool:
        """
        Connect to the broker
        Returns True if connection successful
        """
        pass
    
    @abstractmethod
    def disconnect(self) -> None:
        """Disconnect from the broker"""
        pass
    
    @abstractmethod
    def get_account_info(self) -> Optional[Dict]:
        """
        Get account information
        Returns dict with account details or None if failed
        """
        pass
    
    @abstractmethod
    def place_option_order(self, contract: Dict, quantity: int, 
                          order_type: str = 'MARKET') -> Optional[str]:
        """
        Place an option order
        
        Args:
            contract: Option contract details
            quantity: Number of contracts
            order_type: Order type (MARKET, LIMIT, etc.)
            
        Returns:
            Order ID if successful, None otherwise
        """
        pass
    
    @abstractmethod
    def place_stock_order(self, symbol: str, quantity: int, side: str,
                         order_type: str = 'MARKET', limit_price: Optional[float] = None,
                         time_in_force: str = 'DAY') -> Optional[str]:
        """
        Place a stock order
        
        Args:
            symbol: Stock symbol
            quantity: Number of shares
            side: 'BUY' or 'SELL'
            order_type: Order type (MARKET, LIMIT, etc.)
            limit_price: Limit price for limit orders
            time_in_force: Time in force (DAY, GTC, etc.)
            
        Returns:
            Order ID if successful, None otherwise
        """
        pass
    
    @abstractmethod
    def cancel_order(self, order_id: str) -> bool:
        """
        Cancel an order
        
        Args:
            order_id: Order ID to cancel
            
        Returns:
            True if successful
        """
        pass
    
    @abstractmethod
    def get_order_status(self, order_id: str) -> Optional[Dict]:
        """
        Get order status
        
        Args:
            order_id: Order ID
            
        Returns:
            Order details dict or None if not found
        """
        pass
    
    @abstractmethod
    def get_open_orders(self) -> List[Dict]:
        """
        Get all open orders
        
        Returns:
            List of order dicts
        """
        pass
    
    @abstractmethod
    def get_positions(self) -> List[Dict]:
        """
        Get all open positions
        
        Returns:
            List of position dicts
        """
        pass
    
    @abstractmethod
    def close_position(self, symbol: str, quantity: Optional[int] = None) -> Optional[str]:
        """
        Close a position
        
        Args:
            symbol: Symbol to close
            quantity: Quantity to close (None for entire position)
            
        Returns:
            Order ID if successful
        """
        pass
    
    @abstractmethod
    def get_option_chain(self, underlying: str, expiration: Optional[str] = None) -> Optional[Dict]:
        """
        Get option chain for underlying
        
        Args:
            underlying: Underlying symbol
            expiration: Optional expiration date filter
            
        Returns:
            Option chain data or None if failed
        """
        pass
    
    @abstractmethod
    def get_option_quotes(self, contracts: List[str]) -> Optional[Dict]:
        """
        Get quotes for option contracts
        
        Args:
            contracts: List of option contract symbols
            
        Returns:
            Dict of contract symbol to quote data
        """
        pass
    
    @property
    @abstractmethod
    def is_connected(self) -> bool:
        """Check if broker is connected"""
        pass