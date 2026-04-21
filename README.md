# 📈 Global Portfolio DCA Backtest System

A professional-grade, multi-market backtesting engine for Dollar Cost Averaging (DCA) and long-term accumulation strategies. Compare your steady contributions against Lump Sum and Windfall scenarios with rich, interactive reporting.

## ✨ Key Features

*   **Global Market Support:** Backtest **US Equities**, **Crypto** (via yfinance), and **Chinese A-shares/Funds** (via AkShare).
*   **Intelligent Benchmarking:** Automatically compares your DCA plan against a **Lump Sum** or **Windfall** (installment-based) baseline to calculate your **DCA Alpha**.
*   **Robust Reporting:** Generates interactive HTML reports with dual-series charts (Portfolio Value vs. Cost Basis) and detailed monthly statements.
*   **Offline-First:** Built-in `dca-download` tool to cache market data locally for fast, offline backtesting.
*   **Advanced Logic:** Handles fractional shares, automatic data alignment across markets, and market-specific adjustments (HFQ for A-shares).

---

## 🚀 Quick Start

### 1. Setup Environment
This project uses `uv` for high-performance dependency management.

```bash
# Clone and enter the repo
git clone <your-repo-url>
cd mydcatrade

# Create and activate venv
uv venv --prompt "mydcatrade"
source .venv/bin/activate

# Install in editable mode
uv pip install -e .
uv pip install pyarrow
```

### 2. Run your first Backtest
```bash
dca-backtest --assets SPY:500 QQQ:500 --frequency monthly
```

---

## 📈 Usage Examples

### A. Multi-Market Portfolio
Mix US Stocks, Crypto, and Chinese Funds in a single plan.
```bash
dca-backtest --assets VTI:500 BTC-USD:200 009504:1000 --currency RMB
```

### B. "Windfall" Comparison
Should you invest your savings all at once or over 6 months? Use `--lump-sum-span`.
```bash
dca-backtest --assets VOO:1000 --lump-sum-span 6 --start-date 2022-01-01
```

### C. Chinese A-Shares & Funds
The system auto-detects 6-digit codes and routes them to AkShare with back-adjustment.
```bash
# China Merchants Bank (Stock)
dca-backtest --assets 600036:1000 --currency RMB

# Gold ETF Feeder (Fund)
dca-backtest --assets 009504:1000 --currency RMB
```

---

## 🛠️ Tools & Commands

### `dca-backtest`
The main execution engine.

| Flag | Description | Default |
|------|-------------|---------|
| `--assets` | List of `SYMBOL:AMOUNT` pairs | `SPY:1000` |
| `--frequency` | `weekly`, `biweekly`, or `monthly` | `monthly` |
| `--currency` | Report symbol: `USD` or `RMB` | `USD` |
| `--lump-sum-span` | Spread benchmark over N installments | `1` |
| `--start-date` | Start date (YYYY-MM-DD) | Last 5 Years |
| `--end-date` | End date (YYYY-MM-DD) | Today |

### `dca-download`
Cache data locally to enable offline mode and faster runs.
```bash
# Cache 10 years of data
dca-download SPY AAPL BTC-USD 600036
```

---

## 📊 Viewing Results

Every run generates a structured results bundle in the `results/` directory.

1.  **Global Portal:** Open `results/index.html` to see a leaderboard of all your backtests.
2.  **Detailed Reports:** Open `results/<plan_name>/latest/report.html` for:
    *   **7-Metric Hero Dashboard:** ROI, CAGR, Max Drawdown, and DCA Alpha.
    *   **Growth Charts:** Interactive Portfolio Value vs. Cost Basis.
    *   **Asset Breakdown:** Target vs. Actual weights (Drift analysis).
    *   **Monthly Statements:** Historical ledger of every contribution.

```bash
# Open the global dashboard
open results/index.html
```

---

## 🧪 Development & Testing

```bash
# Run the core test suite
pytest tests/ -v
```
