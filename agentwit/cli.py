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

@main.command(context_settings={"allow_extra_args": True, "ignore_unknown_options": True})
@click.option("--target", default=None, help="Target MCP server URL (HTTP mode)")
@click.option("--port", default=8765, show_default=True, help="Port to listen on (HTTP mode)")
@click.option("--host", default="127.0.0.1", show_default=True, help="Host to bind (HTTP mode)")
@click.option("--log-dir", default="./witness_logs", show_default=True, help="Directory for witness logs")
@click.option("--actor", default="agent", show_default=True, help="Actor identifier")
@click.option("--stdio", is_flag=True, default=False, help="stdio proxy mode: intercept subprocess stdin/stdout")
@click.option("--webhook", default=None, help="Webhook URL for risk notifications")
@click.option("--webhook-on", default="HIGH,CRITICAL", show_default=True, help="Comma-separated severity levels that trigger webhook")
@click.option("--timeout", default=30, show_default=True, type=float, help="HTTP request timeout in seconds")
@click.argument("cmd", nargs=-1, type=click.UNPROCESSED)
def proxy(
    target: str | None,
    port: int,
    host: str,
    log_dir: str,
    actor: str,
    stdio: bool,
    webhook: str | None,
    webhook_on: str,
    timeout: float,
    cmd: tuple,
) -> None:
    """Start the transparent proxy server (HTTP or stdio mode).

    HTTP mode forwards requests to TARGET and records them:

        agentwit proxy --target http://localhost:3000 --port 8765

    stdio mode wraps a subprocess MCP server:

        agentwit proxy --stdio -- python mcp_server.py
    """
    import asyncio

    from .witness.log import WitnessLogger
    from .config import load_config

    cfg = load_config()

    if stdio:
        if not cmd:
            click.echo("Error: --stdio requires a command after --", err=True)
            sys.exit(1)

        click.echo(f"Starting agentwit stdio proxy")
        click.echo(f"Command: {list(cmd)}")
        click.echo(f"Witness logs → {log_dir}", err=True)

        logger = WitnessLogger(session_dir=log_dir, actor=actor)
        click.echo(f"Session: {logger.session_path}", err=True)

        from .proxy.stdio_proxy import run_stdio_proxy

        exit_code = asyncio.run(
            run_stdio_proxy(list(cmd), logger, actor=actor, config=cfg)
        )
        logger.close()
        sys.exit(exit_code)

    # HTTP mode — CLI --target wins, else config's proxy.target.
    target = target or cfg.get("proxy", {}).get("target")
    if not target:
        click.echo("Error: --target is required in HTTP proxy mode", err=True)
        sys.exit(1)

    import uvicorn

    from .proxy.http_proxy import create_proxy_app

    click.echo(f"Starting agentwit proxy → {target}")
    click.echo(f"Listening on {host}:{port}")
    click.echo(f"Witness logs → {log_dir}")

    logger = WitnessLogger(session_dir=log_dir, actor=actor)
    click.echo(f"Session: {logger.session_path}")

    app = create_proxy_app(
        target_url=target,
        witness_logger=logger,
        actor=actor,
        webhook_url=webhook,
        webhook_on=webhook_on,
        timeout=timeout,
        config=cfg,
    )

    try:
        uvicorn.run(app, host=host, port=port)
    finally:
        logger.close()


# ---------------------------------------------------------------------------
# verify
# ---------------------------------------------------------------------------

@main.command()
@click.option(
    "--session",
    required=True,
    type=click.Path(exists=True),
    help="Session directory containing witness.jsonl",
)
def verify(session: str) -> None:
    """Verify SHA-256 chain integrity and ed25519 signatures for a session.

    Example:

        agentwit verify --session ./witness_logs/session_20240101_120000
    """
    from .witness.chain import ChainManager
    from .security.signing import EventSigner

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

    if not events:
        click.echo("No events found.")
        return

    chain = ChainManager(session_id=session_path.name)
    chain_results = chain.verify_chain(events)

    signer = EventSigner()

    click.echo(f"Session: {session_path.name}  ({len(events)} events)")
    click.echo(f"Key fingerprint: {signer.fingerprint()}")
    click.echo("")
    click.echo(f"{'#':>4}  chain   sig     witness_id")
    click.echo("-" * 72)

    all_valid = True
    for idx, (event, cr) in enumerate(zip(events, chain_results)):
        chain_ok = cr["valid"]

        sig = event.get("signature", "")
        event_without_sig = {k: v for k, v in event.items()
                             if k not in ("signature", "signed_by")}
        sig_ok = signer.verify(event_without_sig, sig) if sig else False

        if not chain_ok or not sig_ok:
            all_valid = False

        chain_str = click.style("OK  ", fg="green") if chain_ok else click.style("FAIL", fg="red", bold=True)
        sig_str = click.style("OK  ", fg="green") if sig_ok else click.style("FAIL", fg="red", bold=True)
        witness_id = event.get("witness_id", "?")
        click.echo(f"{idx:>4}  {chain_str}  {sig_str}  {witness_id}")

    click.echo("")
    if all_valid:
        click.echo(click.style("Result: ALL VALID", fg="green", bold=True))
    else:
        click.echo(click.style("Result: INTEGRITY ERROR DETECTED", fg="red", bold=True))
        sys.exit(1)


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

