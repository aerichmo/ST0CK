# ST0CK Technical Documentation

Comprehensive technical documentation for the ST0CK automated trading system.

## System Architecture

### Core Components

#### 1. **Trading Engines**

- **BaseEngine** (`src/base_engine.py`)
  - Abstract base class for all trading engines
  - Handles broker initialization, market hours, risk checks
  - Provides common functionality to avoid duplication

- **FastTradingEngine** (`src/base_fast_engine.py`)
  - High-performance engine for options trading
  - Pre-fetches option chains at session start
  - Implements opening range calculations

- **UnifiedSimpleEngine** (`src/unified_simple_engine.py`)
  - Configurable engine for stock trading
  - Supports both simple and advanced modes
  - Used by ST0CKA strategy

- **ST0CKGEngine** (`src/st0ckg_engine.py`)
  - Specialized for ST0CKG/Battle Lines strategy
  - Multi-signal pattern recognition
  - ATM option selection

#### 2. **Market Data Layer**

- **UnifiedMarketData** (`src/unified_market_data.py`)
  - Single source of truth for all market data
  - Multi-level caching (5s quotes, 60s options, 5m bars)
  - Connection pooling integration
  - Async support for concurrent fetching
  - Cache statistics tracking

- **ConnectionPool** (`src/connection_pool.py`)
  - Manages Alpaca API connections
  - Rate limiting per endpoint type
  - Automatic retry with exponential backoff
  - Connection pool statistics

#### 3. **Order Execution**

- **AlpacaBroker** (`src/alpaca_broker.py`)
  - Implements BrokerInterface
  - Handles all order types (market, limit, stop)
  - OCO (One-Cancels-Other) order support
  - Position management

#### 4. **Risk Management**

- **RiskManager** (`src/risk_manager.py`)
  - Dynamic position sizing based on:
    - Account size
    - Market volatility
    - Win/loss streaks
    - Time of day
    - Signal strength
  - Daily loss limits
  - Consecutive loss protection

#### 5. **Data Persistence**

- **MultiBotDatabaseManager** (`src/multi_bot_database.py`)
  - Supports multiple concurrent bots
  - Trade logging and performance tracking
  - Bot registry management
  - Batched writes for performance

### Strategy Components

#### ST0CKG Strategy

**Signal Types** (weighted 0-10):
1. **Gamma Squeeze** (8.5) - Market maker positioning
2. **VWAP Reclaim** (7.0) - Mean reversion
3. **Opening Drive** (7.5) - Momentum continuation
4. **Liquidity Vacuum** (6.5) - Thin order book moves
5. **Options Pin** (6.0) - High OI magnetization
6. **Dark Pool Flow** (5.5) - Institutional bias

**Position Sizing Factors**:
- Base risk: 3% of capital
- Account size multiplier (0.5-1.5x)
- Volatility adjustment (0.7-1.3x)
- Win rate modifier (0.8-1.2x)
- Time decay factor (0.8-1.0x)
- Consecutive wins/losses (0.7-1.3x)
- Signal strength (0.8-1.2x)
- Regime filter (0.5-1.0x)

**Exit Rules**:
- Stop loss: 1R (R = $0.10 SPY move)
- Target 1: 1.5R (50% position)
- Target 2: 3R (remaining position)
- Trailing stop: Activated at 1R profit
- Time exit: Close before session end

#### ST0CKA Strategy

- Simple buy-and-hold for small profit
- Entry: Market buy 1 SPY share
- Exit: Limit sell at entry + $0.01
- Time-based exit at 10:55 AM if at breakeven
- Maximum risk: $10 per day

## Performance Optimizations

### 1. **Caching Strategy**

```python
# Cache TTLs optimized for different data types
quote_cache = TTLCache(maxsize=1000, ttl=5)      # Real-time quotes
option_cache = TTLCache(maxsize=5000, ttl=60)    # Option chains
snapshot_cache = TTLCache(maxsize=2000, ttl=30)  # Option Greeks
bar_cache = TTLCache(maxsize=100, ttl=300)       # Historical bars
```

### 2. **Connection Pooling**

- 3 stock data connections
- 3 option data connections  
- 2 trading connections
- Automatic connection reuse
- Rate limiting prevents throttling

### 3. **Database Optimizations**

- Bulk insert operations using `bulk_insert_mappings`
- Background thread for batch flushing
- IPv4 DNS caching for cloud databases
- Connection pooling for concurrent access

### 4. **Async Operations**

