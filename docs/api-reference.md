# API Reference

## CLI Commands

All commands are available via the `agentwit` executable installed by pip.

```
agentwit [--version] [--help] COMMAND [ARGS]
```

---

### `agentwit proxy`

Start the transparent witness proxy.

```
agentwit proxy [OPTIONS] [CMD]...
```

| Option | Default | Description |
|---|---|---|
| `--target URL` | — | Upstream MCP server URL (HTTP mode, required) |
| `--port INT` | `8765` | Port to listen on (HTTP mode) |
| `--host TEXT` | `127.0.0.1` | Host to bind (HTTP mode) |
| `--log-dir PATH` | `./witness_logs` | Directory for witness log sessions |
| `--actor TEXT` | `agent` | Actor identifier written into every event |
| `--stdio` | `False` | Enable stdio proxy mode |
| `--webhook URL` | — | Webhook URL for HIGH/CRITICAL notifications |
| `--webhook-on TEXT` | `HIGH,CRITICAL` | Comma-separated severity levels |
| `--timeout FLOAT` | `30.0` | HTTP request timeout in seconds |
| `CMD...` | — | Subprocess command (stdio mode only, after `--`) |

**Examples:**

```bash
# HTTP mode
agentwit proxy --target http://localhost:3000 --port 8765

# HTTP mode with Slack notifications
agentwit proxy \
  --target http://localhost:3000 \
  --webhook https://hooks.slack.com/services/T00/B00/xxx \
  --webhook-on HIGH,CRITICAL

# stdio mode
agentwit proxy --stdio -- python my_mcp_server.py
agentwit proxy --stdio -- npx @modelcontextprotocol/server-filesystem /data

# Custom timeout and log directory
agentwit proxy \
  --target http://localhost:3000 \
  --timeout 60 \
  --log-dir /var/log/agentwit
```

---

### `agentwit verify`

Verify SHA-256 chain integrity and ed25519 signatures for a session.

```
agentwit verify --session PATH
```

| Option | Description |
|---|---|
| `--session PATH` | Session directory containing `witness.jsonl` (required) |

**Output:**

```
Session: session_20260101_120000  (47 events)
Key fingerprint: abc123def456...

   #  chain   sig     witness_id
------------------------------------------------------------------------
   0  OK      OK      a1b2c3d4e5f6...
   1  OK      OK      b2c3d4e5f6a1...
  ...
Result: ALL VALID
```

Exit code `0` on success, `1` on any integrity failure.

---

### `agentwit report`

Generate an audit report from a witness log session.

```
agentwit report --session PATH [--format FORMAT] [--output PATH]
```

| Option | Default | Description |
|---|---|---|
| `--session PATH` | — | Session directory (required) |
| `--format FORMAT` | `json` | `json` / `markdown` / `html` |
| `--output PATH` | `-` (stdout) | Output file path |

**Examples:**

```bash
agentwit report --session ./witness_logs/session_xxx --format html -o report.html
agentwit report --session ./witness_logs/session_xxx --format markdown
agentwit report --session ./witness_logs/session_xxx --format json > data.json
```

---

### `agentwit replay`

Replay and display all events from a session.

```
agentwit replay --session PATH [--verify | --no-verify]
```

| Option | Default | Description |
|---|---|---|
| `--session PATH` | — | Session directory (required) |
| `--verify / --no-verify` | `--verify` | Check chain integrity before replaying |

---

### `agentwit diff`

Compare tool call patterns and risk profiles between two sessions.

```
agentwit diff --session-a PATH --session-b PATH
```

| Option | Description |
|---|---|
| `--session-a PATH` | First session directory (required) |
| `--session-b PATH` | Second session directory (required) |

**Output:**

```
Session A: session_001  (23 events)
Session B: session_002  (31 events)

Tools called:
  bash                                    A=5  B=12  !=
  read_file                               A=8  B=8
  fetch                                   A=3  B=0   !=

Risk summary:
  A: total=4  high_risk_events=2
  B: total=9  high_risk_events=5
  Risk profiles differ between sessions.
```

---

## Python API

### `AgentwitCallback`

LangChain callback handler that records all agent/tool/LLM events.

```python
from agentwit import WitnessLogger
from agentwit.integrations.langchain import AgentwitCallback

logger = WitnessLogger(session_dir="./witness_logs", actor="langchain-agent")
cb = AgentwitCallback(witness_logger=logger)

# Pass to any LangChain chain or agent
chain.invoke({"input": "..."}, config={"callbacks": [cb]})
logger.close()
```

**Hooks implemented:**

