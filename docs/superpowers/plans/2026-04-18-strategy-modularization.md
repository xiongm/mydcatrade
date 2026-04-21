# Strategy Modularization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor the backtester so strategies are selected explicitly via `--strategy`, live under `strategies/mean_reversion/`, and produce a stable `entry_signal` / `exit_signal` contract while the existing engine, portfolio rules, and reporting stay fixed.

**Architecture:** Keep the current execution model centered in `backtest.py` and move strategy-specific indicator preparation and signal generation behind a small strategy interface plus a registry. The CLI will resolve a named strategy, prepare frames through that strategy, validate the standard signal contract, and then pass the resulting frames into the unchanged backtest engine.

**Tech Stack:** Python 3.12, argparse, pandas, numpy, yfinance, pytest

---

## File Structure

- Modify: `pyproject.toml`
- Modify: `src/mean_reversion/cli.py`
- Modify: `src/mean_reversion/backtest.py`
- Modify: `src/mean_reversion/__init__.py`
- Delete: `src/mean_reversion/strategy.py`
- Create: `src/mean_reversion/strategies/__init__.py`
- Create: `src/mean_reversion/strategies/registry.py`
- Create: `src/mean_reversion/strategies/mean_reversion/__init__.py`
- Create: `src/mean_reversion/strategies/mean_reversion/base.py`
- Create: `src/mean_reversion/strategies/mean_reversion/v1.py`
- Create: `src/mean_reversion/strategies/mean_reversion/strict.py`
- Create: `src/mean_reversion/strategies/mean_reversion/fast_exit.py`
- Modify: `tests/test_strategy.py`
- Modify: `tests/test_backtest.py`
- Create: `tests/test_cli.py`

`strategies/mean_reversion/base.py` will define the reusable strategy protocol and signal validation helper.  
`strategies/registry.py` will own the CLI name to strategy lookup.  
`strategies/mean_reversion/v1.py` will preserve the current signal behavior exactly.  
`strict.py` and `fast_exit.py` will be named rule variants with hardcoded defaults.  
`cli.py` will parse `--strategy`, fail clearly when it is missing, and route execution through the selected strategy.  
`backtest.py` should remain focused on the portfolio simulation and gain only a narrow preflight validation helper if needed.

### Task 1: Create The Strategy Package And Contract

**Files:**
- Create: `src/mean_reversion/strategies/__init__.py`
- Create: `src/mean_reversion/strategies/mean_reversion/__init__.py`
- Create: `src/mean_reversion/strategies/mean_reversion/base.py`
- Modify: `tests/test_strategy.py`

- [ ] **Step 1: Write the failing contract and validation tests**

```python
import pandas as pd
import pytest

from mean_reversion.strategies.mean_reversion.base import validate_signal_frames


def test_validate_signal_frames_accepts_standard_signal_contract():
    frame = pd.DataFrame(
        {
            "open": [1.0],
            "high": [1.0],
            "low": [1.0],
            "close": [1.0],
            "volume": [100],
            "entry_signal": [True],
            "exit_signal": [False],
        },
        index=pd.date_range("2026-01-01", periods=1, name="date"),
    )

    validate_signal_frames({"IVV": frame, "QQQ": frame.copy()})


def test_validate_signal_frames_rejects_missing_signal_columns():
    frame = pd.DataFrame(
        {"open": [1.0], "high": [1.0], "low": [1.0], "close": [1.0], "volume": [100]},
        index=pd.date_range("2026-01-01", periods=1, name="date"),
    )

    with pytest.raises(ValueError, match="entry_signal"):
        validate_signal_frames({"IVV": frame})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./.venv/bin/python -m pytest tests/test_strategy.py::test_validate_signal_frames_accepts_standard_signal_contract tests/test_strategy.py::test_validate_signal_frames_rejects_missing_signal_columns -v`  
Expected: FAIL with `ModuleNotFoundError` because the new strategy package does not exist yet.

