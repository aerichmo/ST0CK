#!/usr/bin/env python3
"""
Recreate database tables with correct schema
Use this if migration fails or tables are corrupted
"""
import os
import sys
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv()

def recreate_tables():
    """Recreate all tables with correct schema"""
    
    # Get database URL from environment
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        print("ERROR: DATABASE_URL not set in environment")
        return False
    
    print(f"Connecting to database...")
    
    try:
        # Create engine
        engine = create_engine(database_url)
        
        # Backup existing data
        print("\nBacking up existing data...")
        with engine.connect() as conn:
            try:
                # Check if trades table exists and has data
                result = conn.execute(text("SELECT COUNT(*) FROM trades"))
                count = result.scalar()
                if count > 0:
                    print(f"Found {count} existing trades")
                    print("Creating backup...")
                    conn.execute(text("ALTER TABLE trades RENAME TO trades_backup"))
                    conn.commit()
                    print("✅ Backup created as 'trades_backup'")
            except:
                print("No existing trades table to backup")
        
        # Import models and create all tables
        print("\nCreating tables with correct schema...")
        from src.unified_database import Base
        
        # Drop existing tables (except backups)
        print("Dropping old tables...")
        Base.metadata.drop_all(engine)
        
        # Create all tables fresh
        print("Creating new tables...")
        Base.metadata.create_all(engine)
        
        print("✅ All tables created successfully")
        
        # Verify table structure
        from sqlalchemy import inspect
        inspector = inspect(engine)
        
        print("\nVerifying trades table structure:")
        columns = inspector.get_columns('trades')
        for col in columns:
            print(f"  - {col['name']}: {col['type']}")
        
        # Try to restore data from backup if it exists
        try:
            with engine.connect() as conn:
                result = conn.execute(text("SELECT 1 FROM trades_backup LIMIT 1"))
                if result.fetchone():
                    print("\nRestoring data from backup...")
                    # Get common columns
                    backup_cols = [col['name'] for col in inspector.get_columns('trades_backup')]
                    new_cols = [col['name'] for col in inspector.get_columns('trades')]
                    common_cols = [col for col in backup_cols if col in new_cols]
                    
                    if common_cols:
                        cols_str = ', '.join(common_cols)
                        conn.execute(text(f"""
                            INSERT INTO trades ({cols_str})
                            SELECT {cols_str} FROM trades_backup
                        """))
                        conn.commit()
                        print("✅ Data restored successfully")
                    
                    # Drop backup table
                    conn.execute(text("DROP TABLE trades_backup"))
                    conn.commit()
        except:
            pass  # No backup to restore
        
        return True
        
    except Exception as e:
        print(f"❌ Recreation failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    print("ST0CK Database Recreation")
    print("=" * 50)
    print("WARNING: This will recreate all tables!")
    print("Existing data will be backed up if possible.")
    print()
    
    response = input("Continue? (yes/no): ")
    if response.lower() != 'yes':
        print("Cancelled.")
        sys.exit(0)
    
    success = recreate_tables()
    
    if success:
        print("\n✅ Database recreated successfully!")
    else:
        print("\n❌ Recreation failed!")
        sys.exit(1)