const express = require('express');
const path = require('path');

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

// Serve the main page
app.get('/', (req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'index.html'));
});

app.listen(PORT, () => {
  console.log(`ST0CK tracker running on port ${PORT}`);
});