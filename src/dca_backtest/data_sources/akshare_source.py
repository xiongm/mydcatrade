from __future__ import annotations
import time
from datetime import datetime, UTC
from typing import Optional
import pandas as pd
import akshare as ak
import requests

from .base import normalize_symbol_frame, validate_ohlcv_frames

def retry_with_backoff(retries=3, backoff_in_seconds=2):
    def decorator(func):
        def wrapper(*args, **kwargs):
            x = 0
            while True:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    # If it's a known "Data Not Found" error, don't retry
                    err_msg = str(e).lower()
                    if "no data" in err_msg or "not found" in err_msg:
                        raise e
                    
                    if x == retries:
                        print(f"Failed after {retries} retries.")
                        raise e
                    
                    wait = (backoff_in_seconds * 2 ** x)
                    print(f"Network or Rate Limit issue ({e}), retrying in {wait}s... (Attempt {x+1}/{retries})")
                    time.sleep(wait)
                    x += 1
        return wrapper
    return decorator

class AkShareDataSource:
    """
    Data source for Chinese A-shares and Funds using AkShare.
    Includes robust retries and backoff.
    """
    name = "akshare"

    def load_bars(
        self, 
        symbols: tuple[str, ...], 
        start_date: Optional[str] = None, 
        end_date: Optional[str] = None
    ) -> dict[str, pd.DataFrame]:
        frames = {}
        
        for symbol in symbols:
            # Small delay between symbols to be nice to servers
            if frames: time.sleep(1)
            
            try:
                df = self._fetch_with_retries(symbol, start_date, end_date)
                frames[symbol] = normalize_symbol_frame(df)
            except Exception as e:
                print(f"Final error for {symbol}: {e}")
                raise ValueError(f"Could not fetch data for {symbol} after retries. Error: {e}")
        
        validate_ohlcv_frames(frames)
        return frames

    @retry_with_backoff(retries=3, backoff_in_seconds=3)
    def _fetch_with_retries(self, symbol, start_date, end_date):
        # 1. Try fetching as Stock (let exceptions bubble to decorator)
        df = self._fetch_as_stock(symbol, start_date, end_date)
        if df is not None and not df.empty:
            return df
        
        # 2. Try fetching as Fund
        print(f"{symbol} not found as A-share stock, trying as Fund...")
        df = self._fetch_as_fund(symbol, start_date, end_date)
        if df is not None and not df.empty:
            return df
            
        raise ValueError(f"No data returned for {symbol} from either Stock or Fund interfaces.")

    def _fetch_as_stock(self, symbol: str, start_date: str | None, end_date: str | None) -> pd.DataFrame | None:
        ak_start = start_date.replace("-", "") if start_date else "20100101"
        ak_end = end_date.replace("-", "") if end_date else datetime.now(tz=UTC).strftime("%Y%m%d")
        
        # We DON'T catch exceptions here so retry_with_backoff can see them
        return ak.stock_zh_a_hist(
            symbol=symbol, 
            period="daily", 
            start_date=ak_start, 
            end_date=ak_end, 
            adjust="hfq"
        ).rename(columns={
            "日期": "Date", "开盘": "Open", "收盘": "Close",
            "最高": "High", "最低": "Low", "成交量": "Volume"
        })

    def _fetch_as_fund(self, symbol: str, start_date: str | None, end_date: str | None) -> pd.DataFrame | None:
        # We DON'T catch exceptions here so retry_with_backoff can see them
        df = ak.fund_open_fund_info_em(symbol=symbol, indicator="单位净值走势")
        if df.empty: return None
        
        df = df.rename(columns={"净值日期": "Date", "单位净值": "Close"})
        df["Open"] = df["Close"]; df["High"] = df["Close"]; df["Low"] = df["Close"]; df["Volume"] = 0
        
        df['Date'] = pd.to_datetime(df['Date'])
        if start_date: df = df[df['Date'] >= pd.to_datetime(start_date)]
        if end_date: df = df[df['Date'] <= pd.to_datetime(end_date)]
        return df
