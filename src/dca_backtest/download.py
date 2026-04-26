import argparse
import json
from pathlib import Path
import yfinance as yf
import pandas as pd
import re
import akshare as ak
import efinance as ef
from datetime import datetime, UTC, timedelta

def get_yf_symbol(symbol: str) -> str:
    clean_sym = symbol[1:] if symbol.startswith('F') else symbol
    if not re.match(r'^\d{6}$', clean_sym): return symbol
    if clean_sym.startswith(('60', '68', '90', '51', '58')): return f"{clean_sym}.SS"
    return f"{clean_sym}.SZ"

def save_metadata(symbol: str, name: str, root_dir: Path):
    meta_path = root_dir / f"{symbol}.json"
    meta = {"symbol": symbol, "name": name, "updated_at": datetime.now().isoformat()}
    meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False))

def download_and_cache(symbols: list[str], root_dir: str = "data/csv", lookback_years: int = 10):
    root = Path(root_dir)
    root.mkdir(parents=True, exist_ok=True)
    end_dt = datetime.now(tz=UTC).date()
    start_dt = end_dt - timedelta(days=(365 * lookback_years) + 30)
    
    for symbol in symbols:
        path = root / f"{symbol}.csv"
        div_path = root / f"{symbol}_dividends.csv"
        success = False
        found_name = None
        clean_sym = symbol[1:] if symbol.startswith('F') else symbol
        is_fund = symbol.startswith('F') or (re.match(r'^\d{6}$', symbol) and not re.match(r'^(60|000|002|300|688|900)', symbol))

        route = ["efinance", "akshare", "yahoo"] if is_fund else ["yahoo", "efinance", "akshare"]

        for provider in route:
            try:
                df = None; divs = pd.Series(dtype=float)
                if provider == "yahoo":
                    yf_sym = get_yf_symbol(symbol)
                    ticker = yf.Ticker(yf_sym)
                    df = ticker.history(start=start_dt.isoformat(), end=end_dt.isoformat(), auto_adjust=False)
                    if not df.empty:
                        divs = df['Dividends'][df['Dividends'] > 0]
                        if isinstance(df.columns, pd.MultiIndex): df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
                elif provider == "efinance":
                    df = ef.stock.get_quote_history(clean_sym, beg=start_dt.strftime("%Y%m%d"), end=end_dt.strftime("%Y%m%d"), fqt=2)
                    if df is not None and not df.empty:
                        if '股票名称' in df.columns: found_name = df['股票名称'].iloc[0]
                        df = df.rename(columns={"日期": "Date", "开盘": "Open", "收盘": "Close", "最高": "High", "最低": "Low", "成交量": "Volume"})
                        # Fetch divs
                        d_df = ef.stock.get_dividend_history(clean_sym)
                        if d_df is not None and not d_df.empty:
                             divs = d_df.rename(columns={"除权除息日": "Date", "每股派息": "Amount"}).set_index(pd.to_datetime(d_df["除权除息日"]))["每股派息"]
                    else:
                        df = ef.fund.get_quote_history(clean_sym)
                        if df is not None and not df.empty:
                            df = df.rename(columns={"日期": "Date", "单位净值": "Close"})
                            df["Open"] = df["Close"]; df["High"] = df["Close"]; df["Low"] = df["Close"]; df["Volume"] = 0
                            if "累计净值" in df.columns:
                                df['diff'] = df['累计净值'] - df['单位净值']
                                df['div'] = df['diff'].diff().fillna(0).clip(lower=0)
                                divs = df[df['div'] > 0].set_index(pd.to_datetime(df["Date"]))["div"]
                elif provider == "akshare":
                    # (Similar logic for AkShare if needed, omitting for brevity in this turn as efinance/yahoo are primary)
                    pass

                if df is not None and not df.empty:
                    df.to_csv(path, index=False if provider != "yahoo" else True)
                    if not divs.empty: divs.to_csv(div_path)
                    if found_name: save_metadata(symbol, found_name, root)
                    print(f"Saved {symbol} (and dividends) from {provider}")
                    success = True; break
            except Exception as e: print(f"{provider} failed for {symbol}: {e}")

def main():
    parser = argparse.ArgumentParser(description="Download ticker data.")
    parser.add_argument("symbols", nargs="+"); parser.add_argument("--dir", default="data/csv"); parser.add_argument("--years", type=int, default=10)
    args = parser.parse_args(); download_and_cache(args.symbols, args.dir, args.years)

if __name__ == "__main__": main()
