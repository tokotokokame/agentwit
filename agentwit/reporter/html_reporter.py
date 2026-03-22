"""HTML report generator for witness log sessions.

Generates a self-contained HTML report with inline CSS (dark theme).
No external dependencies — standard library only.
"""
from __future__ import annotations

import html
import json
from datetime import datetime
from pathlib import Path

import agentwit
from agentwit.witness.chain import ChainManager
from agentwit.analyzer.owasp_mapper import OWASPMapper, OWASP_DESCRIPTIONS

_CSS = """
:root {
  --bg: #0d1117;
  --surface: #161b22;
  --border: #30363d;
  --text: #c9d1d9;
  --muted: #8b949e;
  --accent: #58a6ff;
  --green: #3fb950;
  --red: #f85149;
  --yellow: #d29922;
  --orange: #e3b341;
  --critical-bg: #3d1a1a;
  --high-bg: #2d1f00;
  --medium-bg: #1f1f00;
}
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
body {
  background: var(--bg);
  color: var(--text);
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, monospace;
  font-size: 14px;
  line-height: 1.6;
  padding: 24px;
}
h1 { font-size: 1.6rem; color: var(--accent); margin-bottom: 4px; }
h2 { font-size: 1.1rem; color: var(--text); margin: 24px 0 10px; border-bottom: 1px solid var(--border); padding-bottom: 6px; }
.subtitle { color: var(--muted); font-size: 0.85rem; margin-bottom: 20px; }
.card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 16px;
  margin-bottom: 16px;
}
.meta-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 12px;
}
.meta-item { display: flex; flex-direction: column; gap: 2px; }
.meta-label { font-size: 0.75rem; color: var(--muted); text-transform: uppercase; letter-spacing: 0.05em; }
.meta-value { font-size: 0.95rem; color: var(--text); font-weight: 500; }
.badge {
  display: inline-block;
  padding: 3px 10px;
  border-radius: 20px;
  font-size: 0.8rem;
  font-weight: 700;
  letter-spacing: 0.04em;
}
.badge-valid   { background: #0d2818; color: var(--green); border: 1px solid var(--green); }
.badge-tampered{ background: #3d1a1a; color: var(--red);   border: 1px solid var(--red); }
.risk-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 10px;
}
.risk-cell {
  border-radius: 6px;
  padding: 12px;
  text-align: center;
  border: 1px solid var(--border);
}
.risk-cell .count { font-size: 2rem; font-weight: 700; }
.risk-cell .label { font-size: 0.75rem; color: var(--muted); text-transform: uppercase; }
.risk-critical { background: #2a0a0a; color: var(--red); }
.risk-high     { background: #1f1000; color: var(--orange); }
.risk-medium   { background: #1a1600; color: var(--yellow); }
.risk-low      { background: #0e1a0e; color: var(--green); }
table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.85rem;
}
thead th {
  background: var(--surface);
  color: var(--muted);
  text-align: left;
  padding: 8px 12px;
  border-bottom: 2px solid var(--border);
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}
tbody tr { border-bottom: 1px solid var(--border); }
tbody tr:hover { background: #1c2128; }
tbody td { padding: 8px 12px; vertical-align: top; }
.row-critical { background: var(--critical-bg) !important; }
.row-high     { background: var(--high-bg) !important; }
.row-medium   { background: var(--medium-bg) !important; }
.ts { color: var(--muted); font-size: 0.78rem; white-space: nowrap; }
.tool { font-family: monospace; color: var(--accent); }
.action { color: var(--text); }
.risk-badge {
  display: inline-block;
  padding: 1px 6px;
  border-radius: 4px;
  font-size: 0.72rem;
  font-weight: 700;
  margin: 1px 2px;
}
.sev-critical { background: #5c1f1f; color: #ff6b6b; }
.sev-high     { background: #3d2800; color: #ffa657; }
.sev-medium   { background: #3d3300; color: #e3b341; }
.sev-low      { background: #1a2e1a; color: #7ee787; }
.witness-id { font-family: monospace; font-size: 0.7rem; color: var(--muted); }
.owasp-badge {
  display: inline-block;
  padding: 1px 7px;
  border-radius: 4px;
  font-size: 0.72rem;
  font-weight: 700;
  margin: 1px 2px;
  background: #1a2640;
  color: #58a6ff;
  border: 1px solid #264a80;
  font-family: monospace;
}
.owasp-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 10px;
}
.owasp-cell {
  background: var(--surface);
  border: 1px solid #264a80;
  border-radius: 6px;
  padding: 12px;
}
.owasp-cell .owasp-id   { font-family: monospace; font-size: 1.1rem; font-weight: 700; color: #58a6ff; }
.owasp-cell .owasp-name { font-size: 0.78rem; color: var(--muted); margin: 2px 0 6px; }
.owasp-cell .owasp-count { font-size: 1.6rem; font-weight: 700; color: var(--text); }
footer {
  margin-top: 32px;
  padding-top: 12px;
  border-top: 1px solid var(--border);
  color: var(--muted);
  font-size: 0.8rem;
  text-align: center;
}
"""


