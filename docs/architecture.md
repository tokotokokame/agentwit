# Architecture

## Design Philosophy: Guard vs. Witness

Most security tools in the AI agent ecosystem are **guards** — they intercept
traffic, evaluate it against a policy, and either allow or block it.

agentwit is a **witness**.

| Property | Guard | Witness (agentwit) |
|---|---|---|
| Blocks traffic | Yes | **Never** |
| Modifies responses | Sometimes | **Never** |
| Single point of failure | Yes | No |
| Audit trail | Optional | **Always** |
| Tamper-evident log | Rarely | **Always** |
| Signed evidence | Rarely | **Always** |
| Introduces latency | Yes (policy eval) | Sub-millisecond |

### Why Not Block?

Blocking proxies introduce two fundamental problems:

1. **False positives cause outages.** If the guard mis-classifies a legitimate
   tool call as malicious, the agent's task fails silently. Debugging is hard
   because the guard was in the way.

2. **Bypassability.** A sophisticated attacker (or a prompt-injected agent)
   that knows a guard is present will attempt to find an unmonitored path.
   A witness that never blocks cannot be "bypassed" in the same sense — it
   just keeps watching.

agentwit's philosophy: **record everything faithfully, detect anomalies
accurately, and let humans decide what to do next.** The tamper-evident log
is the source of truth for incident response, compliance audits, and forensic
analysis.

---

## Component Overview

```
┌─────────────────────────────────────────────────────────────┐
│                        AI Agent                              │
└───────────────────────────┬─────────────────────────────────┘
                            │  JSON-RPC (HTTP / SSE / stdio)
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                     agentwit Proxy                           │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │ BypassDetect │  │  RiskScorer  │  │  Plugin System   │  │
│  │              │  │              │  │  (entry-points)  │  │
│  │ Detects      │  │ 15 built-in  │  │  load_plugins()  │  │
│  │ proxy-bypass │  │ patterns     │  │  scan() per req  │  │
│  └──────┬───────┘  └──────┬───────┘  └────────┬─────────┘  │
│         └─────────────────┴──────────────┬─────┘            │
│                                           │ risk_indicators  │
│                          ┌────────────────▼───────────────┐ │
│                          │      WitnessLogger             │ │
│                          │                                │ │
│                          │  log_event() / alog_event()    │ │
│                          │  ChainManager (SHA-256 chain)  │ │
│                          │  EventSigner  (ed25519)        │ │
│                          └────────────────┬───────────────┘ │
│                                           │                  │
│                          ┌────────────────▼───────────────┐ │
│                          │   witness.jsonl  (per session) │ │
│                          │   audit.jsonl    (global)      │ │
│                          └────────────────────────────────┘ │
└───────────────────────────┬─────────────────────────────────┘
                            │  (identical request, no changes)
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                     MCP Server                               │
│              (unmodified, unaware of proxy)                  │
└─────────────────────────────────────────────────────────────┘
```

---

## Witness Log Chain Structure

Every event appended to `witness.jsonl` is cryptographically chained to the
previous event. This makes post-hoc modification detectable.

```
Session start
     │
     ▼
┌────────────────────────────────────────────────────────┐
│  Event 0                                               │
│  ─────────────────────────────────────────────────     │
│  timestamp:      2026-03-01T12:00:00Z                  │
│  action:         tools/list                            │
│  tool:           null                                  │
│  full_payload:   { ... }                               │
│  input_hash:     sha256(params)                        │
│  output_hash:    sha256(result)                        │
│  risk_indicators: []                                   │
│  ─────────────────────────────────────────────────     │
│  event_hash:     sha256(all above fields, sorted)      │
│  session_chain:  sha256(genesis_hash + event_hash)  ◄──┼── genesis = sha256("genesis:<session_id>")
│  witness_id:     sha256(event without chain fields)    │
│  signature:      ed25519_sign(event)                   │
└────────────────────────┬───────────────────────────────┘
                         │  prev_chain_hash = session_chain[0]
                         ▼
┌────────────────────────────────────────────────────────┐
│  Event 1                                               │
│  ─────────────────────────────────────────────────     │
│  timestamp:      2026-03-01T12:00:01Z                  │
│  action:         tools/call                            │
│  tool:           bash                                  │
│  risk_indicators: [{pattern: shell_exec, sev: HIGH}]   │
│  ─────────────────────────────────────────────────     │
│  event_hash:     sha256(all above fields, sorted)      │
│  session_chain:  sha256(prev_chain + event_hash)    ◄──┼── chains to Event 0
│  witness_id:     sha256(event without chain fields)    │
│  signature:      ed25519_sign(event)                   │
└────────────────────────┬───────────────────────────────┘
                         │
                         ▼
                       ...
```

