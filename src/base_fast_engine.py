"""
Fast, lean trading engine optimized for SPY options
Minimal overhead, maximum speed
"""

import logging
from datetime import datetime, time
from typing import Dict, Optional
import pandas as pd

from .unified_market_data import UnifiedMarketData
from .options_selector import FastOptionsSelector
from .alpaca_broker import AlpacaBroker
from .trend_filter import TrendFilter
from .risk_manager import RiskManager
from .database import DatabaseManager

logger = logging.getLogger(__name__)


class FastTradingEngine:
    """Lean trading engine with minimal overhead"""
    
    def __init__(self, config: dict, capital: float, db_connection_string: str):
        self.config = config
        self.capital = capital
        
        # Initialize unified market data
        self.market_data = UnifiedMarketData()
        
        # Pre-fetch options for the session
        logger.info("Pre-fetching SPY options for trading session...")
        self.market_data.prefetch_session_data('SPY')
        
        # Initialize components
        self.broker = AlpacaBroker(
            config["alpaca"]["api_key"],
            config["alpaca"]["secret_key"],
            config["alpaca"]["paper"]
        )
        self.broker.connect()
        
        self.options_selector = FastOptionsSelector(config, self.market_data)
        self.trend_filter = TrendFilter(config)
        self.risk_manager = RiskManager(config, capital)
        
        # Database is mandatory
        self.db = DatabaseManager(db_connection_string)
        
        # Trading state
        self.positions = {}
        self.last_signal_time = None
        self.opening_range_calculated = False
        
        # Trading window
        self.window_start = time(9, 40)
        self.window_end = time(10, 30)
        
        logger.info(f"FastTradingEngine initialized with ${capital:,.2f}")
    
    def run_trading_cycle(self):
        """Single trading cycle - ultra fast"""
        try:
            current_time = datetime.now().time()
            
            # Calculate opening range once
            if not self.opening_range_calculated and current_time >= time(9, 40):
                self._calculate_opening_range()
                self.opening_range_calculated = True
            
            # Check if in trading window
            if not (self.window_start <= current_time <= self.window_end):
                return
            
            # Check risk limits
            allowed, reason = self.risk_manager.check_trade_allowed()
            if not allowed:
                logger.debug(f"Trading not allowed: {reason}")
                return
            
            # Get current SPY data
            spy_quote = self.market_data.get_spy_quote()
            if spy_quote['price'] <= 0:
                return
            
            # Check for signal
            signal = self._check_for_signal(spy_quote)
            if signal:
                self._process_signal(signal, spy_quote)
            
            # Monitor positions
            self._monitor_positions()
            
        except Exception as e:
            logger.error(f"Error in trading cycle: {e}")
    
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
    
    def _check_for_signal(self, spy_quote: Dict) -> Optional[Dict]:
        """Check for trading signal"""
        or_data = self.market_data.get_opening_range('SPY')
        if not or_data:
            return None
        
        current_price = spy_quote['price']
        
        # Simple breakout check
        signal = None
        if current_price > or_data['high'] * 1.001:  # 0.1% above high
            signal = {
                'type': 'LONG',
                'price': current_price,
                'stop_level': or_data['low'],
                'or_high': or_data['high'],
                'or_low': or_data['low'],
                'strength': min((current_price - or_data['high']) / or_data['range'], 1.0)
            }
        elif current_price < or_data['low'] * 0.999:  # 0.1% below low
            signal = {
                'type': 'SHORT',
                'price': current_price,
                'stop_level': or_data['high'],
                'or_high': or_data['high'],
                'or_low': or_data['low'],
                'strength': min((or_data['low'] - current_price) / or_data['range'], 1.0)
            }
        
        # Avoid duplicate signals
        if signal and self.last_signal_time:
            if (datetime.now() - self.last_signal_time).seconds < 300:  # 5 min cooldown
                return None
        
        return signal
    
    def _process_signal(self, signal: Dict, spy_quote: Dict):
        """Process trading signal - streamlined"""
        logger.info(f"Processing {signal['type']} signal at ${signal['price']:.2f}")
        
        # Select option
        contract = self.options_selector.select_best_option(
            'SPY', 
            signal['type'], 
            spy_quote['price']
        )
        
        if not contract:
            logger.warning("No suitable option found")
            return
        
        # Get fresh quote
        quotes = self.market_data.get_option_quotes_batch([contract['contract_symbol']])
        if contract['contract_symbol'] not in quotes:
            logger.error("Failed to get option quote")
            return
        
        quote = quotes[contract['contract_symbol']]
        
        # Calculate position size
        position_size = self.risk_manager.calculate_position_size(
            quote['ask'],
            signal['stop_level']
        )
        
        if position_size <= 0:
            logger.warning("Position size too small")
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
            position_id = f"SPY_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            self.positions[position_id] = {
                'symbol': contract['contract_symbol'],
                'quantity': position_size,
                'entry_price': quote['ask'],
                'stop_loss': signal['stop_level'],
                'signal': signal,
                'entry_time': datetime.now(),
                'order_id': order['id']
            }
            
            # Log to database
            self.db.log_trade({
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
            logger.info(f"Opened position: {position_size} {contract['contract_symbol']} @ ${quote['ask']:.2f}")
    
    def _monitor_positions(self):
        """Monitor open positions - fast version"""
        if not self.positions:
            return
        
        # Get SPY quote once
        spy_quote = self.market_data.get_spy_quote()
        current_price = spy_quote['price']
        
        # Get all option quotes in one batch
        symbols = [pos['symbol'] for pos in self.positions.values()]
        option_quotes = self.market_data.get_option_quotes_batch(symbols)
        
        positions_to_close = []
        
        for position_id, position in self.positions.items():
            symbol = position['symbol']
            
            # Check stop loss
            if position['signal']['type'] == 'LONG' and current_price <= position['stop_loss']:
                positions_to_close.append((position_id, 'STOP_LOSS'))
            elif position['signal']['type'] == 'SHORT' and current_price >= position['stop_loss']:
                positions_to_close.append((position_id, 'STOP_LOSS'))
            
            # Check time stop (close all by 10:25)
            elif datetime.now().time() >= time(10, 25):
                positions_to_close.append((position_id, 'TIME_EXIT'))
            
            # Check profit target
            elif symbol in option_quotes:
                quote = option_quotes[symbol]
                current_value = quote['bid']
                pnl_pct = (current_value - position['entry_price']) / position['entry_price']
                
                if pnl_pct >= 0.20:  # 20% profit target
                    positions_to_close.append((position_id, 'PROFIT_TARGET'))
        
        # Close positions
        for position_id, reason in positions_to_close:
            self._close_position(position_id, reason)
    
    def _close_position(self, position_id: str, reason: str):
        """Close position"""
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
                # Log to database
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
                
                # Remove from positions
                del self.positions[position_id]
                logger.info(f"Closed position {position_id} - Reason: {reason}")
                
        except Exception as e:
            logger.error(f"Failed to close position: {e}")
    
    def shutdown(self):
        """Clean shutdown"""
        # Close all positions
        for position_id in list(self.positions.keys()):
            self._close_position(position_id, "SHUTDOWN")
        
        # Disconnect
        self.broker.disconnect()
        logger.info("FastTradingEngine shutdown complete")