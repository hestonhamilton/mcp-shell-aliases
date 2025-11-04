# Troubleshooting

## No aliases show up

- Ensure `alias_files` points to real files. Paths with `~` expand to your home directory, and relative entries are resolved next to the config file.
- If you pass `--config` and the file is missing, startup now fails with `ConfigError: Config file <path> not found`.
- Run with `--verbose` to see warnings about missing or malformed aliases.

## Execution denied

- Check the catalog: the alias might be marked `safe: false`. Update `allow_patterns` or enable dry-run.
- Calls must include `dry_run=false` **and** `confirm=true` to execute.
- A `ToolError` mentioning "Alias is not marked safe" indicates the denylist matched; run in dry-run mode or adjust the allowlist with care.

## `cwd` rejected

- The requested directory must be within `allow_cwd_roots` (default `~`). Add additional roots in the config or CLI.

## Output truncated

- Increase `max_stdout_bytes` / `max_stderr_bytes` via config or environment variables.

## Timeouts

- Increase `default_timeout_seconds` or pass `timeout_seconds` in the tool call for long-running aliases.
- The `timeout_seconds` argument must be positive and no more than 5× the configured default. Values outside the range return a `ToolError`.

## Unknown alias or resource

- `ToolError: Alias 'xyz' is not defined` means the alias was not parsed from any configured file. Refresh `alias://catalog` to confirm.
- `Unknown resource: alias://name` indicates the resource template path is wrong; use `alias://{alias_name}` syntax.

## HTTP server not reachable

- Ensure `transport` is set to `http`, `streamable-http`, or `sse` and that the
  `http_host`/`http_port` pair matches the host configuration.
- Ports below 1024 may require elevated privileges; choose a higher port such as
  `3921` when running locally.

## Still stuck?

- Run the automated tests (`docs/Testing.md`) to catch regressions.
- Use `--verbose` logging to see which config values are loaded at runtime.
