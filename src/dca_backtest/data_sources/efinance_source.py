from __future__ import annotations
from datetime import datetime, UTC
from typing import Optional, Dict
import pandas as pd
import efinance as ef

from .base import normalize_symbol_frame, validate_ohlcv_frames

class EFinanceDataSource:
    """
    Data source for Chinese A-shares and Funds using efinance.
    More stable than AkShare for general market data.
    """
    name = "efinance"

    def __init__(self):
        self.symbol_names: Dict[str, str] = {}

    def load_bars(
        self, 
        symbols: tuple[str, ...], 
        start_date: Optional[str] = None, 
        end_date: Optional[str] = None,
        is_fund_hint: bool = False
    ) -> dict[str, pd.DataFrame]:
        frames = {}
        
        for symbol in symbols:
            clean_sym = symbol[1:] if symbol.startswith('F') else symbol
            is_fund = is_fund_hint or symbol.startswith('F')
            
            print(f"Fetching {symbol} from efinance...")
            try:
                df = None
                if is_fund:
                    df = ef.fund.get_quote_history(clean_sym)
                    if df is not None and not df.empty:
                        try:
                            info = ef.fund.get_base_info(clean_sym)
                            if not info.empty: self.symbol_names[symbol] = info['基金简称'].iloc[0]
                        except Exception: pass
                        df = df.rename(columns={"日期": "Date", "单位净值": "Close"})
                        df["Open"] = df["Close"]; df["High"] = df["Close"]; df["Low"] = df["Close"]; df["Volume"] = 0
                
                if df is None or len(df) < 5:
                    df = ef.stock.get_quote_history(
                        clean_sym, 
                        beg=start_date.replace("-", "") if start_date else "19900101",
                        end=end_date.replace("-", "") if end_date else "20500101",
                        klt=101, fqt=2
                    )
                    if df is not None and not df.empty:
                         if '股票名称' in df.columns: self.symbol_names[symbol] = df['股票名称'].iloc[0]
                         df = df.rename(columns={"日期": "Date", "开盘": "Open", "收盘": "Close", "最高": "High", "最低": "Low", "成交量": "Volume"})

                if df is None or len(df) < 5:
                    raise ValueError(f"No meaningful data returned for {symbol}")
                
                frames[symbol] = normalize_symbol_frame(df)
            except Exception as e:
                print(f"Error fetching {symbol} from efinance: {e}")
                raise
        
        validate_ohlcv_frames(frames)
        return frames

    def load_dividends(
        self,
        symbols: tuple[str, ...],
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> dict[str, pd.Series]:
        divs: dict[str, pd.Series] = {}
        for symbol in symbols:
            clean_sym = symbol[1:] if symbol.startswith('F') else symbol
            try:
                # 1. Try as Stock first (using official dividend history)
                df = ef.stock.get_dividend_history(clean_sym)
                if df is not None and not df.empty:
                    df = df.rename(columns={"除权除息日": "Date", "每股派息": "Amount"})
                    # Normalize dates to midnight
                    s = df.set_index(pd.to_datetime(df["Date"]).dt.normalize())["Amount"]
                    if start_date: s = s[s.index >= start_date]
                    if end_date: s = s[s.index <= end_date]
                    divs[symbol] = s
                else:
                    # 2. Try as Fund (Extract dividend from NAV vs Accumulated NAV)
                    df = ef.fund.get_quote_history(clean_sym)
                    if df is not None and not df.empty and "单位净值" in df.columns and "累计净值" in df.columns:
                        df['diff'] = df['累计净值'] - df['单位净值']
                        df['dividend'] = df['diff'].diff().fillna(0).clip(lower=0)
                        s = df[df['dividend'] > 0].set_index(pd.to_datetime(df["日期"]).dt.normalize())["dividend"]
                        if start_date: s = s[s.index >= start_date]
                        if end_date: s = s[s.index <= end_date]
                        divs[symbol] = s
                    else:
                        divs[symbol] = pd.Series(dtype=float)
            except Exception:
                divs[symbol] = pd.Series(dtype=float)
        return divs
