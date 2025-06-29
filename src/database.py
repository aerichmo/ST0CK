from sqlalchemy import create_engine, Column, String, Float, Integer, DateTime, Boolean, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timedelta
import logging
from typing import Dict, List, Optional
from collections import deque
import threading
import time
import socket
from urllib.parse import urlparse, urlunparse

logger = logging.getLogger(__name__)
Base = declarative_base()

# IPv4 cache for DNS lookups
_ipv4_cache = {}

class Trade(Base):
    __tablename__ = 'trades'
    
    id = Column(Integer, primary_key=True)
    position_id = Column(String, unique=True, nullable=False)
    symbol = Column(String, nullable=False)
    contract_symbol = Column(String, nullable=False)
    option_type = Column(String, nullable=False)
    signal_type = Column(String, nullable=False)
    
    entry_time = Column(DateTime, nullable=False)
    entry_price = Column(Float, nullable=False)
    contracts = Column(Integer, nullable=False)
    
    exit_time = Column(DateTime)
    exit_price = Column(Float)
    exit_reason = Column(String)
    
    realized_pnl = Column(Float, default=0.0)
    commission = Column(Float, default=0.0)
    
    or_high = Column(Float)
    or_low = Column(Float)
    ema_8 = Column(Float)
    ema_21 = Column(Float)
    atr = Column(Float)
    volume_ratio = Column(Float)
    
    greeks = Column(JSON)
    
    stop_loss = Column(Float)
    target_1 = Column(Float)
    target_2 = Column(Float)
    
    status = Column(String, default='OPEN')
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class ExecutionLog(Base):
    __tablename__ = 'execution_logs'
    
    id = Column(Integer, primary_key=True)
    position_id = Column(String, nullable=False)
    timestamp = Column(DateTime, nullable=False)
    action = Column(String, nullable=False)
    contracts = Column(Integer)
    price = Column(Float)
    details = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)

