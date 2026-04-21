from .csv_source import CsvDataSource
from .parquet_source import ParquetDataSource
from .yfinance_source import YFinanceDataSource
from .hybrid_source import HybridDataSource
from .akshare_source import AkShareDataSource


DATA_SOURCE_FACTORIES = {
    "yfinance": YFinanceDataSource,
    "csv": CsvDataSource,
    "parquet": ParquetDataSource,
    "hybrid": HybridDataSource,
    "akshare": AkShareDataSource,
}


def list_data_source_names() -> list[str]:
    return sorted(DATA_SOURCE_FACTORIES)


def get_data_source(name: str):
    try:
        return DATA_SOURCE_FACTORIES[name]()
    except KeyError as exc:
        valid = ", ".join(list_data_source_names())
        raise ValueError(f"Unknown data source '{name}'. Valid data sources: {valid}") from exc
