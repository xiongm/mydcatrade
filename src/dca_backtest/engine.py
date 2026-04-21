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
    
    # Use the index of the first symbol to define the date range
    # Assume data is aligned or we only iterate over available bars
    first_symbol = plan.symbols[0]
    all_dates = data[first_symbol].index
    start_date = all_dates[0]

    for dt in all_dates:
        # 1. Check for scheduled contribution (Wednesday logic)
        if is_contribution_day(dt, plan.frequency, start_date):
            # Inject cash
            state.cash += plan.contribution_amount
            
            # 2. Execute Purchases at TODAY'S Open price (Wednesday Open)
            # We assume the bar for dt has 'Open' and 'Close'
            for symbol, weight in plan.weights.items():
                if symbol not in data:
                    continue
                
                # Check if price data exists for this day
                # In real backtests, handle missing bars (e.g., Friday-to-Monday)
                try:
                    price = data[symbol].loc[dt, "Open"]
                except KeyError:
                    # If Wednesday is a holiday, bar won't exist in OHLCV frame
                    # The event loop should skip it, and next available day 
                    # will trigger is_contribution_day if it's the next trading day
                    # but is_contribution_day currently strictly checks weekday == 2.
                    # TODO: For V1, assume Wednesday is always a trading day for mock tests.
                    # Handle holidays by checking 'is first bar after scheduled wed' in future V1.1.
                    continue
                
                amount_to_spend = plan.contribution_amount * weight
                
                # Support fractional shares
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
