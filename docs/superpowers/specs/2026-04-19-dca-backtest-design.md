# Design Spec: DCA Backtest System (V1)

## 1. Purpose
A specialized backtesting engine for Dollar Cost Averaging (DCA) and long-term accumulation strategies. This system is designed to be separate from tactical/signal-driven engines, focusing on contribution schedules, multi-asset allocation, and long-horizon portfolio growth.

## 2. Core Concepts
- **Plan**: Defines the investment strategy (symbols, weights, contribution amount, frequency).
- **Schedule**: Logic for determining contribution dates (Wednesday-based: Weekly, Biweekly, Monthly).
- **Engine**: A state machine that iterates through time, injecting cash on scheduled dates and purchasing assets.
- **Portfolio State**: Tracks cash balance, share counts per symbol, and total market value over time.

## 3. Architecture

### 3.1 Data Flow
1. **Load Data**: Fetch OHLCV bars for all symbols in the plan universe using the Data Source Registry.
2. **Initialize Engine**: Set starting capital (default $0) and load the Plan configuration.
3. **Event Loop**: Iterate through every trading day in the data range.
   - Check if today is a scheduled contribution day (Wednesday).
   - If yes: Add contribution amount to cash balance.
   - Execute Purchases: Calculate share quantities based on fixed target weights using today's **Open** price.
   - Update State: Record trades and update cash/shares.
   - Calculate Daily Value: Compute total portfolio value (cash + shares * close price) for the daily equity curve.
4. **Finalize**: Calculate aggregate performance metrics (Total Invested, CAGR, Max Drawdown).
5. **Report**: Write results bundle (CSV, JSON, MD, HTML).

### 3.2 Key Components
- `dca_backtest.engine`: The main execution loop and state management.
- `dca_backtest.schedules`: Logic for Weekly, Biweekly, and First-Wednesday-of-Month rules.
- `dca_backtest.plans`: Configuration model for DCA plans.
- `dca_backtest.data_sources`: Reused registry pattern for `yfinance`, `csv`, and `parquet`.
- `dca_backtest.results`: Reused bundle writer and HTML portal generator.

## 4. Implementation Details

### 4.1 Contribution Logic (Wednesday Open)
- Contributions are added to cash on the morning of the scheduled Wednesday.
- Purchases are executed immediately at the **Open** price of that same Wednesday.
- If Wednesday is a market holiday, the contribution and purchase move to the **next available trading day**.

### 4.2 Allocation (Accumulation Only)
- For each contribution, the new cash is split according to target weights.
- `shares_to_buy = (contribution_cash * weight) / open_price`.
- No selling of existing shares occurs (no rebalancing).
- Fractional shares will be supported in the engine (standard for DCA backtests) but can be toggled to integer-only in the future.

### 4.3 Metrics
- **Total Invested**: Cumulative sum of all contributions.
- **Portfolio Value**: Final market value of all holdings + remaining cash.
- **Unrealized Gain/Loss**: (Portfolio Value - Total Invested) / Total Invested.
- **CAGR**: Compound Annual Growth Rate based on the first contribution date to the end date.
- **Max Drawdown**: Peak-to-trough decline of the daily equity curve.

## 5. File Structure (New)
```text
src/
  dca_backtest/
    cli.py           # Entry point
    config.py        # Global settings
    engine.py        # Backtest loop
    schedules.py     # Date logic
    models.py        # Plan and State definitions
    data_sources/    # Pluggable loaders
    results/         # Bundle writer and indexer
    reporting.py     # Metric calculations
tests/
  test_engine.py
  test_schedules.py
  test_data_sources.py
```

## 6. Success Criteria
- Ability to run a backtest for a 60/40 SPY/TLT portfolio with weekly $100 contributions.
- Generation of a daily equity curve CSV.
- Production of a summary report showing the final portfolio value vs total invested.
- Clean separation from the previous `mean_reversion` package.
