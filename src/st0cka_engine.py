"""
ST0CKA Engine - Simple SPY scalping strategy
Buy 1 share of SPY at market open and sell with $0.01 profit GTC
"""
import logging
import sys
from datetime import datetime, time as datetime_time
from typing import Dict, Optional, Any
import pytz

from .base_engine import BaseEngine
from .unified_market_data import UnifiedMarketData
from bots.st0cka.strategy import ST0CKAStrategy

logger = logging.getLogger(__name__)


class ST0CKAEngine(BaseEngine):
    """
    ST0CKA Engine - Simple SPY scalping with $0.01 profit target
    Supports both simple single-position and advanced multi-position modes
    """
    
    def __init__(self, config: dict, capital: float, db_connection_string: str):
        """Initialize unified simple engine with configuration"""
        # Call parent constructor
        super().__init__(config, capital, db_connection_string)
        
        # Engine mode configuration
        self.mode = config.get('engine_mode', 'simple')  # 'simple' or 'advanced'
        self.symbol = config.get('symbol', 'SPY')
        self.use_market_data = config.get('use_market_data', True)
        self.auto_shutdown = config.get('auto_shutdown', False)
        
        # Trading configuration
        self.profit_target = config.get('profit_target', 0.01)
        self.max_positions = config.get('max_positions', 1)
        self.track_daily_stats = config.get('track_daily_stats', False)
        
        # Trading windows
        self.buy_window = config.get('buy_window', {
            'start': datetime_time(9, 30),
            'end': datetime_time(10, 0)
        })
        self.sell_window = config.get('sell_window', {
            'start': datetime_time(10, 0),
            'end': datetime_time(11, 0)
        })
        self.shutdown_time = config.get('shutdown_time', datetime_time(11, 0))
        
        # Initialize strategy
        self.strategy = ST0CKAStrategy(self.bot_id, config)
        
        # Position tracking based on mode
        if self.mode == 'simple':
            # Simple state tracking (ST0CKA style)
            self.have_position = False
            self.entry_price = None
            self.sell_order_id = None
            self.position_id = None
        else:
            # Advanced state tracking (SimpleStockEngine style)
            self.positions = {}  # position_id -> position info
            if self.track_daily_stats:
                self.trades_today = 0
                self.daily_pnl = 0.0
        
        # Market data (optional)
        if self.use_market_data and not hasattr(self, 'market_data'):
            self.market_data = UnifiedMarketData()
        
        logger.info("Initialized ST0CKAEngine in %s mode for %s", 
                   self.mode, self.symbol)
    
    def run_trading_cycle(self):
        """Main trading cycle"""
        try:
            # Check if market is open first
            if not self.is_market_open():
                return
            
            now_et = datetime.now(pytz.timezone('America/New_York'))
            current_time = now_et.time()
            
            # Check for auto shutdown
            if self.auto_shutdown and current_time >= self.shutdown_time:
                logger.info("Auto shutdown time reached. Exiting.")
                if self.mode == 'simple' and self.have_position:
                    self._sell_position_market("SHUTDOWN")
                sys.exit(0)
            
            # Simple mode logic
            if self.mode == 'simple':
                self._run_simple_cycle(current_time)
            else:
                # Advanced mode logic
                self._run_advanced_cycle(current_time)
                
        except Exception as e:
            logger.error("Error in trading cycle: %s", e)
    
    def _run_simple_cycle(self, current_time: datetime_time):
        """Run simple single-position trading cycle"""
        # Buy logic
        if not self.have_position:
            if self.buy_window['start'] <= current_time <= self.buy_window['end']:
                self._buy_position()
        else:
            # Check if we should sell
            if self.sell_window['start'] <= current_time <= self.sell_window['end']:
                self._check_sell_simple()
    
    def _run_advanced_cycle(self, current_time: datetime_time):
        """Run advanced multi-position trading cycle"""
        # Check if we can open new positions
        if len(self.positions) < self.max_positions:
            if self.buy_window['start'] <= current_time <= self.buy_window['end']:
                # Check if strategy has signal
                signal = self.strategy.check_entry_conditions(self._get_market_data())
                if signal and signal.is_valid():
                    self._open_position_advanced(signal)
        
        # Monitor existing positions
        for position_id in list(self.positions.keys()):
            if self.sell_window['start'] <= current_time <= self.sell_window['end']:
                self._check_sell_advanced(position_id)
    
    def _buy_position(self):
        """Buy position (simple mode)"""
        try:
            # Place market order
            order_data = {
                'symbol': self.symbol,
                'qty': 1,
                'side': 'buy',
                'type': 'market',
                'time_in_force': 'day'
            }
            
            order = self.broker.submit_order(**order_data)
            
            if order:
                logger.info("Buy order placed: %s", order.id)
                self.position_id = f"{self.bot_id}_{order.id}"
                
                # Wait for fill
                filled_order = self._wait_for_fill(order.id)
                if filled_order:
                    self.have_position = True
                    self.entry_price = float(filled_order.filled_avg_price)
                    logger.info("Bought %s at $%.2f", self.symbol, self.entry_price)
                    
                    # Log to database
                    self._log_entry(filled_order)
                    
        except Exception as e:
            logger.error("Failed to buy %s: %s", self.symbol, e)
    
    def _check_sell_simple(self):
        """Check and execute sell logic (simple mode)"""
        if not self.have_position:
            return
        
        try:
            # First try limit order at profit target
            if not self.sell_order_id:
                target_price = self.entry_price + self.profit_target
                
                order_data = {
                    'symbol': self.symbol,
                    'qty': 1,
                    'side': 'sell',
                    'type': 'limit',
                    'limit_price': round(target_price, 2),
                    'time_in_force': 'day'
                }
                
                order = self.broker.submit_order(**order_data)
                if order:
                    self.sell_order_id = order.id
                    logger.info("Sell limit order placed at $%.2f", target_price)
            else:
                # Check if order filled
                order = self.broker.get_order(self.sell_order_id)
                if order and order.status == 'filled':
                    self._handle_sell_fill(order)
                elif order and order.status in ['canceled', 'rejected']:
                    self.sell_order_id = None
            
            # Check if we should sell at market
            current_time = datetime.now(pytz.timezone('America/New_York')).time()
            if current_time >= datetime_time(10, 55):
                current_price = self._get_current_price()
                if current_price and current_price >= self.entry_price:
                    logger.info("Near end of window, selling at breakeven or better")
                    self._sell_position_market("TIME_EXIT")
                    
        except Exception as e:
            logger.error("Error in sell check: %s", e)
    
    def _sell_position_market(self, reason: str):
        """Sell position at market (simple mode)"""
        try:
            # Cancel any open sell orders first
            if self.sell_order_id:
                self.broker.cancel_order(self.sell_order_id)
                self.sell_order_id = None
            
            # Place market order
            order_data = {
                'symbol': self.symbol,
                'qty': 1,
                'side': 'sell',
                'type': 'market',
                'time_in_force': 'day'
            }
            
            order = self.broker.submit_order(**order_data)
            if order:
                filled_order = self._wait_for_fill(order.id)
                if filled_order:
                    self._handle_sell_fill(filled_order, reason)
                    
        except Exception as e:
            logger.error("Failed to sell at market: %s", e)
    
    def _handle_sell_fill(self, order, reason: str = "LIMIT_FILL"):
        """Handle filled sell order"""
        exit_price = float(order.filled_avg_price)
        pnl = exit_price - self.entry_price
        
        logger.info("Sold %s at $%.2f, PnL: $%.2f", 
                   self.symbol, exit_price, pnl)
        
        # Log to database
        self._log_exit(order, reason, pnl)
        
        # Reset state
        self.have_position = False
        self.entry_price = None
        self.sell_order_id = None
        self.position_id = None
        
        # Update daily stats if tracking
        if self.track_daily_stats:
            self.daily_pnl += pnl
            self.trades_today += 1
    
    def _get_current_price(self) -> Optional[float]:
        """Get current price of symbol"""
        if self.use_market_data and self.market_data:
            quote = self.market_data.get_spy_quote() if self.symbol == 'SPY' else None
            if quote:
                return quote.get('price', 0)
        return None
    
    def _get_market_data(self) -> Dict:
        """Get market data for strategy"""
        return {
            'symbol': self.symbol,
            'price': self._get_current_price() or 0,
            'timestamp': datetime.now()
        }
    
    def _wait_for_fill(self, order_id: str, timeout: int = 10):
        """Wait for order to fill"""
        import time
        for _ in range(timeout):
            order = self.broker.get_order(order_id)
            if order and order.status == 'filled':
                return order
            time.sleep(1)
        return None
    
    def _log_entry(self, order):
        """Log position entry to database"""
        if self.db:
            self.db.log_trade_entry(
                position_id=self.position_id,
                symbol=self.symbol,
                signal_type='BUY',
                entry_price=float(order.filled_avg_price),
                quantity=int(order.qty),
                order_id=order.id
            )
    
    def _log_exit(self, order, reason: str, pnl: float):
        """Log position exit to database"""
        if self.db:
            self.db.log_trade_exit(
                position_id=self.position_id,
                exit_price=float(order.filled_avg_price),
                exit_reason=reason,
                realized_pnl=pnl,
                order_id=order.id
            )
    
    def _open_position_advanced(self, signal):
        """Open position in advanced mode"""
        # Implementation for advanced mode
        # Similar to SimpleStockEngine's open_position logic
        pass
    
    def _check_sell_advanced(self, position_id: str):
        """Check sell conditions in advanced mode"""
        # Implementation for advanced mode
        # Similar to SimpleStockEngine's monitor_positions logic
        pass
    
    def _monitor_positions(self):
        """Monitor positions (required by base class)"""
        # Handled in run_trading_cycle
        pass
    
    def _process_signal(self, signal: Dict[str, Any]):
        """Process signal (required by base class)"""
        # Handled in run_trading_cycle
        pass
    
    def _close_position(self, position_id: str, reason: str):
        """Close position (required by base class)"""
        if self.mode == 'simple':
            self._sell_position_market(reason)
        else:
            # Advanced mode close logic
            pass