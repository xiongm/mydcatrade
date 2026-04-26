from __future__ import annotations
from pathlib import Path
from typing import Optional, Dict
import json
import pandas as pd
import re
from .csv_source import CsvDataSource
from .yfinance_source import YFinanceDataSource
from .akshare_source import AkShareDataSource
from .efinance_source import EFinanceDataSource

class HybridDataSource:
    """
    Smart data source with Market Routing, Name Discovery, and Dividend support.
    """
    name = "hybrid"

    def __init__(self, root_dir: Path | str = Path("data/csv")):
        self.csv_source = CsvDataSource(root_dir)
        self.yf_source = YFinanceDataSource()
        self.ak_source = AkShareDataSource()
        self.ef_source = EFinanceDataSource()
        self.root_dir = Path(root_dir)
        self.symbol_names: Dict[str, str] = {}

    def _is_a_share_stock(self, symbol: str) -> bool:
        return bool(re.match(r'^(60|000|002|300|688|900)\d{3,4}$', symbol))

    def _is_fund(self, symbol: str) -> bool:
        if symbol.startswith('F'): return True
        if re.match(r'^\d{6}$', symbol) and not self._is_a_share_stock(symbol): return True
        return False

    def _get_yf_symbol(self, symbol: str) -> str:
        if not re.match(r'^\d{6}$', symbol): return symbol
        if symbol.startswith(('60', '68', '90', '51', '58')): return f"{symbol}.SS"
        return f"{symbol}.SZ"

    def _resolve_name(self, symbol: str) -> str | None:
        meta_path = self.root_dir / f"{symbol}.json"
        if meta_path.exists():
            try: return json.loads(meta_path.read_text()).get("name")
            except Exception: pass
        clean_sym = symbol[1:] if symbol.startswith('F') else symbol
        try:
            if self._is_fund(symbol):
                import akshare as ak
                df_names = ak.fund_name_em()
                matches = df_names[df_names['基金代码'] == clean_sym]
                if not matches.empty: return matches['基金简称'].iloc[0]
            elif self._is_a_share_stock(symbol):
                import efinance as ef
                info = ef.stock.get_base_info(clean_sym)
                if isinstance(info, (pd.Series, dict)): return info.get('股票名称')
                elif isinstance(info, pd.DataFrame) and not info.empty: return info['股票名称'].iloc[0]
            else:
                import yfinance as yf
                ticker = yf.Ticker(symbol)
                return ticker.info.get('shortName') or ticker.info.get('longName')
        except Exception: pass
        return None

    def load_bars(self, symbols: tuple[str, ...], start_date: Optional[str] = None, end_date: Optional[str] = None) -> dict[str, pd.DataFrame]:
        frames = {}
        for symbol in symbols:
            name = self._resolve_name(symbol)
            if name: 
                self.symbol_names[symbol] = name
                meta_path = self.root_dir / f"{symbol}.json"
                if not meta_path.exists():
                    try: meta_path.write_text(json.dumps({"symbol": symbol, "name": name}, ensure_ascii=False))
                    except Exception: pass

            local_path = self.root_dir / f"{symbol}.csv"
            use_local = False
            if local_path.exists():
                try:
                    local_df = self.csv_source.load_bars((symbol,), start_date, end_date)[symbol]
                    if len(local_df) > 5:
                        frames[symbol] = local_df
                        use_local = True
                        print(f"Using local data for {symbol}")
                except Exception: pass
            
            if not use_local:
                success = False
                route = ["yahoo", "efinance", "akshare"] if not self._is_fund(symbol) else ["efinance", "akshare", "yahoo"]
                for provider in route:
                    try:
                        df = None
                        if provider == "yahoo": df = self.yf_source.load_bars((self._get_yf_symbol(symbol),), start_date, end_date)[self._get_yf_symbol(symbol)]
                        elif provider == "efinance": df = self.ef_source.load_bars((symbol[1:] if symbol.startswith('F') else symbol,), start_date, end_date, is_fund_hint=self._is_fund(symbol))[symbol[1:] if symbol.startswith('F') else symbol]
                        elif provider == "akshare": df = self.ak_source.load_bars((symbol[1:] if symbol.startswith('F') else symbol,), start_date, end_date, is_fund_hint=self._is_fund(symbol))[symbol[1:] if symbol.startswith('F') else symbol]
                        
                        if df is not None and not df.empty:
                            if start_date: df = df[df.index >= pd.to_datetime(start_date)]
                            if end_date: df = df[df.index <= pd.to_datetime(end_date)]
                            frames[symbol] = df; success = True; break
                    except Exception as e: print(f"{provider} failed for {symbol}: {e}")
                if not success: raise ValueError(f"Could not fetch {symbol}")
        return frames

    def load_dividends(self, symbols: tuple[str, ...], start_date: Optional[str] = None, end_date: Optional[str] = None) -> dict[str, pd.Series]:
        divs = {}
        for symbol in symbols:
            # 1. Try Local Cache
            local_path = self.root_dir / f"{symbol}_dividends.csv"
            if local_path.exists():
                try:
                    s = pd.read_csv(local_path, index_index=0, parse_dates=True).iloc[:, 0]
                    if start_date: s = s[s.index >= start_date]
                    if end_date: s = s[s.index <= end_date]
                    divs[symbol] = s
                    print(f"Using local dividends for {symbol}")
                    continue
                except Exception: pass

            # 2. Try Live Providers
            success = False
            route = ["yahoo", "efinance", "akshare"] if not self._is_fund(symbol) else ["efinance", "akshare", "yahoo"]
            for provider in route:
                try:
                    source = getattr(self, f"{provider[:2]}_source" if provider != "yahoo" else "yf_source")
                    res = source.load_dividends((self._get_yf_symbol(symbol) if provider == "yahoo" else (symbol[1:] if symbol.startswith('F') else symbol),), start_date, end_date)
                    s = res[list(res.keys())[0]]
                    if not s.empty:
                        divs[symbol] = s; success = True; break
                except Exception: pass
            
            if not success: divs[symbol] = pd.Series(dtype=float)
        return divs
