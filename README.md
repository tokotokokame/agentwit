# agentwit

> Transparent witness for AI agent ↔ MCP server communications

[日本語版 / Japanese](README.ja.md)

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-132%20passing-brightgreen.svg)](#)
[![PyPI](https://img.shields.io/badge/PyPI-v0.3.0-orange.svg)](https://pypi.org/project/agentwit/)

## Articles
- 📝 [Why I built a "witness" for AI agents — design philosophy (Zenn)](https://zenn.dev/tokotokokame/articles/bba6a258a458a1)
- 📝 [Practical guide: audit an MCP server in 5 minutes (Zenn)](https://zenn.dev/tokotokokame/articles/)
- 📝 [From Witness to Inspector — how agentwit evolved (Zenn)](https://zenn.dev/tokotokokame/articles/)

## What is agentwit?

agentwit is a transparent proxy that sits between AI agents and MCP servers,
recording every communication as a tamper-proof witness log.

Unlike existing tools that act as **"guards"** (blocking suspicious traffic),
agentwit acts as a **"witness"** — it never blocks, never interferes, but
records everything with cryptographic chain integrity.

**v0.3.0 adds MCP Inspector** — a desktop GUI for debugging MCP servers
in real time, with audit logs unified with the CLI proxy.

## Guard vs. Witness

| Tool         | Approach          | Blocks traffic | Tamper-proof log |
|--------------|-------------------|:--------------:|:----------------:|
| mcp-scan     | Proxy + Guard     | ✅             | ❌               |
| Proximity    | Static scanner    | —              | ❌               |
| Intercept    | Policy proxy      | ✅             | ❌               |
| **agentwit** | **Witness proxy** | **❌**         | **✅**           |

## How it works

```
AI Agent
   │
   ▼
agentwit proxy  ◄── records every message with chain hash
   │                 never blocks, fully transparent
   ▼
MCP Server       ◄── zero modification required
```

Each recorded event is chained to the previous one via SHA-256:

```
genesis_hash = sha256("genesis:" + session_id)
      │
      ▼
event_1:  session_chain = sha256(genesis_hash  +  hash(event_1))
      │
      ▼
event_2:  session_chain = sha256(event_1_chain +  hash(event_2))
```

Any single-byte modification breaks the chain from that point forward —
making tampering immediately detectable.

## Quick Start

### Installation

```bash
pip install agentwit
pip install agentwit[full]  # with LangChain integration
```

### 1. Start the witness proxy

```bash
agentwit proxy --target http://localhost:3000 --port 8765
# Starting agentwit proxy → http://localhost:3000
# Listening on 127.0.0.1:8765
# Session: ./witness_logs/session_20260314_120000
```

### 2. Point your agent to the proxy

```
# Before: http://localhost:3000
# After:  http://localhost:8765
# That's it. No other changes needed.
```

### 3. Generate an audit report

```bash
agentwit report --session ./witness_logs/session_20260314_120000 \
                --format html --output report.html
```

### 4. Verify chain integrity

```bash
agentwit replay --session ./witness_logs/session_20260314_120000
# Session: session_20260314_120000  (6 events)
# Chain integrity: VALID
```

## MCP Inspector GUI (v0.3.0)

A desktop debugger for MCP servers. Built with Tauri + React.

```
Left panel   — server info + tool list (READ/WRITE/EXEC tags)
Center panel — parameter editor + JSON response viewer
Right panel  — History / Metrics / Compare tabs
```

### Launch

```bash
# From .deb package (Linux)
sudo dpkg -i mcp-inspector_0.1.0_amd64.deb
mcp-inspector

# From source
cd gui && npm install && npx tauri dev
```

### Connect to an MCP server

```
Transport: HTTP
URL: http://localhost:3000/mcp
```

For a remote server over SSH:

```bash
ssh -fNL 3000:localhost:3000 your-server
# then connect to http://localhost:3000/mcp
```

### Audit log integration

Enable **"agentwit audit"** in the GUI header — all executions are
written to `~/.agentwit/audit.jsonl` in the same format as the CLI proxy.

```
Development (GUI)  ─┐
                     ├→ same audit.jsonl → agentwit report
Production (proxy) ─┘
```

### MCP Inspector vs. existing tools

| Feature              | Anthropic CLI | Postman | agentwit Inspector |
|----------------------|:-------------:|:-------:|:------------------:|
| GUI                  | ❌            | ✅      | ✅                 |
| MCP-native           | ✅            | ❌      | ✅                 |
| stdio support        | ✅            | ❌      | ✅                 |
| audit log            | ❌            | ❌      | **✅**             |
| cost tracking        | ❌            | ❌      | **✅**             |
| session compare      | ❌            | limited | **✅**             |
| local / offline      | ✅            | ✅      | ✅                 |

## Commands

```
agentwit proxy   --target URL [--port 8765] [--log-dir ./witness_logs] [--actor NAME]
agentwit report  --session DIR [--format json|markdown|html] [--output FILE]
agentwit replay  --session DIR [--verify/--no-verify]
agentwit diff    --session-a DIR --session-b DIR
```

| Command   | Description                                    |
|-----------|------------------------------------------------|
| `proxy`   | Start the transparent witness proxy            |
| `report`  | Generate audit report (json / markdown / html) |
| `replay`  | Replay and verify chain integrity of a session |
| `diff`    | Compare two sessions side by side              |

### Webhook notifications

```bash
agentwit proxy --target http://localhost:3000 --port 8765 \
  --webhook https://hooks.slack.com/services/xxx \
  --webhook-on HIGH,CRITICAL
```

Slack and Discord are both supported (auto-detected from URL format).

### stdio transport

```bash
agentwit proxy --stdio -- python my_mcp_server.py
```

## Witness Log Format

Each intercepted event is stored as one JSON line in `witness.jsonl`:

```json
{
  "witness_id":      "sha256 of the entire signed event",
  "session_chain":   "sha256(prev_chain_hash + event_hash)",
  "timestamp":       "2026-03-14T12:18:53.708937+00:00",
  "actor":           "demo-agent",
  "action":          "tools/call",
  "tool":            "bash",
  "input_hash":      "sha256 of the input payload",
  "output_hash":     "sha256 of the output payload",
  "full_payload":    { "params": {}, "result": {} },
  "risk_indicators": [
    { "pattern": "shell_exec", "severity": "high", "matched": "bash" }
  ]
}
```

## Tamper Detection

```bash
# Simulate tampering: change "actor" in event[0]
python3 -c "
import json; lines=open('witness.jsonl').readlines()
e=json.loads(lines[0]); e['actor']='ATTACKER'
lines[0]=json.dumps(e)+'\n'; open('witness.jsonl','w').writelines(lines)
"

agentwit replay --session ./witness_logs/session_20260314_120000
# Chain integrity: TAMPERED
#   [event 0] FAIL - session_chain mismatch:
#     expected '0fd4d24bcb3dab7d171e…'
#     got      'a79a9e4cdb19795a521e…'
```

## LangChain Integration

```bash
pip install agentwit[full]
```

```python
from agentwit import AgentwitCallback

callbacks = [AgentwitCallback(output="./audit.json")]

agent.run("your task", callbacks=callbacks)
```

## Python API

```python
from agentwit import WitnessLogger, ChainManager

# Direct logging (no proxy needed)
logger = WitnessLogger(session_dir="./logs", actor="my-agent")
logger.log_event(
    action="tools/call",
    tool="bash",
    full_payload={"params": {"command": "ls"}, "result": {"stdout": "..."}}
)
logger.close()

# Verify a recorded session
chain = ChainManager(session_id="session_20260314_120000")
results = chain.verify_chain(events)
all_valid = all(r["valid"] for r in results)
```

## Version History

| Version | Date       | Highlights                                          |
|---------|------------|-----------------------------------------------------|
| v0.1.0  | 2026-03-14 | MVP: HTTP/SSE/stdio proxy, tamper-proof witness log |
| v0.2.0  | 2026-03-15 | HTML/Markdown reports, timeline diff, LangChain, Slack/Discord |
| v0.3.0  | 2026-03-16 | MCP Inspector GUI, unified audit log, standard MCP `/mcp` endpoint |

## Use Cases

- **Security engineers** — audit AI agent behavior with tamper-proof evidence
- **Enterprise teams** — compliance logs for AI activity
- **AI researchers** — reproducibly compare agent sessions
- **Penetration testers** — document MCP tool usage as forensic evidence
- **MCP developers** — debug servers with a GUI before deploying

## Roadmap

- [ ] MCP spec auto-tracking (monthly change detection + automated tests)
- [ ] HTML report generation from GUI
- [ ] stdio transport live testing
- [ ] Windows build verification
- [ ] GUI test coverage (Rust + React components)
- [ ] Auto-reconnect on connection drop
- [ ] OWASP LLM Top 10 mapping

## Requirements

- Python 3.10+
- FastAPI, uvicorn, httpx, click (installed automatically)
- GUI: Node.js 18+, Rust 1.70+ (for building from source)

## License

[MIT](LICENSE) © agentwit contributors