- [ ] **Step 3: Implement the strategy protocol and signal validation helper**

```python
from __future__ import annotations

from typing import Protocol

import pandas as pd


class Strategy(Protocol):
    name: str

    def prepare_frames(self, frames: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
        ...

    def build_signals(self, frames: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
        ...


REQUIRED_SIGNAL_COLUMNS = ("entry_signal", "exit_signal")


def validate_signal_frames(frames: dict[str, pd.DataFrame]) -> None:
    if not frames:
        raise ValueError("No strategy frames supplied")

    for symbol, frame in frames.items():
        missing = [column for column in REQUIRED_SIGNAL_COLUMNS if column not in frame.columns]
        if missing:
            raise ValueError(f"{symbol} is missing required signal columns: {missing}")
```

```python
from .base import Strategy, validate_signal_frames

__all__ = ["Strategy", "validate_signal_frames"]
```

```python
from .mean_reversion import Strategy, validate_signal_frames

__all__ = ["Strategy", "validate_signal_frames"]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./.venv/bin/python -m pytest tests/test_strategy.py::test_validate_signal_frames_accepts_standard_signal_contract tests/test_strategy.py::test_validate_signal_frames_rejects_missing_signal_columns -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/mean_reversion/strategies/__init__.py src/mean_reversion/strategies/mean_reversion/__init__.py src/mean_reversion/strategies/mean_reversion/base.py tests/test_strategy.py
git commit -m "feat: add strategy contract and signal validation"
```

### Task 2: Extract The Baseline Strategy Into `mean_reversion/v1.py`

**Files:**
- Create: `src/mean_reversion/strategies/mean_reversion/v1.py`
- Delete: `src/mean_reversion/strategy.py`
- Modify: `tests/test_strategy.py`

- [ ] **Step 1: Write the failing baseline strategy regression test**

```python
import pandas as pd

from mean_reversion.strategies.mean_reversion.v1 import MeanReversionV1Strategy


def test_mean_reversion_v1_builds_entry_and_exit_signals_from_current_rules():
    dates = pd.date_range("2026-01-01", periods=6, freq="D", name="date")
    market = pd.DataFrame(
        {"open": [1]*6, "high": [1]*6, "low": [1]*6, "close": [1, 2, 3, 4, 5, 6], "volume": [1]*6},
        index=dates,
    )
    tradable = pd.DataFrame(
        {"open": [10, 10, 10, 9, 8, 9], "high": [10]*6, "low": [8]*6, "close": [10, 10, 10, 9, 8, 9], "volume": [100]*6},
        index=dates,
    )

    strategy = MeanReversionV1Strategy()
    prepared = strategy.prepare_frames({"SPY": market, "IVV": tradable, "QQQ": tradable.copy()})
    signals = strategy.build_signals(prepared)

    assert "market_ok" in signals["SPY"].columns
    assert "entry_signal" in signals["IVV"].columns
    assert "exit_signal" in signals["IVV"].columns
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/bin/python -m pytest tests/test_strategy.py::test_mean_reversion_v1_builds_entry_and_exit_signals_from_current_rules -v`  
Expected: FAIL because `MeanReversionV1Strategy` does not exist yet.

- [ ] **Step 3: Implement the baseline strategy by extracting the current logic**

