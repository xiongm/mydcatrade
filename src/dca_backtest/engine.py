import pandas as pd
from typing import Dict, Optional, List
from datetime import datetime
from dca_backtest.models import Plan, PortfolioState, Trade
from dca_backtest.schedules import is_contribution_day

def run_backtest(
    plan: Plan, 
    data: Dict[str, pd.DataFrame], 
    dividends: Optional[Dict[str, pd.Series]] = None,
    initial_cash: float = 0.0,
    contribution_limit: Optional[int] = None,
    reinvest_dividends: bool = False
) -> PortfolioState:
    """
    Executes a DCA backtest with support for Dividends and DRIP.
    """
    state = PortfolioState(cash=initial_cash)
    state.dividend_income = 0.0
    state.dividend_shares: Dict[str, float] = {} # Track shares bought via dividends
    
    first_symbol = plan.symbols[0]
    all_dates = data[first_symbol].index
    start_date = all_dates[0]
    
    contributions_made = 0

    for dt in all_dates:
        # 1. Process Dividends (on Ex-Date)
        if dividends:
            for symbol in plan.symbols:
                if symbol in dividends and dt in dividends[symbol].index:
                    div_per_share = dividends[symbol].loc[dt]
                    total_shares = state.shares.get(symbol, 0.0)
                    payout = total_shares * div_per_share
                    
                    if payout > 0:
                        state.dividend_income += payout
                        if reinvest_dividends:
                            # DRIP: Buy at current Open price
                            price = data[symbol].loc[dt, "open"]
                            if pd.isna(price) or price <= 0:
                                state.cash += payout
                            else:
                                new_shares = payout / price
                                state.shares[symbol] = total_shares + new_shares
                                state.dividend_shares[symbol] = state.dividend_shares.get(symbol, 0.0) + new_shares
                                # Record as a non-cash contribution trade
                                state.trades.append(Trade(date=dt, symbol=symbol, shares=new_shares, price=price, amount=0.0))
                        else:
                            # Keep as cash
                            state.cash += payout

        # 2. Process Scheduled Contribution
        if is_contribution_day(dt, plan.frequency, start_date):
            if contribution_limit is None or contributions_made < contribution_limit:
                state.cash += plan.contribution_amount
                contributions_made += 1
            
                for symbol, weight in plan.weights.items():
                    if symbol not in data: continue
                    try:
                        price = data[symbol].loc[dt, "open"]
                        if pd.isna(price) or price <= 0:
                            continue
                        amount_to_spend = plan.contribution_amount * weight
                        shares_bought = amount_to_spend / price
                        
                        state.shares[symbol] = state.shares.get(symbol, 0.0) + shares_bought
                        state.trades.append(Trade(date=dt, symbol=symbol, shares=shares_bought, price=price, amount=amount_to_spend))
                        state.cash -= amount_to_spend
                    except KeyError: continue
                
    return state
