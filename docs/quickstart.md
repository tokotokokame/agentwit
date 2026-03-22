# Quickstart Guide

Get agentwit recording AI agent tool calls in under 30 seconds.

---

## Installation

```bash
pip install agentwit
```

To include LangChain callback integration:

```bash
pip install agentwit[full]
```

**Requirements:** Python 3.10 or later. All runtime dependencies (FastAPI,
uvicorn, httpx, click, cryptography) are installed automatically.

---

## 30-Second Audit Start

```bash
# 1. Install
pip install agentwit

# 2. Start the proxy (replace 3000 with your MCP server port)
agentwit proxy --target http://localhost:3000 --port 8765

# 3. Point your AI agent to port 8765 instead of 3000
#    No changes to the MCP server needed. That's it.

# Output you'll see:
# [agentwit] 14:32:01  tools/call  bash       HIGH ⚠  shell_exec
# [agentwit] 14:32:03  tools/call  read_file  LOW  ✓
# [agentwit] 14:32:05  tools/call  bash       CRITICAL 🚨 privilege_escalation
```

Witness logs are written to `./witness_logs/` in the current directory.

---

## Proxy Modes

agentwit supports three transport modes matching the three MCP transport types.

### HTTP / Streamable HTTP Mode

For MCP servers that communicate over HTTP or HTTP+SSE:

```bash
agentwit proxy \
  --target http://localhost:3000 \
  --port 8765 \
  --host 127.0.0.1 \
  --log-dir ./witness_logs \
  --actor my-agent
```

All HTTP methods (GET, POST, PUT, PATCH, DELETE) are forwarded transparently.
SSE streams are proxied without buffering — every chunk is forwarded
immediately while the complete stream is recorded after it closes.

**With webhook notifications on high-risk events:**

```bash
agentwit proxy \
  --target http://localhost:3000 \
  --port 8765 \
  --webhook https://hooks.slack.com/services/xxx \
  --webhook-on HIGH,CRITICAL
```

**With custom request timeout:**

```bash
agentwit proxy --target http://localhost:3000 --timeout 60
```

### SSE Mode (Server-Sent Events)

SSE transport is handled automatically when the upstream server returns a
`text/event-stream` content type. No special flag is required — the proxy
detects SSE responses and streams them back to the client while recording
the full event sequence.

### stdio Mode

For MCP servers that use stdin/stdout (the most common transport for local
servers):

```bash
# Wrap any stdio MCP server:
agentwit proxy --stdio -- python my_mcp_server.py

# With arguments to the subprocess:
agentwit proxy --stdio -- npx @modelcontextprotocol/server-filesystem /data

# The proxy intercepts every JSON-RPC line in both directions.
```

In stdio mode agentwit:
1. Spawns the MCP server as a subprocess.
2. Reads every newline-delimited JSON-RPC message from your stdin and
   forwards it to the subprocess stdin.
3. Reads every response from the subprocess stdout and forwards it to your
   stdout.
4. Logs both directions with risk scoring.
5. Auto-restarts the subprocess (up to 3 times) if it exits with a non-zero
   return code.

---

## Report Generation

After a session ends, generate an audit report in HTML, Markdown, or JSON:

```bash
# HTML report (opens in browser, recommended)
agentwit report \
  --session ./witness_logs/session_20260101_120000 \
  --format html \
  --output ./report.html

# Markdown report
agentwit report \
  --session ./witness_logs/session_20260101_120000 \
  --format markdown \
  --output ./report.md

# JSON report (machine-readable)
agentwit report \
  --session ./witness_logs/session_20260101_120000 \
  --format json \
  --output ./report.json

# Print to stdout
agentwit report \
  --session ./witness_logs/session_20260101_120000 \
  --format json
```

The HTML report includes:
- Session metadata (actor, duration, total events)
- Risk summary (Critical / High / Medium / Low event counts)
- OWASP LLM Top 10 category breakdown
- Full event timeline with risk indicators and OWASP labels
- Chain integrity verification result

---

## Verify Log Integrity

