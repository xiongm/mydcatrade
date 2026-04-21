import numpy as np
import pandas as pd
from typing import Dict

def calculate_metrics(equity_curve: pd.Series, total_invested: float) -> Dict[str, float]:
    """
    Calculates key performance metrics for a DCA backtest.
    """
    if equity_curve.empty:
        return {
            "total_invested": total_invested,
            "final_value": 0.0,
            "total_return": 0.0,
            "cagr": 0.0,
            "max_drawdown": 0.0
        }
    
    final_value = float(equity_curve.iloc[-1])
    total_return = (final_value - total_invested) / total_invested if total_invested > 0 else 0.0
    
    # CAGR calculation
    # Based on the first date in the equity curve to the last
    days = (equity_curve.index[-1] - equity_curve.index[0]).days
    years = days / 365.25
    
    # CAGR = (End Value / Start Value) ^ (1 / years) - 1
    # For DCA, 'Start Value' is problematic. We use 'Total Invested' as a proxy 
    # for money-weighted performance, but standard CAGR often uses initial value.
    # Here we follow the plan's instruction: (final_value / total_invested) ** (1/years) - 1
    if years > 0 and total_invested > 0 and final_value > 0:
        cagr = (final_value / total_invested) ** (1/years) - 1
    else:
        cagr = 0.0
    
    # Drawdown
    rolling_max = equity_curve.cummax()
    drawdown = (equity_curve - rolling_max) / rolling_max
    max_drawdown = float(drawdown.min())
    
    return {
        "total_invested": total_invested,
        "final_value": final_value,
        "total_return": total_return,
        "cagr": float(cagr),
        "max_drawdown": max_drawdown
    }
