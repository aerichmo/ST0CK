import logging
import schedule
import time
from datetime import datetime, time as dt_time
import pytz
from typing import Dict, List, Optional
import uuid
import json
from concurrent.futures import ThreadPoolExecutor

from config.trading_config import TRADING_CONFIG
from src.market_data import MarketDataProvider
from src.trend_filter import TrendFilter
from src.options_selector import OptionsSelector
from src.risk_manager import RiskManager
from src.exit_manager import ExitManager
from src.database import DatabaseManager
from src.broker_interface import PaperTradingBroker

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
        
        self.market_data = MarketDataProvider(config)
        self.trend_filter = TrendFilter(config)
        self.options_selector = OptionsSelector(config)
        self.risk_manager = RiskManager(config, initial_equity)
        self.exit_manager = ExitManager(config)
        
        self.timezone = config["session"]["timezone"]
        self.active_window_start = config["session"]["active_start"]
        self.active_window_end = config["session"]["active_end"]
        
        self.universe = []
        self.opening_ranges = {}
        self.running = False
        self.last_bar_time = {}
        
    def initialize_session(self):
        """Initialize daily trading session"""
        logger.info("Initializing trading session")
        
        self.risk_manager.reset_daily_stats()
        
        self.universe = self.config["universe"]["base_symbols"].copy()
        
        gappers = self.market_data.get_pre_market_gappers()
        self.universe.extend(gappers)
        
        logger.info(f"Trading universe: {self.universe}")
        
        self.broker.connect()
        
        self.calculate_opening_ranges()
        
    def calculate_opening_ranges(self):
        """Calculate opening range for all symbols"""
        current_date = datetime.now(self.timezone)
        
        with ThreadPoolExecutor(max_workers=10) as executor:
            results = executor.map(
                lambda symbol: (symbol, self.market_data.get_opening_range(symbol, current_date)),
                self.universe
            )
            
            for symbol, (orh, orl) in results:
                if orh and orl:
                    self.opening_ranges[symbol] = {'high': orh, 'low': orl}
                    logger.info(f"{symbol} Opening Range: H={orh:.2f}, L={orl:.2f}")
    
    def scan_for_signals(self):
        """Main scanning loop for entry signals"""
        current_time = datetime.now(self.timezone).time()
        
        if not (self.active_window_start <= current_time <= self.active_window_end):
            return
        
        allowed, reason = self.risk_manager.check_trade_allowed()
        if not allowed:
            logger.warning(f"Trading disabled: {reason}")
            return
        
        for symbol in self.universe:
            try:
                if symbol not in self.opening_ranges:
                    continue
                
                bars = self.market_data.get_5min_bars(symbol, lookback_days=1)
                
                if bars.empty:
                    continue
                
                last_bar_time = bars.index[-1]
                if symbol in self.last_bar_time and self.last_bar_time[symbol] == last_bar_time:
                    continue
                
                self.last_bar_time[symbol] = last_bar_time
                
                if not self.trend_filter.validate_market_conditions(bars):
                    continue
                
                trend_bias = self.trend_filter.get_trend_bias(bars)
                if not trend_bias:
                    continue
                
                or_data = self.opening_ranges[symbol]
                signal = self.trend_filter.check_entry_trigger(
                    bars, or_data['high'], or_data['low'], trend_bias
                )
                
                if signal:
                    self.process_signal(symbol, signal, bars)
                    
            except Exception as e:
                logger.error(f"Error scanning {symbol}: {e}")
    
    def process_signal(self, symbol: str, signal: Dict, bars):
        """Process trading signal and execute trade"""
        logger.info(f"Signal detected for {symbol}: {signal['type']}")
        
        current_quote = self.market_data.get_current_quote(symbol)
        if not current_quote:
            return
        
        contract = self.options_selector.select_option_contract(
            symbol, signal['type'], current_quote['price']
        )
        
        if not contract:
            logger.warning(f"No suitable option contract found for {symbol}")
            return
        
        if not self.options_selector.validate_contract_liquidity(contract):
            logger.warning(f"Contract liquidity check failed for {symbol}")
            return
        
        position_size = self.risk_manager.calculate_position_size(contract['mid_price'])
        
        position = {
            'position_id': str(uuid.uuid4()),
            'symbol': symbol,
            'contract_symbol': contract['contract_symbol'],
            'option_type': contract['option_type'],
            'entry_price': contract['mid_price'],
            'contracts': position_size,
            'signal': signal
        }
        
        if not self.risk_manager.add_position(position):
            return
        
        order_id = self.broker.place_option_order(contract, position_size)
        
        if order_id:
            position['order_id'] = order_id
            
            oco_order = self.exit_manager.create_oco_order(position)
            exit_levels = self.exit_manager.calculate_exit_levels(
                contract['mid_price'], contract['option_type']
            )
            
            oco_id = self.broker.place_oco_order(
                contract, position_size, 
                oco_order['orders']['stop_loss']['price'],
                [oco_order['orders']['target_1']['price'], 
                 oco_order['orders']['target_2']['price']]
            )
            
            position['oco_id'] = oco_id
            
            self.db.log_trade_entry(position, signal, contract, exit_levels)
            
            logger.info(f"Trade executed: {position['position_id']} - "
                       f"{position_size} {contract['option_type']}s at ${contract['mid_price']}")
    
    def monitor_positions(self):
        """Monitor open positions for exit conditions"""
        for position_id, position in self.risk_manager.active_positions.items():
            if position['status'] != 'OPEN':
                continue
            
            try:
                quote = self.broker.get_option_quote(position['contract_symbol'])
                if not quote:
                    continue
                
                current_price = quote['last']
                
                self.risk_manager.update_position_pnl(position_id, current_price)
                
                exit_triggers = self.exit_manager.check_exit_conditions(
                    position_id, current_price
                )
                
                for trigger in exit_triggers:
                    self.execute_exit(trigger)
                    
            except Exception as e:
                logger.error(f"Error monitoring position {position_id}: {e}")
        
        time_stop_positions = self.risk_manager.check_time_stops()
        for position_id in time_stop_positions:
            quote = self.broker.get_option_quote(
                self.risk_manager.active_positions[position_id]['contract_symbol']
            )
            if quote:
                self.execute_exit({
                    'position_id': position_id,
                    'order_type': 'time_stop',
                    'exit_price': quote['last'],
                    'contracts': self.risk_manager.active_positions[position_id]['remaining_contracts'],
                    'reason': 'Time stop (60 min)'
                })
    
    def execute_exit(self, exit_trigger: Dict):
        """Execute position exit"""
        position_id = exit_trigger['position_id']
        exit_price = exit_trigger['exit_price']
        contracts = exit_trigger['contracts']
        reason = exit_trigger['reason']
        
        result = self.risk_manager.close_position(position_id, exit_price, contracts)
        
        if result:
            self.db.log_trade_exit(
                position_id, exit_price, contracts, 
                reason, result['trade_pnl']
            )
            
            logger.info(f"Position exit: {position_id} - {contracts} contracts at "
                       f"${exit_price} ({reason}) - P&L: ${result['trade_pnl']:.2f}")
            
            self.db.log_risk_metrics(self.risk_manager.get_risk_metrics())
    
    def end_of_day_tasks(self):
        """Perform end of day tasks"""
        logger.info("Running end of day tasks")
        
        for position_id in list(self.risk_manager.active_positions.keys()):
            position = self.risk_manager.active_positions[position_id]
            if position['status'] == 'OPEN':
                quote = self.broker.get_option_quote(position['contract_symbol'])
                if quote:
                    self.execute_exit({
                        'position_id': position_id,
                        'order_type': 'eod',
                        'exit_price': quote['last'],
                        'contracts': position['remaining_contracts'],
                        'reason': 'End of day'
                    })
        
        expectancy_report = self.db.get_expectancy_report(days=30)
        logger.info(f"Expectancy Report: {json.dumps(expectancy_report, indent=2)}")
        
        risk_metrics = self.risk_manager.get_risk_metrics()
        logger.info(f"Daily Risk Metrics: {json.dumps(risk_metrics, indent=2)}")
        
        self.broker.disconnect()
        self.db.close()
    
    def run(self):
        """Main trading loop"""
        self.running = True
        
        # Check if we should run initialization immediately
        current_time = datetime.now(self.timezone)
        market_open = current_time.replace(hour=9, minute=25, second=0)
        market_close = current_time.replace(hour=16, minute=0, second=0)
        
        # If started between 9:25 AM and 4:00 PM ET on a weekday, initialize immediately
        if (current_time.weekday() < 5 and 
            market_open <= current_time <= market_close):
            logger.info("Market hours detected, initializing session immediately")
            self.initialize_session()
        
        # Schedule daily tasks
        schedule.every().day.at("09:25").do(self.initialize_session)
        schedule.every().day.at("16:00").do(self.end_of_day_tasks)
        
        # Only schedule scanning during active window
        def conditional_scan():
            current = datetime.now(self.timezone).time()
            if self.active_window_start <= current <= self.active_window_end:
                self.scan_for_signals()
        
        def conditional_monitor():
            current = datetime.now(self.timezone).time()
            market_close_time = dt_time(16, 0)
            if current <= market_close_time:
                self.monitor_positions()
        
        schedule.every(5).seconds.do(conditional_scan)
        schedule.every(5).seconds.do(conditional_monitor)
        
        logger.info("Trading engine started - will run autonomously")
        
        while self.running:
            try:
                schedule.run_pending()
                time.sleep(1)
                
                # Auto-shutdown after market close
                if datetime.now(self.timezone).time() > dt_time(16, 5):
                    logger.info("After market hours - shutting down")
                    self.running = False
                    
            except KeyboardInterrupt:
                logger.info("Shutting down trading engine")
                self.running = False
                self.end_of_day_tasks()
            except Exception as e:
                logger.error(f"Unexpected error in main loop: {e}")
    
    def stop(self):
        """Stop trading engine"""
        self.running = False