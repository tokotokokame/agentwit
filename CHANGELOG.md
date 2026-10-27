# Changelog

All notable changes to agentwit are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Changed
- Risk scoring no longer scans MCP introspection/handshake methods
  (`tools/list`, `initialize`, `ping`, `resources/list`, `prompts/list`, …)
  by default. Their payloads are capability *catalogues*, not actions, so
  keyword-scanning them flagged a security-domain toolset on every single
  `tools/list` — e.g. a tool named `cloud-scan` (param `credentials`) tripped
  credential_access and a description mentioning `nmap` tripped
  lateral_movement, firing HIGH alerts on mere capability enumeration. These
  events are still recorded (chain + signature intact); they are just not
  risk-scored. Set `monitor.score_introspection: true` to restore catalogue
  scanning. Real risk in `tools/call` arguments and results is unaffected.

### Fixed
- HTTP proxy: every forwarded request that produced a risk indicator
  returned **500** (`NameError: ... '_notifier' ...`). The bypass branch in
  `proxy_all` assigned `_notifier`, making it a local and shadowing the
  enclosing notifier that the nested `_record()` closes over; when the
  branch had not run (the normal daemon / NotificationHub setup) the
  closure reference was unbound. Renamed the bypass-branch local. The HTTP
  passthrough had no forward test at all, so a buffered-JSON MCP response
  — the real-world case — was never exercised; added one that drives a
  flagged payload through the route and fails with the original NameError
  if the shadow returns.
- `notify.routes`: an unquoted `on:`/`off:` key is read by YAML as the
  boolean `True`/`False`, not the string `"on"`/`"off"`. This previously
  parsed, saved, and passed `config validate` — while silently disabling
  severity routing forever (discovered live during a real deployment: the
  route validated, test pushes worked, but real HIGH/CRITICAL alerts never
  fired). `validate_config` now rejects it with a message pointing at the
  fix. README and README.ja updated with the quoting requirement.

---

## [1.2.0] - 2026-10-26

Resident-service update: run agentwit as a daemon, manage it from a local
console, route alerts to Slack/Discord/email, and keep secrets out of config
and logs.

### Added

- **Unified config + secrets layer** — `~/.agentwit/config.yaml` (no secrets)
  plus `~/.agentwit/secrets.env` (0600). Config references credentials as
  `${env:NAME}`; nothing secret ships in the package. `agentwit init` and
  `agentwit config get|set|validate`.
- **Resident daemon** — `agentwit daemon`: single process (one thread idle,
  no children, ~60–70 MB RSS), SIGHUP hot-reload of monitor/notify settings
  without dropping the socket, graceful SIGTERM/SIGINT. systemd user unit and
  macOS LaunchAgent under `packaging/` with memory/CPU caps and hardening.
- **Config-driven monitoring** — toggle risk rules, limit scored tools, and
  control redaction from config; wired into both HTTP and stdio proxies.
- **Notification hub** — multiple destinations (Slack, Discord, generic
  webhook, email/SMTP), per-route severity routing, per-minute rate limit,
  https + host allow-list SSRF guard for webhooks, SMTP-host SSRF guard.
- **Local settings console** — `agentwit ui`: loopback-only page to view and
  change config, add destinations (secret-safe), and review detections. CSRF
  token delivered via URL fragment; secret values are never returned by the API.
- **Secret redaction** — two layers: key-name based, and value scanning for
  high-confidence secret shapes (Bearer/Authorization, AWS/GitHub/OpenAI/Slack
  tokens, JWT, Slack/Discord webhook URLs, PEM private keys).
- **Session summary push** — `agentwit summary [--session] [--push]` and an
  optional daemon end-of-session push, so a phone sees activity via the
  existing notification routes.

### Fixed

- `cli.py` referenced an undefined `cli` for the `gui` command, which made the
  whole CLI unimportable; corrected to the `main` group.
- Webhook URLs (a secret) and raw exception text are no longer written to logs.
- CSRF token compared in constant time; malformed Content-Length returns 400.

### Security

- Notification fields from MCP traffic are sanitized (@channel/@here, Slack
  control spans, backticks, control chars) before interpolation.
- First-pass threat-model review recorded; see the security review doc.

---

## [1.0.0] - 2026-03-22

### Added

- **Plugin system** — third-party detection plugins via Python entry-points
  (`agentwit.plugins` group). `PluginBase` ABC with `scan(event) → list[dict]`.
  `load_plugins()` auto-discovers installed plugins at proxy startup.