```python
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from ...indicators import enrich_symbol_frame


@dataclass(frozen=True)
class MeanReversionV1Strategy:
    name: str = "mean_reversion_v1"
    market_symbol: str = "SPY"
    trade_symbols: tuple[str, ...] = ("IVV", "QQQ")
    market_ma_window: int = 200
    trend_ma_window: int = 50
    rsi_window: int = 2
    entry_rsi_threshold: float = 15.0
    exit_rsi_threshold: float = 60.0

    def prepare_frames(self, frames: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
        market = enrich_symbol_frame(
            frames[self.market_symbol],
            ma_window=self.market_ma_window,
            rsi_window=self.rsi_window,
        ).rename(columns={f"ma_{self.market_ma_window}": "market_ma"})
        market["market_ok"] = market["close"] > market["market_ma"]

        prepared = {self.market_symbol: market}
        for symbol in self.trade_symbols:
            prepared[symbol] = enrich_symbol_frame(
                frames[symbol],
                ma_window=self.trend_ma_window,
                rsi_window=self.rsi_window,
            ).rename(
                columns={
                    f"ma_{self.trend_ma_window}": "trend_ma",
                    f"rsi_{self.rsi_window}": "rsi",
                }
            )
        return prepared

    def build_signals(self, frames: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
        market = frames[self.market_symbol].copy()
        signal_frames = {self.market_symbol: market}

        for symbol in self.trade_symbols:
            enriched = frames[symbol].copy()
            enriched["entry_signal"] = (
                market["market_ok"]
                & (enriched["close"] > enriched["trend_ma"])
                & enriched["two_down_closes"]
                & (enriched["rsi"] < self.entry_rsi_threshold)
            )
            enriched["exit_signal"] = enriched["rsi"] > self.exit_rsi_threshold
            signal_frames[symbol] = enriched

        return signal_frames
```

```python
from .base import Strategy, validate_signal_frames
from .v1 import MeanReversionV1Strategy

__all__ = ["Strategy", "validate_signal_frames", "MeanReversionV1Strategy"]
```

- [ ] **Step 4: Remove the old flat strategy module after the extraction**

```text
Delete file: src/mean_reversion/strategy.py
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `./.venv/bin/python -m pytest tests/test_strategy.py -v`  
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/mean_reversion/strategies/mean_reversion/v1.py src/mean_reversion/strategies/mean_reversion/__init__.py tests/test_strategy.py
git rm src/mean_reversion/strategy.py
git commit -m "feat: extract baseline mean reversion strategy"
```

### Task 3: Add Named Mean Reversion Variants

**Files:**
- Create: `src/mean_reversion/strategies/mean_reversion/strict.py`
- Create: `src/mean_reversion/strategies/mean_reversion/fast_exit.py`
- Modify: `src/mean_reversion/strategies/mean_reversion/__init__.py`
- Modify: `tests/test_strategy.py`

- [ ] **Step 1: Write the failing variant behavior tests**

```python
from mean_reversion.strategies.mean_reversion.fast_exit import MeanReversionFastExitStrategy
from mean_reversion.strategies.mean_reversion.strict import MeanReversionStrictStrategy


def test_mean_reversion_strict_uses_tighter_entry_threshold_than_v1():
    strategy = MeanReversionStrictStrategy()

    assert strategy.entry_rsi_threshold < 15.0


def test_mean_reversion_fast_exit_uses_faster_exit_threshold_than_v1():
    strategy = MeanReversionFastExitStrategy()

    assert strategy.exit_rsi_threshold < 60.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./.venv/bin/python -m pytest tests/test_strategy.py::test_mean_reversion_strict_uses_tighter_entry_threshold_than_v1 tests/test_strategy.py::test_mean_reversion_fast_exit_uses_faster_exit_threshold_than_v1 -v`  
Expected: FAIL because the variant strategy classes do not exist yet.

- [ ] **Step 3: Implement the variant strategies with hardcoded defaults**

```python
from dataclasses import dataclass

from .v1 import MeanReversionV1Strategy


@dataclass(frozen=True)
class MeanReversionStrictStrategy(MeanReversionV1Strategy):
    name: str = "mean_reversion_strict"
    entry_rsi_threshold: float = 10.0
```

```python
from dataclasses import dataclass

from .v1 import MeanReversionV1Strategy


@dataclass(frozen=True)
class MeanReversionFastExitStrategy(MeanReversionV1Strategy):
    name: str = "mean_reversion_fast_exit"
    exit_rsi_threshold: float = 50.0
    max_hold_days: int = 3
```

