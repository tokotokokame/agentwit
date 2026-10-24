"""Default configuration and the schema used to validate it.

The schema is intentionally small and declarative: each leaf is a
``(type, )`` or ``(type, allowed_values)`` spec. Unknown top-level or
nested keys are reported by the validator rather than silently accepted,
so a typo in ``config.yaml`` cannot quietly disable a control.
"""
from __future__ import annotations

from typing import Any

# Default config — contains NO secrets, only references and plain settings.
DEFAULT_CONFIG: dict[str, Any] = {
    "proxy": {
        "target": "http://localhost:3000",
        "host": "127.0.0.1",      # loopback only; 0.0.0.0 requires opt-in + warning
        "port": 8765,
        "timeout": 30.0,
    },
    "monitor": {
        "rules": {                # built-in rule name -> on/off (工程2で本格結線)
            "shell_exec": True,
            "privilege_escalation": True,
            "credential_access": True,
            "data_exfil": True,
            "persistence": True,
            "lateral_movement": True,
        },
        "only_tools": [],         # [] = all tools; names = restrict monitoring scope
        "redact": {
            "enabled": True,      # keep secrets out of the tamper-evident log
            "keys": ["password", "token", "api_key", "apikey",
                     "secret", "authorization", "bearer", "private_key"],
        },
    },
    "notify": {
        "routes": [],             # e.g. {name, kind, secret_ref, on:[...]} (工程3)
        "rate_limit": {"max_per_min": 10},
    },
}

# Severity vocabulary shared across the project.
SEVERITIES = ("LOW", "MEDIUM", "HIGH", "CRITICAL")

# Hosts we will POST notifications to. Anything else is rejected (SSRF guard).
ALLOWED_NOTIFY_HOSTS = ("hooks.slack.com", "discord.com", "discordapp.com")
