from __future__ import annotations

from difflib import unified_diff


def unified_markdown_diff(old: str, new: str, fromfile: str = "old", tofile: str = "new") -> str:
    """Return a unified diff string between two markdown texts.

    Normalizes line endings and ensures trailing newlines for stable diffs.
    """
    old_lines = (old or "").splitlines(keepends=False)
    new_lines = (new or "").splitlines(keepends=False)
    diff = unified_diff(
        old_lines,
        new_lines,
        fromfile=fromfile,
        tofile=tofile,
        lineterm="",
        n=3,
    )
    return "\n".join(diff)
