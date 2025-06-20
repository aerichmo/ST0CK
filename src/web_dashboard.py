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


class TradingDashboard:
    """
    Web-based real-time trading dashboard using Plotly Dash.
    Shows candlestick charts, indicators, and trade executions.
    """
    
    def __init__(self, trading_engine, market_data_provider, db_manager=None):
        """
        Initialize the trading dashboard.
        
        Args:
            trading_engine: TradingEngine instance
            market_data_provider: Market data provider instance
            db_manager: Optional database manager
        """
        self.engine = trading_engine
        self.market_data = market_data_provider
        self.db = db_manager
        
        # Initialize Dash app
        self.app = dash.Dash(__name__)
        
        # Data storage
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
        
        # Setup layout
        self._setup_layout()
        
        # Setup callbacks
        self._setup_callbacks()
        
    def _is_active_trading_time(self):
        """Check if current time is within active trading window."""
        now_et = datetime.now(self.et_timezone).time()
        
        # Check if it's a weekday
        if datetime.now(self.et_timezone).weekday() >= 5:  # Saturday = 5, Sunday = 6
            return False, "Weekend - Market Closed"
        
        # Check time windows
        if now_et < self.market_open:
            return False, "Pre-Market - Trading starts at 9:30 AM ET"
        elif now_et < self.opening_range_end:
            return True, "Opening Range Period (9:30-9:40 AM ET)"
        elif now_et <= self.active_trading_end:
            return True, "Active Trading Window (9:40-10:30 AM ET)"
        elif now_et <= self.session_end:
            return True, "Position Monitoring Only (No New Trades)"
        else:
            return False, "After Hours - Market Closed"
            
    def _get_optimal_interval(self):
        """Get optimal update interval based on current trading phase."""
        now_et = datetime.now(self.et_timezone)
        current_time = now_et.time()
        
        # Pre-market and active trading window - 1 second updates
        pre_market_start = time(9, 20)
        if pre_market_start <= current_time <= self.active_trading_end:
            return 1000  # 1 second from 9:20 AM to 10:30 AM
            
        # Position monitoring - 15 second updates
        elif self.active_trading_end < current_time <= self.session_end:
            return 15000  # 15 seconds from 10:31 AM to 4:05 PM
            
        # All other times (nights, weekends, outside hours) - 5 minute updates
        else:
            return 300000  # 5 minutes
        
    def _setup_layout(self):
        """Create the dashboard layout."""
        self.app.layout = html.Div([
            # Header
            html.Div([
                html.H1('ST0CK Trading Dashboard', 
                       style={'textAlign': 'center', 'color': '#ffffff'}),
                html.H3(f'SPY Options Trading - Opening Range Breakout Strategy',
                       style={'textAlign': 'center', 'color': '#ffffff'})
            ], style={'backgroundColor': '#0071ce', 'padding': '20px'}),  # Walmart blue header
            
            # Main content area
            html.Div([
                # Left panel - Account info and controls
                html.Div([
                    # Account info card
                    html.Div([
                        html.H4('Account Status', style={'color': '#0071ce'}),
                        html.Div(id='account-info', children=[
                            html.P('Loading...', style={'color': '#2a2a2a'})
                        ])
                    ], style={
                        'backgroundColor': '#ffffff',
                        'padding': '15px',
                        'borderRadius': '5px',
                        'marginBottom': '20px',
                        'border': '1px solid #e8e8e8'
                    }),
                    
                    # Position info card
                    html.Div([
                        html.H4('Current Position', style={'color': '#0071ce'}),
                        html.Div(id='position-info', children=[
                            html.P('No active position', style={'color': '#666666'})
                        ])
                    ], style={
                        'backgroundColor': '#ffffff',
                        'padding': '15px',
                        'borderRadius': '5px',
                        'marginBottom': '20px',
                        'border': '1px solid #e8e8e8'
                    }),
                    
                    # Trading status
                    html.Div([
                        html.H4('Trading Status', style={'color': '#0071ce'}),
                        html.Div(id='trading-status', children=[
                            html.P('System Active', style={'color': '#0071ce'})
                        ])
                    ], style={
                        'backgroundColor': '#ffffff',
                        'padding': '15px',
                        'borderRadius': '5px',
                        'border': '1px solid #e8e8e8'
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
                    
                    # Store for dynamic interval management
                    dcc.Store(id='interval-store', data={'interval': 5000})
                ], style={'width': '60%', 'float': 'left', 'padding': '10px'}),
                
                # Right panel - Trade log
                html.Div([
                    html.H4('Recent Trades', style={'color': '#0071ce'}),
                    html.Div(id='trade-log', style={
                        'height': '500px',
                        'overflowY': 'scroll',
                        'backgroundColor': '#ffffff',
                        'padding': '10px',
                        'borderRadius': '5px',
                        'border': '1px solid #e8e8e8'
                    })
                ], style={'width': '20%', 'float': 'left', 'padding': '10px'})
                
            ], style={'overflow': 'hidden'}),
            
            # Footer
            html.Div([
                html.P('Real-time Alpaca market data', 
                      style={'textAlign': 'center', 'color': '#666666'})
            ], style={'clear': 'both', 'padding': '20px', 'backgroundColor': '#f5f5f5'})
            
        ], style={'backgroundColor': '#f5f5f5', 'minHeight': '100vh'})
        
    def _setup_callbacks(self):
        """Setup Dash callbacks for real-time updates."""
        
        # Update interval dynamically
        @self.app.callback(
            Output('interval-component', 'interval'),
            [Input('interval-store', 'data')]
        )
        def update_interval(data):
            return self._get_optimal_interval()
        
        @self.app.callback(
            [Output('candlestick-chart', 'figure'),
             Output('account-info', 'children'),
             Output('position-info', 'children'),
             Output('trade-log', 'children'),
             Output('trading-status', 'children'),
             Output('interval-store', 'data')],
            [Input('interval-component', 'n_intervals')]
        )
        def update_dashboard(n):
            # Check if we should update
            is_active, status_msg = self._is_active_trading_time()
            
            # Get current interval
            current_interval = self._get_optimal_interval()
            interval_seconds = current_interval / 1000
            
            # Create status display
            status_color = '#0071ce' if is_active else '#fc6500'  # Walmart blue/orange
            current_time = datetime.now(self.et_timezone).strftime('%I:%M:%S %p ET')
            status_html = [
                html.P(status_msg, style={'color': status_color, 'fontWeight': 'bold'}),
                html.P(f'Current Time: {current_time}', style={'color': '#2a2a2a'}),
                html.P(f'Updates: Every {interval_seconds}s', style={'color': '#666666', 'fontSize': '12px'})
            ]
            
            # Only fetch new data during active hours
            if is_active:
                self._fetch_latest_data()
            
            # Create candlestick chart
            fig = self._create_candlestick_chart()
            
            # Update account info
            account_html = self._format_account_info()
            
            # Update position info
            position_html = self._format_position_info()
            
            # Update trade log
            trade_log_html = self._format_trade_log()
            
            return fig, account_html, position_html, trade_log_html, status_html, {'interval': current_interval}
            
    def _fetch_latest_data(self):
        """Fetch the latest market and trading data."""
        try:
            # Get current time in ET
            now_et = datetime.now(self.et_timezone)
            
            # Calculate time window for data fetch
            # Show data from 9:25 AM to 10:35 AM ET (5 min buffer on each side)
            today_925am = now_et.replace(hour=9, minute=25, second=0, microsecond=0)
            today_1035am = now_et.replace(hour=10, minute=35, second=0, microsecond=0)
            
            # Determine time range
            if now_et.time() < time(10, 35):
                # Before 10:35 AM - show from 9:25 AM to now
                start_time = today_925am
                end_time = now_et
            else:
                # After 10:35 AM - show the complete trading window
                start_time = today_925am
                end_time = today_1035am
            
            bars = self.market_data.get_stock_bars(
                'SPY',
                timeframe="5Min",
                start=start_time,
                end=end_time,
                limit=100
            )
            
            if not bars.empty:
                self.price_data = bars
                # Calculate indicators
                self.price_data['ema8'] = self.price_data['close'].ewm(span=8).mean()
                self.price_data['ema21'] = self.price_data['close'].ewm(span=21).mean()
                
            # Get account info from trading engine
            if hasattr(self.engine, 'broker'):
                self.account_info = self.engine.broker.get_account_info() or {}
                
            # Get current position
            if hasattr(self.engine, 'positions') and self.engine.positions:
                self.current_position = list(self.engine.positions.values())[0]
            else:
                self.current_position = None
                
            # Get opening range
            if hasattr(self.engine, 'opening_ranges') and 'SPY' in self.engine.opening_ranges:
                self.opening_range = self.engine.opening_ranges['SPY']
                
            # Get recent trades from database
            if self.db:
                try:
                    recent_trades = self.db.get_recent_trades(limit=10)
                    self.trades = recent_trades
                except:
                    pass
                    
        except Exception as e:
            logger.error(f"Error fetching dashboard data: {e}")
            
    def _create_candlestick_chart(self):
        """Create the candlestick chart with indicators."""
        fig = make_subplots(
            rows=2, cols=1,
            shared_xaxes=True,
            vertical_spacing=0.03,
            row_heights=[0.7, 0.3]
        )
        
        if not self.price_data.empty:
            # Candlestick chart
            fig.add_trace(
                go.Candlestick(
                    x=self.price_data.index,
                    open=self.price_data['open'],
                    high=self.price_data['high'],
                    low=self.price_data['low'],
                    close=self.price_data['close'],
                    name='SPY',
                    increasing_line_color='green',
                    decreasing_line_color='red'
                ),
                row=1, col=1
            )
            
            # EMAs
            fig.add_trace(
                go.Scatter(
                    x=self.price_data.index,
                    y=self.price_data['ema8'],
                    mode='lines',
                    name='EMA 8',
                    line=dict(color='cyan', width=2)
                ),
                row=1, col=1
            )
            
            fig.add_trace(
                go.Scatter(
                    x=self.price_data.index,
                    y=self.price_data['ema21'],
                    mode='lines',
                    name='EMA 21',
                    line=dict(color='orange', width=2)
                ),
                row=1, col=1
            )
            
            # Opening range
            if self.opening_range:
                orh, orl, _ = self.opening_range
                
                # Opening range high
                fig.add_hline(
                    y=orh, line_dash="dash", line_color="yellow",
                    annotation_text="OR High", row=1, col=1
                )
                
                # Opening range low
                fig.add_hline(
                    y=orl, line_dash="dash", line_color="yellow",
                    annotation_text="OR Low", row=1, col=1
                )
                
            # Volume bars
            colors = ['green' if row['close'] >= row['open'] else 'red' 
                     for _, row in self.price_data.iterrows()]
            
            fig.add_trace(
                go.Bar(
                    x=self.price_data.index,
                    y=self.price_data['volume'],
                    name='Volume',
                    marker_color=colors,
                    opacity=0.7
                ),
                row=2, col=1
            )
            
            # Add trade markers
            for trade in self.trades[-10:]:  # Last 10 trades
                trade_time = trade.get('timestamp', datetime.now())
                
                if trade.get('action') == 'BUY':
                    fig.add_annotation(
                        x=trade_time,
                        y=trade.get('price', 0),
                        text="▲",
                        showarrow=True,
                        arrowhead=0,
                        font=dict(size=20, color='green'),
                        row=1, col=1
                    )
                elif trade.get('action') == 'SELL':
                    fig.add_annotation(
                        x=trade_time,
                        y=trade.get('price', 0),
                        text="▼",
                        showarrow=True,
                        arrowhead=0,
                        font=dict(size=20, color='red'),
                        row=1, col=1
                    )
                    
        # Update layout
        is_active, status = self._is_active_trading_time()
        title_color = '#0071ce' if is_active else '#fc6500'
        
        fig.update_layout(
            template='plotly_white',  # Clean white background
            title={
                'text': f'SPY 5-Minute Candles | Opening Range: 9:30-9:40 ET | Active Trading: 9:40-10:30 ET<br><sub>{status}</sub>',
                'font': {'color': title_color, 'size': 18}
            },
            yaxis_title='Price ($)',
            yaxis2_title='Volume',
            xaxis2_title='Time',
            hovermode='x unified',
            showlegend=True,
            legend=dict(x=0, y=1, bgcolor='rgba(255,255,255,0.8)'),
            plot_bgcolor='white',
            paper_bgcolor='white'
        )
        
        fig.update_xaxes(rangeslider_visible=False)
        
        return fig
        
    def _format_account_info(self):
        """Format account information HTML."""
        if not self.account_info:
            return [html.P('No data available', style={'color': '#666666'})]
            
        buying_power = self.account_info.get('buying_power', 0)
        portfolio_value = self.account_info.get('portfolio_value', 0)
        realized_pnl = self.account_info.get('realized_pnl', 0)
        
        pnl_color = '#0071ce' if realized_pnl >= 0 else '#fc6500'
        
        return [
            html.P(f'Buying Power: ${buying_power:,.2f}', 
                  style={'color': '#2a2a2a', 'margin': '5px'}),
            html.P(f'Portfolio Value: ${portfolio_value:,.2f}', 
                  style={'color': '#2a2a2a', 'margin': '5px'}),
            html.P(f'Realized P&L: ${realized_pnl:,.2f}', 
                  style={'color': pnl_color, 'margin': '5px', 'fontWeight': 'bold'})
        ]
        
    def _format_position_info(self):
        """Format position information HTML."""
        if not self.current_position:
            return [html.P('No active position', style={'color': '#666666'})]
            
        symbol = self.current_position.get('symbol', 'N/A')
        quantity = self.current_position.get('quantity', 0)
        avg_price = self.current_position.get('avg_price', 0)
        unrealized_pnl = self.current_position.get('unrealized_pnl', 0)
        
        pnl_color = '#0071ce' if unrealized_pnl >= 0 else '#fc6500'
        
        return [
            html.P(f'Symbol: {symbol}', style={'color': '#2a2a2a', 'margin': '5px'}),
            html.P(f'Quantity: {quantity} contracts', 
                  style={'color': '#2a2a2a', 'margin': '5px'}),
            html.P(f'Avg Price: ${avg_price:.2f}', 
                  style={'color': '#2a2a2a', 'margin': '5px'}),
            html.P(f'Unrealized P&L: ${unrealized_pnl:.2f}', 
                  style={'color': pnl_color, 'margin': '5px', 'fontWeight': 'bold'})
        ]
        
    def _format_trade_log(self):
        """Format trade log HTML."""
        if not self.trades:
            return [html.P('No trades yet', style={'color': '#666666'})]
            
        trade_elements = []
        
        for trade in reversed(self.trades[-10:]):  # Last 10 trades, newest first
            timestamp = trade.get('timestamp', datetime.now())
            action = trade.get('action', 'N/A')
            quantity = trade.get('quantity', 0)
            price = trade.get('price', 0)
            pnl = trade.get('pnl', 0)
            
            action_color = '#0071ce' if action == 'BUY' else '#fc6500'
            pnl_color = '#0071ce' if pnl >= 0 else '#fc6500'
            
            trade_div = html.Div([
                html.P(f'{timestamp.strftime("%H:%M:%S")} - {action}',
                      style={'color': action_color, 'fontWeight': 'bold', 
                            'margin': '2px'}),
                html.P(f'{quantity} @ ${price:.2f}',
                      style={'color': '#2a2a2a', 'margin': '2px'}),
                html.P(f'P&L: ${pnl:.2f}' if action == 'SELL' else '',
                      style={'color': pnl_color, 'margin': '2px'})
            ], style={
                'backgroundColor': '#f8f8f8',
                'padding': '8px',
                'marginBottom': '5px',
                'borderRadius': '3px',
                'border': '1px solid #e8e8e8'
            })
            
            trade_elements.append(trade_div)
            
        return trade_elements
        
    def run(self, host='127.0.0.1', port=8050, debug=False):
        """Run the dashboard server."""
        logger.info(f"Starting dashboard on http://{host}:{port}")
        self.app.run(host=host, port=port, debug=debug)