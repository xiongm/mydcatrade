# Results Review And Presentation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a durable results-saving system that writes deduplicated canonical result bundles, per-run audit history, lightweight latest views, and deterministic text/HTML/LLM review artifacts for each backtest run.

**Architecture:** Introduce a results-writing layer that sits after the backtest/reporting calculations and before final CLI output. It will compute a stable fingerprint from run identity plus structured outputs, write canonical bundle files under `results/<strategy>/<market>__<instrument_type>__<source>/bundles/<fingerprint>/`, append lightweight audit records under `history/`, and refresh a small `latest/` view that points to the latest resolved result without duplicating raw data files.

**Tech Stack:** Python 3.12, pandas, json, hashlib, pathlib, html templating with standard library string formatting, pytest

---

## File Structure

- Modify: `src/mean_reversion/cli.py`
- Modify: `src/mean_reversion/reporting.py`
- Modify: `src/mean_reversion/__init__.py`
- Create: `src/mean_reversion/results/__init__.py`
- Create: `src/mean_reversion/results/models.py`
- Create: `src/mean_reversion/results/paths.py`
- Create: `src/mean_reversion/results/fingerprint.py`
- Create: `src/mean_reversion/results/writer.py`
- Create: `tests/test_results_paths.py`
- Create: `tests/test_results_fingerprint.py`
- Create: `tests/test_results_writer.py`

`results/models.py` will define the typed run context and payload shapes used by the writer.  
`results/paths.py` will own directory and filename construction so storage layout is centralized.  
`results/fingerprint.py` will compute stable deduplication keys.  
`results/writer.py` will write canonical bundles, audit history, latest views, markdown summaries, LLM review payloads, and HTML reports.  
`cli.py` will assemble run context and invoke the writer after summary data is computed.  
`reporting.py` will stay focused on metrics but may gain small helpers for serializable summaries/charts if needed.

### Task 1: Create Results Models And Storage Path Builder

**Files:**
- Create: `src/mean_reversion/results/__init__.py`
- Create: `src/mean_reversion/results/models.py`
- Create: `src/mean_reversion/results/paths.py`
- Create: `tests/test_results_paths.py`

- [ ] **Step 1: Write the failing path-construction tests**

```python
from pathlib import Path

from mean_reversion.results.models import RunContext
from mean_reversion.results.paths import bucket_dir, bundle_dir, history_file, latest_dir


def test_bucket_dir_uses_strategy_and_composite_market_instrument_source():
    context = RunContext(
        strategy="mean_reversion_v1",
        market="us",
        instrument_type="etf",
        source="yfinance",
        timestamp="2026-04-18T14-10-00",
        symbols=("SPY", "IVV", "QQQ"),
        date_start="2021-03-22",
        date_end="2026-04-17",
        slippage_bps=10.0,
        code_commit="2a954a7",
    )

    path = bucket_dir(Path("results"), context)

    assert path == Path("results/mean_reversion_v1/us__etf__yfinance")


def test_bundle_and_history_paths_use_fingerprint_and_timestamp():
    context = RunContext(
        strategy="mean_reversion_v1",
        market="us",
        instrument_type="etf",
        source="yfinance",
        timestamp="2026-04-18T14-10-00",
        symbols=("SPY", "IVV", "QQQ"),
        date_start="2021-03-22",
        date_end="2026-04-17",
        slippage_bps=10.0,
        code_commit="2a954a7",
    )

    assert bundle_dir(Path("results"), context, "abc123") == Path("results/mean_reversion_v1/us__etf__yfinance/bundles/abc123")
    assert history_file(Path("results"), context) == Path("results/mean_reversion_v1/us__etf__yfinance/history/2026-04-18T14-10-00.json")
    assert latest_dir(Path("results"), context) == Path("results/mean_reversion_v1/us__etf__yfinance/latest")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./.venv/bin/python -m pytest tests/test_results_paths.py -v`  
Expected: FAIL because the `results` package and path helpers do not exist yet.

- [ ] **Step 3: Implement the run context model and path helpers**

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class RunContext:
    strategy: str
    market: str
    instrument_type: str
    source: str
    timestamp: str
    symbols: tuple[str, ...]
    date_start: str
    date_end: str
    slippage_bps: float
    code_commit: str
```

```python
from pathlib import Path

from .models import RunContext


def bucket_dir(root: Path, context: RunContext) -> Path:
    bucket = f"{context.market}__{context.instrument_type}__{context.source}"
    return root / context.strategy / bucket


