# Configuration Reference

The MCP Bash Aliases server is configured via a YAML file (default `config.yaml`). Values can also be overridden with CLI flags or environment variables prefixed with `MCP_BASH_ALIASES_`.

## Top-Level Fields

- `alias_files` (`list[str]`, default: `[]`)
  Explicit alias files to parse. Entries expand `~` to the user's home directory and resolve relative to the config file's directory. Files are read in order; later files override earlier definitions.
- `allow_patterns` (`list[str]`)
  Regex patterns that mark alias expansions as safe for execution. Patterns are
  decoded with Python's escape sequences, so `"^ls\\b"` and `"^ls\b"` are treated
  the same.
- `deny_patterns` (`list[str]`)
  Regex patterns that block execution regardless of allow rules.
- `default_cwd` (`str`, default: `~`)
  Default working directory if callers do not provide one.
- `allow_cwd_roots` (`list[str]`, default: `["~"]`)
  Whitelisted directory roots for execution. Requests outside these roots are rejected.
- `audit_log_path` (`str`)
  File path for JSON lines audit logs (folders are created automatically).
- `enable_hot_reload` (`bool`, default: `true`)
  When enabled, the catalog reloads alias files on every request.
- `transport` (`str`, default: `stdio`)
  Allowed values: `stdio`, `http`, `streamable-http`, or `sse`.
- `http_host` (`str`, default: `127.0.0.1`)
  Host binding for HTTP/SSE transports.
- `http_port` (`int`, default: `3921`)
  Port binding for HTTP/SSE transports.
- `http_path` (`str`, default: `/mcp`)
  URL path exposed when serving HTTP/SSE. A leading slash is added automatically.

### Example `config.yaml`

#### Stdio transport (default)

```yaml
alias_files:
  - ~/.bash_aliases
allow_patterns:
  - '^ls\\b'
  - '^git\\b(?!\\s+(push|reset|rebase|clean))'
deny_patterns:
  - '^rm\\b'
default_cwd: '~'
allow_cwd_roots:
  - '~'
audit_log_path: '~/.local/state/mcp-bash-aliases/audit.log'
execution:
  max_stdout_bytes: 10000
  max_stderr_bytes: 10000
  default_timeout_seconds: 20
enable_hot_reload: true
transport: stdio
```

#### HTTP transport for local agents

```yaml
alias_files:
  - ~/.bash_aliases
allow_patterns:
  - '^ls\\b'
  - '^rg\\b'
deny_patterns:
  - '^rm\\b'
default_cwd: '~'
allow_cwd_roots:
  - '~'
execution:
  max_stdout_bytes: 15000
  max_stderr_bytes: 15000
  default_timeout_seconds: 20
enable_hot_reload: false
transport: http
http_host: 127.0.0.1
http_port: 3921
http_path: /mcp
```

Set `transport` to `streamable-http` or `sse` if your host requires those
variants. Hosts should point at `http://<http_host>:<http_port><http_path>`.

## Execution Limits

```
execution:
  max_stdout_bytes: 10000
  max_stderr_bytes: 10000
  default_timeout_seconds: 20
```

- `max_stdout_bytes` / `max_stderr_bytes`
  Upper bounds for captured output; excess is truncated and flagged.
- `default_timeout_seconds`
  Timeout for alias execution unless the caller provides `timeout_seconds`.

## Environment Variables

Environment variable overrides use uppercase keys. Examples:

- `MCP_BASH_ALIASES_ALIAS_FILES="~/.bash_aliases:~/.bashrc"`
- `MCP_BASH_ALIASES_ENABLE_HOT_RELOAD=false`
- `MCP_BASH_ALIASES_DEFAULT_TIMEOUT_SECONDS=10`
- `MCP_BASH_ALIASES_ALLOW_CWD_ROOTS="~:~/projects"`
- `MCP_BASH_ALIASES_TRANSPORT=http`
- `MCP_BASH_ALIASES_HTTP_HOST=0.0.0.0`
- `MCP_BASH_ALIASES_HTTP_PORT=3921`
- `MCP_BASH_ALIASES_HTTP_PATH=/mcp`

List values are colon-delimited. If `ALLOW_CWD_ROOTS` is empty, the server falls
back to `default_cwd`.

## CLI Flags

Selected overrides are available on the CLI:

- `--alias-file ~/.bash_aliases`
- `--allow-pattern '^git\b'`
- `--deny-pattern '^rm\b'`
- `--default-cwd ~/workspace`
- `--hot-reload/--no-hot-reload`
- `--max-stdout-bytes 2048`
- `--max-stderr-bytes 2048`
- `--timeout 15`
- `--allow-cwd-root ~/projects`
- `--transport http`
- `--http-host 0.0.0.0`
- `--http-port 3921`
- `--http-path /mcp`
