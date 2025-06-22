"""
APEX Trading Dashboard Server
Serves performance tracking and forecasts
"""
import os
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from datetime import datetime, timedelta
import sqlite3
import json

app = Flask(__name__)
CORS(app)

# Database connection
DATABASE_URL = os.environ.get('DATABASE_URL', 'sqlite:///trading_multi.db')

def get_db_connection():
    """Get database connection"""
    if DATABASE_URL.startswith('sqlite:'):
        db_path = DATABASE_URL.replace('sqlite:///', '')
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        return conn
    else:
        # PostgreSQL support can be added later
        raise NotImplementedError("Only SQLite supported currently")

# Serve static files
@app.route('/')
def index():
    """Serve the yearly dashboard"""
    return send_from_directory('public', 'index.html')

@app.route('/st0ckg')
def monthly():
    """Serve the monthly dashboard"""
    return send_from_directory('public', 'monthly.html')

@app.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({'status': 'healthy', 'timestamp': datetime.now().isoformat()})

@app.route('/api/performance')
def get_performance():
    """Get APEX performance data"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get current month's trades
        current_month = datetime.now().strftime('%Y-%m')
        query = """
            SELECT 
                DATE(entry_time) as trade_date,
                SUM(realized_pnl) as daily_pnl,
                COUNT(*) as trade_count,
                SUM(CASE WHEN realized_pnl > 0 THEN 1 ELSE 0 END) as wins
            FROM trades
            WHERE bot_id = 'apex'
            AND strftime('%Y-%m', entry_time) = ?
            AND status = 'CLOSED'
            GROUP BY DATE(entry_time)
            ORDER BY trade_date
        """
        
        cursor.execute(query, (current_month,))
        results = cursor.fetchall()
        
        # Get all trading days for the month
        year = int(current_month.split('-')[0])
        month = int(current_month.split('-')[1])
        
        # Create a dict of actual results
        results_dict = {}
        for row in results:
            results_dict[row[0]] = {
                'pnl': float(row[1]) if row[1] else 0,
                'trades': row[2],
                'wins': row[3]
            }
        
        # Generate full month data
        days = []
        actuals = []
        cumulative_capital = []
        capital = 5000  # Starting capital
        
        # Get all days in the month
        import calendar
        num_days = calendar.monthrange(year, month)[1]
        
        for day in range(1, num_days + 1):
            date = f"{year}-{month:02d}-{day:02d}"
            date_obj = datetime(year, month, day)
            
            # Skip weekends
            if date_obj.weekday() >= 5:  # Saturday = 5, Sunday = 6
                continue
                
            days.append(date)
            
            # Check if we have data for this day
            if date in results_dict:
                daily_pnl = results_dict[date]['pnl']
                actuals.append(daily_pnl)
                capital += daily_pnl
                cumulative_capital.append(capital)
            elif date_obj.date() <= datetime.now().date():
                # Past day with no trades
                actuals.append(0)
                cumulative_capital.append(capital)
            else:
                # Future day
                actuals.append(None)
                cumulative_capital.append(None)
        
        # Calculate statistics
        total_trades = sum(r[2] for r in results) if results else 0
        total_wins = sum(r[3] for r in results) if results else 0
        win_rate = (total_wins / total_trades * 100) if total_trades > 0 else 0
        
        conn.close()
        
        return jsonify({
            'days': days,
            'actuals': actuals,
            'cumulativeCapital': cumulative_capital,
            'winRate': win_rate,
            'totalTrades': total_trades
        })
        
    except Exception as e:
        # Return demo data if database not available
        app.logger.error(f"Database error: {e}")
        return jsonify({
            'demo': True,
            'message': 'Using demo data'
        })

@app.route('/api/performance/yearly')
def get_yearly_performance():
    """Get APEX yearly performance data"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get monthly aggregated data for current year
        current_year = datetime.now().strftime('%Y')
        query = """
            SELECT 
                strftime('%m', entry_time) as month,
                SUM(realized_pnl) as monthly_pnl,
                COUNT(*) as trade_count,
                SUM(CASE WHEN realized_pnl > 0 THEN 1 ELSE 0 END) as wins
            FROM trades
            WHERE bot_id = 'apex'
            AND strftime('%Y', entry_time) = ?
            AND status = 'CLOSED'
            GROUP BY strftime('%m', entry_time)
            ORDER BY month
        """
        
        cursor.execute(query, (current_year,))
        results = cursor.fetchall()
        
        # Create a dict of actual results by month
        results_dict = {}
        for row in results:
            month_num = int(row[0]) - 1  # Convert to 0-indexed
            results_dict[month_num] = {
                'pnl': float(row[1]) if row[1] else 0,
                'trades': row[2],
                'wins': row[3]
            }
        
        # Generate full year data
        months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
        monthlyPnL = []
        cumulativeCapital = []
        monthlyReturns = []
        capital = 5000  # Starting capital
        
        current_month = datetime.now().month - 1  # 0-indexed
        
        for i in range(12):
            if i in results_dict:
                # We have data for this month
                pnl = results_dict[i]['pnl']
                monthlyPnL.append(pnl)
                previous_capital = capital
                capital += pnl
                cumulativeCapital.append(capital)
                monthly_return = (pnl / previous_capital) * 100 if previous_capital > 0 else 0
                monthlyReturns.append(monthly_return)
            elif i <= current_month:
                # Past month with no trades
                monthlyPnL.append(0)
                cumulativeCapital.append(capital)
                monthlyReturns.append(0)
            else:
                # Future month
                monthlyPnL.append(None)
                cumulativeCapital.append(None)
                monthlyReturns.append(None)
        
        conn.close()
        
        return jsonify({
            'months': months,
            'monthlyPnL': monthlyPnL,
            'cumulativeCapital': cumulativeCapital,
            'monthlyReturns': monthlyReturns
        })
        
    except Exception as e:
        # Return demo data if database not available
        app.logger.error(f"Database error: {e}")
        return jsonify({
            'demo': True,
            'message': 'Using demo data'
        })

