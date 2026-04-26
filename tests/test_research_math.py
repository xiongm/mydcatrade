import pandas as pd
import numpy as np
from dca_backtest.research_math import calculate_xirr, calculate_drawdown_metrics

def test_calculate_xirr():
    dates = pd.to_datetime(["2020-01-01", "2021-01-01", "2022-01-01"])
    cash_flows = [-1000.0, -1000.0, 2200.0] # 6.52% return
    xirr = calculate_xirr(dates, cash_flows)
    assert 0.06 < xirr < 0.07

def test_calculate_drawdown_metrics():
    equity = pd.Series([100, 120, 60, 90, 150], index=pd.date_range("2020-01-01", periods=5))
    metrics = calculate_drawdown_metrics(equity)
    assert metrics["max_drawdown"] == -0.5  # (60 - 120) / 120
