"""
ST0CKG Engine - Battle Lines 0-DTE trading
Merged with FastTradingEngine for streamlined architecture
"""
import logging
from datetime import datetime, time, timedelta
from typing import Dict, Optional
import os
import pandas as pd

from .base_engine import BaseEngine
from .unified_market_data import UnifiedMarketData
from .options_selector import FastOptionsSelector
from .trend_filter import TrendFilter
from .multi_bot_database import MultiBotDatabaseManager

logger = logging.getLogger(__name__)


class ST0CKGEngine(BaseEngine):
    """ST0CKG Engine - Battle Lines 0-DTE trading with integrated fast execution"""
    
    def __init__(self, config: dict, capital: float, db_connection_string: str):
        # Initialize with bot_id from config
        self.bot_id = config.get('bot_id', 'st0ckg')
        
        # Call parent constructor to initialize common components
        super().__init__(config, capital, db_connection_string)
        
        # Create multi-bot aware database (replacing the base one)
        self.multi_db = MultiBotDatabaseManager(
            connection_string=db_connection_string,
            bot_id=self.bot_id
        )
        
        # Register bot
        self.multi_db.register_bot(
            bot_id=self.bot_id,
            bot_name='ST0CKG Engine',
            strategy_type='ST0CKGStrategy',
            alpaca_account=os.getenv('ST0CKG_ALPACA_ACCOUNT', 'primary'),
            config=config
        )
        
        # Override database with multi-bot version
        self.db = self.multi_db
        
        # Pre-fetch options for the session
        logger.info("Pre-fetching SPY options for trading session...")
        self.market_data.prefetch_session_data('SPY')
        
        # Initialize engine-specific components
        self.options_selector = FastOptionsSelector(config, self.market_data)
        self.trend_filter = TrendFilter(config)
        
        # Engine-specific state
        self.last_signal_time = None
        self.opening_range_calculated = False
        
        # Trading window - use config if available, otherwise default
        if 'trading_window' in config:
            self.window_start = config['trading_window'].get('start', time(9, 40))
            self.window_end = config['trading_window'].get('end', time(10, 30))
        else:
            # Default trading window
            self.window_start = time(9, 40)
            self.window_end = time(10, 30)
        
        # Initialize ST0CKG strategy
        from bots.st0ckg.strategy import ST0CKGStrategy
        from .error_reporter import ErrorReporter
        
        try:
            self.strategy = ST0CKGStrategy(self.bot_id, config)
            self.strategy.initialize(self.market_data, self.multi_db)
        except Exception as e:
            context = {
                'bot_id': self.bot_id,
                'config': config.get('strategy_name', 'Unknown'),
                'has_database': self.multi_db is not None,
                'market_data_available': self.market_data is not None
            }
            ErrorReporter.report_failure(self.bot_id, e, context)
            raise RuntimeError(f"ST0CKG strategy initialization failed: {str(e)}")
        
        logger.info(f"[{self.bot_id}] ST0CKG Engine initialized with ${capital:,.2f}, trading window: {self.window_start.strftime('%I:%M %p')} - {self.window_end.strftime('%I:%M %p')}")
    
    def run_trading_cycle(self):
        """Single trading cycle - ultra fast"""
        from .error_reporter import ErrorReporter
        
        try:
            # Check if market is open first
            if not self.is_market_open():
                return
            
            current_time = datetime.now().time()
            
            # Log every 30 seconds
            if not hasattr(self, 'last_log_time'):
                self.last_log_time = datetime.now()
                logger.info(f"[{self.bot_id}] First trading cycle at {current_time.strftime('%H:%M:%S')}")
            
            if (datetime.now() - self.last_log_time).seconds >= 30:
                logger.info(f"[{self.bot_id}] Trading cycle at {current_time.strftime('%H:%M:%S')} - Strategy ready")
                self.last_log_time = datetime.now()
            
            # Mark opening range as calculated after 9:40
            if not self.opening_range_calculated and current_time >= time(9, 40):
                self.opening_range_calculated = True
                logger.info(f"[{self.bot_id}] Opening range period complete")
            
            # Check if in trading window using base class method
            if not self.is_within_trading_window():
                return
            
            # Check risk limits using base class method
            if not self.check_risk_limits():
                return
            
            # Get current SPY data
            try:
                spy_quote = self.market_data.get_spy_quote()
                if not spy_quote or spy_quote.get('price', 0) <= 0:
                    raise ValueError(f"Invalid SPY quote received: {spy_quote}")
            except Exception as e:
                context = {
                    'cycle_time': current_time.strftime('%H:%M:%S'),
                    'market_open': self.is_market_open(),
                    'in_trading_window': self.is_within_trading_window()
                }
                ErrorReporter.report_failure(self.bot_id, e, context)
                raise RuntimeError(f"Failed to get market data: {str(e)}")
            
            # Check for signal from strategy
            try:
                # Build market data context
                market_context = {
                    'spy_quote': spy_quote,
                    'recent_bars': self._get_recent_bars(),
                    'volume_ratio': self._calculate_volume_ratio(),
                    'opening_range': self._get_opening_range_data()
                }
                
                signal = self.strategy.check_entry_conditions(spy_quote['price'], market_context)
                if signal:
                    logger.info(f"[{self.bot_id}] Got signal: {signal}")
                    self._process_signal(signal, spy_quote)
            except Exception as e:
                context = {
                    'spy_price': spy_quote.get('price', 'Unknown'),
                    'battle_lines': getattr(self.strategy, 'battle_lines', {}),
                    'has_position': len(self.positions) > 0
                }
                ErrorReporter.report_failure(self.bot_id, e, context)
                
                # Re-raise if critical
                if 'CRITICAL' in str(e):
                    raise
                else:
                    logger.error(f"[{self.bot_id}] Error in strategy: {e}")
            
            # Monitor positions
            self._monitor_positions()
            
        except Exception as e:
            if 'CRITICAL' not in str(e):  # Don't double-report critical errors
                context = {
                    'engine_state': 'run_trading_cycle',
                    'positions_count': len(self.positions),
                    'daily_pnl': self.daily_pnl
                }
                ErrorReporter.report_failure(self.bot_id, e, context)
            raise
    
    def _calculate_opening_range(self):
        """Calculate and cache opening range"""
        try:
            bars = self.market_data.get_5min_bars('SPY', lookback_days=1)
            if bars.empty:
                return
            
            # Get 9:30-9:40 bars
            today_bars = bars[bars.index.date == datetime.now().date()]
            or_bars = today_bars.between_time('09:30', '09:40')
            
            if not or_bars.empty:
                or_high = float(or_bars['high'].max())
                or_low = float(or_bars['low'].min())
                
                self.market_data.set_opening_range('SPY', or_high, or_low)
                logger.info(f"SPY Opening Range: ${or_low:.2f} - ${or_high:.2f}")
        
        except Exception as e:
            logger.error(f"Failed to calculate opening range: {e}")
    
    def _get_recent_bars(self):
        """Get recent price bars for market context"""
        try:
            bars = self.market_data.get_bars('SPY', timeframe='5Min', limit=10)
            if bars is not None and len(bars) > 0:
                return bars.to_dict('records')
        except:
            pass
        return []
    
    def _calculate_volume_ratio(self):
        """Calculate current volume vs average"""
        try:
            # This would need implementation based on your market data
            return 1.0
        except:
            return 1.0
    
    def _get_opening_range_data(self):
        """Get opening range data if available"""
        try:
            # This would need implementation
            return {}
        except:
            return {}
    
    def _process_signal(self, signal: Dict, spy_quote: Dict):
        """Process trading signal with ST0CKG-specific logic"""
        from .error_reporter import ErrorReporter
        
        try:
            logger.info(f"[{self.bot_id}] Processing {signal.get('metadata', {}).get('primary_signal', 'UNKNOWN')} signal")
            
            # Check for duplicate signals
            if self.last_signal_time and (datetime.now() - self.last_signal_time).seconds < 300:
                logger.debug("Signal cooldown active, skipping")
                return
            
            # Get signal type (handle both old and new format)
            signal_type = signal.get('signal_type', signal.get('type', 'UNKNOWN'))
            
            # Select option contract
            try:
                contract = self.options_selector.select_best_option(
                    'SPY', 
                    signal_type,
                    spy_quote['price']
                )
                if not contract:
                    raise ValueError("No suitable option contract found")
                    
                option_symbol = contract.get('contract_symbol')
                if not option_symbol:
                    raise ValueError("Option contract missing symbol")
                    
            except Exception as e:
                context = {
                    'signal_type': signal_type,
                    'spy_price': spy_quote['price'],
                    'signal_metadata': signal.get('metadata', {})
                }
                ErrorReporter.report_failure(self.bot_id, e, context)
                raise RuntimeError(f"Option selection failed: {str(e)}")
        
            # Get fresh quote
            try:
                quotes = self.market_data.get_option_quotes_batch([option_symbol])
                if option_symbol not in quotes:
                    raise ValueError(f"Failed to get quote for {option_symbol}")
                quote = quotes[option_symbol]
            except Exception as e:
                context = {
                    'option_symbol': option_symbol,
                    'signal_type': signal_type
                }
                ErrorReporter.report_failure(self.bot_id, e, context)
                raise RuntimeError(f"Option quote failed: {str(e)}")
            
            # Calculate position size
            try:
                if hasattr(self.strategy, 'calculate_position_size'):
                    position_size = self.strategy.calculate_position_size(signal, quote['mid'])
                else:
                    position_size = self.risk_manager.calculate_position_size(
                        quote['ask'],
                        signal.get('stop_level', spy_quote['price'] * 0.99)
                    )
                
                if position_size <= 0:
                    raise ValueError(f"Invalid position size: {position_size}")
                    
            except Exception as e:
                context = {
                    'option_price': quote['ask'],
                    'account_balance': self.capital,
                    'risk_settings': self.config.get('risk_management', {})
                }
                ErrorReporter.report_failure(self.bot_id, e, context)
                raise RuntimeError(f"Position sizing failed: {str(e)}")
            
            # Place order
            try:
                order_id = self.broker.place_option_order(
                    option_symbol,
                    position_size,
                    'MARKET'
                )
                
                if not order_id:
                    raise ValueError("Broker returned no order ID")
                    
            except Exception as e:
                context = {
                    'option_symbol': option_symbol,
                    'position_size': position_size,
                    'broker_connected': self.broker.is_connected()
                }
                ErrorReporter.report_failure(self.bot_id, e, context)
                raise RuntimeError(f"Order placement failed: {str(e)}")
            
            # Track position
            position_id = f"SPY_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            self.positions[position_id] = {
                'symbol': option_symbol,
                'quantity': position_size,
                'entry_price': quote['ask'],
                'stop_loss': signal.get('stop_level', spy_quote['price'] * 0.99),
                'signal': signal,
                'entry_time': datetime.now(),
                'order_id': order_id
            }
            
            # Log to database
            try:
                self.db.log_trade({
                    'timestamp': datetime.now(),
                    'symbol': 'SPY',
                    'option_symbol': option_symbol,
                    'action': 'BUY',
                    'quantity': position_size,
                    'price': quote['ask'],
                    'signal_type': signal_type,
                    'signal_strength': signal.get('strength', 0)
                })
            except Exception as e:
                # Log but don't fail the trade
                logger.error(f"Failed to log trade to database: {e}")
            
            self.last_signal_time = datetime.now()
            logger.info(f"Opened position: {position_size} {option_symbol} @ ${quote['ask']:.2f}")
            
        except Exception as e:
            # Re-raise all exceptions from signal processing
            raise
    
    def _select_atm_option(self, direction: str, spot_price: float) -> Optional[str]:
        """Select ATM option - ST0CKG specific"""
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
            if quote and quote['volume'] >= self.config.get('option_selection', {}).get('min_volume', 100):
                spread = (quote['ask'] - quote['bid']) / quote['mid'] if quote['mid'] > 0 else float('inf')
                max_spread = self.config.get('option_selection', {}).get('max_spread_pct', 0.02)
                if spread <= max_spread:
                    return option_symbol
            
            # Try adjacent strikes if ATM doesn't work
            for offset in [1, -1, 2, -2]:
                strike = atm_strike + offset
                option_symbol = f"SPY{expiry}{option_type}{strike:08d}"
                
                quote = self.market_data.get_option_quote(option_symbol)
                if quote and quote['volume'] >= self.config.get('option_selection', {}).get('min_volume', 100):
                    spread = (quote['ask'] - quote['bid']) / quote['mid'] if quote['mid'] > 0 else float('inf')
                    if spread <= max_spread:
                        return option_symbol
            
            return None
            
        except Exception as e:
            logger.error(f"Option selection failed: {e}")
            return None
    
    def _monitor_positions(self):
        """Monitor open positions - fast version"""
        from .error_reporter import ErrorReporter
        
        if not self.positions:
            return
        
        try:
            # Get SPY quote once
            spy_quote = self.market_data.get_spy_quote()
            if not spy_quote or spy_quote.get('price', 0) <= 0:
                raise ValueError("Invalid SPY quote for position monitoring")
            current_price = spy_quote['price']
        
            # Get all option quotes in one batch
            symbols = [pos['symbol'] for pos in self.positions.values()]
            try:
                option_quotes = self.market_data.get_option_quotes_batch(symbols)
            except Exception as e:
                context = {
                    'position_count': len(self.positions),
                    'symbols': symbols[:5]  # First 5 symbols only
                }
                ErrorReporter.report_failure(self.bot_id, e, context)
                logger.error(f"Failed to get option quotes: {e}")
                # Continue with SPY-based stops only
                option_quotes = {}
            
            positions_to_close = []
            
            for position_id, position in self.positions.items():
                try:
                    symbol = position['symbol']
                    signal_type = position['signal'].get('signal_type', position['signal'].get('type', 'UNKNOWN'))
                    
                    # Check stop loss based on SPY price
                    if signal_type == 'LONG' and current_price <= position['stop_loss']:
                        positions_to_close.append((position_id, 'STOP_LOSS'))
                    elif signal_type == 'SHORT' and current_price >= position['stop_loss']:
                        positions_to_close.append((position_id, 'STOP_LOSS'))
                    
                    # Check time stop (close all 5 minutes before window end)
                    close_time = datetime.combine(datetime.today(), self.window_end) - timedelta(minutes=5)
                    if datetime.now().time() >= close_time.time():
                        positions_to_close.append((position_id, 'TIME_EXIT'))
                    
                    # Check profit target if we have option quote
                    elif symbol in option_quotes:
                        quote = option_quotes[symbol]
                        current_value = quote.get('bid', 0)
                        if current_value > 0 and position['entry_price'] > 0:
                            pnl_pct = (current_value - position['entry_price']) / position['entry_price']
                            
                            if pnl_pct >= 0.20:  # 20% profit target
                                positions_to_close.append((position_id, 'PROFIT_TARGET'))
                                
                except Exception as e:
                    logger.error(f"Error monitoring position {position_id}: {e}")
                    # Don't let one position error stop monitoring others
            
            # Close positions
            for position_id, reason in positions_to_close:
                try:
                    self._close_position(position_id, reason)
                except Exception as e:
                    context = {
                        'position_id': position_id,
                        'reason': reason,
                        'position_details': self.positions.get(position_id, {})
                    }
                    ErrorReporter.report_failure(self.bot_id, e, context)
                    logger.error(f"Failed to close position {position_id}: {e}")
                    
        except Exception as e:
            context = {
                'positions_count': len(self.positions),
                'engine_state': 'position_monitoring'
            }
            ErrorReporter.report_failure(self.bot_id, e, context)
            raise RuntimeError(f"Position monitoring failed: {str(e)}")
    
    def _close_position(self, position_id: str, reason: str):
        """Close position"""
        from .error_reporter import ErrorReporter
        
        position = self.positions.get(position_id)
        if not position:
            return
        
        try:
            # Place sell order
            order_id = self.broker.place_option_order(
                position['symbol'],
                position['quantity'],
                'MARKET',
                side='SELL'
            )
            
            if not order_id:
                raise ValueError("Failed to get order ID from broker")
            
            # Log to database
            try:
                self.db.log_trade({
                    'timestamp': datetime.now(),
                    'symbol': 'SPY',
                    'option_symbol': position['symbol'],
                    'action': 'SELL',
                    'quantity': position['quantity'],
                    'price': 0,  # Will be filled by broker
                    'signal_type': f"EXIT_{reason}",
                    'signal_strength': 0
                })
            except Exception as e:
                logger.error(f"Failed to log position close to database: {e}")
            
            # Update daily metrics
            # Note: P&L calculation would need actual fill price
            self.update_daily_metrics(0, reason == 'PROFIT_TARGET')
            
            # Remove from positions
            del self.positions[position_id]
            logger.info(f"Closed position {position_id} - Reason: {reason}")
                
        except Exception as e:
            context = {
                'position_id': position_id,
                'reason': reason,
                'symbol': position.get('symbol', 'Unknown'),
                'quantity': position.get('quantity', 0),
                'entry_price': position.get('entry_price', 0)
            }
            ErrorReporter.report_failure(self.bot_id, e, context)
            raise RuntimeError(f"Failed to close position: {str(e)}")
    
    def is_in_active_window(self) -> bool:
        """Check if we're in the active trading window"""
        current_time = datetime.now().time()
        return self.window_start <= current_time <= self.window_end
    
    def shutdown(self):
        """Clean shutdown"""
        # Close all positions
        for position_id in list(self.positions.keys()):
            self._close_position(position_id, "SHUTDOWN")
        
        # Use parent's shutdown
        super().shutdown()
        logger.info(f"[{self.bot_id}] ST0CKG Engine shutdown complete")