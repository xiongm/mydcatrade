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
    try:
        symbol, amount = pair_str.split(':')
        return symbol.upper(), float(amount)
    except ValueError: raise argparse.ArgumentTypeError(f"Invalid asset pair '{pair_str}'")

def parse_alias_pair(pair_str: str) -> tuple[str, str]:
    try:
        symbol, name = pair_str.split(':', 1)
        return symbol.upper(), name
    except ValueError: raise argparse.ArgumentTypeError(f"Invalid alias pair '{pair_str}'")

def main():
    parser = argparse.ArgumentParser(description="DCA Backtest CLI")
    parser.add_argument("--assets", nargs="+", type=parse_asset_pair, help="SYMBOL:AMOUNT pairs")
    parser.add_argument("--aliases", nargs="+", type=parse_alias_pair, help="SYMBOL:NAME pairs")
    parser.add_argument("--lump-sum-span", type=int, default=1, help="Benchmark installments")
    parser.add_argument("--currency", choices=["USD", "RMB"], default="USD")
    parser.add_argument("--reinvest", action="store_true", help="Auto-reinvest dividends (DRIP)")
    parser.add_argument("--frequency", choices=["weekly", "biweekly", "monthly"], default="monthly")
    parser.add_argument("--data-source", default="hybrid", choices=list_data_source_names())
    parser.add_argument("--results-dir", default="results")
    parser.add_argument("--start-date", help="YYYY-MM-DD")
    parser.add_argument("--end-date", help="YYYY-MM-DD")
    
    args = parser.parse_args()
    if not args.start_date: args.start_date = (datetime.now() - timedelta(days=5*365)).strftime("%Y-%m-%d")
    curr_sym = "¥" if args.currency == "RMB" else "$"
    
    # 1. Setup Symbols and Weights
    final_symbols = []; final_weights = {}; total_amount = 0.0
    if args.assets:
        for symbol, amount in args.assets:
            final_symbols.append(symbol); total_amount += amount
        for symbol, amount in args.assets:
            final_weights[symbol] = amount / total_amount
    else:
        print("Error: --assets required."); sys.exit(1)
    
    plan = Plan(name=f"dca_{'_'.join(final_symbols)}_{args.frequency}", symbols=final_symbols,
                weights=final_weights, contribution_amount=total_amount, frequency=args.frequency)
    
    print(f"Starting DCA Backtest: {plan.name} ({args.currency}, Reinvest={args.reinvest})")
    
    # 2. Load Data (Prices + Dividends)
    source = get_data_source(args.data_source)
    print(f"Loading data from {args.data_source}...")
    data = source.load_bars(tuple(final_symbols), start_date=args.start_date, end_date=args.end_date)
    divs = source.load_dividends(tuple(final_symbols), start_date=args.start_date, end_date=args.end_date)
    
    # Align
    union_idx = pd.Index([])
    for df in data.values(): union_idx = union_idx.union(df.index)
    aligned_data = {s: df.reindex(union_idx).ffill() for s, df in data.items()}
    
    # Names
    final_names = {}
    if hasattr(source, "symbol_names"): final_names.update(source.symbol_names)
    if args.aliases:
        for sym, name in args.aliases: final_names[sym] = name
            
    # 3. Run Primary Backtest
    print("Running primary DCA...")
    state = run_backtest(plan, aligned_data, dividends=divs, reinvest_dividends=args.reinvest)
    total_capital = sum(t.amount for t in state.trades)
    
    # 4. Run Comparison (Windfall)
    span = max(1, args.lump_sum_span)
    comp_plan = Plan(name="comparison", symbols=final_symbols, weights=final_weights,
                      contribution_amount=total_capital / span, frequency=args.frequency)
    comp_state = run_backtest(comp_plan, aligned_data, dividends=divs, 
                              contribution_limit=span, reinvest_dividends=args.reinvest)

    # 5. Calculate Daily Metrics
    print("Calculating daily metrics...")
    results_data = {"equity": [], "basis": [], "invested": [], "comp_equity": [], "dividend_accum": []}
    current_div_total = 0.0

    for dt in union_idx:
        # Check for dividends on this day
        for s in final_symbols:
             if s in divs and dt in divs[s].index:
                 shares = sum(t.shares for t in state.trades if t.symbol == s and t.date < dt)
                 current_div_total += shares * divs[s].loc[dt]
        
        results_data["dividend_accum"].append(current_div_total)
        results_data["invested"].append(sum(t.amount for t in state.trades if t.date == dt))
        results_data["basis"].append(sum(t.amount for t in state.trades if t.date <= dt))
        
        # Current Value
        shares = {s: sum(t.shares for t in state.trades if t.symbol == s and t.date <= dt) for s in final_symbols}
        results_data["equity"].append(state.cash + sum(q * aligned_data[s].loc[dt, "close"] for s, q in shares.items()))
        
        comp_shares = {s: sum(t.shares for t in comp_state.trades if t.symbol == s and t.date <= dt) for s in final_symbols}
        results_data["comp_equity"].append(comp_state.cash + sum(q * aligned_data[s].loc[dt, "close"] for s, q in comp_shares.items()))
            
    curve_df = pd.DataFrame(results_data, index=union_idx)
    curve_df["roi_pct"] = (curve_df["equity"] - curve_df["basis"]) / curve_df["basis"]
    curve_df["roi_pct"] = curve_df["roi_pct"].fillna(0.0)
    
    metrics = calculate_metrics(curve_df["equity"], total_capital)
    metrics.update({"currency": args.currency, "reinvest": args.reinvest, "total_dividends": float(state.dividend_income)})
    
    comp_final_val = curve_df["comp_equity"].iloc[-1]
    metrics["comparison"] = {
        "type": "Lump Sum" if span == 1 else f"Windfall ({span})",
        "final_value": float(comp_final_val),
        "alpha": float(curve_df["equity"].iloc[-1] - comp_final_val),
        "installments": [] # (Can re-populate if needed)
    }

    # 6. Asset Attribution
    symbol_metrics = []
    final_dt, final_val = union_idx[-1], curve_df["equity"].iloc[-1]
    for s in final_symbols:
        s_basis = sum(t.amount for t in state.trades if t.symbol == s)
        s_shares = sum(t.shares for t in state.trades if t.symbol == s)
        s_val = s_shares * aligned_data[s].loc[final_dt, "close"]
        s_divs = sum(t.shares * divs[s].loc[dt] for t in state.trades if t.symbol == s for dt in divs[s].index if dt > t.date) if s in divs else 0
        symbol_metrics.append({
            "symbol": s, "name": final_names.get(s, s), "basis": float(s_basis),
            "final_value": float(s_val), "dividends": float(s_divs),
            "target_weight": float(final_weights[s]), "actual_weight": float(s_val / final_val)
        })
    metrics["symbol_metrics"] = symbol_metrics

    # 7. Monthly Table
    monthly_df = curve_df.resample('ME').last()
    metrics["monthly_metrics"] = [{
        "month": dt.strftime("%b %Y"), "invested": float(row['invested']),
        "basis": float(row['basis']), "value": float(row['equity']), "roi_pct": float(row['roi_pct']),
        "div_accum": float(row['dividend_accum'])
    } for dt, row in monthly_df.iterrows()]
    
    write_results_bundle(Path(args.results_dir), RunContext(plan=plan, data_source=args.data_source, symbols=final_symbols,
                         date_range=f"{union_idx[0].date()} to {union_idx[-1].date()}", commit_hash="local"),
                         metrics, pd.DataFrame([asdict(t) for t in state.trades]), curve_df)
    print(f"DCA Backtest Complete. Final Value: {curr_sym}{metrics['final_value']:,.2f}")

if __name__ == "__main__": main()
