import argparse
import sys
from pathlib import Path
import pandas as pd
from datetime import datetime, timedelta
from dataclasses import asdict

from dca_backtest.models import Plan, RunContext
from dca_backtest.engine import run_backtest
from dca_backtest.reporting import calculate_metrics
from dca_backtest.data_sources.registry import get_data_source, list_data_source_names
from dca_backtest.results.writer import write_results_bundle

def parse_asset_pair(pair_str: str) -> tuple[str, float]:
    """Parses a SYMBOL:AMOUNT string into (symbol, amount)."""
    try:
        symbol, amount = pair_str.split(':')
        return symbol.upper(), float(amount)
    except ValueError:
        raise argparse.ArgumentTypeError(f"Invalid asset pair '{pair_str}'. Expected format: SYMBOL:AMOUNT")

def parse_alias_pair(pair_str: str) -> tuple[str, str]:
    """Parses a SYMBOL:NAME string into (symbol, name)."""
    try:
        symbol, name = pair_str.split(':', 1)
        return symbol.upper(), name
    except ValueError:
        raise argparse.ArgumentTypeError(f"Invalid alias pair '{pair_str}'. Expected format: SYMBOL:NAME")

def main():
    parser = argparse.ArgumentParser(description="DCA Backtest CLI")
    
    # Grouped arguments
    parser.add_argument("--assets", nargs="+", type=parse_asset_pair, 
                        help="List of assets and their amounts in SYMBOL:AMOUNT format (e.g. SPY:500 QQQ:300)")
    parser.add_argument("--aliases", nargs="+", type=parse_alias_pair,
                        help="Human-readable names for tickers in SYMBOL:NAME format (e.g. 002594:BYD)")
    
    # Comparison arguments
    parser.add_argument("--lump-sum-span", type=int, default=1, 
                        help="Compare DCA to spreading the entire capital over the first N installments (default: 1 for Lump Sum)")
    
    # Currency argument
    parser.add_argument("--currency", choices=["USD", "RMB"], default="USD", help="Currency symbol for the report (USD or RMB)")
    
    # Old individual arguments
    parser.add_argument("--symbols", nargs="+", help="Symbols to include in the plan")
    parser.add_argument("--weights", nargs="+", type=float, help="Target weights for symbols")
    parser.add_argument("--amount", type=float, default=1000.0, help="Total contribution amount")
    parser.add_argument("--amounts", nargs="+", type=float, help="Exact dollar amounts for each symbol per cycle")
    
    parser.add_argument("--frequency", choices=["weekly", "biweekly", "monthly"], default="monthly", help="Contribution frequency")
    parser.add_argument("--data-source", default="hybrid", choices=list_data_source_names(), help="Data source to use")
    parser.add_argument("--results-dir", default="results", help="Directory to store results")
    parser.add_argument("--start-date", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end-date", help="End date (YYYY-MM-DD)")
    
    args = parser.parse_args()
    
    if not args.start_date:
        args.start_date = (datetime.now() - timedelta(days=5*365)).strftime("%Y-%m-%d")
    
    # Currency Symbol for Terminal
    curr_sym = "¥" if args.currency == "RMB" else "$"
    
    # 1. Determine Weights and Total Amount
    final_symbols = []
    final_weights = {}
    total_amount = 0.0

    if args.assets:
        for symbol, amount in args.assets:
            final_symbols.append(symbol)
            total_amount += amount
        for symbol, amount in args.assets:
            final_weights[symbol] = amount / total_amount
    elif args.amounts:
        if not args.symbols or len(args.symbols) != len(args.amounts):
            print("Error: Number of symbols must match number of amounts.")
            sys.exit(1)
        final_symbols = [s.upper() for s in args.symbols]
        total_amount = sum(args.amounts)
        final_weights = {s: a / total_amount for s, a in zip(final_symbols, args.amounts)}
    else:
        final_symbols = [s.upper() for s in (args.symbols or ["SPY"])]
        if args.weights:
            if len(final_symbols) != len(args.weights):
                print("Error: Number of symbols must match number of weights.")
                sys.exit(1)
            total_weight = sum(args.weights)
            final_weights = {s: w / total_weight for s, w in zip(final_symbols, args.weights)}
        else:
            final_weights = {s: 1.0 / len(final_symbols) for s in final_symbols}
        total_amount = args.amount
    
    plan = Plan(
        name=f"dca_{'_'.join(final_symbols)}_{args.frequency}",
        symbols=final_symbols,
        weights=final_weights,
        contribution_amount=total_amount,
        frequency=args.frequency
    )
    
    print(f"Starting DCA Backtest for Plan: {plan.name} ({args.currency})")
    
    # 2. Load Data
    source = get_data_source(args.data_source)
    print(f"Loading data from {args.data_source}...")
    raw_data = source.load_bars(tuple(final_symbols), start_date=args.start_date, end_date=args.end_date)
    
    # 2.1 Align Data
    union_idx = pd.Index([])
    for df in raw_data.values():
        union_idx = union_idx.union(df.index)
    
    data = {}
    for s, df in raw_data.items():
        data[s] = df.reindex(union_idx).ffill()
    
    # 2.2 Aggregate Names/Aliases
    final_names = {}
    if hasattr(source, "symbol_names"):
        final_names.update(source.symbol_names)
    
    if args.aliases:
        for sym, name in args.aliases:
            final_names[sym] = name
            
    # 3. Run Baseline Backtest
    print("Running primary DCA backtest...")
    state = run_backtest(plan, data)
    total_capital = sum(t.amount for t in state.trades)
    
    # 4. Run Comparison Backtest
    span = max(1, args.lump_sum_span)
    comparison_type = "Lump Sum" if span == 1 else f"Windfall DCA ({span} installments)"
    print(f"Running comparison {comparison_type} with total capital {curr_sym}{total_capital:,.2f}...")
    
    comp_plan = Plan(
        name="comparison",
        symbols=final_symbols,
        weights=final_weights,
        contribution_amount=total_capital / span,
        frequency=args.frequency
    )
    comparison_state = run_backtest(comp_plan, data, contribution_limit=span)
    
    trades_by_date = {}
    for t in comparison_state.trades:
        date_str = str(t.date.date())
        if date_str not in trades_by_date:
            trades_by_date[date_str] = {"date": date_str, "total": 0.0, "breakdown": []}
        trades_by_date[date_str]["total"] += t.amount
        trades_by_date[date_str]["breakdown"].append({
            "symbol": t.symbol, "amount": t.amount, "price": t.price, "shares": t.shares
        })
    comparison_installments = list(trades_by_date.values())

    # 5. Calculate Daily Metrics
    print("Calculating daily metrics...")
    dates = union_idx
    
    results_data = {"equity": [], "basis": [], "invested": [], "comp_equity": []}

    for dt in dates:
        today_invested = sum(t.amount for t in state.trades if t.date == dt)
        results_data["invested"].append(today_invested)
        results_data["basis"].append(sum(t.amount for t in state.trades if t.date <= dt))
        
        # Primary Equity
        shares = {s: sum(t.shares for t in state.trades if t.symbol == s and t.date <= dt) for s in final_symbols}
        results_data["equity"].append(state.cash + sum(q * data[s].loc[dt, "close"] for s, q in shares.items()))
        
        # Comparison Equity
        comp_shares = {s: sum(t.shares for t in comparison_state.trades if t.symbol == s and t.date <= dt) for s in final_symbols}
        results_data["comp_equity"].append(comparison_state.cash + sum(q * data[s].loc[dt, "close"] for s, q in comp_shares.items()))
            
    curve_df = pd.DataFrame(results_data, index=dates)
    curve_df["roi_pct"] = (curve_df["equity"] - curve_df["basis"]) / curve_df["basis"]
    curve_df["roi_pct"] = curve_df["roi_pct"].fillna(0.0)
    
    metrics = calculate_metrics(curve_df["equity"], total_capital)
    metrics["currency"] = args.currency
    
    comp_final_val = curve_df["comp_equity"].iloc[-1]
    metrics["comparison"] = {
        "type": comparison_type,
        "final_value": comp_final_val,
        "profit": comp_final_val - total_capital,
        "roi_pct": (comp_final_val - total_capital) / total_capital if total_capital > 0 else 0.0,
        "alpha": (curve_df["equity"].iloc[-1] - comp_final_val),
        "installments": comparison_installments
    }

    # 6. Breakdowns & Snapshots
    symbol_metrics = []
    final_dt, final_val = dates[-1], curve_df["equity"].iloc[-1]
    for s in final_symbols:
        s_basis = sum(t.amount for t in state.trades if t.symbol == s)
        s_val = sum(t.shares for t in state.trades if t.symbol == s) * data[s].loc[final_dt, "close"]
        symbol_metrics.append({
            "symbol": s, 
            "name": final_names.get(s, s),
            "target_weight": final_weights[s], "basis": s_basis,
            "final_value": s_val, "roi_pct": (s_val - s_basis) / s_basis if s_basis > 0 else 0,
            "actual_weight": s_val / final_val if final_val > 0 else 0
        })
    metrics["symbol_metrics"] = symbol_metrics

    monthly_df = curve_df.resample('ME').last()
    monthly_df['invested'] = curve_df['invested'].resample('ME').sum()
    metrics["monthly_metrics"] = [{
        "month": dt.strftime("%b %Y"), "invested": float(row['invested']),
        "basis": float(row['basis']), "value": float(row['equity']), "roi_pct": float(row['roi_pct']),
        "comp_value": float(row['comp_equity'])
    } for dt, row in monthly_df.iterrows()]

    # Add Purchase Log (last 100 trades for visibility)
    metrics["purchase_log"] = [{
        "date": t.date.strftime("%Y-%m-%d"),
        "symbol": t.symbol,
        "name": final_names.get(t.symbol, t.symbol),
        "price": t.price,
        "shares": t.shares,
        "amount": t.amount
    } for t in state.trades[-100:]] # Show latest 100 trades
    
    # 7. Write Results
    print("Writing results bundle...")
    context = RunContext(plan=plan, data_source=args.data_source, symbols=final_symbols,
                         date_range=f"{dates[0].date()} to {dates[-1].date()}", commit_hash="local")
    write_results_bundle(root_dir=Path(args.results_dir), context=context, summary=metrics,
                         trades=pd.DataFrame([asdict(t) for t in state.trades]), equity_curve=curve_df)
    
    print(f"DCA Backtest Complete. Final Value: {curr_sym}{metrics['final_value']:,.2f} ({metrics['total_return']:.2%})")

if __name__ == "__main__":
    main()
