#!/usr/bin/env bash

# Run the full project test suite (lint, type-check, tests with coverage).
#
# - Prefers the repo's virtualenv at .venv if present
# - Falls back to system-installed tools if not
# - Skips optional steps (ruff/mypy) if tools are not installed

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Select Python and Pip
if [[ -x "$ROOT_DIR/.venv/bin/python" ]]; then
  PY="$ROOT_DIR/.venv/bin/python"
  PIP="$ROOT_DIR/.venv/bin/pip"
else
  PY="$(command -v python3 || command -v python)"
  PIP="$(command -v pip3 || command -v pip || echo "")"
fi

echo "==> Using Python: $($PY -V 2>&1)"
if [[ -n "${PIP}" ]]; then
  echo "==> Using Pip: $($PIP --version 2>/dev/null || echo 'pip not found')"
fi

# Resolve tool commands with preference for the venv
cmd_or_venv() {
  local name="$1"
  if [[ -x "$ROOT_DIR/.venv/bin/$name" ]]; then
    echo "$ROOT_DIR/.venv/bin/$name"
    return 0
  fi
  if command -v "$name" >/dev/null 2>&1; then
    command -v "$name"
    return 0
  fi
  return 1
}

# 1) Lint (ruff) — optional
if RUFF_BIN=$(cmd_or_venv ruff); then
  echo "\n==> Running ruff lint"
  "$RUFF_BIN" check mcp_shell_aliases tests
else
  echo "\n==> Ruff not found; skipping lint (optional)."
fi

# 2) Type checking (mypy) — optional
if MYPY_BIN=$(cmd_or_venv mypy); then
  echo "\n==> Running mypy type checks"
  "$MYPY_BIN" mcp_shell_aliases
else
  echo "\n==> Mypy not found; skipping type checks (optional)."
fi

# 3) Tests with coverage (pytest)
if PYTEST_BIN=$(cmd_or_venv pytest); then
  echo "\n==> Running pytest with coverage"
  "$PYTEST_BIN" --cov=mcp_shell_aliases --cov-report=term-missing -ra "$@"
else
  echo "\n==> pytest not found; attempting via python -m pytest"
  "$PY" -m pytest --cov=mcp_shell_aliases --cov-report=term-missing -ra "$@"
fi

echo "\n==> All steps completed"
