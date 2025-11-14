**Overview**
- Purpose: Use the MCP Shell Aliases server from the Gemini CLI and extensions.
- What it exposes: Tools and resources that surface your shell aliases as safe, auditable actions.

**Quick Setup**
- Install as an extension: `gemini extensions install <github_url>` and consent when prompted.
- Or add as an MCP server (stdio): `gemini mcp add mcp-shell-aliases python -m mcp_shell_aliases --config /path/to/config.yaml`
- Refresh and verify: In a Gemini CLI session, run `/mcp refresh`, then list tools with `/mcp tools`.

**Tools**
- `alias.catalog`: Returns metadata for all aliases.
  - Result: `aliases[]` with fields `name`, `expansion`, `safe`, `sourceFile`, `example`.
- `alias.exec`: Execute or dry-run a single alias.
  - Args: `name` (string), `args` (string, optional), `dry_run` (bool, default true), `confirm` (bool, required true to execute), `cwd` (string, optional), `timeout_seconds` (int, optional).
  - Behavior: If the alias is not marked safe, only dry-run is allowed. Real execution requires `dry_run=false` and `confirm=true`.
  - Response: Structured payload with `stdout`, `stderr`, `returnCode`, `truncatedStdout`, `truncatedStderr`, `durationMs`, `cwd`, plus `aliasSafe` and `sourceFile`.

**Resources**
- `alias://catalog`: JSON array of `alias.catalog` entries.
- `alias://{alias_name}`: JSON entry for a single alias.

**Typical Flow**
- Discover: Call `alias.catalog` (or read `alias://catalog`) to see available aliases and which are safe.
- Inspect: Read `alias://{name}` to confirm the exact expansion and any examples.
- Dry-run: Call `alias.exec` with `dry_run=true` to preview the command line and environment.
- Execute: Only if appropriate, call `alias.exec` with `dry_run=false` and `confirm=true`.

**Prompting Examples**
- List aliases and choose one
  - “List the available alias catalog, select a safe alias that lists files, then dry-run it.”
- Dry-run an alias
  - Tool call: `alias.exec` with `{ "name": "lsdocs", "args": "-la", "dry_run": true }`.
- Execute a safe alias
  - Tool call: `alias.exec` with `{ "name": "list-branches", "dry_run": false, "confirm": true }`.

**Safety Model**
- Allowlist-only: Aliases matching configured regexes are marked `safe`; everything else is dry-run only.
- Defaults: `dry_run=true`, bounded output sizes, and timeouts.
- CWD policy: Requests outside configured `allow_cwd_roots` are rejected.
- Auditing: Every invocation is written to a JSONL audit log.

**Transports**
- Default is stdio (no extra ports). The extension manifest runs a bootstrap that creates a local venv and starts the stdio server.
- HTTP/SSE modes are available via config/flags, but the Gemini CLI uses stdio for extensions.

**Troubleshooting**
- After install: Run `/mcp refresh` to load new tools.
- If tools don’t appear: Check `gemini extensions list`, ensure the extension is enabled, and view logs in the extension folder.
- Permission or path issues: Verify `config.yaml` paths (e.g., `alias_files`) exist inside the environment where Gemini runs.

