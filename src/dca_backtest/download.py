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
    """Converts code to Yahoo Finance format."""
    clean_sym = symbol[1:] if symbol.startswith('F') else symbol
    if not re.match(r'^\d{6}$', clean_sym):
        return symbol
    if clean_sym.startswith(('60', '68', '90', '51', '58')):
        return f"{clean_sym}.SS"
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
        success = False
        found_name = None
        
        # Clean symbol for domestic providers
        clean_sym = symbol[1:] if symbol.startswith('F') else symbol
        
        # 1. Route Decision
        is_fund = symbol.startswith('F') or (re.match(r'^\d{6}$', symbol) and not re.match(r'^(60|000|002|300|688|900)', symbol))
        
        route = []
        if is_fund:
            route = ["efinance", "akshare", "yahoo"]
        elif re.match(r'^\d{6}$', symbol):
            route = ["yahoo", "efinance", "akshare"]
        else:
            route = ["yahoo"]

        for provider in route:
            try:
                df = None
                if provider == "yahoo":
                    yf_sym = get_yf_symbol(symbol)
                    df = yf.download(yf_sym, start=start_dt.isoformat(), end=end_dt.isoformat(), auto_adjust=False, progress=True)
                    if df is not None and not df.empty:
                        if isinstance(df.columns, pd.MultiIndex):
                            df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
                
                elif provider == "efinance":
                    df = ef.stock.get_quote_history(clean_sym, beg=start_dt.strftime("%Y%m%d"), end=end_dt.strftime("%Y%m%d"), fqt=2)
                    if df is not None and not df.empty:
                        if '股票名称' in df.columns: found_name = df['股票名称'].iloc[0]
                        df = df.rename(columns={"日期": "Date", "开盘": "Open", "收盘": "Close", "最高": "High", "最低": "Low", "成交量": "Volume"})
                    else:
                        df = ef.fund.get_quote_history(clean_sym)
                        if df is not None and not df.empty:
                            df = df.rename(columns={"日期": "Date", "单位净值": "Close"})
                            df["Open"] = df["Close"]; df["High"] = df["Close"]; df["Low"] = df["Close"]; df["Volume"] = 0
                            # Try name lookup for fund but avoid the crashy get_base_info if possible
                            # We'll use a hardcoded fallback or wait for better API
                
                elif provider == "akshare":
                    try:
                        df = ak.stock_zh_a_hist(symbol=clean_sym, period="daily", start_date=start_dt.strftime("%Y%m%d"), end_date=end_dt.strftime("%Y%m%d"), adjust="hfq")
                        if not df.empty:
                            df = df.rename(columns={"日期": "Date", "开盘": "Open", "收盘": "Close", "最高": "High", "最低": "Low", "成交量": "Volume"})
                    except: df = pd.DataFrame()

                if df is not None and not df.empty:
                    df.to_csv(path, index=False)
                    if found_name: save_metadata(symbol, found_name, root)
                    print(f"Saved {symbol} from {provider}")
                    success = True
                    break
            except Exception as e:
                print(f"{provider} failed for {symbol}: {e}")

        if not success:
            print(f"Warning: All sources failed for {symbol}")

def main():
    parser = argparse.ArgumentParser(description="Download and cache ticker data.")
    parser.add_argument("symbols", nargs="+", help="Tickers (e.g. AAPL, BTC-USD, 600036, F009504)")
    parser.add_argument("--dir", default="data/csv", help="Directory to save CSV files.")
    parser.add_argument("--years", type=int, default=10, help="Years of history.")
    args = parser.parse_args()
    download_and_cache(args.symbols, args.dir, args.years)

if __name__ == "__main__":
    main()