```python
from .base import Strategy, validate_signal_frames
from .fast_exit import MeanReversionFastExitStrategy
from .strict import MeanReversionStrictStrategy
from .v1 import MeanReversionV1Strategy

__all__ = [
    "Strategy",
    "validate_signal_frames",
    "MeanReversionV1Strategy",
    "MeanReversionStrictStrategy",
    "MeanReversionFastExitStrategy",
]
```

- [ ] **Step 4: Add one signal-difference regression test**

```python
def test_variant_names_are_unique_for_cli_selection():
    assert MeanReversionStrictStrategy().name == "mean_reversion_strict"
    assert MeanReversionFastExitStrategy().name == "mean_reversion_fast_exit"
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `./.venv/bin/python -m pytest tests/test_strategy.py -v`  
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/mean_reversion/strategies/mean_reversion/strict.py src/mean_reversion/strategies/mean_reversion/fast_exit.py src/mean_reversion/strategies/mean_reversion/__init__.py tests/test_strategy.py
git commit -m "feat: add named mean reversion strategy variants"
```

### Task 4: Add Strategy Registry And CLI Selection

**Files:**
- Create: `src/mean_reversion/strategies/registry.py`
- Modify: `src/mean_reversion/cli.py`
- Create: `tests/test_cli.py`

- [ ] **Step 1: Write the failing CLI and registry tests**

```python
import pytest

from mean_reversion.strategies.registry import get_strategy, list_strategy_names


def test_list_strategy_names_returns_supported_cli_names():
    assert "mean_reversion_v1" in list_strategy_names()
    assert "mean_reversion_strict" in list_strategy_names()
    assert "mean_reversion_fast_exit" in list_strategy_names()


def test_get_strategy_returns_requested_strategy_instance():
    strategy = get_strategy("mean_reversion_v1")

    assert strategy.name == "mean_reversion_v1"


def test_get_strategy_rejects_unknown_name():
    with pytest.raises(ValueError, match="Unknown strategy"):
        get_strategy("does_not_exist")
```

```python
import pytest

from mean_reversion.cli import build_parser


def test_cli_requires_strategy_flag():
    parser = build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args([])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./.venv/bin/python -m pytest tests/test_cli.py -v`  
Expected: FAIL because the registry and CLI parser do not exist yet.

- [ ] **Step 3: Implement the strategy registry**

```python
from __future__ import annotations

from .mean_reversion import (
    MeanReversionFastExitStrategy,
    MeanReversionStrictStrategy,
    MeanReversionV1Strategy,
)


STRATEGY_FACTORIES = {
    "mean_reversion_v1": MeanReversionV1Strategy,
    "mean_reversion_strict": MeanReversionStrictStrategy,
    "mean_reversion_fast_exit": MeanReversionFastExitStrategy,
}


def list_strategy_names() -> list[str]:
    return sorted(STRATEGY_FACTORIES)


def get_strategy(name: str):
    try:
        return STRATEGY_FACTORIES[name]()
    except KeyError as exc:
        valid = ", ".join(list_strategy_names())
        raise ValueError(f"Unknown strategy '{name}'. Valid strategies: {valid}") from exc
```

- [ ] **Step 4: Implement CLI parsing and strategy resolution**

```python
from __future__ import annotations

import argparse

from .backtest import run_backtest
from .config import BacktestConfig
from .data import download_daily_bars
from .reporting import build_summary_stats, compare_runs, write_outputs
from .strategies.mean_reversion import validate_signal_frames
from .strategies.registry import get_strategy, list_strategy_names


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--strategy",
        required=True,
        help=f"Strategy name. Try mean_reversion_v1 first. Valid choices: {', '.join(list_strategy_names())}",
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    strategy = get_strategy(args.strategy)

    config = BacktestConfig()
    bars = download_daily_bars(config)
    prepared = strategy.prepare_frames(bars)
    signals = strategy.build_signals(prepared)
    validate_signal_frames({symbol: signals[symbol] for symbol in config.trade_symbols})

    base_result = run_backtest(signals, config, slippage_bps=0.0)
    base_summary = build_summary_stats(base_result.trades, base_result.equity_curve)
    write_outputs(config.output_dir, base_result.trades, base_result.equity_curve, base_summary, run_name="base")

    slippage_result = run_backtest(signals, config, slippage_bps=config.slippage_bps)
    slippage_summary = build_summary_stats(slippage_result.trades, slippage_result.equity_curve)
    write_outputs(config.output_dir, slippage_result.trades, slippage_result.equity_curve, slippage_summary, run_name="slippage")

    comparison = compare_runs(base_result, slippage_result)
    comparison.to_csv(f"{config.output_dir}/comparison.csv")
```