class HtmlReporter:
    """Generate a self-contained HTML audit report from a witness log session."""

    def __init__(self, session_dir: Path) -> None:
        self.session_dir = Path(session_dir)

    def load_events(self) -> list[dict]:
        """Read all events from ``witness.jsonl``."""
        jsonl = self.session_dir / "witness.jsonl"
        events: list[dict] = []
        with open(jsonl, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    events.append(json.loads(line))
        return events

    def generate(self) -> str:
        """Build and return the HTML report string."""
        events = self.load_events()
        session_id = self.session_dir.name
        generated_at = datetime.utcnow().isoformat(timespec="seconds") + "Z"
        actor = events[0].get("actor", "unknown") if events else "unknown"
        total_events = len(events)

        # Chain verification
        chain = ChainManager(session_id=session_id)
        if events:
            results = chain.verify_chain(events)
            chain_valid = all(r["valid"] for r in results)
        else:
            chain_valid = True

        # Risk counts (per event, by worst severity in that event)
        from agentwit.analyzer.scorer import RiskScorer

        scorer = RiskScorer()
        risk_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        event_risk_levels: list[str] = []

        for event in events:
            indicators = event.get("risk_indicators") or scorer.score_event(event)
            worst = _worst_for_indicators(indicators)
            event_risk_levels.append(worst)
            if worst in risk_counts:
                risk_counts[worst] += 1

        # OWASP enrichment
        mapper = OWASPMapper()
        enriched_events = mapper.map_events(events)
        owasp_counts = mapper.summary(enriched_events)

        # Build HTML sections
        badge_cls = "badge-valid" if chain_valid else "badge-tampered"
        badge_text = "VALID" if chain_valid else "TAMPERED"

        meta_html = _meta_grid(session_id, generated_at, actor, total_events)
        risk_html = _risk_summary(risk_counts)
        timeline_html = _event_timeline(enriched_events, event_risk_levels)
        chain_html = _chain_section(chain_valid)
        owasp_html = _owasp_summary(owasp_counts)

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Witness Report: {html.escape(session_id)}</title>
  <style>{_CSS}</style>
</head>
<body>
  <h1>Witness Report</h1>
  <p class="subtitle">Generated by agentwit v{html.escape(agentwit.__version__)}</p>

  <div class="card">
    <h2>Session Info</h2>
    {meta_html}
    <div style="margin-top:14px;">
      Chain Integrity:&nbsp;
      <span class="badge {badge_cls}">{badge_text}</span>
    </div>
  </div>

  <div class="card">
    <h2>Risk Summary</h2>
    {risk_html}
  </div>

  <div class="card">
    <h2>Event Timeline</h2>
    {timeline_html}
  </div>

  <div class="card">
    <h2>OWASP LLM Top 10 Summary</h2>
    {owasp_html}
  </div>

  <div class="card">
    <h2>Chain Verification</h2>
    {chain_html}
  </div>

  <footer>
    agentwit v{html.escape(agentwit.__version__)} &mdash; Generated {html.escape(generated_at)}
  </footer>
</body>
</html>"""

    def render(self) -> str:
        return self.generate()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _worst_for_indicators(indicators: list[dict]) -> str:
    order = {"low": 0, "medium": 1, "high": 2, "critical": 3}
    worst = ""
    for ri in indicators:
        sev = ri.get("severity", "low")
        if order.get(sev, 0) > order.get(worst, -1):
            worst = sev
    return worst or ""


def _meta_grid(session_id: str, generated_at: str, actor: str, total: int) -> str:
    items = [
        ("Session ID", session_id),
        ("Generated At", generated_at),
        ("Actor", actor),
        ("Total Events", str(total)),
    ]
    cells = "".join(
        f'<div class="meta-item">'
        f'<span class="meta-label">{html.escape(k)}</span>'
        f'<span class="meta-value">{html.escape(v)}</span>'
        f"</div>"
        for k, v in items
    )
    return f'<div class="meta-grid">{cells}</div>'


def _risk_summary(counts: dict) -> str:
    cells = ""
    for sev, label in [("critical", "Critical"), ("high", "High"), ("medium", "Medium"), ("low", "Low")]:
        cells += (
            f'<div class="risk-cell risk-{sev}">'
            f'<div class="count">{counts.get(sev, 0)}</div>'
            f'<div class="label">{label}</div>'
            f"</div>"
        )
    return f'<div class="risk-grid">{cells}</div>'


def _event_timeline(events: list[dict], risk_levels: list[str]) -> str:
    if not events:
        return "<p style='color:var(--muted)'>No events recorded.</p>"

    rows = ""
    for i, (event, level) in enumerate(zip(events, risk_levels)):
        row_cls = f" row-{level}" if level in ("critical", "high", "medium") else ""
        ts = html.escape(event.get("timestamp", ""))
        action = html.escape(event.get("action", ""))
        tool = html.escape(event.get("tool", "") or "-")
        wid = html.escape((event.get("witness_id", "") or "")[:16])
        indicators = event.get("risk_indicators") or []
        badges = ""
        owasp_badges = ""
        for ri in indicators:
            sev = ri.get("severity", "low")
            pat = html.escape(ri.get("pattern", ""))
            badges += f'<span class="risk-badge sev-{sev}">{pat}</span>'
            owasp_cat = ri.get("owasp_category")
            if owasp_cat:
                owasp_badges += f'<span class="owasp-badge">{html.escape(owasp_cat)}</span>'
        if not badges:
            badges = '<span style="color:var(--muted)">—</span>'
        if not owasp_badges:
            owasp_badges = '<span style="color:var(--muted)">—</span>'

        rows += (
            f'<tr class="{row_cls}">'
            f'<td class="ts">{ts}</td>'
            f'<td class="action">{action}</td>'
            f'<td class="tool">{tool}</td>'
            f'<td>{badges}</td>'
            f'<td>{owasp_badges}</td>'
            f'<td class="witness-id">{wid}…</td>'
            f"</tr>"
        )

    return (
        "<table>"
        "<thead><tr>"
        "<th>Timestamp</th><th>Action</th><th>Tool</th>"
        "<th>Risk Indicators</th><th>OWASP</th><th>Witness ID</th>"
        "</tr></thead>"
        f"<tbody>{rows}</tbody>"
        "</table>"
    )


def _owasp_summary(counts: dict[str, int]) -> str:
    if not counts:
        return "<p style='color:var(--muted)'>No OWASP-mapped risk indicators detected.</p>"
    cells = ""
    for owasp_id, name in OWASP_DESCRIPTIONS.items():
        count = counts.get(owasp_id, 0)
        if count == 0:
            continue
        cells += (
            f'<div class="owasp-cell">'
            f'<div class="owasp-id">{html.escape(owasp_id)}</div>'
            f'<div class="owasp-name">{html.escape(name)}</div>'
            f'<div class="owasp-count">{count}</div>'
            f"</div>"
        )
    if not cells:
        return "<p style='color:var(--muted)'>No OWASP-mapped risk indicators detected.</p>"
    return f'<div class="owasp-grid">{cells}</div>'


def _chain_section(chain_valid: bool) -> str:
    if chain_valid:
        return (
            '<p><span class="badge badge-valid">VALID</span>'
            '&nbsp;All event hashes verified — log has not been tampered with.</p>'
        )
    return (
        '<p><span class="badge badge-tampered">TAMPERED</span>'
        '&nbsp;<strong style="color:var(--red)">Chain integrity check FAILED.</strong>'
        " One or more events have been modified after recording.</p>"
    )
