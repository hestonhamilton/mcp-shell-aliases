"""Safety classification helpers."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, List, Pattern


@dataclass(slots=True)
class SafetyClassifier:
    """Classifies alias expansions as safe or unsafe."""

    allow_patterns: List[Pattern[str]]
    deny_patterns: List[Pattern[str]]

    @classmethod
    def from_strings(cls, allow_patterns: Iterable[str], deny_patterns: Iterable[str]) -> "SafetyClassifier":
        return cls(
            allow_patterns=[re.compile(_normalize_regex(pattern)) for pattern in allow_patterns],
            deny_patterns=[re.compile(_normalize_regex(pattern)) for pattern in deny_patterns],
        )

    def is_safe(self, expansion: str) -> bool:
        if any(pattern.search(expansion) for pattern in self.deny_patterns):
            return False

        if not self.allow_patterns:
            return False

        return any(pattern.search(expansion) for pattern in self.allow_patterns)


def _normalize_regex(pattern: str) -> str:
    """Allow configuration strings to use escaped sequences like ``\\b`` or ``\\s``."""
    if "\\" not in pattern:
        return pattern
    try:
        return pattern.encode("utf-8").decode("unicode_escape")
    except UnicodeDecodeError:
        return pattern
