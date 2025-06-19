import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import pytz
from typing import List, Dict, Tuple, Optional
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging
import time
from functools import wraps
from collections import defaultdict

logger = logging.getLogger(__name__)

def retry_on_failure(max_retries: int = 3, delay: float = 1.0):
    """Decorator to retry failed API calls"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_retries - 1:
                        logger.error(f"{func.__name__} failed after {max_retries} attempts: {e}")
                        raise
                    logger.warning(f"{func.__name__} attempt {attempt + 1} failed, retrying in {delay}s...")
                    time.sleep(delay)
            return None
        return wrapper
    return decorator

class MarketDataProvider:
    def __init__(self, config: dict):
        self.config = config
        self.timezone = config["session"]["timezone"]
        self._cache = defaultdict(dict)
        self._cache_ttl = 60  # Cache TTL in seconds
        
    def get_pre_market_gappers(self) -> List[str]:
        """Find stocks gapping ≥±0.75% in pre-market with required liquidity"""
        try:
            # Try primary method
            gappers = self._get_gappers_yahoo()
            if gappers:
                return gappers
            
            # Fallback to alternative scanner
            logger.warning("Primary gapper scanner failed, using fallback method")
            return self._get_gappers_fallback()
            
        except Exception as e:
            logger.error(f"All gapper scanners failed: {e}")
            return []
    
    def _get_gappers_yahoo(self) -> List[str]:
        """Primary method using Yahoo Finance scanner"""
        try:
            gap_threshold = self.config["universe"]["pre_market_gap_threshold"]
            min_market_cap = self.config["universe"]["min_market_cap"]
            
            scanners = ["pre_market_gainers", "pre_market_losers"]
            all_gappers = []
            
            for scanner in scanners:
                url = f"https://query1.finance.yahoo.com/v1/finance/screener/instrument/equity/fields?category=pre_market_mover&locale=en-US&quoteType=EQUITY&sortField=percentchange&sortType={'DESC' if 'gainers' in scanner else 'ASC'}&size=20"
                
                response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
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
            
            # Filter by option volume in parallel
            filtered_gappers = self._filter_by_option_volume(all_gappers)
            return filtered_gappers[:self.config["universe"]["max_additional_symbols"]]
            
        except Exception as e:
            logger.error(f"Yahoo gapper scanner error: {e}")
            return []
    
    def _get_gappers_fallback(self) -> List[str]:
        """Fallback method using direct ticker scanning"""
        try:
            # Common high-volume stocks to check
            candidates = ['AAPL', 'MSFT', 'AMZN', 'GOOGL', 'META', 'TSLA', 'NVDA', 
                         'AMD', 'NFLX', 'BABA', 'DIS', 'BA', 'JPM', 'GS', 'WMT']
            
            gap_threshold = self.config["universe"]["pre_market_gap_threshold"]
            gappers = []
            
            with ThreadPoolExecutor(max_workers=15) as executor:
                futures = {executor.submit(self._check_gap, symbol): symbol 
                          for symbol in candidates}
                
                for future in as_completed(futures):
                    symbol = futures[future]
                    try:
                        gap_pct = future.result()
                        if gap_pct and abs(gap_pct) >= gap_threshold:
                            gappers.append((symbol, abs(gap_pct)))
                    except Exception as e:
                        logger.debug(f"Failed to check gap for {symbol}: {e}")
            
            # Sort by gap percentage and return top symbols
            gappers.sort(key=lambda x: x[1], reverse=True)
            symbols = [g[0] for g in gappers]
            
            # Filter by option volume
            filtered = self._filter_by_option_volume(symbols)
            return filtered[:self.config["universe"]["max_additional_symbols"]]
            
        except Exception as e:
            logger.error(f"Fallback gapper scanner error: {e}")
            return []
    
    def _check_gap(self, symbol: str) -> Optional[float]:
        """Check if symbol is gapping"""
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info
            
            prev_close = info.get('previousClose', 0)
            current = info.get('regularMarketPrice', 0)
            
            if prev_close and current:
                return (current - prev_close) / prev_close
            return None
            
        except Exception:
            return None
    
    def _filter_by_option_volume(self, symbols: List[str]) -> List[str]:
        """Filter symbols by option volume in parallel"""
        filtered = []
        
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = {executor.submit(self._check_option_volume, symbol): symbol 
                      for symbol in symbols}
            
            for future in as_completed(futures):
                symbol = futures[future]
                try:
                    if future.result():
                        filtered.append(symbol)
                except Exception as e:
                    logger.debug(f"Option volume check failed for {symbol}: {e}")
        
        return filtered
    
    def _check_option_volume(self, symbol: str) -> bool:
        """Check if symbol has sufficient average option volume"""
        try:
            # Check cache first
            cache_key = f"option_volume_{symbol}"
            if cache_key in self._cache:
                cached_time, cached_result = self._cache[cache_key]
                if time.time() - cached_time < self._cache_ttl:
                    return cached_result
            
            ticker = yf.Ticker(symbol)
            options_dates = ticker.options
            
            if not options_dates:
                self._cache[cache_key] = (time.time(), False)
                return False
            
            total_volume = 0
            dates_to_check = min(3, len(options_dates))
            
            for i in range(dates_to_check):
                opt_chain = ticker.option_chain(options_dates[i])
                total_volume += opt_chain.calls['volume'].fillna(0).sum()
                total_volume += opt_chain.puts['volume'].fillna(0).sum()
            
            avg_volume = total_volume / dates_to_check if dates_to_check > 0 else 0
            result = avg_volume >= self.config["universe"]["min_avg_option_volume"]
            
            # Cache result
            self._cache[cache_key] = (time.time(), result)
            return result
            
        except Exception as e:
            logger.debug(f"Option volume check error for {symbol}: {e}")
            return False
    
    @retry_on_failure(max_retries=3, delay=0.5)
    def get_5min_bars(self, symbol: str, lookback_days: int = 2) -> pd.DataFrame:
        """Get 5-minute bars for trend and volume analysis with retry logic"""
        ticker = yf.Ticker(symbol)
        end_date = datetime.now(self.timezone)
        start_date = end_date - timedelta(days=lookback_days)
        
        data = ticker.history(
            start=start_date,
            end=end_date,
            interval="5m",
            prepost=True,
            actions=False,
            auto_adjust=True,
            back_adjust=False,
            progress=False
        )
        
        if data.empty:
            # Try alternative interval as fallback
            logger.warning(f"No 5m data for {symbol}, trying 2m interval")
            data = ticker.history(
                start=start_date,
                end=end_date,
                interval="2m",
                prepost=True,
                actions=False,
                progress=False
            )
            
            if not data.empty:
                # Resample to 5m
                data = data.resample('5T').agg({
                    'Open': 'first',
                    'High': 'max',
                    'Low': 'min',
                    'Close': 'last',
                    'Volume': 'sum'
                }).dropna()
        
        if data.empty:
            logger.error(f"No data available for {symbol}")
            return pd.DataFrame()
        
        # Ensure timezone
        if data.index.tz is None:
            data.index = data.index.tz_localize(pytz.UTC)
        data.index = data.index.tz_convert(self.timezone)
        
        # Calculate indicators
        data['ATR'] = self._calculate_atr(data, period=14)
        data['EMA_8'] = data['Close'].ewm(span=8, adjust=False).mean()
        data['EMA_21'] = data['Close'].ewm(span=21, adjust=False).mean()
        data['Volume_MA'] = data['Volume'].rolling(window=10).mean()
        
        return data
    
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
    
    @retry_on_failure(max_retries=2, delay=0.5)
    def get_opening_range(self, symbol: str, date: datetime) -> Tuple[float, float]:
        """Get opening range high and low for the first 10 minutes"""
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
            interval="1m",
            progress=False
        )
        
        if data.empty:
            # Fallback to 2m data
            data = ticker.history(
                start=or_start,
                end=or_end,
                interval="2m",
                progress=False
            )
        
        if data.empty:
            logger.error(f"No opening range data for {symbol}")
            return None, None
        
        orh = data['High'].max()
        orl = data['Low'].min()
        
        return orh, orl
    
    @retry_on_failure(max_retries=2, delay=0.3)
    def get_current_quote(self, symbol: str) -> Dict:
        """Get current quote data with caching"""
        # Check cache
        cache_key = f"quote_{symbol}"
        if cache_key in self._cache:
            cached_time, cached_data = self._cache[cache_key]
            if time.time() - cached_time < 5:  # 5 second cache for quotes
                return cached_data
        
        ticker = yf.Ticker(symbol)
        info = ticker.info
        
        # Try fast_info as fallback
        if not info.get('regularMarketPrice'):
            try:
                fast = ticker.fast_info
                quote = {
                    'symbol': symbol,
                    'price': fast.get('last_price', 0),
                    'volume': fast.get('last_volume', 0),
                    'bid': info.get('bid', 0),
                    'ask': info.get('ask', 0),
                    'timestamp': datetime.now(self.timezone)
                }
            except:
                quote = {
                    'symbol': symbol,
                    'price': 0,
                    'volume': 0,
                    'bid': 0,
                    'ask': 0,
                    'timestamp': datetime.now(self.timezone)
                }
        else:
            quote = {
                'symbol': symbol,
                'price': info.get('regularMarketPrice', 0),
                'volume': info.get('regularMarketVolume', 0),
                'bid': info.get('bid', 0),
                'ask': info.get('ask', 0),
                'timestamp': datetime.now(self.timezone)
            }
        
        # Cache the result
        self._cache[cache_key] = (time.time(), quote)
        return quote