@main.command("gui")
@click.argument("extra_args", nargs=-1, type=click.UNPROCESSED)
def gui_command(extra_args):
    """MCP Inspector GUI を起動する。"""
    import sys
    from agentwit.gui_launcher import main as _gui_main
    sys.exit(_gui_main(list(extra_args)))


# ---------------------------------------------------------------------------
# init / config
# ---------------------------------------------------------------------------

@main.command()
def init() -> None:
    """Create ~/.agentwit/ with a default config and an empty secrets.env.

    Idempotent — existing files are kept. No secrets are written; add them
    to secrets.env yourself and reference them from config.yaml as
    ${env:NAME}.
    """
    from .config import init_home

    for key, val in init_home().items():
        click.echo(f"  {key:8s} {val}")
    click.echo("")
    click.echo("Next: put credentials in ~/.agentwit/secrets.env (chmod 600),")
    click.echo("then 'agentwit config set ...' to wire them up.")


@main.group()
def config() -> None:
    """View, change and validate configuration."""


@config.command("get")
@click.argument("key", required=False)
def config_get(key: str | None) -> None:
    """Show the whole config, or one dotted KEY (e.g. proxy.port).

    Secret references are shown as-is (${env:...}); secrets are never
    expanded to the terminal.
    """
    import yaml

    from .config import load_config

    cfg = load_config(resolve_secrets=False)
    if not key:
        click.echo(yaml.safe_dump(cfg, sort_keys=False, allow_unicode=True).rstrip())
        return
    cur: object = cfg
    for part in key.split("."):
        if not isinstance(cur, dict) or part not in cur:
            click.echo(f"No such key: {key}", err=True)
            sys.exit(1)
        cur = cur[part]
    if isinstance(cur, (dict, list)):
        click.echo(yaml.safe_dump(cur, sort_keys=False, allow_unicode=True).rstrip())
    else:
        click.echo(str(cur))


@config.command("set")
@click.argument("key")
@click.argument("value")
def config_set(key: str, value: str) -> None:
    """Set a dotted KEY to VALUE (YAML-typed), if it keeps the config valid.

    Examples:

        agentwit config set proxy.port 9000
        agentwit config set monitor.rules.data_exfil false
        agentwit config set proxy.target http://localhost:3000
    """
    import yaml

    from .config import load_config, save_config, validate_config

    cfg = load_config(resolve_secrets=False)
    parsed = yaml.safe_load(value)

    parts = key.split(".")
    cur = cfg
    for p in parts[:-1]:
        nxt = cur.get(p)
        if not isinstance(nxt, dict):
            nxt = {}
            cur[p] = nxt
        cur = nxt
    cur[parts[-1]] = parsed

    errors, warnings = validate_config(cfg)
    if errors:
        click.echo("Rejected — that change would make the config invalid:", err=True)
        for e in errors:
            click.echo(f"  - {e}", err=True)
        sys.exit(1)
    for w in warnings:
        click.echo(click.style(f"warning: {w}", fg="yellow"))
    save_config(cfg)
    click.echo(f"set {key} = {parsed!r}")


@config.command("validate")
def config_validate() -> None:
    """Validate the on-disk config.yaml and report errors/warnings."""
    import yaml

    from .config import config_home, validate_config

    path = config_home() / "config.yaml"
    if not path.exists():
        click.echo("No config.yaml — run 'agentwit init' first.", err=True)
        sys.exit(1)
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    errors, warnings = validate_config(raw)
    for w in warnings:
        click.echo(click.style(f"warning: {w}", fg="yellow"))
    for e in errors:
        click.echo(click.style(f"error:   {e}", fg="red"))
    if errors:
        sys.exit(1)
    click.echo(click.style("config.yaml is valid", fg="green", bold=True))


# ---------------------------------------------------------------------------
# daemon
# ---------------------------------------------------------------------------

