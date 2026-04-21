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

    # Ensure directory exists
    canonical_dir.mkdir(parents=True, exist_ok=True)
    
    # Always write the reports (HTML/MD) so UI updates take effect
    # but only write the heavy CSV data if it's new
    _write_canonical_bundle(canonical_dir, context, summary, trades, equity_curve, skip_data=deduplicated)

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
    skip_data: bool = False
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

    # Always update metadata and reports
    (canonical_dir / "run_meta.json").write_text(json.dumps(run_meta, indent=2, cls=CustomJSONEncoder))
    (canonical_dir / "summary.json").write_text(json.dumps(summary, indent=2, cls=CustomJSONEncoder))
    (canonical_dir / "summary.md").write_text(summary_md)
    (canonical_dir / "report.html").write_text(report_html)
    (canonical_dir / "charts.json").write_text(json.dumps(charts, indent=2, cls=CustomJSONEncoder))

    # Only write CSVs if data is unique
    if not skip_data:
        trades.to_csv(canonical_dir / "trades.csv", index=False)
        equity_curve.to_csv(canonical_dir / "equity_curve.csv")

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
    return f"{value:+.2%}" if value != 0 else "0.00%"

def _build_summary_markdown(context: RunContext, summary: dict) -> str:
    curr = "¥" if summary.get("currency") == "RMB" else "$"
    return "\n".join(
        [
            f"# Plan: {context.plan.name}",
            "",
            f"- Data Source: {context.data_source}",
            f"- Symbols: {', '.join(context.symbols)}",
            f"- Date Range: {context.date_range}",
            f"- Contribution: {curr}{context.plan.contribution_amount} ({context.plan.frequency})",
            f"- Commit: {context.commit_hash}",
            "",
            "## Performance",
            f"- Cost Basis: {curr}{float(summary.get('total_invested', 0.0)):,.2f}",
            f"- Final Portfolio Value: {curr}{float(summary.get('final_value', 0.0)):,.2f}",
            f"- Total Return: {_format_percentage(float(summary.get('total_return', 0.0)))}",
            f"- CAGR: {_format_percentage(float(summary.get('cagr', 0.0)))}",
            f"- Max Drawdown: {_format_percentage(float(summary.get('max_drawdown', 0.0)))}",
        ]
    )

def _build_charts_payload(equity_curve: pd.DataFrame) -> dict:
    dates = [str(index.date()) for index in equity_curve.index]
    payload = {
        "dates": dates,
        "equity": [float(v) for v in equity_curve["equity"]],
        "basis": [float(v) for v in equity_curve["basis"]],
        "roi_pct": [float(v) for v in equity_curve["roi_pct"]],
    }
    if "comp_equity" in equity_curve:
        payload["comp_equity"] = [float(v) for v in equity_curve["comp_equity"]]
    return payload

