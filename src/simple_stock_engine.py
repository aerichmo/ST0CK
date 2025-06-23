"""
Simple stock trading engine for basic stock trades
No options, just buy/sell stocks
"""
import logging
import time
from datetime import datetime
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class SimpleStockEngine:
    """Simple engine for stock-only trading strategies"""
    
    def __init__(self, config: Dict, capital: float, db_connection_string: str):
        self.config = config
        self.capital = capital
        self.db_connection_string = db_connection_string
        
        # Initialize components
        self.broker = None
        self.strategy = None
        self.database = None
        self.is_running = False
        self.positions = {}
        
        # Trading state
        self.trades_today = 0
        self.daily_pnl = 0.0
        
        logger.info(f"Initialized SimpleStockEngine with ${capital:,.2f} capital")
        
        # Initialize components
        self._initialize_components()
        
    def _initialize_components(self):
        """Initialize broker, strategy, and database"""
        try:
            # Initialize broker
            from src.alpaca_broker import AlpacaBroker
            self.broker = AlpacaBroker(
                api_key=self.config['alpaca']['api_key'],
                secret_key=self.config['alpaca']['secret_key'],
                base_url=self.config['alpaca'].get('base_url'),
                paper=self.config['alpaca'].get('paper', True)
            )
            
            if not self.broker.connect():
                raise RuntimeError("Failed to connect to broker")
                
            # Initialize strategy
            bot_id = self.config['bot_id']
            if bot_id == 'st0cka':
                from bots.st0cka.strategy import ST0CKAStrategy
                self.strategy = ST0CKAStrategy(bot_id, self.config)
            else:
                raise ValueError(f"Unknown bot_id: {bot_id}")
                
            # Initialize strategy
            if not self.strategy.initialize(None):  # ST0CKA doesn't need market data
                raise RuntimeError("Failed to initialize strategy")
                
            # Initialize database
            from src.multi_bot_database import MultiBotDatabaseManager
            self.database = MultiBotDatabaseManager(
                self.db_connection_string,
                bot_id=bot_id
            )
            
            logger.info("All components initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize components: {e}")
            raise
            
    def is_in_active_window(self) -> bool:
        """Check if we're in active trading window"""
        now = datetime.now()
        window = self.config.get('trading_window', {})
        start = window.get('start')
        end = window.get('end')
        
        if start and end:
            return start <= now.time() <= end
        return True
        
    def run_trading_cycle(self):
        """Run one trading cycle"""
        try:
            if not self.is_in_active_window():
                return
                
            # Get current price for SPY
            symbol = self.config.get('symbol', 'SPY')
            
            # For now, use a simple approach - just let the strategy decide
            # ST0CKA will check if it's market open time
            current_price = 0.0  # Price will be determined by market order
            
            # Check entry conditions
            signal = self.strategy.check_entry_conditions(current_price, {})
            
            if signal and self.strategy.validate_signal(signal):
                # Place buy order
                self._execute_entry(signal, current_price)
                
            # Check exit conditions for existing positions
            self._check_exits(current_price)
            
        except Exception as e:
            logger.error(f"Error in trading cycle: {e}")
            
    def _execute_entry(self, signal, current_price):
        """Execute entry trade"""
        try:
            symbol = self.config.get('symbol', 'SPY')
            
            # Always buy 1 share for ST0CKA
            quantity = 1
            
            # Place market buy order
            order_id = self.broker.place_stock_order(
                symbol=symbol,
                quantity=quantity,
                side='BUY',
                order_type='MARKET'
            )
            
            if order_id:
                logger.info(f"Placed buy order for {quantity} shares of {symbol}")
                
                # Wait for fill
                time.sleep(2)
                
                # Get fill price
                order_status = self.broker.get_order_status(order_id)
                if order_status and order_status['status'] == 'filled':
                    fill_price = order_status['avg_fill_price']
                    
                    # Place sell limit order for $0.01 profit
                    sell_price = fill_price + self.config.get('profit_target', 0.01)
                    
                    sell_order_id = self.broker.place_stock_order(
                        symbol=symbol,
                        quantity=quantity,
                        side='SELL',
                        order_type='LIMIT',
                        limit_price=sell_price,
                        time_in_force='GTC'
                    )
                    
                    if sell_order_id:
                        logger.info(f"Placed GTC sell order at ${sell_price:.2f} (${self.config.get('profit_target', 0.01)} profit)")
                        
                        # Track position
                        self.positions[symbol] = {
                            'entry_price': fill_price,
                            'quantity': quantity,
                            'sell_order_id': sell_order_id,
                            'entry_time': datetime.now()
                        }
                        
                        # Notify strategy
                        self.strategy.on_position_opened({
                            'symbol': symbol,
                            'entry_price': fill_price,
                            'quantity': quantity
                        })
                        
                        # Log to database
                        self.database.log_trade(
                            symbol=symbol,
                            action='BUY',
                            quantity=quantity,
                            price=fill_price,
                            order_type='MARKET',
                            reason='market_open'
                        )
                        
        except Exception as e:
            logger.error(f"Failed to execute entry: {e}")
            
    def _check_exits(self, current_price):
        """Check exit conditions"""
        # For ST0CKA, exits are handled by GTC limit orders
        # Just check if orders have been filled
        for symbol, position in list(self.positions.items()):
            try:
                sell_order_id = position.get('sell_order_id')
                if sell_order_id:
                    order_status = self.broker.get_order_status(sell_order_id)
                    if order_status and order_status['status'] == 'filled':
                        # Position closed
                        fill_price = order_status['avg_fill_price']
                        pnl = (fill_price - position['entry_price']) * position['quantity']
                        
                        logger.info(f"Position closed: {symbol} at ${fill_price:.2f}, PnL: ${pnl:.2f}")
                        
                        # Notify strategy
                        self.strategy.on_position_closed(position, pnl, 'target')
                        
                        # Log to database
                        self.database.log_trade(
                            symbol=symbol,
                            action='SELL',
                            quantity=position['quantity'],
                            price=fill_price,
                            order_type='LIMIT',
                            reason='profit_target'
                        )
                        
                        # Remove from positions
                        del self.positions[symbol]
                        
            except Exception as e:
                logger.error(f"Error checking exit for {symbol}: {e}")
                
    def shutdown(self):
        """Shutdown the engine"""
        logger.info("Shutting down SimpleStockEngine")
        self.is_running = False
        
        if self.broker:
            self.broker.disconnect()
            
        logger.info("SimpleStockEngine shutdown complete")