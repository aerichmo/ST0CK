import psycopg2
from psycopg2.extras import RealDictCursor
from sqlalchemy import create_engine, Column, String, Float, Integer, DateTime, Boolean, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import json
import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)
Base = declarative_base()

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

class DatabaseManager:
    def __init__(self, connection_string: str):
        self.engine = create_engine(connection_string)
        Base.metadata.create_all(self.engine)
        Session = sessionmaker(bind=self.engine)
        self.session = Session()
        
    def log_trade_entry(self, position: Dict, signal: Dict, contract: Dict, 
                       exit_levels: Dict) -> None:
        """Log new trade entry to database"""
        try:
            trade = Trade(
                position_id=position['position_id'],
                symbol=position['symbol'],
                contract_symbol=contract['contract_symbol'],
                option_type=contract['option_type'],
                signal_type=signal['type'],
                entry_time=datetime.now(),
                entry_price=position['entry_price'],
                contracts=position['contracts'],
                or_high=signal.get('or_level') if signal['type'] == 'LONG' else None,
                or_low=signal.get('or_level') if signal['type'] == 'SHORT' else None,
                ema_8=signal['ema_8'],
                ema_21=signal['ema_21'],
                atr=signal['atr'],
                volume_ratio=signal['volume_ratio'],
                greeks=contract['greeks'],
                stop_loss=exit_levels['stop_loss'],
                target_1=exit_levels['target_1'],
                target_2=exit_levels['target_2'],
                status='OPEN'
            )
            
            self.session.add(trade)
            self.session.commit()
            
            self.log_execution(position['position_id'], 'ENTRY', 
                             position['contracts'], position['entry_price'],
                             {'signal': signal, 'contract': contract})
            
        except Exception as e:
            logger.error(f"Error logging trade entry: {e}")
            self.session.rollback()
    
    def log_trade_exit(self, position_id: str, exit_price: float, 
                      contracts: int, reason: str, pnl: float) -> None:
        """Log trade exit or partial exit"""
        try:
            trade = self.session.query(Trade).filter_by(position_id=position_id).first()
            
            if trade:
                if contracts == trade.contracts:
                    trade.exit_time = datetime.now()
                    trade.exit_price = exit_price
                    trade.exit_reason = reason
                    trade.status = 'CLOSED'
                
                trade.realized_pnl = pnl
                self.session.commit()
                
                self.log_execution(position_id, 'EXIT', contracts, exit_price,
                                 {'reason': reason, 'pnl': pnl})
            
        except Exception as e:
            logger.error(f"Error logging trade exit: {e}")
            self.session.rollback()
    
    def log_execution(self, position_id: str, action: str, contracts: int,
                     price: float, details: Dict) -> None:
        """Log execution details"""
        try:
            execution = ExecutionLog(
                position_id=position_id,
                timestamp=datetime.now(),
                action=action,
                contracts=contracts,
                price=price,
                details=details
            )
            
            self.session.add(execution)
            self.session.commit()
            
        except Exception as e:
            logger.error(f"Error logging execution: {e}")
            self.session.rollback()
    
    def log_risk_metrics(self, metrics: Dict) -> None:
        """Log current risk metrics"""
        try:
            risk_metric = RiskMetrics(
                timestamp=datetime.now(),
                current_equity=metrics['current_equity'],
                daily_pnl=metrics['daily_pnl'],
                daily_pnl_pct=metrics['daily_pnl_pct'],
                consecutive_losses=metrics['consecutive_losses'],
                active_positions=metrics['active_positions'],
                trades_today=metrics['trades_today'],
                trading_enabled=metrics['trading_enabled']
            )
            
            self.session.add(risk_metric)
            self.session.commit()
            
        except Exception as e:
            logger.error(f"Error logging risk metrics: {e}")
            self.session.rollback()
    
    def get_daily_trades(self, date: datetime) -> List[Dict]:
        """Get all trades for a specific date"""
        try:
            trades = self.session.query(Trade).filter(
                Trade.entry_time >= date.replace(hour=0, minute=0, second=0),
                Trade.entry_time < date.replace(hour=23, minute=59, second=59)
            ).all()
            
            return [self._trade_to_dict(trade) for trade in trades]
            
        except Exception as e:
            logger.error(f"Error getting daily trades: {e}")
            return []
    
    def get_expectancy_report(self, days: int = 30) -> Dict:
        """Generate expectancy report for recent trading"""
        try:
            cutoff_date = datetime.now() - timedelta(days=days)
            trades = self.session.query(Trade).filter(
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
    
    def close(self):
        """Close database connection"""
        self.session.close()