from flask import Flask, render_template_string
import json

app = Flask(__name__)

# Monthly targets
MONTHLY_TARGETS = {
    "2025-07": {"start": 5000, "target": 10512, "risk_pct": 20},
    "2025-08": {"start": 10512, "target": 18239, "risk_pct": 15},
    "2025-09": {"start": 18239, "target": 31645, "risk_pct": 10},
    "2025-10": {"start": 31645, "target": 43275, "risk_pct": 10},
    "2025-11": {"start": 43275, "target": 59178, "risk_pct": 5},
    "2025-12": {"start": 59178, "target": 72227, "risk_pct": 5},
    "2026-01": {"start": 72227, "target": 88153, "risk_pct": 3},
    "2026-02": {"start": 88153, "target": 107590, "risk_pct": 3},
    "2026-03": {"start": 107590, "target": 131314, "risk_pct": 3},
    "2026-04": {"start": 131314, "target": 160269, "risk_pct": 3},
    "2026-05": {"start": 160269, "target": 195608, "risk_pct": 3},
    "2026-06": {"start": 195608, "target": 238739, "risk_pct": 3}
}

@app.route('/')
def index():
    with open('public/index.html', 'r') as f:
        html_content = f.read()
    
    # Replace the API call with inline data
    html_content = html_content.replace(
        "await fetch('/api/targets')",
        f"Promise.resolve({{ok: true, json: async () => ({json.dumps(MONTHLY_TARGETS)})}}))"
    )
    
    return html_content

@app.route('/api/targets')
def get_targets():
    return json.dumps(MONTHLY_TARGETS)

if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)