# MCP Shell Aliases Server

A Model Context Protocol (MCP) server that exposes your shell aliases as safe, discoverable tools. It parses configured alias files (e.g. `~/.bash_aliases`) and surfaces them to MCP hosts such as the Gemini CLI.

## Features

- Discovers aliases from explicitly configured files.
- Emits MCP tools/resources for dry-run and real execution.
- Enforces allowlist-only safety rules and dry-run by default.
- Sandboxes execution with constrained environment, cwd policy, and timeouts.
- Writes structured audit logs for every invocation.

## Quick Start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .[dev]

# copy and edit a config
cp examples/sample_config.yaml config.yaml

# run the server over stdio
mcp-shell-aliases --config config.yaml --verbose
```

Point your MCP host at the `mcp-shell-aliases` executable (or `python3 -m mcp_shell_aliases`) with the same config file.

## Configuration

The server loads settings from `config.yaml`, environment variables (`MCP_SHELL_ALIASES_*`), and CLI flags. See `docs/CONFIGURATION.md` for the full reference. A minimal config:

```yaml
alias_files:
  - ~/.bash_aliases
allow_patterns:
  - '^ls\b'
```

## Safety Model

- Aliases are classified using allowlist regexes. Anything that fails to match stays in dry-run mode.
- Real execution requires `dry_run=false` and `confirm=true` tool arguments.
- Commands execute via `/bin/bash -lc` with a scrubbed environment, bounded output, and timeouts.
- Audit logs capture every call. See `docs/SECURITY.md` for details.

## Gemini Extension Integration

This project can be installed as a Gemini extension, allowing the Gemini CLI to discover and utilize your shell aliases as tools.

### Installation via Gemini CLI

To install the `mcp-shell-aliases` server as a Gemini extension, you can use the `gemini extensions install` command. This command expects a GitHub repository URL where the `gemini-extension.json` file is located at the root.

```bash
gemini extensions install https://github.com/your-org/mcp-shell-aliases.git
```

**Note:** If your repository is private, you will need to ensure your Gemini CLI environment has access to your SSH keys or appropriate credentials.

After installation, the Gemini CLI will use the `mcp_server` command defined in the `gemini-extension.json` to run the MCP server.

### Docker-based Testing Workflow

For development and testing of the Gemini extension, especially when dealing with private repositories or specific environments, a Docker-based workflow is recommended.

1.  **Build the Docker Image:**
    ```bash
    docker build -t mcp-shell-aliases-gemini-extension .
    ```
2.  **Run the Test Script:**
    The `test_extension.sh` script automates the process of running a Docker container, installing the extension within it, and performing basic verification.
    ```bash
    ./test_extension.sh
    ```
    **Important:** Ensure your `github.key` is added to your SSH agent (`ssh-add github.key`) if you are testing with a private repository, as the script uses SSH agent forwarding. Remember to replace the placeholder `GITHUB_REPO_URL` in `test_extension.sh` with your actual repository URL.

### Manual Configuration

For manual configuration or if you prefer to run the server directly, you can update your MCP host configuration (e.g., in `.gemini/settings.json`) to use the server.

```json
{
  "mcp_server": {
    "command": [
      "python",
      "-m",
      "mcp_shell_aliases",
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
mcp-shell-aliases \
  --config config.yaml \
  --transport http \
  --http-host 127.0.0.1 \
  --http-port 3921 \
  --http-path /mcp
```

Then point your host at `http://127.0.0.1:3921/mcp`. Use `--transport sse` or
`--transport streamable-http` for alternative FastMCP transports.

If using the Gemini CLI, ensure your project’s `.gemini/settings.json` has an
`mcpServers` entry with `httpUrl` (not `command`) for HTTP transports:

```json
{
  "mcpServers": {
    "mcp-shell-aliases": {
      "httpUrl": "http://127.0.0.1:3921/mcp"
    }
  }
}
```

To add an HTTP server to the Gemini CLI, you must explicitly use the `--transport http` flag:

```bash
gemini mcp add mcp-shell-aliases http://127.0.0.1:3921/mcp --transport http
```

**Note:** For HTTP and SSE transports, the `mcp-shell-aliases` server must be running independently before you add it to the Gemini CLI. The CLI will not automatically start HTTP/SSE servers.

If the CLI still can’t connect, switch the server to `--transport sse` and reuse
the same URL.

## Project Status

- ✅ Python/FastMCP implementation exposes `alias.exec` and browseable resources.
- ✅ Safety rails enforced: dry-run default, allowlist patterns, timeouts, cwd policy, audit logs.
- ✅ Hot reload is available via on-demand catalog refresh (no file watcher yet).
- 🚧 Prompt helpers, inotify-style hot reload, and advanced hardening are still on the roadmap (see `TODO.md`).

## Testing & Quality

```bash
# lint
ruff check mcp_shell_aliases tests

# unit + contract suite (includes in-process MCP smoke tests)
pytest --cov=mcp_shell_aliases --cov-report=term-missing

# type checking (requires stub package: python -m pip install types-PyYAML)
mypy mcp_shell_aliases
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

## Tool API and CWD Guidance

Use these parameters with `alias.exec` to control execution and working directory.

- name: alias name to run.
- args: optional string appended to the alias expansion.
- dry_run: true by default; set to false to execute.
- confirm: required when `dry_run` is false. Acts as a safety gate.
- cwd: working directory to run in; defaults to `default_cwd` (usually `~`). Must be inside `allow_cwd_roots`.
- timeout_seconds: optional positive integer; must be ≤ 5× `execution.default_timeout_seconds`.

Response fields include `command`, `cwd`, `exitCode`, `stdout`, `stderr`, `truncated`, `timedOut`, `dryRun`, plus `aliasSafe` and `sourceFile` for context.

### Running in the right directory (cwd)

- Default behavior: If you do not pass `cwd`, commands run in `default_cwd` (home by default).
- For repo‑specific aliases (e.g., git), pass a project path explicitly:
  - `alias.exec {"name":"gst","dry_run": false, "confirm": true, "cwd": "/path/to/repo"}`
- With agents: Ask the agent to include a `cwd` that points at your project root when calling tools. Example instruction: “When running git aliases, set `cwd` to the current project directory.”

### Safety and allowlist

- An alias is “safe” only if its expansion matches `allow_patterns`.
- Unsafe aliases can still be previewed with `dry_run: true`.
- Real execution requires both `dry_run: false` and `confirm: true`.

### Hot reload vs. config changes

- The server re-parses alias files and re-applies the in-memory allowlist on each request (hot reload).
- Editing `config.yaml` itself (e.g., changing `allow_patterns`, `default_cwd`, or `alias_files`) requires restarting the server for changes to take effect.

## Contributing

See `gemini-shell-aliases/CONTRIBUTING.md` for development workflow and coding standards.
