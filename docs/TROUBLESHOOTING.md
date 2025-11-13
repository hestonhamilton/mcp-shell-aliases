# Troubleshooting

## No aliases show up

- Ensure `alias_files` points to real files. Paths with `~` expand to your home directory, and relative entries are resolved next to the config file.
- If you pass `--config` and the file is missing, startup now fails with `ConfigError: Config file <path> not found`.
- Run with `--verbose` to see warnings about missing or malformed aliases.

## Execution denied

- Check the catalog: the alias might be marked `safe: false`. Update `allow_patterns` or enable dry-run.
- Calls must include `dry_run=false` **and** `confirm=true` to execute.
- A `ToolError` mentioning "Alias is not marked safe" indicates the allowlist did not match; run in dry-run mode or adjust the allowlist with care.

## Git reports "not a git repository"

- By default, tools run in `default_cwd` (home). Pass a project path with the `cwd` argument, e.g.:
  - `alias.exec {"name":"gst","dry_run": false, "confirm": true, "cwd": "/path/to/repo"}`
- Alternatively, set `default_cwd` in `config.yaml` to your workspace root (requires server restart).

## `cwd` rejected

- The requested directory must be within `allow_cwd_roots` (default `~`). Add additional roots in the config or CLI.

## Config changes not taking effect

- The server hot-reloads alias files on each request, but it does not re-read `config.yaml` automatically.
- After changing `allow_patterns`, `alias_files`, `default_cwd`, or other top‑level settings, restart the server.

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

## Gemini CLI doesn’t recognize the server

- Verify the server is running and reachable: start with
  `mcp-shell-aliases --config config.yaml --transport http --http-host 127.0.0.1 --http-port 3921 --http-path /mcp --verbose`.
- Check your project’s `.gemini/settings.json` (or `~/.gemini/settings.json` if added with `--scope user`).
  For HTTP transports the entry must use `httpUrl`, not `command`:
  ```json
  {
    "mcpServers": {
      "mcp-shell-aliases": { "httpUrl": "http://127.0.0.1:3921/mcp" }
    }
  }
  ```
- Run `gemini mcp list` to confirm registration and `/mcp refresh` inside the CLI to load tools.
- If connection still fails, try switching the server to `--transport sse` and keep the same URL.
- Ensure the URL path matches your `http_path` (default `/mcp`) and avoid trailing-space or quoting issues.

## Still stuck?

- Run the automated tests (`docs/Testing.md`) to catch regressions.
- Use `--verbose` logging to see which config values are loaded at runtime.
