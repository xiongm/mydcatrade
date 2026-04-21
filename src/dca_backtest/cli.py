import argparse
import sys
from pathlib import Path
import pandas as pd
from datetime import datetime
from dataclasses import asdict

from dca_backtest.models import Plan, RunContext
from dca_backtest.engine import run_backtest
from dca_backtest.reporting import calculate_metrics
from dca_backtest.data_sources.registry import get_data_source, list_data_source_names
from dca_backtest.results.writer import write_results_bundle

def main():
    parser = argparse.ArgumentParser(description="DCA Backtest CLI")
    parser.add_argument("--symbols", nargs="+", default=["SPY"], help="Symbols to include in the plan")
    parser.add_argument("--weights", nargs="+", type=float, default=[1.0], help="Target weights for symbols")
    parser.add_argument("--amount", type=float, default=1000.0, help="Contribution amount")
    parser.add_argument("--frequency", choices=["weekly", "biweekly", "monthly"], default="monthly", help="Contribution frequency")
    parser.add_argument("--data-source", default="yfinance", choices=list_data_source_names(), help="Data source to use")
    parser.add_argument("--results-dir", default="results", help="Directory to store results")
    
    args = parser.parse_args()
    
    if len(args.symbols) != len(args.weights):
        print("Error: Number of symbols must match number of weights.")
        sys.exit(1)
    
    # Normalize weights to sum to 1.0
    total_weight = sum(args.weights)
    weights = {s: w / total_weight for s, w in zip(args.symbols, args.weights)}
    
    plan = Plan(
        name=f"dca_{'_'.join(args.symbols)}_{args.frequency}",
        symbols=args.symbols,
        weights=weights,
        contribution_amount=args.amount,
        frequency=args.frequency
    )
    
    print(f"Starting DCA Backtest for Plan: {plan.name}")
    print(f"Symbols: {args.symbols}")
    print(f"Weights: {weights}")
    print(f"Contribution: ${args.amount} ({args.frequency})")
    
    # 1. Load Data
    source = get_data_source(args.data_source)
    print(f"Loading data from {args.data_source}...")
    data = source.load_bars(tuple(args.symbols))
    
    # 2. Run Backtest
    print("Running backtest engine...")
    state = run_backtest(plan, data)
    
    # 3. Calculate Daily Equity Curve
    print("Calculating metrics...")
    first_symbol = args.symbols[0]
    dates = data[first_symbol].index
    
    equity_values = []
    for dt in dates:
        current_shares = {}
        for t in state.trades:
            if t.date <= dt:
                current_shares[t.symbol] = current_shares.get(t.symbol, 0.0) + t.shares
        
        daily_val = state.cash # Use remaining cash if any
        # In fact, we should track daily cash correctly, but for accumulation only
        # cash usually goes to zero each contribution.
        for s, q in current_shares.items():
            daily_val += q * data[s].loc[dt, "close"]
        equity_values.append(daily_val)
        
    equity_curve = pd.Series(equity_values, index=dates, name="equity")
    total_invested = len(state.trades) * args.amount
    
    metrics = calculate_metrics(equity_curve, total_invested)
    
    # 4. Write Results
    print("Writing results bundle...")
    context = RunContext(
        plan=plan,
        data_source=args.data_source,
        symbols=args.symbols,
        date_range=f"{dates[0].date()} to {dates[-1].date()}",
        commit_hash="local"
    )
    
    trades_df = pd.DataFrame([asdict(t) for t in state.trades])
    
    write_results_bundle(
        root_dir=Path(args.results_dir),
        context=context,
        summary=metrics,
        trades=trades_df,
        equity_curve=equity_curve.to_frame()
    )
    
    print(f"DCA Backtest Complete. Results in {args.results_dir}/{plan.name}")
    print(f"Final Value: ${metrics['final_value']:,.2f}")
    print(f"Total Return: {metrics['total_return']:.2%}")

if __name__ == "__main__":
    main()
