# ST0CK Enhanced - Gamma Scalping Infrastructure for ST0CK Strategies

This project combines the sophisticated infrastructure from Alpaca's gamma scalping implementation with ST0CK's proven trading strategies, creating a powerful hybrid trading system.

## 🚀 What's New

- **Multi-Strategy Support**: Run ST0CKA, ST0CKG, gamma scalping, or hybrid modes
- **Volatility-Aware Trading**: Dynamic position sizing based on market conditions
- **Enhanced Performance**: Async architecture with intelligent caching
- **Improved Risk Management**: Multiple safety layers and real-time monitoring
- **Easy Configuration**: Simple environment-based setup

## 📊 Available Strategies

### 1. ST0CKA Enhanced
- **Original**: Buy 1 SPY share, sell for $0.01 profit
- **Enhanced**: Volatility-based position sizing (1-3 shares)
- **New Features**: Mean reversion detection, dynamic targets

### 2. ST0CKG Enhanced  
- **Original**: 6 signal types for 0-DTE options
- **Enhanced**: Added dealer gamma signal from options flow
- **New Features**: Improved signal detection using gamma insights

### 3. Gamma Scalping (Original)
- **Strategy**: Market-neutral options straddle with delta hedging
- **Best For**: Volatile, range-bound markets
- **Capital**: Higher requirements due to options premiums

### 4. Hybrid Mode
- **Adaptive**: Switches strategies based on volatility regime
- **Low Vol**: Uses ST0CKA approach
- **High Vol**: Uses gamma scalping approach

## 🛠️ Quick Start

### 1. Installation

```bash
# Clone and enter directory
cd ST0CK/gamma-scalping-fork

# Install dependencies
pip install -r requirements_st0ck.txt

# Setup environment
cp .env.st0ck.template .env
# Edit .env with your API credentials
```

### 2. Configuration

Edit `.env` file:
```bash
# Essential settings
IS_PAPER_TRADING=true
ST0CKAKEY=your_alpaca_api_key
ST0CKASECRET=your_alpaca_secret
STRATEGY_MODE=st0cka
```

### 3. Run a Strategy

```bash
# Simple ST0CKA
python run_st0ck.py st0cka

# ST0CKA with volatility sizing
python run_st0ck.py st0cka

# ST0CKG enhanced
python run_st0ck.py st0ckg

# Original gamma scalping
python run_st0ck.py gamma_scalping

# Hybrid mode
python run_st0ck.py hybrid
```

## ⚙️ Configuration Options

### Strategy Modes

| Mode | Description | Capital Req | Risk Level |
|------|-------------|-------------|------------|
| `st0cka` | Simple SPY scalping | Low ($500) | Low |
| `st0ckg` | Options signal trading | Medium ($2K) | Medium |
| `gamma_scalping` | Delta-neutral options | High ($10K+) | Medium |
| `hybrid` | Adaptive switching | Medium ($5K) | Medium |

### Key Settings

```python
# ST0CKA Configuration
ST0CKA_CONFIG = {
    "profit_target": 0.01,           # $0.01 per share
    "position_size_min": 1,          # Minimum shares
    "position_size_max": 3,          # Maximum shares
    "use_volatility_sizing": True,   # Dynamic sizing
    "use_mean_reversion": False,     # Mean reversion mode
}

# Volatility Thresholds
VOLATILITY_CONFIG = {
    "low_vol_threshold": 0.10,       # 10% vol = max size
    "high_vol_threshold": 0.25,      # 25% vol = min size
}

# Risk Management
RISK_MANAGEMENT = {
    "max_daily_loss": -500.0,        # Stop at $500 loss
    "max_consecutive_losses": 3,     # Stop after 3 losses
}
```

## 🔄 How It Works

### Architecture Overview

```
Market Data → Strategy Engine → Risk Manager → Position Manager → Alpaca API
     ↓              ↓               ↓              ↓
  Caching      Signal Detection  Limit Checks   Execution
  Filtering    Position Sizing   P&L Tracking   Fill Monitoring
```

### Strategy Selection Logic

```python
def select_strategy(volatility, market_regime):
    if mode == "hybrid":
        if volatility > 0.20:
            return "gamma_scalping"
        else:
            return "st0cka"
    elif mode == "st0cka":
        return enhance_with_volatility_sizing()
    elif mode == "st0ckg":  
        return add_gamma_signals()
```

