"""
Unified database management with proper connection pooling and session handling
Consolidates database.py and multi_bot_database.py functionality
"""
import os
import socket
from contextlib import contextmanager
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from urllib.parse import urlparse, urlunparse
from collections import defaultdict
import threading
from queue import Queue, Empty

from sqlalchemy import create_engine, Column, String, Float, Integer, DateTime, JSON, Boolean, Index, event
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, scoped_session, Session
from sqlalchemy.pool import NullPool, QueuePool, StaticPool
from sqlalchemy.exc import OperationalError, DisconnectionError

from .unified_logging import get_logger, LogContext
from .error_reporter import ErrorReporter

Base = declarative_base()

# Table Definitions - Consolidated from all sources
class Trade(Base):
    __tablename__ = 'trades'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    bot_id = Column(String, nullable=False)
    symbol = Column(String, nullable=False)
    action = Column(String, nullable=False)
    quantity = Column(Integer, nullable=False)
    entry_price = Column(Float, nullable=False)
    exit_price = Column(Float)
    entry_time = Column(DateTime, nullable=False)
    exit_time = Column(DateTime)
    pnl = Column(Float)
    pnl_percent = Column(Float)
    strategy_details = Column(JSON)
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_bot_entry_time', 'bot_id', 'entry_time'),
        Index('idx_bot_symbol', 'bot_id', 'symbol'),
        Index('idx_entry_time', 'entry_time'),
    )

class ExecutionLog(Base):
    __tablename__ = 'execution_logs'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    bot_id = Column(String, nullable=False)
    timestamp = Column(DateTime, nullable=False)
    action = Column(String, nullable=False)
    details = Column(JSON)
    error = Column(String)
    
    __table_args__ = (
        Index('idx_exec_bot_time', 'bot_id', 'timestamp'),
    )

class RiskMetrics(Base):
    __tablename__ = 'risk_metrics'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    bot_id = Column(String, nullable=False)
    timestamp = Column(DateTime, nullable=False)
    metric_type = Column(String, nullable=False)
    value = Column(Float, nullable=False)
    metric_metadata = Column(JSON)
    
    __table_args__ = (
        Index('idx_risk_bot_time', 'bot_id', 'timestamp'),
        Index('idx_risk_type', 'metric_type'),
    )

class BotRegistry(Base):
    __tablename__ = 'bot_registry'
    
    bot_id = Column(String, primary_key=True)
    created_at = Column(DateTime, nullable=False)
    config = Column(JSON, nullable=False)
    active = Column(Boolean, default=True)
    last_seen = Column(DateTime)
    performance_stats = Column(JSON)

class BattleLines(Base):
    __tablename__ = 'battle_lines'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, nullable=False)
    pdh = Column(Float)
    pdl = Column(Float)
    overnight_high = Column(Float)
    overnight_low = Column(Float)
    premarket_high = Column(Float)
    premarket_low = Column(Float)
    rth_high = Column(Float)
    rth_low = Column(Float)
    
    __table_args__ = (
        Index('idx_battle_lines_timestamp', 'timestamp'),
    )

