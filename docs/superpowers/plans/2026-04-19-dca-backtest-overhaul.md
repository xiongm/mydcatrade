# DCA Backtest System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a specialized DCA backtest engine that supports multi-asset fixed-weight allocation on a Wednesday-based schedule (Weekly, Biweekly, Monthly).

**Architecture:** An event-driven daily loop that checks for scheduled contribution dates, injects cash, and executes purchases at the market Open price. Daily equity curves are tracked for performance reporting.

**Tech Stack:** Python 3.12, Pandas, NumPy, yfinance.

---

### Task 1: Project Scaffolding & Core Models

**Files:**
- Create: `src/dca_backtest/models.py`
- Create: `src/dca_backtest/__init__.py`
- Modify: `pyproject.toml`

- [ ] **Step 1: Define core data models**
```python
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List

@dataclass
class Plan:
    name: str
    symbols: List[str]
    weights: Dict[str, float]
    contribution_amount: float
    frequency: str  # 'weekly', 'biweekly', 'monthly'

@dataclass
class Trade:
    date: datetime
    symbol: str
    shares: float
    price: float
    amount: float

@dataclass
class PortfolioState:
    cash: float = 0.0
    shares: Dict[str, float] = field(default_factory=dict)
    trades: List[Trade] = field(default_factory=list)
```

- [ ] **Step 2: Update pyproject.toml to include dca-backtest entrypoint**
```toml
[project.scripts]
dca-backtest = "dca_backtest.cli:main"
```

- [ ] **Step 3: Commit**
```bash
git add pyproject.toml src/dca_backtest/
git commit -m "feat: scaffold dca_backtest and define core models"
```

---

### Task 2: Contribution Schedule Logic

**Files:**
- Create: `src/dca_backtest/schedules.py`
- Create: `tests/test_schedules.py`

- [ ] **Step 1: Write failing tests for schedules**
```python
from datetime import datetime
from dca_backtest.schedules import is_contribution_day

def test_weekly_schedule():
    # 2026-04-15 is a Wednesday
    assert is_contribution_day(datetime(2026, 4, 15), 'weekly') is True
    # 2026-04-16 is a Thursday
    assert is_contribution_day(datetime(2026, 4, 16), 'weekly') is False

def test_monthly_schedule():
    # First Wednesday of April 2026 is April 1st
    assert is_contribution_day(datetime(2026, 4, 1), 'monthly') is True
    # Second Wednesday is not
    assert is_contribution_day(datetime(2026, 4, 8), 'monthly') is False
```

- [ ] **Step 2: Implement schedule logic**
```python
from datetime import datetime, timedelta

def is_contribution_day(dt: datetime, frequency: str, start_date: datetime = None) -> bool:
    if dt.weekday() != 2:  # Wednesday
        return False
    
    if frequency == 'weekly':
        return True
    
    if frequency == 'monthly':
        # Check if it's the first Wednesday
        return dt.day <= 7
    
    if frequency == 'biweekly':
        if start_date is None:
            return True # Default to every Wed if no start_date
        days_since = (dt - start_date).days
        return (days_since // 7) % 2 == 0
    
    return False
```

- [ ] **Step 3: Run tests and verify**
Run: `pytest tests/test_schedules.py`

- [ ] **Step 4: Commit**
```bash
git add src/dca_backtest/schedules.py tests/test_schedules.py
git commit -m "feat: implement wednesday-based contribution schedules"
```

---

### Task 3: Core Backtest Engine (Daily Loop)

**Files:**
- Create: `src/dca_backtest/engine.py`
- Create: `tests/test_engine.py`

- [ ] **Step 1: Write failing test for engine**
```python
import pandas as pd
from datetime import datetime
from dca_backtest.engine import run_backtest
from dca_backtest.models import Plan

def test_engine_basic_accumulation():
    plan = Plan(
        name="test_plan",
        symbols=["SPY"],
        weights={"SPY": 1.0},
        contribution_amount=100.0,
        frequency="weekly"
    )
    # Mock data: 2 Wednesdays
    data = {
        "SPY": pd.DataFrame({
            "Open": [10.0, 10.0, 10.0, 10.0, 10.0],
            "Close": [11.0, 11.0, 11.0, 11.0, 11.0]
        }, index=pd.date_range("2026-04-13", periods=5, freq="D"))
    }
    # 2026-04-15 is Wed
    state = run_backtest(plan, data)
    assert state.cash == 0.0
    assert state.shares["SPY"] == 10.0 # $100 / $10 open
```

