# TODO.md — MCP “Bash Aliases as Tools” Server

This document describes the end-to-end plan to design, implement, harden, test, package, and integrate an MCP server that exposes shell aliases as safe, discoverable tools for AI hosts.

---

## 0) Project Setup

- [x] **Pick language & SDK**
  - Python: FastMCP
- [x] **Initialize repo**
  - Py:
    ```bash
    mkdir mcp-bash-aliases && cd $_
    uv venv || python -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
    ```
- [x] **Repo hygiene**
  - Add `.editorconfig`, `.gitignore`, `LICENSE`, `CONTRIBUTING.md`.
  - Set `package.json` or `pyproject.toml` scripts for `build`, `start:stdio`, `test`, `lint`.

---

## 1) Requirements & Threat Model

- [x] **Functional goals** (prompts deferred to later milestone)
  - Parse and catalog shell aliases from explicit files (e.g., `~/.bash_aliases`, `~/.bashrc`, `/etc/bash.bashrc`).
  - Expose:
    - **Tools**: execute a chosen alias with optional args (default to dry-run).
    - **Resources**: `alias://catalog` (JSON list) and `alias://{name}` (details).
    - **Prompts** (optional): “suggest” and “confirm” flows.
- [x] **Non-functional goals**
  - Safety by default (allowlist, dry-run, timeouts, env scrub, audit logs).
  - Deterministic behavior across hosts (stdio transport).
- [x] **Threat model**
  - Prevent destructive commands.
  - Avoid leaking secrets via environment or output.
  - Constrain execution context (PATH, CWD, time, output size).

---

## 2) Data Model & Config

- [x] **Alias object**
  ```ts
  type Alias = {
    name: string
    expansion: string
    safe: boolean           // computed via allowlist rules
    sourceFile: string      // provenance
  }
  ```
- [x] **Config file** `config.yaml` (or JSON/TOML)
  - `aliasFiles`: list of absolute paths to parse.
  - `allowPatterns`: regex list that marks expansions as “safe”.
  - `denyPatterns`: regex list for hard blocks.
  - `defaultCwd`: default working directory (e.g., `$HOME`).
  - `maxStdoutBytes`/`maxStderrBytes` (e.g., 10000).
  - `defaultTimeoutSeconds` (e.g., 20).
  - `auditLogPath` (e.g., `~/.local/state/mcp-bash-aliases/audit.log`).
  - `enableHotReload: true|false`.
- [x] **Load config with precedence**
  1. CLI flags → 2. Env vars → 3. Project config file → 4. Built-in defaults.

---

## 3) Alias Discovery & Parsing

- [x] **Implement parser**
  - Parse only **explicitly configured** files.
  - Regex for aliases: `^alias\s+([A-Za-z0-9_\-]+)='([^']+)'$` (and support double quotes).
  - Record `sourceFile` for each alias; later used for debugging.
- [x] **Deduplication & conflicts**
  - Later files override earlier ones or log a warning; document the policy.
- [x] **Sanitization**
  - Trim whitespace; reject names with spaces or shell metacharacters.
- [x] **Allowlist/denylist computation**
  - `safe = matches(allowPatterns) && !matches(denyPatterns)`.

---

## 4) Execution Sandbox & Safety Rails

- [x] **Dry-run by default**
  - Tools execute in simulation unless `dryRun: false && confirm: true`.
- [x] **Allowlist enforcement**
  - If `safe === false`, permit **only** dry-run; return an error if execution requested.
- [x] **Command construction**
  - Build final command as: `<expansion> <args>`; do **not** re-quote user args internally.
  - Execute with `/bin/bash -lc "<cmd>"` to resolve aliases/functions consistently.
- [x] **Environment scrubbing**
  - Minimal `PATH` (e.g., `/usr/bin:/bin`).
  - Drop all non-essential env vars; optionally pass through `LANG`, `LC_*`, `HOME`.
- [x] **Working directory**
  - If `cwd` provided, require it to be within an allowlisted root (e.g., `$HOME`); else use default.
- [x] **Timeouts & truncation**
  - Kill process after `timeoutSeconds`.
  - Truncate `stdout`/`stderr` to configured byte limits.
- [x] **Return structure**
  ```json
  {
    "command": "git status",
    "exitCode": 0,
    "stdout": "...",
    "stderr": "",
    "truncated": { "stdout": false, "stderr": false },
    "timedOut": false
  }
  ```
