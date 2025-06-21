import os
import json
import asyncio
from typing import Dict, Optional, List, Any
from datetime import datetime
import logging
import subprocess
from abc import ABC

from .broker_interface import BrokerInterface

logger = logging.getLogger(__name__)


class MCPBroker(BrokerInterface):
    """
    Broker implementation using Alpaca MCP (Model Context Protocol) server.
    This provides a simplified interface to Alpaca's trading API through
    natural language-like commands.
    """
    
    def __init__(self, mode: str = "paper"):
        """
        Initialize MCP Broker connection.
        
        Args:
            mode: Trading mode ('paper' or 'live')
        """
        self.mode = mode
        self.is_paper = mode == "paper"
        self.mcp_server_path = None
        self.mcp_process = None
        self._connected = False
        
    def _start_mcp_server(self):
        """Start the MCP server process if not already running."""
        try:
            # Check if MCP server is installed
            mcp_path = os.path.expanduser("~/alpaca-mcp-server")
            if not os.path.exists(mcp_path):
                raise RuntimeError(
                    "Alpaca MCP server not found. Please install it first:\n"
                    "git clone https://github.com/alpacahq/alpaca-mcp-server.git ~/alpaca-mcp-server"
                )
            
            self.mcp_server_path = mcp_path
            
            # Start the MCP server
            env = os.environ.copy()
            env.update({
                "ALPACA_API_KEY": os.getenv("ALPACA_API_KEY"),
                "ALPACA_SECRET_KEY": os.getenv("ALPACA_API_SECRET"),
                "PAPER": str(self.is_paper)
            })
            
            self.mcp_process = subprocess.Popen(
                ["python", "-m", "alpaca_mcp_server"],
                cwd=self.mcp_server_path,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            # Give server time to start
            import time
            time.sleep(2)
            
            logger.info(f"MCP server started in {self.mode} mode")
            
        except Exception as e:
            logger.error(f"Failed to start MCP server: {e}")
            raise
    
    def _call_mcp(self, method: str, **kwargs) -> Dict[str, Any]:
        """
        Call an MCP server method.
        
        Args:
            method: The MCP method to call
            **kwargs: Method arguments
            
        Returns:
            Dict containing the response
        """
        try:
            # In a real implementation, this would communicate with the MCP server
            # For now, we'll use subprocess to call MCP commands
            cmd = ["python", "-m", "alpaca_mcp_server.client", method]
            
            # Add arguments
            for key, value in kwargs.items():
                cmd.extend([f"--{key}", str(value)])
            
            result = subprocess.run(
                cmd,
                cwd=self.mcp_server_path,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode != 0:
                raise RuntimeError(f"MCP call failed: {result.stderr}")
            
            return json.loads(result.stdout)
            
        except json.JSONDecodeError:
            # If response isn't JSON, return as text
            return {"response": result.stdout}
        except Exception as e:
            logger.error(f"MCP call failed: {e}")
            raise
    
    def connect(self) -> bool:
        """Connect to Alpaca through MCP server."""
        try:
            if not self.mcp_process:
                self._start_mcp_server()
            
            # Verify connection
            account = self._call_mcp("get_account_info")
            if account:
                self._connected = True
                logger.info(f"Connected to Alpaca MCP ({self.mode} mode)")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to connect: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from MCP server."""
        try:
            if self.mcp_process:
                self.mcp_process.terminate()
                self.mcp_process.wait(timeout=5)
                self.mcp_process = None
            
            self._connected = False
            logger.info("Disconnected from Alpaca MCP")
            
        except Exception as e:
            logger.error(f"Error during disconnect: {e}")
    
    def place_option_order(
        self,
        symbol: str,
        expiration: str,
        strike: float,
        option_type: str,
        side: str,
        quantity: int,
        order_type: str = "market",
        limit_price: Optional[float] = None
    ) -> Optional[Order]:
        """Place an option order through MCP."""
        try:
            # Format the option symbol for Alpaca
            # SPY240115C00475000 format
            exp_date = datetime.strptime(expiration, "%Y-%m-%d").strftime("%y%m%d")
            strike_str = f"{int(strike * 1000):08d}"
            option_symbol = f"{symbol}{exp_date}{option_type[0].upper()}{strike_str}"
            
            # Place order through MCP
            response = self._call_mcp(
                "place_option_order",
                symbol=option_symbol,
                side=side,
                quantity=quantity,
                order_type=order_type,
                limit_price=limit_price
            )
            
            if response and "order" in response:
                order_data = response["order"]
                return Order(
                    id=order_data.get("id"),
                    symbol=symbol,
                    side=side,
                    quantity=quantity,
                    order_type=order_type,
                    status=order_data.get("status", "pending"),
                    filled_qty=order_data.get("filled_qty", 0),
                    avg_fill_price=order_data.get("filled_avg_price"),
                    created_at=datetime.now()
                )
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to place option order: {e}")
            return None
    
    def place_oco_order(
        self,
        symbol: str,
        quantity: int,
        take_profit_price: float,
        stop_loss_price: float,
        position_id: Optional[str] = None
    ) -> Optional[Dict[str, Order]]:
        """Place OCO (One-Cancels-Other) order through MCP."""
        try:
            # MCP doesn't have direct OCO support, so we'll place two orders
            # and manage them programmatically
            
            # Place take profit order
            tp_response = self._call_mcp(
                "place_stock_order",
                symbol=symbol,
                side="sell",
                quantity=quantity,
                order_type="limit",
                limit_price=take_profit_price
            )
            
            # Place stop loss order
            sl_response = self._call_mcp(
                "place_stock_order",
                symbol=symbol,
                side="sell",
                quantity=quantity,
                order_type="stop",
                stop_price=stop_loss_price
            )
            
            orders = {}
            
            if tp_response and "order" in tp_response:
                tp_data = tp_response["order"]
                orders["take_profit"] = Order(
                    id=tp_data.get("id"),
                    symbol=symbol,
                    side="sell",
                    quantity=quantity,
                    order_type="limit",
                    status=tp_data.get("status", "pending"),
                    limit_price=take_profit_price,
                    created_at=datetime.now()
                )
            
            if sl_response and "order" in sl_response:
                sl_data = sl_response["order"]
                orders["stop_loss"] = Order(
                    id=sl_data.get("id"),
                    symbol=symbol,
                    side="sell",
                    quantity=quantity,
                    order_type="stop",
                    status=sl_data.get("status", "pending"),
                    stop_price=stop_loss_price,
                    created_at=datetime.now()
                )
            
            return orders if len(orders) == 2 else None
            
        except Exception as e:
            logger.error(f"Failed to place OCO order: {e}")
            return None
    
    def cancel_order(self, order_id: str) -> bool:
        """Cancel an order through MCP."""
        try:
            response = self._call_mcp("cancel_order", order_id=order_id)
            return response and response.get("success", False)
            
        except Exception as e:
            logger.error(f"Failed to cancel order: {e}")
            return False
    
    def get_order_status(self, order_id: str) -> Optional[Order]:
        """Get order status through MCP."""
        try:
            response = self._call_mcp("get_order", order_id=order_id)
            
            if response and "order" in response:
                order_data = response["order"]
                return Order(
                    id=order_data.get("id"),
                    symbol=order_data.get("symbol"),
                    side=order_data.get("side"),
                    quantity=order_data.get("qty"),
                    order_type=order_data.get("order_type"),
                    status=order_data.get("status"),
                    filled_qty=order_data.get("filled_qty", 0),
                    avg_fill_price=order_data.get("filled_avg_price"),
                    created_at=datetime.fromisoformat(order_data.get("created_at"))
                )
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get order status: {e}")
            return None
    
    def get_account_info(self) -> Optional[AccountInfo]:
        """Get account information through MCP."""
        try:
            response = self._call_mcp("get_account_info")
            
            if response and "account" in response:
                account_data = response["account"]
                return AccountInfo(
                    buying_power=float(account_data.get("buying_power", 0)),
                    cash=float(account_data.get("cash", 0)),
                    portfolio_value=float(account_data.get("portfolio_value", 0)),
                    positions=[]  # Positions would need separate call
                )
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get account info: {e}")
            return None
    
    def get_option_quote(
        self,
        symbol: str,
        expiration: str,
        strike: float,
        option_type: str
    ) -> Optional[Dict[str, float]]:
        """Get option quote through MCP."""
        try:
            # Format the option symbol
            exp_date = datetime.strptime(expiration, "%Y-%m-%d").strftime("%y%m%d")
            strike_str = f"{int(strike * 1000):08d}"
            option_symbol = f"{symbol}{exp_date}{option_type[0].upper()}{strike_str}"
            
            response = self._call_mcp("get_option_quote", symbol=option_symbol)
            
            if response and "quote" in response:
                quote_data = response["quote"]
                return {
                    "bid": float(quote_data.get("bid_price", 0)),
                    "ask": float(quote_data.get("ask_price", 0)),
                    "last": float(quote_data.get("last_price", 0)),
                    "volume": int(quote_data.get("volume", 0)),
                    "open_interest": int(quote_data.get("open_interest", 0))
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get option quote: {e}")
            return None