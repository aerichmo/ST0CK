# Migration Guide: Transitioning to MCP as Default Broker

## Overview
ST0CK now uses the Alpaca MCP (Model Context Protocol) server as the default broker implementation, providing simplified API integration and enhanced capabilities. The built-in paper trading broker remains available for offline testing.

## What's Changed

### Default Broker
- **Before**: Built-in paper trading broker was default (`--broker paper`)
- **Now**: Alpaca MCP is default (`--broker mcp`)

### Market Data
- **Before**: Yahoo Finance for all market data
- **Now**: Alpaca MCP for real-time data when using MCP broker, Yahoo Finance fallback for paper broker

### Command Line
- **Before**: `python main.py --mode paper`
- **Now**: Same command, but uses MCP by default

## Migration Steps

### 1. Install MCP Server
```bash
# Run the provided setup script
./setup_mcp.sh
```

### 2. Configure Alpaca Credentials
Edit `~/alpaca-mcp-server/.env`:
```env
ALPACA_API_KEY=your_alpaca_api_key
ALPACA_SECRET_KEY=your_alpaca_secret_key
PAPER=True
```

### 3. Update Your Scripts
If you have automation scripts, no changes needed unless you want to force paper broker:
```bash
# Uses MCP by default now
python main.py --mode paper

# Force built-in paper broker
python main.py --broker paper --mode paper
```

## Benefits of MCP

### 1. Real-Time Market Data
- More accurate quotes and fills
- Actual market hours validation
- Live options chains with Greeks

### 2. Simplified Code
- Cleaner API calls
- Built-in error handling
- Automatic retries

### 3. Future Capabilities
- Natural language trading commands
- Interactive monitoring via Claude/VS Code
- Conversational strategy adjustments

## When to Use Each Broker

### Use MCP Broker (Default)
- Production trading
- Testing with real market data
- Integration with Alpaca accounts
- When internet connection is available

### Use Paper Broker
- Offline development
- Unit testing
- Strategy backtesting
- When Alpaca API is unavailable

## Troubleshooting

### MCP Connection Issues
```bash
# Check MCP server status
cd ~/alpaca-mcp-server
python -m alpaca_mcp_server.client get_account_info

# Verify credentials
cat ~/alpaca-mcp-server/.env
```

### Fallback to Paper Broker
```bash
# If MCP fails, use paper broker
python main.py --broker paper
```

### Performance Comparison
- MCP: ~50-100ms API latency
- Paper: 0ms (local simulation)

## Code Compatibility

All existing strategies and configurations work with both brokers:
- Risk management rules unchanged
- Trading strategies compatible
- Database logging consistent
- Monitoring webhooks functional

## FAQ

**Q: Do I need an Alpaca account?**
A: Yes, for MCP broker. Free paper trading account is sufficient.

**Q: Can I still use paper broker?**
A: Yes, use `--broker paper` flag.

**Q: Will my strategies need modification?**
A: No, the broker interface is unchanged.

**Q: Is MCP more expensive?**
A: No, uses same Alpaca pricing (free for paper trading).

## Support

For issues with:
- MCP setup: Check [Alpaca MCP docs](https://github.com/alpacahq/alpaca-mcp-server)
- ST0CK integration: See MCP_INTEGRATION.md
- General questions: Review README.md