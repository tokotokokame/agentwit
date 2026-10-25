"""agentwit configuration layer.

Single place that owns ``~/.agentwit/``: the non-secret ``config.yaml``,
the ``secrets.env`` holding credentials, directory permissions, schema
validation and secret-reference resolution.

Secrets are never stored in ``config.yaml`` and never shipped in the
package — ``config.yaml`` only holds references like ``${env:NAME}``.
"""
from __future__ import annotations

from .loader import (
    config_home,
    load_config,
    save_config,
    validate_config,
    init_home,
    check_permissions,
)
from .secrets import resolve, SecretResolver, set_secret, list_secret_names
from .redact import redact_payload

__all__ = [
    "config_home",
    "load_config",
    "save_config",
    "validate_config",
    "init_home",
    "check_permissions",
    "resolve",
    "SecretResolver",
    "set_secret",
    "list_secret_names",
    "redact_payload",
]