| Hook | audit.jsonl type | Description |
|---|---|---|
| `on_agent_action` | `agent_thought` | ReAct Thought extraction + tool selected |
| `on_agent_finish` | `agent_finish` | Final answer + thought |
| `on_llm_start` | `llm_start` | First 100 chars of prompt (privacy) |
| `on_llm_end` | `llm_end` | First 100 chars of response (privacy) |
| `on_tool_start` | `tool_start` | Tool name + input |
| `on_tool_end` | `tool_end` | Tool output |
| `on_tool_error` | `tool_error` | Error message |
| `on_chain_start` | `chain_start` | Chain name + inputs |
| `on_chain_end` | `chain_end` | Chain outputs |

**`agent_thought` audit record:**

```json
{
  "type": "agent_thought",
  "thought": "I need to search for the answer",
  "tool_selected": "web_search",
  "reasoning": "query string here",
  "timestamp": "2026-03-22T12:00:00Z",
  "session_id": "session_20260322_120000"
}
```

---

### `OWASPMapper`

Maps internal risk pattern names to OWASP LLM Top 10 (2025) categories.

```python
from agentwit.analyzer.owasp_mapper import OWASPMapper

mapper = OWASPMapper()

# Map a single pattern
mapper.map("privilege_escalation")   # → "LLM06"
mapper.map("unknown_pattern")        # → None

# Get human-readable description
mapper.describe("LLM01")  # → "Prompt Injection"
mapper.describe("LLM99")  # → "Unknown"

# Enrich a list of events
enriched = mapper.map_events(events)
# Each risk_indicator with a known pattern gains:
#   "owasp_category": "LLM06"
#   "owasp_name": "Excessive Agency"

# Summarise OWASP categories across events
counts = mapper.summary(enriched)
# → {"LLM01": 3, "LLM06": 1}
```

**Pattern → OWASP mapping table:**

| Pattern | OWASP ID | Category |
|---|---|---|
| `instruction_override` | LLM01 | Prompt Injection |
| `role_hijack` | LLM01 | Prompt Injection |
| `jailbreak` | LLM01 | Prompt Injection |
| `hidden_instruction` | LLM01 | Prompt Injection |
| `data_extraction` | LLM01 | Prompt Injection |
| `credential_access` | LLM02 | Sensitive Information Disclosure |
| `credential_access_extended` | LLM02 | Sensitive Information Disclosure |
| `data_exfiltration` | LLM02 | Sensitive Information Disclosure |
| `privilege_escalation` | LLM06 | Excessive Agency |
| `persistence` | LLM06 | Excessive Agency |
| `lateral_movement` | LLM06 | Excessive Agency |
| `tool_schema_change` | LLM08 | Vector and Embedding Weaknesses |
| `proxy_bypass_detected` | LLM08 | Vector and Embedding Weaknesses |
| `call_rate_anomaly` | LLM10 | Unbounded Consumption |
| `session_cost_exceeded` | LLM10 | Unbounded Consumption |

---

### `PluginBase`

Abstract base class for custom detection plugins.

```python
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
        payload = event.get("full_payload", {})
        if "DROP TABLE" in str(payload):
            alerts.append({
                "pattern": "sql_injection_attempt",
                "severity": "critical",
                "description": "Possible SQL injection in tool input",
            })
        return alerts
```

See [plugin-guide.md](plugin-guide.md) for the complete guide.

---

### `WitnessLogger`

Core logging class. Usually instantiated by the CLI; available for
programmatic use.

```python
from agentwit.witness.log import WitnessLogger

logger = WitnessLogger(session_dir="./witness_logs", actor="my-agent")

# Synchronous
event = logger.log_event(
    action="tools/call",
    tool="bash",
    full_payload={"params": {...}, "result": {...}},
    risk_indicators=[{"pattern": "shell_exec", "severity": "high"}],
)
print(event["witness_id"])   # sha256 hex
print(event["session_chain"]) # sha256 hex

# Asynchronous
event = await logger.alog_event(action="tools/list", tool=None, full_payload={})

logger.close()
```

---

## `audit.jsonl` Format

The global audit file at `~/.agentwit/audit.jsonl` records high-level
security events from all sessions. Each line is a JSON object.

### `connection_error`

Written when all 3 retry attempts to the upstream server are exhausted.

```json
{
  "type": "connection_error",
  "target": "http://localhost:3000/tools/call",
  "retries": 3,
  "error": "Connect call failed ('127.0.0.1', 3000)",
  "timestamp": "2026-03-22T12:00:00Z"
}
```

### `sse_timeout`

