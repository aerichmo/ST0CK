"""
Day Trade Tracker
Tracks day trades to help stay within PDT limits
"""
import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)

class DayTradeTracker:
    """Track day trades to avoid PDT violations"""
    
    def __init__(self, data_file: str = "day_trades.json"):
        self.data_file = data_file
        self.trades = self._load_trades()
        
    def _load_trades(self) -> List[Dict]:
        """Load trades from file"""
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, 'r') as f:
                    return json.load(f)
            except:
                return []
        return []
    
    def _save_trades(self):
        """Save trades to file"""
        with open(self.data_file, 'w') as f:
            json.dump(self.trades, f, indent=2, default=str)
    
    def add_trade(self, symbol: str, entry_time: datetime, exit_time: Optional[datetime] = None):
        """Add a trade"""
        trade = {
            "symbol": symbol,
            "entry_time": entry_time.isoformat(),
            "exit_time": exit_time.isoformat() if exit_time else None,
            "is_day_trade": False
        }
        
        # Check if it's a day trade
        if exit_time and entry_time.date() == exit_time.date():
            trade["is_day_trade"] = True
            
        self.trades.append(trade)
        self._save_trades()
        
        logger.info(f"Trade recorded: {symbol} - Day trade: {trade['is_day_trade']}")
    
    def get_day_trade_count(self, lookback_days: int = 5) -> int:
        """Get number of day trades in the last N days"""
        cutoff = datetime.now() - timedelta(days=lookback_days)
        
        day_trades = 0
        for trade in self.trades:
            if trade["is_day_trade"]:
                entry_time = datetime.fromisoformat(trade["entry_time"])
                if entry_time >= cutoff:
                    day_trades += 1
                    
        return day_trades
    
    def can_day_trade(self, max_day_trades: int = 3) -> bool:
        """Check if we can make another day trade"""
        current_count = self.get_day_trade_count()
        can_trade = current_count < max_day_trades
        
        logger.info(f"Day trades in last 5 days: {current_count}/{max_day_trades}")
        
        if not can_trade:
            logger.warning("Cannot day trade - PDT limit reached!")
            
        return can_trade
    
    def get_next_available_date(self) -> datetime:
        """Get the date when a day trade slot becomes available"""
        if self.can_day_trade():
            return datetime.now()
            
        # Find the oldest day trade
        day_trades = [
            (datetime.fromisoformat(t["entry_time"]), t) 
            for t in self.trades 
            if t["is_day_trade"]
        ]
        
        if day_trades:
            day_trades.sort(key=lambda x: x[0])
            oldest_trade_date = day_trades[0][0]
            available_date = oldest_trade_date + timedelta(days=5)
            return available_date
            
        return datetime.now()