"""
Trading service - Core business logic for trade execution
"""
import asyncio
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass

from ..unified_logging import get_logger
from ..unified_database import UnifiedDatabaseManager
from ..unified_cache import UnifiedCache
from ..error_reporter import ErrorReporter

@dataclass
class TradeRequest:
    """Trade request data"""
    bot_id: str
    symbol: str
    side: str  # 'buy' or 'sell'
    quantity: int
    order_type: str  # 'market', 'limit', 'stop'
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None
    time_in_force: str = 'day'
    metadata: Dict[str, Any] = None

@dataclass
class TradeResult:
    """Trade execution result"""
    success: bool
    order_id: Optional[str] = None
    filled_price: Optional[float] = None
    filled_quantity: Optional[int] = None
    timestamp: Optional[datetime] = None
    error: Optional[str] = None

class TradingService:
    """
    Handles trade execution logic
    Separates business rules from broker implementation
    """
    
    def __init__(self, 
                 broker,
                 db_manager: UnifiedDatabaseManager,
                 cache: UnifiedCache,
                 risk_manager):
        """
        Initialize trading service
        
        Args:
            broker: Broker implementation
            db_manager: Database manager
            cache: Cache manager
            risk_manager: Risk manager
        """
        self.broker = broker
        self.db = db_manager
        self.cache = cache
        self.risk_manager = risk_manager
        self.logger = get_logger(__name__)
    
    async def execute_trade(self, request: TradeRequest) -> TradeResult:
        """
        Execute a trade with all business logic checks
        
        Args:
            request: Trade request details
            
        Returns:
            TradeResult with execution details
        """
        try:
            # Step 1: Validate request
            validation_error = self._validate_request(request)
            if validation_error:
                return TradeResult(success=False, error=validation_error)
            
            # Step 2: Risk checks
            if request.side == 'buy':
                # Calculate approximate risk
                risk_amount = request.quantity * (request.limit_price or 0)
                allowed, reason = await self.risk_manager.check_trade_allowed(
                    request.bot_id, 
                    risk_amount
                )
                if not allowed:
                    return TradeResult(success=False, error=f"Risk check failed: {reason}")
            
            # Step 3: Place order
            order = await self.broker.place_order(
                symbol=request.symbol,
                qty=request.quantity,
                side=request.side,
                order_type=request.order_type,
                time_in_force=request.time_in_force,
                limit_price=request.limit_price,
                stop_price=request.stop_price
            )
            
            if not order:
                return TradeResult(success=False, error="Order placement failed")
            
            # Step 4: Log to database
            self._log_trade_attempt(request, order.id)
            
            # Step 5: Wait for fill (if market order)
            if request.order_type == 'market':
                filled_order = await self.broker.wait_for_fill(order.id, timeout=30)
                if filled_order:
                    return TradeResult(
                        success=True,
                        order_id=filled_order.id,
                        filled_price=float(filled_order.filled_avg_price),
                        filled_quantity=int(filled_order.filled_qty),
                        timestamp=datetime.now()
                    )
            
            # For limit/stop orders, return immediately
            return TradeResult(
                success=True,
                order_id=order.id,
                timestamp=datetime.now()
            )
            
        except Exception as e:
            self.logger.error(f"Trade execution failed: {e}", 
                            extra={"bot_id": request.bot_id, "symbol": request.symbol, 
                                   "order_type": request.order_type.value}, 
                            exc_info=True)
            ErrorReporter.report_failure(request.bot_id, e, {'request': request})
            return TradeResult(success=False, error=str(e))
    
    async def cancel_order(self, bot_id: str, order_id: str) -> bool:
        """Cancel an order"""
        try:
            await self.broker.cancel_order(order_id)
            self._log_order_cancellation(bot_id, order_id)
            return True
        except Exception as e:
            self.logger.error(f"Failed to cancel order {order_id}: {e}", 
                            extra={"bot_id": bot_id, "order_id": order_id})
            return False
    
    async def modify_order(self, 
                          bot_id: str,
                          order_id: str,
                          new_limit_price: Optional[float] = None,
                          new_stop_price: Optional[float] = None,
                          new_quantity: Optional[int] = None) -> bool:
        """Modify an existing order"""
        try:
            # Cancel and replace (most brokers don't support true modify)
            original_order = await self.broker.get_order(order_id)
            if not original_order:
                return False
            
            # Cancel original
            await self.broker.cancel_order(order_id)
            
            # Place new order with modifications
            new_request = TradeRequest(
                bot_id=bot_id,
                symbol=original_order.symbol,
                side=original_order.side,
                quantity=new_quantity or original_order.qty,
                order_type=original_order.order_type,
                limit_price=new_limit_price or original_order.limit_price,
                stop_price=new_stop_price or original_order.stop_price,
                time_in_force=original_order.time_in_force
            )
            
            result = await self.execute_trade(new_request)
            return result.success
            
        except Exception as e:
            self.logger.error(f"Failed to modify order {order_id}: {e}", 
                            extra={"bot_id": bot_id, "order_id": order_id})
            return False
    
    def _validate_request(self, request: TradeRequest) -> Optional[str]:
        """Validate trade request"""
        if request.quantity <= 0:
            return "Invalid quantity"
        
        if request.side not in ['buy', 'sell']:
            return "Invalid side"
        
        if request.order_type not in ['market', 'limit', 'stop', 'stop_limit']:
            return "Invalid order type"
        
        if request.order_type in ['limit', 'stop_limit'] and not request.limit_price:
            return "Limit price required for limit orders"
        
        if request.order_type in ['stop', 'stop_limit'] and not request.stop_price:
            return "Stop price required for stop orders"
        
        return None
    
    def _log_trade_attempt(self, request: TradeRequest, order_id: str):
        """Log trade attempt to database"""
        self.db.log_execution(
            action='trade_attempt',
            details={
                'order_id': order_id,
                'symbol': request.symbol,
                'side': request.side,
                'quantity': request.quantity,
                'order_type': request.order_type,
                'limit_price': request.limit_price,
                'stop_price': request.stop_price,
                'metadata': request.metadata
            }
        )
    
    def _log_order_cancellation(self, bot_id: str, order_id: str):
        """Log order cancellation"""
        self.db.log_execution(
            action='order_cancelled',
            details={'order_id': order_id, 'bot_id': bot_id}
        )