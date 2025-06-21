"""
Fast, lean options selector using unified market data
Optimized for SPY trading with minimal API calls
"""

import logging
from typing import Dict, Optional
from datetime import datetime, timedelta
from .unified_market_data import UnifiedMarketData

logger = logging.getLogger(__name__)


class FastOptionsSelector:
    """Lean options selector with aggressive optimization"""
    
    def __init__(self, config: dict, market_data: UnifiedMarketData):
        self.config = config
        self.market_data = market_data
        self.target_delta = config["options"]["target_delta"]
        self.delta_tolerance = config["options"]["delta_tolerance"]
        
        # Cache for option selections (1 minute TTL)
        self._selection_cache = {}
        self._cache_ttl = 60
        
    def select_best_option(self, symbol: str, signal_type: str, 
                          current_price: float) -> Optional[Dict]:
        """
        Select best option contract - ultra fast version
        """
        # Cache key includes price bucket (rounded to nearest dollar)
        price_bucket = int(current_price)
        cache_key = f"{symbol}_{signal_type}_{price_bucket}"
        
        # Check cache
        if cache_key in self._selection_cache:
            cached_time, cached_contract = self._selection_cache[cache_key]
            if (datetime.now().timestamp() - cached_time) < self._cache_ttl:
                logger.info(f"Using cached option selection for {cache_key}")
                return cached_contract
        
        # Get expiration (always use weekly for SPY)
        expiry = self._get_weekly_expiry()
        option_type = 'CALL' if signal_type == 'LONG' else 'PUT'
        
        # Find best options using unified data
        candidates = self.market_data.find_best_options(
            symbol=symbol,
            expiration=expiry,
            option_type=option_type,
            target_delta=self.target_delta
        )
        
        if not candidates:
            logger.warning(f"No suitable options found for {symbol}")
            return None
        
        # Select best candidate
        best = self._select_from_candidates(candidates, current_price)
        
        if best:
            # Cache the selection
            self._selection_cache[cache_key] = (datetime.now().timestamp(), best)
            
            logger.info(f"Selected {best['contract_symbol']} - "
                       f"Strike: ${best['strike']}, Delta: {best['delta']:.3f}, "
                       f"Ask: ${best['ask']:.2f}")
        
        return best
    
    def _select_from_candidates(self, candidates: list, current_price: float) -> Optional[Dict]:
        """Select best option from candidates"""
        if not candidates:
            return None
        
        # Score each candidate
        for candidate in candidates:
            score = 0
            
            # Delta match (most important)
            delta_score = 100 * (1 - candidate['delta_diff'] / 0.1)
            score += delta_score * 0.4
            
            # Liquidity score
            liquidity = candidate['volume'] + candidate['oi'] / 10
            liquidity_score = min(100, liquidity / 10)
            score += liquidity_score * 0.3
            
            # Spread score
            if candidate['ask'] > 0:
                spread_pct = (candidate['ask'] - candidate['bid']) / candidate['ask']
                spread_score = 100 * (1 - min(spread_pct / 0.05, 1))
                score += spread_score * 0.2
            
            # IV score (prefer median IV)
            iv_score = 100 * (1 - abs(candidate['iv'] - 0.20) / 0.20)
            score += max(0, iv_score) * 0.1
            
            candidate['score'] = score
        
        # Sort by score
        candidates.sort(key=lambda x: x['score'], reverse=True)
        
        # Additional validation
        best = candidates[0]
        
        # Ensure minimum liquidity
        if best['volume'] < 50 and best['oi'] < 500:
            logger.warning(f"Low liquidity for {best['contract_symbol']}")
            # Try next candidate
            for candidate in candidates[1:]:
                if candidate['volume'] >= 50 or candidate['oi'] >= 500:
                    best = candidate
                    break
        
        # Final spread check
        if best['ask'] > 0:
            spread_pct = (best['ask'] - best['bid']) / best['ask']
            if spread_pct > self.config["options"]["max_spread_pct"]:
                logger.warning(f"Spread too wide: {spread_pct:.1%}")
                return None
        
        return best
    
    def _get_weekly_expiry(self) -> datetime:
        """Get next weekly expiry for SPY"""
        today = datetime.now()
        days_until_friday = (4 - today.weekday()) % 7
        
        # If it's Friday after market close, use next Friday
        if days_until_friday == 0 and today.hour >= 16:
            days_until_friday = 7
        
        # If less than 2 days to expiry, use next week
        if days_until_friday < 2:
            days_until_friday += 7
        
        return today + timedelta(days=days_until_friday)
    
    def clear_cache(self):
        """Clear selection cache"""
        self._selection_cache.clear()
        logger.info("Cleared options selection cache")