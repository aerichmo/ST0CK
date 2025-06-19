import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import pytz
from typing import List, Dict, Tuple
import requests
from concurrent.futures import ThreadPoolExecutor
import logging

logger = logging.getLogger(__name__)

class MarketDataProvider:
    def __init__(self, config: dict):
        self.config = config
        self.timezone = config["session"]["timezone"]
        
    def get_pre_market_gappers(self) -> List[str]:
        """Find stocks gapping ≥±0.75% in pre-market with required liquidity"""
        try:
            gap_threshold = self.config["universe"]["pre_market_gap_threshold"]
            min_market_cap = self.config["universe"]["min_market_cap"]
            min_option_volume = self.config["universe"]["min_avg_option_volume"]
            
            scanners = ["pre_market_gainers", "pre_market_losers"]
            all_gappers = []
            
            for scanner in scanners:
                url = f"https://query1.finance.yahoo.com/v1/finance/screener/instrument/equity/fields?category=pre_market_mover&locale=en-US&quoteType=EQUITY&sortField=percentchange&sortType={'DESC' if 'gainers' in scanner else 'ASC'}&size=20"
                
                response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
                if response.status_code == 200:
                    data = response.json()
                    quotes = data.get('quotes', [])
                    
                    for quote in quotes:
                        symbol = quote.get('symbol')
                        pct_change = abs(quote.get('regularMarketChangePercent', 0) / 100)
                        market_cap = quote.get('marketCap', 0)
                        
                        if (pct_change >= gap_threshold and 
                            market_cap >= min_market_cap and
                            symbol not in all_gappers):
                            all_gappers.append(symbol)
            
            filtered_gappers = []
            with ThreadPoolExecutor(max_workers=10) as executor:
                results = executor.map(self._check_option_volume, all_gappers)
                for symbol, has_volume in zip(all_gappers, results):
                    if has_volume:
                        filtered_gappers.append(symbol)
            
            return filtered_gappers[:self.config["universe"]["max_additional_symbols"]]
            
        except Exception as e:
            logger.error(f"Error getting pre-market gappers: {e}")
            return []
    
    def _check_option_volume(self, symbol: str) -> bool:
        """Check if symbol has sufficient average option volume"""
        try:
            ticker = yf.Ticker(symbol)
            options_dates = ticker.options
            
            if not options_dates:
                return False
            
            total_volume = 0
            for exp_date in options_dates[:3]:
                opt_chain = ticker.option_chain(exp_date)
                total_volume += opt_chain.calls['volume'].sum()
                total_volume += opt_chain.puts['volume'].sum()
            
            avg_volume = total_volume / len(options_dates[:3]) if options_dates else 0
            return avg_volume >= self.config["universe"]["min_avg_option_volume"]
            
        except Exception:
            return False
    
    def get_5min_bars(self, symbol: str, lookback_days: int = 2) -> pd.DataFrame:
        """Get 5-minute bars for trend and volume analysis"""
        try:
            ticker = yf.Ticker(symbol)
            end_date = datetime.now(self.timezone)
            start_date = end_date - timedelta(days=lookback_days)
            
            data = ticker.history(
                start=start_date,
                end=end_date,
                interval="5m",
                prepost=True
            )
            
            if data.empty:
                return pd.DataFrame()
            
            data.index = data.index.tz_localize(pytz.UTC).tz_convert(self.timezone)
            
            data['ATR'] = self._calculate_atr(data, period=14)
            data['EMA_8'] = data['Close'].ewm(span=8, adjust=False).mean()
            data['EMA_21'] = data['Close'].ewm(span=21, adjust=False).mean()
            data['Volume_MA'] = data['Volume'].rolling(window=10).mean()
            
            return data
            
        except Exception as e:
            logger.error(f"Error getting 5min bars for {symbol}: {e}")
            return pd.DataFrame()
    
    def _calculate_atr(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
        """Calculate Average True Range"""
        high = df['High']
        low = df['Low']
        close = df['Close']
        
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=period).mean()
        
        return atr
    
    def get_opening_range(self, symbol: str, date: datetime) -> Tuple[float, float]:
        """Get opening range high and low for the first 10 minutes"""
        try:
            or_start = datetime.combine(
                date.date(),
                self.config["session"]["opening_range_start"],
                self.timezone
            )
            or_end = datetime.combine(
                date.date(),
                self.config["session"]["opening_range_end"],
                self.timezone
            )
            
            ticker = yf.Ticker(symbol)
            data = ticker.history(
                start=or_start,
                end=or_end,
                interval="1m"
            )
            
            if data.empty:
                return None, None
            
            orh = data['High'].max()
            orl = data['Low'].min()
            
            return orh, orl
            
        except Exception as e:
            logger.error(f"Error getting opening range for {symbol}: {e}")
            return None, None
    
    def get_current_quote(self, symbol: str) -> Dict:
        """Get current quote data"""
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info
            
            return {
                'symbol': symbol,
                'price': info.get('regularMarketPrice', 0),
                'volume': info.get('regularMarketVolume', 0),
                'bid': info.get('bid', 0),
                'ask': info.get('ask', 0),
                'timestamp': datetime.now(self.timezone)
            }
            
        except Exception as e:
            logger.error(f"Error getting quote for {symbol}: {e}")
            return {}