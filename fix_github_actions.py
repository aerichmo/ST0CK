#!/usr/bin/env python3
"""
Fix for GitHub Actions connection issues with Alpaca API
This script implements workarounds for network restrictions in GitHub Actions
"""
import os
import sys
import time
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

def setup_github_actions_environment():
    """Configure environment for GitHub Actions compatibility"""
    
    # 1. Set connection timeouts
    os.environ['HTTPX_TIMEOUT'] = '30'
    
    # 2. Disable SSL verification if needed (only for testing)
    # os.environ['CURL_CA_BUNDLE'] = ''
    
    # 3. Set user agent to identify as GitHub Actions
    os.environ['USER_AGENT'] = 'ST0CK-Bot/1.0 (GitHub Actions)'
    
    # 4. Check if running in GitHub Actions
    if os.getenv('GITHUB_ACTIONS') == 'true':
        print("Running in GitHub Actions environment")
        print(f"Runner OS: {os.getenv('RUNNER_OS')}")
        print(f"Runner Name: {os.getenv('RUNNER_NAME')}")
        
        # 5. Test network connectivity
        import subprocess
        test_hosts = [
            'google.com',
            'api.github.com', 
            'paper-api.alpaca.markets',
            'data.alpaca.markets'
        ]
        
        print("\nTesting network connectivity:")
        for host in test_hosts:
            try:
                result = subprocess.run(
                    ['ping', '-c', '1', '-W', '2', host],
                    capture_output=True,
                    text=True
                )
                if result.returncode == 0:
                    print(f"  ✓ {host} - reachable")
                else:
                    print(f"  ✗ {host} - unreachable")
            except Exception as e:
                print(f"  ? {host} - error: {e}")
        
        # 6. Check for proxy settings
        proxy_vars = ['HTTP_PROXY', 'HTTPS_PROXY', 'NO_PROXY']
        print("\nProxy settings:")
        for var in proxy_vars:
            value = os.getenv(var)
            if value:
                print(f"  {var}: {value}")
            else:
                print(f"  {var}: not set")
        
        # 7. Implement connection retry wrapper
        print("\nImplementing connection retry wrapper...")
        
        return True
    else:
        print("Not running in GitHub Actions")
        return False


def test_alpaca_with_retry():
    """Test Alpaca connection with GitHub Actions workarounds"""
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
    
    # Create session with retry strategy
    session = requests.Session()
    retry_strategy = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["HEAD", "GET", "OPTIONS", "POST"]
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    
    # Set headers
    headers = {
        'User-Agent': 'ST0CK-Bot/1.0 (GitHub Actions)',
        'Accept': 'application/json',
        'APCA-API-KEY-ID': os.getenv('ST0CKGKEY', ''),
        'APCA-API-SECRET-KEY': os.getenv('ST0CKGSECRET', '')
    }
    
    # Test endpoints
    endpoints = [
        ('Account', 'https://paper-api.alpaca.markets/v2/account'),
        ('Clock', 'https://paper-api.alpaca.markets/v2/clock'),
        ('Assets', 'https://paper-api.alpaca.markets/v2/assets/SPY')
    ]
    
    print("\nTesting Alpaca endpoints with retry logic:")
    for name, url in endpoints:
        try:
            response = session.get(url, headers=headers, timeout=30)
            print(f"  {name}: {response.status_code}")
            if response.status_code == 401:
                print("    Authentication failed - check API credentials")
            elif response.status_code == 200:
                print("    Success!")
        except Exception as e:
            print(f"  {name}: Failed - {e}")


if __name__ == "__main__":
    print(f"GitHub Actions Connection Fix - {datetime.now()}")
    print("=" * 60)
    
    # Setup environment
    is_github_actions = setup_github_actions_environment()
    
    # Test connection with workarounds
    if is_github_actions:
        print("\nApplying GitHub Actions workarounds...")
        time.sleep(2)  # Give network time to stabilize
        test_alpaca_with_retry()
    else:
        print("\nRunning standard connection test...")
        os.system("python test_connection.py")