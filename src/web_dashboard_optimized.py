import dash
from dash import dcc, html, Input, Output, State
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, time
import pytz
import threading
import queue
import logging
from flask import Flask

logger = logging.getLogger(__name__)


class OptimizedTradingDashboard:
    """
    Optimized web dashboard with dynamic update intervals based on trading phase.
    Reduces resource usage during non-critical periods.
    """
    
    def __init__(self, trading_engine, market_data_provider, db_manager=None):
        """Initialize the optimized trading dashboard."""
        self.engine = trading_engine
        self.market_data = market_data_provider
        self.db = db_manager
        
        # Initialize Dash app
        self.app = dash.Dash(__name__)
        
        # Data storage with smaller buffer
        self.price_data = pd.DataFrame()
        self.trades = []
        self.current_position = None
        self.opening_range = None
        self.account_info = {}
        
        # Trading time windows (ET)
        self.et_timezone = pytz.timezone('US/Eastern')
        self.market_open = time(9, 30)
        self.opening_range_end = time(9, 40)
        self.active_trading_end = time(10, 30)
        self.session_end = time(16, 5)
        
        # Cache to reduce API calls
        self.last_data_fetch = None
        self.data_cache_seconds = 2
        
        # Setup layout
        self._setup_layout()
        
        # Setup callbacks
        self._setup_callbacks()
        
    def _get_optimal_interval(self):
        """Determine optimal update interval based on current time."""
        now_et = datetime.now(self.et_timezone)
        current_time = now_et.time()
        
        # Weekend - very slow updates
        if now_et.weekday() >= 5:
            return 60000  # 60 seconds
            
        # Active trading window - fastest updates
        if self.opening_range_end <= current_time <= self.active_trading_end:
            return 2000  # 2 seconds
            
        # Opening range - fast updates
        elif self.market_open <= current_time < self.opening_range_end:
            return 3000  # 3 seconds
            
        # Position monitoring - moderate updates
        elif self.active_trading_end < current_time <= self.session_end:
            return 10000  # 10 seconds
            
        # Outside market hours - slow updates
        else:
            return 30000  # 30 seconds
            
    def _setup_layout(self):
        """Create the dashboard layout with dynamic interval."""
        self.app.layout = html.Div([
            # Header
            html.Div([
                html.H1('ST0CK Trading Dashboard - Optimized', 
                       style={'textAlign': 'center', 'color': '#00ff00'}),
                html.H3(f'SPY Options Trading - Opening Range Breakout (9:40-10:30 AM ET)',
                       style={'textAlign': 'center', 'color': '#888'})
            ], style={'backgroundColor': '#1e1e1e', 'padding': '20px'}),
            
            # Main content area
            html.Div([
                # Left panel - Status and info
                html.Div([
                    # Update frequency indicator
                    html.Div([
                        html.H4('Update Frequency', style={'color': '#00ff00'}),
                        html.Div(id='update-frequency', children=[
                            html.P('Calculating...', style={'color': '#fff'})
                        ])
                    ], style={
                        'backgroundColor': '#2e2e2e',
                        'padding': '15px',
                        'borderRadius': '5px',
                        'marginBottom': '20px'
                    }),
                    
                    # Account info card
                    html.Div([
                        html.H4('Account Status', style={'color': '#00ff00'}),
                        html.Div(id='account-info', children=[
                            html.P('Loading...', style={'color': '#fff'})
                        ])
                    ], style={
                        'backgroundColor': '#2e2e2e',
                        'padding': '15px',
                        'borderRadius': '5px',
                        'marginBottom': '20px'
                    }),
                    
                    # Trading status
                    html.Div([
                        html.H4('Trading Status', style={'color': '#00ff00'}),
                        html.Div(id='trading-status', children=[
                            html.P('System Active', style={'color': '#00ff00'})
                        ])
                    ], style={
                        'backgroundColor': '#2e2e2e',
                        'padding': '15px',
                        'borderRadius': '5px'
                    })
                    
                ], style={'width': '20%', 'float': 'left', 'padding': '10px'}),
                
                # Center panel - Charts
                html.Div([
                    # Candlestick chart
                    dcc.Graph(
                        id='candlestick-chart',
                        style={'height': '600px'},
                        config={'displayModeBar': False}
                    ),
                    
                    # Dynamic update interval
                    dcc.Interval(
                        id='interval-component',
                        interval=5000,  # Will be updated dynamically
                        n_intervals=0
                    ),
                    
                    # Store for dynamic interval
                    dcc.Store(id='interval-store', data={'interval': 5000})
                    
                ], style={'width': '60%', 'float': 'left', 'padding': '10px'}),
                
                # Right panel - Performance metrics
                html.Div([
                    html.H4('Performance Metrics', style={'color': '#00ff00'}),
                    html.Div(id='performance-metrics', style={
                        'backgroundColor': '#2e2e2e',
                        'padding': '10px',
                        'borderRadius': '5px'
                    }, children=[
                        html.P('Updates during trading hours', style={'color': '#888'})
                    ])
                ], style={'width': '20%', 'float': 'left', 'padding': '10px'})
                
            ], style={'overflow': 'hidden'}),
            
            # Footer
            html.Div([
                html.P('Optimized for free-tier resources | Updates adjust based on market phase', 
                      style={'textAlign': 'center', 'color': '#888'})
            ], style={'clear': 'both', 'padding': '20px'})
            
        ], style={'backgroundColor': '#1e1e1e', 'minHeight': '100vh'})
        
    def _setup_callbacks(self):
        """Setup Dash callbacks with optimization."""
        
        # Update interval dynamically
        @self.app.callback(
            Output('interval-component', 'interval'),
            [Input('interval-store', 'data')]
        )
        def update_interval(data):
            return self._get_optimal_interval()
        
        # Main dashboard update
        @self.app.callback(
            [Output('candlestick-chart', 'figure'),
             Output('account-info', 'children'),
             Output('trading-status', 'children'),
             Output('update-frequency', 'children'),
             Output('performance-metrics', 'children'),
             Output('interval-store', 'data')],
            [Input('interval-component', 'n_intervals')]
        )
        def update_dashboard(n):
            # Get current interval
            current_interval = self._get_optimal_interval()
            interval_seconds = current_interval / 1000
            
            # Check if we should update
            is_active, status_msg = self._is_active_trading_time()
            
            # Create status display
            status_color = '#00ff00' if is_active else '#ff0000'
            current_time = datetime.now(self.et_timezone).strftime('%I:%M:%S %p ET')
            status_html = [
                html.P(status_msg, style={'color': status_color, 'fontWeight': 'bold'}),
                html.P(f'Current Time: {current_time}', style={'color': '#fff'})
            ]
            
            # Update frequency display
            freq_color = '#00ff00' if interval_seconds <= 5 else '#ffaa00' if interval_seconds <= 10 else '#888'
            freq_html = [
                html.P(f'Every {interval_seconds} seconds', 
                      style={'color': freq_color, 'fontWeight': 'bold'}),
                html.P('Optimized for current market phase', style={'color': '#888', 'fontSize': '12px'})
            ]
            
            # Only fetch new data if cache expired and during active hours
            if is_active and (self.last_data_fetch is None or 
                            (datetime.now() - self.last_data_fetch).total_seconds() > self.data_cache_seconds):
                self._fetch_latest_data()
                self.last_data_fetch = datetime.now()
            
            # Create candlestick chart
            fig = self._create_optimized_chart()
            
            # Update account info (lightweight)
            account_html = self._format_account_info()
            
            # Performance metrics
            perf_html = self._format_performance_metrics()
            
            return (fig, account_html, status_html, freq_html, perf_html, 
                   {'interval': current_interval})
            
    def _is_active_trading_time(self):
        """Check if current time is within active trading window."""
        now_et = datetime.now(self.et_timezone).time()
        
        if datetime.now(self.et_timezone).weekday() >= 5:
            return False, "Weekend - Market Closed"
        
        if now_et < self.market_open:
            return False, f"Pre-Market - Opens at 9:30 AM ET"
        elif now_et < self.opening_range_end:
            return True, "Opening Range Period (9:30-9:40 AM ET)"
        elif now_et <= self.active_trading_end:
            return True, "Active Trading Window (9:40-10:30 AM ET)"
        elif now_et <= self.session_end:
            return True, "Position Monitoring Only"
        else:
            return False, "After Hours - Market Closed"
            
    def _fetch_latest_data(self):
        """Fetch only essential data to minimize resource usage."""
        try:
            now_et = datetime.now(self.et_timezone)
            
            # Focused time window
            today_925am = now_et.replace(hour=9, minute=25, second=0, microsecond=0)
            today_1035am = now_et.replace(hour=10, minute=35, second=0, microsecond=0)
            
            if now_et.time() < time(10, 35):
                start_time = today_925am
                end_time = now_et
            else:
                start_time = today_925am
                end_time = today_1035am
            
            # Fetch only 5-min bars (less data)
            bars = self.market_data.get_stock_bars(
                'SPY',
                timeframe="5Min",
                start=start_time,
                end=end_time,
                limit=50  # Reduced from 100
            )
            
            if not bars.empty:
                self.price_data = bars
                # Calculate only essential indicators
                self.price_data['ema8'] = self.price_data['close'].ewm(span=8, adjust=False).mean()
                self.price_data['ema21'] = self.price_data['close'].ewm(span=21, adjust=False).mean()
                
        except Exception as e:
            logger.error(f"Error fetching data: {e}")
            
    def _create_optimized_chart(self):
        """Create lightweight chart optimized for performance."""
        fig = make_subplots(
            rows=2, cols=1,
            shared_xaxes=True,
            vertical_spacing=0.03,
            row_heights=[0.7, 0.3]
        )
        
        if not self.price_data.empty:
            # Simplified candlestick (no fancy effects)
            fig.add_trace(
                go.Candlestick(
                    x=self.price_data.index,
                    open=self.price_data['open'],
                    high=self.price_data['high'],
                    low=self.price_data['low'],
                    close=self.price_data['close'],
                    name='SPY',
                    showlegend=False
                ),
                row=1, col=1
            )
            
            # EMAs only
            fig.add_trace(
                go.Scatter(
                    x=self.price_data.index,
                    y=self.price_data['ema8'],
                    mode='lines',
                    name='EMA 8',
                    line=dict(color='cyan', width=1)
                ),
                row=1, col=1
            )
            
            fig.add_trace(
                go.Scatter(
                    x=self.price_data.index,
                    y=self.price_data['ema21'],
                    mode='lines',
                    name='EMA 21',
                    line=dict(color='orange', width=1)
                ),
                row=1, col=1
            )
            
            # Simple volume bars
            fig.add_trace(
                go.Bar(
                    x=self.price_data.index,
                    y=self.price_data['volume'],
                    name='Volume',
                    showlegend=False,
                    marker_color='gray'
                ),
                row=2, col=1
            )
            
        # Minimal layout
        is_active, status = self._is_active_trading_time()
        
        fig.update_layout(
            template='plotly_dark',
            title=f'SPY 5-Min | {status}',
            height=600,
            margin=dict(l=50, r=50, t=50, b=50),
            showlegend=True,
            legend=dict(x=0, y=1, bgcolor='rgba(0,0,0,0)'),
            hovermode='x unified'
        )
        
        fig.update_xaxes(rangeslider_visible=False)
        fig.update_yaxes(title_text="Price", row=1, col=1)
        fig.update_yaxes(title_text="Volume", row=2, col=1)
        
        return fig
        
    def _format_account_info(self):
        """Lightweight account info display."""
        if not self.account_info:
            return [html.P('Connect broker for account data', style={'color': '#888'})]
            
        return [
            html.P(f'Mode: {self.account_info.get("mode", "View Only")}', 
                  style={'color': '#fff', 'margin': '5px'})
        ]
        
    def _format_performance_metrics(self):
        """Simple performance metrics."""
        return [
            html.P('Win Rate: --', style={'color': '#fff'}),
            html.P('Daily P&L: --', style={'color': '#fff'}),
            html.P('Trades Today: --', style={'color': '#fff'})
        ]
        
    def run(self, host='127.0.0.1', port=8050, debug=False):
        """Run the dashboard server."""
        logger.info(f"Starting optimized dashboard on http://{host}:{port}")
        self.app.run(host=host, port=port, debug=debug)