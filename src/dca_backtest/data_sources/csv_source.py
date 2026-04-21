from __future__ import annotations

from pathlib import Path
from typing import Optional

import pandas as pd

from .base import normalize_symbol_frame, validate_ohlcv_frames


class CsvDataSource:
    name = "csv"

    def __init__(self, root_dir: Path | str = Path("data/csv")) -> None:
        self.root_dir = Path(root_dir)

    def load_bars(
        self, 
        symbols: tuple[str, ...], 
        start_date: Optional[str] = None, 
        end_date: Optional[str] = None
    ) -> dict[str, pd.DataFrame]:
        frames = {}
        for symbol in symbols:
            path = self.root_dir / f"{symbol}.csv"
            df = normalize_symbol_frame(pd.read_csv(path))
            
            # Filter by date if provided
            if start_date:
                df = df[df.index >= start_date]
            if end_date:
                df = df[df.index <= end_date]
                
            frames[symbol] = df
        validate_ohlcv_frames(frames)
        return frames