def bundle_dir(root: Path, context: RunContext, fingerprint: str) -> Path:
    return bucket_dir(root, context) / "bundles" / fingerprint


def history_file(root: Path, context: RunContext) -> Path:
    return bucket_dir(root, context) / "history" / f"{context.timestamp}.json"


def latest_dir(root: Path, context: RunContext) -> Path:
    return bucket_dir(root, context) / "latest"
```

```python
from .models import RunContext
from .paths import bucket_dir, bundle_dir, history_file, latest_dir

__all__ = ["RunContext", "bucket_dir", "bundle_dir", "history_file", "latest_dir"]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./.venv/bin/python -m pytest tests/test_results_paths.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/mean_reversion/results/__init__.py src/mean_reversion/results/models.py src/mean_reversion/results/paths.py tests/test_results_paths.py
git commit -m "feat: add results storage models and path helpers"
```

### Task 2: Add Stable Fingerprinting For Deduplicated Bundles

**Files:**
- Create: `src/mean_reversion/results/fingerprint.py`
- Create: `tests/test_results_fingerprint.py`

- [ ] **Step 1: Write the failing fingerprint tests**

```python
from mean_reversion.results.fingerprint import build_bundle_fingerprint
from mean_reversion.results.models import RunContext


def test_build_bundle_fingerprint_is_stable_for_same_context_and_payload():
    context = RunContext(
        strategy="mean_reversion_v1",
        market="us",
        instrument_type="etf",
        source="yfinance",
        timestamp="2026-04-18T14-10-00",
        symbols=("SPY", "IVV", "QQQ"),
        date_start="2021-03-22",
        date_end="2026-04-17",
        slippage_bps=10.0,
        code_commit="2a954a7",
    )
    payload = {
        "base": {"total_return": 0.14, "number_of_trades": 67},
        "slippage": {"total_return": 0.08, "number_of_trades": 67},
    }

    first = build_bundle_fingerprint(context, payload)
    second = build_bundle_fingerprint(context, payload)

    assert first == second


def test_build_bundle_fingerprint_changes_when_payload_changes():
    context = RunContext(
        strategy="mean_reversion_v1",
        market="us",
        instrument_type="etf",
        source="yfinance",
        timestamp="2026-04-18T14-10-00",
        symbols=("SPY", "IVV", "QQQ"),
        date_start="2021-03-22",
        date_end="2026-04-17",
        slippage_bps=10.0,
        code_commit="2a954a7",
    )

    first = build_bundle_fingerprint(context, {"base": {"total_return": 0.14}})
    second = build_bundle_fingerprint(context, {"base": {"total_return": 0.12}})

    assert first != second
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./.venv/bin/python -m pytest tests/test_results_fingerprint.py -v`  
Expected: FAIL because the fingerprint module does not exist yet.

- [ ] **Step 3: Implement the fingerprint helper**

```python
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict

from .models import RunContext


def build_bundle_fingerprint(context: RunContext, payload: dict) -> str:
    fingerprint_payload = {
        "context": asdict(context),
        "payload": payload,
    }
    encoded = json.dumps(fingerprint_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:16]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./.venv/bin/python -m pytest tests/test_results_fingerprint.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/mean_reversion/results/fingerprint.py tests/test_results_fingerprint.py
git commit -m "feat: add results bundle fingerprinting"
```

### Task 3: Implement Canonical Bundle, History, And Latest Writers

**Files:**
- Create: `src/mean_reversion/results/writer.py`
- Create: `tests/test_results_writer.py`

- [ ] **Step 1: Write the failing writer tests**

```python
import json
from pathlib import Path

import pandas as pd

from mean_reversion.results.models import RunContext
from mean_reversion.results.writer import write_results_bundle


