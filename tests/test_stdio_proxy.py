"""Tests for proxy/stdio_proxy.py"""
from __future__ import annotations

import asyncio
import json
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agentwit.proxy.stdio_proxy import StdioProxy, run_stdio_proxy


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_logger():
    logger = MagicMock()
    logger.alog_event = AsyncMock()
    return logger


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestStdioProxyInit:
    def test_attributes(self):
        logger = _make_logger()
        proxy = StdioProxy(command=["python", "server.py"], witness_logger=logger, actor="test")
        assert proxy.command == ["python", "server.py"]
        assert proxy.witness_logger is logger
        assert proxy.actor == "test"

    def test_default_actor(self):
        logger = _make_logger()
        proxy = StdioProxy(command=["echo"], witness_logger=logger)
        assert proxy.actor == "stdio_proxy"


class TestLogMessage:
    """Unit-test _log_message in isolation."""

    @pytest.mark.asyncio
    async def test_valid_json_rpc_request(self):
        logger = _make_logger()
        proxy = StdioProxy(command=["echo"], witness_logger=logger)
        msg = {"jsonrpc": "2.0", "method": "tools/call", "params": {"name": "bash"}, "id": 1}
        await proxy._log_message(json.dumps(msg).encode() + b"\n", "request")
        logger.alog_event.assert_awaited_once()
        call_kwargs = logger.alog_event.call_args.kwargs
        assert call_kwargs["action"] == "tools/call"
        assert call_kwargs["tool"] == "bash"

    @pytest.mark.asyncio
    async def test_valid_json_rpc_response(self):
        logger = _make_logger()
        proxy = StdioProxy(command=["echo"], witness_logger=logger)
        msg = {"jsonrpc": "2.0", "result": {"content": "ok"}, "id": 1}
        await proxy._log_message(json.dumps(msg).encode() + b"\n", "response")
        logger.alog_event.assert_awaited_once()
        call_kwargs = logger.alog_event.call_args.kwargs
        # No method in response → action falls back to "response"
        assert call_kwargs["action"] == "response"

    @pytest.mark.asyncio
    async def test_invalid_json_ignored(self):
        logger = _make_logger()
        proxy = StdioProxy(command=["echo"], witness_logger=logger)
        await proxy._log_message(b"not json\n", "request")
        logger.alog_event.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_empty_line_ignored(self):
        logger = _make_logger()
        proxy = StdioProxy(command=["echo"], witness_logger=logger)
        await proxy._log_message(b"\n", "request")
        logger.alog_event.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_risk_indicators_attached(self):
        logger = _make_logger()
        proxy = StdioProxy(command=["echo"], witness_logger=logger)
        msg = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {"name": "bash", "arguments": {"command": "sudo rm -rf /"}},
            "id": 2,
        }
        await proxy._log_message(json.dumps(msg).encode() + b"\n", "request")
        call_kwargs = logger.alog_event.call_args.kwargs
        # Should detect shell_exec and privilege_escalation
        indicators = call_kwargs["risk_indicators"]
        assert isinstance(indicators, list)
        patterns = [i["pattern"] for i in indicators]
        assert any("shell_exec" in p or "privilege_escalation" in p for p in patterns)


class TestRunStdioProxy:
    @pytest.mark.asyncio
    async def test_echo_command(self, tmp_path):
        """Integration test: proxy wraps 'echo hello' and logs the output."""
        from agentwit.witness.log import WitnessLogger

        logger = WitnessLogger(session_dir=str(tmp_path), actor="test")

        # Patch stdin so it closes immediately (EOF)
        mock_reader = AsyncMock()
        mock_reader.readline = AsyncMock(side_effect=[b""])

        with patch("agentwit.proxy.stdio_proxy.asyncio.StreamReader", return_value=mock_reader):
            with patch("agentwit.proxy.stdio_proxy.asyncio.StreamReaderProtocol"):
                with patch.object(asyncio.get_event_loop(), "connect_read_pipe", new_callable=AsyncMock):
                    # Run a simple subprocess
                    proxy = StdioProxy(
                        command=[sys.executable, "-c", "import sys; sys.exit(0)"],
                        witness_logger=logger,
                    )
                    code = await proxy.run()

        logger.close()
        assert code == 0

    @pytest.mark.asyncio
    async def test_convenience_function(self, tmp_path):
        from agentwit.witness.log import WitnessLogger

        logger = WitnessLogger(session_dir=str(tmp_path), actor="test")
        mock_reader = AsyncMock()
        mock_reader.readline = AsyncMock(side_effect=[b""])

        with patch("agentwit.proxy.stdio_proxy.asyncio.StreamReader", return_value=mock_reader):
            with patch("agentwit.proxy.stdio_proxy.asyncio.StreamReaderProtocol"):
                with patch.object(asyncio.get_event_loop(), "connect_read_pipe", new_callable=AsyncMock):
                    code = await run_stdio_proxy(
                        [sys.executable, "-c", "import sys; sys.exit(0)"],
                        logger,
                    )
        logger.close()
        assert code == 0
