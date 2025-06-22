"""
APEX Simplified Trading Engine
Lean and focused on execution
"""
import logging
from datetime import datetime
from typing import Dict, Optional
import os

from .base_fast_engine import FastTradingEngine
from .multi_bot_database import MultiBotDatabaseManager

logger = logging.getLogger(__name__)


class APEXSimplifiedEngine(FastTradingEngine):
    """Simplified APEX engine - just the essentials"""
    
    def __init__(self, config: dict, capital: float, db_connection_string: str):
        # Initialize with bot_id
        self.bot_id = 'apex'
        
        # Create multi-bot aware database
        self.multi_db = MultiBotDatabaseManager(
            connection_string=db_connection_string,
            bot_id=self.bot_id
        )
        
        # Register bot
        self.multi_db.register_bot(
            bot_id=self.bot_id,
            bot_name='APEX Simplified',
            strategy_type='APEXSimplifiedStrategy',
            alpaca_account=os.getenv('APEX_ALPACA_ACCOUNT', 'primary'),
            config=config
        )
        
        # Initialize parent
        super().__init__(config, capital, db_connection_string)
        
        # Override database with multi-bot version
        self.db = self.multi_db
        
        logger.info(f"[{self.bot_id}] APEX Simplified Engine initialized")
    
    def _process_signal(self, signal: Dict, spy_quote: Dict):
        """Process trading signal"""
        logger.info(f"[{self.bot_id}] Processing {signal.get('metadata', {}).get('signal_type')} signal")
        
        # Find ATM option
        option_symbol = self._select_atm_option(
            signal['direction'],
            spy_quote['last']
        )
        
        if not option_symbol:
            logger.warning(f"[{self.bot_id}] No suitable option found")
            return
            
        # Get option quote
        option_quote = self.market_data.get_option_quote(option_symbol)
        if not option_quote:
            return
            
        # Calculate position size
        contracts = self.strategy.calculate_position_size(
            signal,
            option_quote['mid']
        )
        
        if contracts <= 0:
            return
            
        # Place order
        self._place_option_order(
            symbol=option_symbol,
            quantity=contracts,
            side=signal['direction'],
            limit_price=option_quote['ask'] if signal['direction'] == 'buy' else option_quote['bid']
        )
    
    def _select_atm_option(self, direction: str, spot_price: float) -> Optional[str]:
        """Select ATM option - simplified"""
        try:
            # Round to nearest dollar for SPY
            atm_strike = round(spot_price)
            
            # Get today's expiry
            today = datetime.now()
            expiry = today.strftime('%y%m%d')
            
            # Build option symbol
            option_type = 'C' if direction == 'buy' else 'P'
            option_symbol = f"SPY{expiry}{option_type}{atm_strike:08d}"
            
            # Quick validation
            quote = self.market_data.get_option_quote(option_symbol)
            if quote and quote['volume'] >= self.config['option_selection']['min_volume']:
                spread = (quote['ask'] - quote['bid']) / quote['mid']
                if spread <= self.config['option_selection']['max_spread_pct']:
                    return option_symbol
                    
            # Try adjacent strikes if ATM doesn't work
            for offset in [1, -1, 2, -2]:
                strike = atm_strike + offset
                option_symbol = f"SPY{expiry}{option_type}{strike:08d}"
                
                quote = self.market_data.get_option_quote(option_symbol)
                if quote and quote['volume'] >= self.config['option_selection']['min_volume']:
                    spread = (quote['ask'] - quote['bid']) / quote['mid']
                    if spread <= self.config['option_selection']['max_spread_pct']:
                        return option_symbol
                        
            return None
            
        except Exception as e:
            logger.error(f"Option selection failed: {e}")
            return None