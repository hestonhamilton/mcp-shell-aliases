
# Packaging & Dependency Strategies for a Python FastMCP Server as a Gemini CLI Extension

> Goal: ship an extension that **just works** when installed via `gemini extensions install ...`—with minimal friction for end users—while keeping your developer workflow sane.

---

## TL;DR: Which method should you use?

- **You want zero-runtime-deps UX:** Ship **per‑platform binaries** (PyInstaller/Nuitka). Users don’t need Python or `pip`. Highest polish; heavier release process.
- **You’re OK requiring a system Python but want no `pip install`:** Ship a **self‑contained single file** with **PEX** or **Shiv** (zipapp). One artifact; Python required.
- **You prefer a “smart runner” that auto-resolves deps:** Use **`uvx`** (from Astral’s `uv`) to run your published package. Fast, cached, no manual venvs. Requires `uv` on the host.
- **You want to keep current layout with least change:** Use a tiny **bootstrap script with `uv`** to create a local venv and install deps on first run. Still self‑contained inside the extension folder and very fast.

---

## The Extension Contract (How Gemini CLI Runs Your Server)

Gemini CLI extensions define how to **start** your MCP server via `gemini-extension.json`:
- `mcpServers.<name>.command` — the executable to run
- `args` — arguments to pass
- `cwd` — working directory
- You can use variables like `${extensionPath}` and `${/}` to build portable paths.

Gemini doesn’t manage Python envs. Your extension must make sure the runtime + deps exist and the server starts reliably.

---

## Method 1 — Prebuilt Per‑Platform Binaries (PyInstaller / Nuitka)

**Idea:** Compile your FastMCP server (and its deps) into a native executable per OS/arch. Ship those binaries in GitHub Releases or directly in the repo.

### Pros
- **Zero friction**: no Python, no `pip`, no venv.
- **Fast startup** and consistent behavior.
- **Security**: no dynamic install step from the network at runtime.

### Cons
- **Multiple artifacts**: build for linux‑x86_64, linux‑arm64, darwin‑arm64, windows‑amd64, etc.
- **Large binaries** compared to source.
- Some packages with native extensions can be tricky to bundle.

### Example layout
```
fastmcp-ext/
  gemini-extension.json
  run            # POSIX launcher
  run.ps1        # Windows launcher
  bin/
    fastmcp-linux-x86_64
    fastmcp-linux-arm64
    fastmcp-darwin-arm64
    fastmcp-windows-amd64.exe
```

### `gemini-extension.json`
```json
{
  "name": "fastmcp-binary",
  "version": "0.1.0",
  "mcpServers": {
    "aliases": {
      "command": "${extensionPath}${/}run",
      "cwd": "${extensionPath}"
    }
  }
}
```

### `run` (POSIX; detect platform and exec)
```bash
#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

uname_s=$(uname -s | tr '[:upper:]' '[:lower:]')
uname_m=$(uname -m)

case "${uname_s}-${uname_m}" in
  linux-x86_64) bin="bin/fastmcp-linux-x86_64" ;;
  linux-aarch64|linux-arm64) bin="bin/fastmcp-linux-arm64" ;;
  darwin-arm64) bin="bin/fastmcp-darwin-arm64" ;;
  *) echo "Unsupported platform: ${uname_s}-${uname_m}" >&2; exit 1 ;;
esac

exec "${bin}"
```

### `run.ps1` (Windows)
```powershell
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
$arch = (Get-CimInstance Win32_Processor).AddressWidth
$bin = "bin\fastmcp-windows-amd64.exe"
& $bin
```

### Build notes
- **PyInstaller**: `pyinstaller --onefile server.py`
- **Nuitka**: `python -m nuitka --onefile server.py`
- Automate matrix builds via GitHub Actions; upload artifacts to Releases.
- Keep versioning in sync with `gemini-extension.json` for clear updates.

---

## Method 2 — Self‑Contained Python Artifact (PEX / Shiv / Zipapp)

**Idea:** Bundle your code + deps into one file run by `python`, without `pip install`.

### Pros
- Single‑file deploy per target Python/ABI.
- No network install step at runtime.
- Smaller than native binaries; faster to produce.

### Cons
- Requires a suitable **system Python** at runtime.
- Platform/ABI compatibility matters (e.g., manylinux wheels).
- Slightly slower start than a native binary.