- **OWASP LLM Top 10 (2025) mapping** — `OWASPMapper` class maps 15 built-in
  risk patterns to LLM01/02/06/08/10 categories. HTML reports now include an
  OWASP summary card and per-event OWASP column.
- **Proxy error handling**
  - HTTP proxy: 3-attempt exponential backoff (1 s → 2 s → 4 s) on upstream
    connection failure. Writes `connection_error` to `audit.jsonl` on exhaustion.
  - SSE proxy: timeout + retry (up to 3 attempts). Writes `sse_timeout` to
    `audit.jsonl` on exhaustion.
  - stdio proxy: auto-restarts subprocess up to 3 times on non-zero exit.
    Writes `process_crash` to `audit.jsonl` after all restarts fail.
- **`--timeout` CLI option** for `agentwit proxy` (default: 30 s).
- **LangChain callback enhancements** (`AgentwitCallback`)
  - `on_agent_action`: extracts ReAct `Thought:` line and writes
    `agent_thought` record to `audit.jsonl`.
  - `on_agent_finish`: writes `agent_finish` record with final answer.
  - `on_llm_start`: writes `llm_start` record with 100-char prompt preview.
  - `on_llm_end`: writes `llm_end` record with 100-char response preview.
- **GUI Export Report button** — amber button in the History tab opens a native
  save dialog, calls `generate_report` Tauri command, and shows a toast on success.
- **Docker SIEM stack** — `docker/docker-compose.siem.yml` + extended
  `docker/fluent-bit.conf` with Splunk HEC, Elasticsearch, and Grafana Loki
  outputs. Sensitive fields masked by `record_modifier`.
- **GitHub Actions GUI build** (`.github/workflows/build_gui.yml`) — builds
  Linux `.deb` and Windows `.msi` artifacts on version tags.
- **Documentation** — `docs/quickstart.md`, `docs/architecture.md`,
  `docs/api-reference.md`, `docs/plugin-guide.md`, `CONTRIBUTING.md`.

### Changed

- Version bumped to **1.0.0**.
- `create_proxy_app()` now accepts `timeout: float` parameter.
- `WitnessLogger.alog_event()` now accepts optional `risk_indicators` list to
  merge plugin alerts alongside built-in scorer results.
- HTML report: OWASP category column added to event timeline table.
- GUI text contrast improved (`--text-md`, `--text-lo` CSS variables updated
  for better readability on dark background).

---

## [0.7.0] - 2026-02-15

### Added

- **OWASP LLM Top 10 mapping** (initial) — `agentwit/analyzer/owasp_mapper.py`
  with `map()`, `describe()`, `map_events()`, and `summary()` methods.
- **HTML report OWASP card** — new summary section shows counts per OWASP
  category with color-coded badges.
- 33 new tests for `OWASPMapper` (`tests/test_owasp_mapper.py`).

### Changed

- Version bumped to **0.7.0**.
- `html_reporter.py` imports and calls `OWASPMapper`; event timeline includes
  OWASP column.

---

## [0.6.0] - 2026-01-20

### Added

- **Proxy error handling with retry** — HTTP proxy retries failed upstream
  connections 3 times with exponential backoff.
- **SSE proxy** fully implemented — previously raised `NotImplementedError`.
  Now streams upstream SSE events with timeout and retry support.
- **stdio proxy auto-restart** — subprocess automatically restarted up to 3
  times on non-zero exit code.
- **`--timeout` option** for `agentwit proxy`.
- **`audit.jsonl` error records** — `connection_error`, `sse_timeout`, and
  `process_crash` record types written to `~/.agentwit/audit.jsonl`.
- **LangChain `AgentwitCallback` enhancements** — thought extraction, audit
  log writing for `on_agent_action`, `on_agent_finish`, `on_llm_start`,
  `on_llm_end`. 32 new tests in `tests/test_agent_monitor.py`.
- **GUI Export Report** — Tauri `generate_report` command, `tauri-plugin-dialog`
  save dialog, amber Export Report button in History tab with toast notification.

### Changed

- Version bumped to **0.6.0**.
- `pyproject.toml` dev extras updated.

---

## [0.5.0] - 2025-12-10

### Added

- **ed25519 signing** — every witness log event is signed with a per-host
  ed25519 key stored at `~/.agentwit/signing_key.pem`. Signature and public key
  fingerprint are embedded in each event.
