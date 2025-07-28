"""
ST0CK Enhanced Trading Strategy
Combines ST0CKA/G strategies with gamma scalping infrastructure
"""

import asyncio
import logging
from datetime import datetime, time
from typing import Optional, Dict, Any
import pytz

import config
from strategy.hedging_strategy import TradingStrategy, TradeCommand

logger = logging.getLogger(__name__)


class ST0CKEnhancedStrategy(TradingStrategy):
    """
    Enhanced ST0CK strategy that leverages gamma scalping infrastructure
    Supports multiple modes: ST0CKA, ST0CKG, and hybrid
    """
    
    def __init__(self, position_manager, delta_queue, trade_action_queue, shutdown_event):
        super().__init__(position_manager, delta_queue, trade_action_queue, shutdown_event)
        
        # Strategy configuration
        self.strategy_mode = config.STRATEGY_MODE
        self.strategy_config = config.get_active_config()
        
        # Market data
        self.current_price = None
        self.vwap = None
        self.volatility = None
        self.last_entry_time = None
        
        # Risk tracking
        self.daily_pnl = 0.0
        self.consecutive_losses = 0
        self.positions_today = 0
        
        # Timezone
        self.eastern = pytz.timezone('US/Eastern')
        
        logger.info(f"Initialized ST0CK Enhanced Strategy in {self.strategy_mode} mode")
    
    async def run(self):
        """Main strategy loop - adapted from gamma scalping"""
        logger.info(f"Starting ST0CK Enhanced Strategy loop in {self.strategy_mode} mode")
        
        while not self.shutdown_event.is_set():
            try:
                # Get market update (delta calculation in original)
                market_update = await asyncio.wait_for(
                    self.delta_queue.get(), 
                    timeout=config.HEARTBEAT_TRIGGER_SECONDS
                )
                
                # Extract market data
                self.current_price = market_update.get('underlying_price')
                self.vwap = market_update.get('vwap', self.current_price)
                self.volatility = market_update.get('volatility', 0.15)
                
                # Check if we should trade based on mode
                if self.strategy_mode == "st0cka":
                    await self._execute_st0cka_logic()
                elif self.strategy_mode == "st0ckg":
                    await self._execute_st0ckg_logic(market_update)
                elif self.strategy_mode == "hybrid":
                    await self._execute_hybrid_logic(market_update)
                else:
                    # Fall back to original gamma scalping
                    await self._execute_gamma_scalping(market_update)
                    
            except asyncio.TimeoutError:
                # No market update within heartbeat interval
                continue
            except Exception as e:
                logger.error(f"Error in strategy loop: {e}", exc_info=True)
                await asyncio.sleep(1)
    
    async def _execute_st0cka_logic(self):
        """Execute ST0CKA strategy with enhancements"""
        now = datetime.now(self.eastern)
        
        # Check if within trading window
        if not self._in_st0cka_buy_window(now):
            return
        
        # Check risk limits
        if not self._check_risk_limits():
            return
        
        # Calculate position size based on volatility
        position_size = self._calculate_st0cka_position_size()
        
        # Check for entry conditions
        if self._check_st0cka_entry_conditions():
            # Create trade command
            trade_command = TradeCommand(
                symbol=config.HEDGING_ASSET,
                quantity=position_size,
                multiplier=1,
                metadata={
                    "strategy": "st0cka_enhanced",
                    "volatility": self.volatility,
                    "profit_target": self._calculate_profit_target()
                }
            )
            
            # Send trade command
            try:
                await self.trade_action_queue.put(trade_command)
                self.last_entry_time = now
                self.positions_today += 1
                logger.info(f"ST0CKA entry signal: {position_size} shares at ${self.current_price:.2f}")
            except asyncio.QueueFull:
                logger.warning("Trade queue full, skipping trade")
    
    async def _execute_st0ckg_logic(self, market_update: Dict[str, Any]):
        """Execute ST0CKG strategy with gamma insights"""
        # This would integrate with existing ST0CKG signal detection
        # For now, simplified implementation
        
        signals = self._detect_st0ckg_signals(market_update)
        
        if signals:
            best_signal = max(signals.items(), key=lambda x: x[1]['score'])
            signal_type, signal_data = best_signal
            
            # Determine trade direction
            if signal_type in ['GAMMA_SQUEEZE', 'OPENING_DRIVE']:
                direction = 1 if signal_data.get('direction') == 'bullish' else -1
            else:
                direction = 0  # No trade
            
            if direction != 0:
                quantity = self._calculate_st0ckg_position_size(signal_data)
                
                trade_command = TradeCommand(
                    symbol=config.HEDGING_ASSET,
                    quantity=quantity * direction,
                    multiplier=1,
                    metadata={
                        "strategy": "st0ckg_enhanced",
                        "signal": signal_type,
                        "score": signal_data['score']
                    }
                )
                
                try:
                    await self.trade_action_queue.put(trade_command)
                    logger.info(f"ST0CKG signal: {signal_type} with score {signal_data['score']}")
                except asyncio.QueueFull:
                    logger.warning("Trade queue full, skipping trade")
    
    async def _execute_hybrid_logic(self, market_update: Dict[str, Any]):
        """Execute hybrid strategy based on market conditions"""
        # Use volatility to determine which strategy to use
        if self.volatility > config.HYBRID_CONFIG['volatility_threshold_for_gamma']:
            # High volatility - use gamma scalping approach
            await self._execute_gamma_scalping(market_update)
        else:
            # Low volatility - use ST0CKA approach
            await self._execute_st0cka_logic()
    
    async def _execute_gamma_scalping(self, market_update: Dict[str, Any]):
        """Fall back to original gamma scalping logic"""
        # Use parent class implementation
        await super()._make_trading_decision(market_update.get('portfolio_delta', 0))
    
    def _in_st0cka_buy_window(self, now: datetime) -> bool:
        """Check if within ST0CKA buy window"""
        start_time = datetime.strptime(self.strategy_config['buy_window_start'], '%H:%M').time()
        end_time = datetime.strptime(self.strategy_config['buy_window_end'], '%H:%M').time()
        
        current_time = now.time()
        return start_time <= current_time <= end_time
    
    def _check_risk_limits(self) -> bool:
        """Check if risk limits allow trading"""
        risk_config = config.RISK_MANAGEMENT
        
        # Daily loss limit
        if self.daily_pnl <= risk_config['max_daily_loss']:
            logger.warning(f"Daily loss limit reached: ${self.daily_pnl:.2f}")
            return False
        
        # Consecutive losses
        if self.consecutive_losses >= risk_config['max_consecutive_losses']:
            logger.warning(f"Consecutive loss limit reached: {self.consecutive_losses}")
            return False
        
        return True
    
    def _calculate_st0cka_position_size(self) -> int:
        """Calculate position size based on volatility"""
        if not self.strategy_config['use_volatility_sizing']:
            return self.strategy_config['position_size_min']
        
        # Volatility-based sizing
        vol_config = config.VOLATILITY_CONFIG
        
        if self.volatility < vol_config['low_vol_threshold']:
            return self.strategy_config['position_size_max']
        elif self.volatility > vol_config['high_vol_threshold']:
            return self.strategy_config['position_size_min']
        else:
            # Linear interpolation
            vol_range = vol_config['high_vol_threshold'] - vol_config['low_vol_threshold']
            vol_normalized = (self.volatility - vol_config['low_vol_threshold']) / vol_range
            
            size_range = self.strategy_config['position_size_max'] - self.strategy_config['position_size_min']
            position_size = self.strategy_config['position_size_max'] - (vol_normalized * size_range)
            
            return max(1, int(position_size))
    
    def _check_st0cka_entry_conditions(self) -> bool:
        """Check ST0CKA entry conditions"""
        # Basic price check
        if self.current_price is None:
            return False
        
        # Check entry interval
        if self.last_entry_time:
            seconds_since_last = (datetime.now(self.eastern) - self.last_entry_time).total_seconds()
            if seconds_since_last < self.strategy_config['entry_interval_seconds']:
                return False
        
        # Mean reversion check if enabled
        if self.strategy_config['use_mean_reversion']:
            deviation = abs(self.current_price - self.vwap) / self.vwap
            if deviation < config.MEAN_REVERSION_CONFIG['vwap_deviation_threshold']:
                return False
        
        return True
    
    def _calculate_profit_target(self) -> float:
        """Calculate dynamic profit target based on volatility"""
        base_target = self.strategy_config['profit_target']
        
        if self.strategy_config['use_volatility_sizing']:
            # Scale target with volatility
            vol_multiplier = self.volatility / 0.15  # Assuming 15% is normal
            return base_target * max(1, vol_multiplier)
        
        return base_target
    
    def _detect_st0ckg_signals(self, market_update: Dict[str, Any]) -> Dict[str, Dict]:
        """Detect ST0CKG signals including gamma-based ones"""
        signals = {}
        
        # Simplified signal detection - in production would use full ST0CKG logic
        
        # Gamma signal from the delta engine
        portfolio_delta = market_update.get('portfolio_delta', 0)
        if abs(portfolio_delta) > 5:  # Significant gamma exposure
            signals['DEALER_GAMMA'] = {
                'score': config.ST0CKG_CONFIG['signal_weights']['DEALER_GAMMA'],
                'direction': 'bearish' if portfolio_delta > 0 else 'bullish',
                'details': f"Dealer gamma imbalance: {portfolio_delta:.1f}"
            }
        
        # VWAP reclaim signal
        if self.vwap and self.current_price:
            deviation = (self.current_price - self.vwap) / self.vwap
            if abs(deviation) > 0.002 and abs(deviation) < 0.005:
                signals['VWAP_RECLAIM'] = {
                    'score': config.ST0CKG_CONFIG['signal_weights']['VWAP_RECLAIM'],
                    'direction': 'bearish' if deviation > 0 else 'bullish',
                    'details': f"VWAP deviation: {deviation:.3%}"
                }
        
        return signals
    
    def _calculate_st0ckg_position_size(self, signal_data: Dict) -> int:
        """Calculate position size for ST0CKG trades"""
        # Simplified - in production would use full risk management
        account_value = self.position_manager.account_cash
        risk_amount = account_value * config.ST0CKG_CONFIG['risk_per_trade']
        
        # For stocks (not options yet)
        position_value = risk_amount / 0.10  # Assume $0.10 stop loss
        shares = int(position_value / self.current_price)
        
        return max(1, min(shares, 100))  # Cap at 100 shares
    
    async def update_pnl(self, trade_result: Dict):
        """Update P&L tracking"""
        pnl = trade_result.get('pnl', 0)
        self.daily_pnl += pnl
        
        if pnl < 0:
            self.consecutive_losses += 1
        else:
            self.consecutive_losses = 0
        
        logger.info(f"Trade result: ${pnl:.2f}, Daily P&L: ${self.daily_pnl:.2f}")


class VolatilityTracker:
    """Track and calculate volatility metrics"""
    
    def __init__(self, lookback_period: int = 20):
        self.lookback_period = lookback_period
        self.price_history = []
        self.last_volatility = 0.15  # Default 15%
    
    def update(self, price: float) -> float:
        """Update price history and calculate volatility"""
        self.price_history.append(price)
        
        # Keep only lookback period
        if len(self.price_history) > self.lookback_period:
            self.price_history.pop(0)
        
        # Calculate realized volatility
        if len(self.price_history) >= 2:
            returns = []
            for i in range(1, len(self.price_history)):
                ret = (self.price_history[i] - self.price_history[i-1]) / self.price_history[i-1]
                returns.append(ret)
            
            if returns:
                import numpy as np
                volatility = np.std(returns) * np.sqrt(252)  # Annualized
                self.last_volatility = volatility
        
        return self.last_volatility