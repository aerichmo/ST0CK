#!/usr/bin/env python3
"""Force cleanup all expired positions based on date pattern"""
import sqlite3
import os
from datetime import datetime

# Use environment variable or default
db_url = os.environ.get('DATABASE_URL', 'sqlite:///trading_multi.db')
# Extract path from URL
if db_url.startswith('sqlite:///'):
    db_path = db_url.replace('sqlite:///', '')
else:
    db_path = 'trading_multi.db'

print(f"Database URL: {db_url}")
print(f"Database path: {db_path}")

if os.path.exists(db_path):
    print(f"Database found at {db_path}")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # First check what's in the database
    cursor.execute("SELECT contract_symbol, bot_id, status, entry_time FROM option_trades WHERE status = 'OPEN'")
    open_positions = cursor.fetchall()
    print(f"Current open positions: {len(open_positions)}")
    for pos in open_positions:
        print(f"  - {pos[0]} (bot: {pos[1]}, entered: {pos[3]})")
    
    # Close any positions with August 4th expiration (250804)
    cursor.execute("""
        UPDATE option_trades 
        SET status = 'CLOSED',
            exit_time = '2025-08-04 16:00:00',
            exit_price = 0.01,
            exit_reason = 'expired_cleanup',
            realized_pnl = -entry_price * contracts + 0.01 * contracts
        WHERE status = 'OPEN'
        AND contract_symbol LIKE '%250804%'
    """)
    
    aug4_closed = cursor.rowcount
    
    # Also close any positions from July or earlier
    cursor.execute("""
        UPDATE option_trades 
        SET status = 'CLOSED',
            exit_time = datetime('now'),
            exit_price = 0.01,
            exit_reason = 'expired_cleanup',
            realized_pnl = -entry_price * contracts + 0.01 * contracts
        WHERE status = 'OPEN'
        AND entry_time < '2025-08-01'
    """)
    
    old_closed = cursor.rowcount
    
    conn.commit()
    
    print(f"\nClosed {aug4_closed} August 4th positions")
    print(f"Closed {old_closed} old positions from before August")
    
    # Show current open positions after cleanup
    cursor.execute("SELECT COUNT(*) FROM option_trades WHERE status = 'OPEN'")
    open_count = cursor.fetchone()[0]
    print(f"\nRemaining open positions: {open_count}")
    
    # Show which positions remain open
    if open_count > 0:
        cursor.execute("SELECT contract_symbol, bot_id, entry_time FROM option_trades WHERE status = 'OPEN'")
        remaining = cursor.fetchall()
        print("Remaining positions:")
        for pos in remaining:
            print(f"  - {pos[0]} (bot: {pos[1]}, entered: {pos[2]})")
    
    conn.close()
    print("\nCleanup complete!")
else:
    print(f"Database not found at {db_path}")
    print(f"Current directory: {os.getcwd()}")
    print(f"Directory contents: {os.listdir('.')}")