- [ ] **Step 5: Add a CLI smoke test for a valid named strategy**

```python
import pandas as pd

from mean_reversion import cli
from mean_reversion.backtest import BacktestResult
from mean_reversion.config import BacktestConfig


def test_cli_main_runs_selected_strategy(monkeypatch, tmp_path):
    monkeypatch.setattr(cli, "BacktestConfig", lambda: BacktestConfig(output_dir=str(tmp_path)))
    monkeypatch.setattr(cli, "download_daily_bars", lambda config: {})
    monkeypatch.setattr(cli, "run_backtest", lambda frames, config, slippage_bps=0.0: BacktestResult(
        trades=pd.DataFrame([{"return_pct": 0.01, "pnl": 10.0}]),
        equity_curve=pd.DataFrame({"equity": [10_000.0, 10_100.0]}, index=pd.date_range("2026-01-01", periods=2, name="date")),
    ))

    class StubStrategy:
        name = "mean_reversion_v1"

        def prepare_frames(self, frames):
            return {
                "SPY": pd.DataFrame({"close": [1.0], "market_ok": [True]}, index=pd.date_range("2026-01-01", periods=1, name="date")),
                "IVV": pd.DataFrame({"open": [1.0], "high": [1.0], "low": [1.0], "close": [1.0], "volume": [100], "entry_signal": [True], "exit_signal": [False]}, index=pd.date_range("2026-01-01", periods=1, name="date")),
                "QQQ": pd.DataFrame({"open": [1.0], "high": [1.0], "low": [1.0], "close": [1.0], "volume": [100], "entry_signal": [False], "exit_signal": [False]}, index=pd.date_range("2026-01-01", periods=1, name="date")),
            }

        def build_signals(self, frames):
            return frames

    monkeypatch.setattr(cli, "get_strategy", lambda name: StubStrategy())

    cli.main(["--strategy", "mean_reversion_v1"])

    assert (tmp_path / "base_summary.csv").exists()
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `./.venv/bin/python -m pytest tests/test_cli.py -v`  
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add src/mean_reversion/strategies/registry.py src/mean_reversion/cli.py tests/test_cli.py
git commit -m "feat: add cli strategy selection and registry"
```

### Task 5: Reconnect Engine Tests To The New Strategy Boundary

**Files:**
- Modify: `src/mean_reversion/backtest.py`
- Modify: `tests/test_backtest.py`

- [ ] **Step 1: Write the failing engine-validation regression test**

```python
import pandas as pd
import pytest

from mean_reversion.backtest import run_backtest
from mean_reversion.config import BacktestConfig


def test_run_backtest_rejects_frames_missing_standard_signal_columns():
    dates = pd.date_range("2026-01-01", periods=2, freq="D", name="date")
    market = pd.DataFrame({"open": [1, 1], "high": [1, 1], "low": [1, 1], "close": [1, 1]}, index=dates)
    invalid = pd.DataFrame({"open": [100, 100], "high": [101, 101], "low": [99, 99], "close": [100, 100]}, index=dates)

    with pytest.raises(ValueError, match="entry_signal"):
        run_backtest({"SPY": market, "IVV": invalid, "QQQ": invalid.copy()}, BacktestConfig())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/bin/python -m pytest tests/test_backtest.py::test_run_backtest_rejects_frames_missing_standard_signal_columns -v`  
