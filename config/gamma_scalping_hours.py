"""
Optimal Trading Hours Configuration for Gamma Scalping
Based on intraday volatility patterns and market microstructure research
"""

from dataclasses import dataclass
from typing import Dict, List, Tuple
from datetime import time

@dataclass
class TradingSession:
    """Defines a trading session with specific characteristics"""
    name: str
    start_time: str  # HH:MM format in ET
    end_time: str    # HH:MM format in ET
    target_delta: float
    volatility_rank: str  # HIGH, MEDIUM, LOW
    description: str
    
    
# Optimal gamma scalping sessions based on volatility patterns
GAMMA_SCALPING_SESSIONS = {
    "opening_drive": TradingSession(
        name="Opening Drive",
        start_time="09:30",
        end_time="11:00",
        target_delta=0.45,
        volatility_rank="HIGH",
        description="Highest intraday volatility, large price swings, maximum gamma opportunities"
    ),
    
    "late_morning": TradingSession(
        name="Late Morning Reversal",
        start_time="11:00",
        end_time="11:30",
        target_delta=0.40,
        volatility_rank="MEDIUM",
        description="Momentum exhaustion, good for mean reversion gamma trades"
    ),
    
    "lunch_lull": TradingSession(
        name="Lunch Hour",
        start_time="11:30",
        end_time="13:00",
        target_delta=0.35,
        volatility_rank="LOW",
        description="Lower volume but sharp moves possible, less institutional competition"
    ),
    
    "midday_avoid": TradingSession(
        name="Mid-Day Dead Zone",
        start_time="13:00",
        end_time="14:30",
        target_delta=0.30,
        volatility_rank="VERY_LOW",
        description="AVOID - Lowest volatility, theta decay dominates gamma gains"
    ),
    
    "fed_time": TradingSession(
        name="Fed Announcement Window",
        start_time="13:45",
        end_time="14:15",
        target_delta=0.50,
        volatility_rank="EXTREME",
        description="Only on Fed days - extreme volatility around 2:00 PM announcements"
    ),
    
    "pre_power": TradingSession(
        name="Pre-Power Hour Setup",
        start_time="14:30",
        end_time="15:00",
        target_delta=0.40,
        volatility_rank="MEDIUM",
        description="Positioning before final hour, volatility starts to pick up"
    ),
    
    "power_hour": TradingSession(
        name="Power Hour",
        start_time="15:00",
        end_time="15:45",
        target_delta=0.50,
        volatility_rank="HIGH",
        description="Second volatility spike, position squaring, 0-DTE gamma explosion"
    ),
    
    "closing_rush": TradingSession(
        name="Closing Rush",
        start_time="15:45",
        end_time="16:00",
        target_delta=0.45,
        volatility_rank="HIGH",
        description="Final positioning, MOC orders, high gamma for 0-DTE"
    )
}


# Recommended sessions for different gamma scalping strategies
STRATEGY_RECOMMENDATIONS = {
    "aggressive_0dte": ["opening_drive", "power_hour", "closing_rush"],
    "standard_gamma": ["opening_drive", "late_morning", "power_hour"],
    "mean_reversion": ["late_morning", "lunch_lull", "pre_power"],
    "fed_days": ["opening_drive", "fed_time", "power_hour"],
    "conservative": ["opening_drive", "power_hour"]
}


# Options order cutoff times (CRITICAL for risk management)
ORDER_CUTOFFS = {
    "standard_options": "15:15",  # 3:15 PM ET for regular options
    "spy_qqq_options": "15:30",   # 3:30 PM ET for SPY/QQQ
    "0dte_emergency": "15:45",    # Emergency exit time for 0-DTE
}


# Volatility expectations by time of day (for position sizing)
INTRADAY_VOLATILITY_MULTIPLIERS = {
    "09:30-10:00": 1.5,   # 50% higher volatility than daily average
    "10:00-10:30": 1.3,   # 30% higher
    "10:30-11:00": 1.2,   # 20% higher
    "11:00-11:30": 1.1,   # 10% higher
    "11:30-12:00": 0.9,   # 10% lower
    "12:00-13:00": 0.7,   # 30% lower (lunch)
    "13:00-14:00": 0.6,   # 40% lower (dead zone)
    "14:00-14:30": 0.8,   # 20% lower
    "14:30-15:00": 1.0,   # Average
    "15:00-15:30": 1.3,   # 30% higher
    "15:30-16:00": 1.4,   # 40% higher
}


def get_optimal_sessions(strategy_type: str = "standard_gamma") -> List[TradingSession]:
    """Get recommended trading sessions for a strategy type"""
    session_names = STRATEGY_RECOMMENDATIONS.get(strategy_type, ["opening_drive", "power_hour"])
    return [GAMMA_SCALPING_SESSIONS[name] for name in session_names if name in GAMMA_SCALPING_SESSIONS]


def get_current_volatility_multiplier(current_time: str) -> float:
    """Get expected volatility multiplier for current time"""
    # Convert time to find matching period
    for time_range, multiplier in INTRADAY_VOLATILITY_MULTIPLIERS.items():
        start, end = time_range.split("-")
        if start <= current_time <= end:
            return multiplier
    return 1.0  # Default multiplier


def should_trade_gamma(current_time: str, min_volatility_rank: str = "MEDIUM") -> bool:
    """Determine if current time is suitable for gamma scalping"""
    volatility_ranks = ["VERY_LOW", "LOW", "MEDIUM", "HIGH", "EXTREME"]
    min_rank_index = volatility_ranks.index(min_volatility_rank)
    
    for session in GAMMA_SCALPING_SESSIONS.values():
        if session.start_time <= current_time <= session.end_time:
            session_rank_index = volatility_ranks.index(session.volatility_rank)
            return session_rank_index >= min_rank_index
    
    return False


# Special calendar considerations
ENHANCED_VOLATILITY_DAYS = {
    "fomc_days": "Fed announcement days - trade fed_time session",
    "opex_friday": "Monthly options expiration - higher gamma all day",
    "quarter_end": "Quarter-end rebalancing - power hour enhanced",
    "half_days": "Holiday half days - compress to morning only",
    "earnings_season": "Add 20% to all volatility multipliers"
}