import pandas as pd
import pytest
from unittest.mock import MagicMock

from dca_backtest.data_sources.base import normalize_symbol_frame, validate_ohlcv_frames
from dca_backtest.data_sources.csv_source import CsvDataSource
from dca_backtest.data_sources.parquet_source import ParquetDataSource
from dca_backtest.data_sources.yfinance_source import YFinanceDataSource
from dca_backtest.data_sources.hybrid_source import HybridDataSource


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

# --- SMOKE TESTS FOR NEW HYBRID LOGIC ---

def test_hybrid_source_routing_smoke(monkeypatch):
    source = HybridDataSource(root_dir="tests/fixtures/csv_source")
    
    # Mock price loading for all providers to avoid network
    mock_df = pd.DataFrame({
        "open": [10.0], "high": [11.0], "low": [9.0], "close": [10.5], "volume": [1000]
    }, index=pd.to_datetime(["2026-01-02"]))
    
    # 1. Test US Ticker (routes to Yahoo directly as 'SPY')
    source.yf_source.load_bars = MagicMock(return_value={"SPY": mock_df})
    frames = source.load_bars(("SPY",))
    assert "SPY" in frames
    # Verify first argument was correct ticker
    assert source.yf_source.load_bars.call_args[0][0] == ("SPY",)

    # 2. Test A-Share (routes to Yahoo as '600036.SS')
    source.yf_source.load_bars = MagicMock(return_value={"600036.SS": mock_df})
    frames = source.load_bars(("600036",))
    assert "600036" in frames
    assert source.yf_source.load_bars.call_args[0][0] == ("600036.SS",)

def test_hybrid_source_name_resolution_logic(monkeypatch, tmp_path):
    root = tmp_path / "data"
    root.mkdir()
    source = HybridDataSource(root_dir=root)
    
    monkeypatch.setattr(source, "_resolve_name", lambda sym: "Test Company" if sym == "002594" else None)
    
    # Load bars should trigger name discovery
    source.yf_source.load_bars = MagicMock(return_value={"002594.SZ": pd.DataFrame()})
    
    try:
        source.load_bars(("002594",))
    except: pass 
    
    assert source.symbol_names["002594"] == "Test Company"
    assert (root / "002594.json").exists()
