#!/usr/bin/env python3
"""
Database migration script to add missing bot_id column to trades table
"""
import os
import sys
from sqlalchemy import create_engine, text, Column, String, inspect
from sqlalchemy.exc import OperationalError, ProgrammingError
from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv()

def migrate_database():
    """Add bot_id column to trades table if it doesn't exist"""
    
    # Get database URL from environment
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        print("ERROR: DATABASE_URL not set in environment")
        return False
    
    print(f"Connecting to database...")
    
    try:
        # Create engine
        engine = create_engine(database_url)
        
        # Check if trades table exists
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        
        if 'trades' not in tables:
            print("Trades table doesn't exist. Creating all tables...")
            from src.unified_database import Base
            Base.metadata.create_all(engine)
            print("✅ All tables created successfully")
            return True
        
        # Check if bot_id column exists
        columns = [col['name'] for col in inspector.get_columns('trades')]
        
        if 'bot_id' in columns:
            print("✅ bot_id column already exists in trades table")
            return True
        
        print("Adding bot_id column to trades table...")
        
        # Add bot_id column
        with engine.connect() as conn:
            # PostgreSQL syntax
            if 'postgresql' in database_url:
                conn.execute(text("""
                    ALTER TABLE trades 
                    ADD COLUMN bot_id VARCHAR NOT NULL DEFAULT 'legacy'
                """))
                conn.commit()
                
                # Create indexes
                print("Creating indexes...")
                conn.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_bot_entry_time 
                    ON trades(bot_id, entry_time)
                """))
                conn.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_bot_symbol 
                    ON trades(bot_id, symbol)
                """))
                conn.commit()
                
            # SQLite syntax  
            else:
                conn.execute(text("""
                    ALTER TABLE trades 
                    ADD COLUMN bot_id TEXT NOT NULL DEFAULT 'legacy'
                """))
                conn.commit()
                
                # Create indexes
                print("Creating indexes...")
                conn.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_bot_entry_time 
                    ON trades(bot_id, entry_time)
                """))
                conn.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_bot_symbol 
                    ON trades(bot_id, symbol)
                """))
                conn.commit()
        
        print("✅ bot_id column added successfully")
        
        # Add any other missing columns
        print("\nChecking for other missing columns...")
        inspector = inspect(engine)
        columns = inspector.get_columns('trades')
        column_names = [col['name'] for col in columns]
        
        # Define all required columns with their types
        required_columns = {
            'action': 'VARCHAR' if 'postgresql' in database_url else 'TEXT',
            'quantity': 'INTEGER',
            'pnl': 'FLOAT',
            'pnl_percent': 'FLOAT',
            'strategy_details': 'JSON' if 'postgresql' in database_url else 'TEXT'
        }
        
        # Add missing columns
        with engine.connect() as conn:
            for col_name, col_type in required_columns.items():
                if col_name not in column_names:
                    print(f"Adding column {col_name}...")
                    try:
                        if 'postgresql' in database_url:
                            default_value = 'NULL'
                            if col_name == 'action':
                                default_value = "'unknown'"
                            elif col_name == 'quantity':
                                default_value = '0'
                            
                            conn.execute(text(f"""
                                ALTER TABLE trades 
                                ADD COLUMN {col_name} {col_type} DEFAULT {default_value}
                            """))
                        else:
                            # SQLite
                            default_value = 'NULL'
                            if col_name == 'action':
                                default_value = "'unknown'"
                            elif col_name == 'quantity':
                                default_value = '0'
                                
                            conn.execute(text(f"""
                                ALTER TABLE trades 
                                ADD COLUMN {col_name} {col_type} DEFAULT {default_value}
                            """))
                        conn.commit()
                        print(f"✅ Added column {col_name}")
                    except Exception as e:
                        print(f"❌ Failed to add column {col_name}: {e}")
        
        # Final verification
        print("\nFinal verification...")
        inspector = inspect(engine)
        columns = inspector.get_columns('trades')
        column_names = [col['name'] for col in columns]
        
        all_required = ['id', 'bot_id', 'symbol', 'action', 'quantity', 
                       'entry_price', 'exit_price', 'entry_time', 'exit_time',
                       'pnl', 'pnl_percent', 'strategy_details']
        
        missing = [col for col in all_required if col not in column_names]
        
        if missing:
            print(f"❌ Still missing columns: {missing}")
            return False
        else:
            print("✅ All required columns present")
        
        return True
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    print("ST0CK Database Migration")
    print("=" * 50)
    
    success = migrate_database()
    
    if success:
        print("\n✅ Migration completed successfully!")
    else:
        print("\n❌ Migration failed!")
        sys.exit(1)