- [x] **Audit logging**
  - Append JSON lines: timestamp, alias, args, cwd, exitCode, timedOut.
  - Redact obvious secrets by pattern (tokens, keys) before writing.

---

## 5) MCP Server: Capabilities & Transport

- [x] **Server metadata**
  - Name: `bash-aliases`
  - Version: semantic versioning starting at `0.1.0`.
- [x] **Capabilities**
  - `tools`: enabled
  - `resources`: enabled
  - `prompts`: optional
- [x] **Transport**
  - Implement **stdio** transport for maximum host compatibility.
- [x] **Graceful shutdown**
  - Handle SIGINT/SIGTERM; flush audit logs.
- [x] **HTTP/SSE transport option**
  - Configurable `transport` option (`stdio`, `http`, `sse`).
  - Allow binding host/port/path for local agent integration (Codex, Gemini CLI).
  - Document config snippets for stdio vs. HTTP transports.

---

## 6) Tools

- [x] **Single generic tool** `alias.exec`
  - **Schema**
    - `name: string` (alias name)
    - `args: string` (optional)
    - `cwd: string` (optional, validated)
    - `dryRun: boolean` (default `true`)
    - `confirm: boolean` (default `false`; required `true` to actually execute)
    - `timeoutSeconds: integer` (bounded)
  - **Behavior**
    - Look up alias; error if not found.
    - If not safe and execution requested → error instructing dry-run or allowlist update.
    - Execute with sandbox rules; return structured result.
- [ ] **Optional: one tool per alias**
  - At startup, dynamically register `alias.<name>` for each safe alias with `args`, `cwd`, `timeoutSeconds`.
  - Pros: nice UX in tool palettes. Cons: many tools; requires hot-reload hooks.

---

## 7) Resources (Browseable Catalog)

- [x] **`alias://catalog`**
  - MIME: `application/json`
  - Body: array of `{ name, expansion, safe, sourceFile }`.
- [x] **`alias://{name}`**
  - MIME: `text/plain` (or JSON)
  - Body: details + example invocation:
    ```
    alias: ll
    expansion: ls -lhF --color=auto
    safe: true
    example: alias.exec { "name":"ll", "args":"~/projects", "dryRun": true }
    ```

---

## 8) Prompts (Optional but Recommended)

- [ ] **`prompt.alias.suggest`**
  - Purpose: guide hosts to browse `alias://catalog`, choose an alias, simulate with `dryRun: true`, summarize.
  - Fields: none.
  - Template: “Browse `alias://catalog`, then propose a safe plan and call `alias.exec` with `dryRun: true` first.”
- [ ] **`prompt.alias.confirm`**
  - Purpose: require explicit confirmation before non-dry runs.
  - Fields: `name`, `args`, `cwd`.
  - Template asks the host to present the would-run command to the user and wait for consent.

---

## 9) Hot Reload (Developer Experience)

- [ ] **File watching**
  - Watch configured alias files; debounce changes (e.g., 250ms).
  - On change: re-parse; recompute safety; update in-memory catalog.
  - If using “one tool per alias,” register/unregister as needed.
- [ ] **Cache invalidation**
  - Keep a hash of last-seen file contents; reload only when different.

---

## 10) Testing

- [x] **Unit tests**
  - Parsing (single/double quotes, comments, whitespace).
  - Allowlist/denylist rules (positive/negative cases).
  - Path and env validation.
- [ ] **Integration tests**
  - Run server over stdio; call:
    - `alias.exec` (dry-run) on safe/unsafe aliases.
    - `alias.exec` with timeout.
    - `alias://catalog` and `alias://{name}` reads.
  - Verify truncation, timeouts, audit logging.
- [ ] **Fuzz tests (lightweight)**
  - Random arg strings to ensure robust quoting and no crashes.
- [ ] **Security tests**
  - Attempt to run denied patterns.
  - Confirm env scrubbing (no sensitive env surfaces in outputs).

---

## 11) Linting, Formatting, CI

- [x] Configure ESLint/ruff and formatter (Prettier/black).
- [ ] CI workflow:
  - Lint → Unit tests → Integration tests.
  - Cache Node/pip dependencies.
  - On `main` push: build artifacts.

---

## 12) Packaging & Distribution

- [ ] **Node**
  - Bundle with `tsc` to `dist/`.
  - Add `"bin": { "mcp-bash-aliases": "dist/server.js" }` in `package.json`.
  - Optional: publish to npm.
