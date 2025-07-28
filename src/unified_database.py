"""
Unified database management V2 - Separate tables for stocks and options
Fixes the position_id constraint error by using appropriate schemas
"""
import os
from contextlib import contextmanager
from datetime import datetime
from typing import Dict, List, Optional, Any
from sqlalchemy import create_engine, Column, String, Float, Integer, DateTime, JSON, Boolean, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, scoped_session

from .unified_logging import get_logger

Base = declarative_base()

# Stock Trades Table - For ST0CKA and stock strategies
class StockTrade(Base):
    __tablename__ = 'stock_trades'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    bot_id = Column(String, nullable=False)
    position_id = Column(String, nullable=False)  # Generated UUID
    symbol = Column(String, nullable=False)
    action = Column(String, nullable=False)  # BUY/SELL
    quantity = Column(Integer, nullable=False)
    entry_price = Column(Float, nullable=False)
    entry_time = Column(DateTime, nullable=False)
    exit_price = Column(Float)
    exit_time = Column(DateTime)
    exit_reason = Column(String)
    realized_pnl = Column(Float)
    pnl_percent = Column(Float)
    commission = Column(Float, default=0.0)
    strategy_details = Column(JSON)
    status = Column(String, default='OPEN')  # OPEN/CLOSED
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_stock_bot_time', 'bot_id', 'entry_time'),
        Index('idx_stock_position', 'position_id'),
        Index('idx_stock_status', 'status'),
    )

# Option Trades Table - For ST0CKG and option strategies  
class OptionTrade(Base):
    __tablename__ = 'option_trades'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    bot_id = Column(String, nullable=False)
    position_id = Column(String, nullable=False)
    symbol = Column(String, nullable=False)  # Underlying symbol
    contract_symbol = Column(String, nullable=False)  # Option contract
    option_type = Column(String, nullable=False)  # CALL/PUT
    strike = Column(Float, nullable=False)
    expiry = Column(DateTime, nullable=False)
    signal_type = Column(String, nullable=False)
    entry_time = Column(DateTime, nullable=False)
    entry_price = Column(Float, nullable=False)
    contracts = Column(Integer, nullable=False)
    exit_time = Column(DateTime)
    exit_price = Column(Float)
    exit_reason = Column(String)
    realized_pnl = Column(Float)
    commission = Column(Float, default=0.0)
    # Greeks at entry
    delta = Column(Float)
    gamma = Column(Float)
    theta = Column(Float)
    vega = Column(Float)
    iv = Column(Float)  # Implied volatility
    strategy_details = Column(JSON)
    status = Column(String, default='OPEN')
    
    __table_args__ = (
        Index('idx_option_bot_time', 'bot_id', 'entry_time'),
        Index('idx_option_position', 'position_id'),
        Index('idx_option_expiry', 'expiry'),
    )

# Straddle Trades Table - For complex option strategies
class StraddleTrade(Base):
    __tablename__ = 'straddle_trades'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    bot_id = Column(String, nullable=False)
    position_id = Column(String, nullable=False)
    symbol = Column(String, nullable=False)
    strike = Column(Float, nullable=False)
    expiry = Column(DateTime, nullable=False)
    call_contract = Column(String, nullable=False)
    put_contract = Column(String, nullable=False)
    entry_time = Column(DateTime, nullable=False)
    call_entry_price = Column(Float, nullable=False)
    put_entry_price = Column(Float, nullable=False)
    contracts = Column(Integer, nullable=False)
    total_premium_paid = Column(Float, nullable=False)
    exit_time = Column(DateTime)
    exit_pnl = Column(Float)
    exit_reason = Column(String)
    max_profit = Column(Float)  # Track best unrealized
    max_loss = Column(Float)    # Track worst unrealized
    strategy_details = Column(JSON)
    status = Column(String, default='OPEN')
    
    __table_args__ = (
        Index('idx_straddle_bot_time', 'bot_id', 'entry_time'),
        Index('idx_straddle_position', 'position_id'),
    )

# Keep existing tables for compatibility
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
    )


