import pandas as pd
import pytest

from dca_backtest.data_sources.base import normalize_symbol_frame, validate_ohlcv_frames
from dca_backtest.data_sources.csv_source import CsvDataSource
from dca_backtest.data_sources.parquet_source import ParquetDataSource
from dca_backtest.data_sources.yfinance_source import YFinanceDataSource


def test_normalize_symbol_frame_standardizes_columns_and_index():
    raw = pd.DataFrame(
        {
            "Date": ["2026-01-02", "2026-01-03"],
            "Open": [100.0, 101.0],
            "High": [101.0, 102.0],
            "Low": [99.0, 100.0],
            "Close": [100.5, 101.5],
            "Volume": [1_000, 2_000],
        }
    )

    normalized = normalize_symbol_frame(raw)

    assert list(normalized.columns) == ["open", "high", "low", "close", "volume"]
    assert normalized.index.name == "date"
    assert normalized.loc[pd.Timestamp("2026-01-02"), "close"] == 100.5


def test_validate_ohlcv_frames_rejects_missing_required_columns():
    frame = pd.DataFrame(
        {"open": [1.0], "high": [1.0], "close": [1.0]},
        index=pd.date_range("2026-01-01", periods=1, name="date"),
    )

    with pytest.raises(ValueError, match="low"):
        validate_ohlcv_frames({"SPY": frame})


def test_yfinance_source_normalizes_downloaded_frames(monkeypatch):
    raw = pd.DataFrame(
        {
            "Date": ["2026-01-02", "2026-01-03"],
            "Open": [100.0, 101.0],
            "High": [101.0, 102.0],
            "Low": [99.0, 100.0],
            "Close": [100.5, 101.5],
            "Volume": [1_000, 2_000],
        }
    )

    source = YFinanceDataSource()
    # Mock download to return our raw frame
    monkeypatch.setattr(source, "_download_symbol", lambda symbol, start_date=None, end_date=None: raw)

    frames = source.load_bars(("SPY",))

    assert "SPY" in frames
    assert frames["SPY"].index.name == "date"
    assert list(frames["SPY"].columns) == ["open", "high", "low", "close", "volume"]


def test_csv_source_loads_one_file_per_symbol_fixture():
    source = CsvDataSource(root_dir="tests/fixtures/csv_source")

    frames = source.load_bars(("SPY", "IVV", "QQQ"))

    assert sorted(frames) == ["IVV", "QQQ", "SPY"]
    assert frames["SPY"].loc["2026-01-02", "close"] == 100.5


def test_parquet_source_loads_one_file_per_symbol_fixture():
    source = ParquetDataSource(root_dir="tests/fixtures/parquet_source")

    frames = source.load_bars(("SPY", "IVV", "QQQ"))

    assert sorted(frames) == ["IVV", "QQQ", "SPY"]
    assert frames["QQQ"].loc["2026-01-03", "open"] == 201.0
