"""
Position management service - Handles position tracking and P&L calculations
"""
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

from ..unified_logging import get_logger
from ..unified_database import UnifiedDatabaseManager
from ..unified_cache import UnifiedCache

@dataclass
class PositionUpdate:
    """Position update data"""
    position_id: str
    current_price: float
    timestamp: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)

class PositionService:
    """
    Manages position lifecycle and calculations
    """
    
    def __init__(self,
                 db_manager: UnifiedDatabaseManager,
                 cache: UnifiedCache):
        """
        Initialize position service
        
        Args:
            db_manager: Database manager
            cache: Cache manager
        """
        self.db = db_manager
        self.cache = cache
        self.logger = get_logger(__name__)
    
    def create_position(self,
                       bot_id: str,
                       symbol: str,
                       side: str,
                       quantity: int,
                       entry_price: float,
                       order_id: str,
                       metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Create a new position
        
        Returns:
            Position ID
        """
        position_data = {
            'bot_id': bot_id,
            'symbol': symbol,
            'action': f'BUY_{side.upper()}',
            'quantity': quantity,
            'entry_price': entry_price,
            'entry_time': datetime.now(),
            'strategy_details': metadata or {}
        }
        
        # Log to database
        self.db.log_trade(position_data)
        
        # Cache position data
        position_id = order_id  # Use order ID as position ID
        cache_key = f"position:{bot_id}:{position_id}"
        self.cache.set(cache_key, position_data, 3600)  # 1 hour cache
        
        self.logger.info(f"Created position {position_id} for {bot_id}")
        
        return position_id
    
    def update_position(self, 
                       bot_id: str,
                       position_id: str,
                       update: PositionUpdate) -> bool:
        """
        Update position with current market data
        
        Returns:
            True if successful
        """
        try:
            # Get position from cache
            cache_key = f"position:{bot_id}:{position_id}"
            position = self.cache.get(cache_key)
            
            if not position:
                # Try database
                trades = self.db.get_trades(bot_id, limit=100)
                position = next((t for t in trades if str(t.id) == position_id), None)
                if not position:
                    return False
            
            # Calculate P&L
            entry_price = position.get('entry_price', position.entry_price if hasattr(position, 'entry_price') else 0)
            quantity = position.get('quantity', position.quantity if hasattr(position, 'quantity') else 0)
            
            if position.get('action', '').startswith('BUY'):
                pnl = (update.current_price - entry_price) * quantity
            else:  # Short position
                pnl = (entry_price - update.current_price) * quantity
            
            pnl_percent = (pnl / (entry_price * quantity)) * 100 if entry_price > 0 else 0
            
            # Update cache with new data
            position_update = {
                **position,
                'current_price': update.current_price,
                'unrealized_pnl': pnl,
                'unrealized_pnl_pct': pnl_percent,
                'last_update': update.timestamp
            }
            
            self.cache.set(cache_key, position_update, 3600)
            
            # Log significant P&L changes
            if abs(pnl_percent) > 1.0:
                self.logger.info(
                    f"Position {position_id} P&L: ${pnl:.2f} ({pnl_percent:.2f}%)"
                )
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to update position {position_id}: {e}")
            return False
    
    def close_position(self,
                      bot_id: str,
                      position_id: str,
                      exit_price: float,
                      exit_time: datetime,
                      exit_reason: str) -> Optional[Dict[str, Any]]:
        """
        Close a position and calculate final P&L
        
        Returns:
            Position summary with P&L
        """
        try:
            # Get position data
            cache_key = f"position:{bot_id}:{position_id}"
            position = self.cache.get(cache_key)
            
            if not position:
                self.logger.error(f"Position {position_id} not found")
                return None
            
            # Calculate final P&L
            entry_price = position.get('entry_price', 0)
            quantity = position.get('quantity', 0)
            
            if position.get('action', '').startswith('BUY'):
                pnl = (exit_price - entry_price) * quantity
            else:  # Short position
                pnl = (entry_price - exit_price) * quantity
            
            pnl_percent = (pnl / (entry_price * quantity)) * 100 if entry_price > 0 else 0
            
            # Update database
            self.db.update_trade_exit(
                int(position_id),
                exit_price,
                exit_time,
                pnl,
                pnl_percent
            )
            
            # Clear cache
            self.cache.delete(cache_key)
            
            # Return summary
            summary = {
                'position_id': position_id,
                'symbol': position.get('symbol'),
                'entry_price': entry_price,
                'exit_price': exit_price,
                'quantity': quantity,
                'pnl': pnl,
                'pnl_percent': pnl_percent,
                'exit_reason': exit_reason,
                'duration': (exit_time - position.get('entry_time', exit_time)).total_seconds()
            }
            
            self.logger.info(
                f"Closed position {position_id}: P&L ${pnl:.2f} ({pnl_percent:.2f}%)"
            )
            
            return summary
            
        except Exception as e:
            self.logger.error(f"Failed to close position {position_id}: {e}")
            return None
    
    def get_open_positions(self, bot_id: str) -> List[Dict[str, Any]]:
        """Get all open positions for a bot"""
        # Get from database
        db_positions = self.db.get_active_positions(bot_id)
        
        # Enhance with cached data
        positions = []
        for pos in db_positions:
            cache_key = f"position:{bot_id}:{pos.id}"
            cached = self.cache.get(cache_key)
            
            if cached:
                positions.append(cached)
            else:
                positions.append({
                    'position_id': str(pos.id),
                    'symbol': pos.symbol,
                    'quantity': pos.quantity,
                    'entry_price': pos.entry_price,
                    'entry_time': pos.entry_time,
                    'action': pos.action
                })
        
        return positions
    
    def calculate_portfolio_metrics(self, bot_id: str) -> Dict[str, Any]:
        """Calculate portfolio-level metrics"""
        positions = self.get_open_positions(bot_id)
        
        if not positions:
            return {
                'total_positions': 0,
                'total_value': 0,
                'total_pnl': 0,
                'total_pnl_pct': 0
            }
        
        total_value = 0
        total_cost = 0
        total_pnl = 0
        
        for pos in positions:
            quantity = pos.get('quantity', 0)
            entry_price = pos.get('entry_price', 0)
            current_price = pos.get('current_price', entry_price)
            
            position_cost = entry_price * quantity
            position_value = current_price * quantity
            position_pnl = pos.get('unrealized_pnl', position_value - position_cost)
            
            total_cost += position_cost
            total_value += position_value
            total_pnl += position_pnl
        
        return {
            'total_positions': len(positions),
            'total_value': total_value,
            'total_cost': total_cost,
            'total_pnl': total_pnl,
            'total_pnl_pct': (total_pnl / total_cost * 100) if total_cost > 0 else 0,
            'positions': positions
        }