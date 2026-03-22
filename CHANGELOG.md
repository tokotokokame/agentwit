# Changelog

All notable changes to agentwit are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

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
