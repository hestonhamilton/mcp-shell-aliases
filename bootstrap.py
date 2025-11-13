#!/usr/bin/env python3
"""
Bootstrap launcher for the MCP Shell Aliases server.

This script ensures a local virtual environment exists under the extension
directory, installs minimal runtime dependencies, and then execs the server
in stdio (or whichever transport is requested via flags passed through).

It is intended to be invoked by Gemini's `extensions install` runtime via the
`gemini-extension.json` mcp_server.command field.
"""

from __future__ import annotations

import os
import shlex
import subprocess
import sys
from pathlib import Path


def _which(executable: str) -> str:
    from shutil import which

    path = which(executable)
    if not path:
        raise RuntimeError(f"Required executable '{executable}' not found in PATH")
    return path


def ensure_venv(venv_dir: Path) -> Path:
    venv_python = venv_dir / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if venv_python.exists():
        return venv_python

    venv_dir.mkdir(parents=True, exist_ok=True)
    # Create venv
    subprocess.run([sys.executable, "-m", "venv", str(venv_dir)], check=True)

    # Upgrade pip and install minimal runtime deps
    pip = [str(venv_python), "-m", "pip"]
    subprocess.run(pip + ["install", "--upgrade", "pip"], check=True)

    # Prefer requirements.runtime.txt if present, otherwise install the package locally.
    repo_root = Path(__file__).resolve().parent
    runtime_reqs = repo_root / "requirements.runtime.txt"
    if runtime_reqs.exists():
        subprocess.run(pip + ["install", "-r", str(runtime_reqs)], check=True)
        # Install the package itself in editable mode so local sources are used.
        subprocess.run(pip + ["install", "-e", str(repo_root)], check=True)
    else:
        # Fallback: install the local project (declared deps in pyproject.toml)
        subprocess.run(pip + ["install", "-e", str(repo_root)], check=True)

    return venv_python


def main(argv: list[str]) -> int:
    repo_root = Path(__file__).resolve().parent
    venv_dir = repo_root / ".venv"

    try:
        venv_python = ensure_venv(venv_dir)
    except Exception as exc:  # keep bootstrap output simple for host UIs
        print(f"[bootstrap] Failed to prepare virtualenv: {exc}", file=sys.stderr)
        return 1

    # Build the exec command: venv python -m mcp_shell_aliases <args>
    cmd = [str(venv_python), "-u", "-m", "mcp_shell_aliases"] + argv

    # Ensure unbuffered stdio and a clean environment suitable for MCP stdio.
    env = os.environ.copy()
    env.setdefault("PYTHONUNBUFFERED", "1")

    # Exec the server process
    try:
        # Use replace to give the child the same PID when supported.
        if hasattr(os, "execvpe"):
            os.execvpe(cmd[0], cmd, env)
        else:
            # Windows fallback
            proc = subprocess.Popen(cmd, env=env)
            return proc.wait()
    except Exception as exc:
        print(f"[bootstrap] Failed to exec server: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

