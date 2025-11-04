# Testing.md — MCP “Bash Aliases as Tools” (Python/FastMCP)

This document describes a **complete testing strategy** for a Python/FastMCP server that exposes shell aliases as tools and resources. It covers unit, contract, integration, end‑to‑end (E2E) smoke tests, security checks, fuzzing, coverage, and CI. All examples assume **pytest + pytest‑asyncio** with a temporary `$HOME` per test so runs are hermetic and do not touch your real shell config.

> Philosophy: keep the MCP transport thin and test the **core logic directly**; add a small black‑box smoke test over stdio to prove the wiring.

---

## 1) Test Pyramid & Scope

**Layers (top→bottom):**
1. **E2E smoke (stdio)** – spawn the FastMCP server as a subprocess and call a single tool & resource. (~1–2 tests)
2. **Contract tests (core handlers)** – call `alias_exec(...)`, `catalog()`, `alias_detail(...)` directly. (majority of behavior)
3. **Unit tests** – parser, safety policy, sandbox (timeout/truncation), env/cwd validation.
4. **Security tests** – denylist enforcement, env‑scrubbing, path constraints.
5. **Fuzzing / property tests** – randomized `args` strings & expansions (Hypothesis).

**Non‑goals:** Testing FastMCP or JSON‑RPC serialization itself. We assume the library is correct; we only do a smoke check.

---

## 2) Project Layout (test‑friendly)

```
mcp_bash_aliases/
  core/
    parse.py          # parse_aliases(files) -> list[Alias]
    policy.py         # allow/deny helpers
    sandbox.py        # exec_alias(aliases_map, input) -> result
    resources.py      # catalog(), alias_detail(name)
    types.py          # dataclasses/TypedDict for Alias/Exec* types
    config.py         # typed config loader with defaults (pure)
  server.py           # FastMCP wiring (@tool, @resource), calls core
tests/
  conftest.py
  unit/
    test_parse.py
    test_policy.py
    test_sandbox.py
    test_resources.py
  contract/
    test_tool_alias_exec.py
    test_resources_contract.py
  e2e/
    test_stdio_smoke.py
```

> Keep **core** pure and importable. `server.py` should be thin: it builds the alias catalog, registers tools/resources, and calls core functions.

---

## 3) Dependencies

Add to your `pyproject.toml`:

```toml
[project.optional-dependencies]
test = [
  "pytest>=8.0",
  "pytest-asyncio>=0.23",
  "pytest-cov>=5.0",
  "hypothesis>=6.100",
  "ruff>=0.6",
  "mypy>=1.10"
]
```

Optional dev tools:
- `pre-commit` for ruff/black hooks
- `nox` or `tox` for matrix testing Python 3.10–3.12

---

## 4) Pytest Configuration

`pytest.ini`:
```ini
[pytest]
addopts = -ra -q --strict-markers --cov=mcp_bash_aliases --cov-report=term-missing
asyncio_mode = auto
testpaths = tests
```

`conftest.py` (key fixtures):
```python
# tests/conftest.py
import os, pathlib, json, shutil, tempfile, contextlib
import pytest

@pytest.fixture
def temp_home(monkeypatch, tmp_path):
    # Create a private HOME for each test
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    return home

@pytest.fixture
def write_aliases(temp_home):
    def _write(lines: list[str], fname: str = ".bash_aliases"):
        p = temp_home / fname
        p.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return p
    return _write

@pytest.fixture
def allow_patterns():
    # mirror your config defaults
    return [r"^ls\b", r"^cat\b", r"^git\b(?!\s+(push|reset|rebase|clean))", r"^grep\b", r"^rg\b"]

@pytest.fixture
def deny_patterns():
    return [r"^rm\b", r"^dd\b", r"^shutdown\b", r"^reboot\b", r"^sudo\b"]

@pytest.fixture
def config_defaults(monkeypatch, tmp_path):
    # If core.config.get_config reads environment/file, steer it to tmp inputs
    monkeypatch.setenv("MCP_DEFAULT_CWD", str(tmp_path))
    monkeypatch.setenv("MCP_STDOUT_MAX", "10000")
    monkeypatch.setenv("MCP_STDERR_MAX", "10000")
    monkeypatch.setenv("MCP_TIMEOUT_SECONDS", "20")
```

---

## 5) Unit Tests (examples)

### 5.1 Parse

