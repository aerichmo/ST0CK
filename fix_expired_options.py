#!/usr/bin/env python3
"""
Fix expired option positions in the database
"""
import sqlite3
from datetime import datetime
import re

def extract_expiry_from_symbol(symbol):
    """Extract expiry date from option symbol like SPY250804P00627000"""
    # Option symbol format: SPYYMMDDP/CXXXXX000
    match = re.match(r'([A-Z]+)(\d{6})[PC]\d+', symbol)
    if match:
        date_str = match.group(2)
        # Convert YYMMDD to date
        year = 2000 + int(date_str[:2])
        month = int(date_str[2:4])
        day = int(date_str[4:6])
        try:
            return datetime(year, month, day)
        except ValueError:
            return None
    return None

def fix_expired_options():
    """Update status of expired options to closed"""
    conn = sqlite3.connect('trading_multi.db')
    cursor = conn.cursor()
    
    # First, let's see what's in the option_trades table
    print("Checking option_trades table...")
    cursor.execute("""
        SELECT id, bot_id, contract_symbol, contracts, entry_price, status, exit_time
        FROM option_trades 
        WHERE bot_id = 'st0ckg'
        ORDER BY id DESC
        LIMIT 20
    """)
    
    all_trades = cursor.fetchall()
    print(f"\nFound {len(all_trades)} ST0CKG option trades:")
    for trade in all_trades:
        print(f"  ID: {trade[0]}, Symbol: {trade[2]}, Status: {trade[5]}, Exit: {trade[6]}")
    
    # Now fix any that are still marked as OPEN but have expired symbols
    today = datetime.now().date()
    
    cursor.execute("""
        SELECT id, contract_symbol, contracts, entry_price
        FROM option_trades 
        WHERE bot_id = 'st0ckg' 
        AND (status = 'OPEN' OR status IS NULL)
        AND exit_time IS NULL
    """)
    
    open_trades = cursor.fetchall()
    expired_count = 0
    
    print(f"\n\\nFound {len(open_trades)} open ST0CKG positions")
    
    for trade_id, symbol, contracts, entry_price in open_trades:
        expiry = extract_expiry_from_symbol(symbol)
        
        if expiry and expiry.date() < today:
            print(f"\\nClosing expired option: {symbol}")
            print(f"  Expired on: {expiry.date()}")
            print(f"  Contracts: {contracts}, Entry price: ${entry_price}")
            
            # Close the position
            cursor.execute("""
                UPDATE option_trades 
                SET status = 'CLOSED',
                    exit_time = ?,
                    exit_price = 0.01,
                    exit_reason = 'Expired worthless - cleanup',
                    realized_pnl = ?
                WHERE id = ?
            """, (expiry.isoformat(), -(contracts * entry_price * 100), trade_id))
            
            expired_count += 1
    
    if expired_count > 0:
        conn.commit()
        print(f"\\n✓ Closed {expired_count} expired positions")
    else:
        print("\\n✓ No expired positions to close")
    
    # Show current open positions
    cursor.execute("""
        SELECT contract_symbol, contracts, entry_price, entry_time
        FROM option_trades 
        WHERE bot_id = 'st0ckg' 
        AND (status = 'OPEN' OR status IS NULL)
        AND exit_time IS NULL
    """)
    
    remaining = cursor.fetchall()
    if remaining:
        print(f"\\nRemaining open positions: {len(remaining)}")
        for symbol, contracts, price, entry_time in remaining:
            print(f"  {symbol} x{contracts} @ ${price} (entered {entry_time})")
    else:
        print("\\nNo open positions remaining")
    
    conn.close()

if __name__ == "__main__":
    fix_expired_options()