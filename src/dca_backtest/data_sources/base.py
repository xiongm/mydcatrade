from __future__ import annotations

from typing import Protocol

import pandas as pd


REQUIRED_OHLCV_COLUMNS = ("open", "high", "low", "close", "volume")


class DataSource(Protocol):
    name: str

    def load_bars(self, symbols: tuple[str, ...]) -> dict[str, pd.DataFrame]:
        ...


def normalize_symbol_frame(raw: pd.DataFrame) -> pd.DataFrame:
    if isinstance(raw.columns, pd.MultiIndex):
        raw = raw.copy()
        raw.columns = [first if first else second for first, second in raw.columns.to_flat_index()]

    renamed = raw.rename(
        columns={
            "Date": "date",
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Volume": "volume",
        }
    )
    frame = renamed.loc[:, ["date", *[column for column in REQUIRED_OHLCV_COLUMNS if column in renamed.columns]]].copy()
    frame["date"] = pd.to_datetime(frame["date"], utc=False)
    frame = frame.set_index("date").sort_index()
    frame.index.name = "date"
    validate_ohlcv_frames({"_single": frame})
    return frame


def validate_ohlcv_frames(frames: dict[str, pd.DataFrame]) -> None:
    if not frames:
        raise ValueError("No OHLCV frames supplied")

    for symbol, frame in frames.items():
        missing = [column for column in REQUIRED_OHLCV_COLUMNS if column not in frame.columns]
        if missing:
            raise ValueError(f"{symbol} is missing required OHLCV columns: {missing}")
