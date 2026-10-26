"""Redact secrets from payloads before they enter the witness log.

Two layers, both preserving the audit trail (the detection *fact* still
lands in the log via risk_indicators; only the raw secret is removed):

  1. Key-name based — any dict key whose name contains a configured
     sensitive substring has its whole value replaced.
  2. Value scanning (optional) — high-confidence secret patterns found
     *inside* string values (e.g. a Bearer token embedded in a shell
     command) have just the secret substring masked, keeping surrounding
     context. Only strongly-identifying shapes are matched, to avoid
     over-redacting ordinary data.

Neither layer mutates its input.
"""
from __future__ import annotations

import re
from typing import Any

PLACEHOLDER = "***REDACTED***"

# (regex, prefix_group). prefix_group 0 → replace the whole match;
# >0 → keep that captured prefix and mask the rest. High-confidence only.
_VALUE_PATTERNS: list[tuple[re.Pattern, int]] = [
    (re.compile(r"(?i)\b(bearer\s+)[A-Za-z0-9._\-]{8,}"), 1),
    (re.compile(r"(?i)(authorization\s*[:=]\s*[A-Za-z]+\s+)[A-Za-z0-9._\-=/+]{8,}"), 1),
    (re.compile(r"(?i)(api[_-]?key\s*[:=]\s*)[A-Za-z0-9._\-]{12,}"), 1),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), 0),                       # AWS access key id
    (re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"), 0),            # GitHub token
    (re.compile(r"\bsk-[A-Za-z0-9]{16,}\b"), 0),                   # OpenAI-style key
    (re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"), 0),          # Slack token
    (re.compile(r"eyJ[A-Za-z0-9_\-]+\.eyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+"), 0),  # JWT
    (re.compile(r"https://hooks\.slack\.com/services/[A-Za-z0-9/_\-]+"), 0),
    (re.compile(r"https://discord(?:app)?\.com/api/webhooks/[A-Za-z0-9/_\-]+"), 0),
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----"), 0),
]


def redact_payload(obj: Any, keys: list[str], scan_values: bool = False) -> Any:
    """Return a copy of *obj* with secrets removed.

    *keys* are lower-cased substrings matched against dict key names. When
    *scan_values* is true, string values are also scanned for embedded
    high-confidence secrets. The input is not mutated.
    """
    if not keys and not scan_values:
        return obj
    return _walk(obj, [k.lower() for k in (keys or [])], scan_values)


def _walk(obj: Any, keys: list[str], scan: bool) -> Any:
    if isinstance(obj, dict):
        out: dict[Any, Any] = {}
        for k, v in obj.items():
            if isinstance(k, str) and any(s in k.lower() for s in keys):
                out[k] = PLACEHOLDER
            else:
                out[k] = _walk(v, keys, scan)
        return out
    if isinstance(obj, list):
        return [_walk(v, keys, scan) for v in obj]
    if scan and isinstance(obj, str):
        return _scan_value(obj)
    return obj


def _scan_value(s: str) -> str:
    for rx, prefix_group in _VALUE_PATTERNS:
        if prefix_group == 0:
            s = rx.sub(PLACEHOLDER, s)
        else:
            s = rx.sub(lambda m: m.group(prefix_group) + PLACEHOLDER, s)
    return s