Written when an SSE stream times out after all retries.

```json
{
  "type": "sse_timeout",
  "target": "http://localhost:3000/events",
  "retries": 3,
  "error": "Read timeout",
  "timestamp": "2026-03-22T12:00:00Z"
}
```

### `process_crash`

Written when a stdio subprocess exits non-zero and all restarts fail.

```json
{
  "type": "process_crash",
  "command": ["python", "my_mcp_server.py"],
  "returncode": 1,
  "restarts_attempted": 3,
  "timestamp": "2026-03-22T12:00:00Z"
}
```

### `agent_thought`

Written by `AgentwitCallback.on_agent_action`.

```json
{
  "type": "agent_thought",
  "thought": "I need to look up the current weather",
  "tool_selected": "web_search",
  "reasoning": "weather in Tokyo today",
  "timestamp": "2026-03-22T12:00:00Z",
  "session_id": "session_20260322_120000"
}
```

### `agent_finish`

Written by `AgentwitCallback.on_agent_finish`.

```json
{
  "type": "agent_finish",
  "final_answer": "The weather in Tokyo is 18°C and sunny.",
  "thought": "I have all the information needed.",
  "timestamp": "2026-03-22T12:00:00Z",
  "session_id": "session_20260322_120000"
}
```

### `llm_start` / `llm_end`

```json
{ "type": "llm_start", "prompt_preview": "You are a helpful assistant. The user asks: ...", "timestamp": "...", "session_id": "..." }
{ "type": "llm_end",   "response_preview": "The answer to your question is...", "timestamp": "...", "session_id": "..." }
```

---

## `witness.jsonl` Event Format

Each line in a session's `witness.jsonl` is a signed, chained event.

```json
{
  "timestamp":       "2026-03-22T12:00:01.234567+00:00",
  "actor":           "agent",
  "action":          "tools/call",
  "tool":            "bash",
  "input_hash":      "sha256 hex of params dict",
  "output_hash":     "sha256 hex of result dict",
  "full_payload": {
    "params":  { "name": "bash", "arguments": { "command": "ls" } },
    "result":  { "content": "file1.txt\nfile2.txt" }
  },
  "risk_indicators": [
    {
      "pattern":        "shell_exec",
      "severity":       "high",
      "matched":        "bash",
      "owasp_category": "LLM06",
      "owasp_name":     "Excessive Agency"
    }
  ],
  "witness_id":     "sha256 hex (event identity hash)",
  "session_chain":  "sha256 hex (cumulative chain hash)",
  "signature":      "base64url-encoded ed25519 signature",
  "signed_by":      "ed25519 public key fingerprint (hex)"
}
```

**Field descriptions:**

| Field | Type | Description |
|---|---|---|
| `timestamp` | ISO-8601 | UTC time when the event was recorded |
| `actor` | string | Identifier set via `--actor` |
| `action` | string | MCP method (`tools/call`) or HTTP verb |
| `tool` | string\|null | Tool name from `params.name` |
| `input_hash` | hex | SHA-256 of canonical JSON of request params |
| `output_hash` | hex | SHA-256 of canonical JSON of response result |
| `full_payload` | object | Complete request + response |
| `risk_indicators` | array | Detected risk patterns (may be empty) |
| `witness_id` | hex | SHA-256 of the event (without chain fields) |
| `session_chain` | hex | Cumulative chain hash (links to previous event) |
| `signature` | base64 | ed25519 signature over the canonical JSON |
| `signed_by` | hex | Fingerprint of the signing public key |

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `AGENTWIT_LOG_PATH` | `~/.agentwit/audit.jsonl` | Path to global audit log (Docker / Fluent Bit) |
| `SPLUNK_HOST` | `splunk-server` | Splunk HEC hostname (SIEM stack) |
| `SPLUNK_PORT` | `8088` | Splunk HEC port |
| `SPLUNK_HEC_TOKEN` | — | Splunk HTTP Event Collector token (required for Splunk output) |
| `ES_HOST` | `elasticsearch` | Elasticsearch hostname |
| `ES_PORT` | `9200` | Elasticsearch port |
| `LOKI_HOST` | `localhost` | Grafana Loki hostname |
| `LOKI_PORT` | `3100` | Grafana Loki port |
| `TARGET_URL` | — | Upstream MCP server URL (Docker Compose) |
| `WEBHOOK_URL` | — | Webhook notification URL (Docker Compose) |
| `HOME` / `USERPROFILE` | — | Used to locate `~/.agentwit/` (auto-detected) |
| `HOSTNAME` | — | Injected as `host` label in Fluent Bit records |
