import dash
from dash import dcc, html, Input, Output, State
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
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
        
        # Setup layout
        self._setup_layout()
        
        # Setup callbacks
        self._setup_callbacks()
        
    def _setup_layout(self):
        """Create the dashboard layout."""
        self.app.layout = html.Div([
            # Header
            html.Div([
                html.H1('ST0CK Trading Dashboard', 
                       style={'textAlign': 'center', 'color': '#00ff00'}),
                html.H3(f'SPY Options Trading - Opening Range Breakout Strategy',
                       style={'textAlign': 'center', 'color': '#888'})
            ], style={'backgroundColor': '#1e1e1e', 'padding': '20px'}),
            
            # Main content area
            html.Div([
                # Left panel - Account info and controls
                html.Div([
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
                    
                    # Position info card
                    html.Div([
                        html.H4('Current Position', style={'color': '#00ff00'}),
                        html.Div(id='position-info', children=[
                            html.P('No active position', style={'color': '#888'})
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
                    
                    # Update interval
                    dcc.Interval(
                        id='interval-component',
                        interval=5000,  # Update every 5 seconds
                        n_intervals=0
                    )
                ], style={'width': '60%', 'float': 'left', 'padding': '10px'}),
                
                # Right panel - Trade log
                html.Div([
                    html.H4('Recent Trades', style={'color': '#00ff00'}),
                    html.Div(id='trade-log', style={
                        'height': '500px',
                        'overflowY': 'scroll',
                        'backgroundColor': '#2e2e2e',
                        'padding': '10px',
                        'borderRadius': '5px'
                    })
                ], style={'width': '20%', 'float': 'left', 'padding': '10px'})
                
            ], style={'overflow': 'hidden'}),
            
            # Footer
            html.Div([
                html.P('Real-time data updates every 5 seconds', 
                      style={'textAlign': 'center', 'color': '#888'})
            ], style={'clear': 'both', 'padding': '20px'})
            
        ], style={'backgroundColor': '#1e1e1e', 'minHeight': '100vh'})
        
    def _setup_callbacks(self):
        """Setup Dash callbacks for real-time updates."""
        
        @self.app.callback(
            [Output('candlestick-chart', 'figure'),
             Output('account-info', 'children'),
             Output('position-info', 'children'),
             Output('trade-log', 'children')],
            [Input('interval-component', 'n_intervals')]
        )
        def update_dashboard(n):
            # Update data
            self._fetch_latest_data()
            
            # Create candlestick chart
            fig = self._create_candlestick_chart()
            
            # Update account info
            account_html = self._format_account_info()
            
            # Update position info
            position_html = self._format_position_info()
            
            # Update trade log
            trade_log_html = self._format_trade_log()
            
            return fig, account_html, position_html, trade_log_html
            
    def _fetch_latest_data(self):
        """Fetch the latest market and trading data."""
        try:
            # Get price data
            end_time = datetime.now()
            start_time = end_time - timedelta(hours=2)
            
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
        fig.update_layout(
            template='plotly_dark',
            title='SPY 5-Minute Candles with Opening Range Breakout',
            yaxis_title='Price ($)',
            yaxis2_title='Volume',
            xaxis2_title='Time',
            hovermode='x unified',
            showlegend=True,
            legend=dict(x=0, y=1)
        )
        
        fig.update_xaxes(rangeslider_visible=False)
        
        return fig
        
    def _format_account_info(self):
        """Format account information HTML."""
        if not self.account_info:
            return [html.P('No data available', style={'color': '#888'})]
            
        buying_power = self.account_info.get('buying_power', 0)
        portfolio_value = self.account_info.get('portfolio_value', 0)
        realized_pnl = self.account_info.get('realized_pnl', 0)
        
        pnl_color = '#00ff00' if realized_pnl >= 0 else '#ff0000'
        
        return [
            html.P(f'Buying Power: ${buying_power:,.2f}', 
                  style={'color': '#fff', 'margin': '5px'}),
            html.P(f'Portfolio Value: ${portfolio_value:,.2f}', 
                  style={'color': '#fff', 'margin': '5px'}),
            html.P(f'Realized P&L: ${realized_pnl:,.2f}', 
                  style={'color': pnl_color, 'margin': '5px', 'fontWeight': 'bold'})
        ]
        
    def _format_position_info(self):
        """Format position information HTML."""
        if not self.current_position:
            return [html.P('No active position', style={'color': '#888'})]
            
        symbol = self.current_position.get('symbol', 'N/A')
        quantity = self.current_position.get('quantity', 0)
        avg_price = self.current_position.get('avg_price', 0)
        unrealized_pnl = self.current_position.get('unrealized_pnl', 0)
        
        pnl_color = '#00ff00' if unrealized_pnl >= 0 else '#ff0000'
        
        return [
            html.P(f'Symbol: {symbol}', style={'color': '#fff', 'margin': '5px'}),
            html.P(f'Quantity: {quantity} contracts', 
                  style={'color': '#fff', 'margin': '5px'}),
            html.P(f'Avg Price: ${avg_price:.2f}', 
                  style={'color': '#fff', 'margin': '5px'}),
            html.P(f'Unrealized P&L: ${unrealized_pnl:.2f}', 
                  style={'color': pnl_color, 'margin': '5px', 'fontWeight': 'bold'})
        ]
        
    def _format_trade_log(self):
        """Format trade log HTML."""
        if not self.trades:
            return [html.P('No trades yet', style={'color': '#888'})]
            
        trade_elements = []
        
        for trade in reversed(self.trades[-10:]):  # Last 10 trades, newest first
            timestamp = trade.get('timestamp', datetime.now())
            action = trade.get('action', 'N/A')
            quantity = trade.get('quantity', 0)
            price = trade.get('price', 0)
            pnl = trade.get('pnl', 0)
            
            action_color = '#00ff00' if action == 'BUY' else '#ff0000'
            pnl_color = '#00ff00' if pnl >= 0 else '#ff0000'
            
            trade_div = html.Div([
                html.P(f'{timestamp.strftime("%H:%M:%S")} - {action}',
                      style={'color': action_color, 'fontWeight': 'bold', 
                            'margin': '2px'}),
                html.P(f'{quantity} @ ${price:.2f}',
                      style={'color': '#fff', 'margin': '2px'}),
                html.P(f'P&L: ${pnl:.2f}' if action == 'SELL' else '',
                      style={'color': pnl_color, 'margin': '2px'})
            ], style={
                'backgroundColor': '#3e3e3e',
                'padding': '8px',
                'marginBottom': '5px',
                'borderRadius': '3px'
            })
            
            trade_elements.append(trade_div)
            
        return trade_elements
        
    def run(self, host='127.0.0.1', port=8050, debug=False):
        """Run the dashboard server."""
        logger.info(f"Starting dashboard on http://{host}:{port}")
        self.app.run_server(host=host, port=port, debug=debug)