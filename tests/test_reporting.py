import pandas as pd
import numpy as np
from dca_backtest.reporting import calculate_metrics

def test_calculate_metrics_basic():
    # Final value: 120, Invested: 100
    dates = pd.date_range("2026-04-13", periods=366, freq="D")
    # Linear growth for equity curve
    equity_curve = pd.Series(np.linspace(0, 120, 366), index=dates)
    total_invested = 100.0
    
    metrics = calculate_metrics(equity_curve, total_invested)
    
    assert metrics["total_invested"] == 100.0
    assert metrics["final_value"] == 120.0
    assert metrics["total_return"] == 0.2 # 20%
    # CAGR for exactly 1 year and 20% growth is 20%
    assert 0.19 < metrics["cagr"] < 0.21
    assert metrics["max_drawdown"] == 0.0 # Linear growth has no drawdown

def test_calculate_metrics_drawdown():
    dates = pd.date_range("2026-04-13", periods=10, freq="D")
    # Equity curve with a 50% drawdown
    values = [100, 110, 120, 60, 70, 80, 100, 110, 120, 130]
    equity_curve = pd.Series(values, index=dates)
    total_invested = 100.0
    
    metrics = calculate_metrics(equity_curve, total_invested)
    # Peak: 120, Trough: 60 -> (60-120)/120 = -0.5
    assert metrics["max_drawdown"] == -0.5
