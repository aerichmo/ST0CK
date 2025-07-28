#!/usr/bin/env python3
"""
ST0CK Gamma Scalping Launcher
Full integration of Alpaca's gamma scalping with ST0CK infrastructure
"""
import os
import sys
import asyncio
import argparse
from datetime import datetime
import signal
import json

# Ensure logs directory exists
os.makedirs('logs', exist_ok=True)
os.makedirs('logs/gamma_trades', exist_ok=True)

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Add src to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.unified_logging import configure_logging, get_logger
from src.gamma_manager import GammaScalpingManager
from src.error_reporter import ErrorReporter


class GammaScalpingLauncher:
    """
    Main launcher for ST0CK gamma scalping
    Handles initialization, monitoring, and graceful shutdown
    """
    
    def __init__(self, args):
        self.args = args
        self.logger = None
        self.manager = None
        self.start_time = datetime.now()
        
    def setup_logging(self):
        """Configure logging for gamma scalping"""
        log_file = f"logs/gamma_scalping_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        
        configure_logging(
            log_level=self.args.log_level,
            log_to_file=True,
            log_file=log_file,
            sentry_dsn=os.getenv('SENTRY_DSN') if not self.args.no_sentry else None
        )
        
        self.logger = get_logger(__name__)
        self.logger.info("=" * 50)
        self.logger.info("ST0CK Gamma Scalping Starting")
        self.logger.info("=" * 50)
        self.logger.info(f"Configuration:")
        self.logger.info(f"  Mode: {self.args.mode}")
        self.logger.info(f"  DTE Range: {self.args.min_dte}-{self.args.max_dte}")
        self.logger.info(f"  Delta Threshold: {self.args.delta_threshold}")
        self.logger.info(f"  Max Contracts: {self.args.max_contracts}")
        self.logger.info(f"  Paper Trading: {self.args.paper}")
        self.logger.info("=" * 50)
    
    def configure_environment(self):
        """Set environment variables for gamma scalping"""
        # Override config values based on arguments
        os.environ['INITIALIZATION_MODE'] = self.args.mode
        os.environ['MIN_DAYS_TO_EXPIRATION'] = str(self.args.min_dte)
        os.environ['MAX_DAYS_TO_EXPIRATION'] = str(self.args.max_dte)
        os.environ['HEDGING_DELTA_THRESHOLD'] = str(self.args.delta_threshold)
        os.environ['MAX_CONTRACTS'] = str(self.args.max_contracts)
        os.environ['IS_PAPER_TRADING'] = 'true' if self.args.paper else 'false'
        
        # Ensure API credentials are set
        if not os.getenv('ST0CKAKEY') or not os.getenv('ST0CKASECRET'):
            raise ValueError("Missing ST0CK API credentials. Set ST0CKAKEY and ST0CKASECRET")
    
    async def run(self):
        """Run the gamma scalping strategy"""
        try:
            # Create manager
            self.manager = GammaScalpingManager(bot_id="st0cka_gamma")
            
            # Initialize
            self.logger.info("Initializing gamma scalping components...")
            await self.manager.initialize()
            
            # Show account status
            await self.show_account_status()
            
            # Run strategy
            self.logger.info("Starting gamma scalping strategy...")
            await self.manager.run()
            
        except KeyboardInterrupt:
            self.logger.info("Received keyboard interrupt")
        except Exception as e:
            self.logger.error(f"Fatal error: {e}", exc_info=True)
            ErrorReporter.report_failure('gamma_scalping', e, {
                'args': vars(self.args),
                'runtime': (datetime.now() - self.start_time).total_seconds()
            })
            raise
        finally:
            await self.cleanup()
    
    async def show_account_status(self):
        """Display account status before starting"""
        if not self.manager or not self.manager.options_broker:
            return
            
        try:
            account = self.manager.options_broker.get_account()
            positions = self.manager.options_broker.get_positions()
            option_positions = self.manager.options_broker.get_option_positions()
            
            self.logger.info("\n" + "=" * 50)
            self.logger.info("ACCOUNT STATUS")
            self.logger.info("=" * 50)
            self.logger.info(f"Buying Power: ${float(account.buying_power):,.2f}")
            self.logger.info(f"Portfolio Value: ${float(account.portfolio_value):,.2f}")
            self.logger.info(f"Cash: ${float(account.cash):,.2f}")
            
            if positions:
                self.logger.info(f"\nStock Positions: {len(positions)}")
                for symbol, pos in positions.items():
                    self.logger.info(
                        f"  {symbol}: {pos['quantity']} shares @ "
                        f"${pos['avg_price']:.2f} (P&L: ${pos['unrealized_pnl']:.2f})"
                    )
            
            if option_positions:
                self.logger.info(f"\nOption Positions: {len(option_positions)}")
                for pos in option_positions:
                    self.logger.info(
                        f"  {pos['symbol']}: {pos['quantity']} contracts "
                        f"(P&L: ${pos['unrealized_pnl']:.2f})"
                    )
            
            self.logger.info("=" * 50 + "\n")
            
        except Exception as e:
            self.logger.error(f"Failed to show account status: {e}")
    
    async def cleanup(self):
        """Clean up resources"""
        self.logger.info("\n" + "=" * 50)
        self.logger.info("SHUTDOWN SUMMARY")
        self.logger.info("=" * 50)
        
        runtime = (datetime.now() - self.start_time).total_seconds()
        hours = runtime / 3600
        
        self.logger.info(f"Total Runtime: {hours:.2f} hours")
        
        if self.manager:
            self.logger.info(f"Total Trades: {self.manager.total_trades}")
            self.logger.info(f"Total P&L: ${self.manager.total_pnl:.2f}")
            
            # Save final state
            await self.save_final_state()
        
        self.logger.info("=" * 50)
        self.logger.info("Gamma scalping shutdown complete")
    
    async def save_final_state(self):
        """Save final state for analysis"""
        try:
            state = {
                'timestamp': datetime.now().isoformat(),
                'runtime_hours': (datetime.now() - self.start_time).total_seconds() / 3600,
                'total_trades': self.manager.total_trades,
                'total_pnl': self.manager.total_pnl,
                'configuration': vars(self.args)
            }
            
            # Get final positions
            if self.manager.options_broker:
                state['final_positions'] = {
                    'stocks': self.manager.options_broker.get_positions(),
                    'options': self.manager.options_broker.get_option_positions()
                }
            
            # Save to file
            filename = f"logs/gamma_trades/final_state_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(filename, 'w') as f:
                json.dump(state, f, indent=2, default=str)
            
            self.logger.info(f"Final state saved to {filename}")
            
        except Exception as e:
            self.logger.error(f"Failed to save final state: {e}")


