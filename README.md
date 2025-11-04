# MCP Bash Aliases Server

A Model Context Protocol (MCP) server that exposes your shell aliases as safe, discoverable tools. It parses configured alias files (e.g. `~/.bash_aliases`) and surfaces them to MCP hosts such as the Gemini CLI.

## Features

- Discovers aliases from explicitly configured files.
- Emits MCP tools/resources for dry-run and real execution.
- Enforces allowlist/denylist safety rules and dry-run by default.
- Sandboxes execution with constrained environment, cwd policy, and timeouts.
- Writes structured audit logs for every invocation.

## Quick Start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .[dev]

# copy and edit a config
cp gemini-shell-aliases/examples/sample_config.yaml config.yaml

# run the server over stdio
mcp-bash-aliases --config config.yaml --verbose
```

Point your MCP host at the `mcp-bash-aliases` executable (or `python3 -m mcp_bash_aliases`) with the same config file.

## Configuration

The server loads settings from `config.yaml`, environment variables (`MCP_BASH_ALIASES_*`), and CLI flags. See `docs/CONFIGURATION.md` for the full reference. A minimal config:

```yaml
alias_files:
  - ~/.bash_aliases
allow_patterns:
  - '^ls\b'
deny_patterns:
  - '^rm\b'
```

## Safety Model

- Aliases are classified using allow/deny regexes. Unsafe aliases can only run in dry-run mode.
- Real execution requires `dry_run=false` and `confirm=true` tool arguments.
- Commands execute via `/bin/bash -lc` with a scrubbed environment, bounded output, and timeouts.
- Audit logs capture every call. See `docs/SECURITY.md` for details.

## Host Integration

Update your MCP host configuration to use the new server, for example in `gemini-extension.json`:

```json
{
  "mcp_server": {
    "command": [
      "python3",
      "-m",
      "mcp_bash_aliases",
      "--config",
      "${extensionPath}/config.yaml"
    ]
  }
}
```

Verify by listing the `alias.catalog` tool, reading the `alias://catalog` resource, and executing a safe alias with `dry_run`.

### HTTP/SSE Transports

Some agentic tools prefer to talk over HTTP instead of stdio. You can start the
server on a local port with:

```bash
mcp-bash-aliases \
  --config config.yaml \
  --transport http \
  --http-host 127.0.0.1 \
  --http-port 3921 \
  --http-path /mcp
```

Then point your host at `http://127.0.0.1:3921/mcp`. Use `--transport sse` or
`--transport streamable-http` for alternative FastMCP transports.

## Project Status

- ✅ Python/FastMCP implementation exposes `alias.exec` and browseable resources.
- ✅ Safety rails enforced: dry-run default, allow/deny patterns, timeouts, cwd policy, audit logs.
- ✅ Hot reload is available via on-demand catalog refresh (no file watcher yet).
- 🚧 Prompt helpers, inotify-style hot reload, and advanced hardening are still on the roadmap (see `TODO.md`).

## Testing & Quality

```bash
# lint
ruff check mcp_bash_aliases tests

# unit + contract suite (includes in-process MCP smoke tests)
pytest --cov=mcp_bash_aliases --cov-report=term-missing

# type checking (requires stub package: python -m pip install types-PyYAML)
mypy mcp_bash_aliases
```

The test suite exercises alias parsing, sandbox execution, CLI entry points, and
the FastMCP server itself via the official Python client. See
`docs/Testing.md` for the complete breakdown and troubleshooting tips.

## Tool Usage Example

```json
{
  "tool": "alias.exec",
  "arguments": {
    "name": "ll",
    "args": "~/projects",
    "dry_run": true
  }
}
```

Unsafe aliases will always return dry-run results unless they match the configured allowlist patterns.

## Contributing

See `gemini-shell-aliases/CONTRIBUTING.md` for development workflow and coding standards.
