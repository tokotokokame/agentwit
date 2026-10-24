"""Redact secrets from payloads before they enter the witness log.

Key-name based: any dict key whose name contains one of the configured
sensitive substrings (case-insensitive) has its value replaced. Works
recursively through nested dicts and lists. The detection *fact* still
lands in the log (via risk_indicators); only the raw value is removed, so
the tamper-evident chain keeps its audit value without storing credentials
in plaintext.
"""
from __future__ import annotations

from typing import Any

PLACEHOLDER = "***REDACTED***"


def redact_payload(obj: Any, keys: list[str]) -> Any:
    """Return a copy of *obj* with values under sensitive keys replaced.

    *keys* are lower-cased substrings to match against each dict key.
    The input is not mutated.
    """
    if not keys:
        return obj
    lowered = [k.lower() for k in keys]
    return _walk(obj, lowered)


def _walk(obj: Any, keys: list[str]) -> Any:
    if isinstance(obj, dict):
        out: dict[Any, Any] = {}
        for k, v in obj.items():
            if isinstance(k, str) and any(s in k.lower() for s in keys):
                out[k] = PLACEHOLDER
            else:
                out[k] = _walk(v, keys)
        return out
    if isinstance(obj, list):
        return [_walk(v, keys) for v in obj]
    return obj