def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description='ST0CK Gamma Scalping - Options volatility trading',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run with default settings (0-5 DTE, 3 delta threshold)
  python launch_gamma_scalping.py
  
  # Run with 0DTE only for maximum gamma
  python launch_gamma_scalping.py --min-dte 0 --max-dte 0
  
  # Run with higher delta threshold (less frequent hedging)
  python launch_gamma_scalping.py --delta-threshold 10
  
  # Resume with existing positions
  python launch_gamma_scalping.py --mode resume
  
  # Run in live trading mode (BE CAREFUL!)
  python launch_gamma_scalping.py --live
        """
    )
    
    # Trading mode
    parser.add_argument(
        '--mode', 
        choices=['init', 'resume'], 
        default='init',
        help='Initialization mode: init (close existing) or resume (keep existing)'
    )
    
    # Options parameters
    parser.add_argument(
        '--min-dte', 
        type=int, 
        default=0,
        help='Minimum days to expiration (default: 0)'
    )
    parser.add_argument(
        '--max-dte', 
        type=int, 
        default=5,
        help='Maximum days to expiration (default: 5)'
    )
    
    # Strategy parameters
    parser.add_argument(
        '--delta-threshold', 
        type=float, 
        default=3.0,
        help='Delta threshold for hedging (default: 3.0)'
    )
    parser.add_argument(
        '--max-contracts', 
        type=int, 
        default=5,
        help='Maximum contracts per position (default: 5)'
    )
    
    # Trading environment
    parser.add_argument(
        '--live', 
        action='store_true',
        help='Use LIVE trading (default: paper trading)'
    )
    parser.add_argument(
        '--paper', 
        action='store_true',
        default=True,
        help='Use paper trading (default)'
    )
    
    # Logging
    parser.add_argument(
        '--log-level', 
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        default='INFO',
        help='Logging level (default: INFO)'
    )
    parser.add_argument(
        '--no-sentry', 
        action='store_true',
        help='Disable Sentry error reporting'
    )
    
    args = parser.parse_args()
    
    # Handle live/paper logic
    if args.live:
        args.paper = False
    
    return args


async def main():
    """Main entry point"""
    # Parse arguments
    args = parse_arguments()
    
    # Create launcher
    launcher = GammaScalpingLauncher(args)
    
    # Setup
    launcher.setup_logging()
    launcher.configure_environment()
    
    # Show startup banner
    print("\n" + "=" * 50)
    print("ST0CK GAMMA SCALPING")
    print("=" * 50)
    print(f"Mode: {'PAPER' if args.paper else 'LIVE'} TRADING")
    print(f"Strategy: {args.mode.upper()}")
    print(f"Options: {args.min_dte}-{args.max_dte} DTE")
    print(f"Delta Threshold: {args.delta_threshold}")
    print("=" * 50)
    print("Press Ctrl+C to stop")
    print("=" * 50 + "\n")
    
    # Run
    await launcher.run()


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nShutdown requested by user")
    except Exception as e:
        print(f"\nFATAL ERROR: {e}")
        sys.exit(1)