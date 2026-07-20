"""Validate commit messages before they reach ``git commit``.

Heredoc-driven commit flows (``make commit message_file=- <<'EOF' ... EOF``) can
leak shell fragments into the recorded message when a terminator is mistyped or
trailing shell is pasted after the closing token. Commit ``b68de52`` captured
``EOF && make push 2>&1 | tail -3`` inside its message this way. This module
rejects the obvious shell-leak shapes while keeping false positives unlikely, so
only clearly shell-shaped lines are flagged.
"""

from __future__ import annotations

import re

# A quoted heredoc opener such as ``<<'EOF'`` or ``<<"MSG"`` is unambiguous
# shell, so any quote right after ``<<`` is treated as a leak.
_QUOTED_HEREDOC_OPENER = re.compile(r"<<-?\s*['\"]")

# An unquoted heredoc opener such as ``<<EOF`` or ``<< HEREDOC``. Restricted to
# the common uppercase delimiters so a legitimate left-shift like ``value << 2``
# is never mistaken for a heredoc.
_UNQUOTED_HEREDOC_OPENER = re.compile(r"<<-?\s*(?:EOF|EOT|END|HEREDOC|MSG|BODY|PATCH)\b")

# A bare heredoc terminator left in the body, optionally followed by trailing
# shell (``EOF && make push``). Matches only the common uppercase delimiters as
# a whole leading token so ordinary prose is not flagged.
_HEREDOC_TERMINATOR = re.compile(r"^\s*(?:EOF|EOT|HEREDOC)(?:\s*(?:$|&&|\|\||;|\||&|>|<|\d*>))")

# Shell redirection (``2>&1``) and pipes into a pager (``| tail``/``| head``)
# are unambiguous shell fragments that do not belong in a commit message.
_SHELL_REDIRECT = re.compile(r"\d*>&\d")
_SHELL_PAGER_PIPE = re.compile(r"\|\s*(?:tail|head)\b")


def find_shell_leaks(message: str) -> list[str]:
    """Return one problem description per line that looks like leaked shell.

    Each problem names the 1-based line number and the offending text so the
    author can see exactly which line to fix.
    """
    problems: list[str] = []
    for lineno, line in enumerate(message.splitlines(), start=1):
        reason = _line_leak_reason(line)
        if reason is not None:
            problems.append(f"line {lineno}: {reason} ({line.strip()!r})")
    return problems


def _line_leak_reason(line: str) -> str | None:
    """Return why a single line looks like leaked shell, or ``None`` when clean."""
    if _QUOTED_HEREDOC_OPENER.search(line) or _UNQUOTED_HEREDOC_OPENER.search(line):
        return "contains a heredoc opener"
    if _HEREDOC_TERMINATOR.match(line):
        return "contains a bare heredoc terminator"
    if _SHELL_REDIRECT.search(line):
        return "contains a shell redirection"
    if _SHELL_PAGER_PIPE.search(line):
        return "contains a shell pipe into a pager"
    return None


def validate_commit_message(message: str) -> None:
    """Raise ``ValueError`` when a commit message contains leaked shell fragments."""
    problems = find_shell_leaks(message)
    if not problems:
        return
    detail = "\n".join(f"  - {problem}" for problem in problems)
    raise ValueError(
        "Commit message looks like it leaked shell text (a mistyped heredoc "
        "terminator or trailing shell after the closing token):\n"
        f"{detail}\n"
        "Fix the message and re-run the commit."
    )
