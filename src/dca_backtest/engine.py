import pandas as pd
from typing import Dict, Optional, List
from datetime import datetime
from dca_backtest.models import Plan, PortfolioState, Trade
from dca_backtest.schedules import is_contribution_day

def run_backtest(plan: Plan, data: Dict[str, pd.DataFrame], initial_cash: float = 0.0) -> PortfolioState:
    """
    Executes a DCA backtest based on a plan and price data.
    Iterates day-by-day (event-driven).
    """
    state = PortfolioState(cash=initial_cash)
    
    first_symbol = plan.symbols[0]
    all_dates = data[first_symbol].index
    start_date = all_dates[0]

    for dt in all_dates:
        if is_contribution_day(dt, plan.frequency, start_date):
            state.cash += plan.contribution_amount
            
            for symbol, weight in plan.weights.items():
                if symbol not in data:
                    continue
                
                try:
                    price = data[symbol].loc[dt, "open"]
                except KeyError:
                    continue
                
                amount_to_spend = plan.contribution_amount * weight
                shares_bought = amount_to_spend / price
                
                state.shares[symbol] = state.shares.get(symbol, 0.0) + shares_bought
                state.trades.append(Trade(
                    date=dt,
                    symbol=symbol,
                    shares=shares_bought,
                    price=price,
                    amount=amount_to_spend
                ))
                state.cash -= amount_to_spend
                
    return state
