import argparse
from pathlib import Path
import yfinance as yf
import pandas as pd
import re
import akshare as ak
from datetime import datetime, UTC, timedelta

def download_and_cache(symbols: list[str], root_dir: str = "data/csv", lookback_years: int = 10):
    root = Path(root_dir)
    root.mkdir(parents=True, exist_ok=True)
    
    end_date = datetime.now(tz=UTC).date()
    start_date = end_date - timedelta(days=(365 * lookback_years) + 30)
    
    for symbol in symbols:
        path = root / f"{symbol}.csv"
        
        # Check if symbol is a 6-digit code (A-share or Fund)
        if re.match(r'^\d{6}$', symbol):
            print(f"Downloading {symbol} from AkShare...")
            try:
                # 1. Try as Stock
                df = ak.stock_zh_a_hist(
                    symbol=symbol,
                    period="daily",
                    start_date=start_date.strftime("%Y%m%d"),
                    end_date=end_date.strftime("%Y%m%d"),
                    adjust="hfq"
                )
                
                if df.empty:
                    # 2. Try as Fund
                    print(f"{symbol} not found as Stock, trying as Fund...")
                    df = ak.fund_open_fund_info_em(symbol=symbol, indicator="单位净值走势")
                    if not df.empty:
                        df = df.rename(columns={"净值日期": "Date", "单位净值": "Close"})
                        df["Open"] = df["Close"]
                        df["High"] = df["Close"]
                        df["Low"] = df["Close"]
                        df["Volume"] = 0
                else:
                    df = df.rename(columns={
                        "日期": "Date", "开盘": "Open", "收盘": "Close",
                        "最高": "High", "最低": "Low", "成交量": "Volume"
                    })

                if df.empty:
                    print(f"Warning: No data found for {symbol}")
                    continue
                    
                df.to_csv(path, index=False)
                print(f"Saved {symbol} to {path} ({len(df)} bars)")
            except Exception as e:
                print(f"Error downloading {symbol} from AkShare: {e}")
        else:
            # US Ticker (yfinance)
            print(f"Downloading {symbol} from yfinance...")
            try:
                df = yf.download(
                    symbol,
                    start=start_date.isoformat(),
                    end=end_date.isoformat(),
                    auto_adjust=False,
                    progress=True
                )
                if df.empty:
                    print(f"Warning: No data found for {symbol}")
                    continue
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
                df.to_csv(path)
                print(f"Saved {symbol} to {path} ({len(df)} bars)")
            except Exception as e:
                print(f"Error downloading {symbol} from yfinance: {e}")

def main():
    parser = argparse.ArgumentParser(description="Download and cache ticker data for offline use.")
    parser.add_argument("symbols", nargs="+", help="Tickers to download (US or 6-digit A-share/Fund codes)")
    parser.add_argument("--dir", default="data/csv", help="Directory to save CSV files")
    parser.add_argument("--years", type=int, default=10, help="Years of history to download")
    
    args = parser.parse_args()
    download_and_cache(args.symbols, args.dir, args.years)

if __name__ == "__main__":
    main()
