from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

from scripts.gh import cli, gh_runner, pr_review
from scripts.gh.gh_runner import GhError
from tests.gh.gh_test_support import FakeGh, completed_process, has

if TYPE_CHECKING:
    from collections.abc import Sequence


def _query_arg(cmd: list[str]) -> str:
    """Return the ``query=`` argument from a gh graphql command."""
    return next(part for part in cmd if part.startswith("query="))


THREADS_PAYLOAD = {
    "data": {
        "repository": {
            "pullRequest": {
                "reviewThreads": {
                    "pageInfo": {"hasNextPage": False, "endCursor": None},
                    "nodes": [
                        {
                            "id": "PRRT_open1",
                            "isResolved": False,
                            "path": "src/foo.py",
                            "line": 42,
                            "comments": {
                                "nodes": [
                                    {
                                        "body": "Please rename this\nsecond line",
                                        "url": "https://example/1",
                                        "author": {"login": "reviewer"},
                                    }
                                ]
                            },
                        },
                        {
                            "id": "PRRT_done1",
                            "isResolved": True,
                            "path": "src/bar.py",
                            "line": None,
                            "comments": {"nodes": []},
                        },
                    ],
                }
            }
        }
    }
}


def _comments_page(
    thread_id: str,
    comment_nodes: list[dict[str, Any]],
    *,
    threads_next: bool = False,
    threads_cursor: str | None = None,
    comments_next: bool = False,
    comments_cursor: str | None = None,
) -> dict[str, Any]:
    """Build one ``reviewThreads`` page response for the comments query."""
    return {
        "data": {
            "repository": {
                "pullRequest": {
                    "reviewThreads": {
                        "pageInfo": {
                            "hasNextPage": threads_next,
                            "endCursor": threads_cursor,
                        },
                        "nodes": [
                            {
                                "id": thread_id,
                                "comments": {
                                    "pageInfo": {
                                        "hasNextPage": comments_next,
                                        "endCursor": comments_cursor,
                                    },
                                    "nodes": comment_nodes,
                                },
                            }
                        ],
                    }
                }
            }
        }
    }


COMMENTS_PAYLOAD = _comments_page(
    "PRRT_a",
    [
        {
            "id": "PRRC_first",
            "body": "Original review note\nsecond line",
            "url": "https://example/c1",
            "author": {"login": "reviewer"},
        },
        {
            "id": "PRRC_reply",
            "body": "Fixed it",
            "url": "https://example/c2",
            "author": None,
        },
    ],
)


def test_parse_nodes_rejects_non_list() -> None:
    """Test parse nodes rejects non list."""
    with pytest.raises(GhError):
        pr_review._parse_nodes("not a list")


def test_parse_nodes_rejects_non_dict_node() -> None:
    """Test parse nodes rejects non dict node."""
    with pytest.raises(GhError):
        pr_review._parse_nodes([None])


def test_parse_nodes_rejects_node_missing_id() -> None:
    """Test parse nodes rejects node missing id."""
    with pytest.raises(GhError):
        pr_review._parse_nodes([{}])


def test_parse_nodes_null_comments_is_empty() -> None:
    """A thread whose comments field is explicitly null still parses."""
    threads = pr_review._parse_nodes([{"id": "PRRT_x", "comments": None}])
    assert [thread.thread_id for thread in threads] == ["PRRT_x"]


def test_parse_nodes_rejects_non_dict_comments() -> None:
    """Test parse nodes rejects non dict comments."""
    with pytest.raises(GhError):
        pr_review._parse_nodes([{"id": "PRRT_x", "comments": "not a dict"}])


def test_parse_nodes_rejects_non_list_comment_nodes() -> None:
    """Test parse nodes rejects non list comment nodes."""
    with pytest.raises(GhError):
        pr_review._parse_nodes([{"id": "PRRT_x", "comments": {"nodes": "not a list"}}])


def test_parse_nodes_rejects_missing_comment_nodes() -> None:
    """Test parse nodes rejects missing comment nodes."""
    with pytest.raises(GhError):
        pr_review._parse_nodes([{"id": "PRRT_x", "comments": {}}])


def test_parse_nodes_rejects_non_dict_first_comment() -> None:
    """Test parse nodes rejects non dict first comment."""
    with pytest.raises(GhError):
        pr_review._parse_nodes([{"id": "PRRT_x", "comments": {"nodes": ["not a dict"]}}])


def test_parse_nodes_rejects_non_dict_author() -> None:
    """Test parse nodes rejects non dict author."""
    with pytest.raises(GhError):
        pr_review._parse_nodes(
            [{"id": "PRRT_x", "comments": {"nodes": [{"author": "not a dict"}]}}]
        )


def test_parse_comment_nodes_rejects_non_dict() -> None:
    """Test parse comment nodes rejects non dict."""
    with pytest.raises(GhError):
        pr_review._parse_comment_nodes(123)


def test_parse_comment_nodes_rejects_non_dict_element() -> None:
    """Test parse comment nodes rejects non dict element."""
    with pytest.raises(GhError):
        pr_review._parse_comment_nodes([None])


def test_parse_comment_nodes_rejects_missing_id() -> None:
    """Test parse comment nodes rejects missing id."""
    with pytest.raises(GhError):
        pr_review._parse_comment_nodes([{"url": "x"}])