### `gemini-extension.json`
```json
{
  "name": "fastmcp-pex",
  "version": "0.1.0",
  "mcpServers": {
    "aliases": {
      "command": "python",
      "args": ["${extensionPath}${/}server.pex"],
      "cwd": "${extensionPath}"
    }
  }
}
```

### Build notes
- **PEX**: build with a lockfile for reproducibility; target the Python version your users have.
- **Shiv**: similar approach using zipapps; add a console entry point (`-c fastmcp_server:main`).
- Test on clean hosts with only system Python installed.

---

## Method 3 — Smart Runner with `uvx` (Package and Run on Demand)

**Idea:** Publish your MCP server as a Python package (`pyproject.toml` with a console script). At runtime, **`uvx`** resolves and caches deps, then runs your entry point—**no explicit venv** and no manual `pip`.

### Pros
- **Great UX** once `uv` is present: one command that just runs.
- **Very fast** because `uv` uses a resolver + wheel cache.
- Cached envs make subsequent runs instant.
- **Simple updates**: bump the version pin and users get the new package.

### Cons
- Requires **`uv` installed** on the host (small but real prerequisite).
- First run downloads wheels if not cached.

### `gemini-extension.json`
```json
{
  "name": "fastmcp-uvx",
  "version": "0.1.0",
  "mcpServers": {
    "aliases": {
      "command": "uvx",
      "args": ["your-mcp-package@1.2.3", "serve"],
      "cwd": "${extensionPath}"
    }
  }
}
```

### Package setup (excerpt)
```toml
# pyproject.toml
[project]
name = "your-mcp-package"
version = "1.2.3"
dependencies = ["fastmcp", "any-other-deps"]

[project.scripts]
serve = "your_mcp_package.server:main"
```

### Tips
- Consider a **compatibility fallback**: if `uvx` not found, print a clear message or shell-out to a bootstrap installer for `uv`.
- Pin `your-mcp-package@exact` for deterministic behavior; optionally allow `@latest` for rapid iteration.

---

## Method 4 — `uv`-Backed Local Venv Bootstrap (Minimal Changes, Fast Installs)

**Idea:** Keep your current repo layout but switch your first‑run bootstrap from `pip` to **`uv`** for speed and reliability. Still lives inside the extension’s directory, still invisible to the user.

### Pros
- Very fast env creation and installation (`uv venv`, `uv pip`).
- Works offline after first install (wheel cache).
- No system‑wide impact; everything lives under the extension path.

### Cons
- Still creates a venv (some disk footprint).
- Requires `uv` present on the host, or you script a quick install.

### `gemini-extension.json`
```json
{
  "name": "fastmcp-uv-venv",
  "version": "0.1.0",
  "mcpServers": {
    "aliases": {
      "command": "${extensionPath}${/}run.sh",
      "cwd": "${extensionPath}"
    }
  }
}
```

### `run.sh`
```bash
#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

if ! command -v uv >/dev/null 2>&1; then
  echo "This extension needs 'uv'. Install from https://docs.astral.sh/uv/"
  exit 1
fi

uv venv .venv
. .venv/bin/activate
uv pip install -r requirements.txt

exec python server.py
```

### Windows `run.ps1`
```powershell
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
  Write-Host "This extension needs 'uv'. Install from https://docs.astral.sh/uv/"
  exit 1
}
uv venv .venv
. .venv/Scripts/Activate.ps1
uv pip install -r requirements.txt
python server.py
```

---

## Comparison Matrix

| Criterion | Per‑Platform Binaries | PEX/Shiv Single File | `uvx` Package Runner | `uv` Local Venv Bootstrap |
|---|---|---|---|---|
| Requires system Python | No | Yes | Not strictly (but `uv` needs a runtime) | Yes (inside venv) |
| Requires `uv` | No | No | **Yes** | **Yes** |
| First‑run network | No | No | **Yes** (on first resolve) | **Yes** (if wheels not cached) |
| End‑user friction | **Lowest** | Low | Low (after installing `uv`) | Low (after installing `uv`) |
| Release complexity | **High** (per‑OS builds) | Medium | Medium (publish to PyPI or index) | Low |
| Startup speed | **Fastest** | Fast | Fast (cached) | Fast |
| Disk footprint | Medium–High | Low–Medium | Low (shared cache) | Medium (venv per install) |
| Debuggability | Medium (compiled) | High (pure Python) | High (pure Python) | High (pure Python) |
| Reproducibility | High | High (locked) | High (pinned versions) | High (locked requirements) |