**Verification:** `agentwit verify` recomputes every `session_chain` hash
from scratch and checks it against the stored value.  It also re-verifies
each `ed25519` signature.  A single tampered byte in any event breaks the
chain at that point and all subsequent events.

---

## Component Responsibilities

### `agentwit.proxy.http_proxy` — HTTP Proxy

- Accepts all HTTP methods on a configurable port.
- Builds forwarded requests with `X-Agentwit-Proxy` header injected.
- Detects proxy bypass attempts (missing proxy header).
- Retries failed upstream connections up to 3 times (1 s → 2 s → 4 s
  exponential backoff) before returning HTTP 502.
- Streams SSE responses without buffering.
- Calls all loaded plugins via `scan()` for each request/response pair.
- Logs every event to `WitnessLogger`.

### `agentwit.proxy.stdio_proxy` — stdio Proxy

- Spawns the MCP server as a child process.
- Intercepts newline-delimited JSON-RPC on stdin/stdout.
- Forwards in both directions with minimal latency.
- Auto-restarts the subprocess (up to 3 times, 1 s delay) on non-zero exit.
- Writes `process_crash` to `audit.jsonl` after exhausting restarts.

### `agentwit.proxy.sse_proxy` — SSE Proxy

- Connects to an upstream SSE endpoint.
- Parses `data:` lines and logs each event to `WitnessLogger`.
- Retries on `httpx.TimeoutException` (up to 3 times, 30 s default timeout).
- Writes `sse_timeout` to `audit.jsonl` after exhausting retries.

### `agentwit.witness.log` — WitnessLogger

- Thread-safe append-only JSONL writer.
- Builds the unsigned event dict (`_build_event`).
- Calls `ChainManager.sign()` to add `witness_id` and `session_chain`.
- Calls `EventSigner.sign()` to add `signature` and `signed_by`.
- Flushes on every write.

### `agentwit.witness.chain` — ChainManager

- Maintains `_prev_chain_hash` across the session lifetime.
- `sign(event)` → adds `witness_id` and `session_chain`, advances the chain.
- `verify_chain(events)` → stateless re-verification, returns per-event
  results without mutating the manager's state.

### `agentwit.security.signing` — EventSigner

- Generates (or loads from `~/.agentwit/signing_key.pem`) an ed25519 key pair.
- `sign(event)` → base64-encoded signature of the canonical JSON.
- `verify(event, sig)` → boolean integrity check.
- `fingerprint()` → short hex ID of the public key.

### `agentwit.security.bypass_detector` — BypassDetector

- `check_request(headers)` → detects requests that bypassed the proxy
  (missing `X-Agentwit-Proxy` header on non-first-hop requests).
- `inject_header(headers)` → stamps outgoing requests with the proxy marker.

### `agentwit.analyzer.scorer` — RiskScorer

- 15 built-in detection patterns (regex + keyword matching).
- Returns a list of `{pattern, severity, matched}` dicts.
- Severities: `low` / `medium` / `high` / `critical`.

### `agentwit.analyzer.owasp_mapper` — OWASPMapper

- Maps internal pattern names to OWASP LLM Top 10 (2025) category IDs.
- Enriches event lists with `owasp_category` and `owasp_name` fields.
- Produces summary counts per OWASP category.

