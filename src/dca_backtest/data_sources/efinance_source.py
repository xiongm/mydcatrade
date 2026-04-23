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
                
                # 1. Try fetching as Fund
                if is_fund:
                    print(f"Direct Fund fetch for {symbol}...")
                    df = ef.fund.get_quote_history(clean_sym)
                    if df is not None and not df.empty:
                        # CRASH FIX: efinance get_base_info has a TypeError with newer Pandas.
                        # We try to get the name from a safer API or catch the crash.
                        try:
                            # We fetch all funds base info and filter manually to avoid the single-code crash
                            info = ef.fund.get_base_info(clean_sym)
                            if not info.empty:
                                self.symbol_names[symbol] = info['基金简称'].iloc[0]
                        except Exception:
                            # Fallback: Many fund names can be found in the quote history metadata
                            # but efinance's quote history is just a dataframe.
                            pass
                        
                        df = df.rename(columns={"日期": "Date", "单位净值": "Close"})
                        df["Open"] = df["Close"]; df["High"] = df["Close"]; df["Low"] = df["Close"]; df["Volume"] = 0
                
                # 2. Try fetching as Stock
                if df is None or len(df) < 5:
                    print(f"Fetching {symbol} as Stock from efinance...")
                    df = ef.stock.get_quote_history(
                        clean_sym, 
                        beg=start_date.replace("-", "") if start_date else "19900101",
                        end=end_date.replace("-", "") if end_date else "20500101",
                        klt=101,
                        fqt=2
                    )
                    if df is not None and not df.empty:
                         if '股票名称' in df.columns:
                             self.symbol_names[symbol] = df['股票名称'].iloc[0]
                         df = df.rename(columns={"日期": "Date", "开盘": "Open", "收盘": "Close", "最高": "High", "最低": "Low", "成交量": "Volume"})

                if df is None or len(df) < 5:
                    raise ValueError(f"No meaningful data returned for {symbol} by efinance")
                
                frames[symbol] = normalize_symbol_frame(df)
                
            except Exception as e:
                print(f"Error fetching {symbol} from efinance: {e}")
                raise
        
        validate_ohlcv_frames(frames)
        return frames
