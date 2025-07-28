# ST0CK Changelog

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