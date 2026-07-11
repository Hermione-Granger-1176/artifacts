from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

import scripts.ci.refresh_action_shas as ras

if TYPE_CHECKING:
    from pathlib import Path
    from urllib.request import Request

SHA_A = "a" * 40
SHA_B = "b" * 40


class FakeResponse:
    """Minimal file-like context manager returned by the fake urlopen."""

    def __init__(self, payload: object) -> None:
        self._payload = payload

    def read(self, amt: int | None = None) -> bytes:
        """Return the JSON-encoded payload bytes."""
        del amt
        return json.dumps(self._payload).encode("utf-8")

    def __enter__(self) -> FakeResponse:
        """Enter the response context."""
        return self

    def __exit__(self, *args: object) -> None:
        """Exit the response context."""
        return None


class FakeUrlOpen:
    """Callable urlopen seam that replays payloads or raises errors in order."""

    def __init__(self, results: list[object]) -> None:
        self._results = list(results)
        self.requests: list[Request] = []
        self.timeouts: list[float] = []

    def __call__(self, request: Request, *, timeout: float) -> FakeResponse:
        """Record the call and replay the next queued result."""
        self.requests.append(request)
        self.timeouts.append(timeout)
        result = self._results.pop(0)
        if isinstance(result, Exception):
            raise result
        return FakeResponse(result)


class StubResolver:
    """Resolver stub that records lookups and returns a fixed SHA."""

    def __init__(self, sha: str) -> None:
        self.sha = sha
        self.calls: list[tuple[str, str]] = []

    def resolve(self, action: str, ref: str) -> str:
        """Record the lookup and return the fixed SHA."""
        self.calls.append((action, ref))
        return self.sha


def test_resolve_caches_repeated_lookups() -> None:
    """Resolve caches repeated lookups."""
    fake = FakeUrlOpen([{"sha": SHA_A}])
    resolver = ras.ActionShaResolver(token="secret", urlopen_fn=fake, sleep_fn=lambda _s: None)

    assert resolver.resolve("actions/checkout", "v7") == SHA_A
    assert resolver.resolve("actions/checkout", "v7") == SHA_A
    assert len(fake.requests) == 1

    request = fake.requests[0]
    assert request.full_url == "https://api.github.com/repos/actions/checkout/commits/v7"
    assert request.headers["Authorization"] == "Bearer secret"
    assert request.headers["Accept"] == "application/vnd.github+json"
    assert fake.timeouts == [ras.REQUEST_TIMEOUT_SECONDS]


def test_resolve_derives_repo_from_subpath_action() -> None:
    """Resolve derives repo from subpath action."""
    fake = FakeUrlOpen([{"sha": SHA_A}])
    resolver = ras.ActionShaResolver(token="t", urlopen_fn=fake, sleep_fn=lambda _s: None)

    assert resolver.resolve("github/codeql-action/init", "v4") == SHA_A
    request_url = fake.requests[0].full_url
    assert request_url == "https://api.github.com/repos/github/codeql-action/commits/v4"


def test_resolve_retries_then_succeeds() -> None:
    """Resolve retries then succeeds."""
    sleeps: list[float] = []
    fake = FakeUrlOpen([RuntimeError("boom"), {"sha": SHA_B}])
    resolver = ras.ActionShaResolver(
        token="t", urlopen_fn=fake, sleep_fn=sleeps.append, backoff_seconds=0.5
    )

    assert resolver.resolve("owner/repo", "v1") == SHA_B
    assert len(fake.requests) == 2
    assert sleeps == [0.5]


def test_resolve_exhausts_retries_and_raises_with_context() -> None:
    """Resolve exhausts retries and raises a contextual error chained to the last one."""
    sleeps: list[float] = []
    last = RuntimeError("e3")
    fake = FakeUrlOpen([RuntimeError("e1"), RuntimeError("e2"), last])
    resolver = ras.ActionShaResolver(token="t", urlopen_fn=fake, sleep_fn=sleeps.append)

    with pytest.raises(RuntimeError, match="Failed to resolve owner/repo@v1: e3") as excinfo:
        resolver.resolve("owner/repo", "v1")
    assert excinfo.value.__cause__ is last
    assert len(fake.requests) == 3
    assert sleeps == [ras.RETRY_BACKOFF_SECONDS, ras.RETRY_BACKOFF_SECONDS * 2]


def test_fetch_raises_when_no_attempts_are_configured() -> None:
    """Fetch raises when no attempts are configured."""
    fake = FakeUrlOpen([])
    resolver = ras.ActionShaResolver(
        token="t", urlopen_fn=fake, sleep_fn=lambda _s: None, max_attempts=0
    )

    with pytest.raises(RuntimeError, match="Failed to resolve owner/repo@v1"):
        resolver.resolve("owner/repo", "v1")
    assert fake.requests == []


def test_commit_sha_extracts_valid_sha() -> None:
    """Commit sha extracts valid sha."""
    assert ras._commit_sha({"sha": SHA_A}) == SHA_A


def test_commit_sha_rejects_missing_or_non_dict_payloads() -> None:
    """Commit sha rejects missing or non dict payloads."""
    with pytest.raises(RuntimeError, match="did not include a commit SHA"):
        ras._commit_sha({"sha": 5})
    with pytest.raises(RuntimeError, match="did not include a commit SHA"):
        ras._commit_sha(["not", "a", "dict"])


def test_default_urlopen_delegates_to_stdlib(monkeypatch: pytest.MonkeyPatch) -> None:
    """Default urlopen delegates to the standard library urlopen."""
    captured: dict[str, object] = {}
    sentinel = object()

    def fake_urlopen(request: Request, timeout: float) -> object:
        captured["request"] = request
        captured["timeout"] = timeout
        return sentinel

    monkeypatch.setattr(ras, "urlopen", fake_urlopen)

    request = ras.Request("https://example.test")
    assert ras._default_urlopen(request, timeout=3) is sentinel
    assert captured["request"] is request
    assert captured["timeout"] == 3


