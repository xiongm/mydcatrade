from __future__ import annotations
import time
from datetime import datetime, UTC
from typing import Optional, Dict
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
                    err_msg = str(e).lower()
                    if "no data" in err_msg or "not found" in err_msg: raise e
                    if x == retries: raise e
                    wait = (backoff_in_seconds * 2 ** x)
                    print(f"Network issue, retrying in {wait}s...")
                    time.sleep(wait)
                    x += 1
        return wrapper
    return decorator

class AkShareDataSource:
    name = "akshare"
    def __init__(self):
        self.symbol_names: Dict[str, str] = {}

    def load_bars(self, symbols: tuple[str, ...], start_date: Optional[str] = None, end_date: Optional[str] = None, is_fund_hint: bool = False) -> dict[str, pd.DataFrame]:
        frames = {}
        for symbol in symbols:
            if frames: time.sleep(1)
            try:
                df = self._fetch_with_retries(symbol, start_date, end_date, is_fund_hint)
                if df is None or len(df) < 5: raise ValueError(f"No meaningful data for {symbol}")
                frames[symbol] = normalize_symbol_frame(df)
            except Exception as e: raise ValueError(f"Could not fetch {symbol}: {e}")
        validate_ohlcv_frames(frames)
        return frames

    def load_dividends(self, symbols: tuple[str, ...], start_date: Optional[str] = None, end_date: Optional[str] = None) -> dict[str, pd.Series]:
        divs: dict[str, pd.Series] = {}
        for symbol in symbols:
            clean_sym = symbol[1:] if symbol.startswith('F') else symbol
            try:
                # Stock Dividends
                df = ak.stock_history_dividend_detail(symbol=clean_sym, indicator="分红送配详情")
                if not df.empty:
                    # Column "派息" is Cash Dividend per share
                    df = df.rename(columns={"股权登记日": "Date", "派息": "Amount"})
                    s = df.set_index(pd.to_datetime(df["Date"]).dt.normalize())["Amount"]
                    if start_date: s = s[s.index >= start_date]
                    if end_date: s = s[s.index <= end_date]
                    divs[symbol] = s
                else:
                    # Fund check
                    df = ak.fund_open_fund_info_em(symbol=clean_sym, indicator="单位净值走势")
                    if not df.empty:
                        df['diff'] = df['累计净值'] - df['单位净值']
                        df['dividend'] = df['diff'].diff().fillna(0).clip(lower=0)
                        s = df[df['dividend'] > 0].set_index(pd.to_datetime(df["净值日期"]).dt.normalize())["dividend"]
                        if start_date: s = s[s.index >= start_date]
                        if end_date: s = s[s.index <= end_date]
                        divs[symbol] = s
                    else: divs[symbol] = pd.Series(dtype=float)
            except Exception: divs[symbol] = pd.Series(dtype=float)
        return divs

    @retry_with_backoff(retries=3, backoff_in_seconds=3)
    def _fetch_with_retries(self, symbol, start_date, end_date, is_fund_hint):
        clean_sym = symbol[1:] if symbol.startswith('F') else symbol
        is_fund = is_fund_hint or symbol.startswith('F')
        df = None
        if is_fund:
            df = self._fetch_as_fund(clean_sym, start_date, end_date)
            if df is not None and len(df) >= 5: return df
        df = self._fetch_as_stock(clean_sym, start_date, end_date)
        if df is not None and len(df) >= 5: return df
        if not is_fund:
            df = self._fetch_as_fund(clean_sym, start_date, end_date)
            if df is not None and len(df) >= 5: return df
        return None

    def _fetch_as_stock(self, symbol: str, start_date: str | None, end_date: str | None) -> pd.DataFrame | None:
        ak_start = start_date.replace("-", "") if start_date else "20100101"
        ak_end = end_date.replace("-", "") if end_date else datetime.now(tz=UTC).strftime("%Y%m%d")
        try:
            return ak.stock_zh_a_hist(symbol=symbol, period="daily", start_date=ak_start, end_date=ak_end, adjust="hfq").rename(columns={
                "日期": "Date", "开盘": "Open", "收盘": "Close", "最高": "High", "最低": "Low", "成交量": "Volume"
            })
        except Exception: return None

    def _fetch_as_fund(self, symbol: str, start_date: str | None, end_date: str | None) -> pd.DataFrame | None:
        try:
            df = ak.fund_open_fund_info_em(symbol=symbol, indicator="单位净值走势")
            if df.empty: return None
            df = df.rename(columns={"净值日期": "Date", "单位净值": "Close"})
            df["Open"] = df["Close"]; df["High"] = df["Close"]; df["Low"] = df["Close"]; df["Volume"] = 0
            df['Date'] = pd.to_datetime(df['Date'])
            if start_date: df = df[df['Date'] >= pd.to_datetime(start_date)]
            if end_date: df = df[df['Date'] <= pd.to_datetime(end_date)]
            return df
        except Exception: return None
