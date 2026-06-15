# Healthcare Markets + Nursing Workforce Command Center

Static GitHub Pages dashboard for monitoring:

- S&P 500 Health Care Select Sector Index, MSCI World Health Care proxy, and Nifty Healthcare proxy/latest available data
- 12-month performance, volatility, correlation matrix, 30-day moving-average deviation alerts
- Top-5 holdings valuation comparison with P/E and available earnings-surprise data
- 2026 nursing workforce pressure by state, license group, and setting
- Nursing career-demand scorecard through 2034, ROI proxy, and educational-attainment shift

## Run locally

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python src/update_data.py
python src/build_static.py
python -m http.server 8000 -d docs
```

Open http://localhost:8000.

## Refresh cadence

GitHub Actions runs `src/update_data.py` and `src/build_static.py` every 30 days and on manual workflow dispatch, then redeploys GitHub Pages.

## Governance and data limits

- No PHI is used.
- Financial data is informational only, not investment advice.
- State nursing shortage percentages are planning proxies when official state shortage data is unavailable or source downloads are blocked.
- MSCI World Health Care uses IXJ ETF as a public proxy.
- Nifty Healthcare historical charting uses the closest available Yahoo public healthcare/pharma proxy when full NIFTY_HEALTHCARE.NS history is unavailable.