```python
# tests/unit/test_parse.py
from mcp_bash_aliases.core.parse import parse_aliases

def test_parse_single_and_double_quotes(write_aliases, allow_patterns, deny_patterns, temp_home):
    write_aliases([
        "alias ll='ls -lhF --color=auto'",
        'alias gs="git status"',
        "alias bad='rm -rf /'"
    ])
    files = [str(temp_home / ".bash_aliases")]
    aliases = parse_aliases(files, allow_patterns, deny_patterns)
    names = {a.name for a in aliases}
    assert {"ll", "gs", "bad"} <= names
    ll = next(a for a in aliases if a.name == "ll")
    assert ll.safe is True
    bad = next(a for a in aliases if a.name == "bad")
    assert bad.safe is False
```

### 5.2 Sandbox (timeouts / truncation / cwd)

```python
# tests/unit/test_sandbox.py
import os, asyncio
import pytest
from mcp_bash_aliases.core.sandbox import exec_alias

@pytest.mark.asyncio
async def test_dry_run_default(tmp_path, temp_home):
    aliases = {"ll": {"expansion": "ls -lh", "safe": True}}
    res = await exec_alias(aliases, {"name":"ll", "args": str(tmp_path)})
    assert res["stdout"] == ""
    assert res["exitCode"] == 0
    assert res["timedOut"] is False

@pytest.mark.asyncio
async def test_timeout_enforced(temp_home):
    aliases = {"sleepy": {"expansion": "sleep 2", "safe": True}}
    res = await exec_alias(aliases, {"name":"sleepy", "dryRun": False, "timeoutSeconds": 1})
    assert res["timedOut"] is True

@pytest.mark.asyncio
async def test_cwd_restricted(temp_home):
    aliases = {"pwd": {"expansion": "pwd", "safe": True}}
    res = await exec_alias(aliases, {"name":"pwd", "dryRun": False, "cwd": "/"})
    # Should fallback to HOME (not /), depending on your policy
    assert str(temp_home) in res["stdout"]
```

### 5.3 Resources

```python
# tests/unit/test_resources.py
from mcp_bash_aliases.core.resources import catalog_resource, alias_detail_resource
from types import SimpleNamespace

def test_catalog_json_shape():
    data = [SimpleNamespace(name="ll", expansion="ls -lh", safe=True, sourceFile="/x")]
    text = catalog_resource(data)
    assert '"name": "ll"' in text

def test_alias_detail_text():
    from types import SimpleNamespace
    txt = alias_detail_resource(SimpleNamespace(name="ll", expansion="ls -lh", safe=True, sourceFile="/x"))
    assert "example: alias.exec" in txt
```

---

## 6) Contract Tests (handlers directly)

```python
# tests/contract/test_tool_alias_exec.py
import asyncio, pytest
from mcp_bash_aliases.server import alias_exec  # FastMCP @tool function

@pytest.mark.asyncio
async def test_default_dry_run(temp_home, write_aliases):
    write_aliases(["alias ll='ls -lh'"])
    res = await alias_exec(name="ll", args=".")
    assert res.get("dryRun") is True
    assert "ls -lh" in res["command"]

@pytest.mark.asyncio
async def test_block_unsafe(temp_home, write_aliases):
    write_aliases(["alias nuke='rm -rf /'"])
    res = await alias_exec(name="nuke", dryRun=False)
    assert "not marked safe" in (res.get("error") or "").lower()
```

Resource contracts:

```python
# tests/contract/test_resources_contract.py
from mcp_bash_aliases.server import catalog, alias_detail  # FastMCP @resource funcs

def test_catalog_resource(temp_home, write_aliases):
    write_aliases(["alias ll='ls -lh'"])
    text = catalog()
    assert "ll" in text

def test_alias_detail_resource(temp_home, write_aliases):
    write_aliases(["alias gs='git status'"])
    text = alias_detail("gs")
    assert "git status" in text
```

---

## 7) E2E Smoke (stdio)

Spawn `python -m mcp_bash_aliases.server` and hit a **test‑only HTTP probe** (guard with `MCP_TEST_HTTP=1`) to avoid writing your own JSON‑RPC probe for stdio.

```python
# tests/e2e/test_stdio_smoke.py
import json, os, subprocess, sys, time, urllib.request, pytest

@pytest.mark.timeout(10)
def test_smoke_alias_exec(temp_home, write_aliases):
    write_aliases(["alias echohi='printf hello'"])
    env = os.environ.copy()
    env["MCP_TEST_HTTP"] = "1"  # server starts a tiny HTTP probe on 127.0.0.1:35671
    p = subprocess.Popen([sys.executable, "-m", "mcp_bash_aliases.server"],
                         cwd=str(temp_home), env=env)
    try:
        time.sleep(0.6)  # allow boot
        req = urllib.request.Request("http://127.0.0.1:35671/tools/alias.exec",
                                     data=json.dumps({"name":"echohi","dryRun": False}).encode("utf-8"),
                                     headers={"Content-Type":"application/json"})
        with urllib.request.urlopen(req, timeout=2) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            assert "hello" in body.get("stdout","")
    finally:
        p.kill()
```

