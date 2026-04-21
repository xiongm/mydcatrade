from pathlib import Path
import json
from datetime import datetime

def update_global_index(root_dir: Path) -> None:
    history_records = []
    latest_results = []
    
    if not root_dir.exists():
        return

    for plan_dir in root_dir.iterdir():
        if not plan_dir.is_dir() or plan_dir.name == "mean_reversion_v1": continue
        for source_dir in plan_dir.iterdir():
            if not source_dir.is_dir(): continue
            
            # Collect history
            hist_dir = source_dir / "history"
            if hist_dir.exists():
                for h_file in hist_dir.glob("*.json"):
                    try:
                        data = json.loads(h_file.read_text())
                        bundle_summary_path = source_dir / "bundles" / data["bundle_fingerprint"] / "summary.json"
                        if bundle_summary_path.exists():
                            summary = json.loads(bundle_summary_path.read_text())
                            data["metrics"] = summary
                            data["source_full"] = source_dir.name
                            data["report_path"] = f"{plan_dir.name}/{source_dir.name}/bundles/{data['bundle_fingerprint']}/report.html"
                            history_records.append(data)
                    except Exception: continue

            # Collect latest
            latest_path = source_dir / "latest" / "latest.json"
            if latest_path.exists():
                try:
                    l_data = json.loads(latest_path.read_text())
                    bundle_summary_path = source_dir / "bundles" / l_data["bundle_fingerprint"] / "summary.json"
                    if bundle_summary_path.exists():
                        summary = json.loads(bundle_summary_path.read_text())
                        l_data["metrics"] = summary
                        l_data["source_full"] = source_dir.name
                        l_data["report_path"] = f"{plan_dir.name}/{source_dir.name}/latest/report.html"
                        latest_results.append(l_data)
                except Exception: continue

    recent_activity = sorted(history_records, key=lambda x: x["timestamp"], reverse=True)[:10]
    leaderboard = sorted(latest_results, key=lambda x: x["metrics"].get("total_return", 0), reverse=True)

    html = _generate_html(recent_activity, leaderboard)
    (root_dir / "index.html").write_text(html)

def _format_pct(val):
    return f"{val:.2%}" if isinstance(val, (int, float)) else "0.00%"

def _format_money(val):
    return f"${val:,.2f}" if isinstance(val, (int, float)) else "$0.00"

def _generate_html(recent, leaderboard):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    recent_rows = ""
    for i, r in enumerate(recent):
        bg = "background: #fffde7;" if i == 0 else ""
        recent_rows += f"""
        <tr style="border-bottom: 1px solid #eee; {bg}">
            <td style="padding: 10px;">{r['timestamp']}</td>
            <td style="padding: 10px;"><b>{r['plan']}</b></td>
            <td style="padding: 10px; font-size: 0.85em; color: #666;">{r['source_full']}</td>
            <td style="padding: 10px; color: {'#2e7d32' if r['metrics'].get('total_return', 0) >= 0 else '#c62828'}; font-weight: bold;">{_format_pct(r['metrics'].get('total_return', 0))}</td>
            <td style="padding: 10px;"><a href="{r['report_path']}" style="color: #1976d2; text-decoration: none; font-weight: bold;">View &rarr;</a></td>
        </tr>"""

    leaderboard_rows = ""
    for r in leaderboard:
        leaderboard_rows += f"""
        <tr style="border-bottom: 1px solid #eee;">
            <td style="padding: 10px;"><b>{r['plan']}</b></td>
            <td style="padding: 10px;"><span style="color: #666;">{r['source_full']}</span></td>
            <td style="padding: 10px;">{_format_money(r['metrics'].get('total_invested', 0))}</td>
            <td style="padding: 10px; color: {'#2e7d32' if r['metrics'].get('total_return', 0) >= 0 else '#c62828'}; font-weight: bold;">{_format_pct(r['metrics'].get('total_return', 0))}</td>
            <td style="padding: 10px;">{_format_pct(r['metrics'].get('cagr', 0))}</td>
            <td style="padding: 10px; color: #c62828;">{_format_pct(r['metrics'].get('max_drawdown', 0))}</td>
            <td style="padding: 10px;"><a href="{r['report_path']}" style="color: #1976d2; text-decoration: none;">Latest &rarr;</a></td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <title>DCA Global Results Portal</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; color: #333; background: #f4f7f6; }}
        .container {{ max-width: 1000px; margin: auto; background: white; padding: 30px; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }}
        h1 {{ color: #111; margin-bottom: 5px; }}
        .subtitle {{ color: #666; margin-bottom: 30px; font-size: 0.9em; }}
        h3 {{ margin-top: 0; color: #444; border-bottom: 2px solid #eee; padding-bottom: 10px; }}
        table {{ width: 100%; border-collapse: collapse; margin-bottom: 40px; }}
        th {{ text-align: left; padding: 12px; background: #fafafa; color: #666; font-size: 0.85em; text-transform: uppercase; border-bottom: 2px solid #eee; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>DCA Global Results Portal</h1>
        <p class="subtitle">Last Updated: {now}</p>
        
        <h3>Recent Activity</h3>
        <table>
            <thead><tr><th>Timestamp</th><th>Plan</th><th>Source</th><th>Return</th><th>Action</th></tr></thead>
            <tbody>{recent_rows}</tbody>
        </table>

        <h3>Performance Leaderboard</h3>
        <table>
            <thead><tr><th>Plan</th><th>Source</th><th>Invested</th><th>Return</th><th>CAGR</th><th>Max DD</th><th>Report</th></tr></thead>
            <tbody>{leaderboard_rows}</tbody>
        </table>
    </div>
</body>
</html>"""
