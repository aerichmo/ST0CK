import logging
import schedule
import time
from datetime import datetime, time as dt_time
import pytz
from typing import Dict, List, Optional
import uuid
import json

from config.trading_config import TRADING_CONFIG
from src.alpaca_market_data import AlpacaMarketDataProvider
from src.trend_filter import TrendFilter
from src.options_selector import OptionsSelector
from src.risk_manager import RiskManager
from src.exit_manager import ExitManager
from src.database import DatabaseManager
from src.broker_interface import BrokerInterface
from src.mcp_broker import MCPBroker

# Create logs directory if it doesn't exist
import os
os.makedirs('logs', exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/trading.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

class TradingEngine:
    def __init__(self, config: dict, broker, db_connection_string: str, 
                 initial_equity: float = 100000):
        self.config = config
        self.broker = broker
        self.db = DatabaseManager(db_connection_string)
        
        # Use Alpaca market data for all brokers
        self.market_data = AlpacaMarketDataProvider()
        logger.info("Using Alpaca market data provider")
            
        self.trend_filter = TrendFilter(config)
        self.trend_filter.market_data = self.market_data  # Set market data reference
        self.options_selector = OptionsSelector(config)
        self.risk_manager = RiskManager(config, initial_equity)
        self.exit_manager = ExitManager(config)
        
        self.timezone = config["session"]["timezone"]
        self.active_window_start = config["session"]["active_start"]
        self.active_window_end = config["session"]["active_end"]
        
        # SPY-only trading
        self.universe = ['SPY']
        self.opening_ranges = {}
        self.running = False
        self.last_bar_time = {}
        
        logger.info("Trading Engine initialized for SPY-only trading")
        
    def initialize_session(self):
        """Initialize daily trading session"""
        logger.info("Initializing SPY trading session")
        
        # Reset daily risk management stats
        self.risk_manager.reset_daily_stats()
        
        # SPY only - no additional symbols
        self.universe = ['SPY']
        
        logger.info(f"Trading universe: {self.universe}")
        
        # Connect to broker
        self.broker.connect()
        
        # Update account balance at session start
        self.update_account_balance()
        
        # Calculate opening range for SPY
        self.calculate_opening_ranges()
    
    def update_account_balance(self):
        """Fetch and update current account balance from broker"""
        try:
            account_info = self.broker.get_account_info()
            if account_info:
                current_balance = account_info.get('buying_power', account_info.get('cash', 0))
                logger.info(f"Updated account balance: ${current_balance:,.2f}")
                # Update risk manager with current balance
                self.risk_manager.update_equity(current_balance)
            else:
                logger.warning("Failed to fetch account balance")
        except Exception as e:
            logger.error(f"Error updating account balance: {e}")
        
    def calculate_opening_ranges(self):
        """Calculate opening range for SPY"""
        current_date = datetime.now(self.timezone).date()
        
        # Create datetime objects for opening range window
        or_start = datetime.combine(
            current_date,
            self.config["session"]["opening_range_start"],
            self.timezone
        )
        or_end = datetime.combine(
            current_date,
            self.config["session"]["opening_range_end"],
            self.timezone
        )
        
        symbol = 'SPY'
        orh, orl, or_volume = self.market_data.get_opening_range(symbol, or_start, or_end)
        
        if orh and orl:
            self.opening_ranges[symbol] = {'high': orh, 'low': orl}
            self.trend_filter.opening_ranges = self.opening_ranges  # Share with trend filter
            logger.info(f"SPY Opening Range: H={orh:.2f}, L={orl:.2f}")
        else:
            logger.error("Failed to calculate SPY opening range")
    
    def scan_for_signals(self):
        """Main scanning loop for SPY entry signals"""
        current_time = datetime.now(self.timezone).time()
        
        # Check if within active trading window
        if not (self.active_window_start <= current_time <= self.active_window_end):
            return
        
        # Check if trading is allowed by risk manager
        allowed, reason = self.risk_manager.check_trade_allowed()
        if not allowed:
            logger.warning(f"Trading disabled: {reason}")
            return
        
        # Only scan SPY
        symbol = 'SPY'
        
        try:
            if symbol not in self.opening_ranges:
                logger.warning("SPY opening range not available")
                return
            
            # Get current market data
            current_data = self.market_data.get_5min_bars(symbol, lookback_days=2)
            if current_data.empty:
                return
            
            latest_bar = current_data.iloc[-1]
            bar_time = latest_bar.name
            
            # Skip if we already processed this bar
            if symbol in self.last_bar_time and self.last_bar_time[symbol] >= bar_time:
                return
            
            self.last_bar_time[symbol] = bar_time
            
            # Check for breakout signals using enhanced method
            signal = self.trend_filter.check_breakout(
                symbol,
                latest_bar,
                self.opening_ranges[symbol]
            )
            
            if signal:
                logger.info(f"SPY Signal detected: {signal['type']} with strength {signal['strength']:.2f}")
                logger.info(f"Market regime: {signal['market_regime']['regime']}, Gap: {signal['gap_analysis']['gap_type']} {signal['gap_analysis']['gap_pct']:.2%}")
                self.process_signal(symbol, signal, latest_bar)
            
        except Exception as e:
            logger.error(f"Error scanning SPY: {e}")
    
    def process_signal(self, symbol: str, signal: Dict, latest_bar):
        """Process SPY trading signal"""
        # Enforce SPY-only
        if symbol != 'SPY':
            logger.warning(f"Rejecting non-SPY signal for {symbol}")
            return
            
        # Get and validate option contract
        contract = self._get_valid_option_contract(symbol, signal)
        if not contract:
            return
            
        # Get option quote
        option_quote = self.broker.get_option_quote(contract['contract_symbol'])
        if not option_quote:
            logger.error("Failed to get SPY option quote")
            return
        
        # Calculate position size with market regime awareness
        position_size = self.risk_manager.calculate_position_size(
            option_quote['ask'],
            signal['stop_level'],
            signal.get('market_regime')
        )
        
        # Apply additional adjustments from option selection
        if signal.get('position_size_mult'):
            position_size = int(position_size * signal['position_size_mult'])
            logger.info(f"Adjusted position size by {signal['position_size_mult']:.2f}x based on IV/spread conditions")
        
        if position_size <= 0:
            logger.warning("Position size too small for SPY")
            return
        
        # Execute trade
        position = self._execute_trade(symbol, signal, contract, option_quote, position_size)
        if position:
            logger.info(f"SPY position opened: {position['position_id']}")
            self.send_trade_notification('ENTRY', position, signal, contract)
    
    def _get_valid_option_contract(self, symbol: str, signal: Dict) -> Optional[Dict]:
        """Get and validate option contract with enhanced selection"""
        # Get current price
        quote = self.market_data.get_current_quote(symbol)
        if not quote or quote['price'] <= 0:
            logger.error("Failed to get SPY quote")
            return None
        
        # Use enhanced selection with market regime awareness
        contract = self.options_selector.select_option_contract_enhanced(
            symbol,
            signal['type'],
            quote['price'],
            signal.get('market_regime')
        )
        
        if not contract:
            logger.warning("No suitable SPY option contract found")
            return None
        
        # Check if entry conditions are favorable
        if not contract['entry_conditions']['favorable']:
            logger.warning(f"Unfavorable entry conditions: {contract['entry_conditions']['warnings']}")
            # Still allow trade but with adjusted sizing
        
        # Validate liquidity
        if not self.options_selector.validate_contract_liquidity(contract):
            logger.warning("SPY contract failed liquidity validation")
            return None
        
        # Apply position size adjustment from regime and IV conditions
        if 'adjusted_position_size_mult' in contract:
            signal['position_size_mult'] = contract['adjusted_position_size_mult']
            
        return contract
    
    def _execute_trade(self, symbol: str, signal: Dict, contract: Dict, 
                      option_quote: Dict, position_size: int) -> Optional[Dict]:
        """Execute trade and setup exit orders"""
        # Place entry order
        order_id = self.broker.place_option_order(
            contract,
            position_size,
            'MARKET'
        )
        
        if not order_id:
            logger.error("Failed to place SPY option order")
            return None
        
        # Create position record
        position = {
            'position_id': str(uuid.uuid4()),
            'symbol': symbol,
            'contracts': position_size,
            'entry_price': option_quote['ask'],
            'entry_time': datetime.now(self.timezone),
            'order_id': order_id
        }
        
        # Calculate exit levels with volatility adjustment
        market_data = {
            'atr': signal.get('atr', 0),
            'market_regime': signal.get('market_regime', {})
        }
        exit_levels = self.exit_manager.calculate_exit_levels(
            option_quote['ask'],
            signal['stop_level'],
            signal['type'],
            market_data
        )
        
        # Place OCO exit orders
        oco_id = self.broker.place_oco_order(
            contract,
            position_size,
            exit_levels['stop_loss'],
            [exit_levels['target_1'], exit_levels['target_2']]
        )
        
        position['oco_id'] = oco_id
        
        # Track position
        self.risk_manager.add_position(position)
        
        # Log to database
        self.db.log_trade_entry(position, signal, contract, exit_levels)
        
        return position
    
    def monitor_positions(self):
        """Monitor open SPY positions with enhanced exit management"""
        positions = self.risk_manager.get_open_positions()
        
        for position in positions:
            try:
                # Time stop check with dynamic adjustment
                if self.exit_manager.check_time_stop(position['entry_time']):
                    logger.info(f"Time stop triggered for SPY position {position['position_id']}")
                    self.close_position(position, 'TIME_STOP')
                    continue
                
                # Get current option quote
                quote = self.broker.get_option_quote(position['contract_symbol'])
                if not quote:
                    continue
                
                current_price = quote['bid']
                
                # Update P&L
                pnl = self.risk_manager.calculate_pnl(
                    position['entry_price'],
                    current_price,
                    position['contracts']
                )
                
                position['unrealized_pnl'] = pnl
                position['current_price'] = current_price
                
                # Update high water mark for trailing stops
                if 'high_water_mark' not in position:
                    position['high_water_mark'] = current_price
                else:
                    position['high_water_mark'] = max(position['high_water_mark'], current_price)
                
                # Check for trailing stop update
                if pnl > 0:  # Only trail stops on profitable positions
                    new_stop = self.exit_manager.update_trailing_stop(
                        position['position_id'],
                        current_price,
                        position['high_water_mark']
                    )
                    if new_stop:
                        logger.info(f"Trailing stop updated to ${new_stop:.2f} for position {position['position_id']}")
                
                # Get current market conditions for exit suggestions
                current_data = self.market_data.get_5min_bars('SPY', lookback_days=1)
                if not current_data.empty:
                    market_regime = self.trend_filter.calculate_market_regime(current_data)
                    
                    # Check for exit suggestions
                    exit_suggestion = self.exit_manager.suggest_exit_action(
                        position,
                        market_regime
                    )
                    
                    if exit_suggestion:
                        logger.info(f"Exit suggestion for {position['position_id']}: {exit_suggestion}")
                        
                        # Act on critical suggestions
                        if exit_suggestion == "CLOSE_END_OF_DAY":
                            self.close_position(position, 'END_OF_DAY')
                            continue
                
                # Log current status
                logger.debug(f"SPY Position {position['position_id']}: "
                           f"Entry=${position['entry_price']:.2f}, "
                           f"Current=${current_price:.2f}, "
                           f"P&L=${pnl:.2f}, "
                           f"High=${position['high_water_mark']:.2f}")
                
            except Exception as e:
                logger.error(f"Error monitoring SPY position {position['position_id']}: {e}")
    
    def close_position(self, position: Dict, reason: str):
        """Close SPY position"""
        try:
            # Get current quote for exit price
            quote = self.broker.get_option_quote(position['contract_symbol'])
            if not quote:
                logger.error(f"Failed to get quote for closing SPY position")
                return
            
            exit_price = quote['bid']
            
            # Cancel OCO orders
            if 'oco_id' in position:
                self.broker.cancel_order(position['oco_id'])
            
            # Place market sell order
            self.broker.simulate_fill(
                position['order_id'],
                exit_price
            )
            
            # Calculate final P&L
            pnl = self.risk_manager.calculate_pnl(
                position['entry_price'],
                exit_price,
                position['contracts']
            )
            
            # Update risk manager
            self.risk_manager.remove_position(position['position_id'])
            self.risk_manager.update_daily_pnl(pnl)
            
            # Log to database
            self.db.log_trade_exit(
                position['position_id'],
                exit_price,
                position['contracts'],
                reason,
                pnl
            )
            
            logger.info(f"SPY position closed: {position['position_id']}, "
                       f"Reason: {reason}, P&L: ${pnl:.2f}")
            
            # Send notification
            self.send_trade_notification('EXIT', position, reason, pnl)
            
        except Exception as e:
            logger.error(f"Error closing SPY position: {e}")
    
    def send_trade_notification(self, action: str, position: Dict, *args):
        """Send trade notification"""
        try:
            message = f"SPY {action}: {position['contracts']} contracts @ ${position['entry_price']:.2f}"
            if action == 'EXIT' and len(args) >= 2:
                reason, pnl = args[0], args[1]
                message += f" | Reason: {reason} | P&L: ${pnl:.2f}"
            
            logger.info(f"NOTIFICATION: {message}")
            # In production, this would send actual notifications
            
        except Exception as e:
            logger.error(f"Error sending notification: {e}")
    
    def _get_current_intervals(self):
        """Get dynamic intervals based on current trading phase"""
        current_time = datetime.now(self.timezone).time()
        
        # Pre-market and active trading (9:20-10:30 AM): Most reactive
        if dt_time(9, 20) <= current_time <= self.active_window_end:
            return {
                'signal_scan': 1,  # 1-second scans during critical window
                'position_monitor': 1,  # 1-second position checks
                'risk_log': 30  # 30-second risk logging
            }
        # Position monitoring phase (10:31 AM-4:05 PM): Moderate reactivity
        elif self.active_window_end < current_time <= dt_time(16, 5):
            return {
                'signal_scan': 5,  # 5-second scans (no new trades allowed anyway)
                'position_monitor': 2,  # 2-second position checks for exits
                'risk_log': 60  # 60-second risk logging
            }
        # All other times: Low reactivity
        else:
            return {
                'signal_scan': 30,  # 30-second scans
                'position_monitor': 10,  # 10-second position checks
                'risk_log': 300  # 5-minute risk logging
            }
    
    def run_trading_loop(self):
        """Main trading loop with dynamic timing"""
        logger.info("Starting SPY trading loop with dynamic timing")
        self.running = True
        
        # Schedule session management
        schedule.every().day.at("09:25").do(self.initialize_session)
        schedule.every().day.at("16:05").do(self.end_session)
        
        # Track last execution times
        last_signal_scan = 0
        last_position_monitor = 0
        last_risk_log = 0
        last_balance_update = 0
        last_timing_mode = None
        
        while self.running:
            try:
                current_time = time.time()
                intervals = self._get_current_intervals()
                
                # Log timing mode changes
                current_mode = None
                if intervals['signal_scan'] == 1:
                    current_mode = "ACTIVE (1s scans)"
                elif intervals['signal_scan'] == 5:
                    current_mode = "MONITORING (5s scans)"
                else:
                    current_mode = "IDLE (30s scans)"
                
                if current_mode != last_timing_mode:
                    logger.info(f"Execution timing changed to: {current_mode}")
                    last_timing_mode = current_mode
                
                # Dynamic signal scanning
                if current_time - last_signal_scan >= intervals['signal_scan']:
                    self.scan_for_signals()
                    last_signal_scan = current_time
                
                # Dynamic position monitoring
                if current_time - last_position_monitor >= intervals['position_monitor']:
                    self.monitor_positions()
                    last_position_monitor = current_time
                
                # Dynamic risk logging
                if current_time - last_risk_log >= intervals['risk_log']:
                    self.risk_manager.log_current_state()
                    last_risk_log = current_time
                
                # Update account balance every 5 minutes
                if current_time - last_balance_update >= 300:  # 5 minutes
                    self.update_account_balance()
                    last_balance_update = current_time
                
                # Run scheduled tasks (session management)
                schedule.run_pending()
                
                # Sleep for 100ms for better reactivity
                time.sleep(0.1)
                
            except KeyboardInterrupt:
                logger.info("Trading loop interrupted by user")
                break
            except Exception as e:
                logger.error(f"Error in trading loop: {e}")
                time.sleep(5)
    
    def end_session(self):
        """End of day cleanup"""
        logger.info("Ending SPY trading session")
        
        # Close any remaining positions
        positions = self.risk_manager.get_open_positions()
        for position in positions:
            self.close_position(position, 'END_OF_DAY')
        
        # Generate daily report
        self.generate_daily_report()
        
        # Disconnect from broker
        self.broker.disconnect()
        
        # Force database flush
        if hasattr(self.db, 'force_flush'):
            self.db.force_flush()
    
    def generate_daily_report(self):
        """Generate daily SPY trading report"""
        try:
            account_info = self.broker.get_account_info()
            daily_trades = self.db.get_daily_trades(datetime.now(self.timezone))
            
            report = {
                'date': datetime.now(self.timezone).strftime('%Y-%m-%d'),
                'symbol': 'SPY',
                'trades': len(daily_trades),
                'final_equity': account_info['account_value'],
                'daily_pnl': account_info['realized_pnl'],
                'commission_paid': account_info.get('commission_paid', 0)
            }
            
            logger.info(f"Daily Report: {json.dumps(report, indent=2)}")
            
            # Save report to database
            self.db.log_risk_metrics({
                'current_equity': report['final_equity'],
                'daily_pnl': report['daily_pnl'],
                'daily_pnl_pct': report['daily_pnl'] / 100000,  # Assuming 100k initial
                'consecutive_losses': self.risk_manager.consecutive_losses,
                'active_positions': 0,
                'trades_today': report['trades'],
                'trading_enabled': True
            })
            
        except Exception as e:
            logger.error(f"Error generating daily report: {e}")
    
    def stop(self):
        """Stop trading engine"""
        logger.info("Stopping SPY trading engine")
        self.running = False
        self.end_session()
        
        # Close database connection
        if hasattr(self.db, 'close'):
            self.db.close()