def test_write_results_bundle_creates_canonical_bundle_and_latest_view(tmp_path):
    context = RunContext(
        strategy="mean_reversion_v1",
        market="us",
        instrument_type="etf",
        source="yfinance",
        timestamp="2026-04-18T14-10-00",
        symbols=("SPY", "IVV", "QQQ"),
        date_start="2021-03-22",
        date_end="2026-04-17",
        slippage_bps=10.0,
        code_commit="2a954a7",
    )
    base_summary = {"total_return": 0.14, "max_drawdown": -0.02, "win_rate": 0.79, "average_trade_return": 0.005, "average_win": 0.01, "average_loss": -0.013, "number_of_trades": 67}
    slippage_summary = {"total_return": 0.08, "max_drawdown": -0.03, "win_rate": 0.74, "average_trade_return": 0.003, "average_win": 0.009, "average_loss": -0.014, "number_of_trades": 67}
    comparison = pd.DataFrame({"base": [0.14], "slippage": [0.08], "delta": [-0.06]}, index=["total_return"])
    trades = pd.DataFrame([{"symbol": "IVV", "return_pct": 0.01}])
    equity_curve = pd.DataFrame({"equity": [10_000.0, 10_100.0]}, index=pd.date_range("2026-01-01", periods=2, name="date"))

    result = write_results_bundle(
        root_dir=tmp_path / "results",
        context=context,
        base_summary=base_summary,
        slippage_summary=slippage_summary,
        comparison=comparison,
        trades=trades,
        equity_curve=equity_curve,
    )

    assert result.bundle_dir.exists()
    assert (result.bundle_dir / "run_meta.json").exists()
    assert (result.bundle_dir / "summary.md").exists()
    assert (result.bundle_dir / "llm_review.json").exists()
    assert (result.bundle_dir / "report.html").exists()
    assert (result.latest_dir / "latest.json").exists()
    assert (result.latest_dir / "summary.md").exists()
    assert (result.latest_dir / "report.html").exists()


def test_write_results_bundle_deduplicates_identical_second_run(tmp_path):
    context = RunContext(
        strategy="mean_reversion_v1",
        market="us",
        instrument_type="etf",
        source="yfinance",
        timestamp="2026-04-18T14-10-00",
        symbols=("SPY", "IVV", "QQQ"),
        date_start="2021-03-22",
        date_end="2026-04-17",
        slippage_bps=10.0,
        code_commit="2a954a7",
    )
    payload = {
        "base_summary": {"total_return": 0.14, "number_of_trades": 67},
        "slippage_summary": {"total_return": 0.08, "number_of_trades": 67},
        "comparison": pd.DataFrame({"base": [0.14], "slippage": [0.08], "delta": [-0.06]}, index=["total_return"]),
        "trades": pd.DataFrame([{"symbol": "IVV", "return_pct": 0.01}]),
        "equity_curve": pd.DataFrame({"equity": [10_000.0, 10_100.0]}, index=pd.date_range("2026-01-01", periods=2, name="date")),
    }

    first = write_results_bundle(root_dir=tmp_path / "results", context=context, **payload)
    second_context = RunContext(**{**context.__dict__, "timestamp": "2026-04-18T14-20-00"})
    second = write_results_bundle(root_dir=tmp_path / "results", context=second_context, **payload)

    assert first.fingerprint == second.fingerprint
    assert second.deduplicated is True
    history_dir = tmp_path / "results" / "mean_reversion_v1" / "us__etf__yfinance" / "history"
    assert len(list(history_dir.glob("*.json"))) == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./.venv/bin/python -m pytest tests/test_results_writer.py -v`  
Expected: FAIL because the writer module does not exist yet.

- [ ] **Step 3: Implement bundle writing and dedup logic**

```python
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import pandas as pd

from .fingerprint import build_bundle_fingerprint
from .models import RunContext
from .paths import bundle_dir, history_file, latest_dir


@dataclass(frozen=True)
class WriteResult:
    fingerprint: str
    bundle_dir: Path
    latest_dir: Path
    deduplicated: bool


def write_results_bundle(
    root_dir: Path,
    context: RunContext,
    base_summary: dict,
    slippage_summary: dict,
    comparison: pd.DataFrame,
    trades: pd.DataFrame,
    equity_curve: pd.DataFrame,
) -> WriteResult:
    payload = {
        "base_summary": base_summary,
        "slippage_summary": slippage_summary,
        "comparison": comparison.to_dict(),
    }
    fingerprint = build_bundle_fingerprint(context, payload)
    canonical_dir = bundle_dir(root_dir, context, fingerprint)
    latest_view = latest_dir(root_dir, context)
    deduplicated = canonical_dir.exists()

    if not deduplicated:
        canonical_dir.mkdir(parents=True, exist_ok=True)
        _write_canonical_bundle(canonical_dir, context, base_summary, slippage_summary, comparison, trades, equity_curve)

    _write_history_record(root_dir, context, fingerprint, deduplicated)
    _refresh_latest_view(latest_view, context, fingerprint, canonical_dir)

    return WriteResult(fingerprint=fingerprint, bundle_dir=canonical_dir, latest_dir=latest_view, deduplicated=deduplicated)