class UnifiedDatabaseManager:
    """
    Unified database manager with proper connection pooling and session management
    Replaces both BatchedDatabaseManager and MultiBotDatabaseManager
    """
    
    def __init__(self, database_url: Optional[str] = None, bot_id: Optional[str] = None):
        """
        Initialize unified database manager
        
        Args:
            database_url: Database connection URL
            bot_id: Optional bot identifier for context
        """
        self.bot_id = bot_id
        self.logger = get_logger(__name__, bot_id)
        
        # Get database URL
        self.database_url = database_url or os.getenv('DATABASE_URL', 'sqlite:///trading_multi.db')
        
        # Create engine with appropriate pooling
        self.engine = self._create_engine()
        
        # Create session factory
        self.session_factory = sessionmaker(bind=self.engine)
        self.Session = scoped_session(self.session_factory)
        
        # Create tables if they don't exist
        Base.metadata.create_all(self.engine)
        
        # Initialize batching system
        self._init_batching()
        
        # Start background workers
        self._start_workers()
        
        self.logger.info(f"[{bot_id}] Database manager initialized with URL: {self._safe_url()}")
    
    def _create_engine(self):
        """Create SQLAlchemy engine with appropriate pooling configuration"""
        parsed_url = urlparse(self.database_url)
        
        # SQLite configuration
        if parsed_url.scheme == 'sqlite':
            # Use StaticPool for SQLite to avoid threading issues
            return create_engine(
                self.database_url,
                poolclass=StaticPool,
                connect_args={'check_same_thread': False}
            )
        
        # PostgreSQL/Supabase configuration
        elif parsed_url.scheme in ['postgresql', 'postgres']:
            # Handle Supabase IPv4 resolution
            if 'supabase' in parsed_url.hostname:
                resolved_url = self._resolve_to_ipv4(self.database_url)
            else:
                resolved_url = self.database_url
            
            # Create engine with proper pooling
            engine = create_engine(
                resolved_url,
                poolclass=QueuePool,
                pool_size=10,
                max_overflow=20,
                pool_timeout=30,
                pool_recycle=3600,  # Recycle connections after 1 hour
                pool_pre_ping=True,  # Verify connections before use
                connect_args={
                    'connect_timeout': 10,
                    'options': '-c statement_timeout=30000'  # 30 second statement timeout
                }
            )
            
            # Add connection event listeners
            @event.listens_for(engine, "connect")
            def receive_connect(dbapi_connection, connection_record):
                self.logger.debug(f"[{self.bot_id}] Database connection established")
            
            @event.listens_for(engine, "checkout")
            def receive_checkout(dbapi_connection, connection_record, connection_proxy):
                # Test connection is alive
                try:
                    dbapi_connection.cursor().execute("SELECT 1")
                except:
                    # Connection is dead, invalidate it
                    connection_proxy._pool._invalidate(connection_proxy)
                    raise DisconnectionError("Connection ping failed")
            
            return engine
        
        else:
            # Default configuration for other databases
            return create_engine(self.database_url, pool_pre_ping=True)
    
    def _resolve_to_ipv4(self, url: str) -> str:
        """Resolve hostname to IPv4 address for Supabase compatibility"""
        parsed = urlparse(url)
        hostname = parsed.hostname
        
        try:
            # Force IPv4 resolution
            ipv4_address = socket.getaddrinfo(hostname, None, socket.AF_INET)[0][4][0]
            
            # Reconstruct URL with IPv4 address
            new_netloc = parsed.netloc.replace(hostname, ipv4_address)
            resolved_url = urlunparse((
                parsed.scheme,
                new_netloc,
                parsed.path,
                parsed.params,
                parsed.query,
                parsed.fragment
            ))
            
            self.logger.debug(f"Resolved {hostname} to {ipv4_address}")
            return resolved_url
            
        except Exception as e:
            self.logger.warning(f"Failed to resolve {hostname} to IPv4: {e}, using original URL")
            return url
    
    def _safe_url(self) -> str:
        """Return database URL with password masked"""
        parsed = urlparse(self.database_url)
        if parsed.password:
            return self.database_url.replace(parsed.password, '***')
        return self.database_url
    
    def _init_batching(self):
        """Initialize batching system for write operations"""
        self.batch_size = 10
        self.flush_interval = 5.0  # seconds
        
        # Queues for batched operations
        self.trade_queue = Queue()
        self.execution_queue = Queue()
        self.metrics_queue = Queue()
        
        # Shutdown event
        self.shutdown_event = threading.Event()
    
    def _start_workers(self):
        """Start background worker threads"""
        # Batch flush worker
        self.flush_thread = threading.Thread(
            target=self._flush_worker,
            name=f"db-flush-{self.bot_id}",
            daemon=True
        )
        self.flush_thread.start()
    
    def _flush_worker(self):
        """Background worker for flushing batched operations"""
        while not self.shutdown_event.is_set():
            try:
                # Wait for flush interval or shutdown
                if self.shutdown_event.wait(self.flush_interval):
                    break
                
                # Flush all queues
                self._flush_all()
                
            except Exception as e:
                self.logger.error(f"[{self.bot_id}] Flush worker error: {e}", exc_info=True)
    
    def _flush_all(self):
        """Flush all pending operations"""
        with self.session_scope() as session:
            # Flush trades
            trades = self._drain_queue(self.trade_queue, self.batch_size)
            if trades:
                session.bulk_insert_mappings(Trade, trades)
                self.logger.debug(f"[{self.bot_id}] Flushed {len(trades)} trades")
            
            # Flush executions
            executions = self._drain_queue(self.execution_queue, self.batch_size)
            if executions:
                session.bulk_insert_mappings(ExecutionLog, executions)
                self.logger.debug(f"[{self.bot_id}] Flushed {len(executions)} executions")
            
            # Flush metrics
            metrics = self._drain_queue(self.metrics_queue, self.batch_size)
            if metrics:
                session.bulk_insert_mappings(RiskMetrics, metrics)
                self.logger.debug(f"[{self.bot_id}] Flushed {len(metrics)} metrics")
    
    def _drain_queue(self, queue: Queue, max_items: int) -> List[Dict]:
        """Drain items from queue up to max_items"""
        items = []
        try:
            for _ in range(max_items):
                item = queue.get_nowait()
                items.append(item)
        except Empty:
            pass
        return items
    
    @contextmanager
    def session_scope(self):
        """Provide a transactional scope for database operations"""
        session = self.Session()
        try:
            yield session
            session.commit()
        except OperationalError as e:
            session.rollback()
            self.logger.error(f"[{self.bot_id}] Database operational error: {e}")
            raise
        except Exception as e:
            session.rollback()
            self.logger.error(f"[{self.bot_id}] Database error: {e}", exc_info=True)
            raise
        finally:
            session.close()
    
    def log_trade(self, trade_data: Dict[str, Any]):
        """Log a trade (batched)"""
        # Add bot_id if not present
        if self.bot_id and 'bot_id' not in trade_data:
            trade_data['bot_id'] = self.bot_id
        
        # Add to queue
        self.trade_queue.put(trade_data)
        
        # Force flush if queue is large
        if self.trade_queue.qsize() >= self.batch_size:
            self._flush_all()
    
    def log_execution(self, action: str, details: Dict[str, Any], error: Optional[str] = None):
        """Log an execution event (batched)"""
        execution_data = {
            'bot_id': self.bot_id,
            'timestamp': datetime.now(),
            'action': action,
            'details': details,
            'error': error
        }
        
        self.execution_queue.put(execution_data)
        
        # Force flush if queue is large
        if self.execution_queue.qsize() >= self.batch_size:
            self._flush_all()
    
    def log_risk_metric(self, metric_type: str, value: float, metadata: Optional[Dict] = None):
        """Log a risk metric (batched)"""
        metric_data = {
            'bot_id': self.bot_id,
            'timestamp': datetime.now(),
            'metric_type': metric_type,
            'value': value,
            'metric_metadata': metadata or {}
        }
        
        self.metrics_queue.put(metric_data)
        
        # Force flush if queue is large
        if self.metrics_queue.qsize() >= self.batch_size:
            self._flush_all()
    
    def get_trades(self, bot_id: Optional[str] = None, limit: int = 100) -> List[Trade]:
        """Get recent trades"""
        with self.session_scope() as session:
            query = session.query(Trade)
            
            if bot_id:
                query = query.filter(Trade.bot_id == bot_id)
            elif self.bot_id:
                query = query.filter(Trade.bot_id == self.bot_id)
            
            return query.order_by(Trade.entry_time.desc()).limit(limit).all()
    
    def get_active_positions(self, bot_id: Optional[str] = None) -> List[Trade]:
        """Get active positions"""
        with self.session_scope() as session:
            query = session.query(Trade).filter(Trade.exit_time.is_(None))
            
            if bot_id:
                query = query.filter(Trade.bot_id == bot_id)
            elif self.bot_id:
                query = query.filter(Trade.bot_id == self.bot_id)
            
            return query.all()
    
    def update_trade_exit(self, trade_id: int, exit_price: float, exit_time: datetime, pnl: float, pnl_percent: float):
        """Update trade with exit information"""
        with self.session_scope() as session:
            trade = session.query(Trade).filter(Trade.id == trade_id).first()
            if trade:
                trade.exit_price = exit_price
                trade.exit_time = exit_time
                trade.pnl = pnl
                trade.pnl_percent = pnl_percent
                self.logger.info(f"[{self.bot_id}] Updated trade {trade_id} with exit")
    
    def register_bot(self, bot_id: str, config: Dict[str, Any]):
        """Register a bot in the registry"""
        with self.session_scope() as session:
            bot = session.query(BotRegistry).filter(BotRegistry.bot_id == bot_id).first()
            
            if bot:
                # Update existing bot
                bot.last_seen = datetime.now()
                bot.config = config
                bot.active = True
            else:
                # Create new bot
                bot = BotRegistry(
                    bot_id=bot_id,
                    created_at=datetime.now(),
                    config=config,
                    active=True,
                    last_seen=datetime.now()
                )
                session.add(bot)
            
            self.logger.info(f"Registered bot: {bot_id}")
    
    def get_performance_stats(self, bot_id: Optional[str] = None, days: int = 30) -> Dict[str, Any]:
        """Get performance statistics for a bot"""
        from datetime import timedelta
        
        with self.session_scope() as session:
            cutoff_date = datetime.now() - timedelta(days=days)
            
            query = session.query(Trade).filter(
                Trade.exit_time.isnot(None),
                Trade.entry_time >= cutoff_date
            )
            
            if bot_id:
                query = query.filter(Trade.bot_id == bot_id)
            elif self.bot_id:
                query = query.filter(Trade.bot_id == self.bot_id)
            
            trades = query.all()
            
            if not trades:
                return {
                    'total_trades': 0,
                    'winning_trades': 0,
                    'losing_trades': 0,
                    'win_rate': 0.0,
                    'total_pnl': 0.0,
                    'avg_pnl': 0.0,
                    'max_pnl': 0.0,
                    'min_pnl': 0.0
                }
            
            winning_trades = [t for t in trades if t.pnl > 0]
            losing_trades = [t for t in trades if t.pnl <= 0]
            total_pnl = sum(t.pnl for t in trades)
            
            return {
                'total_trades': len(trades),
                'winning_trades': len(winning_trades),
                'losing_trades': len(losing_trades),
                'win_rate': len(winning_trades) / len(trades) if trades else 0.0,
                'total_pnl': total_pnl,
                'avg_pnl': total_pnl / len(trades) if trades else 0.0,
                'max_pnl': max(t.pnl for t in trades) if trades else 0.0,
                'min_pnl': min(t.pnl for t in trades) if trades else 0.0
            }
    
    def close(self):
        """Close database connections and cleanup"""
        self.logger.info(f"[{self.bot_id}] Shutting down database manager")
        
        # Signal shutdown
        self.shutdown_event.set()
        
        # Final flush
        self._flush_all()
        
        # Wait for thread to finish
        if hasattr(self, 'flush_thread'):
            self.flush_thread.join(timeout=5.0)
        
        # Close session and engine
        self.Session.remove()
        self.engine.dispose()
        
        self.logger.info(f"[{self.bot_id}] Database manager shutdown complete")

# Battle lines specific functions (preserved from battle_lines_manager.py)
def save_battle_lines(db_manager: UnifiedDatabaseManager, battle_lines_data: Dict[str, float]):
    """Save battle lines data"""
    with db_manager.session_scope() as session:
        battle_lines = BattleLines(
            timestamp=datetime.now(),
            **battle_lines_data
        )
        session.add(battle_lines)
        db_manager.logger.info("Battle lines saved to database")

def get_latest_battle_lines(db_manager: UnifiedDatabaseManager) -> Optional[Dict[str, float]]:
    """Get the most recent battle lines"""
    with db_manager.session_scope() as session:
        latest = session.query(BattleLines).order_by(BattleLines.timestamp.desc()).first()
        
        if latest:
            return {
                'pdh': latest.pdh,
                'pdl': latest.pdl,
                'overnight_high': latest.overnight_high,
                'overnight_low': latest.overnight_low,
                'premarket_high': latest.premarket_high,
                'premarket_low': latest.premarket_low,
                'rth_high': latest.rth_high,
                'rth_low': latest.rth_low,
                'timestamp': latest.timestamp
            }
        return None