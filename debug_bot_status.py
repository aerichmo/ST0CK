#!/usr/bin/env python3
"""
Debug script to check what the bot is doing
"""
import os
import sys
from datetime import datetime
import pytz

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

def check_bot_status():
    """Check current bot status from database"""
    
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        print("DATABASE_URL not set")
        return
    
    eastern = pytz.timezone('US/Eastern')
    now = datetime.now(eastern)
    
    print(f"Current time (ET): {now.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Market hours: 9:30 AM - 4:00 PM ET")
    print(f"ST0CKG windows: 9:40-10:30, 1:00-2:30, 3:00-3:45")
    print("-" * 50)
    
    try:
        engine = create_engine(database_url)
        
        with engine.connect() as conn:
            # Check today's trades
            result = conn.execute(text("""
                SELECT COUNT(*) as count, 
                       COALESCE(SUM(pnl), 0) as total_pnl
                FROM trades 
                WHERE bot_id = 'st0ckg' 
                AND DATE(entry_time) = CURRENT_DATE
            """))
            trades = result.fetchone()
            print(f"Today's trades: {trades[0]}")
            print(f"Today's P&L: ${trades[1]:.2f}")
            
            # Check recent execution logs
            print("\nRecent activity:")
            result = conn.execute(text("""
                SELECT timestamp, action, details
                FROM execution_logs
                WHERE bot_id = 'st0ckg'
                ORDER BY timestamp DESC
                LIMIT 5
            """))
            
            logs = result.fetchall()
            if logs:
                for log in logs:
                    print(f"{log[0]}: {log[1]} - {log[2]}")
            else:
                print("No recent execution logs")
            
            # Check battle lines
            result = conn.execute(text("""
                SELECT date, pdh, pdl, 
                       premarket_high, premarket_low,
                       updated_at
                FROM battle_lines
                WHERE bot_id = 'st0ckg'
                AND date = CURRENT_DATE
                ORDER BY updated_at DESC
                LIMIT 1
            """))
            
            bl = result.fetchone()
            if bl:
                print(f"\nBattle Lines for {bl[0]}:")
                print(f"  PDH: ${bl[1]:.2f}, PDL: ${bl[2]:.2f}")
                print(f"  PM High: ${bl[3]:.2f}, PM Low: ${bl[4]:.2f}")
                print(f"  Updated: {bl[5]}")
            else:
                print("\nNo battle lines found for today")
                
    except Exception as e:
        print(f"Error checking status: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    check_bot_status()