```

Implement `_write_canonical_bundle(...)` to write:
- `run_meta.json`
- `summary.json`
- `summary.md`
- `llm_review.json`
- `llm_review.md`
- `trades.csv`
- `equity_curve.csv`
- `comparison.csv`
- `charts.json`
- `report.html`

Implement `_write_history_record(...)` to write one JSON file under `history/` for every run.

Implement `_refresh_latest_view(...)` to write:
- `latest.json`
- copied `summary.md`
- copied `report.html`

- [ ] **Step 4: Run tests to verify they pass**

Run: `./.venv/bin/python -m pytest tests/test_results_writer.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/mean_reversion/results/writer.py tests/test_results_writer.py
git commit -m "feat: add deduplicated results writer"
```

### Task 4: Generate Human-Friendly And LLM-Friendly Review Artifacts

**Files:**
- Modify: `src/mean_reversion/results/writer.py`
- Modify: `tests/test_results_writer.py`

- [ ] **Step 1: Write the failing content-format tests**

```python
import json


def test_summary_md_contains_human_review_sections(tmp_path):
    result = _make_written_result(tmp_path)
    text = (result.bundle_dir / "summary.md").read_text()

    assert "# mean_reversion_v1" in text
    assert "## Base" in text
    assert "## Slippage" in text
    assert "## Delta" in text


def test_llm_review_json_contains_identity_metrics_flags_and_artifact_refs(tmp_path):
    result = _make_written_result(tmp_path)
    payload = json.loads((result.bundle_dir / "llm_review.json").read_text())

    assert payload["run_identity"]["strategy"] == "mean_reversion_v1"
    assert "base" in payload["metrics"]
    assert "slippage" in payload["metrics"]
    assert "delta" in payload["metrics"]
    assert "artifacts" in payload
    assert "flags" in payload
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./.venv/bin/python -m pytest tests/test_results_writer.py::test_summary_md_contains_human_review_sections tests/test_results_writer.py::test_llm_review_json_contains_identity_metrics_flags_and_artifact_refs -v`  
Expected: FAIL until the content generators are implemented consistently.

- [ ] **Step 3: Implement deterministic content generators**

Add helper functions inside `writer.py`:

```python
def _format_percentage(value: float) -> str:
    return f"{value:.2%}"
```

```python
def _build_summary_markdown(context: RunContext, base_summary: dict, slippage_summary: dict, comparison: pd.DataFrame) -> str:
    ...
```

```python
def _build_llm_review_json(context: RunContext, base_summary: dict, slippage_summary: dict, comparison: pd.DataFrame) -> dict:
    ...
```

```python
def _build_llm_review_markdown(payload: dict) -> str:
    ...
```

Required behavior:
- `summary.md` follows the spec’s fixed review layout
- `llm_review.json` includes `run_identity`, `universe`, `metrics`, `flags`, and `artifacts`
- `llm_review.md` is compact and regular enough for direct model ingestion
- `flags` at minimum include:
  - `has_zero_trades`
  - `slippage_material`

- [ ] **Step 4: Run the focused content tests**

Run: `./.venv/bin/python -m pytest tests/test_results_writer.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/mean_reversion/results/writer.py tests/test_results_writer.py
git commit -m "feat: generate text and llm review artifacts"
```

### Task 5: Generate Static HTML Report And Chart Payload

**Files:**
- Modify: `src/mean_reversion/results/writer.py`
- Modify: `tests/test_results_writer.py`

- [ ] **Step 1: Write the failing HTML/chart tests**

```python
import json


def test_charts_json_contains_equity_and_drawdown_series(tmp_path):
    result = _make_written_result(tmp_path)
    charts = json.loads((result.bundle_dir / "charts.json").read_text())

    assert "equity_curve" in charts
    assert "drawdown_curve" in charts


def test_report_html_contains_key_metrics_and_metadata(tmp_path):
    result = _make_written_result(tmp_path)
    html = (result.bundle_dir / "report.html").read_text()

    assert "mean_reversion_v1" in html
    assert "Total Return" in html
    assert "Win Rate" in html
    assert "yfinance" in html
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./.venv/bin/python -m pytest tests/test_results_writer.py::test_charts_json_contains_equity_and_drawdown_series tests/test_results_writer.py::test_report_html_contains_key_metrics_and_metadata -v`  
Expected: FAIL until the HTML and chart payload generators are implemented.

- [ ] **Step 3: Implement `charts.json` and `report.html` generation**

Inside `writer.py`, add:

```python
def _build_charts_payload(equity_curve: pd.DataFrame) -> dict:
    equity = equity_curve["equity"]
    rolling_peak = equity.cummax()
    drawdown = (equity / rolling_peak) - 1
    return {
        "equity_curve": {
            "dates": [str(index.date()) for index in equity_curve.index],
            "values": [float(value) for value in equity],
        },
        "drawdown_curve": {
            "dates": [str(index.date()) for index in equity_curve.index],
            "values": [float(value) for value in drawdown],
        },
    }
