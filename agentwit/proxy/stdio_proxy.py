"""stdio transport proxy for MCP servers.

Intercepts JSON-RPC messages flowing over stdin/stdout between the AI agent
and an MCP server subprocess, logging every message to WitnessLogger.

Usage via CLI::

    agentwit proxy --stdio -- python mcp_server.py
"""
from __future__ import annotations

import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agentwit.witness.log import WitnessLogger


class StdioProxy:
    """Transparent stdio proxy that intercepts newline-delimited JSON-RPC messages.

    The proxy:
    1. Spawns the target command as a subprocess.
    2. Reads lines from our own stdin and forwards them to the subprocess stdin.
    3. Reads lines from the subprocess stdout and forwards them to our stdout.
    4. Logs both directions to WitnessLogger with risk scoring.
    5. Passes subprocess stderr through unchanged (inherited).

    Attributes:
        command: The command and arguments used to start the MCP server.
        witness_logger: Logger instance for recording events.
        actor: Actor identifier written into each log event.
    """

    def __init__(
        self,
        command: list[str],
        witness_logger: "WitnessLogger",
        actor: str = "stdio_proxy",
    ) -> None:
        self.command = command
        self.witness_logger = witness_logger
        self.actor = actor

    async def run(self, max_restarts: int = 3, restart_delay: float = 1.0) -> int:
        """Start subprocess and proxy stdin/stdout, restarting on crash.

        If the subprocess exits with a non-zero return code it is restarted
        up to *max_restarts* times, waiting *restart_delay* seconds between
        each attempt.  After all restarts are exhausted a ``process_crash``
        record is appended to ``audit.jsonl`` in the witness session directory.

        Returns:
            The final subprocess exit code.
        """
        for attempt in range(max_restarts + 1):  # initial run + up to max_restarts
            rc = await self._run_once()
            if rc == 0:
                return 0
            # Non-zero exit — decide whether to restart
            if attempt < max_restarts:
                await asyncio.sleep(restart_delay)
                continue
            # All restarts exhausted — write process_crash to audit.jsonl
            try:
                _audit = Path(self.witness_logger.session_path) / "audit.jsonl"
                _audit.parent.mkdir(parents=True, exist_ok=True)
                with _audit.open("a", encoding="utf-8") as fh:
                    fh.write(json.dumps({
                        "type": "process_crash",
                        "command": self.command,
                        "returncode": rc,
                        "restarts_attempted": max_restarts,
                        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    }) + "\n")
            except Exception:
                pass
            return rc
        return 0  # unreachable, satisfies type checkers

    async def _run_once(self) -> int:
        """Spawn the subprocess once and proxy until it exits.

        Returns:
            The subprocess exit code (0 if returncode is None).
        """
        process = await asyncio.create_subprocess_exec(
            *self.command,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=None,  # inherit: subprocess stderr passes through unchanged
        )

        try:
            await asyncio.gather(
                self._proxy_stdin(process),
                self._proxy_stdout(process),
            )
        except Exception:
            pass
        finally:
            try:
                await process.wait()
            except Exception:
                pass

        return process.returncode or 0

    async def _proxy_stdin(self, process: asyncio.subprocess.Process) -> None:
        """Read from our stdin, log, and forward to subprocess stdin."""
        loop = asyncio.get_event_loop()
        reader = asyncio.StreamReader()
        protocol = asyncio.StreamReaderProtocol(reader)
        await loop.connect_read_pipe(lambda: protocol, sys.stdin.buffer)

        try:
            while True:
                line = await reader.readline()
                if not line:
                    break
                # Forward first to minimise latency
                if process.stdin and not process.stdin.is_closing():
                    process.stdin.write(line)
                    try:
                        await process.stdin.drain()
                    except (BrokenPipeError, ConnectionResetError):
                        break
                await self._log_message(line, direction="request")
        except (asyncio.CancelledError, BrokenPipeError, ConnectionResetError):
            pass
        finally:
            if process.stdin and not process.stdin.is_closing():
                try:
                    process.stdin.close()
                except Exception:
                    pass

    async def _proxy_stdout(self, process: asyncio.subprocess.Process) -> None:
        """Read from subprocess stdout, log, and forward to our stdout."""
        try:
            while True:
                if process.stdout is None:
                    break
                line = await process.stdout.readline()
                if not line:
                    break
                # Forward to our stdout immediately
                sys.stdout.buffer.write(line)
                sys.stdout.buffer.flush()
                await self._log_message(line, direction="response")
        except (asyncio.CancelledError, BrokenPipeError, ConnectionResetError):
            pass

    async def _log_message(self, raw_line: bytes, direction: str) -> None:
        """Parse a newline-delimited JSON-RPC message and log it.

        Silently ignores non-JSON lines (e.g. empty lines, debug output).
        """
        line = raw_line.strip()
        if not line:
            return
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            return

        method: str = msg.get("method", "")
        tool: str = ""
        if isinstance(msg.get("params"), dict):
            params = msg["params"]
            tool = params.get("name", "") or params.get("tool", "")

        action = method if method else direction
        payload = {direction: msg}

        risk_indicators: list[dict] = []
        try:
            from agentwit.analyzer.scorer import RiskScorer

            scorer = RiskScorer()
            temp_event = {"action": action, "tool": tool, "full_payload": payload}
            risk_indicators = scorer.score_event(temp_event)
        except Exception:
            pass

        try:
            await self.witness_logger.alog_event(
                action=action,
                tool=tool,
                full_payload=payload,
                risk_indicators=risk_indicators,
            )
        except Exception:
            pass


async def run_stdio_proxy(
    command: list[str],
    witness_logger: "WitnessLogger",
    actor: str = "stdio_proxy",
) -> int:
    """Convenience coroutine to run the stdio proxy and return the exit code."""
    proxy = StdioProxy(command=command, witness_logger=witness_logger, actor=actor)
    return await proxy.run()
