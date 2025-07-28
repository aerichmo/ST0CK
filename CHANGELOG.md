# ST0CK Changelog

## [2025-07-28] - Database V2 Implementation - Fix Position ID Constraint Error

### Fixed
- **Database Position ID Constraint Error**: Resolved SQLAlchemy IntegrityError that occurred when logging stock trades
  - Error: "NOT NULL constraint failed: trades.option_type" 
  - Root cause: Single trades table required option-specific fields for all trades including stocks

### Changed
- **Database Schema Separation**: Implemented separate tables for different trade types
  - `stock_trades` table for stock trading strategies (ST0CKA)
  - `option_trades` table for options strategies (ST0CKG)
  - `straddle_trades` table for complex option strategies
  - Each table has appropriate columns without unnecessary constraints

### Technical Implementation
- Created `unified_database_v2.py` with new schema design
- Updated `unified_engine.py` to:
  - Detect trade type based on signal data
  - Use `log_stock_trade()` for stock trades
  - Use `log_option_trade()` for option trades
  - Update exits with appropriate methods
- Added compatibility methods:
  - `get_trades()` combines data from both tables
  - `register_bot()` for backward compatibility

### Migration
- Backed up original database as `unified_database_old.py`
- New database creates separate tables automatically
- Existing data remains in old `trades` table

### Benefits
- No more constraint violations when logging trades
- Cleaner data model with type-specific fields
- Better performance with appropriate indexes
- Easier to query strategy-specific data

## [2025-07-28] - ST0CKA Smart Entry Implementation

### Changed
- **ST0CKA Core Strategy**: Replaced immediate buying with smart entry logic
  - Now waits for optimal technical setups instead of buying instantly at market open
  - Requires 2+ confirmation signals before entering positions
  - Prevents FOMO entries and improves win rate

### New Entry Signals
1. **RSI Oversold Bounce** (weight: 3) - Enters when RSI crosses above 30
2. **VWAP Pullback** (weight: 2) - Buys when price is 0.2%+ below VWAP
3. **Support Test** (weight: 2) - Enters near session lows
4. **Volatility Spike** (weight: 1) - Trades on 20%+ volatility increase
5. **Pullback from High** (weight: 1) - Buys on 0.3%+ pullback

### Enhanced Features
- Dynamic position sizing based on signal strength (1-2 shares)
- RSI-based early exit when overbought (>70)
- Stop loss at 1.5x profit target
- 60-second cooldown between entries
- Debug logging shows why bot is waiting

### Rationale
The original ST0CKA would buy immediately when entering the trading window, regardless of market conditions. This led to poor entries and unnecessary losses. Smart entry ensures we only trade when technical conditions are favorable.

## [2025-07-28] - ST0CKA Enhanced with Volatility Features

### Added
- **ST0CKA Enhanced Strategy**: New advanced implementation inspired by Alpaca's gamma scalping
  - **Volatility Mode**: Dynamic position sizing (1-10 shares) based on volatility
  - **Straddle Mode**: Options straddles for pure volatility harvesting
  - **Adaptive Mode**: Automatically switches strategies based on market conditions
  - **Volatility Arbitrage**: Only enters when realized vol > implied vol (Alpaca's key insight)

### New Features
- Realized volatility calculation using 20-bar lookback
- Implied volatility extraction from ATM options
- Position sizing that scales with volatility and RV/IV ratio
- Straddle scoring algorithm from Alpaca (Theta + Cost / Gamma)
- Delta monitoring and rebalancing for market neutrality
- Stop loss at 1.5x profit target for risk management

### Technical Implementation
- Created `st0cka_enhanced_strategy.py` with multiple trading modes
- Added volatility calculation methods with numpy
- Integrated options chain filtering for liquid contracts
- Async market data fetching for performance

### Usage
```bash
python main_unified.py st0cka_volatility  # Recommended
python main_unified.py st0cka_straddle    # Pure Alpaca approach
python main_unified.py st0cka_adaptive    # Auto-switching
```

## [2025-07-28] - Standard Scalping Profit Targets

### Changed
- **ST0CKA Profit Targets**: Updated from fixed $0.01 to standard scalping targets
  - Now uses 0.13% of entry price (middle of 0.10-0.16% industry standard)
  - Minimum profit target: $0.65 per share
  - Maximum profit target: $1.50 per share
  - Dynamic calculation based on SPY price

### Rationale
Research showed $0.01 profit target was 60x smaller than minimum recommended scalping targets. Even with zero commissions, the risk/reward was poor - one bad fill would erase multiple winning trades. Standard targets align with gamma scalping principles of capturing meaningful volatility moves.

## [2025-07-28] - Power Hour Trading Update

### Added
- **ST0CKA Power Hour Trading**: ST0CKA now trades during power hour (3:00-3:45 PM ET) in addition to morning session
  - Buy window: 3:00-3:30 PM ET
  - Sell window: 3:30-3:45 PM ET
  - Based on gamma scalping research showing power hour as second-highest volatility period

- **Gamma Scalping Hours Configuration**: New `config/gamma_scalping_hours.py` module
  - Defines optimal trading sessions based on intraday volatility patterns
  - Includes volatility multipliers for position sizing
  - Helper functions for session selection

- **Gamma Scalping Guide**: Comprehensive guide at `GAMMA_SCALPING_GUIDE.md`
  - Detailed breakdown of best trading hours
  - Visual volatility heatmap
  - Strategy-specific recommendations

### Changed
- **ST0CKG Sessions**: Removed low-volatility midday session (1:00-2:30 PM ET)
  - Now only trades during morning (9:30-11:00 AM) and power hour (3:00-3:45 PM)
  - Extended morning window from 9:40-10:30 to full 9:30-11:00

### Technical Details
- Updated `src/strategies/st0cka_strategy.py` to support dual-session trading
- Enhanced `src/strategies/st0cka_true_gamma_strategy.py` with volatility-based timing
- Modified `src/gamma_manager.py` to use optimal hours configuration

### Rationale
Research shows that:
- 9:30-11:00 AM ET has the highest intraday volatility (50% above average)
- 3:00-4:00 PM ET has the second-highest spike (30-40% above average)
- 1:00-2:30 PM ET is the "dead zone" with 40% below average volatility

By focusing on high-volatility periods, strategies can capture more price movement while avoiding periods where theta decay dominates gamma gains.