# DCA Backtest New Session Prompt

I want to start a **new repo**, separate from my existing mean reversion backtest repo, to build a **DCA backtest system**.

Use this existing repo only as a reference pattern library. Do **not** extend it in place.

Context:

- The current repo is focused on mean reversion, with signal-driven entries/exits.
- I want the DCA system to be a long-term product with clear separation.
- Reuse only the generic ideas:
  - data source registry pattern
  - CLI structure
  - results bundle layout
  - HTML/reporting approach
  - testing style
- Do **not** reuse the current mean reversion engine or strategy/config model directly.

What I want from this new session:

1. Read the handoff doc at `docs/2026-04-19-dca-backtest-handoff.md`.
2. Propose the cleanest architecture for a new DCA backtest repo.
3. Keep V1 intentionally narrow:
   - monthly DCA
   - fixed symbol set
   - fixed weights
   - buy-only
   - pluggable data sources (`yfinance`, `csv`, `parquet`)
   - structured results output similar to the current repo
4. Use DCA-native concepts such as plans, schedules, contributions, allocations, and portfolio state.
5. Avoid dragging mean reversion vocabulary into the new design.
6. After design approval, write an implementation plan for the new repo.

Important questions to resolve early:

- single-asset first vs multi-asset fixed-weight first
- contribution schedule for V1
- execution assumption on contribution date
- handling of non-trading scheduled dates
- which performance metrics belong in V1
- whether benchmark comparison is in scope for V1

The goal is to leave this current repo cleanly focused on mean reversion and build DCA as a separate system with its own clear boundaries.
