import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, Optional, List
import logging
from scipy.stats import norm
import time
from .alpaca_options_data import AlpacaOptionsData

logger = logging.getLogger(__name__)

class OptionsSelector:
    def __init__(self, config: dict, alpaca_client=None):
        self.config = config
        self.target_delta = config["options"]["target_delta"]
        self.delta_tolerance = config["options"]["delta_tolerance"]
        self._risk_free_rate_cache = None
        self._risk_free_rate_timestamp = 0
        self._cache_ttl = 3600  # 1 hour cache for risk-free rate
        self._iv_history_cache = {}
        self._vix_cache = None
        self._vix_cache_timestamp = 0
        # Initialize high-speed options data provider
        self.options_data = AlpacaOptionsData(alpaca_client)
        
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
            # Try to get treasury rates from Alpaca if available
            if self.options_data.alpaca_client:
                from alpaca.data import StockHistoricalDataClient
                from alpaca.data.requests import StockLatestQuoteRequest
                
                # Alpaca doesn't provide treasury rates directly, but we can use
                # TLT (20+ year treasury ETF) as a proxy and derive short-term rates
                request = StockLatestQuoteRequest(symbol_or_symbols="TLT")
                quotes = self.options_data.alpaca_client.get_stock_latest_quote(request)
                
                if quotes and "TLT" in quotes:
                    # Use a simplified yield curve model
                    # Long-term rates are typically higher than short-term
                    # Estimate 3-month rate as 0.7x the long-term implied rate
                    tlt_price = quotes["TLT"].ask_price
                    # Rough approximation: TLT yield ≈ 2.5% + (100-price)/20
                    long_rate = 0.025 + (100 - tlt_price) / 2000
                    rate = long_rate * 0.7  # Short-term adjustment
                    
                    self._risk_free_rate_cache = rate
                    self._risk_free_rate_timestamp = time.time()
                    logger.info(f"Updated risk-free rate to {rate:.4f} ({rate*100:.2f}%) from Alpaca")
                    return rate
        except Exception as e:
            logger.warning(f"Failed to fetch risk-free rate from Alpaca: {e}")
        
        # Use current market conditions default (as of 2024-2025)
        # Federal funds rate is around 4.5-5.5%
        # 3-month T-bills typically trade near fed funds rate
        default_rate = 0.048  # 4.8% default based on current environment
        
        # Cache the default rate
        self._risk_free_rate_cache = default_rate
        self._risk_free_rate_timestamp = time.time()
        
        logger.info(f"Using default risk-free rate of {default_rate:.4f} ({default_rate*100:.2f}%)")
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
            # Get dynamic risk-free rate
            r = self.get_risk_free_rate()
            
            # For SPY, try 0DTE first during market hours
            now = datetime.now()
            if now.weekday() < 5 and now.hour >= 9 and now.hour < 16:
                # Try today's expiry first (0DTE)
                expiry_date = now
                logger.info("Looking for 0DTE options for SPY")
            else:
                # Use weekly expiry
                days_until_friday = (4 - now.weekday()) % 7
                if days_until_friday == 0 and now.hour >= 16:
                    days_until_friday = 7
                expiry_date = now + timedelta(days=days_until_friday)
            
            # Determine option type
            option_type = 'CALL' if signal_type == 'LONG' else 'PUT'
            
            # Use high-speed options data provider with criteria
            contracts = self.options_data.find_options_by_criteria(
                symbol=symbol,
                expiration=expiry_date,
                option_type=option_type,
                target_delta=self.target_delta,
                min_volume=self.config["options"]["min_volume"]
            )
            
            if not contracts:
                logger.warning("No liquid contracts found for SPY")
                return None
            
            # Contracts already filtered and sorted by our criteria
            # Just need to enhance with additional calculations
            candidates = []
            
            for contract in contracts:
                # Contract already has all the data we need
                strike = contract['strike']
                bid = contract['bid']
                ask = contract['ask']
                mid_price = contract['mid_price']
                implied_vol = contract.get('implied_volatility', 0.20)
                spread_pct = contract.get('spread_pct', 0)
                if spread_pct > self.config["options"]["max_spread_pct"]:
                    continue
                
                # Calculate time to expiry
                days_to_expiry = contract.get('days_to_expiry', 1)
                T = days_to_expiry / 365.0
                
                # Calculate or use existing Greeks
                if 'delta' in contract and contract['delta'] != 0:
                    greeks = {
                        'delta': contract['delta'],
                        'gamma': contract.get('gamma', 0),
                        'theta': contract.get('theta', 0),
                        'vega': contract.get('vega', 0)
                    }
                else:
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
                    # Build enhanced contract info
                    enhanced_contract = {
                        'symbol': symbol,
                        'contract_symbol': contract['contract_symbol'],
                        'strike': strike,
                        'expiry': contract['expiration'],
                        'option_type': option_type,
                        'bid': bid,
                        'ask': ask,
                        'mid_price': mid_price,
                        'last': contract.get('last', mid_price),
                        'volume': contract['volume'],
                        'open_interest': contract['open_interest'],
                        'implied_volatility': implied_vol,
                        'greeks': greeks,
                        'days_to_expiry': days_to_expiry,
                        'delta_diff': delta_diff,
                        'spread_pct': spread_pct,
                        'liquidity_score': contract['volume'] + contract['open_interest'] / 10,
                        'risk_free_rate': r
                    }
                    candidates.append(enhanced_contract)
            
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
    
    def get_current_vix(self) -> float:
        """Get current VIX level for volatility assessment"""
        # Check cache first
        if (self._vix_cache is not None and 
            time.time() - self._vix_cache_timestamp < 300):  # 5 minute cache
            return self._vix_cache
        
        try:
            vix = yf.Ticker("^VIX")
            hist = vix.history(period="1d")
            
            if not hist.empty and 'Close' in hist.columns:
                vix_level = hist['Close'].iloc[-1]
                self._vix_cache = vix_level
                self._vix_cache_timestamp = time.time()
                return vix_level
        except Exception as e:
            logger.warning(f"Failed to fetch VIX: {e}")
        
        # Default VIX if fetch fails
        return 20.0
    
    def calculate_iv_rank(self, current_iv: float, symbol: str = 'SPY') -> float:
        """Calculate IV rank over last 252 trading days"""
        try:
            # Get historical data if not cached
            if symbol not in self._iv_history_cache:
                ticker = yf.Ticker(symbol)
                hist = ticker.history(period="1y")
                
                if not hist.empty:
                    # Calculate historical volatility for IV rank approximation
                    returns = hist['Close'].pct_change().dropna()
                    rolling_vol = returns.rolling(window=20).std() * np.sqrt(252)
                    self._iv_history_cache[symbol] = rolling_vol.dropna()
            
            if symbol in self._iv_history_cache:
                vol_series = self._iv_history_cache[symbol]
                if len(vol_series) > 0:
                    # Calculate percentile rank
                    rank = (current_iv > vol_series).sum() / len(vol_series)
                    return rank
                    
        except Exception as e:
            logger.warning(f"Failed to calculate IV rank: {e}")
        
        # Default to middle of range if calculation fails
        return 0.5
    
    def assess_option_entry_conditions(self, contract: Dict) -> Dict:
        """Assess whether current conditions are favorable for option entry"""
        current_iv = contract.get('implied_volatility', 0.20)
        vix_level = self.get_current_vix()
        iv_rank = self.calculate_iv_rank(current_iv)
        
        # Assess conditions
        conditions = {
            'vix_level': vix_level,
            'iv_rank': iv_rank,
            'iv_percentile': iv_rank * 100,
            'current_iv': current_iv,
            'favorable': True,
            'warnings': []
        }
        
        # Check for extreme VIX levels
        if vix_level > 30:
            conditions['warnings'].append("VIX above 30 - High volatility environment")
            conditions['favorable'] = False
        elif vix_level < 12:
            conditions['warnings'].append("VIX below 12 - Low volatility may limit profits")
        
        # Check IV rank
        if iv_rank > 0.8:
            conditions['warnings'].append("IV rank above 80% - Options expensive")
            if contract['option_type'] == 'CALL' or contract['option_type'] == 'PUT':
                conditions['favorable'] = False
        elif iv_rank < 0.2:
            conditions['warnings'].append("IV rank below 20% - Options cheap but moves may be limited")
        
        # Check absolute IV levels for SPY
        if current_iv > 0.35:  # 35% IV is high for SPY
            conditions['warnings'].append("Elevated IV - Consider smaller position size")
        elif current_iv < 0.10:  # 10% IV is very low for SPY
            conditions['warnings'].append("Very low IV - Limited profit potential")
        
        return conditions
    
    def select_option_contract_enhanced(self, symbol: str, signal_type: str, 
                                       current_price: float, market_regime: Dict = None) -> Optional[Dict]:
        """Enhanced option selection with IV and spread validation"""
        # Get base contract selection
        contract = self.select_option_contract(symbol, signal_type, current_price)
        
        if not contract:
            return None
        
        # Add entry condition assessment
        entry_conditions = self.assess_option_entry_conditions(contract)
        contract['entry_conditions'] = entry_conditions
        
        # Enhanced spread validation
        spread_analysis = self.analyze_spread_quality(contract)
        contract['spread_analysis'] = spread_analysis
        
        # Adjust selection based on market regime
        if market_regime:
            contract = self.adjust_for_market_regime(contract, market_regime)
        
        # Log comprehensive selection info
        logger.info(f"Option Selection Summary:")
        logger.info(f"  Contract: {contract['contract_symbol']}")
        logger.info(f"  IV Rank: {entry_conditions['iv_percentile']:.1f}%")
        logger.info(f"  VIX: {entry_conditions['vix_level']:.1f}")
        logger.info(f"  Spread Quality: {spread_analysis['quality']}")
        logger.info(f"  Entry Favorable: {entry_conditions['favorable']}")
        
        if entry_conditions['warnings']:
            for warning in entry_conditions['warnings']:
                logger.warning(f"  ⚠️  {warning}")
        
        return contract
    
    def analyze_spread_quality(self, contract: Dict) -> Dict:
        """Analyze bid-ask spread quality"""
        bid = contract['bid']
        ask = contract['ask']
        mid = contract['mid_price']
        
        spread = ask - bid
        spread_pct = contract['spread_pct']
        
        # Calculate spread in cents
        spread_cents = spread * 100
        
        # Assess quality based on SPY standards
        if spread_cents <= 1:
            quality = "EXCELLENT"
            score = 10
        elif spread_cents <= 2:
            quality = "GOOD"
            score = 8
        elif spread_cents <= 5:
            quality = "FAIR"
            score = 6
        elif spread_cents <= 10:
            quality = "POOR"
            score = 4
        else:
            quality = "VERY_POOR"
            score = 2
        
        # Calculate slippage estimates
        aggressive_fill = ask if contract['option_type'] in ['CALL', 'PUT'] else bid
        passive_fill = bid if contract['option_type'] in ['CALL', 'PUT'] else ask
        
        slippage_aggressive = abs(aggressive_fill - mid) / mid
        slippage_passive = abs(passive_fill - mid) / mid
        
        return {
            'spread': spread,
            'spread_cents': spread_cents,
            'spread_pct': spread_pct,
            'quality': quality,
            'score': score,
            'slippage_aggressive': slippage_aggressive,
            'slippage_passive': slippage_passive,
            'recommended_order_type': 'LIMIT' if spread_cents > 2 else 'MARKET'
        }
    
    def adjust_for_market_regime(self, contract: Dict, market_regime: Dict) -> Dict:
        """Adjust option selection based on market regime"""
        regime = market_regime.get('regime', 'NORMAL')
        
        # In high volatility, consider lower delta options
        if regime == 'HIGH_VOLATILITY':
            contract['adjusted_position_size_mult'] = 0.75
            contract['regime_notes'] = "Consider lower delta or spreads in high vol"
        
        # In trending markets, standard selection is fine
        elif regime == 'TRENDING':
            contract['adjusted_position_size_mult'] = 1.0
            contract['regime_notes'] = "Favorable regime for directional options"
        
        # In choppy markets, be more selective
        elif regime == 'CHOPPY':
            contract['adjusted_position_size_mult'] = 0.5
            contract['regime_notes'] = "Reduce size or avoid in choppy conditions"
        
        else:
            contract['adjusted_position_size_mult'] = 1.0
            contract['regime_notes'] = "Normal market conditions"
        
        return contract