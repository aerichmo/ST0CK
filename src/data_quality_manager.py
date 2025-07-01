"""
Data Quality Manager for handling IEX vs SIP data limitations
Provides smart workarounds for free IEX data feed
"""
from typing import Dict, Optional, Tuple
from datetime import datetime, timedelta
import statistics

from .unified_logging import get_logger


class DataQualityManager:
    """Manages data quality issues with IEX-only feed"""
    
    def __init__(self, market_data_provider):
        self.logger = get_logger(__name__)
        self.market_data = market_data_provider
        self.quality_metrics = {
            'wide_spreads': 0,
            'stale_quotes': 0,
            'adjusted_quotes': 0,
            'estimated_slippage': 0.0
        }
        
        # Thresholds
        self.max_reasonable_spread = {
            'SPY': 0.05,    # 5 cents max for SPY
            'QQQ': 0.05,    # 5 cents max for QQQ
            'IWM': 0.10,    # 10 cents for IWM
            'default': 0.20  # 20 cents for others
        }
    
    async def get_quality_quote(self, symbol: str) -> Dict[str, float]:
        """
        Get quote with quality adjustments for IEX limitations
        
        Returns:
            Dict with price, bid, ask, quality_score
        """
        try:
            # Get raw IEX quote
            quote = await self.market_data.get_quote(symbol)
            if not quote:
                return None
            
            # Check spread quality
            spread = quote['ask'] - quote['bid']
            max_spread = self.max_reasonable_spread.get(symbol, self.max_reasonable_spread['default'])
            
            quality_score = 1.0
            adjusted = False
            
            # If spread is too wide, it's likely stale IEX data
            if spread > max_spread:
                self.quality_metrics['wide_spreads'] += 1
                quality_score *= 0.7
                
                # Estimate tighter spread
                mid_price = (quote['ask'] + quote['bid']) / 2
                estimated_spread = max_spread * 0.6  # Assume real spread is 60% of max
                
                quote['bid'] = mid_price - (estimated_spread / 2)
                quote['ask'] = mid_price + (estimated_spread / 2)
                quote['adjusted'] = True
                adjusted = True
                
                self.logger.warning(
                    f"Wide spread detected for {symbol}: ${spread:.2f}, adjusted to ${estimated_spread:.2f}",
                    extra={'symbol': symbol, 'original_spread': spread}
                )
            
            # Add quality metadata
            quote['quality_score'] = quality_score
            quote['is_adjusted'] = adjusted
            quote['data_source'] = 'IEX'
            
            if adjusted:
                self.quality_metrics['adjusted_quotes'] += 1
            
            return quote
            
        except Exception as e:
            self.logger.error(f"Error getting quality quote for {symbol}: {e}")
            return None
    
    async def get_aggregated_market_view(self) -> Dict[str, float]:
        """
        Get market overview using multiple symbols to compensate for IEX limitations
        """
        symbols = ['SPY', 'QQQ', 'IWM', 'DIA']
        quotes = {}
        
        for symbol in symbols:
            quote = await self.get_quality_quote(symbol)
            if quote:
                quotes[symbol] = quote
        
        if len(quotes) < 2:
            return None
        
        # Calculate market metrics
        avg_quality = statistics.mean([q['quality_score'] for q in quotes.values()])
        
        return {
            'quotes': quotes,
            'avg_quality_score': avg_quality,
            'data_warning': avg_quality < 0.8
        }
    
    def estimate_slippage_cost(self, order_size: int, symbol: str = 'SPY') -> float:
        """
        Estimate potential slippage cost due to IEX data limitations
        """
        # Assume 2-3 cents average slippage for options due to stale quotes
        base_slippage = 0.025  # $0.025 per share
        
        # Adjust for symbol liquidity
        liquidity_multiplier = {
            'SPY': 1.0,
            'QQQ': 1.1,
            'IWM': 1.3
        }.get(symbol, 1.5)
        
        estimated_slippage = order_size * 100 * base_slippage * liquidity_multiplier
        self.quality_metrics['estimated_slippage'] += estimated_slippage
        
        return estimated_slippage
    
    def should_upgrade_data_feed(self) -> Tuple[bool, Dict[str, float]]:
        """
        Analyze if upgrading to SIP data is cost-effective
        """
        # Assume SIP costs $99/month
        sip_monthly_cost = 99.0
        
        # Calculate monthly impact
        days_tracked = max(1, len(self.quality_metrics.get('daily_slippage', [])))
        avg_daily_slippage = self.quality_metrics['estimated_slippage'] / days_tracked
        projected_monthly_slippage = avg_daily_slippage * 20  # 20 trading days
        
        roi_metrics = {
            'current_monthly_slippage': projected_monthly_slippage,
            'sip_monthly_cost': sip_monthly_cost,
            'net_benefit': projected_monthly_slippage - sip_monthly_cost,
            'roi_percentage': ((projected_monthly_slippage - sip_monthly_cost) / sip_monthly_cost * 100)
        }
        
        should_upgrade = roi_metrics['net_benefit'] > 0
        
        if should_upgrade:
            self.logger.info(
                f"Data feed upgrade recommended: ${roi_metrics['net_benefit']:.2f}/month savings",
                extra={'roi_metrics': roi_metrics}
            )
        
        return should_upgrade, roi_metrics
    
    def get_execution_adjustments(self, signal_type: str) -> Dict[str, float]:
        """
        Get execution adjustments based on data quality
        """
        adjustments = {
            'limit_price_buffer': 0.02,  # Add 2 cents to asks for IEX
            'stop_loss_buffer': 0.03,    # Wider stops for uncertainty
            'position_size_multiplier': 0.9  # Slightly smaller positions
        }
        
        # More conservative for certain signals with IEX data
        if signal_type in ['LIQUIDITY_VACUUM', 'DARK_POOL_FLOW']:
            adjustments['position_size_multiplier'] = 0.7  # These need better data
            
        return adjustments
    
    def log_metrics_summary(self):
        """Log daily metrics summary"""
        self.logger.info(
            "Data Quality Metrics",
            extra={
                'metrics': self.quality_metrics,
                'should_upgrade': self.should_upgrade_data_feed()[0]
            }
        )