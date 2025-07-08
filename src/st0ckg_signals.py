"""
ST0CKG Signal Detection System
Implements all 6 signal types for Battle Lines strategy
"""
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import numpy as np

logger = logging.getLogger(__name__)


class ST0CKGSignalDetector:
    """Detects all 6 signal types for ST0CKG strategy"""
    
    def __init__(self, market_data):
        self.market_data = market_data
        self.signal_weights = {
            'GAMMA_SQUEEZE': 8.5,
            'VWAP_RECLAIM': 7.0,
            'OPENING_DRIVE': 7.5,
            'LIQUIDITY_VACUUM': 6.5,
            'OPTIONS_PIN': 6.0,
            'DARK_POOL_FLOW': 5.5
        }
        self._prefetched_option_chains = None
    
    def detect_all_signals(self, symbol: str, current_price: float, 
                          battle_lines: Dict[str, float], 
                          market_context: Dict) -> Dict[str, Dict]:
        """
        Detect all signal types and return scores
        Returns dict of signal_type -> {score, details, confidence}
        """
        # Use pre-fetched option chains if available
        if 'option_chains' in market_context and 'snapshot' in market_context['option_chains']:
            self._prefetched_option_chains = market_context['option_chains']['snapshot']
        
        signals = {}
        
        # 1. Gamma Squeeze Detection
        gamma_signal = self.detect_gamma_squeeze(symbol, current_price, market_context)
        if gamma_signal['score'] > 0:
            signals['GAMMA_SQUEEZE'] = gamma_signal
        
        # 2. VWAP Reclaim Detection
        vwap_signal = self.detect_vwap_reclaim(symbol, current_price, market_context)
        if vwap_signal['score'] > 0:
            signals['VWAP_RECLAIM'] = vwap_signal
        
        # 3. Opening Drive Detection
        opening_signal = self.detect_opening_drive(symbol, current_price, battle_lines, market_context)
        if opening_signal['score'] > 0:
            signals['OPENING_DRIVE'] = opening_signal
        
        # 4. Liquidity Vacuum Detection
        liquidity_signal = self.detect_liquidity_vacuum(symbol, current_price, market_context)
        if liquidity_signal['score'] > 0:
            signals['LIQUIDITY_VACUUM'] = liquidity_signal
        
        # 5. Options Pin Detection
        pin_signal = self.detect_options_pin(symbol, current_price, market_context)
        if pin_signal['score'] > 0:
            signals['OPTIONS_PIN'] = pin_signal
        
        # 6. Dark Pool Flow Detection
        dark_pool_signal = self.detect_dark_pool_flow(symbol, current_price, market_context)
        if dark_pool_signal['score'] > 0:
            signals['DARK_POOL_FLOW'] = dark_pool_signal
        
        return signals
    
    def detect_gamma_squeeze(self, symbol: str, current_price: float, 
                           context: Dict) -> Dict:
        """
        Detect market maker gamma positioning imbalances
        High OI near current price + rapid price movement = potential squeeze
        """
        try:
            score = 0.0
            details = []
            
            # Use pre-fetched options if available
            options = self._prefetched_option_chains
            
            if not options:
                # Skip option chain check if it might fail
                try:
                    options = self.market_data.get_option_chain_snapshot(
                        symbol, 
                        current_price - 5, 
                        current_price + 5
                    )
                except:
                    pass
                
            if options and len(options) > 0:
                # Quick gamma calculation without complex loops
                gamma_concentration = False
                for opt in options[:10]:  # Limit to first 10 for speed
                    if opt.get('strike') and abs(current_price - opt['strike']) < 1.0:
                        if opt.get('open_interest', 0) > 1000:
                            gamma_concentration = True
                            score += 4.0
                            details.append(f"High OI near ${opt['strike']}")
                            break
            
            # Price acceleration check (simpler)
            recent_bars = context.get('recent_bars', [])
            if len(recent_bars) >= 2:
                last_move = abs(recent_bars[-1].get('close', current_price) - 
                              recent_bars[-2].get('close', current_price))
                if last_move > 0.20:  # Big move
                    score += 3.0
                    details.append("Strong price movement")
            
            # Volume check
            if context.get('volume_ratio', 1.0) > 2.0:
                score += 1.5
                details.append(f"Volume: {context['volume_ratio']:.1f}x")
            
            confidence = 'HIGH' if score >= 6 else 'MEDIUM' if score >= 3 else 'LOW'
            
            return {
                'score': min(score, 8.5),
                'details': ', '.join(details) if details else 'No gamma squeeze',
                'confidence': confidence
            }
            
        except Exception as e:
            logger.error(f"Error in gamma squeeze detection: {e}")
            return {'score': 0, 'details': 'Detection error', 'confidence': 'LOW'}
    
    def detect_vwap_reclaim(self, symbol: str, current_price: float, 
                          context: Dict) -> Dict:
        """
        Detect VWAP reclaim patterns (mean reversion)
        Price rejected from VWAP and returning = high probability setup
        """
        try:
            score = 0.0
            details = []
            
            # Get VWAP from context or estimate
            vwap = context.get('vwap', 0)
            if not vwap:
                # Simple VWAP estimate - use opening price as proxy
                opening_range = context.get('opening_range', {})
                vwap = opening_range.get('open', current_price)
            
            # Check distance from VWAP
            vwap_distance = abs(current_price - vwap)
            
            # Simple VWAP reclaim logic
            if vwap_distance < 0.20:  # Near VWAP
                score += 4.0
                details.append(f"Near VWAP ${vwap:.2f}")
                
                # Check direction
                if current_price > vwap:
                    details.append("Above VWAP")
                else:
                    details.append("Below VWAP")
            
            # Volume confirmation
            if context.get('volume_ratio', 1.0) > 1.5:
                score += 2.0
                details.append("Volume confirmed")
            
            # Recent movement check
            recent_bars = context.get('recent_bars', [])
            if len(recent_bars) >= 2:
                if abs(recent_bars[-1].get('close', current_price) - vwap) < \
                   abs(recent_bars[-2].get('close', current_price) - vwap):
                    score += 1.0
                    details.append("Moving toward VWAP")
            
            confidence = 'HIGH' if score >= 5 else 'MEDIUM' if score >= 3 else 'LOW'
            
            return {
                'score': min(score, 7.0),
                'details': ', '.join(details) if details else 'No VWAP signal',
                'confidence': confidence
            }
            
        except Exception as e:
            logger.error(f"Error in VWAP detection: {e}")
            return {'score': 0, 'details': 'Detection error', 'confidence': 'LOW'}
    
    def detect_opening_drive(self, symbol: str, current_price: float, 
                           battle_lines: Dict[str, float], context: Dict) -> Dict:
        """
        Detect opening drive continuation patterns
        Strong directional move off the open that breaks key levels
        """
        try:
            score = 0.0
            details = []
            
            # Get opening range
            opening_range = context.get('opening_range', {})
            if not opening_range:
                return {'score': 0, 'details': 'No opening range data', 'confidence': 'LOW'}
            
            open_price = opening_range.get('open', 0)
            or_high = opening_range.get('high', 0)
            or_low = opening_range.get('low', 0)
            
            if not all([open_price, or_high, or_low]):
                return {'score': 0, 'details': 'Incomplete opening range', 'confidence': 'LOW'}
            
            # Check for directional move
            move_from_open = current_price - open_price
            move_pct = (move_from_open / open_price) * 100
            
            # Strong opening drive characteristics
            if abs(move_pct) > 0.20:  # 0.20% move
                score += 3.0
                direction = 'bullish' if move_from_open > 0 else 'bearish'
                details.append(f"Strong {direction} drive: {move_pct:.2f}%")
                
                # Check if we broke battle lines
                if move_from_open > 0:  # Bullish
                    if current_price > battle_lines['pdh']:
                        score += 2.5
                        details.append("Broke PDH")
                    elif current_price > battle_lines['premarket_high']:
                        score += 2.0
                        details.append("Broke pre-market high")
                else:  # Bearish
                    if current_price < battle_lines['pdl']:
                        score += 2.5
                        details.append("Broke PDL")
                    elif current_price < battle_lines['premarket_low']:
                        score += 2.0
                        details.append("Broke pre-market low")
            
            # Volume confirmation
            or_volume = context.get('opening_volume_ratio', 1.0)
            if or_volume > 2.0:
                score += 2.0
                details.append(f"High opening volume: {or_volume:.1f}x avg")
            
            confidence = 'HIGH' if score >= 6 else 'MEDIUM' if score >= 4 else 'LOW'
            
            return {
                'score': min(score, 7.5),
                'details': ', '.join(details) if details else 'No opening drive',
                'confidence': confidence,
                'move_from_open': move_from_open,
                'direction': 'bullish' if move_from_open > 0 else 'bearish'
            }
            
        except Exception as e:
            logger.error(f"Error detecting opening drive: {e}")
            return {'score': 0, 'details': f'Error: {str(e)}', 'confidence': 'LOW'}
    
    def detect_liquidity_vacuum(self, symbol: str, current_price: float, 
                              context: Dict) -> Dict:
        """
        Detect rapid moves through thin order books
        Large price move on relatively low volume = liquidity vacuum
        """
        try:
            score = 0.0
            details = []
            
            recent_bars = context.get('recent_bars', [])
            if len(recent_bars) < 3:
                return {'score': 0, 'details': 'Insufficient data', 'confidence': 'LOW'}
            
            # Calculate price velocity
            last_bar = recent_bars[-1]
            prev_bar = recent_bars[-2]
            
            price_change = abs(last_bar['close'] - prev_bar['close'])
            price_change_pct = (price_change / prev_bar['close']) * 100
            
            # Calculate volume efficiency (big move on small volume)
            volume_ratio = last_bar['volume'] / context.get('avg_volume', last_bar['volume'])
            
            # Liquidity vacuum: big move, low relative volume
            if price_change_pct > 0.15 and volume_ratio < 0.8:
                score += 4.0
                details.append(f"Rapid move {price_change_pct:.2f}% on low volume")
            
            # Check for gap
            gap = abs(last_bar['open'] - prev_bar['close'])
            if gap > 0.20:
                score += 2.0
                details.append(f"Gap ${gap:.2f}")
            
            # Check bid-ask spread widening
            spread_data = context.get('spread_widening', False)
            if spread_data:
                score += 0.5
                details.append("Spread widening")
            
            confidence = 'HIGH' if score >= 5 else 'MEDIUM' if score >= 3 else 'LOW'
            
            return {
                'score': min(score, 6.5),
                'details': ', '.join(details) if details else 'No liquidity vacuum',
                'confidence': confidence,
                'price_velocity': price_change_pct,
                'volume_efficiency': volume_ratio
            }
            
        except Exception as e:
            logger.error(f"Error detecting liquidity vacuum: {e}")
            return {'score': 0, 'details': f'Error: {str(e)}', 'confidence': 'LOW'}
    
    def detect_options_pin(self, symbol: str, current_price: float, 
                         context: Dict) -> Dict:
        """
        Detect price magnetization to high open interest strikes
        Price tends to gravitate toward high OI strikes near expiry
        """
        try:
            score = 0.0
            details = []
            
            # Use pre-fetched options if available
            options = self._prefetched_option_chains
            
            if not options:
                # Get nearby strikes with high OI
                try:
                    options = self.market_data.get_option_chain_snapshot(
                        symbol,
                        current_price - 3,
                        current_price + 3
                    )
                except:
                    pass
            
            if not options:
                return {'score': 0, 'details': 'No option data', 'confidence': 'LOW'}
            
            # Find max OI strikes
            max_oi_call_strike = None
            max_oi_put_strike = None
            max_call_oi = 0
            max_put_oi = 0
            
            for opt in options:
                oi = opt.get('open_interest', 0)
                if opt['option_type'] == 'CALL' and oi > max_call_oi:
                    max_call_oi = oi
                    max_oi_call_strike = opt['strike']
                elif opt['option_type'] == 'PUT' and oi > max_put_oi:
                    max_put_oi = oi
                    max_oi_put_strike = opt['strike']
            
            # Check for pin behavior
            pin_strike = None
            
            # Are we near a high OI strike?
            if max_oi_call_strike and abs(current_price - max_oi_call_strike) < 0.50:
                score += 3.0
                pin_strike = max_oi_call_strike
                details.append(f"Near max call OI at ${max_oi_call_strike}")
            
            if max_oi_put_strike and abs(current_price - max_oi_put_strike) < 0.50:
                score += 3.0
                if not pin_strike:
                    pin_strike = max_oi_put_strike
                details.append(f"Near max put OI at ${max_oi_put_strike}")
            
            # Check for price consolidation (pinning behavior)
            recent_bars = context.get('recent_bars', [])
            if len(recent_bars) >= 5 and pin_strike:
                # Calculate price range over last 5 bars
                high_5 = max([bar['high'] for bar in recent_bars[-5:]])
                low_5 = min([bar['low'] for bar in recent_bars[-5:]])
                range_5 = high_5 - low_5
                
                if range_5 < 0.50:  # Tight range
                    score += 1.0
                    details.append("Price consolidating")
            
            # Time decay factor (stronger pin closer to expiry)
            hours_to_expiry = context.get('hours_to_expiry', 24)
            if hours_to_expiry < 4:
                score *= 1.2
                details.append("Near expiry")
            
            confidence = 'HIGH' if score >= 4 else 'MEDIUM' if score >= 2 else 'LOW'
            
            return {
                'score': min(score, 6.0),
                'details': ', '.join(details) if details else 'No options pin',
                'confidence': confidence,
                'pin_strike': pin_strike,
                'max_call_oi': max_call_oi,
                'max_put_oi': max_put_oi
            }
            
        except Exception as e:
            logger.error(f"Error detecting options pin: {e}")
            return {'score': 0, 'details': f'Error: {str(e)}', 'confidence': 'LOW'}
    
    def detect_dark_pool_flow(self, symbol: str, current_price: float, 
                            context: Dict) -> Dict:
        """
        Detect institutional directional bias from dark pool activity
        Large trades at specific levels indicate institutional interest
        """
        try:
            score = 0.0
            details = []
            
            # Get recent large trades (this would need a data source)
            # For now, we'll use volume spikes as a proxy
            recent_bars = context.get('recent_bars', [])
            if len(recent_bars) < 10:
                return {'score': 0, 'details': 'Insufficient data', 'confidence': 'LOW'}
            
            # Look for volume spikes at specific price levels
            avg_volume = np.mean([bar['volume'] for bar in recent_bars[:-1]])
            
            # Identify potential dark pool prints
            dark_pool_levels = []
            
            for i, bar in enumerate(recent_bars):
                volume_spike = bar['volume'] / avg_volume if avg_volume > 0 else 0
                
                # Large volume spike at a price level
                if volume_spike > 3.0:
                    # Check if price didn't move much (characteristic of dark pool)
                    price_range = bar['high'] - bar['low']
                    if price_range < 0.20:
                        dark_pool_levels.append({
                            'price': bar['close'],
                            'volume': bar['volume'],
                            'spike': volume_spike
                        })
                        score += 2.0
            
            if dark_pool_levels:
                # Recent dark pool activity
                latest_level = dark_pool_levels[-1]
                details.append(f"Large print at ${latest_level['price']:.2f}")
                
                # Directional bias
                if current_price > latest_level['price']:
                    details.append("Bullish bias")
                else:
                    details.append("Bearish bias")
                
                # Multiple prints = stronger signal
                if len(dark_pool_levels) >= 2:
                    score += 1.5
                    details.append(f"{len(dark_pool_levels)} large prints")
            
            # Check for accumulation/distribution patterns
            volume_trend = context.get('volume_trend', 'neutral')
            if volume_trend == 'increasing':
                score += 1.0
                details.append("Volume accumulation")
            
            confidence = 'MEDIUM' if score >= 4 else 'LOW'
            
            return {
                'score': min(score, 5.5),
                'details': ', '.join(details) if details else 'No dark pool activity',
                'confidence': confidence,
                'dark_pool_levels': dark_pool_levels
            }
            
        except Exception as e:
            logger.error(f"Error detecting dark pool flow: {e}")
            return {'score': 0, 'details': f'Error: {str(e)}', 'confidence': 'LOW'}
    
    def calculate_composite_signal(self, signals: Dict[str, Dict]) -> Tuple[float, str]:
        """
        Calculate composite signal strength from all signals
        Returns (total_score, primary_signal_type)
        """
        if not signals:
            return 0.0, None
        
        total_score = 0.0
        primary_signal = None
        max_weighted_score = 0.0
        
        for signal_type, signal_data in signals.items():
            # Apply weight to score
            weight = self.signal_weights.get(signal_type, 1.0)
            weighted_score = signal_data['score'] * (weight / 10.0)
            total_score += weighted_score
            
            # Track strongest signal
            if weighted_score > max_weighted_score:
                max_weighted_score = weighted_score
                primary_signal = signal_type
        
        return total_score, primary_signal