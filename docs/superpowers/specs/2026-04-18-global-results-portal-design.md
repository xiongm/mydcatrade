# Strategy Intelligence Hub Design

**Date:** 2026-04-18
**Status:** Proposed
**Topic:** Strategy Intelligence Hub (`results/index.html`)

## Goal
Create a central, static HTML dashboard at `results/index.html` (the **Strategy Intelligence Hub**) that allows the user to quickly review recent backtest activity and compare the performance of different strategy configurations (the "Leaderboard").

## Why This Change
As the number of strategy variants, markets, and data sources grows, it becomes difficult to track which run was the latest or which configuration is performing best overall without manually digging into nested directories. A global portal provides immediate visibility into project progress.

## Scope

### In Scope
- Automatic generation of `results/index.html` after every backtest.
- **Recent Activity Section**: Top 5 most recent runs across all strategies.
- **Performance Leaderboard**: Latest "best" result for every unique strategy/market bucket.
- Single-file static HTML with embedded CSS.
- No external JavaScript or CSS framework dependencies.

### Out of Scope
- Interactive sorting or filtering in the browser (static generation only for now).
- Multi-run comparison charts in the global portal.
- Deletion or management of results via the portal.

## Architecture

### Data Discovery
The generator will walk the `results/` directory:
1. **Recent Activity**: 
   - Collect all `history/*.json` files.
   - Parse `timestamp`, `strategy`, `bundle_fingerprint`, and metadata.
   - Extract metrics by reading the corresponding `bundles/<fingerprint>/summary.json`.
   - Sort by timestamp descending and take the top 5.
2. **Leaderboard**:
   - Collect all `latest/latest.json` files.
   - For each, read the `bundles/<fingerprint>/summary.json`.
   - Sort by `total_return` descending.

### File Structure Changes
- Modify: `src/mean_reversion/results/writer.py` to add `update_global_index` function.
- Modify: `src/mean_reversion/cli.py` to invoke `update_global_index` after results are saved.

## UI Design
- **Header**: Project title and "Last Updated" timestamp.
- **Recent Activity Table**: Highlight the very latest run (index 0).
- **Leaderboard Table**: Clear metrics comparison with links to detailed reports.
- **Styling**: Consistent with the existing `report.html` (minimalist, readable, color-coded returns).

## Implementation Strategy
1. Add `update_global_index(root_dir: Path)` to `writer.py`.
2. Implement directory traversal and JSON aggregation.
3. Use a Python f-string or string template to generate the HTML.
4. Wire into `cli.py`.
5. Add a test in `tests/test_results_writer.py` to verify the index is created and contains expected data.

## Success Criteria
- Running a backtest automatically updates/creates `results/index.html`.
- Opening `results/index.html` shows the run just completed at the top of "Recent Activity".
- The "Leaderboard" correctly displays the latest return for each unique strategy/market combo.
