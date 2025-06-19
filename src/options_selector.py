import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, Optional, List
import logging
from scipy.stats import norm
import requests
from functools import lru_cache

logger = logging.getLogger(__name__)

class OptionsSelector:
    def __init__(self, config: dict):
        self.config = config
        self.target_delta = config["options"]["target_delta"]
        self.delta_tolerance = config["options"]["delta_tolerance"]
        self._risk_free_rate = None
        self._rate_last_updated = None
        
    @lru_cache(maxsize=1)
    def get_risk_free_rate(self) -> float:
        """Get current risk-free rate from US Treasury (updates daily)"""
        try:
            # Check if we have a recent rate (within 24 hours)
            if self._risk_free_rate and self._rate_last_updated:
                if (datetime.now() - self._rate_last_updated).total_seconds() < 86400:
                    return self._risk_free_rate
            
            # Fetch 3-month Treasury rate
            url = "https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v1/accounting/od/avg_interest_rates"
            params = {
                "filter": "security_desc:eq:Treasury Bills",
                "sort": "-record_date",
                "page[size]": 1
            }
            
            response = requests.get(url, params=params, timeout=5)
            if response.status_code == 200:
                data = response.json()
                if data.get("data"):
                    # Convert percentage to decimal
                    rate = float(data["data"][0]["avg_interest_rate_amt"]) / 100
                    self._risk_free_rate = rate
                    self._rate_last_updated = datetime.now()
                    logger.info(f"Updated risk-free rate to {rate:.4f}")
                    return rate
            
            # Fallback to Federal Reserve API
            fed_url = "https://api.stlouisfed.org/fred/series/observations"
            fed_params = {
                "series_id": "DGS3MO",  # 3-Month Treasury
                "api_key": "your_fred_api_key",  # Would need actual key
                "file_type": "json",
                "sort_order": "desc",
                "limit": 1
            }
            
            # If no API key or request fails, use reasonable default
            logger.warning("Could not fetch current risk-free rate, using default")
            return 0.05  # 5% default
            
        except Exception as e:
            logger.error(f"Error fetching risk-free rate: {e}")
            return 0.05  # 5% default
    
    def get_weekly_expiry(self) -> str:
        """Get the nearest weekly expiry date"""
        today = datetime.now()
        days_until_friday = (4 - today.weekday()) % 7
        if days_until_friday == 0 and today.hour >= 16:
            days_until_friday = 7
        
        next_friday = today + timedelta(days=days_until_friday)
        return next_friday.strftime('%Y-%m-%d')
    
    def calculate_greeks(self, S: float, K: float, T: float, r: float, 
                        sigma: float, option_type: str) -> Dict[str, float]:
        """Calculate option Greeks using Black-Scholes"""
        # Avoid division by zero
        if T <= 0:
            T = 1/365  # Minimum 1 day
            
        d1 = (np.log(S/K) + (r + sigma**2/2)*T) / (sigma*np.sqrt(T))
        d2 = d1 - sigma*np.sqrt(T)
        
        if option_type == 'CALL':
            delta = norm.cdf(d1)
            gamma = norm.pdf(d1)/(S*sigma*np.sqrt(T))
            theta = -(S*norm.pdf(d1)*sigma)/(2*np.sqrt(T)) - r*K*np.exp(-r*T)*norm.cdf(d2)
            vega = S*norm.pdf(d1)*np.sqrt(T)
        else:
            delta = norm.cdf(d1) - 1
            gamma = norm.pdf(d1)/(S*sigma*np.sqrt(T))
            theta = -(S*norm.pdf(d1)*sigma)/(2*np.sqrt(T)) + r*K*np.exp(-r*T)*norm.cdf(-d2)
            vega = S*norm.pdf(d1)*np.sqrt(T)
        
        return {
            'delta': round(delta, 4),
            'gamma': round(gamma, 4),
            'theta': round(theta/365, 4),  # Daily theta
            'vega': round(vega/100, 4),    # Vega per 1% vol change
            'rho': round(K*T*np.exp(-r*T)*norm.cdf(d2)/100, 4) if option_type == 'CALL' 
                   else round(-K*T*np.exp(-r*T)*norm.cdf(-d2)/100, 4)  # Rho per 1% rate change
        }
    
    def select_option_contract(self, symbol: str, signal_type: str, 
                             current_price: float) -> Optional[Dict]:
        """Select optimal option contract based on delta target"""
        try:
            # For SPY, always use SPY ticker
            if symbol == "SPY":
                ticker = yf.Ticker("SPY")
            else:
                logger.warning(f"Symbol {symbol} not supported, using SPY")
                ticker = yf.Ticker("SPY")
                symbol = "SPY"
            
            expiry = self.get_weekly_expiry()
            
            # Get dynamic risk-free rate
            r = self.get_risk_free_rate()
            
            try:
                option_chain = ticker.option_chain(expiry)
            except Exception:
                logger.warning(f"Weekly expiry not available for {symbol}, trying next available")
                options_dates = ticker.options
                if not options_dates:
                    return None
                expiry = options_dates[0]
                option_chain = ticker.option_chain(expiry)
            
            if signal_type == 'LONG':
                contracts = option_chain.calls
                option_type = 'CALL'
            else:
                contracts = option_chain.puts
                option_type = 'PUT'
            
            # Filter for liquid contracts
            contracts = contracts[
                (contracts['volume'] >= 100) & 
                (contracts['openInterest'] >= 100) &
                (contracts['bid'] > 0) &
                (contracts['ask'] > contracts['bid'])
            ].copy()
            
            if contracts.empty:
                logger.warning(f"No liquid contracts found for {symbol}")
                return None
            
            days_to_expiry = (datetime.strptime(expiry, '%Y-%m-%d') - datetime.now()).days + 1
            T = max(days_to_expiry / 365.0, 1/365)  # Minimum 1 day
            
            best_contract = None
            best_delta_diff = float('inf')
            
            for idx, row in contracts.iterrows():
                strike = row['strike']
                bid = row['bid']
                ask = row['ask']
                mid_price = (bid + ask) / 2
                implied_vol = row.get('impliedVolatility', 0.3)
                
                # Skip if spread is too wide
                spread_pct = (ask - bid) / mid_price if mid_price > 0 else 1
                if spread_pct > 0.10:  # 10% max spread for SPY
                    continue
                
                greeks = self.calculate_greeks(
                    S=current_price,
                    K=strike,
                    T=T,
                    r=r,
                    sigma=implied_vol,
                    option_type=option_type
                )
                
                delta = abs(greeks['delta'])
                delta_diff = abs(delta - self.target_delta)
                
                # Prefer contracts closer to target delta
                if delta_diff < best_delta_diff and delta_diff <= self.delta_tolerance:
                    best_delta_diff = delta_diff
                    best_contract = {
                        'symbol': symbol,
                        'contract_symbol': row['contractSymbol'],
                        'strike': strike,
                        'expiry': expiry,
                        'option_type': option_type,
                        'bid': round(bid, 2),
                        'ask': round(ask, 2),
                        'mid_price': round(mid_price, 2),
                        'last': round(row.get('lastPrice', mid_price), 2),
                        'volume': row['volume'],
                        'open_interest': row['openInterest'],
                        'implied_volatility': round(implied_vol, 3),
                        'greeks': greeks,
                        'days_to_expiry': days_to_expiry,
                        'spread': round(ask - bid, 2),
                        'spread_pct': round(spread_pct * 100, 2),
                        'risk_free_rate': round(r, 4)
                    }
            
            if best_contract:
                logger.info(f"Selected {option_type} strike {best_contract['strike']} "
                          f"with delta {best_contract['greeks']['delta']:.3f}")
            
            return best_contract
            
        except Exception as e:
            logger.error(f"Error selecting option for {symbol}: {e}")
            return None
    
    def validate_contract_liquidity(self, contract: Dict) -> bool:
        """Validate contract has sufficient liquidity for SPY"""
        # SPY specific liquidity requirements (higher than general stocks)
        min_volume = 500
        min_oi = 1000
        max_spread_pct = 0.05  # 5% max spread for SPY
        
        if contract['volume'] < min_volume:
            logger.warning(f"Volume too low: {contract['volume']} < {min_volume}")
            return False
        
        if contract['open_interest'] < min_oi:
            logger.warning(f"Open interest too low: {contract['open_interest']} < {min_oi}")
            return False
        
        spread_pct = contract.get('spread_pct', 100) / 100
        if spread_pct > max_spread_pct:
            logger.warning(f"Spread too wide: {spread_pct:.2%} > {max_spread_pct:.2%}")
            return False
        
        return True
    
    def get_portfolio_greeks(self, positions: List[Dict], current_prices: Dict) -> Dict:
        """Calculate aggregate portfolio Greeks for risk monitoring"""
        total_delta = 0
        total_gamma = 0
        total_theta = 0
        total_vega = 0
        
        r = self.get_risk_free_rate()
        
        for pos in positions:
            if pos['status'] != 'OPEN':
                continue
                
            symbol = pos['symbol']
            current_price = current_prices.get(symbol, pos['entry_price'])
            
            days_to_expiry = (datetime.strptime(pos['expiry'], '%Y-%m-%d') - datetime.now()).days + 1
            T = max(days_to_expiry / 365.0, 1/365)
            
            greeks = self.calculate_greeks(
                S=current_price,
                K=pos['strike'],
                T=T,
                r=r,
                sigma=pos.get('implied_volatility', 0.3),
                option_type=pos['option_type']
            )
            
            # Scale by position size and contract multiplier
            position_multiplier = pos['contracts'] * 100
            total_delta += greeks['delta'] * position_multiplier
            total_gamma += greeks['gamma'] * position_multiplier
            total_theta += greeks['theta'] * position_multiplier
            total_vega += greeks['vega'] * position_multiplier
        
        return {
            'total_delta': round(total_delta, 2),
            'total_gamma': round(total_gamma, 2),
            'total_theta': round(total_theta, 2),
            'total_vega': round(total_vega, 2),
            'delta_dollars': round(total_delta * current_prices.get('SPY', 500), 2)
        }