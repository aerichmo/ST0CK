const express = require('express');
const path = require('path');
const https = require('https');

const app = express();
const PORT = process.env.PORT || 10000;

// Monthly targets data
const MONTHLY_TARGETS = {
  "2025-07": { start: 5000, target: 10512, risk_pct: 20, actual: null },
  "2025-08": { start: 10512, target: 18239, risk_pct: 15, actual: null },
  "2025-09": { start: 18239, target: 31645, risk_pct: 10, actual: null },
  "2025-10": { start: 31645, target: 43275, risk_pct: 10, actual: null },
  "2025-11": { start: 43275, target: 59178, risk_pct: 5, actual: null },
  "2025-12": { start: 59178, target: 72227, risk_pct: 5, actual: null },
  "2026-01": { start: 72227, target: 88153, risk_pct: 3, actual: null },
  "2026-02": { start: 88153, target: 107590, risk_pct: 3, actual: null },
  "2026-03": { start: 107590, target: 131314, risk_pct: 3, actual: null },
  "2026-04": { start: 131314, target: 160269, risk_pct: 3, actual: null },
  "2026-05": { start: 160269, target: 195608, risk_pct: 3, actual: null },
  "2026-06": { start: 195608, target: 238739, risk_pct: 3, actual: null }
};

// Serve static files
app.use(express.static('public'));

// API endpoint for monthly targets
app.get('/api/targets', (req, res) => {
  res.json(MONTHLY_TARGETS);
});

// API endpoint to update actual results (for future use)
app.post('/api/update/:month', express.json(), (req, res) => {
  const month = req.params.month;
  const { actual } = req.body;
  
  if (MONTHLY_TARGETS[month]) {
    MONTHLY_TARGETS[month].actual = actual;
    res.json({ success: true, month, actual });
  } else {
    res.status(404).json({ error: 'Month not found' });
  }
});

// API endpoint for SPY data (using Yahoo Finance API)
app.get('/api/spy-data', async (req, res) => {
  try {
    // For demo purposes, return sample data
    // In production, this would fetch from Yahoo Finance or Alpaca
    const now = Date.now() / 1000;
    const data = [];
    
    // Generate 5-minute bars for the last trading day
    for (let i = 78; i >= 0; i--) { // 78 five-minute bars in a trading day
      const time = now - (i * 300); // 5 minutes = 300 seconds
      const basePrice = 450 + Math.sin(i / 10) * 5;
      const volatility = 0.001;
      
      data.push({
        time: Math.floor(time),
        open: basePrice + (Math.random() - 0.5) * volatility * basePrice,
        high: basePrice + Math.random() * volatility * basePrice * 2,
        low: basePrice - Math.random() * volatility * basePrice * 2,
        close: basePrice + (Math.random() - 0.5) * volatility * basePrice,
        volume: Math.floor(Math.random() * 1000000)
      });
    }
    
    res.json({ data, symbol: 'SPY' });
  } catch (error) {
    res.status(500).json({ error: 'Failed to fetch SPY data' });
  }
});

// Serve static files from public directory
app.use(express.static('public'));

// Serve the main page
app.get('/', (req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'index.html'));
});

app.listen(PORT, () => {
  console.log(`ST0CK tracker running on port ${PORT}`);
});