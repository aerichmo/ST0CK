# ST0CK Real-Time Trading Visualization

## Overview

ST0CK now includes powerful real-time visualization tools to monitor your trading activity. Watch candlestick charts update live, see your trades execute on the chart, and track performance metrics in real-time.

## Features

### 1. Real-Time Candlestick Charts
- 5-minute SPY candles with live updates
- Technical indicators (EMA 8 & 21)
- Opening range visualization (9:30-9:40 ET)
- Volume analysis with color-coded bars

### 2. Trade Execution Overlay
- Green triangles (▲) for buy signals
- Red triangles (▼) for sell signals
- Trade annotations with price and P&L
- Position tracking with real-time P&L

### 3. Two Visualization Modes

#### Web Dashboard (Recommended)
- Modern web interface accessible from any browser
- Real-time updates every 5 seconds
- Account status and position monitoring
- Trade log with recent executions
- No installation required - just open browser

#### Matplotlib Viewer
- Desktop application using matplotlib
- Direct integration with trading engine
- Suitable for single-monitor setups
- Lower resource usage

## Quick Start

### Web Dashboard
```bash
# Start the web dashboard
python visualize.py --mode web

# Access at http://localhost:8050
```

### Matplotlib Viewer
```bash
# Start the matplotlib viewer
python visualize.py --mode matplotlib
```

### Live Trading Integration
```bash
# Connect to live trading engine
python visualize.py --mode web --live

# This starts both trading and visualization
```

## Usage Examples

### Basic Monitoring
```bash
# Monitor with default settings (MCP data, web mode)
python visualize.py
```

### Custom Configuration
```bash
# Use specific broker and port
python visualize.py --broker mcp --port 8080

# Use paper broker data
python visualize.py --broker paper --mode matplotlib
```

### Production Setup
```bash
# Run trading engine
python main.py --broker mcp --mode paper &

# Run visualization dashboard
python visualize.py --mode web --live --port 8050
```

## Dashboard Features

### Account Status Panel
- Buying power
- Portfolio value  
- Realized P&L
- Daily statistics

### Position Monitor
- Current symbol and quantity
- Average entry price
- Real-time unrealized P&L
- Exit target levels

### Trade Log
- Last 10 trades
- Entry/exit prices
- Individual trade P&L
- Timestamp for each trade

### Chart Indicators
- **Yellow dashed lines**: Opening range high/low
- **Cyan line**: 8-period EMA
- **Orange line**: 21-period EMA
- **Green candles**: Bullish (close > open)
- **Red candles**: Bearish (close < open)

## Technical Details

### Trading Time Windows
- **Opening Range**: 9:30-9:40 AM ET (establishes high/low)
- **Active Trading**: 9:40-10:30 AM ET (new trades allowed)
- **Position Monitoring**: 10:30 AM-4:05 PM ET (exits only)
- **Data Updates**: Only during market hours (9:30 AM-4:05 PM ET)

### Update Frequency
- Chart updates: Every 5 seconds during active hours
- No updates on weekends or after hours
- Trade markers: Real-time from database
- Position info: Real-time from broker
- Account data: Every 5 seconds during market hours

### Data Sources
- **Market Data**: Real-time Alpaca API (required)
- **Trade Data**: PostgreSQL database (optional)
- **Update Intervals**:
  - Pre-market & Active Trading (9:20-10:30 AM): Every 1 second
  - Position Monitoring (10:31 AM-4:05 PM): Every 15 seconds
  - All Other Times: Every 5 minutes

### Performance
- Web dashboard: ~50MB RAM
- Matplotlib viewer: ~100MB RAM
- CPU usage: <5% during normal operation

### Execution Timing (Improved)
The trading engine now uses dynamic execution intervals:
- **Pre-market & Active Trading (9:20-10:30 AM)**:
  - Signal scanning: Every 1 second
  - Position monitoring: Every 1 second  
  - Maximum 1-second delay for breakout detection
- **Position Monitoring (10:31 AM-4:05 PM)**:
  - Signal scanning: Every 5 seconds
  - Position monitoring: Every 2 seconds
  - Faster exit management during market hours
- **Idle Times**:
  - Signal scanning: Every 30 seconds
  - Position monitoring: Every 10 seconds
  - Resource conservation when not actively trading

## Troubleshooting

### Dashboard Won't Start
```bash
# Check if port is in use
lsof -i :8050

# Use different port
python visualize.py --port 8081
```

### No Data Showing
```bash
# Verify market data connection
python -c "from src.mcp_market_data import MCPMarketDataProvider; \
m = MCPMarketDataProvider(); print(m.get_stock_quote('SPY'))"
```

### Slow Updates
- Check internet connection
- Verify database connection
- Reduce update interval in code if needed

## Advanced Features

### Custom Indicators
Add custom indicators by modifying `candle_visualizer.py`:
```python
# Add RSI
self.price_data['rsi'] = calculate_rsi(self.price_data['close'])
```

### Multiple Symbols
While ST0CK focuses on SPY, the visualizer can be extended:
```python
# In web_dashboard.py
symbols = ['SPY', 'QQQ', 'IWM']
```

### Export Data
The web dashboard can be extended with export functionality:
- Download trade history as CSV
- Export performance reports
- Save chart snapshots

## Integration with Trading

The visualizer integrates seamlessly with ST0CK's trading engine:

1. **Opening Range Detection**: See the exact moment when opening range is established
2. **Breakout Signals**: Watch as price breaks above/below with volume confirmation
3. **Entry Execution**: See your option orders fill in real-time
4. **Exit Management**: Monitor stop loss and profit target levels
5. **Risk Tracking**: Visual feedback when approaching daily loss limits

## Best Practices

1. **Multi-Monitor Setup**: Run web dashboard on second monitor
2. **Mobile Access**: Access web dashboard from phone/tablet on same network
3. **Logging**: Keep visualizer logs for post-trade analysis
4. **Screenshots**: Capture important trade setups for review

## Future Enhancements

- Heat map for option chain
- Greeks visualization
- Multi-timeframe analysis
- Backtesting overlay
- Performance analytics dashboard

The visualization tools transform ST0CK from a headless bot into a comprehensive trading platform with professional-grade monitoring capabilities.