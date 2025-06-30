"""
Unified risk management system
Handles position sizing, risk limits, and portfolio protection
"""
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
import pytz

from .unified_logging import get_logger
from .unified_database import UnifiedDatabaseManager
from .error_reporter import ErrorReporter

@dataclass
class RiskMetrics:
    """Risk metrics for a trading session"""
    daily_pnl: float
    daily_trades: int
    consecutive_losses: int
    max_drawdown: float
    current_exposure: float
    win_rate: float
    average_win: float
    average_loss: float
    sharpe_ratio: float

class UnifiedRiskManager:
    """
    Centralized risk management for all trading strategies
    """
    
    def __init__(self, 
                 db_manager: UnifiedDatabaseManager,
                 broker=None,
                 max_daily_loss: float = -500.0,
                 max_position_size: float = 0.25,
                 max_portfolio_heat: float = 0.06):
        """
        Initialize risk manager
        
        Args:
            db_manager: Database manager
            broker: Broker instance for account data
            max_daily_loss: Maximum daily loss allowed
            max_position_size: Max position size as % of portfolio
            max_portfolio_heat: Max total risk as % of portfolio
        """
        self.db = db_manager
        self.broker = broker
        self.logger = get_logger(__name__)
        
        # Risk parameters
        self.max_daily_loss = max_daily_loss
        self.max_position_size = max_position_size
        self.max_portfolio_heat = max_portfolio_heat
        
        # Cached metrics
        self._metrics_cache = {}
        self._cache_expiry = {}
        self.cache_duration = 60  # seconds
        
        # Eastern timezone
        self.eastern = pytz.timezone('US/Eastern')
    
    async def check_trade_allowed(self, 
                                 bot_id: str,
                                 proposed_risk: float) -> Tuple[bool, Optional[str]]:
        """
        Check if a new trade is allowed based on risk rules
        
        Args:
            bot_id: Bot identifier
            proposed_risk: Risk amount for proposed trade
            
        Returns:
            (allowed, reason) - True if allowed, reason if not
        """
        try:
            # Get current metrics
            metrics = await self.get_risk_metrics(bot_id)
            
            # Check daily loss limit
            if metrics.daily_pnl <= self.max_daily_loss:
                return False, f"Daily loss limit reached: ${metrics.daily_pnl:.2f}"
            
            # Check if adding this trade would exceed daily loss limit
            if metrics.daily_pnl - proposed_risk < self.max_daily_loss:
                return False, f"Trade would exceed daily loss limit"
            
            # Check consecutive losses
            if metrics.consecutive_losses >= 3:
                return False, f"Too many consecutive losses: {metrics.consecutive_losses}"
            
            # Check portfolio heat
            account = await self.broker.get_account() if self.broker else None
            if account:
                portfolio_value = float(account.equity)
                total_heat = metrics.current_exposure + proposed_risk
                heat_percentage = total_heat / portfolio_value
                
                if heat_percentage > self.max_portfolio_heat:
                    return False, f"Portfolio heat too high: {heat_percentage:.1%}"
                
                # Check position size limit
                position_percentage = proposed_risk / portfolio_value
                if position_percentage > self.max_position_size:
                    return False, f"Position size too large: {position_percentage:.1%}"
            
            return True, None
            
        except Exception as e:
            self.logger.error(f"Risk check failed: {e}", exc_info=True)
            return False, "Risk check error"
    
    async def get_risk_metrics(self, bot_id: str) -> RiskMetrics:
        """Get current risk metrics for a bot"""
        # Check cache
        cache_key = f"{bot_id}_metrics"
        if cache_key in self._metrics_cache:
            if datetime.now() < self._cache_expiry.get(cache_key, datetime.min):
                return self._metrics_cache[cache_key]
        
        # Calculate fresh metrics
        metrics = await self._calculate_metrics(bot_id)
        
        # Cache results
        self._metrics_cache[cache_key] = metrics
        self._cache_expiry[cache_key] = datetime.now() + timedelta(seconds=self.cache_duration)
        
        return metrics
    
    async def _calculate_metrics(self, bot_id: str) -> RiskMetrics:
        """Calculate risk metrics from database"""
        try:
            # Get today's trades
            today_start = datetime.now(self.eastern).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            
            trades = self.db.get_trades(bot_id, limit=100)
            today_trades = [t for t in trades if t.entry_time >= today_start]
            
            # Calculate daily metrics
            daily_pnl = sum(t.pnl or 0 for t in today_trades if t.pnl is not None)
            daily_trades = len(today_trades)
            
            # Count consecutive losses
            consecutive_losses = 0
            for trade in reversed(today_trades):
                if trade.pnl and trade.pnl < 0:
                    consecutive_losses += 1
                elif trade.pnl and trade.pnl > 0:
                    break
            
            # Calculate win rate and averages
            completed_trades = [t for t in today_trades if t.pnl is not None]
            winning_trades = [t for t in completed_trades if t.pnl > 0]
            losing_trades = [t for t in completed_trades if t.pnl <= 0]
            
            win_rate = len(winning_trades) / len(completed_trades) if completed_trades else 0
            average_win = sum(t.pnl for t in winning_trades) / len(winning_trades) if winning_trades else 0
            average_loss = sum(t.pnl for t in losing_trades) / len(losing_trades) if losing_trades else 0
            
            # Calculate current exposure
            active_positions = self.db.get_active_positions(bot_id)
            current_exposure = sum(
                p.entry_price * p.quantity for p in active_positions
            )
            
            # Calculate max drawdown
            cumulative_pnl = 0
            peak_pnl = 0
            max_drawdown = 0
            
            for trade in sorted(completed_trades, key=lambda t: t.exit_time or t.entry_time):
                cumulative_pnl += trade.pnl or 0
                peak_pnl = max(peak_pnl, cumulative_pnl)
                drawdown = peak_pnl - cumulative_pnl
                max_drawdown = max(max_drawdown, drawdown)
            
            # Simple Sharpe ratio (daily)
            if completed_trades and len(completed_trades) > 1:
                returns = [t.pnl_percent or 0 for t in completed_trades]
                avg_return = sum(returns) / len(returns)
                
                if len(returns) > 1:
                    variance = sum((r - avg_return) ** 2 for r in returns) / (len(returns) - 1)
                    std_dev = variance ** 0.5
                    sharpe_ratio = (avg_return / std_dev) * (252 ** 0.5) if std_dev > 0 else 0
                else:
                    sharpe_ratio = 0
            else:
                sharpe_ratio = 0
            
            return RiskMetrics(
                daily_pnl=daily_pnl,
                daily_trades=daily_trades,
                consecutive_losses=consecutive_losses,
                max_drawdown=max_drawdown,
                current_exposure=current_exposure,
                win_rate=win_rate,
                average_win=average_win,
                average_loss=average_loss,
                sharpe_ratio=sharpe_ratio
            )
            
        except Exception as e:
            self.logger.error(f"Failed to calculate risk metrics: {e}", exc_info=True)
            # Return safe defaults
            return RiskMetrics(
                daily_pnl=0,
                daily_trades=0,
                consecutive_losses=0,
                max_drawdown=0,
                current_exposure=0,
                win_rate=0,
                average_win=0,
                average_loss=0,
                sharpe_ratio=0
            )
    
    def calculate_position_size(self,
                              account_value: float,
                              risk_percentage: float,
                              entry_price: float,
                              stop_price: float) -> int:
        """
        Calculate position size based on risk
        
        Args:
            account_value: Total account value
            risk_percentage: Risk per trade (e.g., 0.01 for 1%)
            entry_price: Entry price per share/contract
            stop_price: Stop loss price
            
        Returns:
            Number of shares/contracts
        """
        if stop_price == entry_price:
            return 0
        
        # Calculate risk per unit
        risk_per_unit = abs(entry_price - stop_price)
        
        # Calculate total risk amount
        risk_amount = account_value * risk_percentage
        
        # Calculate position size
        position_size = int(risk_amount / risk_per_unit)
        
        return max(1, position_size)  # Minimum 1 unit
    
    def calculate_kelly_criterion(self, 
                                win_rate: float,
                                avg_win: float,
                                avg_loss: float) -> float:
        """
        Calculate optimal position size using Kelly Criterion
        
        Returns:
            Optimal risk percentage (capped at reasonable levels)
        """
        if avg_loss == 0 or win_rate == 0:
            return 0.01  # Default 1%
        
        # Kelly formula: f = (p * b - q) / b
        # where p = win rate, q = loss rate, b = win/loss ratio
        win_loss_ratio = abs(avg_win / avg_loss)
        kelly_percentage = (win_rate * win_loss_ratio - (1 - win_rate)) / win_loss_ratio
        
        # Cap at 25% (Kelly can suggest very aggressive sizing)
        kelly_percentage = max(0, min(0.25, kelly_percentage))
        
        # Further reduce by factor for safety
        return kelly_percentage * 0.25  # Use 1/4 Kelly
    
    async def log_risk_event(self, 
                           bot_id: str,
                           event_type: str,
                           details: Dict[str, Any]):
        """Log risk management events"""
        self.db.log_risk_metric(
            metric_type=f"risk_event_{event_type}",
            value=1.0,
            metadata={
                'bot_id': bot_id,
                'event_type': event_type,
                'details': details,
                'timestamp': datetime.now().isoformat()
            }
        )
    
    def get_risk_report(self, bot_id: str) -> Dict[str, Any]:
        """Generate risk report for a bot"""
        try:
            metrics = asyncio.run(self.get_risk_metrics(bot_id))
            
            return {
                'bot_id': bot_id,
                'timestamp': datetime.now(self.eastern).isoformat(),
                'daily_metrics': {
                    'pnl': metrics.daily_pnl,
                    'trades': metrics.daily_trades,
                    'consecutive_losses': metrics.consecutive_losses,
                    'current_exposure': metrics.current_exposure
                },
                'performance_metrics': {
                    'win_rate': f"{metrics.win_rate:.1%}",
                    'average_win': metrics.average_win,
                    'average_loss': metrics.average_loss,
                    'max_drawdown': metrics.max_drawdown,
                    'sharpe_ratio': round(metrics.sharpe_ratio, 2)
                },
                'risk_status': {
                    'daily_loss_remaining': self.max_daily_loss - metrics.daily_pnl,
                    'can_trade': metrics.daily_pnl > self.max_daily_loss,
                    'risk_level': self._get_risk_level(metrics)
                }
            }
            
        except Exception as e:
            self.logger.error(f"Failed to generate risk report: {e}")
            return {
                'bot_id': bot_id,
                'error': str(e)
            }
    
    def _get_risk_level(self, metrics: RiskMetrics) -> str:
        """Determine current risk level"""
        if metrics.consecutive_losses >= 3:
            return "HIGH"
        elif metrics.daily_pnl < self.max_daily_loss * 0.5:
            return "MEDIUM"
        elif metrics.win_rate < 0.4:
            return "MEDIUM"
        else:
            return "LOW"