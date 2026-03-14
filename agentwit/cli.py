"""Command-line interface for agentwit.

Provides commands for starting the proxy, generating reports, replaying
sessions, and diffing two sessions.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import click


@click.group()
@click.version_option(package_name="agentwit")
def main() -> None:
    """agentwit - Transparent proxy witness for AI agent <-> MCP server communications."""


# ---------------------------------------------------------------------------
# proxy
# ---------------------------------------------------------------------------

@main.command()
@click.option("--target", required=True, help="Target MCP server URL")
@click.option("--port", default=8765, show_default=True, help="Port to listen on")
@click.option("--host", default="127.0.0.1", show_default=True, help="Host to bind")
@click.option("--log-dir", default="./witness_logs", show_default=True, help="Directory for witness logs")
@click.option("--actor", default="agent", show_default=True, help="Actor identifier")
def proxy(target: str, port: int, host: str, log_dir: str, actor: str) -> None:
    """Start the transparent HTTP proxy server.

    All requests forwarded to TARGET are recorded in LOG_DIR.  Each session
    gets its own timestamped sub-directory containing a ``witness.jsonl`` file.

    Example:

        agentwit proxy --target http://localhost:3000 --port 8765
    """
    import uvicorn

    from .witness.log import WitnessLogger
    from .proxy.http_proxy import create_proxy_app

    click.echo(f"Starting agentwit proxy → {target}")
    click.echo(f"Listening on {host}:{port}")
    click.echo(f"Witness logs → {log_dir}")

    logger = WitnessLogger(session_dir=log_dir, actor=actor)
    click.echo(f"Session: {logger.session_path}")

    app = create_proxy_app(target_url=target, witness_logger=logger, actor=actor)

    try:
        uvicorn.run(app, host=host, port=port)
    finally:
        logger.close()


# ---------------------------------------------------------------------------
# report
# ---------------------------------------------------------------------------

@main.command()
@click.option(
    "--session",
    required=True,
    type=click.Path(exists=True),
    help="Session directory containing witness.jsonl",
)
@click.option(
    "--format",
    "fmt",
    default="json",
    show_default=True,
    type=click.Choice(["json", "markdown", "html"]),
    help="Output format",
)
@click.option(
    "--output",
    default="-",
    show_default=True,
    help="Output file path (use - for stdout)",
)
def report(session: str, fmt: str, output: str) -> None:
    """Generate an audit report from a witness log session.

    Example:

        agentwit report --session ./witness_logs/session_20240101_120000 --format html --output ./report.html
    """
    session_path = Path(session)

    if fmt == "json":
        from .reporter.json_reporter import JsonReporter
        reporter = JsonReporter(session_path)
        content = reporter.render()
    elif fmt == "markdown":
        from .reporter.markdown_reporter import MarkdownReporter
        reporter = MarkdownReporter(session_path)
        try:
            content = reporter.render()
        except NotImplementedError:
            click.echo("Markdown reporter is not yet implemented.", err=True)
            sys.exit(1)
    elif fmt == "html":
        from .reporter.html_reporter import HtmlReporter
        reporter = HtmlReporter(session_path)
        try:
            content = reporter.render()
        except NotImplementedError:
            click.echo("HTML reporter is not yet implemented.", err=True)
            sys.exit(1)
    else:
        click.echo(f"Unknown format: {fmt}", err=True)
        sys.exit(1)

    if output == "-":
        click.echo(content)
    else:
        Path(output).write_text(content, encoding="utf-8")
        click.echo(f"Report written to {output}")


# ---------------------------------------------------------------------------
# replay
# ---------------------------------------------------------------------------

@main.command()
@click.option(
    "--session",
    required=True,
    type=click.Path(exists=True),
    help="Session directory to replay",
)
@click.option(
    "--verify/--no-verify",
    default=True,
    show_default=True,
    help="Verify chain integrity before replaying",
)
def replay(session: str, verify: bool) -> None:
    """Replay and display events from a witness log session.

    When --verify is set (the default) the chain integrity is checked first
    and any broken links are highlighted.

    Example:

        agentwit replay --session ./witness_logs/session_20240101_120000
    """
    from .witness.chain import ChainManager

    session_path = Path(session)
    log_path = session_path / "witness.jsonl"

    if not log_path.exists():
        click.echo(f"No witness.jsonl found in {session_path}", err=True)
        sys.exit(1)

    events: list[dict] = []
    with log_path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                events.append(json.loads(line))

    click.echo(f"Session: {session_path.name}  ({len(events)} events)")

    if verify and events:
        chain = ChainManager(session_id=session_path.name)
        results = chain.verify_chain(events)
        all_valid = all(r["valid"] for r in results)
        status = click.style("VALID", fg="green") if all_valid else click.style("TAMPERED", fg="red", bold=True)
        click.echo(f"Chain integrity: {status}")
        if not all_valid:
            for r in results:
                if not r["valid"]:
                    click.echo(
                        f"  [event {r['index']}] {click.style('FAIL', fg='red')} - {r['reason']}",
                        err=True,
                    )

    click.echo("")
    for idx, event in enumerate(events):
        ts = event.get("timestamp", "?")
        actor = event.get("actor", "?")
        action = event.get("action", "?")
        tool = event.get("tool") or "-"
        indicators = event.get("risk_indicators") or []
        risk_tag = ""
        if indicators:
            severities = [i.get("severity", "low") for i in indicators]
            worst = "high" if "high" in severities else ("medium" if "medium" in severities else "low")
            color = {"high": "red", "medium": "yellow", "low": "cyan"}.get(worst, "white")
            risk_tag = "  " + click.style(f"[{worst.upper()} RISK]", fg=color, bold=True)
        click.echo(f"  [{idx:03d}] {ts}  {actor}  {action}  tool={tool}{risk_tag}")


# ---------------------------------------------------------------------------
# diff
# ---------------------------------------------------------------------------

@main.command()
@click.option(
    "--session-a",
    required=True,
    type=click.Path(exists=True),
    help="First session directory",
)
@click.option(
    "--session-b",
    required=True,
    type=click.Path(exists=True),
    help="Second session directory",
)
def diff(session_a: str, session_b: str) -> None:
    """Diff two witness log sessions.

    Compares the tools called and risk indicators between two sessions,
    highlighting differences.

    Example:

        agentwit diff --session-a ./session_001 --session-b ./session_002
    """
    def _load(path: Path) -> list[dict]:
        log = path / "witness.jsonl"
        if not log.exists():
            click.echo(f"No witness.jsonl in {path}", err=True)
            sys.exit(1)
        events: list[dict] = []
        with log.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    events.append(json.loads(line))
        return events

    path_a = Path(session_a)
    path_b = Path(session_b)
    events_a = _load(path_a)
    events_b = _load(path_b)

    def _summarise(events: list[dict]) -> dict:
        tools: dict[str, int] = {}
        total_risk = 0
        high_risk = 0
        for e in events:
            t = e.get("tool")
            if t:
                tools[t] = tools.get(t, 0) + 1
            indicators = e.get("risk_indicators") or []
            total_risk += len(indicators)
            if any(i.get("severity") == "high" for i in indicators):
                high_risk += 1
        return {"tools": tools, "total_risk": total_risk, "high_risk_events": high_risk}

    summary_a = _summarise(events_a)
    summary_b = _summarise(events_b)

    click.echo(f"Session A: {path_a.name}  ({len(events_a)} events)")
    click.echo(f"Session B: {path_b.name}  ({len(events_b)} events)")
    click.echo("")

    # Tools diff
    all_tools = sorted(set(list(summary_a["tools"]) + list(summary_b["tools"])))
    click.echo("Tools called:")
    for tool in all_tools:
        cnt_a = summary_a["tools"].get(tool, 0)
        cnt_b = summary_b["tools"].get(tool, 0)
        indicator = "  " if cnt_a == cnt_b else click.style("!=", fg="yellow")
        click.echo(f"  {tool:40s}  A={cnt_a}  B={cnt_b}  {indicator}")

    click.echo("")
    click.echo("Risk summary:")

    def _risk_str(s: dict) -> str:
        return f"total={s['total_risk']}  high_risk_events={s['high_risk_events']}"

    click.echo(f"  A: {_risk_str(summary_a)}")
    click.echo(f"  B: {_risk_str(summary_b)}")

    if summary_a["total_risk"] != summary_b["total_risk"]:
        click.echo(click.style("  Risk profiles differ between sessions.", fg="yellow"))
    else:
        click.echo(click.style("  Risk profiles are identical.", fg="green"))