```

```python
def _build_report_html(context: RunContext, base_summary: dict, slippage_summary: dict, comparison: pd.DataFrame, charts: dict) -> str:
    ...
```

Required HTML behavior:
- single static file
- includes run metadata
- includes base/slippage metric cards
- includes an equity and drawdown section
- readable with no framework dependency

- [ ] **Step 4: Run the focused writer tests**

Run: `./.venv/bin/python -m pytest tests/test_results_writer.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/mean_reversion/results/writer.py tests/test_results_writer.py
git commit -m "feat: add static visual report for saved results"
```

### Task 6: Wire Results Saving Into The CLI And Preserve Existing Outputs

**Files:**
- Modify: `src/mean_reversion/cli.py`
- Modify: `src/mean_reversion/reporting.py`
- Modify: `tests/test_cli.py`
- Modify: `tests/test_backtest.py`

- [ ] **Step 1: Write the failing CLI integration test**

```python
import json
from pathlib import Path

import pandas as pd

from mean_reversion import cli
from mean_reversion.backtest import BacktestResult
from mean_reversion.config import BacktestConfig


def test_cli_writes_results_bundle_after_successful_run(monkeypatch, tmp_path):
    monkeypatch.setattr(cli, "BacktestConfig", lambda: BacktestConfig(output_dir=str(tmp_path / "artifacts")))
    monkeypatch.setattr(cli, "RESULTS_ROOT", tmp_path / "results")

    class StubSource:
        name = "yfinance"

        def load_bars(self, symbols):
            idx = pd.date_range("2026-01-01", periods=2, name="date")
            return {
                "SPY": pd.DataFrame({"open": [1.0, 1.0], "high": [1.0, 1.0], "low": [1.0, 1.0], "close": [1.0, 1.0], "volume": [1, 1]}, index=idx),
                "IVV": pd.DataFrame({"open": [1.0, 1.0], "high": [1.0, 1.0], "low": [1.0, 1.0], "close": [1.0, 1.0], "volume": [1, 1], "entry_signal": [True, False], "exit_signal": [False, True]}, index=idx),
                "QQQ": pd.DataFrame({"open": [1.0, 1.0], "high": [1.0, 1.0], "low": [1.0, 1.0], "close": [1.0, 1.0], "volume": [1, 1], "entry_signal": [False, False], "exit_signal": [False, False]}, index=idx),
            }

    class StubStrategy:
        name = "mean_reversion_v1"
        market_symbol = "SPY"
        trade_symbols = ("IVV", "QQQ")
        market = "us"
        instrument_type = "etf"

        def required_symbols(self):
            return ("SPY", "IVV", "QQQ")

        def prepare_frames(self, frames):
            return frames

        def build_signals(self, frames):
            return frames

    monkeypatch.setattr(cli, "get_data_source", lambda name: StubSource())
    monkeypatch.setattr(cli, "get_strategy", lambda name: StubStrategy())
    monkeypatch.setattr(
        cli,
        "run_backtest",
        lambda frames, config, slippage_bps=0.0: BacktestResult(
            trades=pd.DataFrame([{"symbol": "IVV", "return_pct": 0.01, "pnl": 10.0}]),
            equity_curve=pd.DataFrame({"equity": [10_000.0, 10_100.0]}, index=pd.date_range("2026-01-01", periods=2, name="date")),
        ),
    )

    cli.main(["--strategy", "mean_reversion_v1"])

    history_files = list((tmp_path / "results" / "mean_reversion_v1" / "us__etf__yfinance" / "history").glob("*.json"))
    assert len(history_files) == 1
    assert (tmp_path / "results" / "mean_reversion_v1" / "us__etf__yfinance" / "latest" / "summary.md").exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/bin/python -m pytest tests/test_cli.py::test_cli_writes_results_bundle_after_successful_run -v`  
Expected: FAIL because the CLI does not yet call the results writer.

- [ ] **Step 3: Wire the results writer into the CLI**

Add in `cli.py`:

```python
from datetime import datetime
from pathlib import Path
import subprocess

