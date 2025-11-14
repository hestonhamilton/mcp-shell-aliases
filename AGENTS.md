**Overview**
- Purpose: Guide MCP-capable agents on how to safely and effectively use the Shell Aliases server.
- Server ID: `shell-aliases` (as advertised by the server).

**Capabilities**
- Tools:
  - `alias.catalog` → Enumerate available aliases with safety metadata.
  - `alias.exec` → Execute or dry-run a specific alias with optional args and cwd.
- Resources:
  - `alias://catalog` → Full alias catalog (JSON array).
  - `alias://{alias_name}` → Details for a single alias.

**Contract**
- `alias.exec` parameters:
  - `name`: string (required)
  - `args`: string (optional)
  - `dry_run`: boolean (default true)
  - `confirm`: boolean (required true when `dry_run=false`)
  - `cwd`: string (optional; must be under configured allowlist roots)
  - `timeout_seconds`: integer (optional; capped)
- `alias.exec` result fields (core):
  - `stdout`, `stderr` (strings; may be truncated)
  - `returnCode` (int)
  - `truncatedStdout`, `truncatedStderr` (bools)
  - `durationMs` (int), `cwd` (string)
  - Plus `aliasSafe` and `sourceFile` metadata

**Usage Patterns**
- Discovery-first:
  - Call `alias.catalog` to obtain the set of aliases and identify those with `safe=true`.
  - Optionally read `alias://catalog` or `alias://{name}` for human-readable planning and examples.
- Dry-run before execute:
  - For any action, first call `alias.exec` with `dry_run=true` to preview the exact command line.
  - Only if the alias is `safe=true` and the preview is acceptable, consider execution with `dry_run=false` and `confirm=true`.
- CWD discipline:
  - Provide `cwd` when necessary; ensure it is under allowed roots. If omitted, the server defaults to the configured `default_cwd`.
- Timeouts and output sizes:
  - Respect `timeout_seconds` limits; check `truncatedStdout/Stderr` to detect truncation.

**Error Handling**
- `ToolError` messages indicate invalid alias name, disallowed cwd, unsafe execution attempt, invalid timeout, or other guardrail triggers.
- On `unsafe` aliases, execution with `dry_run=false` is rejected; fall back to `dry_run=true` or select a safe alternative.

**Agent Policy Recommendations**
- Default to `dry_run=true` unless the user explicitly authorizes execution.
- Confirm alias intent with the user using the expansion string before running with `confirm=true`.
- Prefer `safe=true` aliases for automatic execution; treat others as informative only.
- Cache the catalog briefly, but refresh when the user suggests aliases changed.
- Capture and surface audit details: `returnCode`, elapsed time, and any truncation flags.

**Transport Notes**
- Stdio is common in local hosts; this server also supports HTTP (`/mcp` path) and SSE variants if the host requires them.
- The server identifies as `shell-aliases` and adheres to FastMCP’s MCP semantics.

**Example Calls**
- List catalog (tool):
  - Tool name: `alias.catalog`
  - Args: none
- Dry-run `list-branches` with extra args:
  - Tool name: `alias.exec`
  - Args: `{ "name": "list-branches", "args": "-a", "dry_run": true }`
- Execute a safe alias in a project directory (only with authorization):
  - Tool name: `alias.exec`
  - Args: `{ "name": "fmt-all", "cwd": "~/project", "dry_run": false, "confirm": true, "timeout_seconds": 20 }`

**Security Model**
- Allowlist-only safety classification via regex against the alias expansion.
- Execution sandboxing: constrained environment, bounded outputs, timeouts, cwd allowlist.
- Audit logging to a JSONL file for traceability.