def test_should_skip_local_and_docker_actions() -> None:
    """Should skip local and docker actions."""
    assert ras._should_skip("./.github/actions/ci-setup", "main") is True
    assert ras._should_skip("docker://alpine", "3") is True


def test_should_skip_expression_refs() -> None:
    """Should skip expression refs."""
    assert ras._should_skip("${{ matrix.action }}", "v1") is True
    assert ras._should_skip("owner/repo", "${{ env.REF }}") is True


def test_should_skip_already_pinned_sha() -> None:
    """Should skip already pinned sha."""
    assert ras._should_skip("owner/repo", SHA_A) is True


def test_should_not_skip_tag_reference() -> None:
    """Should not skip tag reference."""
    assert ras._should_skip("owner/repo", "v4") is False


def test_rewrite_line_ignores_non_uses_lines() -> None:
    """Rewrite line ignores non uses lines."""
    resolver = StubResolver(SHA_A)
    assert ras.rewrite_line("name: Foo", resolver) is None
    assert resolver.calls == []


def test_rewrite_line_skips_local_actions() -> None:
    """Rewrite line skips local actions."""
    resolver = StubResolver(SHA_A)
    assert ras.rewrite_line("        uses: ./.github/actions/ci-setup", resolver) is None
    assert resolver.calls == []


def test_rewrite_line_repins_mapping_form_tag() -> None:
    """Rewrite line repins mapping form tag."""
    resolver = StubResolver(SHA_A)
    line = "        uses: actions/checkout@v7.0.0 # stale"
    assert ras.rewrite_line(line, resolver) == f"        uses: actions/checkout@{SHA_A} # v7.0.0"
    assert resolver.calls == [("actions/checkout", "v7.0.0")]


def test_rewrite_line_repins_list_form_tag() -> None:
    """Rewrite line repins list form tag."""
    resolver = StubResolver(SHA_B)
    result = ras.rewrite_line("  - uses: actions/foo@v1", resolver)
    assert result == f"  - uses: actions/foo@{SHA_B} # v1"


def test_rewrite_file_updates_and_rewrites_content(tmp_path: Path) -> None:
    """Rewrite file updates and rewrites content."""
    path = tmp_path / "wf.yml"
    path.write_text("name: x\n        uses: actions/checkout@v7\n", encoding="utf-8")
    resolver = StubResolver(SHA_A)

    assert ras.rewrite_file(path, resolver) is True
    content = path.read_text(encoding="utf-8")
    assert f"uses: actions/checkout@{SHA_A} # v7" in content
    assert content.endswith("\n")


def test_rewrite_file_leaves_pinned_file_untouched(tmp_path: Path) -> None:
    """Rewrite file leaves pinned file untouched."""
    path = tmp_path / "wf.yml"
    original = f"name: x\n        uses: actions/checkout@{SHA_A} # v7\n"
    path.write_text(original, encoding="utf-8")

    assert ras.rewrite_file(path, StubResolver(SHA_B)) is False
    assert path.read_text(encoding="utf-8") == original


def test_iter_target_files_collects_workflows_and_actions(tmp_path: Path) -> None:
    """Iter target files collects workflows and composite actions."""
    workflows = tmp_path / "workflows"
    workflows.mkdir()
    (workflows / "a.yml").write_text("", encoding="utf-8")
    (workflows / "b.yaml").write_text("", encoding="utf-8")
    (workflows / "ignore.txt").write_text("", encoding="utf-8")

    actions = tmp_path / "actions"
    (actions / "one").mkdir(parents=True)
    (actions / "one" / "action.yml").write_text("", encoding="utf-8")
    (actions / "two").mkdir(parents=True)
    (actions / "two" / "action.yaml").write_text("", encoding="utf-8")

    names = [path.name for path in ras.iter_target_files(workflows, actions)]
    assert names == ["a.yml", "b.yaml", "action.yml", "action.yaml"]


def test_refresh_action_shas_returns_only_changed_files(tmp_path: Path) -> None:
    """Refresh action shas returns only changed files."""
    changed = tmp_path / "c.yml"
    changed.write_text("        uses: actions/x@v1\n", encoding="utf-8")
    unchanged = tmp_path / "u.yml"
    unchanged.write_text("name: y\n", encoding="utf-8")

    result = ras.refresh_action_shas(resolver=StubResolver(SHA_B), files=[changed, unchanged])
    assert result == [changed]


def test_main_requires_a_token(monkeypatch: pytest.MonkeyPatch) -> None:
    """Main requires a token."""
    monkeypatch.delenv("GH_TOKEN", raising=False)
    with pytest.raises(SystemExit, match="GH_TOKEN is required"):
        ras.main([])


def test_main_reports_updated_files(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Main reports updated files."""
    monkeypatch.setenv("GH_TOKEN", "t")
    updated = [ras.REPO_ROOT / ".github" / "workflows" / "demo.yml"]
    monkeypatch.setattr(ras, "refresh_action_shas", lambda **_kwargs: updated)

    assert ras.main([]) == 0
    assert "Updated .github/workflows/demo.yml" in capsys.readouterr().out


def test_main_reports_when_nothing_changed(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Main reports when nothing changed."""
    monkeypatch.setenv("GH_TOKEN", "t")
    monkeypatch.setattr(ras, "refresh_action_shas", lambda **_kwargs: [])

    assert ras.main([]) == 0
    assert "No action references needed updating" in capsys.readouterr().out
