# USA vs China A-share DCA Research Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a research runner that executes multi-market DCA backtests across U.S. and China broad indexes and sector baskets, fetching FX data for USD-adjusted comparisons, and generating aggregated tables and a Markdown summary.

**Architecture:** A standalone module `research_runner.py` that reads a YAML configuration defining markets, broad indexes, and sector baskets. It iterates through these definitions, uses the existing `run_backtest` engine and `HybridDataSource`, fetches USD/CNY FX data via `yfinance`, calculates performance metrics (including XIRR/money-weighted return), and outputs CSVs and a README to the specified output directory.

**Tech Stack:** Python 3.12, Pandas, PyYAML, yfinance.

---

### Task 1: Dependencies and Configuration

**Files:**
- Modify: `pyproject.toml`
- Create: `configs/us_vs_china_dca.yaml`

- [ ] **Step 1: Add PyYAML dependency and new CLI entry point**

Modify `pyproject.toml` to include `PyYAML>=6.0.1` and `scipy>=1.11` (for optimization/XIRR if needed, though we can compute a simplified money-weighted return using scipy.optimize.newton). Let's use `scipy`. Add `dca-research` to scripts.

```toml
[project]
name = "dca-backtest-system"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
  "numpy>=1.26",
  "pandas>=2.2",
  "yfinance>=0.2.54",
  "akshare>=1.18.56",
  "requests",
  "PyYAML>=6.0.1",
  "scipy>=1.11"
]

[project.optional-dependencies]
dev = [
  "pytest>=8.3",
]

[project.scripts]
dca-backtest = "dca_backtest.cli:main"
dca-download = "dca_backtest.download:main"
dca-research = "dca_backtest.research_runner:main"

[tool.pytest.ini_options]
pythonpath = ["src"]
testpaths = ["tests"]
```

- [ ] **Step 2: Create the YAML configuration file**

Create `configs/us_vs_china_dca.yaml` with the provided configuration.

```yaml
broad_indexes:
  US:
    SPY: {name: "S&P 500 ETF", role: "U.S. large-cap broad market"}
    QQQ: {name: "Nasdaq 100 ETF", role: "U.S. growth / tech-heavy benchmark"}
    IWM: {name: "Russell 2000 ETF", role: "U.S. small-cap benchmark"}
  CN:
    000300.SS: {name: "CSI 300", role: "China A-share large-cap broad market"}
    000905.SS: {name: "CSI 500", role: "China A-share mid-cap benchmark"}
    000852.SS: {name: "CSI 1000", role: "China A-share small/mid-cap benchmark"}
    000688.SS: {name: "STAR 50", role: "China hard-tech / growth benchmark"}

sectors:
  US:
    TECH: {name: "Information Technology", tickers: ["MSFT", "NVDA", "AVGO"]}
    COMMUNICATION: {name: "Communication Services", tickers: ["GOOGL", "META", "NFLX"]}
    CONSUMER_DISCRETIONARY: {name: "Consumer Discretionary", tickers: ["AMZN", "TSLA", "HD"]}
    CONSUMER_STAPLES: {name: "Consumer Staples", tickers: ["WMT", "COST", "PG"]}
    FINANCIALS: {name: "Financials", tickers: ["JPM", "BRK-B", "V"]}
    HEALTHCARE: {name: "Health Care", tickers: ["LLY", "UNH", "JNJ"]}
    INDUSTRIALS: {name: "Industrials", tickers: ["GE", "CAT", "RTX"]}
    ENERGY: {name: "Energy", tickers: ["XOM", "CVX", "COP"]}
    MATERIALS: {name: "Materials", tickers: ["LIN", "SHW", "FCX"]}
    UTILITIES: {name: "Utilities", tickers: ["NEE", "SO", "DUK"]}
    REAL_ESTATE: {name: "Real Estate", tickers: ["PLD", "AMT", "EQIX"]}
  CN:
    TECH: {name: "Information Technology / Semis / Hardware", tickers: ["688981.SS", "002475.SZ", "000725.SZ"]}
    COMMUNICATION: {name: "Communication Services / Telecom", tickers: ["600941.SS", "601728.SS", "600050.SS"]}
    CONSUMER_DISCRETIONARY: {name: "Consumer Discretionary", tickers: ["002594.SZ", "000333.SZ", "000651.SZ"]}
    CONSUMER_STAPLES: {name: "Consumer Staples", tickers: ["600519.SS", "000858.SZ", "600887.SS"]}
    FINANCIALS: {name: "Financials", tickers: ["600036.SS", "601318.SS", "600030.SS"]}
    HEALTHCARE: {name: "Health Care", tickers: ["600276.SS", "300760.SZ", "300015.SZ"]}
    INDUSTRIALS: {name: "Industrials / Advanced Manufacturing", tickers: ["300750.SZ", "300124.SZ", "601668.SS"]}
    ENERGY: {name: "Energy", tickers: ["601857.SS", "600028.SS", "600938.SS"]}
    MATERIALS: {name: "Materials", tickers: ["601899.SS", "600309.SS", "600019.SS"]}
    UTILITIES: {name: "Utilities", tickers: ["600900.SS", "600905.SS", "601985.SS"]}
    REAL_ESTATE: {name: "Real Estate", tickers: ["000002.SZ", "600048.SS", "001979.SZ"]}
```

