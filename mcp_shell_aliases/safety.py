# Gemini Shell Aliases - A tool for creating and managing shell aliases.
# Copyright (C) 2025 Heston Hamilton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.

"""Safety classification helpers."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Iterable, List, Pattern


logger = logging.getLogger(__name__)


@dataclass(slots=True)
class SafetyClassifier:
    """Classifies alias expansions as safe or unsafe using allowlist-only rules."""

    allow_patterns: List[Pattern[str]]

    @classmethod
    def from_strings(cls, allow_patterns: Iterable[str]) -> "SafetyClassifier":
        return cls(
            allow_patterns=_compile_patterns(allow_patterns),
        )

    def is_safe(self, expansion: str) -> bool:
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


def _compile_patterns(patterns: Iterable[str]) -> List[Pattern[str]]:
    compiled: List[Pattern[str]] = []
    for raw in patterns:
        normalized = _normalize_regex(raw)
        try:
            compiled.append(re.compile(normalized))
        except re.error:
            logger.warning("Skipping invalid regex pattern '%s'", raw)
    return compiled
