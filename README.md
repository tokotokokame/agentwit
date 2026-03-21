# agentwit

**Debug and audit AI agent ↔ MCP server tool calls.**

```bash
pip install agentwit
agentwit proxy --target http://localhost:3000 --port 8765
```

```
[agentwit] 14:32:01  tools/call  bash       HIGH ⚠  shell_exec
[agentwit] 14:32:03  tools/call  read_file  LOW  ✓
[agentwit] 14:32:05  tools/call  bash       CRITICAL 🚨 privilege_escalation
```

Change one URL. No MCP server modification needed.

![agentwit demo](docs/demo.gif)

[日本語版](README.ja.md) · [PyPI](https://pypi.org/project/agentwit/) · [Releases](https://github.com/tokotokokame/agentwit/releases)

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![PyPI](https://img.shields.io/badge/PyPI-v0.5.0-orange.svg)](https://pypi.org/project/agentwit/)
[![Tests](https://img.shields.io/badge/tests-226%20passing-brightgreen.svg)](#)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## The problem

When an AI agent calls MCP server tools, **you can't see what's happening.**

```
AI Agent
    ↓  (black box)
MCP Server  →  bash / read_file / fetch / ...
```

agentwit sits between them as a transparent proxy and records everything.

```
AI Agent
    ↓
agentwit  ←  logs every call · detects risks · verifies integrity
    ↓
MCP Server  (zero modification)
```

---

## 5-minute demo

```bash
pip install agentwit

# 1. Start the proxy
agentwit proxy --target http://localhost:3000 --port 8765

# 2. Point your agent to port 8765 instead of 3000
#    That's it. Recording starts immediately.

# 3. Generate an audit report
agentwit report --session ./witness_logs/SESSION_ID --format html

# 4. Verify log integrity
agentwit verify --session ./witness_logs/SESSION_ID
# Chain integrity:  VALID ✓
# Signature check:  VALID ✓
```

---

## Features

### Log recording
- Tamper-proof SHA-256 chain — detect any modification
- ed25519 signatures — prove who recorded the log
- HTML / Markdown / JSON report generation
- Auto-backup to `~/.agentwit/backups/` on session end

### Risk detection
| Pattern | Severity |
|---|---|
| `privilege_escalation` (sudo, SUID) | CRITICAL |
| `prompt_injection` (ignore instructions, role hijack) | CRITICAL |
| `data_exfiltration` (external URL POST) | HIGH |
| `credential_access` (password, API key) | HIGH |
| `tool_schema_change` (tool added/modified) | HIGH |
| `call_rate_anomaly` (>30 calls/min) | HIGH |
| `lateral_movement` | HIGH |
| `persistence` (cron, service) | HIGH |

### Notifications
```bash
agentwit proxy --target http://localhost:3000 \
  --webhook https://hooks.slack.com/xxx \
  --webhook-on HIGH,CRITICAL
```
Slack and Discord supported (auto-detected from URL).

---

## Comparison

| Tool | Blocks traffic | Tamper-proof log | Signed log |
|---|:---:|:---:|:---:|
| mcp-scan | ✅ | ❌ | ❌ |
| Proximity | — | ❌ | ❌ |
| Intercept | ✅ | ❌ | ❌ |
| **agentwit** | **❌** | **✅** | **✅** |

Guards stop things. Witnesses record them.
agentwit is a witness — it never blocks, never interferes.

---

## LangChain integration

```bash
pip install agentwit[full]
```

```python
from agentwit import AgentwitCallback

agent.run(
    "your task",
    callbacks=[AgentwitCallback(output="./audit.json")]
)
```

---

## MCP Inspector GUI

Desktop debugger for MCP servers (Linux, Tauri + React).

```bash
sudo dpkg -i mcp-inspector_0.1.0_amd64.deb
mcp-inspector
# Connect: HTTP → http://localhost:3000/mcp
```

Features: tool list · parameter editor · response viewer · session compare · cost tracking

---

## Docker Compose audit stack

One command: agentwit + Grafana + Loki + Fluent Bit.

```bash
cd docker/
cp .env.example .env   # set TARGET_URL
docker compose up -d
# Grafana dashboard: http://localhost:3000
```

API keys / tokens are automatically masked by Fluent Bit.

---

## Commands

| Command | Description |
|---|---|
| `agentwit proxy` | Start transparent witness proxy |
| `agentwit verify` | Verify chain integrity + ed25519 signatures |
| `agentwit report` | Generate audit report (html/markdown/json) |
| `agentwit replay` | Replay session and verify chain |
| `agentwit diff` | Compare two sessions side by side |

---

## Witness log format

```json
{
  "witness_id":      "sha256 of entire event",
  "session_chain":   "sha256(prev_chain + event_hash)",
  "timestamp":       "2026-03-21T12:00:00Z",
  "tool":            "bash",
  "signature":       "base64(ed25519)",
  "risk_indicators": [{ "pattern": "shell_exec", "severity": "HIGH" }]
}
```

---

## Version history

| Version | Highlights |
|---|---|
| v0.1.0 | Proxy, SHA-256 chain log |
| v0.2.0 | HTML reports, LangChain, Slack/Discord |
| v0.3.0 | MCP Inspector GUI |
| v0.4.0 | Prompt injection detection, tool monitoring, Docker stack |
| v0.5.0 | ed25519 signing, bypass detection, anomaly detection |

---

## Articles
- [Why I built a "witness" for AI agents (Zenn)](https://zenn.dev/tokotokokame/articles/bba6a258a458a1)
- [From Witness to Inspector (Zenn)](https://zenn.dev/tokotokokame/articles/9183dd8a1734e2)

---

## Requirements

- Python 3.10+
- Dependencies auto-installed: FastAPI, uvicorn, httpx, click, cryptography

## License

[MIT](LICENSE) © agentwit contributors
