-- Performance optimization indexes for ST0CK database
-- These indexes significantly improve query performance

-- Trades table indexes
CREATE INDEX IF NOT EXISTS idx_bot_entry_time ON trades(bot_id, entry_time DESC);
CREATE INDEX IF NOT EXISTS idx_bot_symbol ON trades(bot_id, symbol);
CREATE INDEX IF NOT EXISTS idx_entry_time ON trades(entry_time DESC);
CREATE INDEX IF NOT EXISTS idx_exit_time ON trades(exit_time DESC) WHERE exit_time IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_pnl ON trades(pnl) WHERE pnl IS NOT NULL;

-- Execution logs indexes
CREATE INDEX IF NOT EXISTS idx_exec_bot_time ON execution_logs(bot_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_exec_action ON execution_logs(action);

-- Risk metrics indexes
CREATE INDEX IF NOT EXISTS idx_risk_bot_time ON risk_metrics(bot_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_risk_type ON risk_metrics(metric_type);

-- Battle lines indexes
CREATE INDEX IF NOT EXISTS idx_battle_lines_timestamp ON battle_lines(timestamp DESC);

-- Bot registry indexes
CREATE INDEX IF NOT EXISTS idx_bot_active ON bot_registry(active) WHERE active = true;
CREATE INDEX IF NOT EXISTS idx_bot_last_seen ON bot_registry(last_seen DESC);

-- Composite indexes for common queries
CREATE INDEX IF NOT EXISTS idx_trades_daily ON trades(bot_id, entry_time::date) WHERE exit_time IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_active_positions ON trades(bot_id, symbol) WHERE exit_time IS NULL;

-- Partial indexes for performance
CREATE INDEX IF NOT EXISTS idx_winning_trades ON trades(bot_id, pnl) WHERE pnl > 0;
CREATE INDEX IF NOT EXISTS idx_losing_trades ON trades(bot_id, pnl) WHERE pnl < 0;

-- JSON indexes for PostgreSQL (if using JSONB)
-- CREATE INDEX IF NOT EXISTS idx_strategy_details ON trades USING gin(strategy_details);
-- CREATE INDEX IF NOT EXISTS idx_exec_details ON execution_logs USING gin(details);

-- Analyze tables for query planner
ANALYZE trades;
ANALYZE execution_logs;
ANALYZE risk_metrics;
ANALYZE battle_lines;
ANALYZE bot_registry;