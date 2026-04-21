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
    
    # Mock data for one week
    # 2026-04-13 (Mon) to 2026-04-17 (Fri)
    # 2026-04-15 is Wed
    dates = pd.date_range("2026-04-13", periods=5, freq="D")
    data = {
        "SPY": pd.DataFrame({
            "Open": [10.0, 10.0, 10.0, 10.0, 10.0],
            "Close": [11.0, 11.0, 11.0, 11.0, 11.0]
        }, index=dates)
    }
    
    state = run_backtest(plan, data)
    
    # Verify shares bought on Wednesday
    # $100 / $10 open price = 10 shares
    assert state.shares["SPY"] == 10.0
    assert state.cash == 0.0
    assert len(state.trades) == 1
    assert state.trades[0].symbol == "SPY"
    assert state.trades[0].shares == 10.0
    assert state.trades[0].price == 10.0
    assert state.trades[0].amount == 100.0

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
        "SPY": pd.DataFrame({"Open": [100.0]*5, "Close": [105.0]*5}, index=dates),
        "TLT": pd.DataFrame({"Open": [50.0]*5, "Close": [52.0]*5}, index=dates)
    }
    
    state = run_backtest(plan, data)
    
    # SPY: 0.6 * 1000 = $600 -> $600 / 100 = 6 shares
    # TLT: 0.4 * 1000 = $400 -> $400 / 50 = 8 shares
    assert state.shares["SPY"] == 6.0
    assert state.shares["TLT"] == 8.0
    assert state.cash == 0.0
    assert len(state.trades) == 2