```bash
agentwit verify --session ./witness_logs/session_20260101_120000

# Output:
# Session: session_20260101_120000  (47 events)
# Key fingerprint: abc123...
#
#    #  chain   sig     witness_id
# -----------------------------------------------------------------------
#    0  OK      OK      a1b2c3d4...
#    1  OK      OK      e5f6a7b8...
#    ...
# Result: ALL VALID
```

---

## Replay and Compare Sessions

```bash
# Replay a session and inspect events with risk levels
agentwit replay --session ./witness_logs/session_A

# Compare two sessions side by side
agentwit diff \
  --session-a ./witness_logs/session_A \
  --session-b ./witness_logs/session_B
```

---

## MCP Inspector GUI

The MCP Inspector is a desktop debugger for MCP servers with a real-time
three-pane interface (tool list · parameter editor · response viewer).

### Download

Download the latest `.deb` from the
[Releases page](https://github.com/tokotokokame/agentwit/releases).

### Install and Launch (Linux)

```bash
sudo dpkg -i mcp-inspector_*.deb
mcp-inspector
```

### First Connection

1. Open the **Connection** panel (top bar).
2. Select transport: **HTTP** or **stdio**.
3. For HTTP: enter `http://localhost:3000/mcp` (your MCP server URL).
4. For stdio: enter the command to launch your MCP server.
5. Click **Connect**.

### Export Report from GUI

Once tool calls appear in the **History** tab:

1. Click the amber **Export Report** button in the History tab header.
2. A save dialog opens — choose a destination file
   (default: `agentwit-report-YYYY-MM-DD.html`).
3. The HTML report is generated and opened in your browser automatically.

---

## Docker Compose (Full Observability Stack)

```bash
cd docker/
cp .env.example .env   # set TARGET_URL=http://your-mcp-server:3000
docker compose up -d
```

Services started: agentwit proxy · Grafana Loki · Fluent Bit · Grafana.

Grafana dashboard: [http://localhost:3000](http://localhost:3000)
(default credentials: admin / changeme)

### SIEM Forwarding

```bash
export SPLUNK_HEC_TOKEN=your-token
export SPLUNK_HOST=splunk.example.com
docker compose -f docker/docker-compose.siem.yml up -d
```

---

## Frequently Asked Questions

**Q: Does agentwit modify my MCP server?**
A: No. agentwit is a transparent proxy — the MCP server receives identical
requests and returns identical responses. Nothing is changed or blocked.

**Q: Does agentwit slow down my agent?**
A: The overhead is sub-millisecond for typical JSON-RPC payloads. Logging is
asynchronous and does not block the request/response path.

**Q: Where are logs stored?**
A: By default, `./witness_logs/<session_id>/witness.jsonl`.  Change the
directory with `--log-dir /path/to/dir`.

**Q: What is the audit.jsonl file?**
A: `~/.agentwit/audit.jsonl` records high-level security events (bypass
detections, connection errors, process crashes) from all sessions. The
per-session `witness.jsonl` contains the full tamper-evident event chain.

**Q: Can I use agentwit with any AI agent framework?**
A: Yes. The HTTP and stdio proxies are framework-agnostic — they work with
Claude, GPT-4, Gemini, or any custom agent that communicates with MCP.
For LangChain specifically, use `AgentwitCallback` for direct integration.

**Q: How do I detect prompt injection?**
A: agentwit's built-in risk scorer checks every tool call payload for
patterns like `ignore previous instructions`, `role hijack`, and hidden
Unicode control characters. Matching events are flagged with severity
CRITICAL and the `prompt_injection` pattern.

**Q: Can I write custom detection rules?**
A: Yes, via the plugin system. See [plugin-guide.md](plugin-guide.md).

**Q: Is the witness log tamper-proof?**
A: Each event is SHA-256 hashed and chained to the previous event's hash
(similar to a blockchain). Any modification — even a single byte — breaks
the chain and is detected by `agentwit verify`. Events are also signed with
an ed25519 key stored in `~/.agentwit/`.

**Q: How do I integrate with Splunk or Elasticsearch?**
A: Use the SIEM Fluent Bit configuration in `docker/docker-compose.siem.yml`.
Set `SPLUNK_HEC_TOKEN` / `ES_HOST` environment variables and start the stack.
