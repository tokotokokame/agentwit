"""Secret resolution: environment variables, then ``secrets.env``.

``config.yaml`` holds only references of the form ``${env:NAME}``. They are
resolved at load time against, in order of precedence:

  1. real process environment variables (``os.environ``)
  2. ``~/.agentwit/secrets.env``  (``KEY=VALUE`` lines, ``chmod 600``)

Secrets are never written back to ``config.yaml`` and ``secrets.env`` is
never merged into ``os.environ`` (so one leaky subprocess env dump does not
expose everything). Unresolved references become ``""`` with a warning.
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

_REF = re.compile(r"\$\{env:([A-Za-z_][A-Za-z0-9_]*)\}")


def _parse_env_file(path: Path) -> dict[str, str]:
    """Parse a ``KEY=VALUE`` file (no ``export``, ``#`` comments). Never raises."""
    out: dict[str, str] = {}
    try:
        raw = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return out
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if key:
            out[key] = val
    return out


class SecretResolver:
    """Resolves ``${env:NAME}`` references. Reads ``secrets.env`` once."""

    def __init__(self, home: Path) -> None:
        self._home = home
        secrets_path = home / "secrets.env"
        if secrets_path.exists():
            self._warn_if_loose(secrets_path)
            self._file = _parse_env_file(secrets_path)
        else:
            self._file = {}

    @staticmethod
    def _warn_if_loose(path: Path) -> None:
        try:
            mode = path.stat().st_mode & 0o077
        except OSError:
            return
        if mode:
            print(
                f"[agentwit] warning: {path} is group/other-readable; "
                f"run 'chmod 600 {path}'",
                file=sys.stderr,
            )

    def get(self, name: str) -> str | None:
        """Look up a single secret by name (env wins over secrets.env)."""
        if name in os.environ:
            return os.environ[name]
        return self._file.get(name)

    def resolve(self, value):
        """Replace every ``${env:NAME}`` in a string. Non-strings pass through."""
        if not isinstance(value, str):
            return value

        def _sub(m: "re.Match[str]") -> str:
            name = m.group(1)
            got = self.get(name)
            if got is None:
                print(
                    f"[agentwit] warning: secret '{name}' is unset "
                    f"(set it in env or ~/.agentwit/secrets.env)",
                    file=sys.stderr,
                )
                return ""
            return got

        return _REF.sub(_sub, value)


def resolve(value, home: Path | None = None):
    """Convenience one-shot resolver against the default home."""
    from .loader import config_home
    return SecretResolver(home or config_home()).resolve(value)
