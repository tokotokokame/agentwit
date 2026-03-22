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
[![PyPI](https://img.shields.io/badge/PyPI-v1.0.0-orange.svg)](https://pypi.org/project/agentwit/)
[![Tests](https://img.shields.io/badge/tests-291%20passing-brightgreen.svg)](#)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![OWASP LLM Top 10](https://img.shields.io/badge/OWASP%20LLM-Top%2010%20mapped-red.svg)](docs/api-reference.md#owaspmapper)

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
from agentwit import WitnessLogger
from agentwit.integrations.langchain import AgentwitCallback

logger = WitnessLogger(session_dir="./witness_logs", actor="langchain-agent")
cb = AgentwitCallback(witness_logger=logger)

chain.invoke({"input": "your task"}, config={"callbacks": [cb]})
logger.close()
```

Records agent thoughts (ReAct `Thought:` extraction), tool calls, LLM prompts
and responses. All events written to `audit.jsonl` with 100-char privacy
truncation on LLM content.

---

## OWASP LLM Top 10 mapping

Every detected risk pattern is automatically mapped to the
[OWASP LLM Top 10 (2025)](https://owasp.org/www-project-top-10-for-large-language-model-applications/)
categories:

| Pattern | OWASP ID | Category |
|---|---|---|
| `instruction_override`, `role_hijack`, `jailbreak` | LLM01 | Prompt Injection |
| `credential_access`, `data_exfiltration` | LLM02 | Sensitive Information Disclosure |
| `privilege_escalation`, `persistence`, `lateral_movement` | LLM06 | Excessive Agency |
| `tool_schema_change`, `proxy_bypass_detected` | LLM08 | Vector and Embedding Weaknesses |
| `call_rate_anomaly`, `session_cost_exceeded` | LLM10 | Unbounded Consumption |

HTML reports include a per-category summary card and an OWASP column in the
event timeline.

---

## Plugin ecosystem

Extend agentwit with custom detection rules — no fork required.

```python
# agentwit_myplugin/__init__.py
from agentwit.plugins.base import PluginBase

class MyPlugin(PluginBase):
    @property
    def name(self) -> str:
        return "my-plugin"

    @property
    def version(self) -> str:
        return "1.0.0"

    def scan(self, event: dict) -> list[dict]:
        alerts = []
        if "DROP TABLE" in str(event.get("full_payload", "")):
            alerts.append({
                "pattern": "sql_injection_attempt",
                "severity": "critical",
                "description": "Possible SQL injection in tool input",
            })
        return alerts
```

Register via `pyproject.toml` entry-points and install — the plugin is
auto-discovered at proxy startup:

```toml
[project.entry-points."agentwit.plugins"]
my_plugin = "agentwit_myplugin:MyPlugin"
```

See [docs/plugin-guide.md](docs/plugin-guide.md) for the complete guide.

---

## MCP Inspector GUI

Desktop debugger for MCP servers — three-pane interface with real-time
tool call inspection.

```bash
# Download the latest .deb from the Releases page, then:
sudo dpkg -i mcp-inspector_*.deb
mcp-inspector
```

**Connection:** open the Connection panel → select HTTP or stdio → enter your
MCP server URL or command → click Connect.

**Export Report:** after tool calls appear in the History tab, click the amber
**Export Report** button to save a self-contained HTML audit report.  The
report opens in your browser automatically.

Features: tool list · parameter editor · response viewer · session compare ·
cost tracking · one-click HTML report export

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

## SIEM integration

Forward `audit.jsonl` to Splunk, Elasticsearch, or Grafana Loki:

```bash
# Splunk
export SPLUNK_HEC_TOKEN=your-token
export SPLUNK_HOST=splunk.example.com
docker compose -f docker/docker-compose.siem.yml up -d

# Elasticsearch
export ES_HOST=elasticsearch.example.com
docker compose -f docker/docker-compose.siem.yml up -d

# Grafana Loki (default)
docker compose -f docker/docker-compose.siem.yml up -d
```

All SIEM outputs use Fluent Bit with automatic auth-header masking.
See the [environment variables reference](docs/api-reference.md#environment-variables)
for all available options.

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
| v0.6.0 | Retry/backoff, stdio auto-restart, LangChain audit log, GUI Export Report |
| v0.7.0 | OWASP LLM Top 10 mapping, enriched HTML reports |
| v1.0.0 | Plugin system, SIEM stack, full documentation |

Full history in [CHANGELOG.md](CHANGELOG.md).

---

## Articles
- [Why I built a "witness" for AI agents (Zenn)](https://zenn.dev/tokotokokame/articles/bba6a258a458a1)
- [From Witness to Inspector (Zenn)](https://zenn.dev/tokotokokame/articles/9183dd8a1734e2)

---

## Documentation

| Doc | Contents |
|---|---|
| [docs/quickstart.md](docs/quickstart.md) | Installation, proxy modes, report generation, GUI, Docker |
| [docs/architecture.md](docs/architecture.md) | Design philosophy, component overview, data flow |
| [docs/api-reference.md](docs/api-reference.md) | CLI reference, Python API, log formats, env vars |
| [docs/plugin-guide.md](docs/plugin-guide.md) | Writing, testing, and publishing custom plugins |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Dev setup, test execution, PR process, conventions |

---

## Requirements

- Python 3.10+
- Dependencies auto-installed: FastAPI, uvicorn, httpx, click, cryptography

## License

[MIT](LICENSE) © agentwit contributors