@app.route('/api/trades')
def get_trades():
    """Get recent APEX trades"""
    limit = request.args.get('limit', 20, type=int)
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        query = """
            SELECT position_id, symbol, contract_symbol as option_symbol,
                   option_type, signal_type, entry_time, entry_price,
                   contracts, exit_time, exit_price, exit_reason,
                   realized_pnl, status
            FROM trades
            WHERE bot_id = 'apex'
            ORDER BY entry_time DESC
            LIMIT ?
        """
        
        cursor.execute(query, (limit,))
        trades = cursor.fetchall()
        
        # Convert to list of dicts
        trade_list = []
        for trade in trades:
            trade_dict = dict(trade)
            # Convert datetime to ISO format if needed
            if trade_dict.get('entry_time'):
                trade_dict['entry_time'] = trade_dict['entry_time']
            if trade_dict.get('exit_time'):
                trade_dict['exit_time'] = trade_dict['exit_time']
            trade_list.append(trade_dict)
        
        conn.close()
        
        return jsonify(trade_list)
        
    except Exception as e:
        app.logger.error(f"Error in get_trades: {e}")
        return jsonify([])

@app.route('/forecast')
def forecast():
    """Serve the forecast document"""
    try:
        with open('APEX_MONTHLY_FORECAST.md', 'r') as f:
            content = f.read()
        # Convert markdown to simple HTML
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>APEX Monthly Forecast</title>
            <style>
                body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; 
                        margin: 40px; line-height: 1.6; }}
                pre {{ background: #f5f5f5; padding: 20px; border-radius: 5px; overflow-x: auto; }}
                table {{ border-collapse: collapse; width: 100%; margin: 20px 0; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                th {{ background-color: #f9fafb; }}
            </style>
        </head>
        <body>
            <pre>{content}</pre>
        </body>
        </html>
        """
        return html
    except:
        return "Forecast not available", 404

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)