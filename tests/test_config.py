"""Tests for agentwit.config — loader, secrets, redaction and CLI."""
from __future__ import annotations

import os
import stat

import pytest
from click.testing import CliRunner

from agentwit import config as C
from agentwit.cli import main


@pytest.fixture()
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTWIT_HOME", str(tmp_path))
    return tmp_path


# --- init / permissions ----------------------------------------------------

def test_init_creates_files(home):
    rep = C.init_home()
    assert (home / "config.yaml").exists()
    assert (home / "secrets.env").exists()
    assert "created" in rep["config"]


@pytest.mark.skipif(os.name != "posix", reason="POSIX permissions only")
def test_init_sets_tight_permissions(home):
    C.init_home()
    assert stat.S_IMODE((home).stat().st_mode) == 0o700
    assert stat.S_IMODE((home / "secrets.env").stat().st_mode) == 0o600


def test_init_is_idempotent(home):
    C.init_home()
    (home / "config.yaml").write_text("proxy: {port: 9001}\n")
    C.init_home()  # must not clobber
    assert C.load_config()["proxy"]["port"] == 9001


# --- secrets ---------------------------------------------------------------

def test_secret_from_file(home):
    C.init_home()
    (home / "secrets.env").write_text("AGENTWIT_SLACK_WEBHOOK=https://hooks.slack.com/x\n")
    assert C.resolve("${env:AGENTWIT_SLACK_WEBHOOK}") == "https://hooks.slack.com/x"


def test_env_beats_file(home, monkeypatch):
    C.init_home()
    (home / "secrets.env").write_text("TOK=from_file\n")
    monkeypatch.setenv("TOK", "from_env")
    assert C.resolve("${env:TOK}") == "from_env"


def test_unresolved_secret_is_empty(home):
    C.init_home()
    assert C.resolve("${env:NOPE}") == ""


def test_config_yaml_never_holds_expanded_secret(home):
    C.init_home()
    (home / "secrets.env").write_text("TOK=supersecret\n")
    # resolve_secrets=False (what the CLI shows / saves) keeps the reference
    cfg = C.load_config(resolve_secrets=False)
    assert "supersecret" not in str(cfg)


# --- validation ------------------------------------------------------------

def test_validate_flags_unknown_and_type(home):
    errors, _ = C.validate_config(
        {"ghost": 1, "proxy": {"oops": 2, "port": "x"}}
    )
    joined = " ".join(errors)
    assert "ghost" in joined and "oops" in joined and "port" in joined


def test_validate_warns_on_wildcard_bind(home):
    _, warnings = C.validate_config({"proxy": {"host": "0.0.0.0"}})
    assert warnings and "interfaces" in warnings[0]


def test_validate_catches_yaml_bool_on_key(home):
    # `on: [HIGH, CRITICAL]` written unquoted in YAML parses to a boolean
    # True key, not the string "on" — severity routing would then silently
    # never fire. This must be a hard validation error, not a passed check.
    errors, _ = C.validate_config(
        {"notify": {"routes": [
            {"kind": "discord", "url": "https://discord.com/x", True: ["HIGH"]}
        ]}}
    )
    joined = " ".join(errors)
    assert "boolean" in joined and '"on"' in joined


def test_validate_catches_yaml_bool_off_key(home):
    errors, _ = C.validate_config(
        {"notify": {"routes": [
            {"kind": "discord", "url": "https://discord.com/x", False: ["LOW"]}
        ]}}
    )
    joined = " ".join(errors)
    assert "boolean" in joined and '"off"' in joined


def test_cli_set_rejects_unquoted_on_key(home):
    # Reproduces the exact footgun: `on:` typed unquoted on the command
    # line. yaml.safe_load coerces the key to True, and `config set` must
    # now reject it instead of silently saving a dead route.
    runner = CliRunner()
    runner.invoke(main, ["init"])
    result = runner.invoke(main, [
        "config", "set", "notify.routes",
        '[{kind: discord, url: "https://discord.com/x", on: [HIGH, CRITICAL]}]',
    ])
    assert result.exit_code != 0
    assert "boolean" in result.output


# --- redaction -------------------------------------------------------------

def test_redact_is_recursive_and_pure(home):
    payload = {"password": "p", "a": {"api_key": "k"}, "l": [{"token": "t"}], "ok": "v"}
    out = C.redact_payload(payload, ["password", "api_key", "token"])
    assert out["password"] == "***REDACTED***"
    assert out["a"]["api_key"] == "***REDACTED***"
    assert out["l"][0]["token"] == "***REDACTED***"
    assert out["ok"] == "v"
    assert payload["password"] == "p"  # input unchanged


# --- resilience ------------------------------------------------------------

def test_broken_config_falls_back(home):
    C.init_home()
    (home / "config.yaml").write_text("proxy: {port: not_int}\nbogus: 1\n")
    cfg = C.load_config()  # must not raise
    assert cfg["proxy"]["port"] == 8765


# --- CLI -------------------------------------------------------------------

def test_cli_set_get_roundtrip(home):
    r = CliRunner()
    assert r.invoke(main, ["init"]).exit_code == 0
    assert r.invoke(main, ["config", "set", "proxy.port", "9000"]).exit_code == 0
    out = r.invoke(main, ["config", "get", "proxy.port"])
    assert out.output.strip() == "9000"


def test_cli_rejects_invalid_set(home):
    r = CliRunner()
    r.invoke(main, ["init"])
    res = r.invoke(main, ["config", "set", "proxy.port", "99999"])
    assert res.exit_code == 1 and "Rejected" in res.output
