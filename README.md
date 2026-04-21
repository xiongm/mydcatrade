# Portfolio Backtest System

A dual-purpose backtesting system for long-term Dollar Cost Averaging (DCA) and tactical Mean Reversion strategies.

## 🚀 Quick Start

### 1. Setup Environment
This project uses `uv` for fast dependency management.
```bash
# Create and activate venv
uv venv --prompt "mydcatrade"
source .venv/bin/activate

# Install in editable mode
uv pip install -e .
uv pip install pyarrow
```

### 2. Run your first DCA Backtest
```bash
dca-backtest --symbols SPY --amount 100 --frequency weekly
```

---

## 📈 DCA Backtest (Accumulation)

The DCA engine supports multi-asset portfolios with fixed contribution schedules on Wednesdays.

### Examples

#### A. Multi-asset with Grouped Allocation (Preferred)
Define your portfolio and dollar amounts in a single, safe argument.
```bash
dca-backtest --assets SPY:600 QQQ:400 --frequency monthly
```

#### C. Crypto Backtest
Test Bitcoin and Ethereum DCA strategies using the `-USD` suffix.
```bash
dca-backtest --assets BTC-USD:500 ETH-USD:300 --frequency weekly
```

#### D. Specific Date Range
Test how a DCA plan performed during a specific period.
```bash
dca-backtest --assets AAPL:200 --frequency biweekly --start-date 2022-01-01 --end-date 2023-12-31
```

#### D. Using Local CSV Data
If you have data in `data/csv/MYSTOCK.csv`.
```bash
dca-backtest --symbols MYSTOCK --amount 100 --data-source csv
```

### Options Reference
| Flag | Description | Default |
|------|-------------|---------|
| `--symbols` | List of tickers to buy | `SPY` |
| `--amount` | Total $ to invest per cycle | `1000.0` |
| `--amounts` | Exact $ per symbol (overrides `--amount`) | None |
| `--weights` | Target % per symbol | Equal |
| `--frequency` | `weekly`, `biweekly`, or `monthly` | `monthly` |
| `--start-date` | Start date (YYYY-MM-DD) | ~5 years ago |
| `--end-date` | End date (YYYY-MM-DD) | Today |
| `--data-source`| `yfinance`, `csv`, or `parquet` | `yfinance` |

---

## 🤖 Mean Reversion Backtest (Tactical)

The repository also includes the original mean reversion engine for signal-driven trading.

```bash
# Run the default mean reversion strategy
mean-reversion-backtest --strategy mean_reversion_v1
```

---

## 📊 Viewing Results

Every run generates a structured results bundle in the `results/` directory.

1.  **Global Portal:** Open `results/index.html` in your browser to see a leaderboard of all your DCA plans and Mean Reversion strategies.
2.  **Detailed Reports:** Each run has its own folder containing:
    *   `report.html`: Visual summary with equity and drawdown charts.
    *   `summary.md`: Human-readable performance metrics.
    *   `trades.csv`: Full ledger of every purchase made.
    *   `equity_curve.csv`: Daily portfolio valuation.

```bash
# Open the results dashboard
open results/index.html
```
