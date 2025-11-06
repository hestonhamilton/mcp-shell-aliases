# Copyright (C) 2025 Heston Hamilton

from __future__ import annotations

from pathlib import Path

from mcp_shell_aliases.aliases import build_catalog
from mcp_shell_aliases.safety import SafetyClassifier


def classifier() -> SafetyClassifier:
    return SafetyClassifier.from_strings([r"^ls\\b"], [r"^rm\\b"])


def test_parses_aliases(tmp_path: Path) -> None:
    alias_file = tmp_path / "aliases"
    alias_file.write_text(
        """
        alias ll='ls -al'
        alias dangerous='rm -rf /'
        # comment should be ignored
        alias invalid-name='echo nope'
        """,
        encoding="utf-8",
    )

    catalog = build_catalog([alias_file], classifier())
    aliases = {alias.name: alias for alias in catalog.all()}

    assert "ll" in aliases
    assert aliases["ll"].safe is True
    assert aliases["dangerous"].safe is False
    assert "invalid-name" not in aliases


def test_prioritises_last_definition(tmp_path: Path) -> None:
    first = tmp_path / "aliases1"
    second = tmp_path / "aliases2"
    first.write_text("alias ll='ls -al'", encoding="utf-8")
    second.write_text("alias ll='ls -a'", encoding="utf-8")

    catalog = build_catalog([first, second], classifier())
    alias = catalog.get("ll")
    assert alias is not None
    assert alias.expansion == "ls -a"
    assert alias.source_file == second