def _build_report_html(context: RunContext, summary: dict, charts: dict) -> str:
    invested = float(summary.get('total_invested', 0.0))
    final_value = float(summary.get('final_value', 0.0))
    profit = final_value - invested
    profit_color = "#059669" if profit >= 0 else "#dc2626"
    
    # Currency Handling
    curr = "¥" if summary.get("currency") == "RMB" else "$"
    
    # Build Asset Breakdown Rows
    asset_rows = ""
    symbol_metrics = summary.get("symbol_metrics", [])
    sorted_metrics = sorted(symbol_metrics, key=lambda x: x.get('roi_pct', 0.0), reverse=True)
    for m in sorted_metrics:
        roi = float(m.get('roi_pct', 0.0))
        roi_color = "#059669" if roi >= 0 else "#dc2626"
        asset_rows += f"""
        <tr style="border-bottom: 1px solid #f1f5f9;">
          <td style="padding: 12px; font-weight: bold;">{m['symbol']}</td>
          <td style="padding: 12px; text-align: right;">{m['target_weight']:.1%}</td>
          <td style="padding: 12px; text-align: right;">{curr}{m['basis']:,.2f}</td>
          <td style="padding: 12px; text-align: right;">{curr}{m['final_value']:,.2f}</td>
          <td style="padding: 12px; text-align: right; color: {roi_color}; font-weight: bold;">{roi:+.2%}</td>
          <td style="padding: 12px; text-align: right;">{m['actual_weight']:.1%}</td>
        </tr>"""

    # Build Monthly History Rows
    monthly_rows = ""
    monthly_metrics = summary.get("monthly_metrics", [])
    has_comparison = "comparison" in summary
    comp_header = "<th>Comp. Value</th>" if has_comparison else ""
    
    for m in monthly_metrics:
        m_roi = float(m.get('roi_pct', 0.0))
        m_roi_color = "#059669" if m_roi >= 0 else "#dc2626"
        comp_cell = f"<td>{curr}{m.get('comp_value', 0.0):,.2f}</td>" if has_comparison else ""
        monthly_rows += f"""
        <tr style="border-bottom: 1px solid #f1f5f9; text-align: right;">
          <td style="padding: 12px; text-align: left; font-weight: bold;">{m['month']}</td>
          <td style="padding: 12px;">{curr}{m['invested']:,.2f}</td>
          <td style="padding: 12px;">{curr}{m['basis']:,.2f}</td>
          <td style="padding: 12px;">{curr}{m['value']:,.2f}</td>
          {comp_cell}
          <td style="padding: 12px; color: {m_roi_color}; font-weight: bold;">{m_roi:+.2%}</td>
        </tr>"""

    # Comparison Calculations
    comparison_card = ""
    comparison_details = ""
    if has_comparison:
        comp = summary["comparison"]
        alpha = comp['alpha']
        alpha_color = "#059669" if alpha >= 0 else "#dc2626"
        comparison_card = f"""
        <div class="card">
          <div class="card-label">DCA Alpha</div>
          <div class="card-value" style="color: {alpha_color}">{curr}{alpha:,.2f}</div>
        </div>
        """
        
        installment_rows = ""
        for inst in comp.get("installments", []):
            breakdown_text = ", ".join([f"{b['symbol']}: {curr}{b['amount']:,.0f}" for b in inst["breakdown"]])
            installment_rows += f"""
            <tr style="border-bottom: 1px solid #f1f5f9;">
              <td style="padding: 12px; font-weight: bold;">{inst['date']}</td>
              <td style="padding: 12px; text-align: right; font-weight: bold;">{curr}{inst['total']:,.2f}</td>
              <td style="padding: 12px; color: #64748b; font-size: 0.9em;">{breakdown_text}</td>
            </tr>"""

        comparison_details = f"""
        <div class="section-card">
          <div class="section-header">Comparison Strategy Details: {comp['type']}</div>
          <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin-bottom: 24px;">
            <div style="background: #f8fafc; padding: 16px; border-radius: 8px; border: 1px solid #e2e8f0; text-align: center;">
              <div style="font-size: 10px; color: #64748b; text-transform: uppercase; font-weight: bold; margin-bottom: 4px;">Comp. Final Value</div>
              <div style="font-size: 1.1em; font-weight: bold;">{curr}{comp['final_value']:,.2f}</div>
            </div>
            <div style="background: #f8fafc; padding: 16px; border-radius: 8px; border: 1px solid #e2e8f0; text-align: center;">
              <div style="font-size: 10px; color: #64748b; text-transform: uppercase; font-weight: bold; margin-bottom: 4px;">DCA Delta ($)</div>
              <div style="font-size: 1.1em; font-weight: bold; color: {alpha_color}">{curr}{alpha:,.2f}</div>
            </div>
            <div style="background: #f8fafc; padding: 16px; border-radius: 8px; border: 1px solid #e2e8f0; text-align: center;">
              <div style="font-size: 10px; color: #64748b; text-transform: uppercase; font-weight: bold; margin-bottom: 4px;">DCA Delta (%)</div>
              <div style="font-size: 1.1em; font-weight: bold; color: {alpha_color}">{ (final_value - comp['final_value'])/comp['final_value'] if comp['final_value'] != 0 else 0:+.2%}</div>
            </div>
          </div>
          
          <h4 style="font-size: 11px; text-transform: uppercase; color: #94a3b8; margin-bottom: 8px;">Installment Log</h4>
          <table style="width: 100%; border-collapse: collapse; font-size: 12px;">
            <thead>
              <tr style="border-bottom: 2px solid #e2e8f0; text-align: left; background: #f8fafc;">
                <th style="padding: 12px;">Date</th>
                <th style="padding: 12px; text-align: right;">Amount</th>
                <th style="padding: 12px;">Allocation Breakdown</th>
              </tr>
            </thead>
            <tbody>
              {installment_rows}
            </tbody>
          </table>
        </div>
        """

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{context.plan.name} Report</title>
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif; margin: 40px; color: #333; background: #f8fafc; }}
    .container {{ max-width: 1200px; margin: auto; }}
    h1 {{ color: #1e293b; margin-bottom: 8px; }}
    .subtitle {{ color: #64748b; margin-bottom: 32px; font-size: 0.9em; }}
    .hero-grid {{ display: grid; gap: 16px; margin-bottom: 32px; }}
    .row-1 {{ grid-template-columns: repeat(4, 1fr); }}
    .row-2 {{ grid-template-columns: repeat(3, 1fr); }}
    .card {{ background: white; padding: 20px; border-radius: 12px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); border: 1px solid #e2e8f0; text-align: center; }}
    .card-label {{ font-size: 0.7em; color: #64748b; text-transform: uppercase; font-weight: bold; margin-bottom: 8px; letter-spacing: 0.05em; }}
    .card-value {{ font-size: 1.25em; font-weight: bold; color: #1e293b; }}
    .section-card {{ background: white; padding: 24px; border-radius: 12px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); border: 1px solid #e2e8f0; margin-bottom: 24px; }}
    .section-header {{ font-weight: bold; margin-bottom: 16px; color: #475569; border-bottom: 1px solid #f1f5f9; padding-bottom: 8px; }}
    table {{ width: 100%; border-collapse: collapse; margin-top: 16px; }}
    th {{ text-align: right; padding: 12px; background: #f8fafc; color: #64748b; font-size: 0.75em; text-transform: uppercase; }}
    th:first-child {{ text-align: left; }}
    canvas {{ width: 100% !important; height: auto !important; }}
  </style>
</head>
<body>
  <div class="container">
    <h1>Plan: {context.plan.name}</h1>
    <p class="subtitle">Data Source: {context.data_source} | Date Range: {context.date_range}</p>

    <!-- Row 1: Core Financials -->
    <div class="hero-grid row-1">
      <div class="card">
        <div class="card-label">Cost Basis</div>
        <div class="card-value">{curr}{invested:,.2f}</div>
      </div>
      <div class="card">
        <div class="card-label">Final Portfolio Value</div>
        <div class="card-value">{curr}{final_value:,.2f}</div>
      </div>
      <div class="card">
        <div class="card-label">Total Profit</div>
        <div class="card-value" style="color: {profit_color}">{curr}{profit:,.2f}</div>
      </div>
      {comparison_card}
    </div>

    <!-- Row 2: Performance & Risk -->
    <div class="hero-grid row-2">
      <div class="card">
        <div class="card-label">Total ROI</div>
        <div class="card-value" style="color: {profit_color}">{_format_percentage(float(summary.get('total_return', 0.0)))}</div>
      </div>
      <div class="card">
        <div class="card-label">Annualized ROI</div>
        <div class="card-value" style="color: {profit_color}">{_format_percentage(float(summary.get('cagr', 0.0)))}</div>
      </div>
      <div class="card">
        <div class="card-label">Max Drawdown</div>
        <div class="card-value" style="color: #dc2626">{_format_percentage(float(summary.get('max_drawdown', 0.0)))}</div>
      </div>
    </div>

    <div class="section-card">
      <div class="section-header">Asset Breakdown</div>
      <table>
        <thead>
          <tr>
            <th style="text-align: left;">Symbol</th>
            <th>Target %</th>
            <th>Cost Basis</th>
            <th>Final Value</th>
            <th>ROI %</th>
            <th>Actual %</th>
          </tr>
        </thead>
        <tbody>
          {asset_rows}
        </tbody>
      </table>
    </div>

    {comparison_details}

    <div class="section-card">
      <div class="section-header">Portfolio Value vs. Cost Basis</div>
      <canvas id="mainChart"></canvas>
    </div>

    <div class="section-card">
      <div class="section-header">Monthly Performance History</div>
      <table>
        <thead>
          <tr>
            <th style="text-align: left;">Month</th>
            <th>Invested</th>
            <th>Total Basis</th>
            <th>Portfolio Value</th>
            {comp_header}
            <th>ROI %</th>
          </tr>
        </thead>
        <tbody>
          {monthly_rows}
        </tbody>
      </table>
    </div>

    <script>
      const data = {json.dumps(charts)};
      const currencySymbol = "{curr}";
      
      const mainDatasets = [
        {{
          label: 'Portfolio Value (DCA)',
          data: data.equity,
          borderColor: '#2563eb',
          backgroundColor: 'rgba(37, 99, 235, 0.05)',
          borderWidth: 2,
          pointRadius: 0,
          fill: true,
          tension: 0.1
        }},
        {{
          label: 'Cost Basis',
          data: data.basis,
          borderColor: '#94a3b8',
          backgroundColor: 'rgba(148, 163, 184, 0.1)',
          borderWidth: 1,
          borderDash: [5, 5],
          pointRadius: 0,
          fill: true,
          tension: 0
        }}
      ];

      if (data.comp_equity) {{
        mainDatasets.push({{
          label: 'Lump Sum / Windfall',
          data: data.comp_equity,
          borderColor: '#f59e0b',
          borderWidth: 2,
          borderDash: [2, 2],
          pointRadius: 0,
          fill: false,
          tension: 0.1
        }});
      }}
      
      new Chart(document.getElementById('mainChart'), {{
        type: 'line',
        data: {{
          labels: data.dates,
          datasets: mainDatasets
        }},
        options: {{
          responsive: true,
          interaction: {{ intersect: false, mode: 'index' }},
          scales: {{
            y: {{ 
              ticks: {{ callback: (v) => currencySymbol + v.toLocaleString() }}
            }}
          }}
        }}
      }});
    </script>
  </div>
</body>
</html>"""
