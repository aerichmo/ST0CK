import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, Optional, List
import logging
from scipy.stats import norm

logger = logging.getLogger(__name__)

class OptionsSelector:
    def __init__(self, config: dict):
        self.config = config
        self.target_delta = config["options"]["target_delta"]
        self.delta_tolerance = config["options"]["delta_tolerance"]
        
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
            'delta': delta,
            'gamma': gamma,
            'theta': theta/365,
            'vega': vega/100
        }
    
    def select_option_contract(self, symbol: str, signal_type: str, 
                             current_price: float) -> Optional[Dict]:
        """Select optimal option contract based on delta target"""
        try:
            ticker = yf.Ticker(symbol)
            expiry = self.get_weekly_expiry()
            
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
            
            contracts = contracts[contracts['volume'] > 0].copy()
            
            if contracts.empty:
                return None
            
            days_to_expiry = (datetime.strptime(expiry, '%Y-%m-%d') - datetime.now()).days + 1
            T = days_to_expiry / 365.0
            r = 0.05
            
            best_contract = None
            best_delta_diff = float('inf')
            
            for idx, row in contracts.iterrows():
                strike = row['strike']
                bid = row['bid']
                ask = row['ask']
                mid_price = (bid + ask) / 2
                implied_vol = row.get('impliedVolatility', 0.3)
                
                if mid_price <= 0 or bid <= 0:
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
                
                if delta_diff < best_delta_diff and delta_diff <= self.delta_tolerance:
                    best_delta_diff = delta_diff
                    best_contract = {
                        'symbol': symbol,
                        'contract_symbol': row['contractSymbol'],
                        'strike': strike,
                        'expiry': expiry,
                        'option_type': option_type,
                        'bid': bid,
                        'ask': ask,
                        'mid_price': mid_price,
                        'volume': row['volume'],
                        'open_interest': row['openInterest'],
                        'implied_volatility': implied_vol,
                        'greeks': greeks,
                        'days_to_expiry': days_to_expiry
                    }
            
            return best_contract
            
        except Exception as e:
            logger.error(f"Error selecting option for {symbol}: {e}")
            return None
    
    def validate_contract_liquidity(self, contract: Dict) -> bool:
        """Validate contract has sufficient liquidity"""
        if contract['volume'] < 10:
            return False
        
        if contract['open_interest'] < 50:
            return False
        
        spread = contract['ask'] - contract['bid']
        spread_pct = spread / contract['mid_price'] if contract['mid_price'] > 0 else 1
        
        if spread_pct > 0.15:
            return False
        
        return True