- [ ] **Step 2: Implement engine loop**
```python
import pandas as pd
from typing import Dict
from dca_backtest.models import Plan, PortfolioState, Trade
from dca_backtest.schedules import is_contribution_day

def run_backtest(plan: Plan, data: Dict[str, pd.DataFrame]) -> PortfolioState:
    state = PortfolioState()
    # Align dates
    all_dates = sorted(data[plan.symbols[0]].index)
    start_date = all_dates[0]

    for dt in all_dates:
        # 1. Contribution
        if is_contribution_day(dt, plan.frequency, start_date):
            state.cash += plan.contribution_amount
            
            # 2. Execute Purchases at Open
            for symbol, weight in plan.weights.items():
                price = data[symbol].loc[dt, "Open"]
                amount_to_spend = plan.contribution_amount * weight
                shares = amount_to_spend / price
                
                state.shares[symbol] = state.shares.get(symbol, 0.0) + shares
                state.trades.append(Trade(dt, symbol, shares, price, amount_to_spend))
                state.cash -= amount_to_spend
                
    return state
```

- [ ] **Step 3: Run tests and verify**
Run: `pytest tests/test_engine.py`

- [ ] **Step 4: Commit**
```bash
git add src/dca_backtest/engine.py tests/test_engine.py
git commit -m "feat: implement core dca engine daily loop"
```

---

### Task 4: Metrics & Reporting

**Files:**
- Create: `src/dca_backtest/reporting.py`
- Create: `tests/test_reporting.py`

- [ ] **Step 1: Implement performance metric calculations**
```python
import numpy as np
import pandas as pd

def calculate_metrics(equity_curve: pd.Series, total_invested: float):
    final_value = equity_curve.iloc[-1]
    total_return = (final_value - total_invested) / total_invested if total_invested > 0 else 0
    
    # CAGR calculation
    days = (equity_curve.index[-1] - equity_curve.index[0]).days
    years = days / 365.25
    cagr = (final_value / total_invested) ** (1/years) - 1 if years > 0 and total_invested > 0 else 0
    
    # Drawdown
    rolling_max = equity_curve.cummax()
    drawdown = (equity_curve - rolling_max) / rolling_max
    max_drawdown = drawdown.min()
    
    return {
        "total_invested": total_invested,
        "final_value": final_value,
        "total_return": total_return,
        "cagr": cagr,
        "max_drawdown": max_drawdown
    }
```

- [ ] **Step 2: Commit**
```bash
git add src/dca_backtest/reporting.py
git commit -m "feat: add performance reporting metrics"
```

---

### Task 5: Result Bundle & CLI Integration

**Files:**
- Create: `src/dca_backtest/cli.py`
- Create: `src/dca_backtest/results/writer.py` (Reuse pattern from mean_reversion)

- [ ] **Step 1: Adapt Result Writer for DCA**
Reuse `src/mean_reversion/results/` logic but update `models.py` to use `PortfolioState` and DCA metrics.

- [ ] **Step 2: Implement CLI orchestrator**
```python
import argparse
from dca_backtest.engine import run_backtest
from dca_backtest.models import Plan
# ... imports for data sources and result writer ...

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", nargs="+", default=["SPY"])
    parser.add_argument("--weights", nargs="+", type=float, default=[1.0])
    parser.add_argument("--amount", type=float, default=1000.0)
    parser.add_argument("--frequency", default="monthly")
    args = parser.parse_args()
    
    # 1. Load Data
    # 2. Run Backtest
    # 3. Generate Report
    print("DCA Backtest Complete.")
```

- [ ] **Step 3: Commit**
```bash
git add src/dca_backtest/cli.py
git commit -m "feat: add CLI and result bundle output"
```
