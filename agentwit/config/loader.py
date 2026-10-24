"""Load, validate, persist and initialise ``~/.agentwit/``.

Design guarantees:
  * ``yaml.safe_load`` only — a config file can never execute code.
  * Unknown/mis-typed keys are reported, not silently accepted.
  * A broken config never crashes a long-running daemon: ``load_config``
    falls back to defaults for the invalid parts and warns on stderr.
  * Directory is ``0700``; ``secrets.env`` is forced to ``0600``.
"""
from __future__ import annotations

import os
import stat
import sys
from pathlib import Path
from typing import Any

from .defaults import DEFAULT_CONFIG, SEVERITIES
from .secrets import SecretResolver

_CONFIG_NAME = "config.yaml"
_SECRETS_NAME = "secrets.env"

_SECRETS_TEMPLATE = """\
# agentwit secrets — chmod 600, never commit, never shipped in the package.
# Referenced from config.yaml as ${env:NAME}. One KEY=VALUE per line.
#
# AGENTWIT_SLACK_WEBHOOK=https://hooks.slack.com/services/xxx/yyy/zzz
# AGENTWIT_DISCORD_WEBHOOK=https://discord.com/api/webhooks/xxx/yyy
"""


# ---------------------------------------------------------------------------
# Paths & permissions
# ---------------------------------------------------------------------------

def config_home() -> Path:
    """Return the agentwit home dir (``$AGENTWIT_HOME`` or ``~/.agentwit``)."""
    env = os.environ.get("AGENTWIT_HOME")
    return Path(env).expanduser() if env else Path.home() / ".agentwit"


def _chmod(path: Path, mode: int) -> None:
    try:
        path.chmod(mode)
    except OSError:
        pass


def check_permissions(home: Path | None = None) -> tuple[list[str], list[str]]:
    """Enforce 0700 on home and 0600 on secrets.env.

    Returns ``(fixed, problems)`` — human-readable messages.
    """
    home = home or config_home()
    fixed: list[str] = []
    problems: list[str] = []
    if home.exists() and (home.stat().st_mode & 0o077):
        _chmod(home, 0o700)
        fixed.append(f"tightened {home} to 0700")
    secrets = home / _SECRETS_NAME
    if secrets.exists() and (secrets.stat().st_mode & 0o077):
        _chmod(secrets, 0o600)
        fixed.append(f"tightened {secrets} to 0600")
    return fixed, problems


# ---------------------------------------------------------------------------
# Merge & validate
# ---------------------------------------------------------------------------

