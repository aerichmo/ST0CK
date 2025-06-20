#!/bin/bash

# Setup script for Alpaca MCP Server integration with ST0CK

echo "Setting up Alpaca MCP Server for ST0CK integration..."

# Check if we're in the right directory
if [ ! -f "main.py" ]; then
    echo "Error: Please run this script from the ST0CK directory"
    exit 1
fi

# Clone MCP server if not already present
if [ ! -d "$HOME/alpaca-mcp-server" ]; then
    echo "Cloning Alpaca MCP server..."
    git clone https://github.com/alpacahq/alpaca-mcp-server.git "$HOME/alpaca-mcp-server"
else
    echo "MCP server already cloned. Updating..."
    cd "$HOME/alpaca-mcp-server" && git pull
    cd - > /dev/null
fi

# Install MCP dependencies
echo "Installing MCP server dependencies..."
cd "$HOME/alpaca-mcp-server"
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Create MCP config file if not exists
if [ ! -f "$HOME/alpaca-mcp-server/.env" ]; then
    echo "Creating MCP configuration..."
    cat > "$HOME/alpaca-mcp-server/.env" << EOF
# Alpaca API Configuration
ALPACA_API_KEY=your_alpaca_api_key
ALPACA_SECRET_KEY=your_alpaca_secret_key
PAPER=True
EOF
    echo "Please edit $HOME/alpaca-mcp-server/.env with your Alpaca API credentials"
fi

cd - > /dev/null

# Update ST0CK requirements if needed
if ! grep -q "mcp-client" requirements.txt; then
    echo "Adding MCP client to requirements..."
    echo "mcp-client>=0.1.0" >> requirements.txt
fi

echo ""
echo "MCP Setup Complete!"
echo ""
echo "Next steps:"
echo "1. Edit $HOME/alpaca-mcp-server/.env with your Alpaca API credentials"
echo "2. Run ST0CK with MCP broker: python main.py --broker mcp --mode paper"
echo ""
echo "Example commands:"
echo "  Paper trading with MCP: python main.py --broker mcp --mode paper"
echo "  Live trading with MCP:  python main.py --broker mcp --mode live"
echo ""