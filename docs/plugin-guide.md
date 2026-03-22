# Plugin Guide

agentwit has a first-class plugin system that lets you add custom detection
rules without forking the project.  Plugins are discovered automatically via
Python entry-points — install the plugin package and it starts working.

---

## How Plugins Work

1. You create a Python package that contains a class subclassing `PluginBase`.
2. You register it under the `agentwit.plugins` entry-point group.
3. When agentwit starts, `load_plugins()` discovers and instantiates it.
4. For every incoming request/response, agentwit calls `plugin.scan(event)`.
5. Alerts returned by `scan()` are merged into `risk_indicators` before the
   event is written to the witness log.

---

## Step-by-Step: Creating Your First Plugin

### Step 1 — Create the project structure

```
agentwit-plugin-myplugin/
├── pyproject.toml
├── README.md
└── agentwit_myplugin/
    └── __init__.py
```

### Step 2 — Implement `PluginBase`

```python
# agentwit_myplugin/__init__.py
from agentwit.plugins.base import PluginBase


class MyPlugin(PluginBase):
    """Example plugin: detects SQL-like patterns in tool inputs."""

    @property
    def name(self) -> str:
        return "my-plugin"

    @property
    def version(self) -> str:
        return "1.0.0"

    def scan(self, event: dict) -> list[dict]:
        """Scan one event and return a list of alert dicts.

        Args:
            event: A dict with keys:
                - action (str): e.g. "tools/call"
                - tool (str | None): e.g. "bash"
                - full_payload (dict): complete request + response

        Returns:
            List of dicts, each with:
                - pattern (str): machine-readable alert name
                - severity (str): "low" | "medium" | "high" | "critical"
                - description (str): human-readable explanation
            Return [] if no issues found.
        """
        alerts = []

        payload_str = str(event.get("full_payload", "")).lower()

        # Example: detect SQL injection keywords
        sql_keywords = ["drop table", "union select", "' or '1'='1"]
        for kw in sql_keywords:
            if kw in payload_str:
                alerts.append({
                    "pattern": "sql_injection_attempt",
                    "severity": "critical",
                    "description": f"Possible SQL injection: keyword '{kw}' found in payload",
                })
                break  # one alert per event is usually enough

        # Example: detect large data transfers (>100 KB response)
        result = event.get("full_payload", {}).get("result", {})
        result_size = len(str(result))
        if result_size > 100_000:
            alerts.append({
                "pattern": "large_response",
                "severity": "medium",
                "description": f"Response size {result_size} bytes exceeds 100 KB threshold",
            })

        return alerts
```

### Step 3 — Write `pyproject.toml`

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "agentwit-plugin-myplugin"
version = "1.0.0"
description = "Custom detection plugin for agentwit"
requires-python = ">=3.10"
dependencies = [
    "agentwit>=0.7.0",
]

# This is the critical section — it registers your plugin
[project.entry-points."agentwit.plugins"]
my_plugin = "agentwit_myplugin:MyPlugin"

[tool.hatch.build.targets.wheel]
packages = ["agentwit_myplugin"]
```

### Step 4 — Install locally for testing

```bash
# Install in editable mode
pip install -e .

# Verify it's registered
python -c "
import importlib.metadata
eps = importlib.metadata.entry_points(group='agentwit.plugins')
for ep in eps:
    print(ep.name, '->', ep.value)
"
# Output: my_plugin -> agentwit_myplugin:MyPlugin
```

### Step 5 — Test your plugin

```python
# test_myplugin.py
from agentwit_myplugin import MyPlugin

plugin = MyPlugin()

def test_name():
    assert plugin.name == "my-plugin"

def test_sql_injection_detected():
    event = {
        "action": "tools/call",
        "tool": "database_query",
        "full_payload": {
            "params": {"query": "SELECT * FROM users WHERE id='' OR '1'='1'"},
            "result": {},
        },
    }
    alerts = plugin.scan(event)
    assert len(alerts) == 1
    assert alerts[0]["pattern"] == "sql_injection_attempt"
    assert alerts[0]["severity"] == "critical"

def test_clean_event_returns_empty():
    event = {
        "action": "tools/call",
        "tool": "read_file",
        "full_payload": {"params": {"path": "/tmp/test.txt"}, "result": {"content": "hello"}},
    }
    assert plugin.scan(event) == []
```

```bash
pip install pytest
pytest test_myplugin.py -v
```

### Step 6 — Verify integration with agentwit

```bash
# In one terminal: start your MCP server
python my_mcp_server.py

# In another terminal: start agentwit proxy
agentwit proxy --target http://localhost:3000 --port 8765