## 📈 Performance Features

### From Gamma Scalping Infrastructure
- **Async Architecture**: Handle multiple data streams efficiently
- **Queue-Based Communication**: Prevent data bottlenecks
- **Intelligent Triggering**: Only process significant price moves
- **Robust Error Handling**: Graceful degradation and recovery

### ST0CK Enhancements
- **Volatility Awareness**: Adjust position size based on market conditions
- **Mean Reversion Signals**: Profit from VWAP deviations
- **Dynamic Targets**: Scale profit targets with volatility
- **Multi-Timeframe Analysis**: Combine different signal types

## 🎯 Trading Examples

### ST0CKA Enhanced Example

```python
# Traditional ST0CKA
Buy 1 SPY @ $590.00
Sell 1 SPY @ $590.01
Profit: $0.01

# Enhanced ST0CKA (high volatility day)
Current Vol: 25% (high)
Position Size: 1 share (conservative)
Target: $0.025 (scaled with vol)

Buy 1 SPY @ $590.00  
Sell 1 SPY @ $590.025
Profit: $0.025
```

### Hybrid Mode Example

```python
# Morning: Low volatility detected
Strategy: ST0CKA mode
Position: 3 shares (max size)

# Afternoon: Volatility spike
Strategy: Switch to gamma scalping
Position: Buy straddle, hedge with shares
```

## 🔧 Command Line Options

```bash
# Basic usage
python run_st0ck.py <strategy> [options]

# Examples
python run_st0ck.py st0cka --live              # Live trading
python run_st0ck.py st0ckg --debug             # Debug mode
python run_st0ck.py hybrid --volatility-off    # Disable vol sizing
python run_st0ck.py st0cka --mean-reversion    # Enable mean reversion
```

## 📊 Monitoring

### Real-Time Metrics
- Daily P&L tracking
- Position monitoring
- Volatility regime detection
- Signal effectiveness

### Performance Dashboard
```bash
# View performance (if ST0CK components available)
http://localhost:10000/

# API endpoints
/api/performance  # Trading results
/api/metrics      # System performance
```

## 🛡️ Risk Management

### Multiple Safety Layers
1. **Daily Loss Limits**: Stop at -$500
2. **Consecutive Loss Protection**: Stop after 3 losses
3. **Position Size Limits**: Max 25% of portfolio
4. **Volatility Adjustments**: Reduce size in high vol
5. **Time-Based Exits**: Close before market close

### Dynamic Adjustments
- Position size scales with volatility
- Profit targets adjust to market conditions
- Strategy switches based on regime

## 🔄 Migration from Original ST0CK

### Easy Migration Path
1. **Keep existing ST0CK**: No changes needed
2. **Test enhanced version**: Run side-by-side
3. **Gradual adoption**: Start with volatility sizing
4. **Full integration**: Switch when comfortable

### Configuration Mapping
```python
# Original ST0CK
position_size = 1
profit_target = 0.01

# Enhanced Version
position_size = calculate_volatility_size(1, 3)
profit_target = scale_with_volatility(0.01)
```

## 🚧 Development Roadmap

### Phase 1: Foundation ✅
- [x] Infrastructure integration
- [x] Basic ST0CKA enhancement
- [x] Configuration system
- [x] Launch scripts

### Phase 2: Enhancement 🚧
- [ ] Full ST0CKG integration
- [ ] Options support for ST0CKG
- [ ] Advanced signal detection
- [ ] Performance analytics

### Phase 3: Advanced 📋
- [ ] Machine learning integration
- [ ] Multi-asset support
- [ ] Advanced risk models
- [ ] Institutional features

## 🤝 Contributing

This project builds on Alpaca's excellent gamma scalping foundation. Contributions welcome for:
- Strategy improvements
- Risk management enhancements
- Performance optimizations
- Documentation updates

## 📄 License

Based on Alpaca's gamma scalping project. See original LICENSE for terms.

---

**⚠️ Important Notes:**
- Always test with paper trading first
- Start with small position sizes
- Monitor performance closely
- Understand the risks involved

**🎯 Best Practices:**
- Run in paper mode for 2+ weeks
- Start with ST0CKA mode
- Enable volatility sizing gradually
- Monitor daily P&L limits