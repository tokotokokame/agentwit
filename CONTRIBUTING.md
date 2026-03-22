# Contributing to agentwit

Thank you for your interest in contributing to agentwit!

---

## Table of Contents

- [Development Environment Setup](#development-environment-setup)
- [Running Tests](#running-tests)
- [Project Structure](#project-structure)
- [Coding Conventions](#coding-conventions)
- [Submitting a Pull Request](#submitting-a-pull-request)
- [Reporting Bugs](#reporting-bugs)
- [Requesting Features](#requesting-features)

---

## Development Environment Setup

### Prerequisites

- Python 3.10 or later
- Git
- (Optional) Node.js 20+ and Rust for GUI development

### Clone and install

```bash
git clone https://github.com/tokotokokame/agentwit.git
cd agentwit

# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate      # Linux / macOS
# .venv\Scripts\activate       # Windows

# Install in editable mode with all dev dependencies
pip install -e ".[dev]"
```

### GUI development (optional)

The desktop GUI lives in `gui/` and is built with Tauri v2 + React.

```bash
# Install Rust (if not already installed)
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh

# Install Node dependencies
cd gui
npm install

# Start the GUI in development mode (hot-reload)
npm run tauri dev
```

### Verify the setup

```bash
# CLI should be available
agentwit --version

# All tests should pass
cd /path/to/agentwit
pytest
```

---

## Running Tests

### Full test suite

```bash
pytest
```

### Specific test files

```bash
pytest tests/test_owasp_mapper.py -v
pytest tests/test_agent_monitor.py -v
pytest tests/test_proxy.py -v
```

### With coverage

```bash
pytest --cov=agentwit --cov-report=term-missing
```

### Test requirements

All tests must pass before a pull request can be merged.  The CI pipeline runs
`pytest` on Python 3.10, 3.11, and 3.12.

---

## Project Structure

```
agentwit/
├── agentwit/
│   ├── analyzer/
│   │   ├── owasp_mapper.py     # OWASP LLM Top 10 mapping
│   │   └── scorer.py           # Built-in risk detection patterns
│   ├── integrations/
│   │   └── langchain.py        # LangChain callback handler
│   ├── monitor/
│   │   └── cost_guard.py       # Call-rate and cost anomaly detection
│   ├── plugins/
│   │   ├── __init__.py         # load_plugins() entry-point discovery
│   │   └── base.py             # PluginBase abstract class
│   ├── proxy/
│   │   ├── http_proxy.py       # HTTP / SSE transparent proxy
│   │   ├── sse_proxy.py        # SSE streaming proxy
│   │   └── stdio_proxy.py      # stdio subprocess proxy
│   ├── reporter/
│   │   ├── html_reporter.py    # HTML audit report generator
│   │   ├── json_reporter.py    # JSON report generator
│   │   └── markdown_reporter.py # Markdown report generator
│   ├── security/
│   │   ├── bypass_detector.py  # X-Agentwit-Proxy header check
│   │   └── signing.py          # ed25519 key management and signing
│   ├── witness/
│   │   ├── chain.py            # SHA-256 chain manager
│   │   └── log.py              # WitnessLogger (thread-safe JSONL writer)
│   └── cli.py                  # Click CLI entry point
├── gui/                        # Tauri v2 + React desktop GUI
├── docker/                     # Docker Compose stacks
├── docs/                       # Documentation
└── tests/                      # Pytest test suite
```

---

## Coding Conventions

### Python style

- Follow [PEP 8](https://peps.python.org/pep-0008/).
- Maximum line length: **100 characters**.
- Use type hints for all public function signatures.
- Use `from __future__ import annotations` for forward references.
- Prefer `pathlib.Path` over `os.path`.

### Naming

- Module names: `snake_case`
- Classes: `PascalCase`
- Functions and variables: `snake_case`
- Constants: `UPPER_SNAKE_CASE`
- Test files: `test_<module_name>.py`
- Test functions: `test_<what_it_tests>`

### Imports

Order imports as: standard library → third-party → local, separated by blank lines.

```python
from __future__ import annotations

import json
import logging
from pathlib import Path

import httpx
from fastapi import FastAPI

from agentwit.witness.log import WitnessLogger
```

### Tests

- Every new public function or class must have tests.
- Aim for **at least 90% branch coverage** on new code.
- Use `pytest` fixtures; avoid `unittest.TestCase` subclasses.
- Name test classes `TestClassName`; name test functions `test_<behavior>`.
- Do not use `time.sleep` in tests — use mocks or `asyncio` event loop control.

### Risk patterns

When adding a new detection pattern to `scorer.py`:

1. Add a constant string name in `UPPER_SNAKE_CASE`.
2. Pick a severity: `low` / `medium` / `high` / `critical`.
3. If the pattern maps to an OWASP LLM Top 10 category, add it to
   `OWASP_MAPPING` in `agentwit/analyzer/owasp_mapper.py`.
4. Add tests in `tests/test_scorer.py`.

### Commit messages

Use the [Conventional Commits](https://www.conventionalcommits.org/) format:

```
feat: add regex-scanner plugin base
fix: retry loop not resetting on successful connection
docs: add plugin guide step-by-step example
test: add owasp_mapper edge-case tests
chore: bump version to 0.8.0
```

---

## Submitting a Pull Request

1. **Fork** the repository and create a feature branch from `master`:

   ```bash
   git checkout -b feat/my-feature
   ```

2. **Make your changes** and add tests.

3. **Run the full test suite** and make sure everything passes:

   ```bash
   pytest
   ```

4. **Push** your branch and open a Pull Request against `master`.

5. In the PR description, include:
   - What the change does and why.
   - How to test it manually (if applicable).
   - Any screenshots for GUI changes.

6. A maintainer will review your PR.  Small, focused PRs are merged faster.
   If your PR is large, consider splitting it into smaller pieces.

### PR checklist

- [ ] Tests added or updated
- [ ] All existing tests pass (`pytest`)
- [ ] Version bumped in `pyproject.toml` if applicable
- [ ] `CHANGELOG.md` updated under `[Unreleased]`
- [ ] Documentation updated if public API changed

---

## Reporting Bugs

Open an issue at [github.com/tokotokokame/agentwit/issues](https://github.com/tokotokokame/agentwit/issues)
with the **Bug report** template and include:

1. agentwit version (`agentwit --version`)
2. Python version (`python --version`)
3. Operating system
4. Minimal reproduction steps
5. Expected behavior
6. Actual behavior (include full tracebacks)

---

## Requesting Features

Open an issue with the **Feature request** template and include:

1. The use case — what problem does this feature solve?
2. A proposed API or CLI interface (if you have one in mind).
3. Whether you are willing to implement it yourself.

For large features, open a discussion first to align on the design before
writing code.

---

## License

By contributing, you agree that your contributions will be licensed under the
[MIT License](LICENSE).
