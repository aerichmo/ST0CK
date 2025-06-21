"""
Lean multi-bot Flask API server
Provides real-time data for the dashboard
"""
import os
from flask import Flask, jsonify, request
from flask_cors import CORS
from datetime import datetime, timedelta
import psycopg2
from psycopg2.extras import RealDictCursor
import json

app = Flask(__name__)
CORS(app)

# Database connection
DATABASE_URL = os.environ.get('DATABASE_URL')

def get_db_connection():
    """Get database connection with dict cursor"""
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
    return conn

@app.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({'status': 'healthy', 'timestamp': datetime.now().isoformat()})

@app.route('/api/multi-bot/stats')
def multi_bot_stats():
    """Get combined stats for all bots"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Get stats for each bot
        bot_stats = {}
        for bot_id in ['st0ckg', 'st0cka']:
            # Today's performance
            cur.execute("""
                SELECT COUNT(*) as trades, 
                       COALESCE(SUM(realized_pnl), 0) as pnl,
                       SUM(CASE WHEN realized_pnl > 0 THEN 1 ELSE 0 END) as wins
                FROM trades
                WHERE bot_id = %s 
                  AND DATE(entry_time) = CURRENT_DATE
                  AND status = 'CLOSED'
            """, (bot_id,))
            today = cur.fetchone()
            
            # All-time stats
            cur.execute("""
                SELECT COUNT(*) as total_trades,
                       COALESCE(SUM(realized_pnl), 0) as total_pnl,
                       SUM(CASE WHEN realized_pnl > 0 THEN 1 ELSE 0 END) as total_wins
                FROM trades
                WHERE bot_id = %s AND status = 'CLOSED'
            """, (bot_id,))
            all_time = cur.fetchone()
            
            # Active positions
            cur.execute("""
                SELECT COUNT(*) as active
                FROM trades
                WHERE bot_id = %s AND status = 'OPEN'
            """, (bot_id,))
            active = cur.fetchone()
            
            capital = 5000 if bot_id == 'st0ckg' else 10000
            
            bot_stats[bot_id] = {
                'todayPnl': float(today['pnl']),
                'todayTrades': today['trades'],
                'totalPnl': float(all_time['total_pnl']),
                'totalTrades': all_time['total_trades'],
                'winRate': (all_time['total_wins'] / all_time['total_trades'] * 100) if all_time['total_trades'] > 0 else 0,
                'activePositions': active['active'],
                'capital': capital
            }
        
        # Calculate combined stats
        combined = {
            'totalPnl': sum(s['totalPnl'] for s in bot_stats.values()),
            'totalReturn': (sum(s['totalPnl'] for s in bot_stats.values()) / 15000) * 100,
            'totalTrades': sum(s['totalTrades'] for s in bot_stats.values()),
            'winRate': calculate_combined_win_rate(bot_stats),
            'activePositions': sum(s['activePositions'] for s in bot_stats.values()),
            'totalCapital': 15000
        }
        
        cur.close()
        conn.close()
        
        return jsonify({
            'combined': combined,
            'st0ckg': bot_stats['st0ckg'],
            'st0cka': bot_stats['st0cka']
        })
        
    except Exception as e:
        app.logger.error(f"Error in multi_bot_stats: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/multi-bot/trades')
def multi_bot_trades():
    """Get recent trades for all bots"""
    limit = request.args.get('limit', 20, type=int)
    
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("""
            SELECT bot_id, position_id, symbol, contract_symbol as option_symbol,
                   option_type, signal_type, entry_time, entry_price,
                   contracts, exit_time, exit_price, exit_reason,
                   realized_pnl, status
            FROM trades
            ORDER BY entry_time DESC
            LIMIT %s
        """, (limit,))
        
        trades = cur.fetchall()
        
        # Convert datetime objects to ISO format
        for trade in trades:
            if trade['entry_time']:
                trade['entry_time'] = trade['entry_time'].isoformat()
            if trade['exit_time']:
                trade['exit_time'] = trade['exit_time'].isoformat()
        
        cur.close()
        conn.close()
        
        return jsonify(trades)
        
    except Exception as e:
        app.logger.error(f"Error in multi_bot_trades: {e}")
        return jsonify([])

@app.route('/api/multi-bot/equity-curve/<bot_id>')
def bot_equity_curve(bot_id):
    """Get equity curve data for a specific bot"""
    days = request.args.get('days', 30, type=int)
    
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("""
            SELECT DATE(entry_time) as date,
                   SUM(realized_pnl) OVER (ORDER BY DATE(entry_time)) as cumulative_pnl
            FROM trades
            WHERE bot_id = %s
              AND status = 'CLOSED'
              AND entry_time >= CURRENT_DATE - INTERVAL '%s days'
            GROUP BY DATE(entry_time), realized_pnl
            ORDER BY date
        """, (bot_id, days))
        
        equity_data = cur.fetchall()
        
        # Convert dates to ISO format
        for point in equity_data:
            point['date'] = point['date'].isoformat()
        
        cur.close()
        conn.close()
        
        return jsonify(equity_data)
        
    except Exception as e:
        app.logger.error(f"Error in bot_equity_curve: {e}")
        return jsonify([])

def calculate_combined_win_rate(bot_stats):
    """Calculate combined win rate across all bots"""
    total_trades = sum(s['totalTrades'] for s in bot_stats.values())
    if total_trades == 0:
        return 0
    
    total_wins = sum(s['winRate'] / 100 * s['totalTrades'] for s in bot_stats.values())
    return (total_wins / total_trades) * 100

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)