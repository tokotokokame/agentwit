"""LangChain callback integration for agentwit.

Usage::

    from agentwit import WitnessLogger
    from agentwit.integrations.langchain import AgentwitCallback

    logger = WitnessLogger(session_dir="./witness_logs", actor="langchain")
    callbacks = [AgentwitCallback(witness_logger=logger)]

    # Pass to any LangChain chain / agent
    chain.invoke({"input": "..."}, config={"callbacks": callbacks})

Requires ``langchain-core>=0.2.0`` (install with ``pip install agentwit[full]``).
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from agentwit.witness.log import WitnessLogger

try:
    from langchain_core.callbacks.base import BaseCallbackHandler
    from langchain_core.outputs import LLMResult
except ImportError as _err:  # pragma: no cover
    raise ImportError(
        "langchain-core is required for AgentwitCallback. "
        "Install it with: pip install agentwit[full]"
    ) from _err


class AgentwitCallback(BaseCallbackHandler):
    """LangChain callback handler that records all agent/tool/LLM events to
    a WitnessLogger JSONL audit trail.

    Args:
        witness_logger: A :class:`~agentwit.witness.log.WitnessLogger` instance.
            All events will be written to this logger's session.
    """

    def __init__(self, witness_logger: "WitnessLogger") -> None:
        super().__init__()
        self._logger = witness_logger

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _now() -> str:
        """Return current UTC time as ISO-8601 string (second precision)."""
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    @staticmethod
    def _extract_thought(log_text: str) -> str:
        """Extract the Thought line from a ReAct-format agent log.

        Searches line by line for the first line starting with ``Thought:``
        (case-insensitive) and returns the text after the colon.  Returns
        an empty string when no such line is found.
        """
        for line in (log_text or "").splitlines():
            stripped = line.strip()
            if stripped.lower().startswith("thought:"):
                return stripped[len("thought:"):].strip()
        return ""

    def _write_audit(self, record: dict) -> None:
        """Append *record* as one JSON line to ``audit.jsonl`` in the session dir.

        Failures are silently swallowed so a broken audit path never
        interrupts the agent's execution.
        """
        try:
            audit_path = Path(self._logger.session_path) / "audit.jsonl"
            with audit_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Tool events
    # ------------------------------------------------------------------

    def on_tool_start(
        self,
        serialized: dict[str, Any],
        input_str: str,
        *,
        run_id: Any = None,
        parent_run_id: Any = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        tool_name = serialized.get("name", "") or ""
        self._log(
            action="tool_start",
            tool=tool_name,
            payload={"input": input_str, "serialized": serialized},
        )

    def on_tool_end(
        self,
        output: str,
        *,
        run_id: Any = None,
        parent_run_id: Any = None,
        tags: list[str] | None = None,
        **kwargs: Any,
    ) -> None:
        self._log(
            action="tool_end",
            tool="",
            payload={"output": output},
        )

    def on_tool_error(
        self,
        error: BaseException | KeyboardInterrupt,
        *,
        run_id: Any = None,
        parent_run_id: Any = None,
        tags: list[str] | None = None,
        **kwargs: Any,
    ) -> None:
        self._log(
            action="tool_error",
            tool="",
            payload={"error": str(error)},
        )

    # ------------------------------------------------------------------
    # LLM events
    # ------------------------------------------------------------------

    def on_llm_start(
        self,
        serialized: dict[str, Any],
        prompts: list[str],
        *,
        run_id: Any = None,
        parent_run_id: Any = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        prompt_preview = (prompts[0] if prompts else "")[:100]
        self._log(
            action="llm_start",
            tool=serialized.get("id", ["", ""])[-1] if serialized.get("id") else "",
            payload={"prompts": prompts, "serialized": serialized},
        )
        self._write_audit({
            "type": "llm_start",
            "prompt_preview": prompt_preview,
            "timestamp": self._now(),
            "session_id": self._logger.session_id,
        })

    def on_llm_end(
        self,
        response: "LLMResult",
        *,
        run_id: Any = None,
        parent_run_id: Any = None,
        tags: list[str] | None = None,
        **kwargs: Any,
    ) -> None:
        response_text = ""
        try:
            gens = response.generations
            if gens and gens[0]:
                gen0 = gens[0][0]
                response_text = getattr(gen0, "text", None) or str(gen0)
        except Exception:
            response_text = str(getattr(response, "generations", ""))
        response_preview = response_text[:100]
        self._log(
            action="llm_end",
            tool="",
            payload={"generations": str(response.generations)},
        )
        self._write_audit({
            "type": "llm_end",
            "response_preview": response_preview,
            "timestamp": self._now(),
            "session_id": self._logger.session_id,
        })

    def on_llm_error(
        self,
        error: BaseException | KeyboardInterrupt,
        *,
        run_id: Any = None,
        parent_run_id: Any = None,
        tags: list[str] | None = None,
        **kwargs: Any,
    ) -> None:
        self._log(
            action="llm_error",
            tool="",
            payload={"error": str(error)},
        )

    # ------------------------------------------------------------------
    # Agent events
    # ------------------------------------------------------------------

    def on_agent_action(
        self,
        action: Any,
        *,
        run_id: Any = None,
        parent_run_id: Any = None,
        tags: list[str] | None = None,
        **kwargs: Any,
    ) -> None:
        tool_name = getattr(action, "tool", "") or ""
        tool_input = getattr(action, "tool_input", None)
        log_text = getattr(action, "log", "") or ""
        thought = self._extract_thought(log_text)
        self._log(
            action="agent_action",
            tool=tool_name,
            payload={
                "tool": tool_name,
                "tool_input": tool_input,
                "log": log_text,
            },
        )
        self._write_audit({
            "type": "agent_thought",
            "thought": thought,
            "tool_selected": tool_name,
            "reasoning": str(tool_input) if tool_input is not None else "",
            "timestamp": self._now(),
            "session_id": self._logger.session_id,
        })

    def on_agent_finish(
        self,
        finish: Any,
        *,
        run_id: Any = None,
        parent_run_id: Any = None,
        tags: list[str] | None = None,
        **kwargs: Any,
    ) -> None:
        log_text = getattr(finish, "log", "") or ""
        return_values = getattr(finish, "return_values", {}) or {}
        final_answer = return_values.get("output", log_text)
        thought = self._extract_thought(log_text)
        self._log(
            action="agent_finish",
            tool="",
            payload={
                "return_values": return_values,
                "log": log_text,
            },
        )
        self._write_audit({
            "type": "agent_finish",
            "final_answer": str(final_answer),
            "thought": thought,
            "timestamp": self._now(),
            "session_id": self._logger.session_id,
        })

    # ------------------------------------------------------------------
    # Chain events
    # ------------------------------------------------------------------

    def on_chain_start(
        self,
        serialized: dict[str, Any],
        inputs: dict[str, Any],
        *,
        run_id: Any = None,
        parent_run_id: Any = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        self._log(
            action="chain_start",
            tool=serialized.get("id", [""])[-1] if serialized.get("id") else "",
            payload={"inputs": inputs},
        )

    def on_chain_end(
        self,
        outputs: dict[str, Any],
        *,
        run_id: Any = None,
        parent_run_id: Any = None,
        tags: list[str] | None = None,
        **kwargs: Any,
    ) -> None:
        self._log(
            action="chain_end",
            tool="",
            payload={"outputs": outputs},
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _log(self, action: str, tool: str, payload: dict[str, Any]) -> None:
        """Write an event to WitnessLogger (sync wrapper with best-effort)."""
        from agentwit.analyzer.scorer import RiskScorer

        try:
            scorer = RiskScorer()
            temp_event = {"action": action, "tool": tool, "full_payload": payload}
            risk_indicators = scorer.score_event(temp_event)
        except Exception:
            risk_indicators = []

        try:
            # Try async path if there's a running loop
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.ensure_future(
                    self._logger.alog_event(
                        action=action,
                        tool=tool,
                        full_payload=payload,
                        risk_indicators=risk_indicators,
                    )
                )
            else:
                loop.run_until_complete(
                    self._logger.alog_event(
                        action=action,
                        tool=tool,
                        full_payload=payload,
                        risk_indicators=risk_indicators,
                    )
                )
        except Exception:
            # Fall back to sync log
            try:
                self._logger.log_event(
                    action=action,
                    tool=tool,
                    full_payload=payload,
                    risk_indicators=risk_indicators,
                )
            except Exception:
                pass
