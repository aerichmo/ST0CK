-- Migration: Add multi-bot support to ST0CK database
-- This migration adds bot_id columns to existing tables and creates a bot registry

-- Add bot_id to trades table with default for existing data
ALTER TABLE trades 
ADD COLUMN bot_id VARCHAR(50) NOT NULL DEFAULT 'st0ckg';

-- Add bot_id to execution_logs table
ALTER TABLE execution_logs 
ADD COLUMN bot_id VARCHAR(50) NOT NULL DEFAULT 'st0ckg';

-- Add bot_id to risk_metrics table
ALTER TABLE risk_metrics 
ADD COLUMN bot_id VARCHAR(50) NOT NULL DEFAULT 'st0ckg';

-- Create bot registry table
CREATE TABLE IF NOT EXISTS bot_registry (
    bot_id VARCHAR(50) PRIMARY KEY,
    bot_name VARCHAR(100) NOT NULL,
    strategy_type VARCHAR(100) NOT NULL,
    alpaca_account VARCHAR(100),
    is_active BOOLEAN DEFAULT true,
    config JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for performance
CREATE INDEX idx_trades_bot_id ON trades(bot_id);
CREATE INDEX idx_execution_logs_bot_id ON execution_logs(bot_id);
CREATE INDEX idx_risk_metrics_bot_id ON risk_metrics(bot_id);
CREATE INDEX idx_trades_bot_timestamp ON trades(bot_id, timestamp);

-- Insert initial bot configurations
INSERT INTO bot_registry (bot_id, bot_name, strategy_type, alpaca_account, config) 
VALUES 
    ('st0ckg', 'ST0CK-G Opening Range Breakout', 'opening_range_breakout', 'primary', 
     '{"trading_window": {"start": "09:40", "end": "10:30"}, "position_sizing": {"max_risk_per_trade": 0.02}}'),
    ('st0cka', 'ST0CK-A [Strategy TBD]', 'tbd', 'secondary', 
     '{"active": false}')
ON CONFLICT (bot_id) DO NOTHING;

-- Create a view for bot-specific trades
CREATE OR REPLACE VIEW bot_trades AS
SELECT 
    bot_id,
    DATE(timestamp) as trade_date,
    COUNT(*) as trade_count,
    SUM(CASE WHEN profit_loss > 0 THEN 1 ELSE 0 END) as winning_trades,
    SUM(CASE WHEN profit_loss < 0 THEN 1 ELSE 0 END) as losing_trades,
    SUM(profit_loss) as total_pnl,
    AVG(profit_loss) as avg_pnl
FROM trades
GROUP BY bot_id, DATE(timestamp);

-- Update trigger for updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_bot_registry_updated_at BEFORE UPDATE
    ON bot_registry FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();