@main.command()
@click.option("--target", default=None, help="Upstream MCP URL (overrides config)")
@click.option("--host", default=None, help="Bind host (overrides config proxy.host)")
@click.option("--port", default=None, type=int, help="Bind port (overrides config)")
@click.option("--log-dir", default=None, help="Witness log dir (default ~/.agentwit/witness_logs)")
@click.option("--actor", default="daemon", show_default=True, help="Actor identifier")
@click.option("--webhook", default=None, help="Single webhook URL (hub routes in config also fire)")
@click.option("--webhook-on", default="HIGH,CRITICAL", show_default=True)
@click.option("--pidfile", default=None, help="Write the PID here while running")
def daemon(
    target: str | None,
    host: str | None,
    port: int | None,
    log_dir: str | None,
    actor: str,
    webhook: str | None,
    webhook_on: str,
    pidfile: str | None,
) -> None:
    """Run agentwit as a long-lived service (single process, SIGHUP reload).

    Settings come from ~/.agentwit/config.yaml; CLI flags override. Edit the
    config and send SIGHUP (``systemctl --user reload`` or ``kill -HUP``) to
    apply monitor/notify changes without dropping the listening socket.
    """
    import asyncio
    import os
    import signal

    import uvicorn

    from .witness.log import WitnessLogger
    from .config import load_config, config_home

    cfg = load_config()
    proxy_cfg = cfg.get("proxy", {})
    target = target or proxy_cfg.get("target")
    if not target:
        click.echo("Error: no target (set proxy.target or pass --target)", err=True)
        sys.exit(1)
    host = host or proxy_cfg.get("host", "127.0.0.1")
    port = port or int(proxy_cfg.get("port", 8765))
    timeout = float(proxy_cfg.get("timeout", 30.0))
    log_dir = log_dir or str(config_home() / "witness_logs")

    if host in ("0.0.0.0", "::"):
        click.echo(click.style(
            f"warning: binding {host} exposes the proxy off-box; "
            "127.0.0.1 is safer", fg="yellow"), err=True)

    witness = WitnessLogger(session_dir=log_dir, actor=actor)

    from .proxy.http_proxy import create_proxy_app
    app = create_proxy_app(
        target_url=target, witness_logger=witness, actor=actor,
        webhook_url=webhook, webhook_on=webhook_on, timeout=timeout, config=cfg,
    )

    uconfig = uvicorn.Config(app, host=host, port=port, log_level="info")
    server = uvicorn.Server(uconfig)
    # We own the signals (see _serve) so cleanup is deterministic; stop uvicorn
    # from installing — and later restoring — its own SIGTERM/SIGINT handlers.
    server.install_signal_handlers = lambda: None

    click.echo(f"agentwit daemon → {target}  (listening {host}:{port})")
    click.echo(f"witness logs → {log_dir}")
    click.echo("SIGHUP reloads config; SIGTERM/SIGINT stops gracefully.")

    if pidfile:
        try:
            Path(pidfile).write_text(str(os.getpid()), encoding="utf-8")
        except OSError as exc:
            click.echo(f"warning: could not write pidfile: {exc}", err=True)

    async def _serve() -> None:
        loop = asyncio.get_running_loop()

        def _reload() -> None:
            try:
                app.state.monitor.reload(load_config())
                click.echo(f"[agentwit] SIGHUP: reloaded {app.state.monitor.summary()}")
            except Exception as exc:
                click.echo(f"[agentwit] SIGHUP reload failed, keeping current "
                           f"config: {exc}", err=True)

        def _stop() -> None:
            # graceful: tell uvicorn to finish, then serve() returns and the
            # outer finally runs (pidfile removal, witness close).
            server.should_exit = True

        for _sig in ("SIGINT", "SIGTERM"):
            if hasattr(signal, _sig):
                try:
                    loop.add_signal_handler(getattr(signal, _sig), _stop)
                except (NotImplementedError, RuntimeError):
                    pass
        if hasattr(signal, "SIGHUP"):
            try:
                loop.add_signal_handler(signal.SIGHUP, _reload)
            except (NotImplementedError, RuntimeError):
                pass  # not supported on this platform
        await server.serve()

    try:
        asyncio.run(_serve())
    except KeyboardInterrupt:  # SIGINT — exit quietly, not with a traceback
        pass
    finally:
        witness.close()
        if pidfile:
            try:
                Path(pidfile).unlink()
            except OSError:
                pass
        click.echo("agentwit daemon stopped.")


# ---------------------------------------------------------------------------
# ui
# ---------------------------------------------------------------------------

@main.command()
@click.option("--port", default=8799, show_default=True, help="Port for the local console")
@click.option("--no-browser", is_flag=True, default=False, help="Don't open a browser")
def ui(port: int, no_browser: bool) -> None:
    """Open the local settings console (loopback only).

    Serves a small page on 127.0.0.1 for viewing and changing config, adding
    notification destinations, and reviewing recent detections. It binds
    loopback only; reach it from another machine over an SSH tunnel
    (``ssh -L <port>:127.0.0.1:<port> your-server``), never by exposing it.
    """
    import webbrowser

    from .ui.server import serve

    httpd, _token = serve(host="127.0.0.1", port=port)
    url = f"http://127.0.0.1:{port}/"
    click.echo(f"agentwit console → {url}")
    click.echo("Loopback only. Press Ctrl+C to stop.")
    if not no_browser:
        try:
            webbrowser.open(url)
        except Exception:
            pass
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
        click.echo("console stopped.")


if __name__ == "__main__":  # python -m agentwit.cli
    main()
