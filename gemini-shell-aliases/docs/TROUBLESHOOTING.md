# Troubleshooting

## No aliases show up

- Ensure `alias_files` points to real files. The server only parses explicitly configured files.
- Run with `--verbose` to see warnings about missing or malformed aliases.

## Execution denied

- Check the catalog: the alias might be marked `safe: false`. Update `allow_patterns` or enable dry-run.
- Calls must include `dry_run=false` **and** `confirm=true` to execute.

## `cwd` rejected

- The requested directory must be within `allow_cwd_roots` (default `~`). Add additional roots in the config or CLI.

## Output truncated

- Increase `max_stdout_bytes` / `max_stderr_bytes` via config or environment variables.

## Timeouts

- Increase `default_timeout_seconds` or pass `timeout_seconds` in the tool call for long-running aliases.