### `agentwit.plugins` — Plugin System

- `load_plugins()` discovers third-party plugins via
  `importlib.metadata.entry_points(group="agentwit.plugins")`.
- Each plugin implements `PluginBase.scan(event) → list[dict]`.
- Plugin alerts are merged into `risk_indicators` before logging.

### `agentwit.monitor.cost_guard` — CostGuard / AnomalyDetector

- Tracks per-tool call rates.
- Emits `call_rate_anomaly` when >30 calls/min to the same tool.
- Tracks session token cost and emits `session_cost_exceeded`.

### `agentwit.reporter` — Report Generators

- `HtmlReporter` → self-contained HTML with dark theme, risk grid, OWASP
  summary, and event timeline.
- `MarkdownReporter` → plain Markdown suitable for GitHub issues.
- `JsonReporter` → machine-readable structured output.

### `agentwit.integrations.langchain` — AgentwitCallback

- LangChain `BaseCallbackHandler` subclass.
- Hooks into `on_agent_action`, `on_agent_finish`, `on_llm_start`,
  `on_llm_end`, `on_tool_start`, `on_tool_end`, `on_chain_start/end`.
- Extracts ReAct-format `Thought:` lines from agent logs.
- Writes structured `agent_thought` / `agent_finish` / `llm_start` /
  `llm_end` records to `audit.jsonl`.
- Truncates LLM prompt/response previews to 100 chars (privacy).

---

## Data Flow

### HTTP Request/Response Flow

```
AI Agent
   │
   │  POST /tools/call  {"method":"tools/call","params":{"name":"bash",...}}
   ▼
agentwit HTTP Proxy
   │
   ├─ 1. BypassDetector.check_request(headers)
   │       └─ if bypass detected → write to audit.jsonl, optionally webhook
   │
   ├─ 2. inject proxy header into forward_headers
   │
   ├─ 3. parse JSON body → identify action="tools/call", tool="bash"
   │
   ├─ 4. send upstream with retry (max 3, backoff 1/2/4 s)
   │       └─ on total failure → write connection_error to audit.jsonl, 502
   │
   ├─ 5. receive upstream response
   │
   ├─ 6. _run_plugins(event_snapshot) → plugin_alerts[]
   │
   ├─ 7. WitnessLogger.alog_event(
   │         action, tool, full_payload,
   │         risk_indicators = scorer.score() + plugin_alerts
   │       )
   │       ├─ ChainManager.sign(event)   → witness_id, session_chain
   │       └─ EventSigner.sign(event)    → signature, signed_by
   │
   └─ 8. return response to AI Agent (identical to upstream)
```

### stdio Flow

```
AI Agent stdin
   │
   ├─ readline() → forward to subprocess stdin
   │                    └─ _log_message(line, "request")
   │                          └─ RiskScorer.score_event()
   │                          └─ WitnessLogger.alog_event()
   │
   └─ (loop)

Subprocess stdout
   │
   ├─ readline() → write to our stdout
   │                    └─ _log_message(line, "response")
   │                          └─ WitnessLogger.alog_event()
   │
   └─ (loop)
```

---

## File Layout

```
~/.agentwit/
├── audit.jsonl          # global security events (bypass, crash, timeout)
├── signing_key.pem      # ed25519 private key (auto-generated)
└── backups/             # auto-backups of completed sessions

./witness_logs/
└── session_20260101_120000/
    └── witness.jsonl    # tamper-evident event chain for this session
```

---

## Security Properties

| Property | Mechanism |
|---|---|
| Tamper detection | SHA-256 chain (like Git tree hash) |
| Origin proof | ed25519 signature on every event |
| Bypass detection | `X-Agentwit-Proxy` header round-trip check |
| Privacy | LLM prompt/response truncated to 100 chars in audit |
| Sensitive field masking | Fluent Bit `record_modifier` removes auth headers |
