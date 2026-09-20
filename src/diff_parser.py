"""Utilities for extracting changed lines from GitHub unified diff patches."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class ChangedLine:
    """A line added to the current version of a changed file."""

    file: str
    line: int
    code: str
    language: str

    def as_dict(self) -> dict[str, object]:
        return {"file": self.file, "line": self.line, "code": self.code, "language": self.language}


def language_for_file(filename: str) -> str:
    """Return a useful language label based on a file extension."""
    suffix = Path(filename).suffix.lower()
    languages = {
        ".py": "python", ".js": "javascript", ".jsx": "javascript", ".ts": "typescript",
        ".tsx": "typescript", ".java": "java", ".go": "go", ".rs": "rust", ".rb": "ruby",
        ".php": "php", ".cs": "csharp", ".cpp": "cpp", ".c": "c", ".sql": "sql",
        ".yml": "yaml", ".yaml": "yaml", ".json": "json", ".sh": "shell", ".bash": "shell",
        ".tf": "terraform", ".xml": "xml", ".html": "html", ".css": "css",
    }
    return languages.get(suffix, "text")


def parse_patch(filename: str, patch: str | None) -> list[ChangedLine]:
    """Parse one GitHub patch and return only added current-file lines.

    Deleted lines are ignored because the auditor should inspect the resulting code.
    Binary files and malformed patches produce an empty list rather than an exception.
    """
    if not patch or patch.startswith("Binary files"):
        return []

    changed: list[ChangedLine] = []
    current_line: int | None = None
    language = language_for_file(filename)

    for raw_line in patch.splitlines():
        if raw_line.startswith("@@"):
            try:
                new_range = raw_line.split("+")[1].split(" ")[0]
                start = new_range.split(",")[0]
                current_line = int(start)
            except (IndexError, ValueError):
                current_line = None
            continue

        if current_line is None or raw_line.startswith("\\ No newline"):
            continue

        if raw_line.startswith("+") and not raw_line.startswith("+++"):
            changed.append(ChangedLine(filename, current_line, raw_line[1:], language))
            current_line += 1
        elif raw_line.startswith("-"):
            continue
        else:
            current_line += 1

    return changed


def extract_changed_lines(files: Iterable[dict[str, object]]) -> list[ChangedLine]:
    """Extract changed lines from GitHub's changed-file response objects."""
    changed: list[ChangedLine] = []
    for file_data in files:
        filename = str(file_data.get("filename", ""))
        changed.extend(parse_patch(filename, file_data.get("patch")))
    return changed