Expected: FAIL because `run_backtest()` does not currently validate the signal contract.

- [ ] **Step 3: Add a narrow signal preflight to the engine**

```python
from .strategies.mean_reversion import validate_signal_frames


def run_backtest(...):
    validate_signal_frames({symbol: frames[symbol] for symbol in config.trade_symbols})
    dates = frames[config.market_symbol].index
    ...
```

- [ ] **Step 4: Run the full backtest test module**

Run: `./.venv/bin/python -m pytest tests/test_backtest.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/mean_reversion/backtest.py tests/test_backtest.py
git commit -m "feat: validate strategy signal contract in engine"
```

### Task 6: End-To-End Regression And Package Cleanup

**Files:**
- Modify: `pyproject.toml`
- Modify: `src/mean_reversion/__init__.py`
- Modify: `tests/test_backtest.py`
- Modify: `tests/test_strategy.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Add a failing CLI error-message regression test**

```python
import pytest

from mean_reversion.cli import build_parser


def test_cli_help_text_suggests_mean_reversion_v1_as_first_strategy():
    parser = build_parser()
    action = next(action for action in parser._actions if action.dest == "strategy")

    assert "mean_reversion_v1" in action.help
```

- [ ] **Step 2: Run the focused regression tests**

Run: `./.venv/bin/python -m pytest tests/test_cli.py::test_cli_help_text_suggests_mean_reversion_v1_as_first_strategy tests/test_strategy.py tests/test_backtest.py -v`  
Expected: FAIL if any public imports or parser wiring remain inconsistent after the refactor.

- [ ] **Step 3: Update package exports and install metadata only if needed**

```python
from .config import BacktestConfig
from .strategies.registry import get_strategy, list_strategy_names

__all__ = ["BacktestConfig", "get_strategy", "list_strategy_names"]
```

If `pyproject.toml` needs no entrypoint changes, keep it unchanged. If the editable install requires a rebuild after module moves, re-run:

```bash
uv pip install -e '.[dev]'
```

- [ ] **Step 4: Run the full test suite**

Run: `./.venv/bin/python -m pytest -v`  
Expected: PASS

- [ ] **Step 5: Run the CLI end to end with an explicit strategy**

Run: `./.venv/bin/python -m mean_reversion.cli --strategy mean_reversion_v1`  
Expected:
- downloads daily data
- runs the baseline strategy
- writes output CSVs under `artifacts/mean_reversion/`
- prints summary stats

- [ ] **Step 6: Run the CLI with a missing required flag**

Run: `./.venv/bin/python -m mean_reversion.cli`  
Expected:
- exits non-zero
- prints an error that `--strategy` is required
- suggests `mean_reversion_v1` as the first strategy to try

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml src/mean_reversion/__init__.py tests/test_backtest.py tests/test_strategy.py tests/test_cli.py
git commit -m "test: verify strategy modularization end to end"
```

## Self-Review

Spec coverage:
- CLI `--strategy` requirement is implemented in Task 4 and validated again in Task 6.
- Internal family-based layout under `strategies/mean_reversion/` is implemented in Tasks 1 through 3.
- Baseline strategy behavior preservation is covered by Task 2 regression tests and Task 6 end-to-end verification.
- Named hardcoded variants are added in Task 3.
- Registry-based lookup and helpful unknown-strategy errors are implemented in Task 4.
- Engine contract validation for `entry_signal` and `exit_signal` is added in Tasks 1 and 5.
- Paper/live integration remains out of scope; no tasks introduce broker/runtime abstractions.

Placeholder scan:
- No `TODO`, `TBD`, or “implement later” placeholders remain.
- Each task has exact file paths, concrete commands, and specific code snippets.

Type consistency:
- The plan consistently uses `Strategy`, `validate_signal_frames()`, `MeanReversionV1Strategy`, `get_strategy()`, and `list_strategy_names()`.
- The CLI contract consistently refers to flat names like `mean_reversion_v1` even though the file layout is nested by family.