- [ ] **Step 3: Commit**
```bash
git add pyproject.toml configs/us_vs_china_dca.yaml
git commit -m "feat: add config and dependencies for research runner"
```

---

### Task 2: Implement Research Math Utilities

**Files:**
- Create: `src/dca_backtest/research_math.py`
- Create: `tests/test_research_math.py`

- [ ] **Step 1: Write failing tests for research math**

```python
import pandas as pd
import numpy as np
from dca_backtest.research_math import calculate_xirr, calculate_drawdown_metrics

def test_calculate_xirr():
    dates = pd.to_datetime(["2020-01-01", "2021-01-01", "2022-01-01"])
    cash_flows = [-1000.0, -1000.0, 2200.0] # 10% return roughly
    xirr = calculate_xirr(dates, cash_flows)
    assert 0.09 < xirr < 0.11

def test_calculate_drawdown_metrics():
    equity = pd.Series([100, 120, 60, 90, 150], index=pd.date_range("2020-01-01", periods=5))
    metrics = calculate_drawdown_metrics(equity)
    assert metrics["max_drawdown"] == -0.5  # (60 - 120) / 120
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_research_math.py -v`
Expected: FAIL with "module not found"

- [ ] **Step 3: Write minimal implementation**

```python
import pandas as pd
import numpy as np
from scipy import optimize

def calculate_xirr(dates, cash_flows):
    if len(dates) != len(cash_flows) or len(dates) < 2:
        return 0.0
    days = (dates - dates[0]).days
    years = days / 365.25
    def npv(r):
        return np.sum(cash_flows / ((1 + r) ** years))
    try:
        return optimize.newton(npv, 0.1)
    except (RuntimeError, ValueError):
        return 0.0

def calculate_drawdown_metrics(equity_curve: pd.Series):
    if equity_curve.empty: return {"max_drawdown": 0.0}
    rolling_max = equity_curve.cummax()
    drawdowns = (equity_curve - rolling_max) / rolling_max
    return {"max_drawdown": float(drawdowns.min())}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_research_math.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/dca_backtest/research_math.py tests/test_research_math.py
git commit -m "feat: add research math utilities"
```

---

### Task 3: Implement Core Research Runner

**Files:**
- Create: `src/dca_backtest/research_runner.py`

- [ ] **Step 1: Write the research runner script structure**

