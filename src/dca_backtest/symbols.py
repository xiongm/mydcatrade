from pathlib import Path
import json
from typing import Dict, Optional

class SymbolRegistry:
    """
    Systematic resolver for ticker names.
    """
    def __init__(self, config_path: str = "config/symbols.json"):
        self.config_path = Path(config_path)
        self.registry: Dict[str, str] = {}
        self._load_registry()

    def _load_registry(self):
        if self.config_path.exists():
            try:
                self.registry = json.loads(self.config_path.read_text())
            except Exception as e:
                print(f"Warning: Could not load symbol registry from {self.config_path}: {e}")

    def resolve_name(self, symbol: str, discovered_name: Optional[str] = None) -> str:
        """
        Layered resolution:
        1. Local config/symbols.json
        2. Discovered name (from data provider)
        3. Raw symbol
        """
        # 1. Master List
        if symbol in self.registry:
            return self.registry[symbol]
        
        # 2. Discovered (live download)
        if discovered_name:
            return discovered_name
            
        return symbol

    def update(self, symbol: str, name: str):
        """Add a new mapping to the registry."""
        self.registry[symbol] = name
        # We don't auto-save to file to keep the source file clean, 
        # but we could in a 'discovery' mode.
