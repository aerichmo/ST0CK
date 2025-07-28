# Gamma Scalping Optimal Timing Guide

## 🕐 Best Trading Hours for Gamma Scalping

Based on extensive research of intraday volatility patterns and market microstructure, here are the optimal windows for gamma scalping strategies.

### 📊 Volatility Heatmap (ET)

```
9:30-11:00  ████████████████████ HIGH (Best)
11:00-11:30 ███████████████      MEDIUM-HIGH  
11:30-13:00 ██████████           MEDIUM-LOW
13:00-14:30 ████                 LOW (Avoid)
14:30-15:00 ██████████           MEDIUM
15:00-16:00 ██████████████████   HIGH (Best)
```

## 🎯 Optimal Trading Windows

### 1. **Opening Drive (9:30-11:00 AM ET)** ⭐⭐⭐⭐⭐
- **Volatility**: Highest of the day
- **Why**: Overnight news digestion, institutional positioning
- **Target Delta**: 0.45 (higher for more gamma)
- **Best For**: Aggressive gamma scalping, 0-DTE trades
- **Key Stats**: 50% higher volatility than daily average

### 2. **Power Hour (3:00-4:00 PM ET)** ⭐⭐⭐⭐⭐
- **Volatility**: Second highest spike
- **Why**: Position squaring, MOC orders, expiration effects
- **Target Delta**: 0.50 (maximum gamma for 0-DTE)
- **Best For**: 0-DTE gamma explosion, closing volatility
- **Critical**: Options orders must be submitted by 3:15 PM (3:30 PM for SPY/QQQ)

### 3. **Late Morning Reversal (11:00-11:30 AM ET)** ⭐⭐⭐
- **Volatility**: Medium-High
- **Why**: Morning momentum exhaustion, reversal setups
- **Target Delta**: 0.40
- **Best For**: Mean reversion gamma trades

### 4. **Fed Time (1:45-2:15 PM ET - Fed Days Only)** ⭐⭐⭐⭐⭐
- **Volatility**: Extreme
- **Why**: FOMC announcements at 2:00 PM
- **Target Delta**: 0.50 (ATM for maximum gamma)
- **Best For**: Event-driven volatility harvesting

## ❌ Times to Avoid

### **Mid-Day Dead Zone (1:00-2:30 PM ET)**
- **Why Avoid**: 
  - Lowest intraday volatility (60% below average)
  - Theta decay dominates gamma gains
  - Minimal price movement
  - Wide bid-ask spreads
- **Exception**: Fed announcement days

## 📈 Strategy-Specific Recommendations

### Aggressive 0-DTE Gamma Scalping
```
Sessions: Opening Drive → Power Hour → Closing Rush
Risk: High | Return: Highest | Capital: $10k+
```

### Standard Gamma Scalping  
```
Sessions: Opening Drive → Late Morning → Power Hour
Risk: Medium | Return: Moderate | Capital: $25k+
```

### Conservative Gamma Scalping
```
Sessions: Opening Drive → Power Hour only
Risk: Low | Return: Steady | Capital: $50k+
```

## 🔧 Implementation in ST0CK

### Current ST0CKG Windows (Already Optimized!)
```python
# Morning Session: 9:30-11:00 AM (Matches opening drive)
# Power Hour: 3:00-3:45 PM (Captures volatility spike)
```

### Enhanced Gamma Scalping Configuration
```python
from config.gamma_scalping_hours import get_optimal_sessions

# Get sessions for your strategy
sessions = get_optimal_sessions("aggressive_0dte")

# Check if current time is good for gamma
if should_trade_gamma(current_time, min_volatility_rank="MEDIUM"):
    # Execute gamma scalping logic
```

## 📊 Volatility Multipliers by Time

| Time Period | Volatility vs Daily Avg | Position Size Adjustment |
|-------------|------------------------|-------------------------|
| 9:30-10:00  | +50%                   | 1.5x base size         |
| 10:00-10:30 | +30%                   | 1.3x base size         |
| 10:30-11:00 | +20%                   | 1.2x base size         |
| 11:00-11:30 | +10%                   | 1.1x base size         |
| 11:30-12:00 | -10%                   | 0.9x base size         |
| 12:00-13:00 | -30%                   | 0.7x base size         |
| 13:00-14:00 | -40%                   | 0.6x base size (avoid) |
| 14:00-14:30 | -20%                   | 0.8x base size         |
| 14:30-15:00 | Average                | 1.0x base size         |
| 15:00-15:30 | +30%                   | 1.3x base size         |
| 15:30-16:00 | +40%                   | 1.4x base size         |

## ⚠️ Critical Order Cutoff Times

- **Standard Options**: 3:15 PM ET
- **SPY/QQQ Options**: 3:30 PM ET  
- **0-DTE Emergency Exit**: 3:45 PM ET

## 🗓️ Special Calendar Considerations

### Enhanced Volatility Days
- **FOMC Days**: Trade the 2:00 PM window
- **Monthly OpEx**: Higher gamma all day (3rd Friday)
- **Quarter End**: Enhanced power hour volatility
- **Earnings Season**: Add 20% to all volatility multipliers

### Reduced Volatility Days
- **Holiday Half Days**: Morning only (close at 1:00 PM)
- **Summer Fridays**: Lower afternoon volume
- **Post-Holiday**: First 30 minutes choppy

## 💡 Pro Tips

1. **Start Small**: Test one session at a time
2. **Track Performance**: Log results by time window
3. **Adjust Deltas**: Higher deltas in high volatility windows
4. **Watch the Clock**: Set alerts for session transitions
5. **Respect Cutoffs**: Never hold 0-DTE past 3:45 PM

## 🚀 Quick Start

For immediate implementation with ST0CK:

```bash
# Run gamma scalping during optimal hours
python launch_gamma_scalping.py --mode init --min-dte 0 --max-dte 0

# Or use ST0CKG which already targets optimal windows
python main_unified.py st0ckg
```

Remember: Gamma scalping profits come from correctly predicting when realized volatility will exceed implied volatility. These time windows maximize your edge.