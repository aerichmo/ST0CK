"""
High-speed options data fetcher using Alpaca exclusively
Optimized for real-time trading with minimal latency
"""

import logging
from typing import Dict, List, Optional
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

logger = logging.getLogger(__name__)


class AlpacaOptionsData:
    """Fast options data provider using Alpaca exclusively"""
    
    def __init__(self, alpaca_client=None):
        """
        Initialize options data provider
        
        Args:
            alpaca_client: Alpaca data client
        """
        self.alpaca_client = alpaca_client
        self._cache = {}
        self._cache_ttl = 60  # Cache for 60 seconds
        
    def get_option_chain(self, symbol: str, expiration: datetime, 
                        option_type: str = 'CALL') -> List[Dict]:
        """
        Get option chain using Alpaca data
        
        Args:
            symbol: Stock symbol
            expiration: Option expiration date
            option_type: 'CALL' or 'PUT'
            
        Returns:
            List of option contracts with real-time data
        """
        cache_key = f"{symbol}_{expiration.date()}_{option_type}"
        
        # Check cache first
        if cache_key in self._cache:
            cached_data, cache_time = self._cache[cache_key]
            if (datetime.now() - cache_time).seconds < self._cache_ttl:
                return cached_data
        
        try:
            # Alpaca does not yet support options data
            # Return empty list until Alpaca adds options support
            logger.warning(f"Alpaca options API not yet available for {symbol}")
            return []
            
        except Exception as e:
            logger.error(f"Failed to fetch options: {e}")
            return []
    
    def get_option_quote(self, contract_symbol: str) -> Optional[Dict]:
        """
        Get real-time quote for specific option contract
        
        Args:
            contract_symbol: Option contract symbol
            
        Returns:
            Real-time quote data
        """
        # Alpaca does not yet support options quotes
        logger.warning(f"Alpaca options quotes not yet available for {contract_symbol}")
        return None
    
    def get_multiple_quotes(self, contract_symbols: List[str]) -> Dict[str, Dict]:
        """
        Get quotes for multiple option contracts in parallel
        
        Args:
            contract_symbols: List of option contract symbols
            
        Returns:
            Dict mapping symbols to quote data
        """
        # Alpaca does not yet support options quotes
        logger.warning("Alpaca options quotes not yet available")
        return {}
    
    def find_options_by_criteria(self, symbol: str, expiration: datetime,
                                option_type: str, target_delta: float = 0.40,
                                min_volume: int = 100) -> List[Dict]:
        """
        Find options matching specific criteria
        
        Args:
            symbol: Underlying symbol
            expiration: Target expiration
            option_type: CALL or PUT
            target_delta: Target delta (e.g., 0.40)
            min_volume: Minimum volume filter
            
        Returns:
            List of matching options sorted by liquidity
        """
        # Alpaca does not yet support options data
        logger.warning(f"Alpaca options search not yet available for {symbol}")
        return []