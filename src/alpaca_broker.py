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
    GetOrdersRequest,
    GetOptionContractsRequest  # Moved from data.requests
)
from alpaca.trading.enums import OrderSide, TimeInForce, OrderStatus, AssetStatus, ContractType
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.historical.option import OptionHistoricalDataClient
from alpaca.data.requests import (
    StockBarsRequest, 
    StockQuotesRequest,
    OptionChainRequest,
    OptionLatestQuoteRequest
)
from alpaca.trading.requests import GetOptionContractsRequest
from alpaca.data.timeframe import TimeFrame

from .broker_interface import BrokerInterface

logger = logging.getLogger(__name__)

class OrderResult:
    """Simple order result wrapper for compatibility"""
    def __init__(self, order_dict: Dict):
        self.id = order_dict['id']
        self.symbol = order_dict['symbol']
        self.qty = order_dict['qty']
        self.side = order_dict['side']
        self.order_type = order_dict['order_type']
        self.status = order_dict['status']


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
            
            # Initialize options data client
            self.option_client = OptionHistoricalDataClient(
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
    
    async def get_account(self) -> Optional[Dict]:
        """Async wrapper for get_account_info for compatibility"""
        return self.get_account_info()
    
    async def place_order(self, symbol: str, qty: int, side: str, 
                         order_type: str = 'market', time_in_force: str = 'day',
                         limit_price: Optional[float] = None, 
                         stop_price: Optional[float] = None) -> Optional[Dict]:
        """Async wrapper for place_stock_order for compatibility"""
        order_id = self.place_stock_order(
            symbol=symbol,
            quantity=qty,
            side=side,
            order_type=order_type,
            limit_price=limit_price,
            time_in_force=time_in_force
        )
        
        if order_id:
            # Return an OrderResult object
            return OrderResult({
                'id': order_id,
                'symbol': symbol,
                'qty': qty,
                'side': side,
                'order_type': order_type,
                'status': 'pending'
            })
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
            logger.error(f"Failed to place option order: {symbol} {quantity} {order_type} - Error: {e}")
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
            logger.error(f"Failed to place OCO order: {symbol} stop@{stop_price} targets@{target_prices} - Error: {e}")
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
        logger.info(f"Requesting option quote for symbol: '{contract_symbol}' (length: {len(contract_symbol)})")
        
        # Validate symbol format - should be like SPY250719C00590000
        if len(contract_symbol) < 10 or not any(c in contract_symbol for c in ['C', 'P']):
            logger.error(f"REJECTED invalid option symbol format: '{contract_symbol}' (length: {len(contract_symbol)})")
            return None
            
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
                
                # Get underlying price for context - extract underlying symbol properly
                # For symbols like SPY250725C00590000 -> SPY, AA250725C00015000 -> AA  
                import re
                match = re.match(r'^([A-Z]+)', contract_symbol)
                underlying_symbol = match.group(1) if match else contract_symbol[:3]
                stock_request = StockQuotesRequest(
                    symbol_or_symbols=underlying_symbol,
                    limit=1,
                    feed='iex'
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
    
    def place_stock_order(self, symbol: str, quantity: int, side: str,
                         order_type: str = 'MARKET', limit_price: Optional[float] = None,
                         time_in_force: str = 'DAY') -> Optional[str]:
        """Place a stock order"""
        if not self.connected:
            return None
            
        try:
            # Convert side string to OrderSide enum
            order_side = OrderSide.BUY if side.upper() == 'BUY' else OrderSide.SELL
            
            # Convert time_in_force string to TimeInForce enum
            tif_map = {
                'DAY': TimeInForce.DAY,
                'GTC': TimeInForce.GTC,
                'IOC': TimeInForce.IOC,
                'FOK': TimeInForce.FOK
            }
            tif = tif_map.get(time_in_force.upper(), TimeInForce.DAY)
            
            # Create order request based on type
            if order_type.upper() == 'MARKET':
                order_data = MarketOrderRequest(
                    symbol=symbol,
                    qty=quantity,
                    side=order_side,
                    time_in_force=tif
                )
            elif order_type.upper() == 'LIMIT':
                if limit_price is None:
                    logger.error("Limit price required for limit orders")
                    return None
                order_data = LimitOrderRequest(
                    symbol=symbol,
                    qty=quantity,
                    side=order_side,
                    time_in_force=tif,
                    limit_price=limit_price
                )
            else:
                logger.error(f"Unsupported order type: {order_type}")
                return None
            
            # Submit order
            order = self.trading_client.submit_order(order_data)
            logger.info(f"Stock order placed: {symbol} {side} {quantity} shares, ID: {order.id}")
            return order.id
            
        except Exception as e:
            logger.error(f"Failed to place stock order: {symbol} {quantity} {side} {order_type} - Error: {e}")
            return None
    
    def close_position(self, symbol: str, quantity: Optional[int] = None) -> Optional[str]:
        """Close a position"""
        if not self.connected:
            return None
            
        try:
            # Get current position
            positions = self.get_positions()
            position = next((p for p in positions if p['symbol'] == symbol), None)
            
            if not position:
                logger.warning(f"No position found for {symbol}")
                return None
            
            # Determine quantity to close
            close_qty = quantity if quantity else abs(position['quantity'])
            
            # Determine side (opposite of position)
            side = 'SELL' if position['quantity'] > 0 else 'BUY'
            
            # Place market order to close
            return self.place_stock_order(
                symbol=symbol,
                quantity=close_qty,
                side=side,
                order_type='MARKET'
            )
            
        except Exception as e:
            logger.error(f"Failed to close position: {e}")
            return None
    
    def get_open_orders(self) -> List[Dict]:
        """Get all open orders"""
        return self.get_orders(status='open')
    
    def get_option_contracts(self, symbol: str, expiration: datetime, option_type: str) -> Optional[List[Dict]]:
        """
        Get option contracts for a symbol and expiration using Alpaca options API
        """
        logger.info(f"Requesting {option_type} option contracts for symbol: '{symbol}', expiration: {expiration}")
        
        if not self.connected:
            return None
            
        try:
            # Determine contract type
            contract_type = ContractType.CALL if option_type.upper() == 'CALL' else ContractType.PUT
            
            # Create request for option contracts
            req = GetOptionContractsRequest(
                underlying_symbol=[symbol],
                status=AssetStatus.ACTIVE,
                expiration_date=expiration.strftime('%Y-%m-%d'),
                type=contract_type
            )
            
            # Debug: log the exact request being sent
            logger.info(f"GetOptionContractsRequest: underlying_symbol={req.underlying_symbol}, "
                       f"expiration_date={req.expiration_date}, type={req.type}, status={req.status}")
            
            # Get contracts from Alpaca using TradingClient
            contracts_response = self.trading_client.get_option_contracts(req)
            
            # Debug log the response
            logger.info(f"Option contracts response: found {len(list(contracts_response)) if hasattr(contracts_response, '__iter__') else 'unknown'} contracts")
            
            # Debug log the response type
            logger.debug(f"Option contracts response type: {type(contracts_response)}")
            if hasattr(contracts_response, '__dict__'):
                logger.debug(f"Response attributes: {contracts_response.__dict__.keys()}")
            
            # Convert to our standard format
            result = []
            # Check if response is a dict with contracts key
            if hasattr(contracts_response, 'option_contracts'):
                contracts_list = contracts_response.option_contracts
            elif isinstance(contracts_response, dict) and 'option_contracts' in contracts_response:
                contracts_list = contracts_response['option_contracts']
            elif isinstance(contracts_response, list):
                contracts_list = contracts_response
            else:
                # Try to iterate directly
                contracts_list = contracts_response
                
            for contract in contracts_list:
                # Handle both object and dict access patterns
                if hasattr(contract, 'symbol'):
                    # Use expiration_date attribute (correct for Alpaca SDK)
                    expiration_date = contract.expiration_date if hasattr(contract, 'expiration_date') else None
                    
                    # Try different possible attribute names for contract type
                    contract_type_val = None
                    for attr_name in ['type', 'option_type', 'contract_type', 'side']:
                        if hasattr(contract, attr_name):
                            contract_type_val = getattr(contract, attr_name)
                            break
                    
                    # Convert to string representation
                    if contract_type_val:
                        if hasattr(contract_type_val, 'value'):
                            type_str = contract_type_val.value  # For enum types
                        elif isinstance(contract_type_val, str):
                            type_str = contract_type_val.upper()
                        else:
                            type_str = str(contract_type_val).upper()
                    else:
                        # Try to extract from symbol (SPY251219C00590000 format)
                        symbol_str = contract.symbol
                        type_str = 'CALL' if 'C' in symbol_str[-9:] else 'PUT'
                    
                    # Log the contract symbol being added - first few only
                    if len(result) < 5:  # Only log first 5 contracts
                        logger.info(f"Adding contract symbol: {contract.symbol}, type: {type_str}, strike: {contract.strike_price}")
                    
                    result.append({
                        'symbol': contract.symbol,  # OCC format symbol
                        'strike': float(contract.strike_price),
                        'expiration': expiration_date,
                        'type': type_str,
                        'underlying': contract.underlying_symbol,
                        'contract_size': contract.size if hasattr(contract, 'size') else 100,
                        'style': contract.style if hasattr(contract, 'style') else 'American'
                    })
                elif isinstance(contract, dict):
                    result.append({
                        'symbol': contract.get('symbol'),  # OCC format symbol
                        'strike': float(contract.get('strike_price', 0)),
                        'expiration': contract.get('expiration'),
                        'type': 'CALL' if contract.get('contract_type') == 'call' else 'PUT',
                        'underlying': contract.get('underlying_symbol', symbol),
                        'contract_size': contract.get('size', 100),
                        'style': contract.get('style', 'American')
                    })
                else:
                    logger.warning(f"Unexpected contract format: {type(contract)}")
            
            logger.info(f"Found {len(result)} {option_type} option contracts for {symbol}")
            return result
            
        except Exception as e:
            logger.error(f"Failed to get option contracts: {e}", exc_info=True)
            return None
    
    def get_option_chain(self, underlying: str, expiration: Optional[str] = None) -> Optional[Dict]:
        """Get option chain for underlying - not implemented for Alpaca"""
        logger.warning("Option chain not implemented for Alpaca broker")
        return None
    
    def get_option_quotes(self, contracts: List[str]) -> Optional[Dict]:
        """Get quotes for multiple option contracts"""
        if not self.connected:
            return None
            
        quotes = {}
        for contract in contracts:
            quote = self.get_option_quote(contract)
            if quote:
                quotes[contract] = quote
                
        return quotes if quotes else None
    
    @property
    def is_connected(self) -> bool:
        """Check if broker is connected"""
        return self.connected