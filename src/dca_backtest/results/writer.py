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

# DEFINITIVE REGISTRY FOR COMMON CHINESE TICKERS
MANUAL_NAME_OVERRIDE = {
    "000051": "Huatai-PB CSI 300 A",
    "F000051": "Huatai-PB CSI 300 A",
    "008396": "Bosera CSI 500 C",
    "F008396": "Bosera CSI 500 C",
    "600036": "China Merchants Bank",
    "002594": "BYD Company",
    "000001": "Ping An Bank",
    "009504": "Fullgoal Gold ETF Feeder",
    "F009504": "Fullgoal Gold ETF Feeder"
}

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
    canonical_dir.mkdir(parents=True, exist_ok=True)
    
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
    
    charts = _build_charts_payload(equity_curve)
    report_html = _build_report_html(context, summary, charts)

    (canonical_dir / "run_meta.json").write_text(json.dumps(run_meta, indent=2, cls=CustomJSONEncoder))
    (canonical_dir / "summary.json").write_text(json.dumps(summary, indent=2, cls=CustomJSONEncoder))
    (canonical_dir / "report.html").write_text(report_html)
    (canonical_dir / "charts.json").write_text(json.dumps(charts, indent=2, cls=CustomJSONEncoder))

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
    (latest_view / "report.html").write_text((canonical_dir / "report.html").read_text())

def _format_percentage(value: float) -> str:
    return f"{value:+.2%}" if value != 0 else "0.00%"

def _build_charts_payload(equity_curve: pd.DataFrame) -> dict:
    dates = [str(index.date()) for index in equity_curve.index]
    payload = {
        "dates": dates,
        "equity": [float(v) for v in equity_curve["equity"]],
        "basis": [float(v) for v in equity_curve["basis"]],
        "roi_pct": [float(v) for v in equity_curve["roi_pct"]],
        "dividend_accum": [float(v) for v in equity_curve.get("dividend_accum", [])]
    }
    if "comp_equity" in equity_curve:
        payload["comp_equity"] = [float(v) for v in equity_curve["comp_equity"]]
    return payload

