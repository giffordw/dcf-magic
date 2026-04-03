# DCF Magic

A simple DCF (Discounted Cash Flow) calculator inspired by Qualtrim's Simple DCF Calculator, with a portfolio dashboard for tracking multiple stocks.

## Quick Start

```bash
python server.py
```

Open http://localhost:8000

## Pages

### Calculator (`/`)
Manual-entry DCF calculator. Enter EPS, PE, growth rate, desired return, and EPS multiple to see projected returns and entry prices. No API calls — all values entered by hand.

### Portfolio (`/portfolio`)
Track multiple stocks with calculated DCF values. Features:
- Add/edit/remove stocks with per-stock assumptions
- Daily price refresh via FMP (one API call per stock per day, cached)
- Sortable table with Delta % column (difference between entry price and current price)
- All calculations update in real-time

## Setup

1. Get a free API key from [Financial Modeling Prep](https://site.financialmodelingprep.com/pricing-plans)
2. Create a `.env` file in the project root:
   ```
   FMP_API_KEY=your_key_here
   ```
3. Run `python server.py`

## Formulas

All projections use a **5-year horizon**.

| Output | Formula |
|---|---|
| Future EPS | `EPS(TTM) x (1 + growth_rate)^5` |
| Future Price | `Future EPS x EPS Multiple` |
| Return from Today's Price | `(Future Price / Current Price)^(1/5) - 1` |
| Entry Price for X% Return | `Future Price / (1 + desired_return)^5` |
| Delta % | `(Entry Price - Current Price) / Current Price x 100` |

## Data

- **Portfolio data**: stored in `portfolio.json` (auto-created)
- **Price source**: [FMP `/stable/profile`](https://site.financialmodelingprep.com/developer/docs) endpoint (free tier)
- Prices are cached per stock per day to minimize API usage
- All financial inputs (EPS, PE, growth, etc.) are entered manually

## FMP Resources

- [API Documentation](https://site.financialmodelingprep.com/developer/docs)
- [Pricing Plans](https://site.financialmodelingprep.com/pricing-plans)
