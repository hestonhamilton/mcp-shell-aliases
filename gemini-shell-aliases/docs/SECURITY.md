# Security Overview

The MCP Bash Aliases server is designed with conservative defaults to avoid destructive shell execution.

## Threat Model

- **Destructive aliases**: Prevent accidental execution of aliases that manipulate critical files or require elevated privileges.
- **Secret exfiltration**: Avoid leaking environment variables or command output that contains secrets.
- **Host integrity**: Restrict working directories and timeouts to limit blast radius.

## Mitigations

- **Allowlist / denylist**: Regex patterns classify aliases as safe. Unsafe aliases can only run in `dry_run` mode.
- **Dry-run first**: Tools default to `dry_run=True`. Callers must set `confirm=true` and `dry_run=false` to execute.
- **Environment scrubbing**: Execution runs with a minimal environment (`PATH=/usr/bin:/bin`) and a deterministic `HOME`/`PWD`.
- **Working directory policy**: Requested `cwd` must reside in an allowlisted root (default `~`).
- **Timeouts & truncation**: Output is truncated to configured byte limits and processes are killed after `default_timeout_seconds`.
- **Audit logging**: Every invocation appends structured JSON lines with alias name, args, cwd, exit code, timeout flag, and dry-run status.
- **Secret redaction**: Audit entries redact obvious secrets (values containing `token`, `secret`, or `password`).
- **Automated enforcement tests**: Contract tests drive the public FastMCP client against the server to prove unsafe aliases raise `ToolError`, cwd rules apply, and resource payloads stay well formed.

## Reporting Issues

If you discover a vulnerability, please open a private issue or contact the maintainers directly. Avoid disclosing sensitive details in public discussions until a fix is available.

## Residual Risks

- Prompt-based confirmation flows and hot-reload file watching are tracked in `TODO.md`.
- If you allow long-running aliases, review and adjust `default_timeout_seconds` or per-call overrides to match your threat model.
