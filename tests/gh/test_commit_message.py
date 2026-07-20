from __future__ import annotations

import pytest

from scripts.gh import commit_message


def test_clean_message_has_no_leaks() -> None:
    """A normal multi-line commit message reports no shell leaks."""
    message = (
        "Add personal timeline header image and organize assets\n\n"
        "- Add hand-drawn sketchnote header image\n"
        "- Move snake SVGs into assets/ folder\n"
    )
    assert commit_message.find_shell_leaks(message) == []
    commit_message.validate_commit_message(message)


def test_leaked_terminator_with_trailing_shell_is_flagged() -> None:
    """The commit b68de52 leak shape is rejected."""
    message = "Redesign scroll-top icon\n\nEOF && make push 2>&1 | tail -3\n"
    problems = commit_message.find_shell_leaks(message)
    assert len(problems) == 1
    assert "line 3" in problems[0]
    with pytest.raises(ValueError, match="leaked shell text"):
        commit_message.validate_commit_message(message)


def test_bare_terminator_line_is_flagged() -> None:
    """A lone heredoc terminator left in the body is rejected."""
    assert commit_message.find_shell_leaks("Subject\n\nEOF\n")
    assert commit_message.find_shell_leaks("Subject\n\n  EOT\n")


@pytest.mark.parametrize(
    "line",
    [
        "make commit message_file=- <<'EOF'",
        'run <<"MSG"',
        "cat <<EOF",
        "here is a heredoc: << HEREDOC",
    ],
)
def test_heredoc_openers_are_flagged(line: str) -> None:
    """Quoted and common unquoted heredoc openers are rejected."""
    assert commit_message.find_shell_leaks(f"Subject\n\n{line}\n")


def test_shell_redirect_and_pager_pipe_are_flagged() -> None:
    """Redirections and pipes into a pager are rejected."""
    assert commit_message.find_shell_leaks("Subject\n\ncmd 2>&1\n")
    assert commit_message.find_shell_leaks("Subject\n\ncmd | tail -3\n")
    assert commit_message.find_shell_leaks("Subject\n\ncmd | head\n")


@pytest.mark.parametrize(
    "message",
    [
        "Shift a value by two: value << 2 keeps the low bits",
        "Document EOF handling in the parser",
        "Reached END of the migration checklist",
        "Explain how tail latency and head-of-line blocking interact",
        "Compare foo && bar behavior in the shell docs",
    ],
)
def test_prose_that_merely_mentions_shell_words_is_not_flagged(message: str) -> None:
    """Ordinary prose mentioning EOF, shifts, or pager words is not a false positive."""
    assert commit_message.find_shell_leaks(message) == []
    commit_message.validate_commit_message(message)


def test_validate_error_lists_every_offending_line() -> None:
    """The raised error enumerates each leaked line."""
    message = "Subject\n\nEOF\ncmd 2>&1\n"
    with pytest.raises(ValueError) as excinfo:
        commit_message.validate_commit_message(message)
    text = str(excinfo.value)
    assert "line 3" in text
    assert "line 4" in text