```python
import argparse
import yaml
import pandas as pd
import yfinance as yf
from pathlib import Path
from datetime import datetime
from dca_backtest.models import Plan
from dca_backtest.engine import run_backtest
from dca_backtest.data_sources.registry import get_data_source
from dca_backtest.research_math import calculate_xirr, calculate_drawdown_metrics

def fetch_fx_data(start_date: str, end_date: str):
    # Fetch CNY=X for USD to CNY. CNY=X means 1 USD = X CNY.
    # To convert CNY to USD, we divide by this rate.
    print("Fetching FX data...")
    fx = yf.download("CNY=X", start=start_date, end=end_date, auto_adjust=False, progress=False)
    if isinstance(fx.columns, pd.MultiIndex):
        fx.columns = [c[0] if isinstance(c, tuple) else c for c in fx.columns]
    fx_close = fx["Close"]
    fx_close.index = pd.to_datetime(fx_close.index).tz_localize(None).normalize()
    # Forward fill weekend/holiday gaps
    fx_close = fx_close.resample('D').ffill()
    return fx_close

def extract_metrics(plan_name, market, category, group_name, state, data, union_idx, total_contribution, fx_series=None):
    # Calculate daily equity
    equity_values = []
    invested_values = []
    cash_flows_dates = []
    cash_flows_amounts = []
    
    for dt in union_idx:
        today_inv = sum(t.amount for t in state.trades if t.date == dt)
        if today_inv > 0:
            cash_flows_dates.append(dt)
            cash_flows_amounts.append(-today_inv)
        invested_values.append(today_inv)
        
        shares = {s: sum(t.shares for t in state.trades if t.symbol == s and t.date <= dt) for s in plan_name.split("_") if s in data}
        eq = state.cash + sum(q * data[s].loc[dt, "close"] for s, q in shares.items() if s in data and dt in data[s].index)
        equity_values.append(eq)

    curve_df = pd.DataFrame({"equity": equity_values}, index=union_idx)
    final_val = equity_values[-1]
    
    cash_flows_dates.append(union_idx[-1])
    cash_flows_amounts.append(final_val)
    xirr = calculate_xirr(pd.DatetimeIndex(cash_flows_dates), np.array(cash_flows_amounts))
    dd = calculate_drawdown_metrics(curve_df["equity"])
    
    usd_final_val = None
    if fx_series is not None and market == "CN":
        # Divide by FX to get USD
        fx_rate = fx_series.reindex(union_idx, method='ffill').iloc[-1]
        if pd.notna(fx_rate) and fx_rate > 0:
            usd_final_val = final_val / float(fx_rate)
            
    res = {
        "market": market,
        "category": category, # "broad_index" or "sector"
        "name": group_name,
        "strategy_id": plan_name,
        "start_date": union_idx[0].strftime("%Y-%m-%d"),
        "end_date": union_idx[-1].strftime("%Y-%m-%d"),
        "total_contributed": total_contribution,
        "ending_value_local": final_val,
        "ending_value_usd_if_applicable": usd_final_val,
        "total_return_pct": (final_val - total_contribution) / total_contribution if total_contribution > 0 else 0,
        "money_weighted_return_or_xirr": xirr,
        "max_drawdown": dd["max_drawdown"],
    }
    
    return res, curve_df

def run_research(config_path: str, output_dir: str, start_date: str, frequency: str, contribution: float):
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
        
    end_date = datetime.now().strftime("%Y-%m-%d")
    fx_series = fetch_fx_data(start_date, end_date)
    source = get_data_source("hybrid")
    
    all_metrics = []
    
    # Collect all tickers to align dates if needed, or process per group
    # For common start dates, we need the minimum valid start date per group
    
    for category, groups in [("broad_index", config["broad_indexes"]), ("sector", config["sectors"])]:
        for market, market_groups in groups.items():
            for group_name, group_data in market_groups.items():
                tickers = group_data.get("tickers", [group_name])
                plan_name = f"{market}_{category.upper()}_{group_name}"
                print(f"Processing {plan_name}...")
                
                raw_data = source.load_bars(tuple(tickers), start_date=start_date, end_date=end_date)
                
                union_idx = pd.Index([])
                for df in raw_data.values(): union_idx = union_idx.union(df.index)
                if len(union_idx) == 0: continue
                
                data = {s: df.reindex(union_idx).ffill() for s, df in raw_data.items()}
                
                weights = {s: 1.0/len(tickers) for s in tickers}
                plan = Plan(name=plan_name, symbols=tickers, weights=weights, contribution_amount=contribution, frequency=frequency)
                
                state = run_backtest(plan, data)
                total_cap = sum(t.amount for t in state.trades)
                
                metrics, curve = extract_metrics(plan_name, market, category, group_name, state, data, union_idx, total_cap, fx_series)
                all_metrics.append(metrics)
                
    df_metrics = pd.DataFrame(all_metrics)
    
    # Split into tables
    broad_df = df_metrics[df_metrics["category"] == "broad_index"]
    sector_df = df_metrics[df_metrics["category"] == "sector"]
    
    broad_df.to_csv(out / "broad_index_summary.csv", index=False)
    sector_df.to_csv(out / "sector_basket_summary.csv", index=False)
    
    print("Research complete. Check outputs folder.")

def main():
    parser = argparse.ArgumentParser(description="USA vs China DCA Research Runner")
    parser.add_argument("--config", required=True)
    parser.add_argument("--start", default="2015-01-01")
    parser.add_argument("--frequency", default="monthly")
    parser.add_argument("--contribution", type=float, default=1000.0)
    parser.add_argument("--output", default="outputs/us_vs_china_dca")
    args = parser.parse_args()
    run_research(args.config, args.output, args.start, args.frequency, args.contribution)

if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Commit**

```bash
git add src/dca_backtest/research_runner.py
git commit -m "feat: implement research runner core logic"
```

---

### Task 4: Advanced Output Generation (Comparison, Rankings, README)

**Files:**
- Modify: `src/dca_backtest/research_runner.py`

- [ ] **Step 1: Enhance `run_research` to generate comparison and README**

Update `run_research` in `research_runner.py` to join US and CN data by sector name to produce `us_vs_china_sector_comparison.csv`.

```python
    # After generating broad_df and sector_df
    # 3. US vs China Sector Comparison
    us_sectors = sector_df[sector_df["market"] == "US"].set_index("name")
    cn_sectors = sector_df[sector_df["market"] == "CN"].set_index("name")
    
    comp_df = us_sectors.join(cn_sectors, lsuffix="_us", rsuffix="_cn", how="inner").reset_index()
    
    comp_out = []
    for _, row in comp_df.iterrows():
        comp_out.append({
            "sector": row["name"],
            "us_ending_value": row["ending_value_local_us"],
            "china_ending_value_local": row["ending_value_local_cn"],
            "china_ending_value_usd": row["ending_value_usd_if_applicable_cn"],
            "us_total_return_pct": row["total_return_pct_us"],
            "china_total_return_local_pct": row["total_return_pct_cn"],
            "us_max_drawdown": row["max_drawdown_us"],
            "china_max_drawdown": row["max_drawdown_cn"],
            "winner_usd_adjusted": "US" if row["ending_value_local_us"] > row["ending_value_usd_if_applicable_cn"] else "CN",
            "performance_gap_usd_pct": (row["ending_value_local_us"] - row["ending_value_usd_if_applicable_cn"]) / row["ending_value_usd_if_applicable_cn"]
        })
    pd.DataFrame(comp_out).to_csv(out / "us_vs_china_sector_comparison.csv", index=False)

    # Generate basic README
    readme_content = f"""# USA vs China A-share DCA Performance Backtest

## Overview
DCA Backtest from {start_date} to {end_date} at {frequency} frequency with {contribution} per period.

## Broad Index Summary
{broad_df[['market', 'name', 'total_return_pct', 'money_weighted_return_or_xirr']].to_markdown(index=False)}

## Sector Comparison
{pd.DataFrame(comp_out)[['sector', 'us_total_return_pct', 'china_total_return_local_pct', 'winner_usd_adjusted']].to_markdown(index=False)}
"""
    (out / "README.md").write_text(readme_content)
```

- [ ] **Step 2: Commit**

```bash
git add src/dca_backtest/research_runner.py
git commit -m "feat: add comparison logic and README generation to research runner"
```
