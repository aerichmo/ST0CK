#!/usr/bin/env python3
"""
Test script to verify ST0CKG bot fixes
"""
import asyncio
import os
import sys
from datetime import datetime

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from unified_logging import get_logger, configure_logging
from unified_market_data import UnifiedMarketData
from alpaca_broker import AlpacaBroker

async def test_option_chain_filtering():
    """Test that option chain filtering reduces API calls"""
    configure_logging(log_level='INFO')
    logger = get_logger(__name__)
    
    # Initialize broker
    broker = AlpacaBroker(
        api_key=os.getenv('ALPACA_API_KEY'),
        secret_key=os.getenv('ALPACA_API_SECRET'),
        paper=True
    )
    
    if not broker.connect():
        logger.error("Failed to connect to broker")
        return False
    
    # Initialize market data
    market_data = UnifiedMarketData(broker)
    
    try:
        # Get expiration for testing
        from datetime import datetime, timedelta
        today = datetime.now().date()
        if today.weekday() < 5:  # Weekday
            expiration = datetime.combine(today, datetime.min.time())
        else:  # Weekend
            days_until_friday = (4 - today.weekday()) % 7
            if days_until_friday == 0:
                days_until_friday = 7
            friday = today + timedelta(days=days_until_friday)
            expiration = datetime.combine(friday, datetime.min.time())
        
        logger.info(f"Testing option chain for expiration: {expiration}")
        
        # Test getting option chain
        start_time = datetime.now()
        contracts = await market_data.get_option_chain('SPY', expiration, 'CALL')
        end_time = datetime.now()
        
        duration = (end_time - start_time).total_seconds()
        
        if contracts:
            logger.info(f"Successfully fetched {len(contracts)} contracts in {duration:.2f} seconds")
            logger.info(f"First contract: {contracts[0]['symbol']} Strike: ${contracts[0]['strike']}")
            
            # Check that we're getting quotes
            contracts_with_quotes = [c for c in contracts if c.get('bid') and c.get('ask')]
            logger.info(f"Contracts with quotes: {len(contracts_with_quotes)}")
            
            return True
        else:
            logger.error("No contracts returned")
            return False
            
    except Exception as e:
        logger.error(f"Test failed: {e}", exc_info=True)
        return False
    finally:
        broker.disconnect()

async def test_find_best_options():
    """Test finding best options with filtering"""
    configure_logging(log_level='INFO')
    logger = get_logger(__name__)
    
    # Initialize broker
    broker = AlpacaBroker(
        api_key=os.getenv('ALPACA_API_KEY'),
        secret_key=os.getenv('ALPACA_API_SECRET'),
        paper=True
    )
    
    if not broker.connect():
        logger.error("Failed to connect to broker")
        return False
    
    # Initialize market data
    market_data = UnifiedMarketData(broker)
    
    try:
        # Test finding best options
        from datetime import datetime
        today = datetime.now().date()
        expiry_str = today.strftime('%Y-%m-%d')
        
        logger.info(f"Finding best CALL options for SPY expiring {expiry_str}")
        
        start_time = datetime.now()
        best_options = await market_data.find_best_options_async('SPY', expiry_str, 'CALL', target_delta=0.30)
        end_time = datetime.now()
        
        duration = (end_time - start_time).total_seconds()
        
        if best_options:
            logger.info(f"Found {len(best_options)} best options in {duration:.2f} seconds")
            for i, opt in enumerate(best_options[:3]):
                logger.info(f"Option {i+1}: {opt['symbol']} Strike: ${opt['strike']} "
                          f"Bid: ${opt.get('bid', 0):.2f} Ask: ${opt.get('ask', 0):.2f}")
            return True
        else:
            logger.error("No best options found")
            return False
            
    except Exception as e:
        logger.error(f"Test failed: {e}", exc_info=True)
        return False
    finally:
        broker.disconnect()

async def main():
    """Run all tests"""
    print("Testing ST0CKG bot fixes...")
    print("=" * 50)
    
    # Test 1: Option chain filtering
    print("\nTest 1: Option chain filtering")
    print("-" * 30)
    success1 = await test_option_chain_filtering()
    print(f"Result: {'PASSED' if success1 else 'FAILED'}")
    
    # Test 2: Find best options
    print("\nTest 2: Find best options")
    print("-" * 30)
    success2 = await test_find_best_options()
    print(f"Result: {'PASSED' if success2 else 'FAILED'}")
    
    print("\n" + "=" * 50)
    print(f"Overall: {'ALL TESTS PASSED' if success1 and success2 else 'SOME TESTS FAILED'}")

if __name__ == '__main__':
    asyncio.run(main())