- [x] **Python**
  - Define console entry point `mcp-bash-aliases` in `pyproject.toml`.
  - Optional: publish to PyPI.
- [ ] **Versioning**
  - Maintain `CHANGELOG.md`.
  - Follow semver; keep `server_info` in sync.

---

## 13) Host Integration

- [ ] **Configure host (e.g., Gemini CLI, Claude desktop, etc.)**
  - Add MCP server pointing to the executable (stdio).
  - Verify tools list and resource browsing.
- [ ] **Smoke test**
  - Read `alias://catalog`.
  - `alias.exec` with `dryRun: true`.
  - Confirm is required for execution (`confirm: true`).
- [ ] **Workspace docs**
  - Provide a README snippet showing how to register the server with popular hosts.

---

## 14) Observability & Logs

- [ ] **Audit log rotation**
  - Rotate by size (e.g., 5MB × 5).
- [ ] **Structured logs**
  - JSON lines with minimal PII; redact secrets.
- [ ] **Metrics (optional)**
  - Counters for calls, denials, timeouts, errors.

---

## 15) Documentation

- [x] **README**
  - Overview, quick start (Node/Python), config reference, safety model.
  - Examples of tool calls and resource reads.
- [x] **SECURITY.md**
  - Threat model, guarantees, non-goals, reporting process.
- [x] **CONFIGURATION.md**
  - All settings with defaults; allow/deny examples.
- [x] **TROUBLESHOOTING.md**
  - Common errors (no aliases parsed, permission issues, timeouts).
- [x] **EXAMPLES/**
  - Example alias files, example host configs.

---

## 16) Hardening & Polishing

- [ ] **Function support (optional)**
  - Detect `name () { ... }` blocks behind a **separate** opt-in allowlist.
  - Require dry-run; mark unsafe by default.
- [x] **CWD policy**
  - Allow only `$HOME` and subdirectories by default; configurable.
- [x] **Command policy**
  - Explicit denylist for destructive verbs (`rm`, `mv` to `/`, `dd`, `mkfs`, `sudo`, package managers, `reboot`).
- [x] **User messaging**
  - Clear error messages with remediation hints (e.g., “Run in dryRun or add regex to allowPatterns.”).

---

## 17) Release

- [ ] Tag `v0.1.0` after passing tests and manual host verification.
- [ ] Attach build artifacts (if distributing binaries).
- [ ] Publish to npm/PyPI (optional).
- [ ] Update docs with installation and host configuration steps.

---

## 18) Post-Release Roadmap (Optional)

- [ ] **One tool per alias** mode toggle (for hosts with tool palettes).
- [ ] **Hot reload** for dynamic tool registration.
- [ ] **Telemetry (opt-in)**: anonymous usage metrics with clear privacy policy.
- [ ] **Per-workspace policy files** to tailor allow/deny patterns.
- [ ] **Command templates**: per-alias schema for structured args instead of raw `args`.
- [ ] **Containerized execution**: run aliases in a restricted container or user namespace.

---

## Reference CLI Snippets

- **Run (Node)**
  ```bash
  npm run build
  node dist/server.js
  ```
- **Run (Python)**
  ```bash
  python server.py
  ```
- **Quick config example (`config.yaml`)**
  ```yaml
  aliasFiles:
    - ~/.bash_aliases
    - ~/.bashrc
  allowPatterns:
    - '^ls\\b'
    - '^cat\\b'
    - '^git\\b(?!\\s+(push|reset|rebase|clean))'
    - '^grep\\b'
    - '^rg\\b'
  denyPatterns:
    - '^rm\\b'
    - '^dd\\b'
    - '^shutdown\\b'
    - '^reboot\\b'
    - '^sudo\\b'
  defaultCwd: '~'
  defaultTimeoutSeconds: 20
  maxStdoutBytes: 10000
  maxStderrBytes: 10000
  auditLogPath: '~/.local/state/mcp-bash-aliases/audit.log'
  enableHotReload: true
  ```

---

## Acceptance Checklist

- [ ] Safe by default (dry-run, allowlist, env scrub, bounded execution).
- [ ] Tools & resources implemented; prompts available.
- [ ] Deterministic stdio transport; graceful shutdown.
- [ ] Unit, integration, and security tests pass in CI.
- [ ] Clear documentation and troubleshooting.
- [ ] Verified with at least one MCP host end-to-end.

---

Delivering this sequence yields a robust, host-friendly MCP server that models aliases as discoverable, auditable tools with strong safety guarantees and predictable behavior.
