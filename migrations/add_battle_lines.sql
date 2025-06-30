-- Add battle lines table for ST0CKG strategy
CREATE TABLE IF NOT EXISTS battle_lines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bot_id VARCHAR(50) NOT NULL,
    symbol VARCHAR(10) NOT NULL,
    date DATE NOT NULL,
    pdh FLOAT NOT NULL,  -- Previous Day High
    pdl FLOAT NOT NULL,  -- Previous Day Low
    overnight_high FLOAT NOT NULL,  -- ES/Futures overnight high
    overnight_low FLOAT NOT NULL,   -- ES/Futures overnight low
    premarket_high FLOAT NOT NULL,  -- Pre-market high
    premarket_low FLOAT NOT NULL,   -- Pre-market low
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(bot_id, symbol, date)
);

-- Add indexes for faster lookups
CREATE INDEX IF NOT EXISTS idx_battle_lines_lookup ON battle_lines(bot_id, symbol, date);
CREATE INDEX IF NOT EXISTS idx_battle_lines_date ON battle_lines(date);

-- Add signal tracking table for analysis
CREATE TABLE IF NOT EXISTS signal_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bot_id VARCHAR(50) NOT NULL,
    symbol VARCHAR(10) NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    signal_type VARCHAR(50) NOT NULL,  -- GAMMA_SQUEEZE, VWAP_RECLAIM, etc.
    signal_score FLOAT NOT NULL,
    signal_details JSON,
    price_at_signal FLOAT NOT NULL,
    battle_line_ref FLOAT,  -- Which battle line triggered it
    taken BOOLEAN DEFAULT FALSE,  -- Whether we traded on this signal
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Add index for signal analysis
CREATE INDEX IF NOT EXISTS idx_signal_history_lookup ON signal_history(bot_id, symbol, timestamp);
CREATE INDEX IF NOT EXISTS idx_signal_history_type ON signal_history(signal_type);