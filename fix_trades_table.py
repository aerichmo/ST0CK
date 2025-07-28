#!/usr/bin/env python3
"""
Fix trades table schema by removing position_id column
"""
import os
from sqlalchemy import create_engine, text

def fix_trades_table():
    # Get database URL from environment
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        print("DATABASE_URL not set")
        return
    
    # Create engine
    engine = create_engine(database_url)
    
    try:
        with engine.connect() as conn:
            # Check if position_id column exists
            result = conn.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'trades' 
                AND column_name = 'position_id'
            """))
            
            if result.fetchone():
                print("Found position_id column in trades table")
                
                # Drop the position_id column
                conn.execute(text("ALTER TABLE trades DROP COLUMN IF EXISTS position_id"))
                conn.commit()
                print("Removed position_id column from trades table")
            else:
                print("position_id column not found in trades table")
                
    except Exception as e:
        print(f"Error fixing trades table: {e}")
    finally:
        engine.dispose()

if __name__ == "__main__":
    fix_trades_table()