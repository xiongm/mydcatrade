import pandas as pd
import numpy as np

def calculate_xirr(dates, cash_flows):
    if len(dates) != len(cash_flows) or len(dates) < 2:
        return 0.0
    days = (dates - dates[0]).days
    years = days / 365.25
    
    def npv(r):
        return np.sum(cash_flows / ((1 + r) ** years))
    
    def npv_derivative(r):
        return np.sum(-years * cash_flows / ((1 + r) ** (years + 1)))

    # Simple Newton-Raphson
    r = 0.1
    for _ in range(100):
        try:
            val = npv(r)
            deriv = npv_derivative(r)
            if abs(val) < 1e-6:
                return r
            r = r - val / deriv
        except (ZeroDivisionError, ValueError, OverflowError):
            return 0.0
    return 0.0

def calculate_drawdown_metrics(equity_curve: pd.Series):
    if equity_curve.empty: return {"max_drawdown": 0.0}
    rolling_max = equity_curve.cummax()
    drawdowns = (equity_curve - rolling_max) / rolling_max
    return {"max_drawdown": float(drawdowns.min())}
