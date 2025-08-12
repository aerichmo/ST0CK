#!/usr/bin/env python3
"""Quick fix for GitHub Actions expired positions"""
import sqlite3
import os

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
    cursor.execute("SELECT contract_symbol, bot_id, status FROM option_trades WHERE status = 'OPEN'")
    open_positions = cursor.fetchall()
    print(f"Current open positions: {open_positions}")
    
    # Close the specific expired positions
    cursor.execute("""
        UPDATE option_trades 
        SET status = 'CLOSED',
            exit_time = '2025-08-04 16:00:00',
            exit_price = 0.01,
            exit_reason = 'expired',
            realized_pnl = CASE 
                WHEN contracts = 1 AND entry_price = 0.84 THEN -0.83
                WHEN contracts = 1 AND entry_price = 1.29 THEN -1.28
                ELSE -entry_price * contracts + 0.01 * contracts
            END
        WHERE bot_id = 'st0ckg' 
        AND status = 'OPEN'
        AND contract_symbol IN ('SPY250804P00627000', 'SPY250804P00629000')
    """)
    
    rows_updated = cursor.rowcount
    conn.commit()
    
    print(f"Closed {rows_updated} expired positions")
    
    # Show current open positions after cleanup
    cursor.execute("SELECT COUNT(*) FROM option_trades WHERE status = 'OPEN'")
    open_count = cursor.fetchone()[0]
    print(f"Remaining open positions: {open_count}")
    
    # Show which positions remain open
    if open_count > 0:
        cursor.execute("SELECT contract_symbol, bot_id, entry_time FROM option_trades WHERE status = 'OPEN'")
        remaining = cursor.fetchall()
        print(f"Remaining positions: {remaining}")
    
    conn.close()
else:
    print(f"Database not found at {db_path}")
    print(f"Current directory: {os.getcwd()}")
    print(f"Directory contents: {os.listdir('.')}")