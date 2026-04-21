from __future__ import annotations
import json
from dataclasses import asdict, dataclass
from pathlib import Path
import pandas as pd
from datetime import datetime
from .fingerprint import build_bundle_fingerprint
from .index_generator import update_global_index
from .models import RunContext
from .paths import bundle_dir, history_file, latest_dir

@dataclass(frozen=True)
class WriteResult:
    fingerprint: str
    bundle_dir: Path
    latest_dir: Path
    deduplicated: bool

class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if hasattr(obj, 'isoformat'):
            return obj.isoformat()
        return super().default(obj)

def write_results_bundle(
    root_dir: Path,
    context: RunContext,
    summary: dict,
    trades: pd.DataFrame,
    equity_curve: pd.DataFrame,
) -> WriteResult:
    payload = {
        "summary": summary,
        "trades": trades.to_dict(),
    }
    fingerprint = build_bundle_fingerprint(context, payload)
    canonical_dir = bundle_dir(root_dir, context, fingerprint)
    latest_view = latest_dir(root_dir, context)
    deduplicated = canonical_dir.exists()

    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")

    if not deduplicated:
        canonical_dir.mkdir(parents=True, exist_ok=True)
        _write_canonical_bundle(canonical_dir, context, summary, trades, equity_curve)

    _write_history_record(root_dir, context, fingerprint, deduplicated, timestamp)
    _refresh_latest_view(latest_view, context, fingerprint, canonical_dir, timestamp)
    update_global_index(root_dir)

    return WriteResult(fingerprint=fingerprint, bundle_dir=canonical_dir, latest_dir=latest_view, deduplicated=deduplicated)

def _write_canonical_bundle(
    canonical_dir: Path,
    context: RunContext,
    summary: dict,
    trades: pd.DataFrame,
    equity_curve: pd.DataFrame,
) -> None:
    run_meta = {
        "plan": asdict(context.plan),
        "data_source": context.data_source,
        "symbols": context.symbols,
        "date_range": context.date_range,
        "commit_hash": context.commit_hash
    }
    
    summary_md = _build_summary_markdown(context, summary)
    charts = _build_charts_payload(equity_curve)
    report_html = _build_report_html(context, summary, charts)

    (canonical_dir / "run_meta.json").write_text(json.dumps(run_meta, indent=2, cls=CustomJSONEncoder))
    (canonical_dir / "summary.json").write_text(json.dumps(summary, indent=2, cls=CustomJSONEncoder))
    (canonical_dir / "summary.md").write_text(summary_md)
    trades.to_csv(canonical_dir / "trades.csv", index=False)
    equity_curve.to_csv(canonical_dir / "equity_curve.csv")
    (canonical_dir / "charts.json").write_text(json.dumps(charts, indent=2, cls=CustomJSONEncoder))
    (canonical_dir / "report.html").write_text(report_html)

def _write_history_record(root_dir: Path, context: RunContext, fingerprint: str, deduplicated: bool, timestamp: str) -> None:
    path = history_file(root_dir, context, timestamp)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "timestamp": timestamp,
        "plan": context.plan.name,
        "data_source": context.data_source,
        "bundle_fingerprint": fingerprint,
        "deduplicated": deduplicated,
        "commit_hash": context.commit_hash,
    }
    path.write_text(json.dumps(payload, indent=2, cls=CustomJSONEncoder))

def _refresh_latest_view(latest_view: Path, context: RunContext, fingerprint: str, canonical_dir: Path, timestamp: str) -> None:
    latest_view.mkdir(parents=True, exist_ok=True)
    payload = {
        "plan": context.plan.name,
        "timestamp": timestamp,
        "bundle_fingerprint": fingerprint,
    }
    (latest_view / "latest.json").write_text(json.dumps(payload, indent=2, cls=CustomJSONEncoder))
    (latest_view / "summary.md").write_text((canonical_dir / "summary.md").read_text())
    (latest_view / "report.html").write_text((canonical_dir / "report.html").read_text())

def _format_percentage(value: float) -> str:
    return f"{value:.2%}"

def _build_summary_markdown(context: RunContext, summary: dict) -> str:
    return "\n".join(
        [
            f"# Plan: {context.plan.name}",
            "",
            f"- Data Source: {context.data_source}",
            f"- Symbols: {', '.join(context.symbols)}",
            f"- Date Range: {context.date_range}",
            f"- Contribution: ${context.plan.contribution_amount} ({context.plan.frequency})",
            f"- Commit: {context.commit_hash}",
            "",
            "## Performance",
            f"- Total Invested: ${float(summary.get('total_invested', 0.0)):,.2f}",
            f"- Final Value: ${float(summary.get('final_value', 0.0)):,.2f}",
            f"- Total Return: {_format_percentage(float(summary.get('total_return', 0.0)))}",
            f"- CAGR: {_format_percentage(float(summary.get('cagr', 0.0)))}",
            f"- Max Drawdown: {_format_percentage(float(summary.get('max_drawdown', 0.0)))}",
        ]
    )

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

def _build_report_html(context: RunContext, summary: dict, charts: dict) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{context.plan.name} Report</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 24px; color: #222; }}
    .grid {{ display: grid; grid-template-columns: repeat(2, minmax(200px, 1fr)); gap: 16px; margin-bottom: 24px; }}
    .card {{ border: 1px solid #ddd; padding: 16px; border-radius: 8px; background: #fafafa; }}
    pre {{ background: #f4f4f4; padding: 12px; border-radius: 6px; overflow-x: auto; }}
  </style>
</head>
<body>
  <h1>Plan: {context.plan.name}</h1>
  <p>Data Source: {context.data_source} | Range: {context.date_range}</p>
  <div class="grid">
    <div class="card">
      <h2>Performance</h2>
      <p>Total Invested: ${float(summary.get('total_invested', 0.0)):,.2f}</p>
      <p>Final Value: ${float(summary.get('final_value', 0.0)):,.2f}</p>
      <p>Total Return: {_format_percentage(float(summary.get('total_return', 0.0)))}</p>
      <p>CAGR: {_format_percentage(float(summary.get('cagr', 0.0)))}</p>
      <p>Max Drawdown: {_format_percentage(float(summary.get('max_drawdown', 0.0)))}</p>
    </div>
  </div>
  <h2>Equity Curve</h2>
  <pre>{json.dumps(charts["equity_curve"], indent=2)}</pre>
  <h2>Drawdown Curve</h2>
  <pre>{json.dumps(charts["drawdown_curve"], indent=2)}</pre>
</body>
</html>"""
