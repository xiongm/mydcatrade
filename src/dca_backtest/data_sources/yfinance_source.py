from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Optional, Dict

import pandas as pd
import yfinance as yf

from .base import normalize_symbol_frame, validate_ohlcv_frames


class YFinanceDataSource:
    name = "yfinance"

    def __init__(self, lookback_years: int = 10) -> None:
        self.lookback_years = lookback_years
        self.symbol_names: Dict[str, str] = {}

    def load_bars(
        self, 
        symbols: tuple[str, ...], 
        start_date: Optional[str] = None, 
        end_date: Optional[str] = None
    ) -> dict[str, pd.DataFrame]:
        frames: dict[str, pd.DataFrame] = {}
        for symbol in symbols:
            # Try to fetch name metadata
            try:
                ticker = yf.Ticker(symbol)
                name = ticker.info.get('shortName') or ticker.info.get('longName')
                if name: self.symbol_names[symbol] = name
            except Exception: pass

            raw = self._download_symbol(symbol, start_date, end_date)
            if raw.empty:
                raise ValueError(f"No data returned for {symbol}")
            frames[symbol] = normalize_symbol_frame(raw.reset_index() if "Date" not in raw.columns else raw)
        validate_ohlcv_frames(frames)
        return frames

    def _download_symbol(
        self, 
        symbol: str, 
        start_date: Optional[str] = None, 
        end_date: Optional[str] = None
    ) -> pd.DataFrame:
        if end_date:
            end = datetime.fromisoformat(end_date).date()
        else:
            end = datetime.now(tz=UTC).date()
            
        if start_date:
            start = datetime.fromisoformat(start_date).date()
        else:
            start = end - timedelta(days=(365 * self.lookback_years) + 30)
            
        return yf.download(
            symbol,
            start=start.isoformat(),
            end=end.isoformat(),
            auto_adjust=False,
            progress=False,
        )
