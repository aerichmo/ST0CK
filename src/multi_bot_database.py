"""
Multi-bot aware database manager
Extends the existing database with bot_id support
"""
from sqlalchemy import Column, String, ForeignKey, Boolean, JSON, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime, timedelta
import logging
import time
from typing import Dict, List, Optional

from .database import (
    Base, Trade, ExecutionLog, RiskMetrics, 
    BatchedDatabaseManager, create_engine, sessionmaker
)

logger = logging.getLogger(__name__)


class BotRegistry(Base):
    """Registry of all bots in the system"""
    __tablename__ = 'bot_registry'
    
    bot_id = Column(String(50), primary_key=True)
    bot_name = Column(String(100), nullable=False)
    strategy_type = Column(String(100), nullable=False)
    alpaca_account = Column(String(100))
    is_active = Column(Boolean, default=True)
    config = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class MultiBotDatabaseManager(BatchedDatabaseManager):
    """Database manager with multi-bot support"""
    
    def __init__(self, connection_string: str, bot_id: str = None, **kwargs):
        super().__init__(connection_string, **kwargs)
        self.bot_id = bot_id
        
        # Create bot registry table if it doesn't exist
        BotRegistry.__table__.create(self.engine, checkfirst=True)
    
    def set_bot_id(self, bot_id: str):
        """Set the current bot ID for operations"""
        self.bot_id = bot_id
    
    def _serialize_config(self, config: Dict) -> Dict:
        """Convert config to JSON-serializable format"""
        import copy
        from datetime import time
        
        def convert_value(obj):
            if isinstance(obj, time):
                return obj.strftime('%H:%M:%S')
            elif isinstance(obj, dict):
                return {k: convert_value(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert_value(v) for v in obj]
            else:
                return obj
        
        return convert_value(config)
    
    def register_bot(self, bot_id: str, bot_name: str, strategy_type: str, 
                    alpaca_account: str = None, config: Dict = None) -> bool:
        """Register a new bot in the system"""
        session = self.Session()
        try:
            # Convert config to JSON-serializable format
            serializable_config = self._serialize_config(config) if config else {}
            
            bot = BotRegistry(
                bot_id=bot_id,
                bot_name=bot_name,
                strategy_type=strategy_type,
                alpaca_account=alpaca_account,
                config=serializable_config,
                is_active=True
            )
            session.merge(bot)  # Use merge to update if exists
            session.commit()
            logger.info(f"Registered bot: {bot_id} - {bot_name}")
            return True
        except Exception as e:
            logger.error(f"Error registering bot: {e}")
            session.rollback()
            return False
        finally:
            session.close()
    
    def get_bot_info(self, bot_id: str) -> Optional[Dict]:
        """Get information about a specific bot"""
        session = self.Session()
        try:
            bot = session.query(BotRegistry).filter_by(bot_id=bot_id).first()
            if bot:
                return {
                    'bot_id': bot.bot_id,
                    'bot_name': bot.bot_name,
                    'strategy_type': bot.strategy_type,
                    'alpaca_account': bot.alpaca_account,
                    'is_active': bot.is_active,
                    'config': bot.config,
                    'created_at': bot.created_at,
                    'updated_at': bot.updated_at
                }
            return None
        except Exception as e:
            logger.error(f"Error getting bot info: {e}")
            return None
        finally:
            session.close()
    
    def list_active_bots(self) -> List[Dict]:
        """List all active bots"""
        session = self.Session()
        try:
            bots = session.query(BotRegistry).filter_by(is_active=True).all()
            return [
                {
                    'bot_id': bot.bot_id,
                    'bot_name': bot.bot_name,
                    'strategy_type': bot.strategy_type,
                    'alpaca_account': bot.alpaca_account
                }
                for bot in bots
            ]
        except Exception as e:
            logger.error(f"Error listing bots: {e}")
            return []
        finally:
            session.close()
    
    def log_trade_entry(self, position: Dict, signal: Dict, contract: Dict, 
                       exit_levels: Dict, bot_id: str = None) -> None:
        """Log new trade entry with bot_id"""
        bot_id = bot_id or self.bot_id
        if not bot_id:
            raise ValueError("bot_id must be specified")
        
        # Add bot_id to trade data
        trade_data = {
            'bot_id': bot_id,
            'position_id': position['position_id'],
            'symbol': position['symbol'],
            'contract_symbol': contract['contract_symbol'],
            'option_type': contract['option_type'],
            'signal_type': signal['type'],
            'entry_time': datetime.now(),
            'entry_price': position['entry_price'],
            'contracts': position['contracts'],
            'or_high': signal.get('or_level') if signal['type'] == 'LONG' else None,
            'or_low': signal.get('or_level') if signal['type'] == 'SHORT' else None,
            'ema_8': signal['ema_8'],
            'ema_21': signal['ema_21'],
            'atr': signal['atr'],
            'volume_ratio': signal['volume_ratio'],
            'greeks': contract['greeks'],
            'stop_loss': exit_levels['stop_loss'],
            'target_1': exit_levels['target_1'],
            'target_2': exit_levels['target_2'],
            'status': 'OPEN'
        }
        
        with self.lock:
            self.trade_queue.append({
                'action': 'INSERT',
                'data': trade_data
            })
            
            # Log execution with bot_id
            self.execution_queue.append({
                'bot_id': bot_id,
                'position_id': position['position_id'],
                'timestamp': datetime.now(),
                'action': 'ENTRY',
                'contracts': position['contracts'],
                'price': position['entry_price'],
                'details': {'signal': signal, 'contract': contract}
            })
            
            if len(self.trade_queue) >= self.batch_size:
                self._flush_trades()
    
    def log_risk_metrics(self, metrics: Dict, bot_id: str = None) -> None:
        """Log risk metrics with bot_id"""
        bot_id = bot_id or self.bot_id
        if not bot_id:
            raise ValueError("bot_id must be specified")
        
        metric_data = {
            'bot_id': bot_id,
            'timestamp': datetime.now(),
            'current_equity': metrics['current_equity'],
            'daily_pnl': metrics['daily_pnl'],
            'daily_pnl_pct': metrics['daily_pnl_pct'],
            'consecutive_losses': metrics['consecutive_losses'],
            'active_positions': metrics['active_positions'],
            'trades_today': metrics['trades_today'],
            'trading_enabled': metrics['trading_enabled']
        }
        
        with self.lock:
            self.metrics_queue.append(metric_data)
            
            if len(self.metrics_queue) >= self.batch_size:
                self._flush_metrics()
    
    def get_bot_daily_trades(self, bot_id: str, date: datetime) -> List[Dict]:
        """Get all trades for a specific bot on a specific date"""
        cache_key = f"bot_daily_trades_{bot_id}_{date.date()}"
        
        # Check cache
        if cache_key in self._cache:
            cached_time, cached_data = self._cache[cache_key]
            if time.time() - cached_time < self._cache_ttl:
                return cached_data
        
        self._flush_all_batches()
        
        session = self.Session()
        try:
            trades = session.query(Trade).filter(
                Trade.bot_id == bot_id,
                Trade.entry_time >= date.replace(hour=0, minute=0, second=0),
                Trade.entry_time < date.replace(hour=23, minute=59, second=59)
            ).all()
            
            result = [self._trade_to_dict(trade) for trade in trades]
            self._cache[cache_key] = (time.time(), result)
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting bot daily trades: {e}")
            return []
        finally:
            session.close()
    
    def get_bot_performance_metrics(self, bot_id: str, days: int = 30) -> Dict:
        """Get performance metrics for a specific bot"""
        self._flush_all_batches()
        
        session = self.Session()
        try:
            cutoff_date = datetime.now() - timedelta(days=days)
            trades = session.query(Trade).filter(
                Trade.bot_id == bot_id,
                Trade.status == 'CLOSED',
                Trade.entry_time >= cutoff_date
            ).all()
            
            if not trades:
                return {'bot_id': bot_id, 'total_trades': 0}
            
            wins = [t for t in trades if t.realized_pnl > 0]
            losses = [t for t in trades if t.realized_pnl <= 0]
            
            total_trades = len(trades)
            win_rate = len(wins) / total_trades if total_trades > 0 else 0
            
            avg_win = sum(t.realized_pnl for t in wins) / len(wins) if wins else 0
            avg_loss = sum(t.realized_pnl for t in losses) / len(losses) if losses else 0
            
            return {
                'bot_id': bot_id,
                'total_trades': total_trades,
                'wins': len(wins),
                'losses': len(losses),
                'win_rate': win_rate,
                'average_win': avg_win,
                'average_loss': avg_loss,
                'total_pnl': sum(t.realized_pnl for t in trades),
                'profit_factor': abs(sum(t.realized_pnl for t in wins) / 
                                   sum(t.realized_pnl for t in losses)) if losses and sum(t.realized_pnl for t in losses) != 0 else float('inf'),
                'best_trade': max(t.realized_pnl for t in trades),
                'worst_trade': min(t.realized_pnl for t in trades),
                'period_days': days
            }
            
        except Exception as e:
            logger.error(f"Error getting bot performance metrics: {e}")
            return {'bot_id': bot_id, 'error': str(e)}
        finally:
            session.close()
    
    def compare_bots_performance(self, days: int = 30) -> List[Dict]:
        """Compare performance across all active bots"""
        active_bots = self.list_active_bots()
        performances = []
        
        for bot in active_bots:
            metrics = self.get_bot_performance_metrics(bot['bot_id'], days)
            metrics['bot_name'] = bot['bot_name']
            metrics['strategy_type'] = bot['strategy_type']
            performances.append(metrics)
        
        # Sort by total P&L descending
        performances.sort(key=lambda x: x.get('total_pnl', 0), reverse=True)
        
        return performances