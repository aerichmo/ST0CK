import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, Optional, List
import logging
from scipy.stats import norm
import requests
from functools import lru_cache
import time

logger = logging.getLogger(__name__)

class OptionsSelector:
    def __init__(self, config: dict):
        self.config = config
        self.target_delta = config["options"]["target_delta"]
        self.delta_tolerance = config["options"]["delta_tolerance"]
        self._risk_free_rate_cache = None
        self._risk_free_rate_timestamp = 0
        self._cache_ttl = 3600  # 1 hour cache for risk-free rate
        
    def get_weekly_expiry(self) -> str:
        """Get the nearest weekly expiry date for SPY"""
        today = datetime.now()
        days_until_friday = (4 - today.weekday()) % 7
        if days_until_friday == 0 and today.hour >= 16:
            days_until_friday = 7
        
        next_friday = today + timedelta(days=days_until_friday)
        return next_friday.strftime('%Y-%m-%d')
    
    def get_risk_free_rate(self) -> float:
        """Get current risk-free rate from Treasury data"""
        # Check cache first
        if (self._risk_free_rate_cache is not None and 
            time.time() - self._risk_free_rate_timestamp < self._cache_ttl):
            return self._risk_free_rate_cache
        
        try:
            # Use 13-week Treasury yield (^IRX) from Yahoo Finance
            treasury = yf.Ticker("^IRX")
            hist = treasury.history(period="1d")
            
            if not hist.empty and 'Close' in hist.columns:
                # ^IRX is quoted as percentage, convert to decimal
                rate = hist['Close'].iloc[-1] / 100
                self._risk_free_rate_cache = rate
                self._risk_free_rate_timestamp = time.time()
                logger.info(f"Updated risk-free rate to {rate:.4f} ({rate*100:.2f}%)")
                return rate
        except Exception as e:
            logger.warning(f"Failed to fetch risk-free rate from ^IRX: {e}")
        
        # Fallback: Try to get 10-year Treasury yield as proxy
        try:
            tnx = yf.Ticker("^TNX")
            hist = tnx.history(period="1d")
            
            if not hist.empty and 'Close' in hist.columns:
                # ^TNX is also quoted as percentage
                # Adjust down slightly for shorter-term rate approximation
                rate = (hist['Close'].iloc[-1] / 100) * 0.85
                self._risk_free_rate_cache = rate
                self._risk_free_rate_timestamp = time.time()
                logger.info(f"Updated risk-free rate from ^TNX to {rate:.4f} ({rate*100:.2f}%)")
                return rate
        except Exception as e:
            logger.warning(f"Failed to fetch risk-free rate from ^TNX: {e}")
        
        # Final fallback: Use a reasonable default based on recent history
        default_rate = 0.045  # 4.5% default
        logger.warning(f"Using default risk-free rate of {default_rate:.4f}")
        return default_rate
    
    def calculate_greeks(self, S: float, K: float, T: float, r: float, 
                        sigma: float, option_type: str) -> Dict[str, float]:
        """Calculate option Greeks using Black-Scholes"""
        # Handle edge cases
        if T <= 0:
            T = 1/365  # Minimum 1 day
        if sigma <= 0:
            sigma = 0.15  # Minimum 15% volatility
            
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
            'vega': round(vega/100, 4)     # Vega per 1% vol change
        }
    
    def select_option_contract(self, symbol: str, signal_type: str, 
                             current_price: float) -> Optional[Dict]:
        """Select optimal SPY option contract based on delta target"""
        # Enforce SPY-only trading
        if symbol != 'SPY':
            logger.warning(f"Only SPY trading is allowed, rejecting {symbol}")
            return None
            
        try:
            ticker = yf.Ticker(symbol)
            
            # Get dynamic risk-free rate
            r = self.get_risk_free_rate()
            
            # For SPY, try 0DTE first during market hours
            now = datetime.now()
            if now.weekday() < 5 and now.hour >= 9 and now.hour < 16:
                # Try today's expiry first (0DTE)
                today_expiry = now.strftime('%Y-%m-%d')
                try:
                    option_chain = ticker.option_chain(today_expiry)
                    expiry = today_expiry
                    logger.info("Using 0DTE options for SPY")
                except:
                    # Fall back to weekly
                    expiry = self.get_weekly_expiry()
                    option_chain = ticker.option_chain(expiry)
            else:
                # Use weekly expiry
                expiry = self.get_weekly_expiry()
                option_chain = ticker.option_chain(expiry)
            
            if signal_type == 'LONG':
                contracts = option_chain.calls
                option_type = 'CALL'
            else:
                contracts = option_chain.puts
                option_type = 'PUT'
            
            # Filter for liquid contracts (SPY typically has excellent liquidity)
            contracts = contracts[
                (contracts['volume'] >= self.config["options"]["min_volume"]) & 
                (contracts['bid'] > 0) & 
                (contracts['ask'] > 0) &
                (contracts['openInterest'] >= self.config["options"]["min_open_interest"])
            ].copy()
            
            if contracts.empty:
                logger.warning("No liquid contracts found for SPY")
                return None
            
            days_to_expiry = max(1, (datetime.strptime(expiry, '%Y-%m-%d') - datetime.now()).days + 1)
            T = days_to_expiry / 365.0
            
            # Calculate delta for each contract and find best match
            candidates = []
            
            for idx, row in contracts.iterrows():
                strike = row['strike']
                bid = row['bid']
                ask = row['ask']
                mid_price = (bid + ask) / 2
                implied_vol = row.get('impliedVolatility', 0.20)  # SPY typically ~20% IV
                
                # Skip if spread is too wide (rare for SPY)
                spread_pct = (ask - bid) / mid_price if mid_price > 0 else 1
                if spread_pct > self.config["options"]["max_spread_pct"]:
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
                
                if delta_diff <= self.delta_tolerance:
                    candidates.append({
                        'symbol': symbol,
                        'contract_symbol': row['contractSymbol'],
                        'strike': strike,
                        'expiry': expiry,
                        'option_type': option_type,
                        'bid': bid,
                        'ask': ask,
                        'mid_price': mid_price,
                        'last': row.get('lastPrice', mid_price),
                        'volume': row['volume'],
                        'open_interest': row['openInterest'],
                        'implied_volatility': implied_vol,
                        'greeks': greeks,
                        'days_to_expiry': days_to_expiry,
                        'delta_diff': delta_diff,
                        'spread_pct': spread_pct,
                        'liquidity_score': self._calculate_liquidity_score(row),
                        'risk_free_rate': r
                    })
            
            if not candidates:
                logger.warning(f"No contracts found within delta tolerance for SPY")
                return None
            
            # Select best contract - for SPY prioritize tightest spread
            candidates.sort(key=lambda x: (
                x['spread_pct'],      # Tightest spread first
                x['delta_diff'],      # Closest to target delta
                -x['volume']          # Highest volume
            ))
            
            best_contract = candidates[0]
            
            logger.info(f"Selected SPY {option_type}: Strike=${best_contract['strike']}, "
                       f"Delta={abs(best_contract['greeks']['delta']):.3f}, "
                       f"IV={best_contract['implied_volatility']:.3f}, "
                       f"Days to expiry={best_contract['days_to_expiry']}, "
                       f"Risk-free rate={r:.3f}")
            
            return best_contract
            
        except Exception as e:
            logger.error(f"Error selecting SPY option: {e}")
            return None
    
    def _calculate_liquidity_score(self, contract_row: pd.Series) -> float:
        """Calculate a liquidity score for SPY option contract"""
        volume = contract_row.get('volume', 0)
        open_interest = contract_row.get('openInterest', 0)
        bid = contract_row.get('bid', 0)
        ask = contract_row.get('ask', 0)
        
        # SPY typically has excellent liquidity, so we can be more stringent
        volume_score = min(volume / 1000, 10)  # Max 10 points
        oi_score = min(open_interest / 5000, 10)  # Max 10 points
        
        # Tighter spread = better liquidity
        if ask > 0 and bid > 0:
            spread_pct = (ask - bid) / ((ask + bid) / 2)
            # SPY typically has very tight spreads
            spread_score = max(0, 10 - (spread_pct * 200))  # More sensitive to spread
        else:
            spread_score = 0
        
        # Combined score (0-30)
        return volume_score + oi_score + spread_score
    
    def validate_contract_liquidity(self, contract: Dict) -> bool:
        """Validate SPY contract has sufficient liquidity"""
        # SPY-specific higher thresholds
        if contract['volume'] < self.config["options"]["min_volume"]:
            logger.warning(f"SPY contract has low volume: {contract['volume']}")
            return False
        
        if contract['open_interest'] < self.config["options"]["min_open_interest"]:
            logger.warning(f"SPY contract has low OI: {contract['open_interest']}")
            return False
        
        # Maximum spread threshold
        if contract.get('spread_pct', 1) > self.config["options"]["max_spread_pct"]:
            logger.warning(f"SPY contract has wide spread: {contract.get('spread_pct', 0):.2%}")
            return False
        
        # Liquidity score threshold
        if contract.get('liquidity_score', 0) < self.config["options"]["min_liquidity_score"]:
            logger.warning(f"SPY contract has low liquidity score: {contract.get('liquidity_score', 0)}")
            return False
        
        return True