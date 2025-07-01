#!/usr/bin/env python3
"""
Quick database fix script - adds missing bot_id column
Run this to fix the database schema issue
"""
import os
import sys
from dotenv import load_dotenv

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Import and run migration
from migrate_database import migrate_database

if __name__ == '__main__':
    load_dotenv()
    print("Running database fix...")
    
    if migrate_database():
        print("\n✅ Database fixed successfully!")
        print("You can now run the trading bot.")
    else:
        print("\n❌ Failed to fix database")
        print("Please check the error messages above")