"""
ST0CKG-specific trading engine implementation
Adapts the fast trading engine for multi-bot architecture
"""
import logging
from datetime import datetime, time
from typing import Dict, Optional
import os

from .base_fast_engine import FastTradingEngine
from .multi_bot_database import MultiBotDatabaseManager

logger = logging.getLogger(__name__)


class St0ckgTradingEngine(FastTradingEngine):
    """ST0CKG trading engine with multi-bot support"""
    
    def __init__(self, config: dict, capital: float, db_connection_string: str):
        # Initialize with bot_id
        self.bot_id = 'st0ckg'
        
        # Create multi-bot aware database
        self.multi_db = MultiBotDatabaseManager(
            connection_string=db_connection_string,
            bot_id=self.bot_id
        )
        
        # Register bot
        self.multi_db.register_bot(
            bot_id=self.bot_id,
            bot_name='ST0CK-G Opening Range Breakout',
            strategy_type='OpeningRangeBreakout',
            alpaca_account=os.getenv('ST0CKG_ALPACA_ACCOUNT', 'primary'),
            config=config
        )
        
        # Initialize parent with original database interface
        super().__init__(config, capital, db_connection_string)
        
        # Override database with multi-bot version
        self.db = self.multi_db
        
        logger.info(f"[{self.bot_id}] Engine initialized with multi-bot support")
    
    def _process_signal(self, signal: Dict, spy_quote: Dict):
        """Process trading signal with bot_id tracking"""
        logger.info(f"[{self.bot_id}] Processing {signal['type']} signal at ${signal['price']:.2f}")
        
        # Select option
        contract = self.options_selector.select_best_option(
            'SPY', 
            signal['type'], 
            spy_quote['price']
        )
        
        if not contract:
            logger.warning(f"[{self.bot_id}] No suitable option found")
            return
        
        # Get fresh quote
        quotes = self.market_data.get_option_quotes_batch([contract['contract_symbol']])
        if contract['contract_symbol'] not in quotes:
            logger.error(f"[{self.bot_id}] Failed to get option quote")
            return
        
        quote = quotes[contract['contract_symbol']]
        
        # Calculate position size
        position_size = self.risk_manager.calculate_position_size(
            quote['ask'],
            signal['stop_level']
        )
        
        if position_size <= 0:
            logger.warning(f"[{self.bot_id}] Position size too small")
            return
        
        # Place order
        order = self.broker.place_option_order(
            contract['contract_symbol'],
            'BUY',
            position_size,
            'MARKET'
        )
        
        if order:
            # Track position
            position_id = f"{self.bot_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            self.positions[position_id] = {
                'symbol': contract['contract_symbol'],
                'quantity': position_size,
                'entry_price': quote['ask'],
                'stop_loss': signal['stop_level'],
                'signal': signal,
                'entry_time': datetime.now(),
                'order_id': order['id']
            }
            
            # Log to database with bot_id
            self.multi_db.log_trade({
                'timestamp': datetime.now(),
                'symbol': 'SPY',
                'option_symbol': contract['contract_symbol'],
                'action': 'BUY',
                'quantity': position_size,
                'price': quote['ask'],
                'signal_type': signal['type'],
                'signal_strength': signal['strength']
            })
            
            self.last_signal_time = datetime.now()
            logger.info(f"[{self.bot_id}] Opened position: {position_size} {contract['contract_symbol']} @ ${quote['ask']:.2f}")
    
    def _close_position(self, position_id: str, reason: str):
        """Close position with bot_id tracking"""
        position = self.positions.get(position_id)
        if not position:
            return
        
        try:
            # Place sell order
            order = self.broker.place_option_order(
                position['symbol'],
                'SELL',
                position['quantity'],
                'MARKET'
            )
            
            if order:
                # Log to database with bot_id
                self.multi_db.log_trade({
                    'timestamp': datetime.now(),
                    'symbol': 'SPY',
                    'option_symbol': position['symbol'],
                    'action': 'SELL',
                    'quantity': position['quantity'],
                    'price': 0,  # Will be filled by broker
                    'signal_type': f"EXIT_{reason}",
                    'signal_strength': 0
                })
                
                # Remove from positions
                del self.positions[position_id]
                logger.info(f"[{self.bot_id}] Closed position {position_id} - Reason: {reason}")
                
        except Exception as e:
            logger.error(f"[{self.bot_id}] Failed to close position: {e}")
    
    def shutdown(self):
        """Clean shutdown with final metrics logging"""
        # Log final risk metrics
        account_info = self.broker.get_account_info()
        if account_info:
            self.multi_db.log_risk_metrics({
                'current_equity': account_info.get('equity', self.capital),
                'daily_pnl': self.risk_manager.daily_pnl,
                'daily_pnl_pct': (self.risk_manager.daily_pnl / self.capital) * 100,
                'consecutive_losses': self.risk_manager.consecutive_losses,
                'active_positions': len(self.positions),
                'trades_today': self.risk_manager.trades_today,
                'trading_enabled': False
            })
        
        # Call parent shutdown
        super().shutdown()
        
        logger.info(f"[{self.bot_id}] Shutdown complete")
    
    def is_in_active_window(self) -> bool:
        """Check if in active trading window"""
        current_time = datetime.now().time()
        return self.window_start <= current_time <= self.window_end