# agentwit will log plugin loading:
# INFO agentwit.plugins: Loaded plugin: my-plugin v1.0.0
# INFO agentwit.plugins: agentwit proxy: 1 plugin(s) active: ['my-plugin']
```

---

## Complete Plugin Example: Regex Pattern Scanner

A more realistic plugin that reads patterns from a configuration file:

```python
# agentwit_regex_scanner/__init__.py
"""
agentwit plugin: regex-based pattern scanner.

Configuration via environment variable AGENTWIT_REGEX_PATTERNS_FILE
pointing to a YAML file:

    patterns:
      - name: aws_key_leak
        regex: 'AKIA[0-9A-Z]{16}'
        severity: critical
        description: "AWS access key detected in payload"
      - name: private_ip_leak
        regex: '192\.168\.\d+\.\d+'
        severity: low
        description: "Private IP address in payload"
"""
from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass, field

from agentwit.plugins.base import PluginBase

logger = logging.getLogger(__name__)


@dataclass
class PatternDef:
    name: str
    regex: re.Pattern
    severity: str
    description: str


class RegexScannerPlugin(PluginBase):
    @property
    def name(self) -> str:
        return "regex-scanner"

    @property
    def version(self) -> str:
        return "1.0.0"

    def __init__(self) -> None:
        self._patterns: list[PatternDef] = self._load_patterns()

    def _load_patterns(self) -> list[PatternDef]:
        path = os.environ.get("AGENTWIT_REGEX_PATTERNS_FILE")
        if not path:
            return self._builtin_patterns()
        try:
            import yaml  # type: ignore[import]
            with open(path) as f:
                config = yaml.safe_load(f)
            return [
                PatternDef(
                    name=p["name"],
                    regex=re.compile(p["regex"]),
                    severity=p.get("severity", "medium"),
                    description=p.get("description", ""),
                )
                for p in config.get("patterns", [])
            ]
        except Exception as exc:
            logger.warning("regex-scanner: failed to load patterns file: %s", exc)
            return self._builtin_patterns()

    def _builtin_patterns(self) -> list[PatternDef]:
        return [
            PatternDef(
                name="aws_access_key",
                regex=re.compile(r"AKIA[0-9A-Z]{16}"),
                severity="critical",
                description="AWS access key ID detected",
            ),
            PatternDef(
                name="jwt_token",
                regex=re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"),
                severity="high",
                description="JWT token detected in payload",
            ),
        ]

    def scan(self, event: dict) -> list[dict]:
        payload_str = json.dumps(event.get("full_payload", {}))
        alerts = []
        for pat in self._patterns:
            if pat.regex.search(payload_str):
                alerts.append({
                    "pattern": pat.name,
                    "severity": pat.severity,
                    "description": pat.description,
                })
        return alerts
```

---

## Publishing to PyPI

### Step 1 — Build the distribution

```bash
pip install build twine
python -m build
# Creates dist/agentwit_plugin_myplugin-1.0.0.tar.gz
#        dist/agentwit_plugin_myplugin-1.0.0-py3-none-any.whl
```

### Step 2 — Upload to PyPI

```bash
# Test on TestPyPI first
twine upload --repository testpypi dist/*

# Install from TestPyPI to verify
pip install --index-url https://test.pypi.org/simple/ agentwit-plugin-myplugin

# Upload to real PyPI
twine upload dist/*
```

### Step 3 — Naming convention

Use the prefix `agentwit-plugin-` for discoverability:

```
agentwit-plugin-myplugin        # good
agentwit-plugin-regex-scanner   # good
my-agentwit-thing               # harder to discover
```

### Step 4 — Add the agentwit-plugin classifier

In your `pyproject.toml`, add a classifier so users can find your plugin:

```toml
[project]
classifiers = [
    "Framework :: agentwit",
    "Topic :: Security",
    "Programming Language :: Python :: 3",
]
```

---

## `pyproject.toml` Entry-Points Reference

The entry-point group name must be exactly `agentwit.plugins`:

```toml
[project.entry-points."agentwit.plugins"]
# Format: <entry_point_name> = "<module_path>:<ClassName>"
my_plugin       = "my_package:MyPlugin"
another_plugin  = "my_package.submodule:AnotherPlugin"
```

The entry-point name (left side) is used only for display in warning messages.
The class name is what matters.

### Multiple Plugins from One Package

```toml
[project.entry-points."agentwit.plugins"]
sql_scanner   = "my_package.scanners:SqlScanner"
pii_scanner   = "my_package.scanners:PiiScanner"
rate_limiter  = "my_package.monitors:RateLimitMonitor"
```

---

## Plugin API Contract

Your `scan()` method receives a snapshot dict with the following keys.
All keys are optional — always use `.get()` with a default:

```python
event = {
    "action":       str,   # e.g. "tools/call", "tools/list", "GET"
    "tool":         str | None,  # tool name if applicable
    "full_payload": {
        "params": dict,    # request parameters
        "result": dict,    # response result (may be absent on error)
    },
}
```

Return an empty list `[]` if no issues are found.  Do not raise exceptions —
agentwit catches them with a warning and continues.

Each alert dict should have at minimum:

```python
{
    "pattern":     str,   # snake_case identifier, e.g. "sql_injection_attempt"
    "severity":    str,   # "low" | "medium" | "high" | "critical"
    "description": str,   # human-readable explanation
}
```

Additional fields are allowed and will be preserved in the witness log.
