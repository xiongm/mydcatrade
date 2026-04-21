# DCA Backtest Handoff

## Purpose

This repo is now a working mean reversion backtest project. The next step is **not** to extend it in place for DCA. The goal is to start a **separate repo / separate session** for a long-term DCA backtest product, while selectively reusing ideas and a few patterns from this codebase.

This document is meant to let a fresh session pick up the DCA effort without scanning the whole current repo.

## Current Repo Summary

This repository currently implements a mean reversion backtester with:

- strategy selection from CLI
- pluggable data sources
- one backtest engine tuned for discrete entries/exits
- CSV artifact output
- structured result bundles
- a global HTML portal for latest results

The package name is `mean_reversion` and the console entrypoint is:

```bash
mean-reversion-backtest
```

The current default strategy is:

- `mean_reversion_v1`
- market symbol: `SPY`
- trade symbols: `IVV`, `QQQ`

The current repo should be treated as a **reference implementation**, not the base folder for the DCA project.

## Why DCA Should Be Separate

DCA is materially different from the current system:

- mean reversion assumes entry and exit signals
- mean reversion holds multiple tactical positions with stop loss, max hold days, and cash reserve rules
- DCA is contribution-driven and long-horizon
- DCA typically needs schedules, contribution logic, optional rebalance logic, benchmark comparison, and cash-flow-aware performance reporting

Trying to force DCA into the current engine would produce awkward abstractions and shared config that means different things in different strategies.

The clean call is:

- keep this repo focused on tactical / signal-driven backtests
- start DCA in a new repo with its own domain language

## What To Reuse From This Repo

These parts are worth copying conceptually, or re-implementing with the same shape.

### 1. Data source interface

Useful pattern:

- a registry of named data sources
- a common `load_bars(symbols)` contract
- normalized OHLCV frames

Relevant files:

- [src/mean_reversion/data_sources/base.py](/Users/xm401/projects/mytrade/src/mean_reversion/data_sources/base.py)
- [src/mean_reversion/data_sources/registry.py](/Users/xm401/projects/mytrade/src/mean_reversion/data_sources/registry.py)
- [src/mean_reversion/data_sources/yfinance_source.py](/Users/xm401/projects/mytrade/src/mean_reversion/data_sources/yfinance_source.py)
- [src/mean_reversion/data_sources/csv_source.py](/Users/xm401/projects/mytrade/src/mean_reversion/data_sources/csv_source.py)
- [src/mean_reversion/data_sources/parquet_source.py](/Users/xm401/projects/mytrade/src/mean_reversion/data_sources/parquet_source.py)

For DCA, keep the interface but rename it around portfolio / contribution use cases rather than strategy bars only.

### 2. CLI pattern

Useful pattern:

- small CLI
- explicit `--strategy`
- explicit `--data-source`
- simple orchestration layer

Relevant file:

- [src/mean_reversion/cli.py](/Users/xm401/projects/mytrade/src/mean_reversion/cli.py)

For DCA, the CLI should likely shift toward something like:

- `--plan`
- `--data-source`
- `--start-date`
- `--end-date`
- `--capital` or `--initial-cash`
- `--contribution-amount`
- `--contribution-frequency`

### 3. Result bundle layout

Useful pattern:

- deterministic bundle fingerprint
- history log
- latest view
- summary markdown
- machine-readable review JSON
- HTML report
- global index page

Relevant files:

- [src/mean_reversion/results/writer.py](/Users/xm401/projects/mytrade/src/mean_reversion/results/writer.py)
- [src/mean_reversion/results/fingerprint.py](/Users/xm401/projects/mytrade/src/mean_reversion/results/fingerprint.py)
- [src/mean_reversion/results/paths.py](/Users/xm401/projects/mytrade/src/mean_reversion/results/paths.py)
- [src/mean_reversion/results/models.py](/Users/xm401/projects/mytrade/src/mean_reversion/results/models.py)
- [src/mean_reversion/results/index_generator.py](/Users/xm401/projects/mytrade/src/mean_reversion/results/index_generator.py)

This is probably the strongest piece to reuse for DCA.

### 4. Test style

Useful pattern:

- focused unit tests around backtest behavior
- registry tests
- CLI tests with monkeypatched dependencies
- artifact writer tests

Relevant tests:

- [tests/test_backtest.py](/Users/xm401/projects/mytrade/tests/test_backtest.py)
- [tests/test_cli.py](/Users/xm401/projects/mytrade/tests/test_cli.py)
- [tests/test_data_sources.py](/Users/xm401/projects/mytrade/tests/test_data_sources.py)
- [tests/test_results_writer.py](/Users/xm401/projects/mytrade/tests/test_results_writer.py)

## What Not To Reuse Directly

These are too mean-reversion-specific to serve as a DCA foundation.

### 1. The backtest engine

Relevant file:

- [src/mean_reversion/backtest.py](/Users/xm401/projects/mytrade/src/mean_reversion/backtest.py)

Reasons not to reuse directly:

- assumes entry / exit signals per bar
- assumes trade objects with entry date, exit date, and stop loss
- assumes max hold days
- assumes tactical position sizing from available cash at signal time

DCA needs a different engine centered on:

- cash contribution events
- purchase allocation rules
- optional rebalance events
- share accumulation over time
- position value growth without tactical exits

### 2. Mean reversion strategy classes

Relevant files:

- [src/mean_reversion/strategies/mean_reversion/v1.py](/Users/xm401/projects/mytrade/src/mean_reversion/strategies/mean_reversion/v1.py)
- [src/mean_reversion/strategies/mean_reversion/strict.py](/Users/xm401/projects/mytrade/src/mean_reversion/strategies/mean_reversion/strict.py)
- [src/mean_reversion/strategies/mean_reversion/fast_exit.py](/Users/xm401/projects/mytrade/src/mean_reversion/strategies/mean_reversion/fast_exit.py)

