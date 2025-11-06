# Testing Guide

This document explains how we verify the FastMCP “shell aliases” server. The
goal is to keep feedback fast while exercising the real MCP surfaces that
hosts will use.

## Test Commands

Run the checks from the project root after activating the virtualenv:

```bash
ruff check mcp_shell_aliases tests
mypy mcp_shell_aliases
pytest --cov=mcp_shell_aliases --cov-report=term-missing
```

The first command lint-checks both source and tests, the second enforces type
safety (we ship with `types-PyYAML` so mypy can succeed), and the third runs
the full unit/contract suite with coverage output. Coverage is expected to be
≥90 %; the current suite sits around 93 %.

## Suite Layout

| File | Focus |
| ---- | ----- |
| `tests/test_aliases.py` | Alias parsing, dedupe, safety classification flags |
| `tests/test_config.py` | File/env precedence, CLI overrides, error cases |
| `tests/test_execution.py` | Sandbox behaviour, timeouts, audit logging |
| `tests/test_safety.py` | Regex normalisation + allowlist logic |
| `tests/test_cli.py` | CLI argument parsing, module entry point wiring |
| `tests/test_server.py` | Contract/integration tests using `fastmcp.Client` |

The server tests stand up an in-memory FastMCP instance and interact with it
through the public client API, which serves as an automated smoke test for the
tools and resources (`alias.exec`, `alias.catalog`, and the
`alias://{alias_name}` template).

## CI / Automation Ready

The default commands above are CI friendly and require no network sockets. The
FastMCP client talks to the in-process server object directly, so tests do not
spawn subprocesses or bind ports. If you need an HTTP-level smoke test, use
`fastmcp.utilities.tests.run_server_async` with `StreamableHttpTransport`.

## Tips

- Use `pytest -k alias.exec` to target a specific scenario while iterating.
- When adding new config or safety options, back them with unit tests first.
- Keep `pytest --cov` green; adjust tests if coverage dips below 90 %.
- Run `mypy` after modifying `server.py` or `config.py`—we make deliberate use
  of typed dictionaries and signal handlers that benefit from validation.

With this loop we can confidently evolve the server and catch regressions
before publishing.
