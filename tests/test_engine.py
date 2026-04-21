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
    
    dates = pd.date_range("2026-04-13", periods=5, freq="D")
    data = {
        "SPY": pd.DataFrame({
            "open": [10.0, 10.0, 10.0, 10.0, 10.0],
            "close": [11.0, 11.0, 11.0, 11.0, 11.0],
            "high": [11.0]*5, "low": [9.0]*5, "volume": [1000]*5
        }, index=dates)
    }
    
    state = run_backtest(plan, data)
    
    assert state.shares["SPY"] == 10.0
    assert state.cash == 0.0
    assert len(state.trades) == 1

def test_engine_multi_asset_accumulation():
    plan = Plan(
        name="test_multi",
        symbols=["SPY", "TLT"],
        weights={"SPY": 0.6, "TLT": 0.4},
        contribution_amount=1000.0,
        frequency="weekly"
    )
    
    dates = pd.date_range("2026-04-13", periods=5, freq="D")
    data = {
        "SPY": pd.DataFrame({"open": [100.0]*5, "close": [105.0]*5, "high": [106.0]*5, "low": [99.0]*5, "volume": [1000]*5}, index=dates),
        "TLT": pd.DataFrame({"open": [50.0]*5, "close": [52.0]*5, "high": [53.0]*5, "low": [49.0]*5, "volume": [1000]*5}, index=dates)
    }
    
    state = run_backtest(plan, data)
    
    assert state.shares["SPY"] == 6.0
    assert state.shares["TLT"] == 8.0
    assert state.cash == 0.0
    assert len(state.trades) == 2