def test_parse_comment_nodes_rejects_non_dict_author() -> None:
    """Test parse comment nodes rejects non dict author."""
    with pytest.raises(GhError):
        pr_review._parse_comment_nodes(
            [{"id": "IC_x", "author": "not a dict", "url": "u", "body": "b"}]
        )


def test_remaining_thread_comments_bad_connection_shape() -> None:
    """Test remaining thread comments bad connection shape."""

    def runner(_cmd: Sequence[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        """Runner."""
        return completed_process(0, json.dumps({"data": {"node": {"comments": "bad"}}}))

    page_info = {"hasNextPage": True, "endCursor": "CUR"}
    with pytest.raises(GhError):
        pr_review._remaining_thread_comments("PRRT_x", page_info, run_fn=runner)


def test_remaining_thread_comments_rejects_non_dict_page_info() -> None:
    """Test remaining thread comments rejects non dict page info."""
    with pytest.raises(GhError):
        pr_review._remaining_thread_comments("PRRT_x", "not a dict")


def test_remaining_thread_comments_hasnext_without_cursor_raises() -> None:
    """Test remaining thread comments hasnext without cursor raises."""
    with pytest.raises(GhError):
        pr_review._remaining_thread_comments("PRRT_x", {"hasNextPage": True})


def test_remaining_thread_comments_bad_hasnext_type_raises() -> None:
    """Test remaining thread comments bad hasnext type raises."""
    with pytest.raises(GhError):
        pr_review._remaining_thread_comments("PRRT_x", {"hasNextPage": "yes", "endCursor": "CUR"})


def test_remaining_thread_comments_bad_endcursor_type_raises() -> None:
    """Test remaining thread comments bad endcursor type raises."""
    with pytest.raises(GhError):
        pr_review._remaining_thread_comments("PRRT_x", {"hasNextPage": True, "endCursor": 123})


def test_remaining_thread_comments_bad_pageinfo_shape() -> None:
    """Test remaining thread comments bad pageinfo shape."""

    def runner(_cmd: Sequence[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        """Runner."""
        return completed_process(
            0,
            json.dumps({"data": {"node": {"comments": {"nodes": [], "pageInfo": "bad"}}}}),
        )

    page_info = {"hasNextPage": True, "endCursor": "CUR"}
    with pytest.raises(GhError):
        pr_review._remaining_thread_comments("PRRT_x", page_info, run_fn=runner)


def test_remaining_thread_comments_missing_nodes_raises() -> None:
    """Test remaining thread comments missing nodes raises."""

    def runner(_cmd: Sequence[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        """Runner."""
        return completed_process(
            0,
            json.dumps(
                {
                    "data": {
                        "node": {
                            "comments": {"pageInfo": {"hasNextPage": False, "endCursor": None}}
                        }
                    }
                }
            ),
        )

    page_info = {"hasNextPage": True, "endCursor": "CUR"}
    with pytest.raises(GhError):
        pr_review._remaining_thread_comments("PRRT_x", page_info, run_fn=runner)


def _threads_runner(payload: dict[str, Any]) -> FakeGh:
    return FakeGh(
        [
            (
                has("repo", "view"),
                completed_process(0, json.dumps({"nameWithOwner": "o/r"})),
            ),
            (has("pr", "view"), completed_process(0, json.dumps({"number": 7}))),
            (has("graphql"), completed_process(0, json.dumps(payload))),
        ]
    )


def test_list_threads_nodes_not_list_raises() -> None:
    """Test list threads nodes not list raises."""
    runner = _threads_runner(
        {
            "data": {
                "repository": {
                    "pullRequest": {
                        "reviewThreads": {
                            "nodes": "x",
                            "pageInfo": {"hasNextPage": False},
                        }
                    }
                }
            }
        }
    )
    with pytest.raises(GhError):
        pr_review.list_threads(7, run_fn=runner)


def test_list_threads_pageinfo_not_dict_raises() -> None:
    """Test list threads pageinfo not dict raises."""
    runner = _threads_runner(
        {
            "data": {
                "repository": {"pullRequest": {"reviewThreads": {"nodes": [], "pageInfo": "bad"}}}
            }
        }
    )
    with pytest.raises(GhError):
        pr_review.list_threads(7, run_fn=runner)


def test_list_threads_hasnext_without_cursor_raises() -> None:
    """Test list threads hasnext without cursor raises."""
    runner = _threads_runner(
        {
            "data": {
                "repository": {
                    "pullRequest": {
                        "reviewThreads": {
                            "nodes": [{"id": "X"}],
                            "pageInfo": {"hasNextPage": True},
                        }
                    }
                }
            }
        }
    )
    with pytest.raises(GhError):
        pr_review.list_threads(7, run_fn=runner)


def test_list_threads_bad_hasnext_type_raises() -> None:
    """Test list threads bad hasnext type raises."""
    runner = _threads_runner(
        {
            "data": {
                "repository": {
                    "pullRequest": {
                        "reviewThreads": {
                            "nodes": [{"id": "X"}],
                            "pageInfo": {"hasNextPage": "yes"},
                        }
                    }
                }
            }
        }
    )
    with pytest.raises(GhError):
        pr_review.list_threads(7, run_fn=runner)


def test_list_threads_bad_endcursor_type_raises() -> None:
    """Test list threads bad endcursor type raises."""
    runner = _threads_runner(
        {
            "data": {
                "repository": {
                    "pullRequest": {
                        "reviewThreads": {
                            "nodes": [{"id": "X"}],
                            "pageInfo": {"hasNextPage": True, "endCursor": 123},
                        }
                    }
                }
            }
        }
    )
    with pytest.raises(GhError):
        pr_review.list_threads(7, run_fn=runner)


def test_list_comments_nodes_not_list_raises() -> None:
    """Test list comments nodes not list raises."""
    runner = _threads_runner(
        {
            "data": {
                "repository": {
                    "pullRequest": {
                        "reviewThreads": {
                            "nodes": "x",
                            "pageInfo": {"hasNextPage": False},
                        }
                    }
                }
            }
        }
    )
    with pytest.raises(GhError):
        pr_review.list_comments(7, run_fn=runner)


def test_list_comments_null_node_raises() -> None:
    """Test list comments null node raises."""
    runner = _threads_runner(
        {
            "data": {
                "repository": {
                    "pullRequest": {
                        "reviewThreads": {
                            "nodes": [None],
                            "pageInfo": {"hasNextPage": False},
                        }
                    }
                }
            }
        }
    )
    with pytest.raises(GhError):
        pr_review.list_comments(7, run_fn=runner)


def test_list_comments_node_missing_id_raises() -> None:
    """Test list comments node missing id raises."""
    runner = _threads_runner(
        {
            "data": {
                "repository": {
                    "pullRequest": {
                        "reviewThreads": {
                            "nodes": [{}],
                            "pageInfo": {"hasNextPage": False},
                        }
                    }
                }
            }
        }
    )
    with pytest.raises(GhError):
        pr_review.list_comments(7, run_fn=runner)


def test_list_comments_node_missing_comments_raises() -> None:
    """Test list comments node missing comments raises."""
    runner = _threads_runner(
        {
            "data": {
                "repository": {
                    "pullRequest": {
                        "reviewThreads": {
                            "nodes": [{"id": "X"}],
                            "pageInfo": {"hasNextPage": False},
                        }
                    }
                }
            }
        }
    )
    with pytest.raises(GhError):
        pr_review.list_comments(7, run_fn=runner)


def test_list_comments_bad_pageinfo_raises() -> None:
    """Test list comments bad pageinfo raises."""
    runner = _threads_runner(
        {
            "data": {
                "repository": {
                    "pullRequest": {
                        "reviewThreads": {
                            "nodes": [{"id": "X", "comments": {"nodes": [], "pageInfo": {}}}],
                            "pageInfo": "bad",
                        }
                    }
                }
            }
        }
    )
    with pytest.raises(GhError):
        pr_review.list_comments(7, run_fn=runner)


def test_list_comments_bad_thread_pageinfo_raises() -> None:
    """A truthy non-dict thread comments.pageInfo must raise GhError, not crash."""
    runner = _threads_runner(
        {
            "data": {
                "repository": {
                    "pullRequest": {
                        "reviewThreads": {
                            "nodes": [
                                {
                                    "id": "X",
                                    "comments": {
                                        "nodes": [],
                                        "pageInfo": "not a dict",
                                    },
                                }
                            ],
                            "pageInfo": {},
                        }
                    }
                }
            }
        }
    )
    with pytest.raises(GhError):
        pr_review.list_comments(7, run_fn=runner)


def test_list_comments_missing_thread_nodes_raises() -> None:
    """Test list comments missing thread nodes raises."""
    runner = _threads_runner(
        {
            "data": {
                "repository": {
                    "pullRequest": {
                        "reviewThreads": {
                            "nodes": [
                                {
                                    "id": "X",
                                    "comments": {"pageInfo": {"hasNextPage": False}},
                                }
                            ],
                            "pageInfo": {"hasNextPage": False},
                        }
                    }
                }
            }
        }
    )
    with pytest.raises(GhError):
        pr_review.list_comments(7, run_fn=runner)


def test_list_comments_hasnext_without_cursor_raises() -> None:
    """Test list comments hasnext without cursor raises."""
    runner = _threads_runner(
        {
            "data": {
                "repository": {
                    "pullRequest": {
                        "reviewThreads": {
                            "nodes": [{"id": "X", "comments": {"nodes": []}}],
                            "pageInfo": {"hasNextPage": True},
                        }
                    }
                }
            }
        }
    )
    with pytest.raises(GhError):
        pr_review.list_comments(7, run_fn=runner)


def test_list_comments_bad_hasnext_type_raises() -> None:
    """Test list comments bad hasnext type raises."""
    runner = _threads_runner(
        {
            "data": {
                "repository": {
                    "pullRequest": {
                        "reviewThreads": {
                            "nodes": [{"id": "X", "comments": {"nodes": []}}],
                            "pageInfo": {"hasNextPage": 1},
                        }
                    }
                }
            }
        }
    )
    with pytest.raises(GhError):
        pr_review.list_comments(7, run_fn=runner)


def test_list_comments_bad_endcursor_type_raises() -> None:
    """Test list comments bad endcursor type raises."""
    runner = _threads_runner(
        {
            "data": {
                "repository": {
                    "pullRequest": {
                        "reviewThreads": {
                            "nodes": [{"id": "X", "comments": {"nodes": []}}],
                            "pageInfo": {"hasNextPage": True, "endCursor": 123},
                        }
                    }
                }
            }
        }
    )
    with pytest.raises(GhError):
        pr_review.list_comments(7, run_fn=runner)


def test_list_comments_missing_thread_pageinfo_raises() -> None:
    """Test list comments missing thread pageinfo raises."""
    runner = _threads_runner(
        {
            "data": {
                "repository": {
                    "pullRequest": {
                        "reviewThreads": {
                            "nodes": [{"id": "X", "comments": {"nodes": [], "pageInfo": None}}],
                            "pageInfo": {"hasNextPage": False},
                        }
                    }
                }
            }
        }
    )
    with pytest.raises(GhError):
        pr_review.list_comments(7, run_fn=runner)


def test_list_comments_bad_top_level_pageinfo_raises() -> None:
    """Test list comments bad top level pageinfo raises."""
    runner = _threads_runner(
        {
            "data": {
                "repository": {
                    "pullRequest": {
                        "reviewThreads": {
                            "nodes": [
                                {
                                    "id": "X",
                                    "comments": {
                                        "nodes": [],
                                        "pageInfo": {"hasNextPage": False},
                                    },
                                }
                            ],
                            "pageInfo": "bad",
                        }
                    }
                }
            }
        }
    )
    with pytest.raises(GhError):
        pr_review.list_comments(7, run_fn=runner)


def test_parse_threads_maps_fields() -> None:
    """Map a GraphQL payload into ReviewThread objects."""
    threads = pr_review.parse_threads(THREADS_PAYLOAD["data"])

    assert [thread.thread_id for thread in threads] == ["PRRT_open1", "PRRT_done1"]
    first = threads[0]
    assert first.state == "open"
    assert first.author == "reviewer"
    assert first.body.startswith("Please rename")
    assert threads[1].state == "resolved"
    assert threads[1].author == "unknown"


def _threads_page(
    thread_id: str, *, has_next: bool, end_cursor: str | None = None
) -> dict[str, Any]:
    """Build a one-node reviewThreads page with the given pagination state."""
    return {
        "repository": {
            "pullRequest": {
                "reviewThreads": {
                    "pageInfo": {"hasNextPage": has_next, "endCursor": end_cursor},
                    "nodes": [
                        {
                            "id": thread_id,
                            "isResolved": False,
                            "path": "f.py",
                            "line": 1,
                            "comments": {
                                "nodes": [{"body": "x", "url": "u", "author": {"login": "r"}}]
                            },
                        }
                    ],
                }
            }
        }
    }


def test_list_threads_follows_pagination() -> None:
    """list_threads pages through reviewThreads until hasNextPage is false."""
    pages = iter(
        [
            _threads_page("PRRT_a", has_next=True, end_cursor="CURSOR1"),
            _threads_page("PRRT_b", has_next=False),
        ]
    )
    calls: list[list[str]] = []

    def runner(cmd: Sequence[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        """Runner."""
        command = list(cmd)
        calls.append(command)
        if has("repo", "view")(command):
            return completed_process(0, json.dumps({"nameWithOwner": "o/r"}))
        if has("graphql")(command):
            return completed_process(0, json.dumps({"data": next(pages)}))
        raise AssertionError(command)

    threads = pr_review.list_threads(7, include_resolved=True, run_fn=runner)

    assert [thread.thread_id for thread in threads] == ["PRRT_a", "PRRT_b"]
    # The second page request carries the first page's endCursor.
    graphql_calls = [command for command in calls if has("graphql")(command)]
    assert len(graphql_calls) == 2
    assert any("after=CURSOR1" in command for command in graphql_calls)


def test_parse_threads_raises_on_missing_pull_request() -> None:
    """A null/absent repository or pull request raises a clear GhError."""
    for payload in ({}, {"repository": None}, {"repository": {"pullRequest": None}}):
        with pytest.raises(GhError):
            pr_review.parse_threads(payload)


def test_list_threads_filters_resolved_by_default() -> None:
    """Drop resolved threads unless include_resolved is set."""
    runner = FakeGh(
        [
            (
                has("repo", "view"),
                completed_process(0, json.dumps({"nameWithOwner": "o/r"})),
            ),
            (has("graphql"), completed_process(0, json.dumps(THREADS_PAYLOAD))),
        ]
    )

    open_only = pr_review.list_threads(7, run_fn=runner)
    everything = pr_review.list_threads(7, include_resolved=True, run_fn=runner)

    assert [thread.thread_id for thread in open_only] == ["PRRT_open1"]
    assert len(everything) == 2


def test_format_threads_is_greppable() -> None:
    """Render each open thread with its id and state."""
    threads = pr_review.parse_threads(THREADS_PAYLOAD["data"])
    text = pr_review.format_threads(threads)

    assert "thread=PRRT_open1" in text
    assert "state=open" in text
    assert "src/foo.py:42" in text
    assert "second line" not in text  # only the first body line is shown


def test_format_threads_empty() -> None:
    """Report when there are no matching threads."""
    assert pr_review.format_threads([]) == "No matching review threads."


def test_reply_uses_thread_id_without_database_id() -> None:
    """Reply via addPullRequestReviewThreadReply keyed on the thread id."""
    runner = FakeGh([(has("graphql"), completed_process(0, json.dumps({"data": {}})))])

    pr_review.reply_to_thread("PRRT_open1", "Fixed", run_fn=runner)

    (cmd,) = runner.calls
    assert "addPullRequestReviewThreadReply" in _query_arg(cmd)
    assert "thread=PRRT_open1" in cmd
    assert "body=Fixed" in cmd


def test_graphql_serializes_variables_by_type() -> None:
    """Bools become JSON true/false via -F, ints stay typed, strings use -f."""
    runner = FakeGh([(has("graphql"), completed_process(0, json.dumps({"data": {}})))])

    gh_runner.graphql(
        "query($flag: Boolean!, $count: Int!, $name: String!) { x }",
        variables={"flag": True, "count": 3, "name": "abc"},
        run_fn=runner,
    )

    (cmd,) = runner.calls
    assert "flag=true" in cmd  # not Python's "True"
    assert "count=3" in cmd
    assert "name=abc" in cmd
    # The bool and int are typed (-F); the string is plain (-f).
    assert cmd[cmd.index("flag=true") - 1] == "-F"
    assert cmd[cmd.index("name=abc") - 1] == "-f"


def test_address_replies_then_resolves() -> None:
    """Address a thread by replying first and resolving second."""
    runner = FakeGh([(has("graphql"), completed_process(0, json.dumps({"data": {}})))])

    pr_review.address_thread("PRRT_open1", "done", run_fn=runner)

    mutations = [_query_arg(cmd) for cmd in runner.calls]
    assert "addPullRequestReviewThreadReply" in mutations[0]
    assert "resolveReviewThread" in mutations[1]


def test_address_short_circuits_when_reply_fails() -> None:
    """Do not resolve a thread if the reply failed."""
    runner = FakeGh([(has("graphql"), completed_process(1, "", "boom"))])

    with pytest.raises(GhError):
        pr_review.address_thread("PRRT_open1", "done", run_fn=runner)

    assert len(runner.calls) == 1  # reply attempted, resolve skipped


def test_pr_summary_includes_meta_and_threads() -> None:
    """Summaries show PR state, a checks tally, and open threads."""
    meta = {
        "number": 7,
        "title": "Add feature",
        "state": "OPEN",
        "url": "https://example/pr/7",
        "statusCheckRollup": [{"conclusion": "SUCCESS"}, {"conclusion": "FAILURE"}],
    }
    runner = FakeGh(
        [
            (has("pr", "view"), completed_process(0, json.dumps(meta))),
            (
                has("repo", "view"),
                completed_process(0, json.dumps({"nameWithOwner": "o/r"})),
            ),
            (has("graphql"), completed_process(0, json.dumps(THREADS_PAYLOAD))),
        ]
    )

    text = pr_review.pr_summary(7, run_fn=runner)

    assert "PR #7 [OPEN] Add feature" in text
    assert "1 failure" in text and "1 success" in text
    assert "open review threads: 1" in text
    assert "thread=PRRT_open1" in text


def test_pr_summary_omits_thread_block_when_no_open_threads() -> None:
    """Summaries skip the thread listing when every thread is resolved."""
    meta = {
        "number": 8,
        "title": "Quiet PR",
        "state": "OPEN",
        "url": "https://example/pr/8",
        "statusCheckRollup": [{"conclusion": "SUCCESS"}],
    }
    empty_threads = {
        "data": {
            "repository": {
                "pullRequest": {
                    "reviewThreads": {
                        "pageInfo": {"hasNextPage": False, "endCursor": None},
                        "nodes": [],
                    }
                }
            }
        }
    }
    runner = FakeGh(
        [
            (has("pr", "view"), completed_process(0, json.dumps(meta))),
            (
                has("repo", "view"),
                completed_process(0, json.dumps({"nameWithOwner": "o/r"})),
            ),
            (has("graphql"), completed_process(0, json.dumps(empty_threads))),
        ]
    )

    text = pr_review.pr_summary(8, run_fn=runner)

    assert "open review threads: 0" in text
    assert "thread=" not in text
    assert not text.endswith("\n")


def test_resolve_repo_falls_back_to_remote() -> None:
    """Parse owner/name from the git remote when gh repo view fails."""
    runner = FakeGh(
        [
            (has("repo", "view"), completed_process(1, "", "no repo")),
            (has("remote"), completed_process(0, "git@github.com:octo/Hello.git\n")),
        ]
    )

    assert gh_runner.resolve_repo(run_fn=runner) == "octo/Hello"


def test_resolve_repo_handles_ssh_remote_with_port() -> None:
    """An SSH remote URL with an explicit port still yields owner/name."""
    runner = FakeGh(
        [
            (has("repo", "view"), completed_process(1, "", "no repo")),
            (
                has("remote"),
                completed_process(0, "ssh://git@github.com:22/octo/Hello.git\n"),
            ),
        ]
    )

    assert gh_runner.resolve_repo(run_fn=runner) == "octo/Hello"


def test_resolve_repo_ignores_non_github_remote() -> None:
    """Do not treat a non-GitHub origin path as a GitHub owner/name slug."""
    runner = FakeGh(
        [
            (has("repo", "view"), completed_process(1, "", "no repo")),
            (
                has("remote"),
                completed_process(0, "https://gitlab.example/octo/Hello.git\n"),
            ),
        ]
    )

    with pytest.raises(GhError):
        gh_runner.resolve_repo(run_fn=runner)


def test_resolve_repo_ignores_github_lookalike_host() -> None:
    """Reject origins whose host merely contains github.com as a substring."""
    runner = FakeGh(
        [
            (has("repo", "view"), completed_process(1, "", "no repo")),
            (
                has("remote"),
                completed_process(0, "https://github.com.evil/octo/Hello.git\n"),
            ),
        ]
    )

    with pytest.raises(GhError):
        gh_runner.resolve_repo(run_fn=runner)


def test_resolve_repo_falls_back_when_key_missing() -> None:
    """A repo-view payload without nameWithOwner still falls back to the remote."""
    runner = FakeGh(
        [
            (has("repo", "view"), completed_process(0, json.dumps({}))),
            (has("remote"), completed_process(0, "git@github.com:octo/Hello.git\n")),
        ]
    )

    assert gh_runner.resolve_repo(run_fn=runner) == "octo/Hello"


def test_resolve_repo_raises_when_unresolvable() -> None:
    """Raise a clear error when neither source yields a slug."""
    runner = FakeGh(
        [
            (has("repo", "view"), completed_process(1, "", "no repo")),
            (has("remote"), completed_process(1, "", "no remote")),
        ]
    )

    with pytest.raises(GhError):
        gh_runner.resolve_repo(run_fn=runner)


def test_current_pr_number_parses_gh_output() -> None:
    """Read the PR number for the current branch."""
    runner = FakeGh([(has("pr", "view"), completed_process(0, json.dumps({"number": 19})))])

    assert gh_runner.current_pr_number(run_fn=runner) == 19


def test_current_pr_number_raises_without_pr() -> None:
    """Raise a friendly error when the branch has no PR."""
    runner = FakeGh([(has("pr", "view"), completed_process(1, "", "no pull requests found"))])

    with pytest.raises(GhError):
        gh_runner.current_pr_number(run_fn=runner)


def test_main_requires_body_for_reply() -> None:
    """Reject a reply that is missing a body via argparse."""
    with pytest.raises(SystemExit) as excinfo:
        cli.main(["reply", "--thread", "PRRT_x"])

    assert excinfo.value.code == 2


def test_main_list_json(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The list command emits JSON when asked."""
    thread = pr_review.ReviewThread("PRRT_x", "open", "f.py", 1, "me", "hi", "u")
    monkeypatch.setattr(pr_review, "list_threads", lambda *_a, **_k: [thread])

    exit_code = cli.main(["list", "--json"])

    captured = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert captured[0]["thread_id"] == "PRRT_x"


def test_list_comments_flattens_all_thread_comments() -> None:
    """list_comments returns every comment across threads, missing author included."""
    runner = FakeGh(
        [
            (
                has("repo", "view"),
                completed_process(0, json.dumps({"nameWithOwner": "o/r"})),
            ),
            (has("graphql"), completed_process(0, json.dumps(COMMENTS_PAYLOAD))),
        ]
    )

    comments = pr_review.list_comments(7, run_fn=runner)

    assert [comment.comment_id for comment in comments] == ["PRRC_first", "PRRC_reply"]
    assert comments[0].author == "reviewer"
    assert comments[1].author == "unknown"  # null author falls back


def test_list_comments_paginates_threads_and_comments() -> None:
    """list_comments pages both reviewThreads and a thread's overflow comments."""
    thread_comments_page = {
        "data": {
            "node": {
                "comments": {
                    "pageInfo": {"hasNextPage": False, "endCursor": None},
                    "nodes": [
                        {
                            "id": "PRRC_a2",
                            "body": "more",
                            "url": "u",
                            "author": {"login": "r"},
                        }
                    ],
                }
            }
        }
    }
    pages = iter(
        [
            _comments_page(
                "PRRT_a",
                [
                    {
                        "id": "PRRC_a1",
                        "body": "first",
                        "url": "u",
                        "author": {"login": "r"},
                    }
                ],
                threads_next=True,
                threads_cursor="TCUR",
                comments_next=True,
                comments_cursor="CCUR",
            ),
            thread_comments_page,
            _comments_page(
                "PRRT_b",
                [
                    {
                        "id": "PRRC_b1",
                        "body": "second",
                        "url": "u",
                        "author": {"login": "r"},
                    }
                ],
            ),
        ]
    )
    calls: list[list[str]] = []

    def runner(cmd: Sequence[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        """Runner."""
        command = list(cmd)
        calls.append(command)
        if has("repo", "view")(command):
            return completed_process(0, json.dumps({"nameWithOwner": "o/r"}))
        if has("graphql")(command):
            return completed_process(0, json.dumps(next(pages)))
        raise AssertionError(command)

    comments = pr_review.list_comments(7, run_fn=runner)

    assert [comment.comment_id for comment in comments] == [
        "PRRC_a1",
        "PRRC_a2",
        "PRRC_b1",
    ]
    graphql_calls = [command for command in calls if has("graphql")(command)]
    assert len(graphql_calls) == 3
    assert any("after=CCUR" in command for command in graphql_calls)  # comment pagination
    assert any("after=TCUR" in command for command in graphql_calls)  # thread pagination


def test_format_comments_shows_first_line_only() -> None:
    """Rendering is one greppable line per comment, first body line only."""
    comment = pr_review.ReviewComment("PRRC_first", "reviewer", "Note here\nsecond line", "u")

    text = pr_review.format_comments([comment])

    assert text == "comment=PRRC_first  @reviewer: Note here"


def test_format_comments_empty() -> None:
    """An empty comment list renders a friendly placeholder."""
    assert pr_review.format_comments([]) == "No review comments."


def test_delete_review_comment_uses_mutation_without_retry() -> None:
    """Deletion keys off the comment node id via deletePullRequestReviewComment."""
    runner = FakeGh([(has("graphql"), completed_process(0, json.dumps({"data": {}})))])

    pr_review.delete_review_comment("PRRC_reply", run_fn=runner)

    (cmd,) = runner.calls
    assert "deletePullRequestReviewComment" in _query_arg(cmd)
    assert "comment=PRRC_reply" in cmd


def test_main_list_comments_json(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The list-comments command emits JSON when asked."""
    comment = pr_review.ReviewComment("PRRC_x", "me", "hi", "u")
    monkeypatch.setattr(pr_review, "list_comments", lambda *_a, **_k: [comment])

    exit_code = cli.main(["list-comments", "--json"])

    captured = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert captured[0]["comment_id"] == "PRRC_x"


def test_main_delete_comment_invokes_helper(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The delete-comment command deletes by node id and confirms."""
    deleted: list[str] = []
    monkeypatch.setattr(pr_review, "delete_review_comment", lambda comment: deleted.append(comment))

    exit_code = cli.main(["delete-comment", "--comment", "PRRC_x"])

    assert exit_code == 0
    assert deleted == ["PRRC_x"]
    assert "Deleted PRRC_x" in capsys.readouterr().out


def test_main_list_prints_text(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The list command prints formatted text by default."""
    thread = pr_review.ReviewThread("PRRT_x", "open", "f.py", 1, "me", "hi", "u")
    monkeypatch.setattr(pr_review, "list_threads", lambda *_a, **_k: [thread])

    exit_code = cli.main(["list"])

    assert exit_code == 0
    assert "thread=PRRT_x" in capsys.readouterr().out


def test_main_reply_reads_body_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The reply command accepts body text from a file."""
    body_file = tmp_path / "reply.md"
    body_file.write_text("Fixed with detail", encoding="utf-8")
    replies: list[tuple[str, str]] = []
    monkeypatch.setattr(
        pr_review,
        "reply_to_thread",
        lambda thread, body: replies.append((thread, body)),
    )

    exit_code = cli.main(["reply", "--thread", "PRRT_x", "--body-file", str(body_file)])

    assert exit_code == 0
    assert replies == [("PRRT_x", "Fixed with detail")]
    assert "Replied to PRRT_x" in capsys.readouterr().out


def test_main_reply_missing_body_file_raises_gh_error() -> None:
    """A missing or unreadable --body-file raises a GhError naming the path."""
    with pytest.raises(GhError, match=r"Could not read --body-file .*nonexistent"):
        cli.main(["reply", "--thread", "PRRT_x", "--body-file", "/nonexistent/path.md"])


def test_main_resolve_invokes_helper(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The resolve command resolves by thread id and confirms."""
    resolved: list[str] = []
    monkeypatch.setattr(pr_review, "resolve_thread", resolved.append)

    exit_code = cli.main(["resolve", "--thread", "PRRT_x"])

    assert exit_code == 0
    assert resolved == ["PRRT_x"]
    assert "Resolved PRRT_x" in capsys.readouterr().out


def test_main_address_invokes_helper(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The address command replies and resolves through the helper."""
    addressed: list[tuple[str, str]] = []
    monkeypatch.setattr(
        pr_review,
        "address_thread",
        lambda thread, body: addressed.append((thread, body)),
    )

    exit_code = cli.main(["address", "--thread", "PRRT_x", "--body", "Fixed now"])

    assert exit_code == 0
    assert addressed == [("PRRT_x", "Fixed now")]
    assert "Replied to and resolved PRRT_x" in capsys.readouterr().out


def test_main_list_comments_prints_text(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The list-comments command prints formatted text by default."""
    comment = pr_review.ReviewComment("PRRC_x", "me", "hi", "u")
    monkeypatch.setattr(pr_review, "list_comments", lambda *_a, **_k: [comment])

    exit_code = cli.main(["list-comments"])

    assert exit_code == 0
    assert "comment=PRRC_x" in capsys.readouterr().out


def test_main_summary_prints_overview(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The summary command prints the PR overview."""
    monkeypatch.setattr(pr_review, "pr_summary", lambda pr: f"summary {pr}")

    exit_code = cli.main(["summary", "--pr", "7"])

    assert exit_code == 0
    assert capsys.readouterr().out.strip() == "summary 7"


def test_main_ci_failures_prints_digest(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The ci-failures command prints the failed-step digest."""
    monkeypatch.setattr(cli.ci_status, "failure_digest", lambda run: f"run {run}")

    exit_code = cli.main(["ci-failures", "--run", "99"])

    assert exit_code == 0
    assert capsys.readouterr().out.strip() == "run 99"


def test_review_threads_missing_connection_raises() -> None:
    """A pullRequest without reviewThreads is surfaced as a GhError."""
    with pytest.raises(GhError):
        pr_review._review_threads({"repository": {"pullRequest": {}}})


def test_review_threads_non_dict_connection_raises() -> None:
    """A reviewThreads value that isn't a mapping is surfaced as a GhError."""
    with pytest.raises(GhError):
        pr_review._review_threads({"repository": {"pullRequest": {"reviewThreads": []}}})


def test_pr_summary_non_dict_meta_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """A non-dict ``gh pr view`` payload is surfaced as a GhError."""
    monkeypatch.setattr(pr_review, "list_threads", lambda *_args, **_kwargs: [])

    def runner(_cmd: Sequence[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        """Runner."""
        return completed_process(0, json.dumps([1, 2]))

    with pytest.raises(GhError):
        pr_review.pr_summary(7, run_fn=runner)


def test_remaining_thread_comments_null_node_raises() -> None:
    """A null node from GraphQL is surfaced as a GhError naming the thread id."""

    def runner(_cmd: Sequence[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        """Runner."""
        return completed_process(0, json.dumps({"data": {"node": None}}))

    page_info = {"hasNextPage": True, "endCursor": "CUR"}
    with pytest.raises(GhError):
        pr_review._remaining_thread_comments("PRRT_x", page_info, run_fn=runner)


def test_rollup_summary_empty() -> None:
    """An empty check rollup is rendered as none."""
    assert pr_review.rollup_summary([]) == "none"


def test_rollup_summary_rejects_non_dict_entry() -> None:
    """Test rollup summary rejects non dict entry."""
    with pytest.raises(GhError):
        pr_review.rollup_summary([{"conclusion": "SUCCESS"}, "not a dict"])


def test_owner_name_rejects_invalid_slug(monkeypatch: pytest.MonkeyPatch) -> None:
    """The owner/name splitter rejects a malformed slug."""
    monkeypatch.setattr(gh_runner, "resolve_repo", lambda **_kwargs: "owner/")

    with pytest.raises(GhError):
        pr_review._owner_name()


def _copilot_runner(seen: dict[str, list[list[str]]]) -> Any:
    """Fake runner that records invocations and returns a PR number on view."""

    def runner(cmd: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        """Runner."""
        seen.setdefault("cmds", []).append(list(cmd))
        if cmd[1:3] == ["pr", "view"]:
            return completed_process(0, json.dumps({"number": 7}))
        return completed_process(0, "")

    return runner


def test_request_copilot_review_requests_reviewer() -> None:
    """Test request copilot review requests reviewer."""
    seen: dict[str, list[list[str]]] = {}
    pr_review.request_copilot_review(7, run_fn=_copilot_runner(seen))
    assert seen["cmds"][-1] == [
        "gh",
        "pr",
        "edit",
        "7",
        "--add-reviewer",
        "@copilot",
    ]


def test_request_copilot_review_defaults_to_current_pr() -> None:
    """Test request copilot review defaults to current pr."""
    seen: dict[str, list[list[str]]] = {}
    pr_review.request_copilot_review(run_fn=_copilot_runner(seen))
    assert [
        "gh",
        "pr",
        "edit",
        "7",
        "--add-reviewer",
        "@copilot",
    ] in seen["cmds"]


def test_request_copilot_review_propagates_error() -> None:
    """Test request copilot review propagates error."""

    def runner(cmd: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        """Runner."""
        if cmd[1:3] == ["pr", "view"]:
            return completed_process(0, json.dumps({"number": 7}))
        raise GhError("graphql: rate limited")

    with pytest.raises(GhError):
        pr_review.request_copilot_review(7, run_fn=runner)


def test_edit_pr_builds_title_and_body_arguments() -> None:
    """edit_pr passes the PR number, title, and body straight to gh."""
    seen: dict[str, list[list[str]]] = {}
    pr_review.edit_pr(7, title="New title", body="New body", run_fn=_copilot_runner(seen))
    assert seen["cmds"][-1] == [
        "gh",
        "pr",
        "edit",
        "7",
        "--title",
        "New title",
        "--body",
        "New body",
    ]


def test_edit_pr_defaults_to_current_pr_and_body_only() -> None:
    """edit_pr omits the number when unset and can edit the body alone."""
    seen: dict[str, list[list[str]]] = {}
    pr_review.edit_pr(body="Only body", run_fn=_copilot_runner(seen))
    assert seen["cmds"][-1] == ["gh", "pr", "edit", "--body", "Only body"]


def test_edit_pr_title_only_omits_body_argument() -> None:
    """edit_pr with only a title never passes a --body flag."""
    seen: dict[str, list[list[str]]] = {}
    pr_review.edit_pr(7, title="Only title", run_fn=_copilot_runner(seen))
    assert seen["cmds"][-1] == ["gh", "pr", "edit", "7", "--title", "Only title"]


def test_edit_pr_forwards_body_file_to_gh() -> None:
    """edit_pr passes a body file straight to gh so gh reads it (no oversized arg)."""
    seen: dict[str, list[list[str]]] = {}
    pr_review.edit_pr(7, body_file="-", run_fn=_copilot_runner(seen))
    assert seen["cmds"][-1] == ["gh", "pr", "edit", "7", "--body-file", "-"]


def test_edit_pr_prefers_body_file_over_inline_body() -> None:
    """A body file wins over an inline body so gh never gets an oversized --body."""
    seen: dict[str, list[list[str]]] = {}
    pr_review.edit_pr(body="inline", body_file="notes.md", run_fn=_copilot_runner(seen))
    assert seen["cmds"][-1] == ["gh", "pr", "edit", "--body-file", "notes.md"]


def test_edit_pr_requires_title_or_body() -> None:
    """edit_pr rejects a call with neither a title, body, nor body file."""
    with pytest.raises(GhError):
        pr_review.edit_pr(7)


def test_remaining_thread_comments_result_not_dict_raises() -> None:
    """Test remaining thread comments result not dict raises."""

    def runner(_cmd: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        """Runner."""
        return completed_process(0, json.dumps({"data": "not a mapping"}))

    with pytest.raises(GhError):
        pr_review._remaining_thread_comments(
            "PRRT_x", {"hasNextPage": True, "endCursor": "C"}, run_fn=runner
        )
