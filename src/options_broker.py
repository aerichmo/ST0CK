"""
Options Trading Support for ST0CK
Extends AlpacaBroker to handle options orders and positions
"""
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from decimal import Decimal
import pandas as pd

from alpaca.trading.client import TradingClient
from alpaca.trading.requests import (
    MarketOrderRequest, LimitOrderRequest, GetOrdersRequest,
    GetOptionContractsRequest
)
from alpaca.trading.enums import OrderSide, TimeInForce, OrderType, OrderStatus
from alpaca.data.historical import StockHistoricalDataClient, OptionHistoricalDataClient
from alpaca.data.requests import (
    StockLatestQuoteRequest, OptionLatestQuoteRequest,
    OptionChainRequest, OptionBarsRequest
)

from .alpaca_broker import AlpacaBroker
from .unified_logging import get_logger


class OptionsBroker(AlpacaBroker):
    """
    Extended broker for options trading
    Handles both stocks and options orders
    """
    
    def __init__(self, api_key: str, api_secret: str, paper: bool = True,
                 bot_id: str = "options_broker"):
        """Initialize options broker with additional clients"""
        super().__init__(api_key, api_secret, paper, bot_id)
        
        self.logger = get_logger(__name__)
        
        # Initialize options data client
        self.options_data_client = OptionHistoricalDataClient(api_key, api_secret)
        
        # Cache for options contracts
        self.contract_cache = {}
        self.cache_expiry = {}
        
    async def get_options_chain(self, symbol: str, expiration_date: Optional[datetime] = None) -> pd.DataFrame:
        """
        Get options chain for a symbol
        
        Returns DataFrame with columns:
        - symbol, strike, expiration, type (call/put), bid, ask, volume, open_interest
        """
        try:
            # Build request
            if expiration_date:
                exp_str = expiration_date.strftime("%Y-%m-%d")
            else:
                # Get next Friday expiration
                today = datetime.now()
                days_until_friday = (4 - today.weekday()) % 7
                if days_until_friday == 0:
                    days_until_friday = 7
                exp_date = today + timedelta(days=days_until_friday)
                exp_str = exp_date.strftime("%Y-%m-%d")
            
            # Check cache
            cache_key = f"{symbol}_{exp_str}"
            if cache_key in self.contract_cache:
                if datetime.now() < self.cache_expiry[cache_key]:
                    return self.contract_cache[cache_key]
            
            # Request options chain
            request = OptionChainRequest(
                symbol_or_symbols=symbol,
                expiration_date=exp_str
            )
            
            chain = self.options_data_client.get_option_chain(request)
            
            # Convert to DataFrame
            data = []
            for contract in chain[symbol]:
                latest_quote = await self._get_option_quote(contract.symbol)
                
                data.append({
                    'symbol': contract.symbol,
                    'underlying': symbol,
                    'strike': float(contract.strike_price),
                    'expiration': contract.expiration_date,
                    'type': contract.option_type,
                    'bid': float(latest_quote.bid_price) if latest_quote else 0,
                    'ask': float(latest_quote.ask_price) if latest_quote else 0,
                    'mid': float((latest_quote.bid_price + latest_quote.ask_price) / 2) if latest_quote else 0,
                    'volume': int(latest_quote.volume) if latest_quote else 0,
                    'open_interest': int(contract.open_interest) if hasattr(contract, 'open_interest') else 0
                })
            
            df = pd.DataFrame(data)
            
            # Cache for 5 minutes
            self.contract_cache[cache_key] = df
            self.cache_expiry[cache_key] = datetime.now() + timedelta(minutes=5)
            
            return df
            
        except Exception as e:
            self.logger.error(f"Failed to get options chain: {e}")
            return pd.DataFrame()
    
    async def _get_option_quote(self, symbol: str) -> Optional[Any]:
        """Get latest quote for an option"""
        try:
            request = OptionLatestQuoteRequest(symbol_or_symbols=symbol)
            quotes = self.options_data_client.get_option_latest_quote(request)
            return quotes.get(symbol)
        except Exception as e:
            self.logger.error(f"Failed to get option quote for {symbol}: {e}")
            return None
    
    async def find_atm_straddle(self, symbol: str, target_dte: int = 0) -> Optional[Dict[str, Any]]:
        """
        Find the best ATM straddle for the given DTE target
        
        Returns dict with 'call' and 'put' contract symbols and details
        """
        try:
            # Get current stock price
            stock_price = await self._get_stock_price(symbol)
            if not stock_price:
                return None
            
            # Find appropriate expiration
            target_date = datetime.now() + timedelta(days=target_dte)
            
            # Get options chain
            chain_df = await self.get_options_chain(symbol, target_date)
            if chain_df.empty:
                return None
            
            # Find ATM strike (closest to current price)
            chain_df['distance'] = abs(chain_df['strike'] - stock_price)
            atm_strike = chain_df.loc[chain_df['distance'].idxmin(), 'strike']
            
            # Get call and put at ATM strike
            calls = chain_df[(chain_df['strike'] == atm_strike) & (chain_df['type'] == 'call')]
            puts = chain_df[(chain_df['strike'] == atm_strike) & (chain_df['type'] == 'put')]
            
            if calls.empty or puts.empty:
                self.logger.warning(f"No ATM straddle found for {symbol} at strike {atm_strike}")
                return None
            
            call = calls.iloc[0]
            put = puts.iloc[0]
            
            # Calculate straddle cost and metrics
            straddle_cost = call['ask'] + put['ask']
            straddle_mid = call['mid'] + put['mid']
            
            return {
                'call': {
                    'symbol': call['symbol'],
                    'strike': call['strike'],
                    'bid': call['bid'],
                    'ask': call['ask'],
                    'mid': call['mid']
                },
                'put': {
                    'symbol': put['symbol'],
                    'strike': put['strike'],
                    'bid': put['bid'],
                    'ask': put['ask'],
                    'mid': put['mid']
                },
                'strike': atm_strike,
                'expiration': call['expiration'],
                'total_cost': straddle_cost,
                'total_mid': straddle_mid,
                'underlying_price': stock_price
            }
            
        except Exception as e:
            self.logger.error(f"Failed to find ATM straddle: {e}")
            return None
    
    async def _get_stock_price(self, symbol: str) -> Optional[float]:
        """Get current stock price"""
        try:
            request = StockLatestQuoteRequest(symbol_or_symbols=symbol)
            quotes = self.stock_data_client.get_stock_latest_quote(request)
            quote = quotes.get(symbol)
            return float(quote.ask_price) if quote else None
        except Exception as e:
            self.logger.error(f"Failed to get stock price for {symbol}: {e}")
            return None
    
    async def place_straddle_order(self, straddle: Dict[str, Any], quantity: int = 1) -> Tuple[Optional[str], Optional[str]]:
        """
        Place orders for both legs of a straddle
        
        Returns tuple of (call_order_id, put_order_id)
        """
        try:
            # Place call order
            call_order = await self.place_option_order(
                symbol=straddle['call']['symbol'],
                quantity=quantity,
                side=OrderSide.BUY,
                order_type=OrderType.MARKET
            )
            
            # Place put order
            put_order = await self.place_option_order(
                symbol=straddle['put']['symbol'],
                quantity=quantity,
                side=OrderSide.BUY,
                order_type=OrderType.MARKET
            )
            
            if call_order and put_order:
                self.logger.info(
                    f"Placed straddle orders: Call {call_order.id}, Put {put_order.id} "
                    f"at strike {straddle['strike']}"
                )
                return (call_order.id, put_order.id)
            else:
                # Cancel successful leg if one failed
                if call_order:
                    await self.cancel_order(call_order.id)
                if put_order:
                    await self.cancel_order(put_order.id)
                return (None, None)
                
        except Exception as e:
            self.logger.error(f"Failed to place straddle orders: {e}")
            return (None, None)
    
    async def place_option_order(self, symbol: str, quantity: int, side: OrderSide,
                                order_type: OrderType = OrderType.MARKET,
                                limit_price: Optional[float] = None) -> Optional[Any]:
        """Place an option order"""
        try:
            # Create order request
            if order_type == OrderType.MARKET:
                order_request = MarketOrderRequest(
                    symbol=symbol,
                    qty=quantity,
                    side=side,
                    time_in_force=TimeInForce.DAY
                )
            else:
                order_request = LimitOrderRequest(
                    symbol=symbol,
                    qty=quantity,
                    side=side,
                    limit_price=limit_price,
                    time_in_force=TimeInForce.DAY
                )
            
            # Submit order
            order = self.trading_client.submit_order(order_request)
            
            self.logger.info(
                f"Placed option order: {symbol} {quantity} {side.value} "
                f"{order_type.value} - Order ID: {order.id}"
            )
            
            return order
            
        except Exception as e:
            self.logger.error(f"Failed to place option order: {e}")
            return None
    
    async def close_straddle(self, call_symbol: str, put_symbol: str,
                           call_qty: int, put_qty: int) -> Tuple[Optional[str], Optional[str]]:
        """
        Close a straddle position
        
        Returns tuple of (call_order_id, put_order_id)
        """
        try:
            # Place sell orders for both legs
            call_order = await self.place_option_order(
                symbol=call_symbol,
                quantity=call_qty,
                side=OrderSide.SELL,
                order_type=OrderType.MARKET
            )
            
            put_order = await self.place_option_order(
                symbol=put_symbol,
                quantity=put_qty,
                side=OrderSide.SELL,
                order_type=OrderType.MARKET
            )
            
            return (
                call_order.id if call_order else None,
                put_order.id if put_order else None
            )
            
        except Exception as e:
            self.logger.error(f"Failed to close straddle: {e}")
            return (None, None)
    
    def get_option_positions(self) -> List[Dict[str, Any]]:
        """Get all option positions"""
        try:
            positions = []
            for position in self.trading_client.get_all_positions():
                # Check if it's an option (longer symbol with date/strike)
                if len(position.symbol) > 10:  # Options have longer symbols
                    positions.append({
                        'symbol': position.symbol,
                        'quantity': int(position.qty),
                        'side': 'long' if int(position.qty) > 0 else 'short',
                        'cost_basis': float(position.cost_basis),
                        'market_value': float(position.market_value),
                        'unrealized_pnl': float(position.unrealized_pl),
                        'current_price': float(position.current_price) if position.current_price else 0
                    })
            
            return positions
            
        except Exception as e:
            self.logger.error(f"Failed to get option positions: {e}")
            return []
    
    def calculate_straddle_pnl(self, positions: List[Dict[str, Any]]) -> Dict[str, float]:
        """Calculate P&L for straddle positions"""
        # Group by expiration/strike
        straddles = {}
        
        for pos in positions:
            # Extract expiration and strike from symbol
            # This is simplified - real implementation would parse properly
            key = pos['symbol'][:10]  # Group key
            
            if key not in straddles:
                straddles[key] = {'pnl': 0, 'cost': 0, 'value': 0}
            
            straddles[key]['pnl'] += pos['unrealized_pnl']
            straddles[key]['cost'] += pos['cost_basis']
            straddles[key]['value'] += pos['market_value']
        
        return straddles