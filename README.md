# agentwit

> Transparent witness for AI agent ↔ MCP server communications

[日本語版 / Japanese](README.ja.md)

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-48%20passing-brightgreen.svg)](#)

## What is agentwit?

agentwit is a transparent proxy that sits between AI agents and MCP servers,
recording every communication as a tamper-proof witness log.

Unlike existing tools that act as **"guards"** (blocking suspicious traffic),
agentwit acts as a **"witness"** — it never blocks, never interferes, but
records everything with cryptographic chain integrity.

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
      │
      ▼
     ...
```

Any single-byte modification to any event breaks the entire chain from
that point forward — making tampering immediately detectable.

## Quick Start

### Installation

```bash
pip install agentwit
```

### 1. Start the witness proxy

```bash
agentwit proxy --target http://localhost:3000 --port 8765
# Starting agentwit proxy → http://localhost:3000
# Listening on 127.0.0.1:8765
# Session: ./witness_logs/session_20260314_120000
```

### 2. Point your agent to the proxy

```bash
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

Events are appended to a JSONL file as they arrive — the proxy never
buffers or delays the upstream response.

## Tamper Detection

Modify any field in the log and agentwit detects it immediately:

```bash
# Simulate tampering: change "actor" in event[0]
python3 -c "
import json; lines=open('witness.jsonl').readlines()
e=json.loads(lines[0]); e['actor']='ATTACKER'
lines[0]=json.dumps(e)+'\n'; open('witness.jsonl','w').writelines(lines)
"

agentwit replay --session ./witness_logs/session_20260314_120000
# Session: session_20260314_120000  (6 events)
# Chain integrity: TAMPERED
#   [event 0] FAIL - session_chain mismatch:
#     expected '0fd4d24bcb3dab7d171e…'
#     got      'a79a9e4cdb19795a521e…'
```

## Use Cases

- **Security engineers** auditing AI agent behavior in production
- **Enterprise teams** requiring AI activity compliance logs
- **AI researchers** reproducibly comparing agent sessions
- **Penetration testers** documenting MCP tool usage as evidence

## Python API

```python
from agentwit import WitnessLogger, ChainManager

# Direct logging (no proxy needed)
logger = WitnessLogger(session_dir="./logs", actor="my-agent")
event = logger.log_event(
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

## Requirements

- Python 3.10+
- FastAPI, uvicorn, httpx, click (installed automatically)

## License

[MIT](LICENSE) © agentwit contributors
