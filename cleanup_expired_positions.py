#!/usr/bin/env python3
"""
Clean up expired option positions from the database
"""
import sqlite3
from datetime import datetime
import re

def extract_expiry_from_symbol(symbol):
    """Extract expiry date from option symbol like SPY250804P00627000"""
    # Option symbol format: SPYYMMDDP/CXXXXX000
    match = re.match(r'([A-Z]+)(\d{6})[PC]\d+', symbol)
    if match:
        ticker = match.group(1)
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

def cleanup_expired_positions():
    """Remove expired positions from the database"""
    conn = sqlite3.connect('trading_multi.db')
    cursor = conn.cursor()
    
    # Get all open option positions
    cursor.execute("""
        SELECT id, bot_id, contract_symbol, contracts, entry_price, expiry 
        FROM option_trades 
        WHERE exit_time IS NULL
    """)
    
    positions = cursor.fetchall()
    today = datetime.now().date()
    expired_count = 0
    
    print(f"Checking {len(positions)} open option positions for expiry...")
    
    for pos_id, bot_id, contract_symbol, contracts, entry_price, expiry_str in positions:
        # Parse expiry from database
        try:
            if expiry_str:
                expiry_date = datetime.fromisoformat(expiry_str.replace('Z', '+00:00'))
            else:
                # Try to extract from symbol
                expiry_date = extract_expiry_from_symbol(contract_symbol)
        except:
            expiry_date = extract_expiry_from_symbol(contract_symbol)
        
        if expiry_date and expiry_date.date() < today:
            print(f"Closing expired position: {contract_symbol} (expired on {expiry_date.date()})")
            
            # Mark position as closed with 100% loss (options expired worthless)
            cursor.execute("""
                UPDATE option_trades 
                SET exit_time = datetime('now'),
                    exit_price = 0.01,
                    exit_reason = 'Expired worthless',
                    realized_pnl = -?,
                    status = 'closed'
                WHERE id = ?
            """, (contracts * entry_price * 100, pos_id))  # Options are 100 shares per contract
            
            expired_count += 1
    
    conn.commit()
    print(f"\nCleaned up {expired_count} expired positions")
    
    # Show remaining open positions
    cursor.execute("""
        SELECT bot_id, contract_symbol, contracts, entry_price 
        FROM option_trades 
        WHERE exit_time IS NULL
    """)
    
    remaining = cursor.fetchall()
    if remaining:
        print(f"\nRemaining open positions: {len(remaining)}")
        for bot_id, contract_symbol, contracts, entry_price in remaining:
            print(f"  {bot_id}: {contract_symbol} x{contracts} @ ${entry_price}")
    else:
        print("\nNo open positions remaining")
    
    conn.close()

if __name__ == "__main__":
    cleanup_expired_positions()