---

## Versioning & Updates

- **Binaries**: bump version, build new artifacts, attach to Release. Users run `gemini extensions update` to pull the latest.
- **PEX/Shiv**: rebuild `server.pex` with locked deps. Consider embedding the version into filename.
- **`uvx`**: pin `your-mcp-package@1.2.3`. Updating is as simple as bumping to `@1.2.4` in `gemini-extension.json`.
- **`uv` venv**: lock with `uv pip compile` (or `pip-tools`) and ship `requirements.lock`. Update the lock and re-run bootstrap.

---

## Security Considerations

- Prefer **immutable artifacts** (binaries or PEX) to reduce runtime supply-chain surface.
- If resolving at runtime (`uvx`/`uv`), use **pinned versions** and consider **hash‑pinned** lock files.
- Never embed API secrets in the extension. Read tokens from environment variables or OS keychains.
- Validate inputs to tools/resources your server exposes; MCP clients may pass user content.

---

## CI/CD Suggestions

- **GitHub Actions** matrix builds:
  - PyInstaller/Nuitka: build per target, upload to Release.
  - PEX/Shiv: build per Python/ABI target; attach to Release.
  - `uvx`: publish to PyPI (or your index) on tag; then update `gemini-extension.json` with the new version pin.
- Add smoke tests that launch the server and run a minimal MCP handshake to ensure the artifact boots.

---

## Troubleshooting Checklist

- **“Command not found”**: Verify `command` and platform launcher names; on Windows use `.exe` and ensure PowerShell script execution policy allows `run.ps1` (or provide a `.cmd`).
- **“Python not found”** (PEX/Shiv): Document the minimal Python requirement (e.g., 3.10+).
- **“uv not found”**: Print a friendly one-liner to install `uv` and exit gracefully.
- **SSL/cert issues** on corporate networks: instruct users how to configure `pip/uv` to trust corporate CAs or use offline wheel caches.
- **Native deps**: For SciPy/NumPy/etc., prefer wheels compatible with your target (manylinux, macOS universal2) or prebuild into binaries.

---

## Decision Guide

Choose the **binary** route if you want the cleanest UX and can afford CI complexity.  
Choose **PEX/Shiv** if you can assume Python exists and you want a single drop‑in file.  
Choose **`uvx`** if you love simple packaging and fast, cached resolution with a small prerequisite.  
Choose **`uv` venv bootstrap** if you want to keep your current repo setup but make first run snappy and automated.

---

## Minimal Scaffolds

### PyInstaller Binary
```bash
pyinstaller --onefile server.py
# Copy dist/server to bin/fastmcp-<platform>
```

### PEX
```bash
pex . -r requirements.txt -m your_mcp_module:main -o server.pex
```

### Publish for `uvx`
```toml
# pyproject.toml
[project]
name = "your-mcp-package"
version = "1.2.3"
dependencies = ["fastmcp"]

[project.scripts]
serve = "your_mcp_package.server:main"
```
```bash
# then `python -m build` and `twine upload dist/*`
```

### `uv` Bootstrap
```bash
uv venv .venv
. .venv/bin/activate
uv pip install -r requirements.txt
python server.py
```

---

## Example `gemini-extension.json` Snippets

**Binary:**
```json
{ "mcpServers": { "aliases": { "command": "${extensionPath}${/}run" } } }
```

**PEX/Shiv:**
```json
{ "mcpServers": { "aliases": { "command": "python", "args": ["${extensionPath}${/}server.pex"] } } }
```

**uvx:**
```json
{ "mcpServers": { "aliases": { "command": "uvx", "args": ["your-mcp-package@1.2.3", "serve"] } } }
```

**uv venv bootstrap:**
```json
{ "mcpServers": { "aliases": { "command": "${extensionPath}${/}run.sh" } } }
```

---

## Final Recommendation

For a public, user‑friendly extension: **Binaries** (best UX) or **`uvx`** (best developer ergonomics).  
For internal or dev audiences where Python is a given: **PEX/Shiv**.  
For incremental migration from your current setup: **`uv` bootstrap**.

Happy shipping. May your MCP tools be sharp and your installs boring.
