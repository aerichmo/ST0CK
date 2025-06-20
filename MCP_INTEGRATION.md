# Alpaca MCP Server Integration

ST0CK now supports the Alpaca Model Context Protocol (MCP) server for simplified API integration and natural language trading capabilities.

## Benefits of MCP Integration

### 1. Simplified API Calls
- **Before (Traditional Alpaca-py):**
  ```python
  api = TradingClient(api_key, secret_key, paper=True)
  order_data = MarketOrderRequest(
      symbol="SPY",
      qty=10,
      side=OrderSide.BUY,
      time_in_force=TimeInForce.DAY
  )
  order = api.submit_order(order_data)
  ```

- **After (MCP):**
  ```python
  order = mcp_broker.place_option_order(
      symbol="SPY",
      side="buy",
      quantity=10
  )
  ```

### 2. Unified Interface
- Single method calls for complex operations
- Automatic error handling and retries
- Consistent response format across all operations

### 3. Natural Language Support
- Future capability to control trading via conversational commands
- Integration with Claude Desktop and VS Code
- Query positions and performance in plain English

## Setup Instructions

### 1. Install MCP Server
```bash
# Run the setup script
./setup_mcp.sh

# Or manually:
git clone https://github.com/alpacahq/alpaca-mcp-server.git ~/alpaca-mcp-server
cd ~/alpaca-mcp-server
pip install -r requirements.txt
```

### 2. Configure API Credentials
Edit `~/alpaca-mcp-server/.env`:
```env
ALPACA_API_KEY=your_paper_api_key
ALPACA_SECRET_KEY=your_paper_secret_key
PAPER=True
```

### 3. Run ST0CK with MCP
```bash
# Paper trading with MCP
python main.py --broker mcp --mode paper

# Live trading with MCP (when ready)
python main.py --broker mcp --mode live
```

## Architecture Changes

### New Components
1. **MCPBroker** (`src/mcp_broker.py`)
   - Implements BrokerInterface using MCP server
   - Handles order placement, cancellation, and status
   - Manages account information queries

2. **MCPMarketDataProvider** (`src/mcp_market_data.py`)
   - Fetches real-time quotes and historical data
   - Provides option chain data with Greeks
   - Handles market hours and trading calendar

### Integration Points
- The MCP broker is a drop-in replacement for PaperTradingBroker
- Switch between brokers using the `--broker` command line flag
- All existing risk management and strategy logic remains unchanged

## Usage Examples

### Basic Trading
```python
# Initialize MCP broker
broker = MCPBroker(mode="paper")
broker.connect()

# Place an option order
order = broker.place_option_order(
    symbol="SPY",
    expiration="2024-01-15",
    strike=475.0,
    option_type="call",
    side="buy",
    quantity=10
)

# Check order status
status = broker.get_order_status(order.id)

# Get account info
account = broker.get_account_info()
print(f"Buying Power: ${account.buying_power:,.2f}")
```

### Market Data
```python
# Initialize market data provider
market_data = MCPMarketDataProvider()

# Get current quote
quote = market_data.get_stock_quote("SPY")
print(f"SPY: ${quote['price']:.2f}")

# Get option chain
chain = market_data.get_option_chain("SPY", "2024-01-15")
calls = chain['calls']
puts = chain['puts']

# Get historical bars
bars = market_data.get_stock_bars("SPY", "5Min", limit=20)
```

## Advantages Over Direct API

1. **Less Boilerplate**: No need to create request objects or handle complex API responses
2. **Better Error Handling**: MCP server handles retries and error formatting
3. **Consistent Interface**: Same method signatures regardless of paper/live mode
4. **Future-Proof**: Ready for natural language trading when MCP adds chat support
5. **Multi-Platform**: Works with Claude Desktop, VS Code, and command line

## Migration Path

The ST0CK architecture supports both traditional and MCP brokers:
- Continue using paper broker for testing: `--broker paper`
- Switch to MCP for Alpaca integration: `--broker mcp`
- All strategy logic remains unchanged

## Troubleshooting

### MCP Server Not Found
```bash
# Ensure MCP server is installed
ls ~/alpaca-mcp-server

# Re-run setup if needed
./setup_mcp.sh
```

### API Authentication Failed
```bash
# Check credentials in MCP config
cat ~/alpaca-mcp-server/.env

# Verify API keys are correct
# Ensure using paper trading keys for paper mode
```

### Connection Issues
```bash
# Test MCP server directly
cd ~/alpaca-mcp-server
python -m alpaca_mcp_server.client get_account_info
```

## Future Enhancements

1. **Natural Language Control**: Execute trades via chat commands
2. **Interactive Monitoring**: Query positions and P&L conversationally
3. **Strategy Adjustments**: Modify parameters without code changes
4. **Emergency Controls**: Cancel all orders via simple commands
5. **Performance Analytics**: Generate reports through natural language queries

The MCP integration maintains all existing ST0CK functionality while providing a cleaner, more maintainable interface to Alpaca's trading APIs.