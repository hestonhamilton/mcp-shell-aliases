# Copyright (C) 2025 Heston Hamilton

from __future__ import annotations

from pathlib import Path

from mcp_shell_aliases.aliases import build_catalog
from mcp_shell_aliases.safety import SafetyClassifier


def classifier() -> SafetyClassifier:
    return SafetyClassifier.from_strings([r"^ls\\b"])


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


def test_missing_file_logs_warning_and_returns_empty(caplog, tmp_path: Path) -> None:
    missing = tmp_path / "nope.aliases"
    with caplog.at_level("WARNING"):
        catalog = build_catalog([missing], classifier())
    assert catalog.all() == []
    assert any("does not exist" in rec.message for rec in caplog.records)


def test_skips_non_matching_lines(tmp_path: Path) -> None:
    alias_file = tmp_path / "aliases"
    alias_file.write_text(
        """
        notanalias ll='ls -al'
        alias ok='ls -al'
        """,
        encoding="utf-8",
    )

    catalog = build_catalog([alias_file], classifier())
    names = [a.name for a in catalog.all()]
    assert "ok" in names
    assert all(n != "notanalias" for n in names)


def test_unescape_double_and_unknown_quote() -> None:
    from mcp_shell_aliases.aliases import _unescape

    assert _unescape('a\"b', '"') == 'a"b'
    # Unknown quote char: pass-through
    assert _unescape("a\\nb", "?") == "a\\nb"


def test_head_command_valueerror_returns_none() -> None:
    from mcp_shell_aliases.aliases import _head_command

    assert _head_command("echo 'unterminated") is None


def test_is_command_available_handles_none_and_builtins(monkeypatch) -> None:
    from mcp_shell_aliases.aliases import _is_command_available

    assert _is_command_available(None) is False
    assert _is_command_available("echo") is True


def test_does_not_override_with_unavailable_command(tmp_path: Path, monkeypatch) -> None:
    # First defines ll with a widely available command (ls)
    first = tmp_path / "aliases1"
    first.write_text("alias ll='ls -al'\n", encoding="utf-8")
    # Second attempts to override with mac-only gls
    second = tmp_path / "aliases2"
    second.write_text("alias ll='gls -lhF --color=auto'\n", encoding="utf-8")

    # Simulate availability: ls exists, gls does not
    import mcp_shell_aliases.aliases as aliases_mod

    def fake_which(cmd: str):  # type: ignore[no-untyped-def]
        return "/bin/ls" if cmd == "ls" else None

    monkeypatch.setattr(aliases_mod.shutil, "which", fake_which)

    catalog = build_catalog([first, second], classifier())
    alias = catalog.get("ll")
    assert alias is not None
    assert alias.expansion.startswith("ls ")
    assert alias.source_file == first


def test_override_when_both_unavailable_falls_back_to_last(tmp_path: Path, monkeypatch) -> None:
    # Neither foo nor bar exists; last definition should win per heuristic fallback
    a = tmp_path / "a"
    b = tmp_path / "b"
    a.write_text("alias tool='foo --ver'\n", encoding="utf-8")
    b.write_text("alias tool='bar --ver'\n", encoding="utf-8")

    import mcp_shell_aliases.aliases as aliases_mod

    def fake_which(_cmd: str):  # type: ignore[no-untyped-def]
        return None

    monkeypatch.setattr(aliases_mod.shutil, "which", fake_which)

    catalog = build_catalog([a, b], classifier())
    alias = catalog.get("tool")
    assert alias is not None
    assert alias.expansion.startswith("bar ")
    assert alias.source_file == b
