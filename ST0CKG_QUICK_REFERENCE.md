# APEX Quick Reference

## Trading Sessions
| Session | Time | Delta | Focus |
|---------|------|-------|-------|
| Morning | 9:30-11:00 | 40-45 | Momentum, Gamma |
| Midday | 1:00-2:30 | 30-35 | VWAP, Reversals |
| Power Hour | 3:00-3:45 | 45-50 | EOD, Unwind |

## Signal Types & Scoring
1. **Gamma Squeeze** (3.0) - MM trapped
2. **VWAP Reclaim** (2.5) - Mean reversion  
3. **Opening Drive** (2.0) - Momentum
4. **Liquidity Vacuum** (2.5) - Thin books
5. **Options Pin** (2.0) - Strike magnet
6. **Dark Pool** (1.5) - Institutional

Min score to trade: 6.0

## Risk Management
- Base risk: 3% (aggressive for $5k)
- Range: 2-6%
- Capital multiplier: 1.5x under $10k
- Max daily loss: $500
- Max consecutive losses: 3
- Max concurrent: 2

## Position Sizing Factors
1. **Capital-based** (1.5x under $10k)
2. Win/loss streak
3. Volatility (VIX)
4. Time in session
5. Signal quality
6. Session type
7. Day of week

## Exit Rules
- Stop loss (structure/ATR)
- Profit targets (by setup type)
- Time exits (45/90 min)
- Session end
- Trailing stop (1R activation)

## Commands
```bash
# Run APEX
python main_multi.py apex

# Check logs
tail -f logs/apex_*.log
```

## Required ENV
```
STOCKG_KEY=xxx
ST0CKG_SECRET=xxx
APEX_TRADING_CAPITAL=5000
```