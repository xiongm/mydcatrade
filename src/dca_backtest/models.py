from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional

@dataclass
class Plan:
    name: str
    symbols: List[str]
    weights: Dict[str, float]
    contribution_amount: float
    frequency: str  # 'weekly', 'biweekly', 'monthly'

@dataclass
class Trade:
    date: datetime
    symbol: str
    shares: float
    price: float
    amount: float

@dataclass
class PortfolioState:
    cash: float = 0.0
    shares: Dict[str, float] = field(default_factory=dict)
    trades: List[Trade] = field(default_factory=list)