def _deep_merge(base: dict, override: dict) -> dict:
    out = dict(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def validate_config(cfg: Any) -> tuple[list[str], list[str]]:
    """Validate against the default shape. Returns ``(errors, warnings)``."""
    errors: list[str] = []
    warnings: list[str] = []

    if not isinstance(cfg, dict):
        return ([f"top level must be a mapping, got {type(cfg).__name__}"], [])

    for key in cfg:
        if key not in DEFAULT_CONFIG:
            errors.append(f"unknown top-level key: {key!r}")

    def _check_section(name: str, known: dict) -> dict:
        section = cfg.get(name, {})
        if not isinstance(section, dict):
            errors.append(f"{name}: must be a mapping")
            return {}
        for k, v in section.items():
            if k not in known:
                errors.append(f"{name}.{k}: unknown key")
                continue
            expected = type(known[k])
            if expected is float and isinstance(v, int):
                continue  # ints are acceptable where a float default lives
            if not isinstance(v, expected):
                errors.append(
                    f"{name}.{k}: expected {expected.__name__}, "
                    f"got {type(v).__name__}"
                )
        return section

    proxy = _check_section("proxy", DEFAULT_CONFIG["proxy"])
    if proxy.get("host") in ("0.0.0.0", "::"):
        warnings.append(
            "proxy.host binds all interfaces — the witness proxy will be "
            "reachable off-box. Keep 127.0.0.1 unless you really mean it."
        )
    port = proxy.get("port")
    if isinstance(port, int) and not (1 <= port <= 65535):
        errors.append(f"proxy.port out of range: {port}")

    _check_section("monitor", DEFAULT_CONFIG["monitor"])
    notify = _check_section("notify", DEFAULT_CONFIG["notify"])
    for i, route in enumerate(notify.get("routes", []) or []):
        if not isinstance(route, dict):
            errors.append(f"notify.routes[{i}]: must be a mapping")
            continue
        for sev in route.get("on", []) or []:
            if str(sev).upper() not in SEVERITIES:
                errors.append(f"notify.routes[{i}].on: bad severity {sev!r}")

    return errors, warnings


# ---------------------------------------------------------------------------
# Load / save / init
# ---------------------------------------------------------------------------

def load_config(
    home: Path | None = None, resolve_secrets: bool = True
) -> dict:
    """Load config.yaml merged over defaults; never raises on a bad file.

    Invalid parts fall back to defaults with a stderr warning, so a daemon
    stays up. Secret references are resolved last (so secrets never sit in
    the returned structure as ``${env:...}``).
    """
    import yaml

    home = home or config_home()
    path = home / _CONFIG_NAME
    user_cfg: dict = {}
    if path.exists():
        try:
            loaded = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            if isinstance(loaded, dict):
                user_cfg = loaded
            else:
                print("[agentwit] warning: config.yaml is not a mapping; "
                      "using defaults", file=sys.stderr)
        except yaml.YAMLError as exc:
            print(f"[agentwit] warning: config.yaml parse error ({exc}); "
                  "using defaults", file=sys.stderr)

    errors, warnings = validate_config(user_cfg)
    for w in warnings:
        print(f"[agentwit] warning: {w}", file=sys.stderr)
    if errors:
        for e in errors:
            print(f"[agentwit] config error ignored: {e}", file=sys.stderr)

    merged = _deep_merge(DEFAULT_CONFIG, user_cfg if not errors else {})
    # If there were errors we still salvage the valid top-level sections:
    if errors:
        for sec in DEFAULT_CONFIG:
            if isinstance(user_cfg.get(sec), dict):
                sec_errs, _ = validate_config({sec: user_cfg[sec]})
                if not sec_errs:
                    merged[sec] = _deep_merge(DEFAULT_CONFIG[sec], user_cfg[sec])

    if resolve_secrets:
        resolver = SecretResolver(home)
        merged = _resolve_tree(merged, resolver)
    return merged


def _resolve_tree(obj: Any, resolver: SecretResolver) -> Any:
    if isinstance(obj, dict):
        return {k: _resolve_tree(v, resolver) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_resolve_tree(v, resolver) for v in obj]
    return resolver.resolve(obj)


def save_config(cfg: dict, home: Path | None = None) -> Path:
    """Write config.yaml (0644). Does not touch secrets."""
    import yaml

    home = home or config_home()
    home.mkdir(parents=True, exist_ok=True)
    _chmod(home, 0o700)
    path = home / _CONFIG_NAME
    path.write_text(
        yaml.safe_dump(cfg, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    _chmod(path, 0o644)
    return path


def init_home(home: Path | None = None) -> dict[str, str]:
    """Create ~/.agentwit with a default config and an empty secrets.env.

    Idempotent: existing files are left untouched. Returns a report dict.
    """
    home = home or config_home()
    report: dict[str, str] = {}
    home.mkdir(parents=True, exist_ok=True)
    _chmod(home, 0o700)
    report["home"] = f"{home} (0700)"

    cfg_path = home / _CONFIG_NAME
    if cfg_path.exists():
        report["config"] = f"{cfg_path} (kept existing)"
    else:
        save_config(DEFAULT_CONFIG, home)
        report["config"] = f"{cfg_path} (created)"

    sec_path = home / _SECRETS_NAME
    if sec_path.exists():
        report["secrets"] = f"{sec_path} (kept existing)"
    else:
        sec_path.write_text(_SECRETS_TEMPLATE, encoding="utf-8")
        report["secrets"] = f"{sec_path} (created)"
    _chmod(sec_path, 0o600)

    for d in ("witness_logs", "backups"):
        (home / d).mkdir(exist_ok=True)
        _chmod(home / d, 0o700)
    return report