def _build_report_html(context: RunContext, summary: dict, charts: dict) -> str:
    invested = float(summary.get('total_invested', 0.0))
    final_value = float(summary.get('final_value', 0.0))
    dividends = float(summary.get('total_dividends', 0.0))
    profit = final_value - invested
    profit_color = "#059669" if profit >= 0 else "#dc2626"
    curr = "¥" if summary.get("currency") == "RMB" else "$"
    
    # Pre-calculate Alpha to avoid formatting string errors
    comp = summary.get("comparison", {})
    alpha_val = float(comp.get("alpha", 0.0))
    alpha_color = "#6366f1" if alpha_val >= 0 else "#dc2626"

    # Attribution Math
    price_appreciation = final_value - dividends - invested
    price_pct = price_appreciation / invested if invested > 0 else 0
    div_yield_pct = dividends / invested if invested > 0 else 0
    payback_pct = dividends / invested if invested > 0 else 0

    # Build Tables
    asset_rows = ""
    for m in sorted(summary.get("symbol_metrics", []), key=lambda x: x.get('basis', 0.0), reverse=True):
        display_name = MANUAL_NAME_OVERRIDE.get(m['symbol'], m.get('name', ''))
        asset_rows += f"""
        <tr style="border-bottom: 1px solid #f1f5f9;">
          <td style="padding: 12px; font-weight: bold;">{m['symbol']}</td>
          <td style="padding: 12px; font-size: 0.9em; color: #64748b;">{display_name}</td>
          <td style="padding: 12px; text-align: right;">{curr}{m['basis']:,.2f}</td>
          <td style="padding: 12px; text-align: right;">{curr}{m['final_value']:,.2f}</td>
          <td style="padding: 12px; text-align: right; color: #6366f1; font-weight: bold;">{curr}{m['dividends']:,.2f}</td>
          <td style="padding: 12px; text-align: right;">{m['actual_weight']:.1%}</td>
        </tr>"""

    monthly_rows = ""
    for m in summary.get("monthly_metrics", []):
        monthly_rows += f"""
        <tr style="border-bottom: 1px solid #f1f5f9; text-align: right;">
          <td style="padding: 12px; text-align: left; font-weight: bold;">{m['month']}</td>
          <td style="padding: 12px;">{curr}{m['invested']:,.2f}</td>
          <td style="padding: 12px;">{curr}{m['basis']:,.2f}</td>
          <td style="padding: 12px;">{curr}{m['value']:,.2f}</td>
          <td style="padding: 12px; color: #6366f1;">{curr}{m.get('div_accum', 0):,.2f}</td>
          <td style="padding: 12px; font-weight: bold;">{m['roi_pct']:+.2%}</td>
        </tr>"""

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
    table {{ width: 100%; border-collapse: collapse; }}
    th {{ text-align: right; padding: 12px; background: #f8fafc; color: #64748b; font-size: 0.75em; text-transform: uppercase; }}
    th:first-child {{ text-align: left; }}
    .attr-bar {{ height: 12px; background: #e2e8f0; border-radius: 6px; overflow: hidden; margin-top: 4px; }}
  </style>
</head>
<body>
  <div class="container">
    <h1>Plan: {context.plan.name}</h1>
    <p class="subtitle">Data Source: {context.data_source} | Reinvest: {summary.get('reinvest')} | Date Range: {context.date_range}</p>

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
      <div class="card">
        <div class="card-label">DCA Alpha</div>
        <div class="card-value" style="color: {alpha_color}">{curr}{alpha_val:,.2f}</div>
      </div>
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

    <div style="display: grid; grid-template-columns: 2fr 1fr; gap: 24px; margin-bottom: 24px;">
      <!-- Attribution Card -->
      <div class="section-card">
        <div class="section-header">Return Attribution</div>
        <div style="display: flex; flex-direction: column; gap: 20px;">
          <div>
            <div style="display: flex; justify-content: space-between; font-size: 11px;">
              <span>Price Appreciation</span>
              <span style="font-weight: bold;">{_format_percentage(price_pct)}</span>
            </div>
            <div class="attr-bar"><div style="width: {max(0, min(100, price_pct*500))}%; height: 100%; background: #059669;"></div></div>
          </div>
          <div>
            <div style="display: flex; justify-content: space-between; font-size: 11px;">
              <span>Dividend Income</span>
              <span style="font-weight: bold; color: #6366f1;">{_format_percentage(div_yield_pct)}</span>
            </div>
            <div class="attr-bar"><div style="width: {max(0, min(100, div_yield_pct*500))}%; height: 100%; background: #6366f1;"></div></div>
          </div>
        </div>
      </div>

      <!-- Payback Card -->
      <div class="section-card" style="text-align: center;">
        <div class="section-header">Capital Payback</div>
        <div style="font-size: 2em; font-weight: bold; color: #6366f1; margin: 10px 0;">{payback_pct:.1%}</div>
        <p style="font-size: 11px; color: #64748b;">Of your original capital has been recovered via dividends.</p>
      </div>
    </div>

    <div class="section-card">
      <div class="section-header">Asset Performance Breakdown</div>
      <table>
        <thead>
          <tr>
            <th style="text-align: left;">Symbol</th>
            <th style="text-align: left;">Name</th>
            <th>Cost Basis</th>
            <th>Final Value</th>
            <th>Dividends</th>
            <th>Weight</th>
          </tr>
        </thead>
        <tbody>{asset_rows}</tbody>
      </table>
    </div>

    <div class="section-card">
      <div class="section-header">Value vs. Cost Basis</div>
      <canvas id="mainChart"></canvas>
    </div>

    <div class="section-card">
      <div class="section-header">Monthly History</div>
      <table>
        <thead>
          <tr>
            <th style="text-align: left;">Month</th>
            <th>Invested</th>
            <th>Total Basis</th>
            <th>Value</th>
            <th>Accum. Divs</th>
            <th>ROI</th>
          </tr>
        </thead>
        <tbody>{monthly_rows}</tbody>
      </table>
    </div>

    <script>
      const data = {json.dumps(charts)};
      new Chart(document.getElementById('mainChart'), {{
        type: 'line',
        data: {{
          labels: data.dates,
          datasets: [
            {{ label: 'Portfolio Value', data: data.equity, borderColor: '#2563eb', backgroundColor: 'rgba(37, 99, 235, 0.05)', fill: true, pointRadius: 0 }},
            {{ label: 'Cost Basis', data: data.basis, borderColor: '#94a3b8', borderDash: [5, 5], pointRadius: 0 }},
            {{ label: 'Lump Sum Benchmark', data: data.comp_equity, borderColor: '#f59e0b', borderDash: [2, 2], pointRadius: 0 }}
          ]
        }},
        options: {{ responsive: true, interaction: {{ mode: 'index', intersect: false }} }}
      }});
    </script>
  </div>
</body>
</html>"""
