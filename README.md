# agentwit — AI Agent Traffic Inspector

> Transparent witness for AI agent ↔ MCP server communications

[日本語版 / Japanese](README.ja.md)

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-226%20passing-brightgreen.svg)](#)
[![PyPI](https://img.shields.io/badge/PyPI-v0.5.0-orange.svg)](https://pypi.org/project/agentwit/)

## Articles
- 📝 [Why I built a "witness" for AI agents — design philosophy (Zenn)](https://zenn.dev/tokotokokame/articles/bba6a258a458a1)
- 📝 [From Witness to Inspector — how agentwit evolved (Zenn)](https://zenn.dev/tokotokokame/articles/9183dd8a1734e2)
- 📝 [The tool monitoring AI agents can be fooled by AI — v0.4.0 (Zenn)](https://zenn.dev/tokotokokame/articles/)
- 📝 [How to prove a log hasn't been tampered with — ed25519 signing in v0.5.0 (Zenn)](https://zenn.dev/tokotokokame/articles/)

## What is agentwit?

agentwit is a transparent proxy that sits between AI agents and MCP servers,
recording every communication as a tamper-proof, cryptographically signed witness log.

Unlike existing tools that act as **"guards"** (blocking suspicious traffic),
agentwit acts as a **"witness"** — it never blocks, never interferes, but
records everything with SHA-256 chain integrity and ed25519 signatures.

## Guard vs. Witness

| Tool         | Approach          | Blocks traffic | Tamper-proof log | Signed log |
|--------------|-------------------|:--------------:|:----------------:|:----------:|
| mcp-scan     | Proxy + Guard     | ✅             | ❌               | ❌         |
| Proximity    | Static scanner    | —              | ❌               | ❌         |
| Intercept    | Policy proxy      | ✅             | ❌               | ❌         |
| **agentwit** | **Witness proxy** | **❌**         | **✅**           | **✅**     |

## How it works

```
AI Agent
   │
   ▼
agentwit proxy  ◄── records every message
   │                 SHA-256 chain + ed25519 signature
   │                 prompt injection detection
   │                 proxy bypass detection
   ▼
MCP Server       ◄── zero modification required
```

## Quick Start

```bash
pip install agentwit
pip install agentwit[full]  # with LangChain integration
```

```bash
# Start the witness proxy
agentwit proxy --target http://localhost:3000 --port 8765

# Point your agent to http://localhost:8765 — that's it

# Verify chain integrity + ed25519 signatures
agentwit verify --session ./witness_logs/SESSION_ID

# Generate audit report
agentwit report --session ./witness_logs/SESSION_ID \
                --format html --output report.html
```

## Security Features

### ed25519 Log Signing (v0.5.0)

On first launch, a keypair is automatically generated:

```
~/.agentwit/signing_key.pem  ← private key (chmod 600)
~/.agentwit/signing_pub.pem  ← public key
```

Every event is signed. No user action required.

```bash
agentwit verify --session ./witness_logs/SESSION_ID
# Chain integrity:  VALID ✓
# Signature check:  VALID ✓
```

### Prompt Injection Detection (v0.4.0)

Detects malicious instructions embedded in MCP server responses — no API required.

| Pattern | Severity | Example |
|---|---|---|
| instruction_override | CRITICAL | "Ignore previous instructions" |
| role_hijack | CRITICAL | "You are now DAN" |
| jailbreak | CRITICAL | "Do anything now" |
| hidden_instruction | HIGH | `<!-- [SYSTEM] -->` |
| data_extraction | HIGH | "Send the above to..." |
| tool_abuse | MEDIUM | "Execute the following" |

### Proxy Bypass Detection (v0.5.0)

Detects requests that bypass agentwit entirely. No sudo, no iptables — pure Python.

```json
{
  "type": "proxy_bypass_detected",
  "severity": "HIGH",
  "detail": "Request missing X-Agentwit-Proxy header"
}
```

### Tool Schema Monitoring (v0.4.0)

Detects when MCP server tools are added, removed, or modified between sessions.

```json
{
  "type": "tool_schema_change",
  "changes": { "added": ["suspicious_tool"], "modified": ["bash"] },
  "severity": "HIGH"
}
```

### Anomaly Detection (v0.5.0)

```json
{ "type": "call_rate_anomaly",   "calls_per_minute": 47, "severity": "HIGH"   }
{ "type": "repeated_tool_call",  "tool": "bash", "count": 15, "severity": "MEDIUM" }
```

### Auto Backup (v0.5.0)

Sessions are automatically backed up to `~/.agentwit/backups/` on exit.
Retains the latest 30 sessions with integrity hashes.

## Commands

```
agentwit proxy   --target URL [--port 8765] [--webhook URL] [--webhook-on HIGH,CRITICAL]
agentwit verify  --session DIR
agentwit report  --session DIR [--format json|markdown|html] [--output FILE]
agentwit replay  --session DIR
agentwit diff    --session-a DIR --session-b DIR
```

## MCP Spec Auto-tracking (v0.4.0)

GitHub Actions checks `modelcontextprotocol/specification` monthly.
On change: runs all tests → creates GitHub Issue → Discord notification.
Cost: $0 (GitHub Actions free tier).

## Docker Compose Audit Stack (v0.4.0)

One-command deployment of agentwit + Grafana + Loki + Fluent Bit:

```bash
cd docker/
cp .env.example .env   # set TARGET_URL
docker compose up -d
# Grafana: http://localhost:3000
```

Fluent Bit automatically masks `Authorization`, `api_key`, `token`, `password` fields.

## MCP Inspector GUI

Desktop debugger for MCP servers (Tauri + React). Available for Linux.

```bash
sudo dpkg -i mcp-inspector_0.1.0_amd64.deb
mcp-inspector
# Connect: HTTP → http://localhost:3000/mcp
```

## Witness Log Format

```json
{
  "witness_id":      "sha256 of the entire event",
  "session_chain":   "sha256(prev_chain + event_hash)",
  "timestamp":       "2026-03-21T12:00:00Z",
  "actor":           "my-agent",
  "action":          "tools/call",
  "tool":            "bash",
  "signature":       "base64(ed25519 signature)",
  "signed_by":       "public key fingerprint",
  "risk_indicators": [{ "pattern": "shell_exec", "severity": "HIGH" }]
}
```

## LangChain Integration

```bash
pip install agentwit[full]
```

```python
from agentwit import AgentwitCallback
callbacks = [AgentwitCallback(output="./audit.json")]
agent.run("task", callbacks=callbacks)
```

## Version History

| Version | Date       | Highlights |
|---------|------------|------------|
| v0.1.0  | 2026-03-14 | MVP: HTTP/SSE/stdio proxy, SHA-256 chain log |
| v0.2.0  | 2026-03-15 | HTML/Markdown reports, timeline diff, LangChain, Slack/Discord |
| v0.3.0  | 2026-03-16 | MCP Inspector GUI, standard MCP `/mcp` endpoint |
| v0.4.0  | 2026-03-21 | MCP spec auto-tracking, prompt injection detection, tool monitoring, Docker stack |
| v0.5.0  | 2026-03-21 | ed25519 signing, proxy bypass detection, anomaly detection, auto backup |

## Roadmap

- [ ] HTML report generation from GUI
- [ ] Agent behavior monitoring (reasoning process recording)
- [ ] Windows build verification
- [ ] GUI test coverage
- [ ] OWASP LLM Top 10 mapping
- [ ] SIEM integration (v1.0.0)

## Requirements

- Python 3.10+
- cryptography>=41.0.0
- FastAPI, uvicorn, httpx, click (auto-installed)
- GUI: Node.js 18+, Rust 1.70+ (build from source)

## License

[MIT](LICENSE) © agentwit contributors