> If you prefer pure stdio: include a tiny test client that sends a single JSON‑RPC request to the process’s stdin and reads stdout. Keep it to *one* smoke test.

---

## 8) Security Tests

```python
# tests/unit/test_security.py
import pytest
from mcp_bash_aliases.core.sandbox import exec_alias

@pytest.mark.asyncio
async def test_denylist_enforced(temp_home, write_aliases):
    write_aliases(["alias dangerous='rm -rf ~'"])
    aliases = {"dangerous": {"expansion":"rm -rf ~", "safe": False}}
    res = await exec_alias(aliases, {"name":"dangerous", "dryRun": False})
    assert "not marked safe" in (res.get("error") or "").lower()

@pytest.mark.asyncio
async def test_env_scrubbed(temp_home, monkeypatch):
    # Enable only if you scrub env in sandbox; otherwise mark xfail and document in SECURITY.md
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "SUPERSECRET")
    aliases = {"printenv": {"expansion": "env", "safe": True}}
    res = await exec_alias(aliases, {"name":"printenv", "dryRun": False})
    assert "SUPERSECRET" not in res["stdout"]
```

---

## 9) Fuzzing / Property Tests (Hypothesis)

```python
# tests/unit/test_fuzz_args.py
import pytest
from hypothesis import given, strategies as st
from mcp_bash_aliases.core.sandbox import exec_alias

@pytest.mark.asyncio
@given(st.text(alphabet=st.characters(blacklist_categories=["Cs"]), min_size=0, max_size=256))
async def test_args_do_not_crash(random_args):
    aliases = {"echo": {"expansion": "printf", "safe": True}}
    res = await exec_alias(aliases, {"name":"echo", "args": random_args, "dryRun": True})
    assert "printf" in res["command"]
```

---

## 10) Coverage Targets

- **Line** ≥ 90%
- **Branches** ≥ 80%
- Enforce in CI: `--cov-fail-under=90`

`pytest.ini`:
```ini
addopts = --cov=mcp_bash_aliases --cov-report=term-missing --cov-fail-under=90
```

---

## 11) Linters & Types

- **ruff**: `ruff check mcp_bash_aliases tests`
- **mypy** strict for `core/`

`pyproject.toml`:
```toml
[tool.ruff]
line-length = 100
target-version = "py311"

[tool.mypy]
strict = true
packages = ["mcp_bash_aliases/core"]
```

---

## 12) Makefile / Nox

```make
.PHONY: test lint type cov e2e
lint:
\truff check mcp_bash_aliases tests
type:
\tmypy mcp_bash_aliases/core
test:
\tpytest -q
e2e:
\tpytest -q tests/e2e
cov:
\tpytest --cov=mcp_bash_aliases --cov-report=xml
```

---

## 13) GitHub Actions CI

`.github/workflows/tests.yml`:
```yaml
name: tests
on:
  push: { branches: [ main ] }
  pull_request: { branches: [ main ] }
jobs:
  pytests:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: [ "3.10", "3.11", "3.12" ]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: ${{ matrix.python-version }} }
      - run: python -m pip install -U pip
      - run: pip install .[test]
      - run: ruff check mcp_bash_aliases tests
      - run: mypy mcp_bash_aliases/core || true
      - run: pytest -q --cov=mcp_bash_aliases --cov-report=term-missing --cov-fail-under=90
```

---

## 14) Local Dev Loop

1. `pip install -e .[test]`
2. `pytest -q` (fast; hermetic HOME)
3. `pytest tests/contract -q` when changing server handlers
4. `pytest tests/e2e -q` after transport changes
5. `ruff check` + `mypy` before push

---

## 15) Acceptance (CI gate)

- ✅ Unit + contract pass
- ✅ E2E smoke passes
- ✅ Coverage ≥ 90%
- ✅ Ruff clean; types acceptable
- ✅ No test touches real `$HOME` or network

---

This plan gives you **fast, deterministic** feedback on real behavior while keeping the full MCP stdio stack under a tiny, reliable smoke test—no manual Gemini sessions required.