These are rule- and indicator-driven. DCA should instead model:

- asset selection
- contribution schedule
- allocation policy
- optional rebalance policy

### 3. The current config model

Relevant file:

- [src/mean_reversion/config.py](/Users/xm401/projects/mytrade/src/mean_reversion/config.py)

This config currently mixes:

- engine controls
- trade universe defaults
- signal-related parameters

For DCA, build a fresh config model instead of adapting this one.

## Recommended Shape For The New DCA Repo

Use this as the starting architecture, not as a mandatory final design.

```text
src/
  dca_backtest/
    cli.py
    config.py
    engine.py
    schedules.py
    contributions.py
    allocations.py
    plans/
      registry.py
      monthly_buy_and_hold.py
      monthly_target_weight.py
    data_sources/
      base.py
      registry.py
      yfinance_source.py
      csv_source.py
      parquet_source.py
    results/
      writer.py
      fingerprint.py
      paths.py
      models.py
      index_generator.py
    reporting.py
tests/
```

## DCA Domain Model To Use

Use DCA-native concepts. Avoid importing mean-reversion vocabulary into the new repo.

Suggested top-level concepts:

- `Plan`
  - defines target symbols, contribution schedule, allocation rule, optional rebalance rule
- `ContributionSchedule`
  - monthly, biweekly, weekly, custom dates
- `AllocationPolicy`
  - single asset, fixed weights, dynamic weights later
- `ExecutionModel`
  - buy at close, buy at next open, buy at monthly first trading day close, etc.
- `RunContext`
  - plan name, source, symbols, date range, contribution settings, commit hash
- `PortfolioState`
  - cash, holdings, contribution ledger, market value

## Minimum V1 Scope For The New Repo

Keep the first DCA version narrow.

Recommended V1:

- one plan: monthly DCA
- one or more symbols with fixed weights
- contributions on a fixed calendar rule
- buy-only, no rebalance yet
- benchmark comparison optional
- same data source choices as current repo: `yfinance`, `csv`, `parquet`
- same result bundle philosophy: canonical bundle + latest + global portal

Good V1 CLI example:

```bash
python -m dca_backtest.cli \
  --plan monthly_dca_v1 \
  --data-source yfinance
```

## Things The New Session Should Decide Early

The fresh session should answer these first, before coding much:

1. Is DCA single-asset first, or multi-asset fixed-weight first?
2. What is the contribution schedule for V1: monthly only, or monthly plus biweekly?
3. What execution assumption should be used: same-day close, next-day open, or first tradable bar after schedule date?
4. Is cash allowed to accumulate when a scheduled date is not tradable, or should it execute on next available bar automatically?
5. Do we want IRR / money-weighted metrics in V1, or only total value / total invested / unrealized gain / CAGR?
6. Should benchmark comparison be in V1?

## Existing Docs Worth Reading

These docs matter if the new session wants to copy patterns rather than invent them again:

- [docs/superpowers/specs/2026-04-18-data-source-and-strategy-modularization-design.md](/Users/xm401/projects/mytrade/docs/superpowers/specs/2026-04-18-data-source-and-strategy-modularization-design.md)
- [docs/superpowers/specs/2026-04-18-results-review-and-presentation-design.md](/Users/xm401/projects/mytrade/docs/superpowers/specs/2026-04-18-results-review-and-presentation-design.md)
- [docs/superpowers/specs/2026-04-18-global-results-portal-design.md](/Users/xm401/projects/mytrade/docs/superpowers/specs/2026-04-18-global-results-portal-design.md)

These are useful mainly for:

- data-source modularity
- strategy / plan registry patterns
- result persistence
- result presentation

## Current Local Commands In This Repo

These are here only as reference because the new session may want similar setup in the new repo.

Environment:

```bash
uv venv
uv pip install -e '.[dev]'
uv pip install pyarrow
```

Run tests:

```bash
./.venv/bin/python -m pytest -v
```

Run current mean reversion CLI:

```bash
./.venv/bin/python -m mean_reversion.cli --strategy mean_reversion_v1
./.venv/bin/python -m mean_reversion.cli --strategy mean_reversion_v1 --data-source csv
./.venv/bin/python -m mean_reversion.cli --strategy mean_reversion_v1 --data-source parquet
```

## Important Current Repo State

As of `2026-04-19`, this worktree is not clean. There are local modifications and generated artifacts present, including:

- results portal / result writer changes
- CLI / backtest test file changes
- generated `results/`
- several docs under `docs/superpowers/`

That matters because a new DCA effort should not assume this repo is a pristine baseline.

## Recommendation To The Next Session

Use this repo as a pattern library, not as the starting directory.

Concrete recommendation:

1. Create a new repo for DCA.
2. Copy only the concepts that are actually generic:
   data sources, registry pattern, result bundles, report generation approach, and test style.
3. Do not carry over the mean reversion engine or strategy config unchanged.
4. Design DCA around plans, schedules, allocations, and contributions from the start.
5. Keep the first version narrow enough that the engine vocabulary stays clean.

## One-Paragraph Brief For The Next Session

Build a new repo for a DCA backtest system, not an extension of this mean reversion repo. Reuse the current repo's data-source registry pattern, CLI shape, results bundle layout, and testing style, but do not reuse the mean reversion backtest engine or strategy/config model directly. Start with a narrow V1: monthly DCA, fixed symbol set, fixed weights, buy-only, pluggable data sources, and the same structured result output philosophy.
