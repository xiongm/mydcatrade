from __future__ import annotations

from pathlib import Path

import pandas as pd

from .base import normalize_symbol_frame, validate_ohlcv_frames


class CsvDataSource:
    name = "csv"

    def __init__(self, root_dir: Path | str = Path("data/csv")) -> None:
        self.root_dir = Path(root_dir)

    def load_bars(self, symbols: tuple[str, ...]) -> dict[str, pd.DataFrame]:
        frames = {}
        for symbol in symbols:
            path = self.root_dir / f"{symbol}.csv"
            frames[symbol] = normalize_symbol_frame(pd.read_csv(path))
        validate_ohlcv_frames(frames)
        return frames
