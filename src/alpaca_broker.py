"""
Alpaca Broker Implementation using alpaca-py SDK
Provides direct, high-speed access to Alpaca's trading and options data APIs
"""

import os
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
from decimal import Decimal

from alpaca.trading.client import TradingClient
from alpaca.trading.requests import (
    MarketOrderRequest, 
    LimitOrderRequest,
    StopOrderRequest,
    GetOrdersRequest
)
from alpaca.trading.enums import OrderSide, TimeInForce, OrderStatus
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest, StockQuotesRequest
from alpaca.data.timeframe import TimeFrame

from .broker_interface import BrokerInterface

logger = logging.getLogger(__name__)


class AlpacaBroker(BrokerInterface):
    """Direct Alpaca broker for high-speed options trading"""
    
    def __init__(self, api_key: str = None, secret_key: str = None, 
                 base_url: str = None, paper: bool = True):
        """
        Initialize Alpaca broker with credentials
        
        Args:
            api_key: Alpaca API key (or from env)
            secret_key: Alpaca secret key (or from env)
            base_url: API base URL (optional)
            paper: Use paper trading (default True)
        """
        # Get credentials from env if not provided
        self.api_key = api_key or os.getenv('ALPACA_API_KEY')
        self.secret_key = secret_key or os.getenv('ALPACA_API_SECRET')
        self.base_url = base_url or os.getenv('ALPACA_BASE_URL')
        
        if not self.api_key or not self.secret_key:
            raise ValueError("Alpaca API credentials required")
        
        self.paper = paper
        self.connected = False
        self.trading_client = None
        self.data_client = None
        
    def connect(self) -> bool:
        """Connect to Alpaca APIs"""
        try:
            # Initialize trading client
            self.trading_client = TradingClient(
                api_key=self.api_key,
                secret_key=self.secret_key,
                paper=self.paper,
                url_override=self.base_url
            )
            
            # Initialize data client (no auth required for basic data)
            self.data_client = StockHistoricalDataClient(
                api_key=self.api_key,
                secret_key=self.secret_key
            )
            
            # Test connection by fetching account
            account = self.trading_client.get_account()
            logger.info(f"Connected to Alpaca {'paper' if self.paper else 'live'} trading")
            logger.info(f"Account: ${float(account.cash):,.2f} cash, "
                       f"${float(account.portfolio_value):,.2f} total")
            
            self.connected = True
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to Alpaca: {e}")
            self.connected = False
            return False
    
    def disconnect(self) -> None:
        """Disconnect from Alpaca"""
        self.connected = False
        logger.info("Disconnected from Alpaca")
    
    def get_account_info(self) -> Optional[Dict]:
        """Get account information"""
        if not self.connected:
            return None
            
        try:
            account = self.trading_client.get_account()
            
            return {
                'account_value': float(account.portfolio_value),
                'buying_power': float(account.buying_power),
                'cash': float(account.cash),
                'initial_capital': float(account.cash),
                'pattern_day_trader': account.pattern_day_trader,
                'trading_blocked': account.trading_blocked,
                'account_blocked': account.account_blocked,
                'daytrade_count': account.daytrade_count,
                'equity': float(account.equity),
                'last_equity': float(account.last_equity),
                'maintenance_margin': float(account.maintenance_margin),
                'currency': account.currency
            }
            
        except Exception as e:
            logger.error(f"Failed to get account info: {e}")
            return None
    
    def place_option_order(self, contract: Dict, quantity: int, 
                          order_type: str = 'MARKET') -> Optional[str]:
        """
        Place an option order
        
        Args:
            contract: Option contract details with 'contract_symbol'
            quantity: Number of contracts
            order_type: MARKET or LIMIT
            
        Returns:
            Order ID if successful
        """
        if not self.connected:
            return None
            
        try:
            # Extract option symbol
            symbol = contract.get('contract_symbol')
            if not symbol:
                logger.error("No contract symbol provided")
                return None
            
            # Create order request
            if order_type.upper() == 'MARKET':
                order_data = MarketOrderRequest(
                    symbol=symbol,
                    qty=quantity,
                    side=OrderSide.BUY,
                    time_in_force=TimeInForce.DAY
                )
            else:
                # For limit orders, use the ask price
                limit_price = contract.get('ask', contract.get('last', 0))
                order_data = LimitOrderRequest(
                    symbol=symbol,
                    qty=quantity,
                    side=OrderSide.BUY,
                    time_in_force=TimeInForce.DAY,
                    limit_price=limit_price
                )
            
            # Submit order
            order = self.trading_client.submit_order(order_data)
            
            logger.info(f"Option order placed: {order.id} - "
                       f"BUY {quantity} {symbol} @ {order_type}")
            
            return order.id
            
        except Exception as e:
            logger.error(f"Failed to place option order: {e}")
            return None
    
    def place_oco_order(self, contract: Dict, quantity: int, 
                       stop_price: float, target_prices: List[float]) -> Optional[str]:
        """
        Place OCO (One-Cancels-Other) order for exits
        
        Note: Alpaca doesn't have native OCO for options, so we'll place 
        individual orders and track them
        """
        if not self.connected:
            return None
            
        try:
            symbol = contract.get('contract_symbol')
            if not symbol:
                return None
            
            order_ids = []
            
            # Place stop loss order
            stop_order = StopOrderRequest(
                symbol=symbol,
                qty=quantity,
                side=OrderSide.SELL,
                time_in_force=TimeInForce.GTC,
                stop_price=stop_price
            )
            stop = self.trading_client.submit_order(stop_order)
            order_ids.append(stop.id)
            
            # Place target orders
            for i, target_price in enumerate(target_prices):
                target_qty = quantity // 2 if i == 0 else quantity - (quantity // 2)
                
                target_order = LimitOrderRequest(
                    symbol=symbol,
                    qty=target_qty,
                    side=OrderSide.SELL,
                    time_in_force=TimeInForce.GTC,
                    limit_price=target_price
                )
                target = self.trading_client.submit_order(target_order)
                order_ids.append(target.id)
            
            # Return composite ID
            oco_id = ":".join(order_ids)
            logger.info(f"OCO orders placed: {oco_id}")
            
            return oco_id
            
        except Exception as e:
            logger.error(f"Failed to place OCO order: {e}")
            return None
    
    def cancel_order(self, order_id: str) -> bool:
        """Cancel an order"""
        if not self.connected:
            return False
            
        try:
            # Handle composite OCO IDs
            if ":" in order_id:
                order_ids = order_id.split(":")
                success = True
                for oid in order_ids:
                    try:
                        self.trading_client.cancel_order_by_id(oid)
                    except:
                        success = False
                return success
            else:
                self.trading_client.cancel_order_by_id(order_id)
                return True
                
        except Exception as e:
            logger.error(f"Failed to cancel order: {e}")
            return False
    
    def get_order_status(self, order_id: str) -> Optional[Dict]:
        """Get order status"""
        if not self.connected:
            return None
            
        try:
            order = self.trading_client.get_order_by_id(order_id)
            
            return {
                'order_id': order.id,
                'symbol': order.symbol,
                'status': order.status.value,
                'filled_qty': int(order.filled_qty) if order.filled_qty else 0,
                'avg_fill_price': float(order.filled_avg_price) if order.filled_avg_price else None,
                'side': order.side.value,
                'order_type': order.order_type.value,
                'submitted_at': order.submitted_at.isoformat() if order.submitted_at else None
            }
            
        except Exception as e:
            logger.error(f"Failed to get order status: {e}")
            return None
    
    def get_option_quote(self, contract_symbol: str) -> Optional[Dict]:
        """
        Get real-time option quote using Alpaca's Options API
        """
        if not self.connected:
            return None
            
        try:
            # Use the options data client
            from alpaca.data.historical.option import OptionHistoricalDataClient
            from alpaca.data.requests import OptionLatestQuoteRequest
            
            # Initialize options client if needed
            if not hasattr(self, 'option_client'):
                self.option_client = OptionHistoricalDataClient(
                    self.api_key,
                    self.secret_key
                )
            
            # Get option quote
            request = OptionLatestQuoteRequest(symbol_or_symbols=contract_symbol)
            quotes = self.option_client.get_option_latest_quote(request)
            
            if contract_symbol in quotes:
                quote = quotes[contract_symbol]
                
                # Get underlying price for context
                underlying_symbol = contract_symbol[:3]  # Extract SPY from option symbol
                stock_request = StockQuotesRequest(
                    symbol_or_symbols=underlying_symbol,
                    limit=1
                )
                stock_quotes = self.data_client.get_stock_quotes(stock_request)
                underlying_price = float(stock_quotes[underlying_symbol][0].ask_price) if underlying_symbol in stock_quotes else 0
                
                return {
                    'contract_symbol': contract_symbol,
                    'bid': float(quote.bid_price) if quote.bid_price else 0,
                    'ask': float(quote.ask_price) if quote.ask_price else 0,
                    'last': float((quote.bid_price + quote.ask_price) / 2) if quote.bid_price and quote.ask_price else 0,
                    'mid_price': float((quote.bid_price + quote.ask_price) / 2) if quote.bid_price and quote.ask_price else 0,
                    'volume': 0,  # Will be in snapshot if needed
                    'open_interest': 0,  # Will be in snapshot if needed
                    'implied_volatility': 0,  # Will be in snapshot if needed
                    'timestamp': datetime.now(),
                    'underlying_price': underlying_price
                }
            else:
                logger.warning(f"No quote found for {contract_symbol}")
                return None
                
        except ImportError:
            logger.error("Alpaca options module not installed. Run: pip install alpaca-py>=0.15.0")
            return None
        except Exception as e:
            logger.error(f"Failed to get option quote: {e}")
            return None
    
    def get_positions(self) -> List[Dict]:
        """Get all positions"""
        if not self.connected:
            return []
            
        try:
            positions = self.trading_client.get_all_positions()
            
            return [{
                'symbol': pos.symbol,
                'quantity': int(pos.qty),
                'avg_price': float(pos.avg_entry_price),
                'current_price': float(pos.current_price) if pos.current_price else None,
                'market_value': float(pos.market_value) if pos.market_value else None,
                'unrealized_pnl': float(pos.unrealized_pl) if pos.unrealized_pl else None,
                'side': pos.side.value
            } for pos in positions]
            
        except Exception as e:
            logger.error(f"Failed to get positions: {e}")
            return []
    
    def get_orders(self, status: str = 'open') -> List[Dict]:
        """Get orders by status"""
        if not self.connected:
            return []
            
        try:
            request = GetOrdersRequest(
                status=status,
                limit=100
            )
            orders = self.trading_client.get_orders(request)
            
            return [{
                'order_id': order.id,
                'symbol': order.symbol,
                'status': order.status.value,
                'side': order.side.value,
                'quantity': int(order.qty),
                'filled_qty': int(order.filled_qty) if order.filled_qty else 0,
                'order_type': order.order_type.value,
                'submitted_at': order.submitted_at.isoformat() if order.submitted_at else None
            } for order in orders]
            
        except Exception as e:
            logger.error(f"Failed to get orders: {e}")
            return []