from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pandas as pd
import yfinance as yf

from .base import normalize_symbol_frame, validate_ohlcv_frames


class YFinanceDataSource:
    name = "yfinance"

    def __init__(self, lookback_years: int = 5) -> None:
        self.lookback_years = lookback_years

    def load_bars(self, symbols: tuple[str, ...]) -> dict[str, pd.DataFrame]:
        frames: dict[str, pd.DataFrame] = {}
        for symbol in symbols:
            raw = self._download_symbol(symbol)
            if raw.empty:
                raise ValueError(f"No data returned for {symbol}")
            frames[symbol] = normalize_symbol_frame(raw.reset_index() if "Date" not in raw.columns else raw)
        validate_ohlcv_frames(frames)
        return frames

    def _download_symbol(self, symbol: str) -> pd.DataFrame:
        end = datetime.now(tz=UTC).date()
        start = end - timedelta(days=(365 * self.lookback_years) + 30)
        return yf.download(
            symbol,
            start=start.isoformat(),
            end=end.isoformat(),
            auto_adjust=False,
            progress=False,
        )
