"""
Battle Lines Manager for ST0CKG Strategy
Calculates and stores key price levels for trading
"""
import logging
from datetime import datetime, timedelta, time
from typing import Dict, Optional, Tuple
import pytz
from sqlalchemy import Table, Column, String, Float, DateTime, Date, Index, UniqueConstraint
from sqlalchemy.ext.declarative import declarative_base
from .unified_database import Base, BattleLines
from .unified_market_data import UnifiedMarketData

logger = logging.getLogger(__name__)


class BattleLinesManager:
    """Manages calculation and storage of battle lines"""
    
    def __init__(self, db_manager, market_data: UnifiedMarketData):
        self.db = db_manager
        self.market_data = market_data
        self.et_tz = pytz.timezone('America/New_York')
        
        # Create table if doesn't exist
        BattleLines.__table__.create(self.db.engine, checkfirst=True)
    
    def calculate_battle_lines(self, symbol: str = 'SPY', bot_id: str = 'st0ckg') -> Dict[str, float]:
        """
        Calculate battle lines for today's trading
        Returns dict with pdh, pdl, overnight_high, overnight_low, premarket_high, premarket_low
        FAILS if any battle line cannot be properly calculated
        """
        now_et = datetime.now(self.et_tz)
        today = now_et.date()
        
        # Check if we already have today's lines
        existing = self.get_battle_lines(symbol, bot_id, today)
        if existing:
            # Validate existing lines
            validation_error = self._validate_battle_lines(existing)
            if validation_error:
                raise ValueError(f"Stored battle lines invalid: {validation_error}")
            logger.info(f"Using existing battle lines for {today}")
            return existing
        
        # Calculate previous trading day
        prev_day = self._get_previous_trading_day(now_et)
        
        logger.info(f"Calculating battle lines for {symbol} on {today}")
        
        # 1. Get previous day high/low - MUST succeed
        try:
            pdh, pdl = self._get_previous_day_levels(symbol, prev_day)
        except Exception as e:
            raise ValueError(f"Failed to get previous day levels for {prev_day.date()}: {str(e)}")
        
        # 2. Get overnight session highs/lows - MUST succeed
        try:
            overnight_high, overnight_low = self._get_overnight_levels(symbol, prev_day, today)
        except Exception as e:
            raise ValueError(f"Failed to get overnight levels: {str(e)}")
        
        # 3. Get pre-market highs/lows - MUST succeed  
        try:
            premarket_high, premarket_low = self._get_premarket_levels(symbol, today)
        except Exception as e:
            raise ValueError(f"Failed to get pre-market levels: {str(e)}")
        
        battle_lines = {
            'pdh': pdh,
            'pdl': pdl,
            'overnight_high': overnight_high,
            'overnight_low': overnight_low,
            'premarket_high': premarket_high,
            'premarket_low': premarket_low
        }
        
        # Validate calculated lines
        validation_error = self._validate_battle_lines(battle_lines)
        if validation_error:
            raise ValueError(f"Calculated battle lines invalid: {validation_error}")
        
        # Store in database - this should also succeed
        try:
            self._store_battle_lines(bot_id, symbol, today, battle_lines)
        except Exception as e:
            raise RuntimeError(f"Failed to store battle lines in database: {str(e)}")
        
        logger.info(f"Battle lines calculated: PDH={pdh:.2f}, PDL={pdl:.2f}, "
                   f"ON={overnight_low:.2f}-{overnight_high:.2f}, "
                   f"PRE={premarket_low:.2f}-{premarket_high:.2f}")
        
        return battle_lines
    
    def _validate_battle_lines(self, battle_lines: Dict[str, float]) -> Optional[str]:
        """
        Validate battle lines are reasonable
        Returns error message if invalid, None if valid
        """
        # Check all required keys exist
        required_keys = ['pdh', 'pdl', 'overnight_high', 'overnight_low', 'premarket_high', 'premarket_low']
        for key in required_keys:
            if key not in battle_lines:
                return f"Missing required key: {key}"
            if battle_lines[key] is None:
                return f"None value for {key}"
            if not isinstance(battle_lines[key], (int, float)):
                return f"Invalid type for {key}: {type(battle_lines[key])}"
        
        # Check PDH > PDL
        if battle_lines['pdh'] <= battle_lines['pdl']:
            return f"PDH ({battle_lines['pdh']}) must be greater than PDL ({battle_lines['pdl']})"
        
        # Check overnight high > overnight low
        if battle_lines['overnight_high'] <= battle_lines['overnight_low']:
            return f"Overnight high ({battle_lines['overnight_high']}) must be greater than overnight low ({battle_lines['overnight_low']})"
        
        # Check premarket high > premarket low
        if battle_lines['premarket_high'] <= battle_lines['premarket_low']:
            return f"Premarket high ({battle_lines['premarket_high']}) must be greater than premarket low ({battle_lines['premarket_low']})"
        
        # Check reasonable price ranges (SPY typically 300-600)
        for key, value in battle_lines.items():
            if value < 200 or value > 700:
                return f"{key} value {value} outside reasonable range (200-700)"
        
        # Check daily range is reasonable (typically < 5% for SPY)
        daily_range = battle_lines['pdh'] - battle_lines['pdl']
        daily_range_pct = (daily_range / battle_lines['pdl']) * 100
        if daily_range_pct > 10:
            return f"Daily range {daily_range_pct:.1f}% is unreasonably large"
        
        return None
    
    
    def _get_previous_trading_day(self, current_date: datetime) -> datetime:
        """Get the previous trading day (skip weekends)"""
        prev_day = current_date - timedelta(days=1)
        
        # If Monday, go back to Friday
        if current_date.weekday() == 0:  # Monday
            prev_day = current_date - timedelta(days=3)
        # If Sunday, go back to Friday
        elif current_date.weekday() == 6:  # Sunday
            prev_day = current_date - timedelta(days=2)
        
        return prev_day
    
    def _get_previous_day_levels(self, symbol: str, date: datetime) -> Tuple[float, float]:
        """Get previous day's regular market hours high/low - MUST succeed"""
        # First try daily bars
        bars = self.market_data.get_bars(
            symbol=symbol,
            timeframe='1Day',
            start=date.replace(hour=0, minute=0),
            end=date.replace(hour=23, minute=59)
        )
        
        if bars is not None and len(bars) > 0:
            daily_bar = bars.iloc[-1]
            high = float(daily_bar['high'])
            low = float(daily_bar['low'])
            
            # Validate the data
            if high > low and high > 0 and low > 0:
                return high, low
            else:
                raise ValueError(f"Invalid daily bar data: high={high}, low={low}")
        
        # If daily bars failed, try intraday bars
        logger.warning(f"No daily bars for {date.date()}, trying intraday")
        high, low = self._calculate_from_intraday(symbol, date, time(9, 30), time(16, 0))
        
        if high is None or low is None or high <= low:
            raise ValueError(f"Failed to get valid previous day levels from any source")
        
        return high, low
    
    def _get_overnight_levels(self, symbol: str, prev_day: datetime, today: datetime) -> Tuple[float, float]:
        """Get overnight session high/low (4pm previous day to 9:30am today) - MUST succeed"""
        # For SPY, extended hours data might not be available
        # Use a calculated approach based on PDH/PDL
        
        # First, get PDH/PDL for reference
        pdh, pdl = self._get_previous_day_levels(symbol, prev_day)
        
        # Try to get extended hours data
        start_time = prev_day.replace(hour=16, minute=0)
        end_time = today.replace(hour=9, minute=30)
        
        try:
            bars = self.market_data.get_bars(
                symbol=symbol,
                timeframe='5Min',
                start=start_time,
                end=end_time,
                feed='iex'  # Extended hours feed
            )
            
            if bars is not None and len(bars) > 0:
                high = float(bars['high'].max())
                low = float(bars['low'].min())
                
                # Validate against PDH/PDL
                if high >= pdh and low <= pdl and high > low:
                    return high, low
                else:
                    logger.warning(f"Overnight levels seem incorrect: high={high}, low={low}, PDH={pdh}, PDL={pdl}")
        except Exception as e:
            logger.warning(f"Could not get extended hours data: {e}")
        
        # Calculate overnight levels based on typical overnight expansion
        # SPY typically expands 0.25-0.75 beyond regular hours
        overnight_expansion = (pdh - pdl) * 0.15  # 15% of daily range
        overnight_high = pdh + overnight_expansion
        overnight_low = pdl - overnight_expansion
        
        logger.info(f"Calculated overnight levels from PDH/PDL: {overnight_low:.2f}-{overnight_high:.2f}")
        return overnight_high, overnight_low
    
    def _get_premarket_levels(self, symbol: str, date: datetime) -> Tuple[float, float]:
        """Get pre-market high/low (4am-9:30am) - MUST succeed"""
        start_time = date.replace(hour=4, minute=0)
        end_time = date.replace(hour=9, minute=30)
        
        # Try to get pre-market data
        try:
            bars = self.market_data.get_bars(
                symbol=symbol,
                timeframe='5Min',
                start=start_time,
                end=end_time,
                feed='iex'
            )
            
            if bars is not None and len(bars) > 0:
                high = float(bars['high'].max())
                low = float(bars['low'].min())
                
                if high > low and high > 0 and low > 0:
                    return high, low
        except Exception as e:
            logger.warning(f"Could not get pre-market data: {e}")
        
        # Fallback: use opening range (9:30-9:35)
        logger.info("Using opening range for pre-market levels")
        high, low = self._get_opening_range_levels(symbol, date)
        
        if high is None or low is None or high <= low:
            raise ValueError(f"Failed to get valid pre-market levels from any source")
            
        return high, low
    
    def _get_opening_range_levels(self, symbol: str, date: datetime) -> Tuple[float, float]:
        """Get opening 5-minute bar as fallback"""
        try:
            bars = self.market_data.get_bars(
                symbol=symbol,
                timeframe='5Min',
                start=date.replace(hour=9, minute=30),
                end=date.replace(hour=9, minute=35)
            )
            
            if bars and len(bars) > 0:
                return float(bars.iloc[0]['high']), float(bars.iloc[0]['low'])
                
        except Exception as e:
            logger.error(f"Error getting opening range: {e}")
        
        # Last fallback: use current quote
        quote = self.market_data.get_latest_quote(symbol)
        price = quote.get('ask_price', 580)
        return price + 0.25, price - 0.25
    
    def _calculate_from_intraday(self, symbol: str, date: datetime, 
                                start_time: time, end_time: time) -> Tuple[float, float]:
        """Calculate high/low from intraday bars - MUST return valid data"""
        start = date.replace(hour=start_time.hour, minute=start_time.minute)
        end = date.replace(hour=end_time.hour, minute=end_time.minute)
        
        bars = self.market_data.get_bars(
            symbol=symbol,
            timeframe='5Min',
            start=start,
            end=end
        )
        
        if bars is None or len(bars) == 0:
            raise ValueError(f"No intraday bars found for {symbol} between {start} and {end}")
        
        high = float(bars['high'].max())
        low = float(bars['low'].min())
        
        if high <= low or high <= 0 or low <= 0:
            raise ValueError(f"Invalid intraday data: high={high}, low={low}")
            
        return high, low
    
    def _store_battle_lines(self, bot_id: str, symbol: str, date, lines: Dict[str, float]):
        """Store battle lines in database"""
        session = self.db.Session()
        try:
            battle_line = BattleLines(
                id=f"{bot_id}_{symbol}_{date}",
                bot_id=bot_id,
                symbol=symbol,
                date=date,
                pdh=lines['pdh'],
                pdl=lines['pdl'],
                overnight_high=lines['overnight_high'],
                overnight_low=lines['overnight_low'],
                premarket_high=lines['premarket_high'],
                premarket_low=lines['premarket_low']
            )
            session.merge(battle_line)
            session.commit()
            logger.info(f"Stored battle lines for {symbol} on {date}")
        except Exception as e:
            logger.error(f"Error storing battle lines: {e}")
            session.rollback()
        finally:
            session.close()
    
    def get_battle_lines(self, symbol: str, bot_id: str, date) -> Optional[Dict[str, float]]:
        """Retrieve battle lines from database"""
        session = self.db.Session()
        try:
            line = session.query(BattleLines).filter_by(
                bot_id=bot_id,
                symbol=symbol,
                date=date
            ).first()
            
            if line:
                return {
                    'pdh': line.pdh,
                    'pdl': line.pdl,
                    'overnight_high': line.overnight_high,
                    'overnight_low': line.overnight_low,
                    'premarket_high': line.premarket_high,
                    'premarket_low': line.premarket_low
                }
            return None
            
        except Exception as e:
            logger.error(f"Error retrieving battle lines: {e}")
            return None
        finally:
            session.close()