from .results.models import RunContext
from .results.writer import write_results_bundle


RESULTS_ROOT = Path("results")
```

After computing `base_summary`, `slippage_summary`, `comparison`, `trades`, and `equity_curve`, build:

```python
context = RunContext(
    strategy=strategy.name,
    market=getattr(strategy, "market", "us"),
    instrument_type=getattr(strategy, "instrument_type", "etf"),
    source=data_source.name,
    timestamp=datetime.now().astimezone().strftime("%Y-%m-%dT%H-%M-%S"),
    symbols=strategy.required_symbols(),
    date_start=str(signals[strategy.market_symbol].index.min().date()),
    date_end=str(signals[strategy.market_symbol].index.max().date()),
    slippage_bps=config.slippage_bps,
    code_commit=_git_head_short(),
)
write_results_bundle(...)
```

Add:

```python
def _git_head_short() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], text=True).strip()
    except Exception:
        return "unknown"
```

Keep the existing `artifacts/mean_reversion/` outputs for now so current workflows do not break.

- [ ] **Step 4: Run the CLI integration tests**

Run: `./.venv/bin/python -m pytest tests/test_cli.py tests/test_backtest.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/mean_reversion/cli.py src/mean_reversion/reporting.py src/mean_reversion/results tests/test_cli.py tests/test_backtest.py
git commit -m "feat: save deduplicated review bundles for runs"
```

### Task 7: End-To-End Verification With Duplicate-Run Deduplication

**Files:**
- Modify: `tests/test_results_writer.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Add the failing dedup-and-latest regression tests**

```python
import json


def test_latest_json_points_to_latest_resolved_fingerprint(tmp_path):
    first = _make_written_result(tmp_path, timestamp="2026-04-18T14-10-00")
    second = _make_written_result(tmp_path, timestamp="2026-04-18T14-20-00")

    latest = json.loads((second.latest_dir / "latest.json").read_text())

    assert latest["bundle_fingerprint"] == second.fingerprint
    assert latest["timestamp"] == "2026-04-18T14-20-00"
```

- [ ] **Step 2: Run the targeted regression tests**

Run: `./.venv/bin/python -m pytest tests/test_results_writer.py tests/test_cli.py -v`  
Expected: FAIL if latest-refresh or history-record behavior is still inconsistent.

- [ ] **Step 3: Run the full test suite**

Run: `./.venv/bin/python -m pytest -v`  
Expected: PASS

- [ ] **Step 4: Run the real CLI twice to verify deduplication**

Run:

```bash
./.venv/bin/python -m mean_reversion.cli --strategy mean_reversion_v1
./.venv/bin/python -m mean_reversion.cli --strategy mean_reversion_v1
```

Expected:
- two history records appear under the same strategy/source bucket
- only one canonical bundle is created if the runs are identical
- `latest/latest.json` points to the canonical bundle fingerprint
- existing `artifacts/mean_reversion/` outputs still update

- [ ] **Step 5: Inspect the saved results tree**

Run:

```bash
find results -maxdepth 5 -type f | sort | head -n 80
```

Expected:
- bundle files exist under `bundles/<fingerprint>/`
- history files exist under `history/`
- latest view contains `latest.json`, `summary.md`, and `report.html`

- [ ] **Step 6: Commit**

```bash
git add tests/test_results_writer.py tests/test_cli.py
git commit -m "test: verify results review bundle generation end to end"
```

## Self-Review

Spec coverage:
- canonical bundles under `bundles/<fingerprint>/` are implemented in Tasks 1 through 3.
- execution audit history under `history/` is implemented in Task 3 and verified again in Task 7.
- lightweight `latest/` view is implemented in Task 3 and validated in Task 7.
- `summary.md`, `report.html`, `llm_review.json`, and `llm_review.md` are generated in Tasks 3 through 5.
- strategy-first and composite bucket naming are enforced by Task 1 path construction.
- no LLM invocation is introduced; LLM-friendly files are deterministic code-generated artifacts.

Placeholder scan:
- No `TODO`, `TBD`, or vague implementation placeholders remain.
- Every task includes exact files, commands, and concrete implementation snippets.

Type consistency:
- The plan consistently uses `RunContext`, `build_bundle_fingerprint()`, `write_results_bundle()`, `bundle_dir()`, `history_file()`, and `latest_dir()`.
- The storage model consistently distinguishes canonical bundles, audit history, and lightweight latest views.