```python
# Fetch multiple quotes concurrently
async def get_multiple_quotes_async(symbols):
    return await connection_manager.get_multiple_quotes_async(symbols)
```

## Monitoring and Metrics

### Cache Performance Metrics

Available at `/api/metrics`:
- Cache hit rates by type
- Total hits/misses
- Cache sizes
- Connection pool utilization
- API request statistics

### Performance Tracking

- Trade-level P&L tracking
- Session-based performance
- Signal type effectiveness
- Risk-adjusted returns

## Testing Strategy

### 1. **Unit Testing**

Test individual components:
- Signal generation accuracy
- Risk calculations
- Order execution logic

### 2. **Integration Testing**

Test component interactions:
- Market data → Strategy → Execution
- Database persistence
- Error handling

### 3. **Paper Trading**

Required before live trading:
- Minimum 2 weeks paper trading
- Track all metrics
- Verify risk management

### 4. **Performance Testing**

- Cache hit rate > 80%
- API response time < 100ms
- Order execution < 500ms

## Deployment

### Local Development

```bash
# Development mode with debug logging
export LOG_LEVEL=DEBUG
python main_multi.py st0ckg
```

### Production Deployment

1. **GitHub Actions** (Recommended)
   - Automated daily execution
   - Secure credential management
   - Artifact storage for logs

2. **Cloud Deployment**
   - Use PostgreSQL for database
   - Enable connection pooling
   - Monitor resource usage

3. **Monitoring**
   - CloudWatch/Datadog for metrics
   - Alerts for errors/failures
   - Daily performance reports

## Future Enhancements

### Machine Learning Integration

1. **Signal Scoring Optimization**
   - Historical performance analysis
   - Dynamic weight adjustment
   - Pattern recognition improvement

2. **Market Regime Detection**
   - Volatility regime classification
   - Trend strength analysis
   - Correlation monitoring

3. **Execution Optimization**
   - Smart order routing
   - Liquidity analysis
   - Spread optimization

### Infrastructure Improvements

1. **Horizontal Scaling**
   - Multiple bot instances
   - Load balancing
   - Distributed caching

2. **Enhanced Monitoring**
   - Real-time dashboards
   - Predictive alerts
   - Performance attribution

## Code Examples

### Creating a New Strategy

```python
from bots.base.strategy import BaseStrategy
from bots.base.strategy import Signal, SignalType

class MyStrategy(BaseStrategy):
    def check_entry_conditions(self, market_data: Dict) -> Optional[Signal]:
        # Implement your logic
        if some_condition:
            return Signal(
                signal_type=SignalType.LONG,
                strength=0.8,
                metadata={'reason': 'My signal'}
            )
        return None
```

### Adding a New Signal Type

```python
# In st0ckg_signals.py
def detect_my_signal(self, data: Dict) -> Dict:
    score = 0.0
    
    # Your signal logic here
    if condition_met:
        score = 8.0
    
    return {
        'score': score,
        'details': 'Signal details',
        'confidence': 'HIGH'
    }
```

### Custom Risk Management

```python
# In risk_manager.py
def calculate_position_size_custom(self, signal_strength: float) -> int:
    base_size = self.capital * self.base_risk / 100
    
    # Add your factors
    my_factor = self._calculate_my_factor()
    
    size = base_size * signal_strength * my_factor
    return int(size / self.contract_multiplier)
```

## Troubleshooting

### Performance Issues

1. **Slow API Responses**
   - Check cache hit rates
   - Verify connection pool health
   - Monitor rate limiting

2. **High Memory Usage**
   - Reduce cache sizes
   - Enable cache expiration
   - Check for memory leaks

3. **Database Bottlenecks**
   - Enable batch flushing
   - Use PostgreSQL for production
   - Add appropriate indexes

### Common Errors

1. **Connection Pool Timeout**
   - Increase pool size
   - Check for connection leaks
   - Monitor concurrent usage

2. **Rate Limiting**
   - Built-in protection should prevent
   - Reduce request frequency if needed
   - Check rate limit configuration

## Security Considerations

1. **API Credentials**
   - Never hardcode credentials
   - Use environment variables
   - Rotate keys regularly

2. **Network Security**
   - Use HTTPS for all API calls
   - Implement IP whitelisting
   - Monitor for unusual activity

3. **Code Security**
   - Regular dependency updates
   - Security scanning in CI/CD
   - Input validation on all data

## Support and Maintenance

- Keep dependencies updated
- Monitor Alpaca API changes
- Regular performance reviews
- Document all customizations

For setup instructions, see [SETUP_GUIDE.md](SETUP_GUIDE.md).