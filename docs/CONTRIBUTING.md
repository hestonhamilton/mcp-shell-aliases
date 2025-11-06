# Contributing

Thanks for your interest in improving MCP Shell Aliases!

## Development Setup

1. Create a virtual environment and install the project in editable mode:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -e .[dev]
   ```
2. Run tests and linters before sending a PR:
   ```bash
   pytest
   ruff check .
   mypy mcp_shell_aliases
   ```

## Code Style

- Keep functions small and focused.
- Add type hints everywhere.
- Include tests for new behavior and safety rules.

## Commit Messages

Follow Conventional Commits when possible (`feat:`, `fix:`, etc.).

We appreciate your contributions!
