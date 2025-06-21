const express = require('express');
const path = require('path');
const { Client } = require('pg');

const app = express();
const PORT = process.env.PORT || 10000;

// Database connection
const dbClient = new Client({
  connectionString: process.env.DATABASE_URL,
  ssl: process.env.DATABASE_URL ? { rejectUnauthorized: false } : false
});

// Connect to database on startup
dbClient.connect().catch(err => {
  console.error('Database connection error:', err);
});

// Serve static files
app.use(express.static('public'));
app.use(express.json());

// Multi-bot API endpoints
app.get('/api/multi-bot/stats', async (req, res) => {
  try {
    // Get stats for each bot
    const st0ckgStats = await getBotStats('st0ckg');
    const st0ckaStats = await getBotStats('st0cka');
    
    // Calculate combined stats
    const combined = {
      totalPnl: st0ckgStats.totalPnl + st0ckaStats.totalPnl,
      totalReturn: ((st0ckgStats.totalPnl + st0ckaStats.totalPnl) / 15000) * 100, // 5k + 10k capital
      totalTrades: st0ckgStats.totalTrades + st0ckaStats.totalTrades,
      winRate: calculateCombinedWinRate(st0ckgStats, st0ckaStats),
      activePositions: st0ckgStats.activePositions + st0ckaStats.activePositions,
      totalCapital: 15000
    };
    
    res.json({
      combined,
      st0ckg: st0ckgStats,
      st0cka: st0ckaStats
    });
  } catch (error) {
    console.error('Error fetching multi-bot stats:', error);
    res.status(500).json({ error: 'Failed to fetch stats' });
  }
});

app.get('/api/multi-bot/trades', async (req, res) => {
  const limit = parseInt(req.query.limit) || 20;
  
  try {
    const query = `
      SELECT bot_id, position_id, symbol, contract_symbol as option_symbol, 
             option_type, signal_type, entry_time, entry_price, 
             contracts, exit_time, exit_price, exit_reason, 
             realized_pnl, status
      FROM trades
      ORDER BY entry_time DESC
      LIMIT $1
    `;
    
    const result = await dbClient.query(query, [limit]);
    res.json(result.rows);
  } catch (error) {
    console.error('Error fetching trades:', error);
    res.json([]);
  }
});

app.get('/api/multi-bot/performance/:bot_id', async (req, res) => {
  const { bot_id } = req.params;
  const days = parseInt(req.query.days) || 30;
  
  try {
    const query = `
      SELECT DATE(entry_time) as date, 
             SUM(realized_pnl) as daily_pnl,
             COUNT(*) as trades,
             SUM(CASE WHEN realized_pnl > 0 THEN 1 ELSE 0 END) as wins
      FROM trades
      WHERE bot_id = $1 
        AND entry_time >= CURRENT_DATE - INTERVAL '$2 days'
        AND status = 'CLOSED'
      GROUP BY DATE(entry_time)
      ORDER BY date DESC
    `;
    
    const result = await dbClient.query(query, [bot_id, days]);
    res.json(result.rows);
  } catch (error) {
    console.error('Error fetching performance:', error);
    res.json([]);
  }
});

// Helper function to get bot stats
async function getBotStats(botId) {
  try {
    // Today's stats
    const todayQuery = `
      SELECT COUNT(*) as trades, 
             COALESCE(SUM(realized_pnl), 0) as pnl,
             SUM(CASE WHEN realized_pnl > 0 THEN 1 ELSE 0 END) as wins
      FROM trades
      WHERE bot_id = $1 
        AND DATE(entry_time) = CURRENT_DATE
        AND status = 'CLOSED'
    `;
    
    const todayResult = await dbClient.query(todayQuery, [botId]);
    const todayStats = todayResult.rows[0];
    
    // All-time stats
    const allTimeQuery = `
      SELECT COUNT(*) as total_trades,
             COALESCE(SUM(realized_pnl), 0) as total_pnl,
             SUM(CASE WHEN realized_pnl > 0 THEN 1 ELSE 0 END) as total_wins
      FROM trades
      WHERE bot_id = $1 AND status = 'CLOSED'
    `;
    
    const allTimeResult = await dbClient.query(allTimeQuery, [botId]);
    const allTimeStats = allTimeResult.rows[0];
    
    // Active positions
    const activeQuery = `
      SELECT COUNT(*) as active
      FROM trades
      WHERE bot_id = $1 AND status = 'OPEN'
    `;
    
    const activeResult = await dbClient.query(activeQuery, [botId]);
    const activePositions = activeResult.rows[0].active;
    
    // Capital based on bot
    const capital = botId === 'st0ckg' ? 5000 : 10000;
    
    return {
      todayPnl: parseFloat(todayStats.pnl) || 0,
      todayTrades: parseInt(todayStats.trades) || 0,
      totalPnl: parseFloat(allTimeStats.total_pnl) || 0,
      totalTrades: parseInt(allTimeStats.total_trades) || 0,
      winRate: allTimeStats.total_trades > 0 
        ? (allTimeStats.total_wins / allTimeStats.total_trades * 100) 
        : 0,
      activePositions: parseInt(activePositions) || 0,
      capital
    };
  } catch (error) {
    console.error(`Error getting stats for ${botId}:`, error);
    return {
      todayPnl: 0,
      todayTrades: 0,
      totalPnl: 0,
      totalTrades: 0,
      winRate: 0,
      activePositions: 0,
      capital: botId === 'st0ckg' ? 5000 : 10000
    };
  }
}

function calculateCombinedWinRate(stats1, stats2) {
  const totalTrades = stats1.totalTrades + stats2.totalTrades;
  if (totalTrades === 0) return 0;
  
  const totalWins = (stats1.winRate / 100 * stats1.totalTrades) + 
                    (stats2.winRate / 100 * stats2.totalTrades);
  
  return (totalWins / totalTrades) * 100;
}

// Serve the multi-bot dashboard
app.get('/', (req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'index.html'));
});

// Health check
app.get('/health', (req, res) => {
  res.json({ status: 'healthy', database: dbClient ? 'connected' : 'disconnected' });
});

app.listen(PORT, () => {
  console.log(`ST0CK Multi-Bot Dashboard running on port ${PORT}`);
});