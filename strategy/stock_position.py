"""
Stock position initialization for ST0CK strategies
Handles initial position setup for stock-based strategies
"""

import logging
import config
from portfolio.position_manager import PositionManager

logger = logging.getLogger(__name__)


async def open_initial_position_stocks(position_manager: PositionManager):
    """
    Initialize position for stock-based strategies (ST0CKA)
    Unlike options strategies, we don't need an initial position
    """
    logger.info(f"Initializing stock-based strategy for {config.HEDGING_ASSET}")
    
    # For ST0CKA, we start with no position
    # The strategy will create positions as signals occur
    
    # Clear any existing positions if in 'init' mode
    if config.INITIALIZATION_MODE == 'init':
        try:
            # Get current positions
            positions = position_manager.trading_client.get_all_positions()
            
            # Close any SPY positions
            for position in positions:
                if position.symbol == config.HEDGING_ASSET:
                    logger.info(f"Closing existing position: {position.symbol} qty: {position.qty}")
                    position_manager.trading_client.close_position(position.symbol)
            
            logger.info("Cleared existing positions")
            
        except Exception as e:
            logger.error(f"Error clearing positions: {e}")
    
    # Set position attributes for compatibility
    position_manager.call_option_symbol = None
    position_manager.put_option_symbol = None
    position_manager.stock_shares_held = 0
    
    logger.info("Stock strategy initialization complete")
    return True


async def calculate_volatility_metrics(position_manager: PositionManager):
    """
    Calculate volatility metrics for position sizing
    """
    try:
        from alpaca.data.requests import StockBarsRequest
        from alpaca.data.timeframe import TimeFrame
        from datetime import datetime, timedelta
        import numpy as np
        
        # Get historical data for volatility calculation
        data_client = position_manager.stock_data_client
        
        request = StockBarsRequest(
            symbol_or_symbols=config.HEDGING_ASSET,
            timeframe=TimeFrame.Day,
            start=datetime.now() - timedelta(days=30),
            end=datetime.now()
        )
        
        bars = data_client.get_stock_bars(request)
        
        if config.HEDGING_ASSET in bars:
            # Calculate daily returns
            prices = [bar.close for bar in bars[config.HEDGING_ASSET]]
            returns = []
            
            for i in range(1, len(prices)):
                ret = (prices[i] - prices[i-1]) / prices[i-1]
                returns.append(ret)
            
            # Calculate realized volatility
            if returns:
                volatility = np.std(returns) * np.sqrt(252)  # Annualized
                logger.info(f"Calculated volatility for {config.HEDGING_ASSET}: {volatility:.2%}")
                return volatility
        
        # Default volatility if calculation fails
        return 0.15
        
    except Exception as e:
        logger.error(f"Error calculating volatility: {e}")
        return 0.15


def get_position_size_for_volatility(volatility: float) -> int:
    """
    Calculate position size based on volatility
    """
    config_st0cka = config.ST0CKA_CONFIG
    
    if not config_st0cka['use_volatility_sizing']:
        return config_st0cka['position_size_min']
    
    # Volatility thresholds
    vol_config = config.VOLATILITY_CONFIG
    
    if volatility < vol_config['low_vol_threshold']:
        # Low volatility - trade more shares
        return config_st0cka['position_size_max']
    elif volatility > vol_config['high_vol_threshold']:
        # High volatility - trade fewer shares
        return config_st0cka['position_size_min']
    else:
        # Medium volatility - interpolate
        vol_range = vol_config['high_vol_threshold'] - vol_config['low_vol_threshold']
        position_range = config_st0cka['position_size_max'] - config_st0cka['position_size_min']
        
        # Linear interpolation (inverse relationship)
        vol_factor = (volatility - vol_config['low_vol_threshold']) / vol_range
        position_adjustment = int(position_range * (1 - vol_factor))
        
        return config_st0cka['position_size_min'] + position_adjustment