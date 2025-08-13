#!/usr/bin/env python3
"""Test Alpaca API connectivity"""
import os
import sys
import socket
import requests
from datetime import datetime

def test_connection():
    print(f"\n{'='*60}")
    print(f"Alpaca API Connection Test - {datetime.now()}")
    print(f"{'='*60}\n")
    
    # Check environment variables
    api_key = os.getenv('ST0CKGKEY', '')
    api_secret = os.getenv('ST0CKGSECRET', '')
    base_url = os.getenv('ALPACA_BASE_URL', 'https://paper-api.alpaca.markets')
    
    print("1. Environment Variables:")
    print(f"   API Key: {'Set' if api_key else 'NOT SET'}")
    print(f"   API Secret: {'Set' if api_secret else 'NOT SET'}")
    print(f"   Base URL: {base_url}\n")
    
    # Test DNS resolution
    print("2. DNS Resolution:")
    hosts = ['paper-api.alpaca.markets', 'data.alpaca.markets']
    for host in hosts:
        try:
            ip = socket.gethostbyname(host)
            print(f"   ✓ {host} -> {ip}")
        except Exception as e:
            print(f"   ✗ {host} -> Failed: {e}")
    
    # Test HTTPS connectivity
    print("\n3. HTTPS Connectivity:")
    test_urls = [
        ('Account API', f"{base_url}/v2/account"),
        ('Data API', "https://data.alpaca.markets/v2/stocks/bars/latest?symbols=SPY&feed=iex")
    ]
    
    headers = {
        'APCA-API-KEY-ID': api_key,
        'APCA-API-SECRET-KEY': api_secret
    }
    
    for name, url in test_urls:
        try:
            print(f"\n   Testing {name}...")
            print(f"   URL: {url}")
            response = requests.get(url, headers=headers, timeout=10)
            print(f"   ✓ Status: {response.status_code}")
            if response.status_code == 401:
                print("   ! Authentication failed - check API credentials")
            elif response.status_code == 200:
                print("   ✓ Connection successful!")
        except requests.exceptions.Timeout:
            print(f"   ✗ Connection timeout after 10 seconds")
        except requests.exceptions.ConnectionError as e:
            print(f"   ✗ Connection error: {e}")
        except Exception as e:
            print(f"   ✗ Unexpected error: {e}")
    
    # Test with curl command
    print("\n4. System curl test:")
    import subprocess
    try:
        result = subprocess.run(['curl', '-I', 'https://paper-api.alpaca.markets'], 
                              capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            print("   ✓ curl command successful")
            print(f"   Headers: {result.stdout.split('\\n')[0]}")
        else:
            print(f"   ✗ curl failed: {result.stderr}")
    except Exception as e:
        print(f"   ✗ curl test failed: {e}")
    
    print(f"\n{'='*60}\n")

if __name__ == "__main__":
    test_connection()