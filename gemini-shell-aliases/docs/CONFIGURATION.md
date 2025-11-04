# Configuration Reference

The MCP Bash Aliases server is configured via a YAML file (default `config.yaml`). Values can also be overridden with CLI flags or environment variables prefixed with `MCP_BASH_ALIASES_`.

## Top-Level Fields

- `alias_files` (`list[str]`, default: `[]`)
  Explicit alias files to parse. Files are read in order; later files override earlier definitions.
- `allow_patterns` (`list[str]`)
  Regex patterns that mark alias expansions as safe for execution.
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

List values are colon-delimited.

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

