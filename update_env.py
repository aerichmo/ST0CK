#!/usr/bin/env python3
"""
Quick script to update .env file with new variable names
"""
import os
from pathlib import Path

def update_env():
    """Update .env file to use new variable names"""
    env_path = Path(".env")
    
    if not env_path.exists():
        print("❌ No .env file found!")
        print("Run setup_secrets.py to create one.")
        return
    
    # Read current .env
    with open(env_path, 'r') as f:
        content = f.read()
    
    # Update variable names
    replacements = [
        # ST0CKA - handle both cases
        ('st0ckakey=', 'ST0CKAKEY='),
        ('st0ckasecret=', 'ST0CKASECRET='),
        ('STOCKA_KEY=', 'ST0CKAKEY='),
        ('ST0CKA_SECRET=', 'ST0CKASECRET='),
        
        # ST0CKG
        ('STOCKG_KEY=', 'ST0CKGKEY='),
        ('ST0CKG_SECRET=', 'ST0CKGSECRET='),
        
        # Remove old APCA variables if they exist
        ('APCA_API_KEY_ID=', '# APCA_API_KEY_ID='),
        ('APCA_API_SECRET_KEY=', '# APCA_API_SECRET_KEY='),
    ]
    
    updated_content = content
    for old, new in replacements:
        updated_content = updated_content.replace(old, new)
    
    # Write updated content
    with open(env_path, 'w') as f:
        f.write(updated_content)
    
    print("✅ Updated .env file with new variable names!")
    print("\nCurrent variables:")
    print("-" * 40)
    
    # Show current values (masked)
    from dotenv import load_dotenv
    load_dotenv(override=True)
    
    vars_to_show = ['ST0CKAKEY', 'ST0CKASECRET', 'ST0CKGKEY', 'ST0CKGSECRET']
    for var in vars_to_show:
        value = os.getenv(var)
        if value:
            masked = value[:4] + '*' * (len(value) - 8) + value[-4:] if len(value) > 8 else '*' * len(value)
            print(f"{var}: {masked}")
        else:
            print(f"{var}: Not set")

if __name__ == "__main__":
    update_env()