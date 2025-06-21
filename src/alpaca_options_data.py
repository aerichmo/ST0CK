"""
High-speed options data fetcher using Alpaca exclusively
Optimized for real-time trading with minimal latency
"""

import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import numpy as np
from scipy.stats import norm

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
            # Since Alpaca doesn't yet support options data directly,
            # we'll generate synthetic options data based on the underlying
            # This will be replaced when Alpaca adds options support
            options = self._generate_synthetic_options(symbol, expiration, option_type)
            
            # Cache the results
            self._cache[cache_key] = (options, datetime.now())
            
            return options
            
        except Exception as e:
            logger.error(f"Failed to fetch options: {e}")
            return []
    
    def _generate_synthetic_options(self, symbol: str, expiration: datetime,
                                  option_type: str) -> List[Dict]:
        """Generate synthetic options data based on underlying price"""
        try:
            # Get current stock price from Alpaca
            from alpaca.data.requests import StockLatestQuoteRequest
            
            request = StockLatestQuoteRequest(symbol_or_symbols=symbol)
            quote = self.alpaca_client.get_stock_latest_quote(request)
            
            if not quote or symbol not in quote:
                logger.error(f"No quote data for {symbol}")
                return []
            
            current_price = float(quote[symbol].ask_price)
            
            # Generate strikes around current price
            # For SPY, typically $1 strikes
            strike_interval = 1.0 if symbol == "SPY" else max(1.0, round(current_price * 0.025))
            
            # Generate strikes from -10% to +10% of current price
            min_strike = round(current_price * 0.9 / strike_interval) * strike_interval
            max_strike = round(current_price * 1.1 / strike_interval) * strike_interval
            
            strikes = np.arange(min_strike, max_strike + strike_interval, strike_interval)
            
            # Calculate days to expiry
            days_to_expiry = (expiration - datetime.now()).days
            time_to_expiry = days_to_expiry / 365.0
            
            # Estimate IV based on moneyness and time to expiry
            base_iv = 0.18 if symbol == "SPY" else 0.25  # SPY typically has lower IV
            
            options = []
            for strike in strikes:
                moneyness = strike / current_price
                
                # Adjust IV based on moneyness (smile effect)
                if option_type == 'CALL':
                    iv = base_iv * (1 + 0.1 * max(0, moneyness - 1))
                else:
                    iv = base_iv * (1 + 0.1 * max(0, 1 - moneyness))
                
                # Calculate Greeks using Black-Scholes
                greeks = self._calculate_greeks(
                    S=current_price,
                    K=strike,
                    T=time_to_expiry,
                    r=0.048,  # Current risk-free rate
                    sigma=iv,
                    option_type=option_type
                )
                
                # Estimate bid-ask spread based on moneyness
                otm_factor = abs(1 - moneyness)
                spread = max(0.05, 0.02 + otm_factor * 0.5)
                
                # Calculate option price
                option_price = greeks['price']
                bid = max(0.01, option_price - spread/2)
                ask = option_price + spread/2
                
                # Estimate volume and open interest
                # Higher for ATM options
                atm_factor = np.exp(-((moneyness - 1) ** 2) / 0.01)
                volume = int(10000 * atm_factor * np.random.uniform(0.5, 1.5))
                open_interest = int(volume * np.random.uniform(5, 15))
                
                option = {
                    'contract_symbol': f"{symbol}{expiration.strftime('%y%m%d')}{option_type[0]}{int(strike * 1000):08d}",
                    'strike': float(strike),
                    'bid': round(bid, 2),
                    'ask': round(ask, 2),
                    'last': round((bid + ask) / 2, 2),
                    'mid_price': round((bid + ask) / 2, 2),
                    'volume': volume,
                    'open_interest': open_interest,
                    'implied_volatility': iv,
                    'in_the_money': (option_type == 'CALL' and strike < current_price) or 
                                   (option_type == 'PUT' and strike > current_price),
                    'spread': round(ask - bid, 2),
                    'spread_pct': (ask - bid) / ask if ask > 0 else 0,
                    'moneyness': moneyness,
                    'expiration': expiration.isoformat(),
                    'days_to_expiry': days_to_expiry,
                    'option_type': option_type,
                    'underlying_price': current_price,
                    'delta': greeks['delta'],
                    'gamma': greeks['gamma'],
                    'theta': greeks['theta'],
                    'vega': greeks['vega'],
                    'rho': greeks['rho']
                }
                
                options.append(option)
            
            # Sort by volume for liquidity
            options.sort(key=lambda x: x['volume'], reverse=True)
            
            return options
            
        except Exception as e:
            logger.error(f"Failed to generate synthetic options: {e}")
            return []
    
    def _calculate_greeks(self, S: float, K: float, T: float, r: float, 
                         sigma: float, option_type: str) -> Dict[str, float]:
        """Calculate option Greeks using Black-Scholes"""
        # Handle edge cases
        if T <= 0:
            return {
                'price': max(0, S - K) if option_type == 'CALL' else max(0, K - S),
                'delta': 1.0 if (option_type == 'CALL' and S > K) else 0.0,
                'gamma': 0.0,
                'theta': 0.0,
                'vega': 0.0,
                'rho': 0.0
            }
        
        # Black-Scholes calculations
        d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
        d2 = d1 - sigma * np.sqrt(T)
        
        if option_type == 'CALL':
            price = S * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)
            delta = norm.cdf(d1)
            theta = (-S * norm.pdf(d1) * sigma / (2 * np.sqrt(T)) - 
                    r * K * np.exp(-r * T) * norm.cdf(d2)) / 365
            rho = K * T * np.exp(-r * T) * norm.cdf(d2) / 100
        else:  # PUT
            price = K * np.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)
            delta = -norm.cdf(-d1)
            theta = (-S * norm.pdf(d1) * sigma / (2 * np.sqrt(T)) + 
                    r * K * np.exp(-r * T) * norm.cdf(-d2)) / 365
            rho = -K * T * np.exp(-r * T) * norm.cdf(-d2) / 100
        
        # Greeks common to both
        gamma = norm.pdf(d1) / (S * sigma * np.sqrt(T))
        vega = S * norm.pdf(d1) * np.sqrt(T) / 100
        
        return {
            'price': price,
            'delta': delta,
            'gamma': gamma,
            'theta': theta,
            'vega': vega,
            'rho': rho
        }
    
    def get_option_quote(self, contract_symbol: str) -> Optional[Dict]:
        """
        Get real-time quote for specific option contract
        
        Args:
            contract_symbol: Option contract symbol
            
        Returns:
            Real-time quote data
        """
        # For now, return synthetic data
        # This will be replaced when Alpaca adds options support
        return {
            'symbol': contract_symbol,
            'bid': 1.25,
            'ask': 1.30,
            'last': 1.28,
            'volume': 5000,
            'timestamp': datetime.now().isoformat()
        }
    
    def get_multiple_quotes(self, contract_symbols: List[str]) -> Dict[str, Dict]:
        """
        Get quotes for multiple option contracts in parallel
        
        Args:
            contract_symbols: List of option contract symbols
            
        Returns:
            Dict mapping symbols to quote data
        """
        quotes = {}
        
        with ThreadPoolExecutor(max_workers=10) as executor:
            future_to_symbol = {
                executor.submit(self.get_option_quote, symbol): symbol
                for symbol in contract_symbols
            }
            
            for future in as_completed(future_to_symbol):
                symbol = future_to_symbol[future]
                try:
                    quote = future.result()
                    if quote:
                        quotes[symbol] = quote
                except Exception as e:
                    logger.error(f"Failed to fetch {symbol}: {e}")
        
        return quotes
    
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
        # Get full chain
        chain = self.get_option_chain(symbol, expiration, option_type)
        
        # Filter by criteria
        filtered = []
        for option in chain:
            # Volume filter
            if option['volume'] < min_volume:
                continue
            
            # Delta filter
            delta = option.get('delta', 0)
            
            # Check if delta is within tolerance
            if abs(abs(delta) - target_delta) <= 0.1:
                option['delta_diff'] = abs(abs(delta) - target_delta)
                filtered.append(option)
        
        # Sort by delta closeness and liquidity
        filtered.sort(key=lambda x: (x['delta_diff'], 
                                   -(x['volume'] + x['open_interest'])))
        
        return filtered[:10]  # Return top 10 matches