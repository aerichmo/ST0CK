import matplotlib.pyplot as plt
import matplotlib.animation as animation
from matplotlib.patches import Rectangle
from matplotlib.lines import Line2D
import mplfinance as mpf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import threading
import queue
from typing import Dict, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class CandleVisualizer:
    """
    Real-time candlestick chart visualizer with trade execution overlay.
    Shows 5-minute candles, opening range, EMA indicators, and trade markers.
    """
    
    def __init__(self, market_data_provider, db_manager=None):
        """
        Initialize the candle visualizer.
        
        Args:
            market_data_provider: Market data provider instance (MCP or Yahoo)
            db_manager: Optional database manager for historical trades
        """
        self.market_data = market_data_provider
        self.db = db_manager
        
        # Chart configuration
        self.symbol = 'SPY'
        self.candle_period = 100  # Show last 100 candles
        self.update_interval = 5000  # Update every 5 seconds
        
        # Data storage
        self.price_data = pd.DataFrame()
        self.trades = []
        self.current_position = None
        self.opening_range = None
        
        # Chart components
        self.fig = None
        self.ax = None
        self.animation = None
        
        # Thread-safe queue for trade updates
        self.trade_queue = queue.Queue()
        
        # Chart style
        plt.style.use('dark_background')
        
    def start(self):
        """Start the real-time visualization."""
        # Initialize the chart
        self._setup_chart()
        
        # Start animation
        self.animation = animation.FuncAnimation(
            self.fig,
            self._update_chart,
            interval=self.update_interval,
            blit=False
        )
        
        plt.show()
        
    def _setup_chart(self):
        """Set up the initial chart layout."""
        # Create figure with subplots
        self.fig = plt.figure(figsize=(15, 10))
        
        # Main price chart (80% height)
        self.ax_price = plt.subplot2grid((5, 1), (0, 0), rowspan=4)
        
        # Volume chart (20% height)
        self.ax_volume = plt.subplot2grid((5, 1), (4, 0), rowspan=1)
        
        # Configure axes
        self.ax_price.set_title(f'{self.symbol} - Real-Time 5-Minute Candles', fontsize=16)
        self.ax_price.set_ylabel('Price ($)', fontsize=12)
        self.ax_volume.set_ylabel('Volume', fontsize=12)
        self.ax_volume.set_xlabel('Time', fontsize=12)
        
        # Grid
        self.ax_price.grid(True, alpha=0.3)
        self.ax_volume.grid(True, alpha=0.3)
        
        # Legend elements
        self.legend_elements = [
            Line2D([0], [0], color='cyan', lw=2, label='EMA 8'),
            Line2D([0], [0], color='orange', lw=2, label='EMA 21'),
            Line2D([0], [0], color='yellow', lw=2, linestyle='--', label='Opening Range'),
            Line2D([0], [0], marker='^', color='w', lw=0, markersize=10, 
                   markerfacecolor='g', label='Buy Signal'),
            Line2D([0], [0], marker='v', color='w', lw=0, markersize=10, 
                   markerfacecolor='r', label='Sell Signal'),
            Line2D([0], [0], marker='x', color='w', lw=0, markersize=10, 
                   markerfacecolor='yellow', label='Exit')
        ]
        
        plt.tight_layout()
        
    def _update_chart(self, frame):
        """Update the chart with latest data."""
        try:
            # Fetch latest price data
            self._fetch_latest_data()
            
            # Process any pending trades
            self._process_trade_queue()
            
            # Clear axes
            self.ax_price.clear()
            self.ax_volume.clear()
            
            if not self.price_data.empty:
                # Plot candlesticks
                self._plot_candles()
                
                # Plot indicators
                self._plot_indicators()
                
                # Plot opening range
                self._plot_opening_range()
                
                # Plot trades
                self._plot_trades()
                
                # Update labels and formatting
                self._format_chart()
                
        except Exception as e:
            logger.error(f"Error updating chart: {e}")
            
    def _fetch_latest_data(self):
        """Fetch the latest market data."""
        try:
            # Get 5-minute bars
            end_time = datetime.now()
            start_time = end_time - timedelta(hours=2)  # Last 2 hours
            
            bars = self.market_data.get_stock_bars(
                self.symbol,
                timeframe="5Min",
                start=start_time,
                end=end_time,
                limit=self.candle_period
            )
            
            if not bars.empty:
                self.price_data = bars
                
                # Calculate indicators
                self.price_data['ema8'] = self.price_data['close'].ewm(span=8).mean()
                self.price_data['ema21'] = self.price_data['close'].ewm(span=21).mean()
                self.price_data['atr'] = self._calculate_atr(self.price_data)
                
        except Exception as e:
            logger.error(f"Error fetching market data: {e}")
            
    def _calculate_atr(self, df, period=14):
        """Calculate Average True Range."""
        high = df['high']
        low = df['low']
        close = df['close']
        
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=period).mean()
        
        return atr
        
    def _plot_candles(self):
        """Plot candlestick chart."""
        for idx, row in self.price_data.iterrows():
            # Determine candle color
            color = 'green' if row['close'] >= row['open'] else 'red'
            
            # Plot high-low line
            self.ax_price.plot([idx, idx], [row['low'], row['high']], 
                             color='white', linewidth=1)
            
            # Plot candle body
            height = abs(row['close'] - row['open'])
            bottom = min(row['close'], row['open'])
            
            rect = Rectangle((idx - 0.3, bottom), 0.6, height,
                           facecolor=color, edgecolor='white', linewidth=1)
            self.ax_price.add_patch(rect)
            
        # Plot volume bars
        colors = ['green' if row['close'] >= row['open'] else 'red' 
                 for _, row in self.price_data.iterrows()]
        self.ax_volume.bar(range(len(self.price_data)), 
                         self.price_data['volume'], 
                         color=colors, alpha=0.7)
        
    def _plot_indicators(self):
        """Plot technical indicators."""
        if 'ema8' in self.price_data.columns:
            self.ax_price.plot(self.price_data['ema8'], 
                             color='cyan', linewidth=2, label='EMA 8')
            
        if 'ema21' in self.price_data.columns:
            self.ax_price.plot(self.price_data['ema21'], 
                             color='orange', linewidth=2, label='EMA 21')
            
    def _plot_opening_range(self):
        """Plot opening range high and low."""
        if self.opening_range:
            orh, orl = self.opening_range
            
            # Plot horizontal lines for opening range
            self.ax_price.axhline(y=orh, color='yellow', linestyle='--', 
                                linewidth=2, alpha=0.7, label='OR High')
            self.ax_price.axhline(y=orl, color='yellow', linestyle='--', 
                                linewidth=2, alpha=0.7, label='OR Low')
            
            # Shade opening range area
            self.ax_price.fill_between(range(len(self.price_data)), 
                                     orl, orh, alpha=0.1, color='yellow')
            
    def _plot_trades(self):
        """Plot trade execution markers."""
        for trade in self.trades:
            # Find the candle index for this trade
            trade_time = trade['timestamp']
            
            # Find nearest candle
            time_diffs = abs(self.price_data.index - trade_time)
            nearest_idx = time_diffs.argmin()
            
            if trade['action'] == 'BUY':
                self.ax_price.scatter(nearest_idx, trade['price'], 
                                    marker='^', s=200, color='green', 
                                    edgecolor='white', linewidth=2, zorder=5)
                
                # Add trade annotation
                self.ax_price.annotate(f"Buy\n${trade['price']:.2f}", 
                                     (nearest_idx, trade['price']),
                                     xytext=(10, 10), textcoords='offset points',
                                     fontsize=8, color='green',
                                     bbox=dict(boxstyle='round,pad=0.3', 
                                             facecolor='black', alpha=0.7))
                
            elif trade['action'] == 'SELL':
                self.ax_price.scatter(nearest_idx, trade['price'], 
                                    marker='v', s=200, color='red', 
                                    edgecolor='white', linewidth=2, zorder=5)
                
                # Add trade annotation with P&L
                pnl = trade.get('pnl', 0)
                pnl_color = 'green' if pnl > 0 else 'red'
                self.ax_price.annotate(f"Sell\n${trade['price']:.2f}\nP&L: ${pnl:.2f}", 
                                     (nearest_idx, trade['price']),
                                     xytext=(10, -10), textcoords='offset points',
                                     fontsize=8, color=pnl_color,
                                     bbox=dict(boxstyle='round,pad=0.3', 
                                             facecolor='black', alpha=0.7))
                
    def _format_chart(self):
        """Format chart labels and appearance."""
        # Set labels
        self.ax_price.set_title(f'{self.symbol} - Real-Time 5-Minute Candles', 
                              fontsize=16)
        self.ax_price.set_ylabel('Price ($)', fontsize=12)
        self.ax_volume.set_ylabel('Volume', fontsize=12)
        
        # Format x-axis with time labels
        if not self.price_data.empty:
            # Show every 10th timestamp
            xticks = range(0, len(self.price_data), 10)
            xlabels = [self.price_data.index[i].strftime('%H:%M') 
                      for i in xticks]
            
            self.ax_price.set_xticks(xticks)
            self.ax_price.set_xticklabels([])  # Hide on price chart
            
            self.ax_volume.set_xticks(xticks)
            self.ax_volume.set_xticklabels(xlabels, rotation=45)
            
        # Add legend
        self.ax_price.legend(handles=self.legend_elements, loc='upper left')
        
        # Grid
        self.ax_price.grid(True, alpha=0.3)
        self.ax_volume.grid(True, alpha=0.3)
        
        # Add current position info
        if self.current_position:
            info_text = (f"Position: {self.current_position['quantity']} contracts\n"
                        f"Avg Price: ${self.current_position['avg_price']:.2f}\n"
                        f"Current P&L: ${self.current_position.get('unrealized_pnl', 0):.2f}")
            
            self.ax_price.text(0.02, 0.98, info_text, transform=self.ax_price.transAxes,
                             fontsize=10, verticalalignment='top',
                             bbox=dict(boxstyle='round,pad=0.5', 
                                     facecolor='black', alpha=0.7))
            
    def add_trade(self, trade_info: Dict):
        """Add a trade to be displayed on the chart."""
        self.trade_queue.put(trade_info)
        
    def update_position(self, position_info: Dict):
        """Update current position information."""
        self.current_position = position_info
        
    def set_opening_range(self, high: float, low: float):
        """Set the opening range values."""
        self.opening_range = (high, low)
        
    def _process_trade_queue(self):
        """Process pending trades from the queue."""
        while not self.trade_queue.empty():
            try:
                trade = self.trade_queue.get_nowait()
                self.trades.append(trade)
                
                # Keep only recent trades (last 20)
                if len(self.trades) > 20:
                    self.trades = self.trades[-20:]
                    
            except queue.Empty:
                break
                
    def stop(self):
        """Stop the visualization."""
        if self.animation:
            self.animation.event_source.stop()
        plt.close(self.fig)