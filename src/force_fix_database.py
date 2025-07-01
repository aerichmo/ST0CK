#!/usr/bin/env python3
"""
Force fix database schema - guaranteed to work
This script will ensure all required columns exist
"""
import os
import sys
from sqlalchemy import create_engine, text, inspect
from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv()

def force_fix_database():
    """Force fix the database schema"""
    
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        print("ERROR: DATABASE_URL not set in environment")
        return False
    
    print(f"Connecting to database...")
    
    try:
        engine = create_engine(database_url)
        is_postgres = 'postgresql' in database_url
        
        with engine.connect() as conn:
            # First, check what columns exist
            print("\nChecking existing columns in trades table...")
            try:
                result = conn.execute(text("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = 'trades'
                """))
                existing_columns = [row[0] for row in result]
                print(f"Existing columns: {existing_columns}")
            except:
                # For SQLite
                result = conn.execute(text("PRAGMA table_info(trades)"))
                existing_columns = [row[1] for row in result]
                print(f"Existing columns: {existing_columns}")
            
            # Define all required columns with PostgreSQL-compatible defaults
            columns_to_add = []
            
            if 'bot_id' not in existing_columns:
                columns_to_add.append(("bot_id", "VARCHAR", "'legacy'"))
            if 'action' not in existing_columns:
                columns_to_add.append(("action", "VARCHAR", "'unknown'"))
            if 'quantity' not in existing_columns:
                columns_to_add.append(("quantity", "INTEGER", "0"))
            if 'pnl' not in existing_columns:
                columns_to_add.append(("pnl", "FLOAT", "NULL"))
            if 'pnl_percent' not in existing_columns:
                columns_to_add.append(("pnl_percent", "FLOAT", "NULL"))
            if 'strategy_details' not in existing_columns:
                if is_postgres:
                    columns_to_add.append(("strategy_details", "JSON", "NULL"))
                else:
                    columns_to_add.append(("strategy_details", "TEXT", "NULL"))
            
            # Add each missing column
            for col_name, col_type, default in columns_to_add:
                print(f"\nAdding column {col_name}...")
                try:
                    if default == "NULL":
                        sql = f"ALTER TABLE trades ADD COLUMN {col_name} {col_type}"
                    else:
                        sql = f"ALTER TABLE trades ADD COLUMN {col_name} {col_type} DEFAULT {default}"
                    
                    conn.execute(text(sql))
                    conn.commit()
                    print(f"✅ Added column {col_name}")
                except Exception as e:
                    if "already exists" in str(e).lower():
                        print(f"✅ Column {col_name} already exists")
                    else:
                        print(f"❌ Failed to add column {col_name}: {e}")
            
            # For action column, update NULL values to 'unknown'
            try:
                print("\nUpdating NULL action values...")
                conn.execute(text("UPDATE trades SET action = 'unknown' WHERE action IS NULL"))
                conn.commit()
                print("✅ Updated NULL action values")
            except:
                pass
            
            # For quantity column, update NULL values to 0
            try:
                print("Updating NULL quantity values...")
                conn.execute(text("UPDATE trades SET quantity = 0 WHERE quantity IS NULL"))
                conn.commit()
                print("✅ Updated NULL quantity values")
            except:
                pass
            
            # Create indexes if they don't exist
            print("\nCreating indexes...")
            try:
                conn.execute(text("CREATE INDEX IF NOT EXISTS idx_bot_entry_time ON trades(bot_id, entry_time)"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS idx_bot_symbol ON trades(bot_id, symbol)"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS idx_entry_time ON trades(entry_time)"))
                conn.commit()
                print("✅ Indexes created")
            except Exception as e:
                print(f"Index creation warning: {e}")
            
            # Final verification
            print("\nFinal verification...")
            try:
                # Test query that was failing
                result = conn.execute(text("""
                    SELECT id, bot_id, symbol, action, quantity, 
                           entry_price, exit_price, entry_time, exit_time,
                           pnl, pnl_percent, strategy_details
                    FROM trades 
                    WHERE bot_id = 'st0ckg' 
                    LIMIT 1
                """))
                print("✅ Test query successful!")
                return True
            except Exception as e:
                print(f"❌ Test query failed: {e}")
                return False
                
    except Exception as e:
        print(f"❌ Force fix failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    print("ST0CK Database Force Fix")
    print("=" * 50)
    
    success = force_fix_database()
    
    if success:
        print("\n✅ Database fixed successfully!")
        sys.exit(0)
    else:
        print("\n❌ Fix failed!")
        sys.exit(1)