"""
High-speed options data fetcher using Alpaca's Options API
Optimized for real-time trading with minimal latency
"""

import logging
from typing import Dict, List, Optional
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import os

logger = logging.getLogger(__name__)


class AlpacaOptionsData:
    """Fast options data provider using Alpaca's Options API"""
    
    def __init__(self, alpaca_client=None, api_key=None, api_secret=None):
        """
        Initialize options data provider
        
        Args:
            alpaca_client: Unused, kept for compatibility
            api_key: Alpaca API key (optional, will use env var if not provided)
            api_secret: Alpaca API secret (optional, will use env var if not provided)
        """
        # Get credentials
        self.api_key = api_key or os.environ.get('APCA_API_KEY_ID')
        self.api_secret = api_secret or os.environ.get('APCA_API_SECRET_KEY')
        
        # Initialize options client when first needed
        self._option_client = None
        self._cache = {}
        self._cache_ttl = 60  # Cache for 60 seconds
        
    def _get_client(self):
        """Lazy initialization of options client"""
        if self._option_client is None:
            try:
                from alpaca.data.historical.option import OptionHistoricalDataClient
                self._option_client = OptionHistoricalDataClient(
                    self.api_key, 
                    self.api_secret
                )
                logger.info("Initialized Alpaca Options client")
            except ImportError:
                logger.error("alpaca-py options module not found. Install with: pip install alpaca-py>=0.15.0")
                raise
            except Exception as e:
                logger.error(f"Failed to initialize options client: {e}")
                raise
        return self._option_client
        
    def get_option_chain(self, symbol: str, expiration: datetime, 
                        option_type: str = 'CALL') -> List[Dict]:
        """
        Get option chain using Alpaca's Options API
        
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
            client = self._get_client()
            
            # Get option contracts from Alpaca
            contracts = client.get_option_contracts(
                underlying_symbol=symbol,
                expiration_date=expiration.date()
            )
            
            # Filter by option type and convert to dict format
            options = []
            for contract in contracts:
                if (option_type == 'CALL' and contract.call_or_put == 'C') or \
                   (option_type == 'PUT' and contract.call_or_put == 'P'):
                    options.append({
                        'contract_symbol': contract.symbol,
                        'strike': float(contract.strike_price),
                        'expiration': contract.expiration_date.isoformat(),
                        'option_type': 'CALL' if contract.call_or_put == 'C' else 'PUT',
                        'underlying_symbol': contract.underlying_symbol,
                        'contract_size': contract.contract_size,
                        'style': contract.style
                    })
            
            # Cache the results
            self._cache[cache_key] = (options, datetime.now())
            
            logger.info(f"Found {len(options)} {option_type} options for {symbol} expiring {expiration.date()}")
            return options
            
        except Exception as e:
            logger.error(f"Failed to fetch options from Alpaca: {e}")
            return []
    
    def get_option_quote(self, contract_symbol: str) -> Optional[Dict]:
        """
        Get real-time quote for specific option contract
        
        Args:
            contract_symbol: Option contract symbol
            
        Returns:
            Real-time quote data
        """
        try:
            client = self._get_client()
            from alpaca.data.requests import OptionLatestQuoteRequest
            
            request = OptionLatestQuoteRequest(symbol_or_symbols=contract_symbol)
            quotes = client.get_option_latest_quote(request)
            
            if contract_symbol in quotes:
                quote = quotes[contract_symbol]
                return {
                    'symbol': contract_symbol,
                    'bid': float(quote.bid_price) if quote.bid_price else 0,
                    'ask': float(quote.ask_price) if quote.ask_price else 0,
                    'bid_size': int(quote.bid_size) if quote.bid_size else 0,
                    'ask_size': int(quote.ask_size) if quote.ask_size else 0,
                    'last': float((quote.bid_price + quote.ask_price) / 2) if quote.bid_price and quote.ask_price else 0,
                    'timestamp': quote.timestamp.isoformat() if quote.timestamp else datetime.now().isoformat()
                }
            return None
            
        except Exception as e:
            logger.error(f"Failed to get option quote: {e}")
            return None
    
    def get_multiple_quotes(self, contract_symbols: List[str]) -> Dict[str, Dict]:
        """
        Get quotes for multiple option contracts in parallel
        
        Args:
            contract_symbols: List of option contract symbols
            
        Returns:
            Dict mapping symbols to quote data
        """
        quotes = {}
        
        # Batch request is more efficient
        try:
            client = self._get_client()
            from alpaca.data.requests import OptionLatestQuoteRequest
            
            request = OptionLatestQuoteRequest(symbol_or_symbols=contract_symbols)
            raw_quotes = client.get_option_latest_quote(request)
            
            for symbol, quote in raw_quotes.items():
                quotes[symbol] = {
                    'symbol': symbol,
                    'bid': float(quote.bid_price) if quote.bid_price else 0,
                    'ask': float(quote.ask_price) if quote.ask_price else 0,
                    'bid_size': int(quote.bid_size) if quote.bid_size else 0,
                    'ask_size': int(quote.ask_size) if quote.ask_size else 0,
                    'last': float((quote.bid_price + quote.ask_price) / 2) if quote.bid_price and quote.ask_price else 0,
                    'timestamp': quote.timestamp.isoformat() if quote.timestamp else datetime.now().isoformat()
                }
                
        except Exception as e:
            logger.error(f"Failed to fetch multiple quotes: {e}")
        
        return quotes
    
    def find_options_by_criteria(self, symbol: str, expiration: datetime,
                                option_type: str, target_delta: float = 0.40,
                                min_volume: int = 100) -> List[Dict]:
        """
        Find options matching specific criteria with Greeks
        
        Args:
            symbol: Underlying symbol
            expiration: Target expiration
            option_type: CALL or PUT
            target_delta: Target delta (e.g., 0.40)
            min_volume: Minimum volume filter
            
        Returns:
            List of matching options sorted by liquidity
        """
        try:
            # Get all contracts for the expiration
            contracts = self.get_option_chain(symbol, expiration, option_type)
            
            if not contracts:
                return []
            
            # Get snapshots with Greeks for all contracts
            client = self._get_client()
            from alpaca.data.requests import OptionSnapshotRequest
            
            contract_symbols = [c['contract_symbol'] for c in contracts]
            
            # Batch request for efficiency
            request = OptionSnapshotRequest(symbol_or_symbols=contract_symbols)
            snapshots = client.get_option_snapshot(request)
            
            # Filter and enhance with Greeks
            filtered = []
            for contract in contracts:
                symbol = contract['contract_symbol']
                if symbol in snapshots:
                    snapshot = snapshots[symbol]
                    
                    # Skip if no quote data
                    if not snapshot.latest_quote:
                        continue
                    
                    # Get Greeks
                    if snapshot.greeks:
                        delta = abs(float(snapshot.greeks.delta)) if snapshot.greeks.delta else 0
                    else:
                        continue  # Skip if no Greeks available
                    
                    # Check delta criteria
                    delta_diff = abs(delta - target_delta)
                    if delta_diff <= 0.1:  # Within 0.1 of target
                        
                        # Get volume from trade data
                        volume = 0
                        if snapshot.latest_trade:
                            volume = int(snapshot.latest_trade.size) if snapshot.latest_trade.size else 0
                        
                        # Apply volume filter
                        if volume >= min_volume or min_volume == 0:  # Allow 0 for testing
                            
                            quote = snapshot.latest_quote
                            enhanced_contract = {
                                **contract,
                                'bid': float(quote.bid_price) if quote.bid_price else 0,
                                'ask': float(quote.ask_price) if quote.ask_price else 0,
                                'mid_price': float((quote.bid_price + quote.ask_price) / 2) if quote.bid_price and quote.ask_price else 0,
                                'volume': volume,
                                'open_interest': int(snapshot.open_interest) if snapshot.open_interest else 0,
                                'implied_volatility': float(snapshot.implied_volatility) if snapshot.implied_volatility else 0,
                                'delta': delta,
                                'gamma': float(snapshot.greeks.gamma) if snapshot.greeks.gamma else 0,
                                'theta': float(snapshot.greeks.theta) if snapshot.greeks.theta else 0,
                                'vega': float(snapshot.greeks.vega) if snapshot.greeks.vega else 0,
                                'rho': float(snapshot.greeks.rho) if snapshot.greeks.rho else 0,
                                'delta_diff': delta_diff,
                                'underlying_price': float(snapshot.underlying_snapshot.latest_quote.ask_price) if snapshot.underlying_snapshot else 0
                            }
                            filtered.append(enhanced_contract)
            
            # Sort by delta closeness and liquidity
            filtered.sort(key=lambda x: (x['delta_diff'], 
                                       -(x['volume'] + x['open_interest'])))
            
            logger.info(f"Found {len(filtered)} options matching criteria for {symbol}")
            return filtered[:10]  # Return top 10 matches
            
        except Exception as e:
            logger.error(f"Failed to find options by criteria: {e}")
            return []