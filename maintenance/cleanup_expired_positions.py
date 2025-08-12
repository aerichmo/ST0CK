#!/usr/bin/env python3
"""
Maintenance script to clean up expired option positions
Run this periodically to close any options that have expired
"""
import os
import sys
from datetime import datetime, timezone
import re

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.unified_database import UnifiedDatabaseManager
from src.unified_logging import configure_logging, get_logger

def cleanup_expired_positions():
    """Clean up any expired option positions"""
    configure_logging('INFO')
    logger = get_logger(__name__)
    
    db = UnifiedDatabaseManager()
    
    try:
        with db.get_session() as session:
            # Get all open option trades
            from src.unified_database import OptionTrade
            
            open_trades = session.query(OptionTrade).filter(
                OptionTrade.status == 'OPEN'
            ).all()
            
            logger.info(f"Found {len(open_trades)} open option positions")
            
            expired_count = 0
            today = datetime.now(timezone.utc).date()
            
            for trade in open_trades:
                # Check if position is expired
                if trade.expiry and trade.expiry.date() < today:
                    logger.info(f"Closing expired position: {trade.contract_symbol} "
                              f"(expired {trade.expiry.date()})")
                    
                    # Mark as closed
                    trade.status = 'CLOSED'
                    trade.exit_time = trade.expiry.replace(hour=16, minute=0)
                    trade.exit_price = 0.01
                    trade.exit_reason = 'expired'
                    trade.realized_pnl = -trade.entry_price * trade.contracts + 0.01 * trade.contracts
                    
                    expired_count += 1
            
            session.commit()
            logger.info(f"Closed {expired_count} expired positions")
            
            # Log remaining open positions
            remaining = session.query(OptionTrade).filter(
                OptionTrade.status == 'OPEN'
            ).count()
            
            logger.info(f"Remaining open positions: {remaining}")
            
    except Exception as e:
        logger.error(f"Error during cleanup: {e}", exc_info=True)
    finally:
        db.close()

if __name__ == "__main__":
    cleanup_expired_positions()