#!/usr/bin/env python3
"""
Migration script to unified ST0CK architecture
Safely migrates from old to new architecture
"""
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

def create_backup():
    """Create backup of current codebase"""
    backup_dir = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    print(f"Creating backup in {backup_dir}/")
    
    # Files to backup
    files_to_backup = [
        "src/logging_config.py",
        "src/performance_config.py",
        "src/database.py",
        "src/multi_bot_database.py",
        "src/base_engine.py",
        "src/risk_manager.py",
        "src/trend_filter.py",
        "main_multi.py",
    ]
    
    os.makedirs(backup_dir, exist_ok=True)
    
    for file_path in files_to_backup:
        if os.path.exists(file_path):
            dest = os.path.join(backup_dir, file_path)
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            shutil.copy2(file_path, dest)
            print(f"  Backed up: {file_path}")
    
    return backup_dir

def update_imports():
    """Update import statements in Python files"""
    replacements = [
        ("from src.logging_config import", "from src.unified_logging import"),
        ("from src.performance_config import", "from src.unified_logging import"),
        ("from src.database import", "from src.unified_database import"),
        ("from src.multi_bot_database import", "from src.unified_database import"),
        ("from src.base_engine import", "from src.unified_engine import"),
        ("from src.risk_manager import", "from src.unified_risk_manager import"),
        ("from src.trend_filter import", "from src.trend_filter_native import"),
        ("from .logging_config import", "from .unified_logging import"),
        ("from .performance_config import", "from .unified_logging import"),
        ("from .database import", "from .unified_database import"),
        ("from .multi_bot_database import", "from .unified_database import"),
        ("from .base_engine import", "from .unified_engine import"),
        ("from .risk_manager import", "from .unified_risk_manager import"),
        ("from .trend_filter import", "from .trend_filter_native import"),
    ]
    
    # Find all Python files
    python_files = []
    for root, dirs, files in os.walk("src"):
        for file in files:
            if file.endswith(".py"):
                python_files.append(os.path.join(root, file))
    
    for root, dirs, files in os.walk("bots"):
        for file in files:
            if file.endswith(".py"):
                python_files.append(os.path.join(root, file))
    
    # Update imports
    for file_path in python_files:
        try:
            with open(file_path, 'r') as f:
                content = f.read()
            
            original_content = content
            for old_import, new_import in replacements:
                content = content.replace(old_import, new_import)
            
            if content != original_content:
                with open(file_path, 'w') as f:
                    f.write(content)
                print(f"  Updated imports in: {file_path}")
                
        except Exception as e:
            print(f"  Error updating {file_path}: {e}")

def move_deprecated_files():
    """Move deprecated files to a deprecated folder"""
    deprecated_dir = "deprecated"
    os.makedirs(deprecated_dir, exist_ok=True)
    
    files_to_deprecate = [
        "src/logging_config.py",
        "src/performance_config.py",
        "src/database.py",
        "src/multi_bot_database.py",
        "src/base_engine.py",
        "src/base_fast_engine.py",
        "src/unified_simple_engine.py",
        "src/trend_filter.py",
        "src/trend_filter_optimized.py",
    ]
    
    for file_path in files_to_deprecate:
        if os.path.exists(file_path):
            dest = os.path.join(deprecated_dir, file_path)
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            shutil.move(file_path, dest)
            print(f"  Moved to deprecated: {file_path}")

def update_environment():
    """Update environment variables"""
    env_file = ".env"
    env_additions = [
        "# Redis configuration",
        "REDIS_URL=redis://localhost:6379",
        "",
        "# Sentry configuration (optional)",
        "# SENTRY_DSN=your_sentry_dsn_here",
        "",
    ]
    
    if os.path.exists(env_file):
        with open(env_file, 'r') as f:
            content = f.read()
        
        if "REDIS_URL" not in content:
            with open(env_file, 'a') as f:
                f.write("\n" + "\n".join(env_additions))
            print("  Added Redis and Sentry configuration to .env")
    else:
        print("  Warning: .env file not found")

def create_redis_config():
    """Create Redis configuration file"""
    redis_config = """# Redis Configuration for ST0CK

# Local Development
# docker run -d -p 6379:6379 redis:alpine

# Production (using Redis Cloud or AWS ElastiCache)
# Update REDIS_URL in .env with your production URL

# Redis key patterns:
# - Quotes: quote:{symbol}
# - Options: option:chain:{symbol}:{expiration}:{type}
# - Bars: bars:{symbol}:{timeframe}
# - Database cache: db:*

# TTL values (seconds):
# - Quotes: 5
# - Options: 60
# - Bars: 300
# - Database queries: 60
"""
    
    with open("redis_config.md", 'w') as f:
        f.write(redis_config)
    print("  Created redis_config.md")

def update_deployment_scripts():
    """Update deployment scripts"""
    # Update deploy.sh if it exists
    if os.path.exists("deploy.sh"):
        with open("deploy.sh", 'r') as f:
            content = f.read()
        
        content = content.replace("main_multi.py", "main_unified.py")
        
        with open("deploy.sh", 'w') as f:
            f.write(content)
        print("  Updated deploy.sh")
    
    # Update GitHub Actions
    workflow_path = ".github/workflows"
    if os.path.exists(workflow_path):
        for file in os.listdir(workflow_path):
            if file.endswith(".yml") or file.endswith(".yaml"):
                file_path = os.path.join(workflow_path, file)
                with open(file_path, 'r') as f:
                    content = f.read()
                
                original_content = content
                content = content.replace("main_multi.py", "main_unified.py")
                
                if content != original_content:
                    with open(file_path, 'w') as f:
                        f.write(content)
                    print(f"  Updated {file_path}")

def main():
    """Run migration"""
    print("ST0CK Migration to Unified Architecture")
    print("=" * 50)
    
    # Check if we're in the right directory
    if not os.path.exists("src") or not os.path.exists("requirements.txt"):
        print("Error: Must run from ST0CK root directory")
        sys.exit(1)
    
    # Step 1: Create backup
    print("\n1. Creating backup...")
    backup_dir = create_backup()
    print(f"   Backup created in: {backup_dir}/")
    
    # Step 2: Update imports
    print("\n2. Updating imports...")
    update_imports()
    
    # Step 3: Update environment
    print("\n3. Updating environment...")
    update_environment()
    
    # Step 4: Create Redis config
    print("\n4. Creating Redis configuration...")
    create_redis_config()
    
    # Step 5: Update deployment scripts
    print("\n5. Updating deployment scripts...")
    update_deployment_scripts()
    
    # Step 6: Move deprecated files
    print("\n6. Moving deprecated files...")
    response = input("   Move deprecated files to 'deprecated/' folder? (y/n): ")
    if response.lower() == 'y':
        move_deprecated_files()
    else:
        print("   Skipped moving deprecated files")
    
    print("\n" + "=" * 50)
    print("Migration complete!")
    print("\nNext steps:")
    print("1. Install Redis: docker run -d -p 6379:6379 redis:alpine")
    print("2. Update requirements: pip install -r requirements.txt")
    print("3. Test with: python main_unified.py --list")
    print("4. Run paper trading tests before production")
    print(f"\nBackup saved in: {backup_dir}/")
    print("If issues arise, restore from backup")

if __name__ == "__main__":
    main()