- **Bypass detection** — `X-Agentwit-Proxy` header round-trip check. Requests
  reaching the upstream that bypassed the proxy are flagged as
  `proxy_bypass_detected`.
- **Anomaly detection** (`CostGuard`) — emits `call_rate_anomaly` when >30
  calls/min to the same tool; emits `session_cost_exceeded` on token cost
  threshold.
- `agentwit verify` CLI command — recomputes SHA-256 chain and re-verifies
  ed25519 signatures for a session. Exit code 1 on any failure.
- `agentwit diff` CLI command — compares tool call counts and risk profiles
  between two sessions.
- `agentwit replay` CLI command — replays all events from a session with
  optional chain verification.
- **Auto-backup** — completed sessions are copied to `~/.agentwit/backups/`.

### Changed

- Version bumped to **0.5.0**.
- `witness.jsonl` format extended with `signature` and `signed_by` fields.

---

## [0.4.0] - 2025-10-28

### Added

- **Prompt injection detection** — built-in patterns for `instruction_override`,
  `role_hijack`, `jailbreak`, `hidden_instruction` (Unicode control characters),
  and `data_extraction`. All flagged CRITICAL.
- **Tool monitoring** — `tool_schema_change` pattern detects when a tool is
  added or its schema changes between sessions.
- **Docker Compose audit stack** — `docker/docker-compose.yml` with agentwit
  proxy + Grafana Loki + Fluent Bit + Grafana dashboard.
- **Fluent Bit integration** — ships `audit.jsonl` and `witness.jsonl` to Loki
  with automatic auth header masking.

### Changed

- Version bumped to **0.4.0**.
- Risk severity labels unified to `low` / `medium` / `high` / `critical`.

---

## [0.3.0] - 2025-09-05

### Added

- **MCP Inspector GUI** — Tauri v2 + React desktop application with three-pane
  layout: tool list, parameter editor, response viewer.
- Session compare view — side-by-side diff of two sessions.
- Cost tracking panel — token usage and estimated cost per session.
- Pre-built `.deb` package for Linux available on the Releases page.

### Changed

- Version bumped to **0.3.0**.
- CLI output: colored severity labels (CRITICAL=red, HIGH=yellow, etc.).

---

## [0.2.0] - 2025-07-18

### Added

- **HTML, Markdown, and JSON report generation** — `agentwit report` command
  with `--format` and `--output` options.
- **LangChain integration** (`AgentwitCallback`) — records agent thoughts, tool
  calls, LLM prompts/responses to `audit.jsonl`.
- **Slack and Discord webhook notifications** — `--webhook` and `--webhook-on`
  options; auto-detected from webhook URL.
- `agentwit report` HTML report includes dark-theme event timeline and risk
  summary grid.

### Changed

- Version bumped to **0.2.0**.
- `witness.jsonl` events include `input_hash` and `output_hash` (SHA-256 of
  request params and response result).

### Fixed

- SSE streams no longer buffered; each chunk forwarded immediately.

---

## [0.1.0] - 2025-05-30

### Added

- Initial release.
- **Transparent HTTP proxy** (`agentwit proxy --target URL --port PORT`).
- **stdio proxy** (`agentwit proxy --stdio -- COMMAND`).
- **SHA-256 chained witness log** — tamper-evident `witness.jsonl` per session.
- **Built-in risk scorer** — 15 detection patterns covering shell execution,
  credential access, privilege escalation, data exfiltration, lateral movement,
  and persistence.
- `agentwit verify` (basic chain check, pre-signing).
- JSONL-format witness log with `witness_id` and `session_chain` fields.
- `--actor` option to label events by agent identity.
- `--log-dir` option to configure the session log directory.

---

[Unreleased]: https://github.com/tokotokokame/agentwit/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/tokotokokame/agentwit/compare/v0.7.0...v1.0.0
[0.7.0]: https://github.com/tokotokokame/agentwit/compare/v0.6.0...v0.7.0
[0.6.0]: https://github.com/tokotokokame/agentwit/compare/v0.5.0...v0.6.0
[0.5.0]: https://github.com/tokotokokame/agentwit/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/tokotokokame/agentwit/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/tokotokokame/agentwit/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/tokotokokame/agentwit/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/tokotokokame/agentwit/releases/tag/v0.1.0
