from __future__ import annotations
from pathlib import Path
from typing import Optional
import pandas as pd
import re
from .csv_source import CsvDataSource
from .yfinance_source import YFinanceDataSource
from .akshare_source import AkShareDataSource

class HybridDataSource:
    """
    Smart data source that auto-detects markets:
    1. Prefer local CSV data if available.
    2. Use AkShare for A-shares (6-digit numeric codes).
    3. Use yfinance for everything else (US Equities and Crypto like BTC-USD).
    """
    name = "hybrid"

    def __init__(self, root_dir: Path | str = Path("data/csv")):
        self.csv_source = CsvDataSource(root_dir)
        self.yf_source = YFinanceDataSource()
        self.ak_source = AkShareDataSource()
        self.root_dir = Path(root_dir)

    def _is_a_share(self, symbol: str) -> bool:
        """Checks if symbol is a 6-digit A-share code."""
        return bool(re.match(r'^\d{6}$', symbol))

    def load_bars(
        self, 
        symbols: tuple[str, ...], 
        start_date: Optional[str] = None, 
        end_date: Optional[str] = None
    ) -> dict[str, pd.DataFrame]:
        frames = {}
        for symbol in symbols:
            local_path = self.root_dir / f"{symbol}.csv"
            
            use_local = False
            if local_path.exists():
                try:
                    local_df = self.csv_source.load_bars((symbol,), start_date, end_date)[symbol]
                    if len(local_df) > 5:
                        frames[symbol] = local_df
                        use_local = True
                        print(f"Using local data for {symbol}")
                except Exception:
                    pass
            
            if not use_local:
                if self._is_a_share(symbol):
                    print(f"Routing {symbol} to AkShare (A-share detected)...")
                    frames[symbol] = self.ak_source.load_bars((symbol,), start_date, end_date)[symbol]
                else:
                    # yfinance handles both US Stocks and Crypto (BTC-USD, etc)
                    print(f"Routing {symbol} to yfinance...")
                    frames[symbol] = self.yf_source.load_bars((symbol,), start_date, end_date)[symbol]
        
        return frames