class UnifiedDatabaseManager:
    """Enhanced database manager with separate stock/option tables"""
    
    def __init__(self, database_url: str = None):
        self.logger = get_logger(__name__)
        self.database_url = database_url or os.getenv('DATABASE_URL', 'sqlite:///trading_multi.db')
        
        # Create engine
        if self.database_url.startswith('sqlite'):
            self.engine = create_engine(self.database_url, pool_pre_ping=True)
        else:
            self.engine = create_engine(self.database_url, pool_pre_ping=True, pool_size=10)
        
        # Create session factory
        self.Session = scoped_session(sessionmaker(bind=self.engine))
        
        # Create tables if they don't exist
        Base.metadata.create_all(self.engine)
        
    @contextmanager
    def get_session(self):
        """Get a database session"""
        session = self.Session()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            raise
        finally:
            session.close()
    
    def log_stock_trade(self, bot_id: str, trade_data: Dict[str, Any]):
        """Log a stock trade to the database"""
        try:
            with self.get_session() as session:
                trade = StockTrade(
                    bot_id=bot_id,
                    position_id=trade_data.get('position_id', f"STK_{datetime.now().timestamp()}"),
                    symbol=trade_data['symbol'],
                    action=trade_data['action'],
                    quantity=trade_data['quantity'],
                    entry_price=trade_data['entry_price'],
                    entry_time=trade_data['entry_time'],
                    strategy_details=trade_data.get('strategy_details', {})
                )
                session.add(trade)
                session.flush()
                return trade.id
        except Exception as e:
            self.logger.error(f"Error logging stock trade: {e}")
            return None
    
    def log_option_trade(self, bot_id: str, trade_data: Dict[str, Any]):
        """Log an option trade to the database"""
        try:
            with self.get_session() as session:
                trade = OptionTrade(
                    bot_id=bot_id,
                    position_id=trade_data['position_id'],
                    symbol=trade_data['symbol'],
                    contract_symbol=trade_data['contract_symbol'],
                    option_type=trade_data['option_type'],
                    strike=trade_data['strike'],
                    expiry=trade_data['expiry'],
                    signal_type=trade_data['signal_type'],
                    entry_time=trade_data['entry_time'],
                    entry_price=trade_data['entry_price'],
                    contracts=trade_data['contracts'],
                    delta=trade_data.get('delta'),
                    gamma=trade_data.get('gamma'),
                    theta=trade_data.get('theta'),
                    vega=trade_data.get('vega'),
                    iv=trade_data.get('iv'),
                    strategy_details=trade_data.get('strategy_details', {})
                )
                session.add(trade)
                session.flush()
                return trade.id
        except Exception as e:
            self.logger.error(f"Error logging option trade: {e}")
            return None
    
    def log_straddle_trade(self, bot_id: str, trade_data: Dict[str, Any]):
        """Log a straddle trade to the database"""
        try:
            with self.get_session() as session:
                trade = StraddleTrade(
                    bot_id=bot_id,
                    position_id=trade_data['position_id'],
                    symbol=trade_data['symbol'],
                    strike=trade_data['strike'],
                    expiry=trade_data['expiry'],
                    call_contract=trade_data['call_contract'],
                    put_contract=trade_data['put_contract'],
                    entry_time=trade_data['entry_time'],
                    call_entry_price=trade_data['call_entry_price'],
                    put_entry_price=trade_data['put_entry_price'],
                    contracts=trade_data['contracts'],
                    total_premium_paid=trade_data['total_premium_paid'],
                    strategy_details=trade_data.get('strategy_details', {})
                )
                session.add(trade)
                session.flush()
                return trade.id
        except Exception as e:
            self.logger.error(f"Error logging straddle trade: {e}")
            return None
    
    def update_stock_trade_exit(self, position_id: str, exit_data: Dict[str, Any]):
        """Update stock trade with exit information"""
        try:
            with self.get_session() as session:
                trade = session.query(StockTrade).filter_by(position_id=position_id).first()
                if trade:
                    trade.exit_price = exit_data['exit_price']
                    trade.exit_time = exit_data['exit_time']
                    trade.exit_reason = exit_data.get('exit_reason')
                    trade.realized_pnl = exit_data.get('realized_pnl')
                    trade.pnl_percent = exit_data.get('pnl_percent')
                    trade.status = 'CLOSED'
                    session.commit()
                    return True
        except Exception as e:
            self.logger.error(f"Error updating stock trade exit: {e}")
        return False
    
    def update_option_trade_exit(self, position_id: str, exit_data: Dict[str, Any]):
        """Update option trade with exit information"""
        try:
            with self.get_session() as session:
                trade = session.query(OptionTrade).filter_by(position_id=position_id).first()
                if trade:
                    trade.exit_price = exit_data['exit_price']
                    trade.exit_time = exit_data['exit_time']
                    trade.exit_reason = exit_data.get('exit_reason')
                    trade.realized_pnl = exit_data.get('realized_pnl')
                    trade.status = 'CLOSED'
                    session.commit()
                    return True
        except Exception as e:
            self.logger.error(f"Error updating option trade exit: {e}")
        return False
    
    def get_daily_performance(self, bot_id: str, date: datetime = None) -> Dict[str, Any]:
        """Get daily performance metrics for a bot"""
        if date is None:
            date = datetime.now()
            
        start_of_day = date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = date.replace(hour=23, minute=59, second=59, microsecond=999999)
        
        with self.get_session() as session:
            # Check stock trades
            stock_trades = session.query(StockTrade).filter(
                StockTrade.bot_id == bot_id,
                StockTrade.entry_time >= start_of_day,
                StockTrade.entry_time <= end_of_day
            ).all()
            
            # Check option trades
            option_trades = session.query(OptionTrade).filter(
                OptionTrade.bot_id == bot_id,
                OptionTrade.entry_time >= start_of_day,
                OptionTrade.entry_time <= end_of_day
            ).all()
            
            # Calculate metrics
            total_trades = len(stock_trades) + len(option_trades)
            total_pnl = sum(t.realized_pnl or 0 for t in stock_trades) + \
                       sum(t.realized_pnl or 0 for t in option_trades)
            
            wins = len([t for t in stock_trades if (t.realized_pnl or 0) > 0]) + \
                   len([t for t in option_trades if (t.realized_pnl or 0) > 0])
            
            return {
                'date': date.date(),
                'total_trades': total_trades,
                'stock_trades': len(stock_trades),
                'option_trades': len(option_trades),
                'total_pnl': total_pnl,
                'wins': wins,
                'losses': total_trades - wins,
                'win_rate': (wins / total_trades * 100) if total_trades > 0 else 0
            }
    
    def log_execution(self, bot_id: str, action: str, details: Dict[str, Any] = None, error: str = None):
        """Log execution events"""
        try:
            with self.get_session() as session:
                log = ExecutionLog(
                    bot_id=bot_id,
                    timestamp=datetime.now(),
                    action=action,
                    details=details or {},
                    error=error
                )
                session.add(log)
        except Exception as e:
            self.logger.error(f"Error logging execution: {e}")
    
    def log_risk_metric(self, bot_id: str, metric_type: str, value: float, metadata: Dict[str, Any] = None):
        """Log risk metrics"""
        try:
            with self.get_session() as session:
                metric = RiskMetrics(
                    bot_id=bot_id,
                    timestamp=datetime.now(),
                    metric_type=metric_type,
                    value=value,
                    metric_metadata=metadata or {}
                )
                session.add(metric)
        except Exception as e:
            self.logger.error(f"Error logging risk metric: {e}")
    
    def register_bot(self, bot_id: str, config: Dict[str, Any]):
        """Register a bot (for compatibility)"""
        self.logger.info(f"Bot registered: {bot_id}")
        # In V2 we don't need a separate bot registration table
        # Each trade table tracks bot_id
        pass
    
    def get_trades(self, bot_id: str, limit: int = 100) -> List[Any]:
        """Get recent trades for a bot (compatibility method)"""
        try:
            with self.get_session() as session:
                # Get stock trades
                stock_trades = session.query(StockTrade).filter(
                    StockTrade.bot_id == bot_id
                ).order_by(StockTrade.entry_time.desc()).limit(limit // 2).all()
                
                # Get option trades
                option_trades = session.query(OptionTrade).filter(
                    OptionTrade.bot_id == bot_id
                ).order_by(OptionTrade.entry_time.desc()).limit(limit // 2).all()
                
                # Combine and sort by entry time
                all_trades = []
                
                # Convert to common format
                for trade in stock_trades:
                    all_trades.append(type('Trade', (), {
                        'id': trade.id,
                        'position_id': trade.position_id,
                        'symbol': trade.symbol,
                        'entry_time': trade.entry_time,
                        'entry_price': trade.entry_price,
                        'exit_price': trade.exit_price,
                        'pnl': trade.realized_pnl,
                        'status': trade.status
                    }))
                
                for trade in option_trades:
                    all_trades.append(type('Trade', (), {
                        'id': trade.id,
                        'position_id': trade.position_id,
                        'symbol': trade.symbol,
                        'entry_time': trade.entry_time,
                        'entry_price': trade.entry_price,
                        'exit_price': trade.exit_price,
                        'pnl': trade.realized_pnl,
                        'status': trade.status
                    }))
                
                # Sort by entry time
                all_trades.sort(key=lambda x: x.entry_time, reverse=True)
                
                return all_trades[:limit]
                
        except Exception as e:
            self.logger.error(f"Error getting trades: {e}")
            return []
    
    def close(self):
        """Close database connections"""
        try:
            self.Session.remove()
            self.engine.dispose()
        except Exception as e:
            self.logger.error(f"Error closing database: {e}")