class RiskMetrics(Base):
    __tablename__ = 'risk_metrics'
    
    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, nullable=False)
    current_equity = Column(Float, nullable=False)
    daily_pnl = Column(Float, nullable=False)
    daily_pnl_pct = Column(Float, nullable=False)
    consecutive_losses = Column(Integer, default=0)
    active_positions = Column(Integer, default=0)
    trades_today = Column(Integer, default=0)
    trading_enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class BatchedDatabaseManager:
    """Database manager with batched writes for improved performance"""
    
    def __init__(self, connection_string: str, batch_size: int = 10, 
                 flush_interval: float = 5.0):
        # SQLite doesn't support pool_size parameters
        if 'sqlite' in connection_string:
            self.engine = create_engine(connection_string)
        else:
            # Force IPv4 for Supabase connections
            if 'supabase.co' in connection_string:
                # Parse and rebuild connection string to force IPv4
                parsed = urlparse(connection_string)
                hostname = parsed.hostname
                
                # Resolve to IPv4 address with caching
                try:
                    if hostname not in _ipv4_cache:
                        _ipv4_cache[hostname] = socket.gethostbyname(hostname)
                    ipv4_addr = _ipv4_cache[hostname]
                    
                    # Replace hostname with IPv4 address
                    netloc = parsed.netloc.replace(hostname, ipv4_addr)
                    connection_string = urlunparse((
                        parsed.scheme,
                        netloc,
                        parsed.path,
                        parsed.params,
                        parsed.query,
                        parsed.fragment
                    ))
                    logger.info(f"Using IPv4 address for database: {ipv4_addr}")
                except Exception as e:
                    logger.warning(f"Could not resolve to IPv4: {e}")
                
                # Add connect_args to force IPv4
                self.engine = create_engine(
                    connection_string,
                    pool_size=10,
                    max_overflow=20,
                    pool_pre_ping=True,
                    connect_args={
                        "connect_timeout": 10,
                        "options": "-c statement_timeout=30000"
                    }
                )
            else:
                self.engine = create_engine(connection_string, 
                                           pool_size=10, 
                                           max_overflow=20,
                                           pool_pre_ping=True)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        
        # Batching configuration
        self.batch_size = batch_size
        self.flush_interval = flush_interval
        
        # Batch queues for different operations
        self.trade_queue = deque()
        self.execution_queue = deque()
        self.metrics_queue = deque()
        
        # Thread safety
        self.lock = threading.Lock()
        self.stop_event = threading.Event()
        
        # Start background flush thread
        self.flush_thread = threading.Thread(target=self._flush_worker, daemon=True)
        self.flush_thread.start()
        
        # Cache for frequently accessed data
        self._cache = {}
        self._cache_ttl = 60  # seconds
        
    def _flush_worker(self):
        """Background thread that periodically flushes batches"""
        while not self.stop_event.is_set():
            try:
                self._flush_all_batches()
                time.sleep(self.flush_interval)
            except Exception as e:
                logger.error(f"Error in flush worker: {e}")
                time.sleep(1)  # Brief pause before retry
    
    def _flush_all_batches(self):
        """Flush all pending batches to database"""
        with self.lock:
            if self.trade_queue or self.execution_queue or self.metrics_queue:
                self._flush_trades()
                self._flush_executions()
                self._flush_metrics()
    
    def _flush_queue(self, queue, model_class, queue_name):
        """Generic flush method for any queue"""
        if not queue:
            return
            
        session = self.Session()
        try:
            if queue_name == 'trade':
                # Special handling for trades with actions
                while queue:
                    trade_data = queue.popleft()
                    
                    if trade_data['action'] == 'INSERT':
                        trade = Trade(**trade_data['data'])
                        session.add(trade)
                    elif trade_data['action'] == 'UPDATE':
                        trade = session.query(Trade).filter_by(
                            position_id=trade_data['position_id']
                        ).first()
                        if trade:
                            for key, value in trade_data['data'].items():
                                setattr(trade, key, value)
            else:
                # Bulk insert for other queues - more efficient with bulk_insert_mappings
                session.bulk_insert_mappings(model_class, list(queue))
                queue.clear()
            
            session.commit()
            logger.debug(f"Flushed {len(queue)} {queue_name}s to database")
            
        except Exception as e:
            logger.error(f"Error flushing {queue_name}s: {e}")
            session.rollback()
        finally:
            session.close()
    
    def _flush_trades(self):
        """Flush pending trades to database"""
        self._flush_queue(self.trade_queue, Trade, 'trade')
    
    def _flush_executions(self):
        """Flush pending executions to database"""
        self._flush_queue(self.execution_queue, ExecutionLog, 'execution')
    
    def _flush_metrics(self):
        """Flush pending metrics to database"""
        self._flush_queue(self.metrics_queue, RiskMetrics, 'metric')
    
    def log_trade_entry(self, position: Dict, signal: Dict, contract: Dict, 
                       exit_levels: Dict) -> None:
        """Log new trade entry to database (batched)"""
        trade_data = {
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
            
            # Log execution
            self.execution_queue.append({
                'position_id': position['position_id'],
                'timestamp': datetime.now(),
                'action': 'ENTRY',
                'contracts': position['contracts'],
                'price': position['entry_price'],
                'details': {'signal': signal, 'contract': contract}
            })
            
            # Force flush if batch is full
            if len(self.trade_queue) >= self.batch_size:
                self._flush_trades()
    
    def log_trade_exit(self, position_id: str, exit_price: float, 
                      contracts: int, reason: str, pnl: float) -> None:
        """Log trade exit or partial exit (batched)"""
        update_data = {
            'realized_pnl': pnl
        }
        
        # Check if full exit
        with self.lock:
            # Find if this is a full exit (would need to track contracts)
            is_full_exit = True  # Simplified for now
            
            if is_full_exit:
                update_data.update({
                    'exit_time': datetime.now(),
                    'exit_price': exit_price,
                    'exit_reason': reason,
                    'status': 'CLOSED'
                })
            
            self.trade_queue.append({
                'action': 'UPDATE',
                'position_id': position_id,
                'data': update_data
            })
            
            # Log execution
            self.execution_queue.append({
                'position_id': position_id,
                'timestamp': datetime.now(),
                'action': 'EXIT',
                'contracts': contracts,
                'price': exit_price,
                'details': {'reason': reason, 'pnl': pnl}
            })
            
            # Force flush if batch is full
            if len(self.trade_queue) >= self.batch_size:
                self._flush_trades()
    
    def log_execution(self, position_id: str, action: str, contracts: int,
                     price: float, details: Dict) -> None:
        """Log execution details (batched)"""
        with self.lock:
            self.execution_queue.append({
                'position_id': position_id,
                'timestamp': datetime.now(),
                'action': action,
                'contracts': contracts,
                'price': price,
                'details': details
            })
            
            # Force flush if batch is full
            if len(self.execution_queue) >= self.batch_size:
                self._flush_executions()
    
    def log_risk_metrics(self, metrics: Dict) -> None:
        """Log current risk metrics (batched)"""
        metric_data = {
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
            
            # Force flush if batch is full
            if len(self.metrics_queue) >= self.batch_size:
                self._flush_metrics()
    
    def get_daily_trades(self, date: datetime) -> List[Dict]:
        """Get all trades for a specific date (with caching)"""
        cache_key = f"daily_trades_{date.date()}"
        
        # Check cache
        if cache_key in self._cache:
            cached_time, cached_data = self._cache[cache_key]
            if time.time() - cached_time < self._cache_ttl:
                return cached_data
        
        # Ensure pending writes are flushed
        self._flush_all_batches()
        
        session = self.Session()
        try:
            trades = session.query(Trade).filter(
                Trade.entry_time >= date.replace(hour=0, minute=0, second=0),
                Trade.entry_time < date.replace(hour=23, minute=59, second=59)
            ).all()
            
            result = [self._trade_to_dict(trade) for trade in trades]
            
            # Cache result
            self._cache[cache_key] = (time.time(), result)
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting daily trades: {e}")
            return []
        finally:
            session.close()
    
    def get_expectancy_report(self, days: int = 30) -> Dict:
        """Generate expectancy report for recent trading"""
        # Ensure pending writes are flushed
        self._flush_all_batches()
        
        session = self.Session()
        try:
            cutoff_date = datetime.now() - timedelta(days=days)
            trades = session.query(Trade).filter(
                Trade.status == 'CLOSED',
                Trade.entry_time >= cutoff_date
            ).all()
            
            if not trades:
                return {}
            
            wins = [t for t in trades if t.realized_pnl > 0]
            losses = [t for t in trades if t.realized_pnl <= 0]
            
            total_trades = len(trades)
            win_rate = len(wins) / total_trades if total_trades > 0 else 0
            
            avg_win = sum(t.realized_pnl for t in wins) / len(wins) if wins else 0
            avg_loss = sum(t.realized_pnl for t in losses) / len(losses) if losses else 0
            
            expectancy = (win_rate * avg_win) + ((1 - win_rate) * avg_loss)
            
            return {
                'total_trades': total_trades,
                'wins': len(wins),
                'losses': len(losses),
                'win_rate': win_rate,
                'average_win': avg_win,
                'average_loss': avg_loss,
                'expectancy': expectancy,
                'profit_factor': abs(sum(t.realized_pnl for t in wins) / 
                                   sum(t.realized_pnl for t in losses)) if losses else float('inf'),
                'total_pnl': sum(t.realized_pnl for t in trades),
                'period_days': days
            }
            
        except Exception as e:
            logger.error(f"Error generating expectancy report: {e}")
            return {}
        finally:
            session.close()
    
    def _trade_to_dict(self, trade: Trade) -> Dict:
        """Convert Trade object to dictionary"""
        return {
            'position_id': trade.position_id,
            'symbol': trade.symbol,
            'contract_symbol': trade.contract_symbol,
            'option_type': trade.option_type,
            'signal_type': trade.signal_type,
            'entry_time': trade.entry_time,
            'entry_price': trade.entry_price,
            'contracts': trade.contracts,
            'exit_time': trade.exit_time,
            'exit_price': trade.exit_price,
            'exit_reason': trade.exit_reason,
            'realized_pnl': trade.realized_pnl,
            'status': trade.status,
            'greeks': trade.greeks
        }
    
    def force_flush(self):
        """Force immediate flush of all pending batches"""
        self._flush_all_batches()
    
    def close(self):
        """Close database connection and flush pending writes"""
        # Stop background thread
        self.stop_event.set()
        
        # Final flush
        self._flush_all_batches()
        
        # Wait for thread to finish
        if self.flush_thread.is_alive():
            self.flush_thread.join(timeout=5)
        
        # Close engine
        self.engine.dispose()

# Maintain backward compatibility
DatabaseManager = BatchedDatabaseManager