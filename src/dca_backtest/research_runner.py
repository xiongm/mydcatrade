import argparse
import json
import pandas as pd
import yfinance as yf
from pathlib import Path
from datetime import datetime
import numpy as np

from dca_backtest.models import Plan
from dca_backtest.engine import run_backtest
from dca_backtest.data_sources.registry import get_data_source
from dca_backtest.research_math import calculate_xirr, calculate_drawdown_metrics

def fetch_fx_data(start_date: str, end_date: str):
    print("Fetching FX data (USD/CNY)...")
    try:
        # CNY=X gives how many CNY per USD.
        fx = yf.download("CNY=X", start=start_date, end=end_date, auto_adjust=False, progress=False)
        if isinstance(fx.columns, pd.MultiIndex):
            fx.columns = [c[0] if isinstance(c, tuple) else c for c in fx.columns]
        fx_close = fx["Close"]
        fx_close.index = pd.to_datetime(fx_close.index).tz_localize(None).normalize()
        fx_close = fx_close.resample('D').ffill()
        return fx_close
    except Exception as e:
        print(f"Warning: Could not fetch FX data: {e}")
        return None

def extract_metrics(plan_name, market, category, group_name, state, data, union_idx, total_contribution, fx_series=None):
    equity_values = []
    invested_values = []
    cash_flows_dates = []
    cash_flows_amounts = []
    
    for dt in union_idx:
        today_inv = sum(t.amount for t in state.trades if t.date == dt)
        if today_inv > 0:
            cash_flows_dates.append(dt)
            cash_flows_amounts.append(-today_inv)
        invested_values.append(today_inv)
        
        # calculate value
        shares = {}
        for s in data.keys():
            shares[s] = sum(t.shares for t in state.trades if t.symbol == s and t.date <= dt)
        
        eq = state.cash + sum(q * data[s].loc[dt, "close"] for s, q in shares.items() if s in data and dt in data[s].index)
        equity_values.append(eq)

    curve_df = pd.DataFrame({"equity": equity_values}, index=union_idx)
    final_val = equity_values[-1]
    
    cash_flows_dates.append(union_idx[-1])
    cash_flows_amounts.append(final_val)
    xirr = calculate_xirr(pd.DatetimeIndex(cash_flows_dates), np.array(cash_flows_amounts))
    dd = calculate_drawdown_metrics(curve_df["equity"])
    
    usd_final_val = None
    if fx_series is not None and market == "CN":
        try:
            # Reindex to our dates
            valid_fx = fx_series.reindex(union_idx, method='ffill')
            fx_rate = valid_fx.iloc[-1]
            if pd.notna(fx_rate) and fx_rate > 0:
                usd_final_val = final_val / float(fx_rate)
        except Exception:
            pass
            
    res = {
        "market": market,
        "category": category,
        "name": group_name,
        "strategy_id": plan_name,
        "start_date": union_idx[0].strftime("%Y-%m-%d"),
        "end_date": union_idx[-1].strftime("%Y-%m-%d"),
        "total_contributed": total_contribution,
        "ending_value_local": final_val,
        "ending_value_usd_if_applicable": usd_final_val,
        "total_return_pct": (final_val - total_contribution) / total_contribution if total_contribution > 0 else 0,
        "money_weighted_return_or_xirr": xirr,
        "max_drawdown": dd["max_drawdown"],
    }
    
    return res, curve_df

