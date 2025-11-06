# Copyright (C) 2025 Heston Hamilton

from __future__ import annotations

import pytest

from mcp_shell_aliases.safety import SafetyClassifier, _normalize_regex


def test_normalize_regex_decodes_escape_sequences() -> None:
    pattern = r"^ls\\b"
    normalised = _normalize_regex(pattern)
    classifier = SafetyClassifier.from_strings([pattern])

    assert normalised == r"^ls\b"
    assert classifier.is_safe("ls -al")


def test_normalize_regex_handles_invalid_sequence() -> None:
    bad_pattern = r"\\x"
    # Should not raise even though it's an invalid escape sequence
    normalized = _normalize_regex(bad_pattern)
    assert normalized == "\\x"

    classifier = SafetyClassifier.from_strings([bad_pattern])
    assert classifier.allow_patterns == []
    assert classifier.is_safe("\\x value") is False


@pytest.mark.parametrize(
    ("expansion", "expected"),
    [
        ("ls -l", True),
        ("rm -rf /", False),
    ],
)
def test_is_safe_uses_allowlist_only(expansion: str, expected: bool) -> None:
    classifier = SafetyClassifier.from_strings([r"^ls"])
    assert classifier.is_safe(expansion) is expected