def run_research(config_path: str, output_dir: str, start_date: str, frequency: str, contribution: float):
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    
    with open(config_path, 'r') as f:
        config = json.load(f)
        
    end_date = datetime.now().strftime("%Y-%m-%d")
    fx_series = fetch_fx_data(start_date, end_date)
    source = get_data_source("hybrid")
    
    all_metrics = []
    all_time_series = []
    
    for category, groups in [("broad_index", config.get("broad_indexes", {})), ("sector", config.get("sectors", {}))]:
        for market, market_groups in groups.items():
            for group_name, group_data in market_groups.items():
                tickers = group_data.get("tickers", [group_name])
                plan_name = f"{market}_{category.upper()}_{group_name}"
                print(f"Processing {plan_name}...")
                
                try:
                    raw_data = source.load_bars(tuple(tickers), start_date=start_date, end_date=end_date)
                except Exception as e:
                    print(f"Failed to load data for {plan_name}: {e}")
                    continue
                
                union_idx = pd.Index([])
                for df in raw_data.values(): union_idx = union_idx.union(df.index)
                if len(union_idx) == 0: continue
                
                data = {s: df.reindex(union_idx).ffill() for s, df in raw_data.items()}
                
                weights = {s: 1.0/len(tickers) for s in tickers}
                plan = Plan(name=plan_name, symbols=tickers, weights=weights, contribution_amount=contribution, frequency=frequency)
                
                state = run_backtest(plan, data)
                total_cap = sum(t.amount for t in state.trades)
                if total_cap == 0:
                    continue
                
                metrics, curve = extract_metrics(plan_name, market, category, group_name, state, data, union_idx, total_cap, fx_series)
                all_metrics.append(metrics)
                
                # Format curve for time series
                monthly_curve = curve.resample('ME').last()
                for dt, row in monthly_curve.iterrows():
                    inv_to_date = sum(t.amount for t in state.trades if t.date <= dt)
                    usd_val = None
                    if fx_series is not None and market == "CN":
                        valid_fx = fx_series.reindex(monthly_curve.index, method='ffill')
                        if pd.notna(valid_fx.loc[dt]) and valid_fx.loc[dt] > 0:
                            usd_val = row["equity"] / float(valid_fx.loc[dt])
                            
                    dd = (row["equity"] - monthly_curve["equity"].cummax().loc[dt]) / monthly_curve["equity"].cummax().loc[dt] if monthly_curve["equity"].cummax().loc[dt] > 0 else 0
                    
                    all_time_series.append({
                        "date": dt.strftime("%Y-%m-%d"),
                        "strategy_id": plan_name,
                        "market": market,
                        "category": category,
                        "sector_or_index": group_name,
                        "contribution": sum(t.amount for t in state.trades if t.date.year == dt.year and t.date.month == dt.month),
                        "cumulative_contribution": inv_to_date,
                        "portfolio_value_local": row["equity"],
                        "portfolio_value_usd_if_applicable": usd_val,
                        "drawdown": dd
                    })
                
    df_metrics = pd.DataFrame(all_metrics)
    pd.DataFrame(all_time_series).to_csv(out / "monthly_portfolio_values.csv", index=False)

    
    broad_df = df_metrics[df_metrics["category"] == "broad_index"]
    sector_df = df_metrics[df_metrics["category"] == "sector"]
    
    broad_df.to_csv(out / "broad_index_summary.csv", index=False)
    sector_df.to_csv(out / "sector_basket_summary.csv", index=False)

    # 3. US vs China Sector Comparison
    us_sectors = sector_df[sector_df["market"] == "US"].set_index("name")
    cn_sectors = sector_df[sector_df["market"] == "CN"].set_index("name")
    
    comp_df = us_sectors.join(cn_sectors, lsuffix="_us", rsuffix="_cn", how="inner").reset_index()
    
    comp_out = []
    for _, row in comp_df.iterrows():
        cn_usd = row["ending_value_usd_if_applicable_cn"]
        if pd.isna(cn_usd):
            cn_usd = 0.0
            
        us_val = row["ending_value_local_us"]
        
        comp_out.append({
            "sector": row["name"],
            "us_ending_value": us_val,
            "china_ending_value_local": row["ending_value_local_cn"],
            "china_ending_value_usd": cn_usd,
            "us_total_return_pct": row["total_return_pct_us"],
            "china_total_return_local_pct": row["total_return_pct_cn"],
            "us_max_drawdown": row["max_drawdown_us"],
            "china_max_drawdown": row["max_drawdown_cn"],
            "winner_usd_adjusted": "US" if us_val > cn_usd else "CN",
            "performance_gap_usd_pct": (us_val - cn_usd) / cn_usd if cn_usd > 0 else 0
        })
    comp_out_df = pd.DataFrame(comp_out)
    comp_out_df.to_csv(out / "us_vs_china_sector_comparison.csv", index=False)

    # 4. Ranking Tables
    best_broad = broad_df.loc[broad_df["ending_value_local"].idxmax()]
    worst_broad = broad_df.loc[broad_df["ending_value_local"].idxmin()]
    
    best_us_sector = sector_df[sector_df["market"] == "US"].loc[sector_df[sector_df["market"] == "US"]["ending_value_local"].idxmax()]
    worst_us_sector = sector_df[sector_df["market"] == "US"].loc[sector_df[sector_df["market"] == "US"]["ending_value_local"].idxmin()]
    
    best_cn_sector = sector_df[sector_df["market"] == "CN"].loc[sector_df[sector_df["market"] == "CN"]["ending_value_local"].idxmax()]
    worst_cn_sector = sector_df[sector_df["market"] == "CN"].loc[sector_df[sector_df["market"] == "CN"]["ending_value_local"].idxmin()]
    
    comp_out_df["abs_performance_gap"] = comp_out_df["performance_gap_usd_pct"].abs()
    largest_gap = comp_out_df.loc[comp_out_df["abs_performance_gap"].idxmax()]
    smallest_gap = comp_out_df.loc[comp_out_df["abs_performance_gap"].idxmin()]
    
    rankings = [
        {"metric": "Best broad index by ending value", "name": best_broad["name"], "value": best_broad["ending_value_local"]},
        {"metric": "Worst broad index by ending value", "name": worst_broad["name"], "value": worst_broad["ending_value_local"]},
        {"metric": "Best U.S. sector basket", "name": best_us_sector["name"], "value": best_us_sector["ending_value_local"]},
        {"metric": "Worst U.S. sector basket", "name": worst_us_sector["name"], "value": worst_us_sector["ending_value_local"]},
        {"metric": "Best China A-share sector basket", "name": best_cn_sector["name"], "value": best_cn_sector["ending_value_local"]},
        {"metric": "Worst China A-share sector basket", "name": worst_cn_sector["name"], "value": worst_cn_sector["ending_value_local"]},
        {"metric": "Largest U.S. vs China performance gap (USD %)", "name": largest_gap["sector"], "value": largest_gap["performance_gap_usd_pct"]},
        {"metric": "Smallest U.S. vs China performance gap (USD %)", "name": smallest_gap["sector"], "value": smallest_gap["performance_gap_usd_pct"]}
    ]
    pd.DataFrame(rankings).to_csv(out / "rankings.csv", index=False)

    # Generate basic README
    readme_content = f"""# USA vs China A-share DCA Performance Backtest

## Overview
DCA Backtest from {start_date} to {end_date} at {frequency} frequency with {contribution} per period.

## Broad Index Summary
{broad_df[['market', 'name', 'total_return_pct', 'money_weighted_return_or_xirr']].to_markdown(index=False)}

## Sector Comparison
{comp_out_df[['sector', 'us_total_return_pct', 'china_total_return_local_pct', 'winner_usd_adjusted']].to_markdown(index=False)}
"""
    (out / "README.md").write_text(readme_content)
    
    print("Research complete. Check outputs folder.")

def main():
    parser = argparse.ArgumentParser(description="USA vs China DCA Research Runner")
    parser.add_argument("--config", required=True)
    parser.add_argument("--start", default="2015-01-01")
    parser.add_argument("--frequency", default="monthly")
    parser.add_argument("--contribution", type=float, default=1000.0)
    parser.add_argument("--output", default="outputs/us_vs_china_dca")
    args = parser.parse_args()
    run_research(args.config, args.output, args.start, args.frequency, args.contribution)

if __name__ == "__main__":
    main()
