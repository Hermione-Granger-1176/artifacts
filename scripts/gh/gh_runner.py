"""Thin, dependency-injected wrappers around the ``gh`` and ``git`` CLIs.

Every public function accepts ``run_fn`` so tests can inject a fake subprocess
runner and exercise the logic without touching the network or a real
repository. Keeping the GitHub plumbing here means the PR and CI helpers share
one place for repository and pull-request detection, timeouts, and retries.

``gh api`` has no built-in retry and treats a single 5xx, network blip, or
rate-limit response as a hard non-zero exit. Per GitHub's API guidance the
shared policy in ``scripts.lib.gh_policy`` retries only transient
infrastructure errors (HTTP 500, 502, 503, and 504 plus network and timeout
failures) with bounded exponential backoff, and fails fast on rate limits
rather than hammering the API (which can get an integration banned). HTTP 501
is treated as fatal, since "Not Implemented" never clears on a retry.
Non-idempotent mutations (posting a reply) opt out of retries so a lost
response never double-posts.

Some environments block GitHub's GraphQL endpoint, and ``gh`` subcommands such
as ``gh pr view`` use GraphQL internally. That failure is reported as
:class:`GhGraphqlUnavailableError`, never retried, and remembered for the rest
of the process. Callers keep GraphQL (or the ``gh`` subcommand) as the primary
path and pass a REST equivalent to :func:`with_rest_fallback` or
:func:`gh_or_rest`; :func:`rest`, :func:`rest_text`, and :func:`rest_pages` are
the shared ``gh api`` client those fallbacks use.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from scripts.lib import gh_policy

RunFunction = Callable[..., subprocess.CompletedProcess[str]]

# Timeouts (seconds). API calls should answer quickly; failed-log downloads can
# be large, so they get a longer budget.
DEFAULT_TIMEOUT = 30
LOG_TIMEOUT = 120

# Retry budget (extra attempts beyond the first) for idempotent calls. The
# classification rules and the bounded exponential backoff live in
# ``scripts.lib.gh_policy`` so every ``gh`` caller in this repository shares one
# rate-limit and transient-failure policy.
DEFAULT_RETRIES = gh_policy.DEFAULT_GH_RETRIES


class GhError(RuntimeError):
    """Raised when a ``gh``/``git`` invocation fails or returns bad data."""


class GhRateLimitError(GhError):
    """Raised when GitHub reports a primary or secondary rate limit.

    Kept distinct from :class:`GhError` so callers never auto-retry it; the
    correct response is to stop and wait for the limit window to reset.
    """


class GhGraphqlUnavailableError(GhError):
    """Raised when the environment refuses GitHub GraphQL requests.

    Distinct from :class:`GhError` so callers can switch to the REST API. Other
    forbidden responses (a missing token scope) stay plain errors and never
    trigger a fallback.
    """


@dataclass
class _GraphqlState:
    """Process-wide verdict on whether GitHub GraphQL can be reached."""

    unavailable: bool = False


_GRAPHQL_STATE = _GraphqlState()


def graphql_unavailable() -> bool:
    """Return whether this process has seen GraphQL refused (so REST should be used)."""
    return _GRAPHQL_STATE.unavailable


def reset_graphql_availability() -> None:
    """Forget a remembered GraphQL-unavailable verdict (tests start from a clean slate)."""
    _GRAPHQL_STATE.unavailable = False


def _graphql_refused(cmd: list[str], detail: str) -> GhGraphqlUnavailableError:
    """Remember that GraphQL is blocked and build the error for ``cmd``."""
    _GRAPHQL_STATE.unavailable = True
    return GhGraphqlUnavailableError(
        f"{_label(cmd)} failed because GitHub GraphQL is unavailable here: {detail}"
    )


def _label(cmd: list[str]) -> str:
    """Return a short command label for error messages (omits long payloads)."""
    return " ".join(cmd[:3])


def _sleep(seconds: float) -> None:
    """Sleep for ``seconds`` (indirection so tests can stub backoff waits)."""
    time.sleep(seconds)


def _run(
    cmd: list[str],
    *,
    run_fn: RunFunction | None = None,
    timeout: int = DEFAULT_TIMEOUT,
    retries: int = 0,
    stdin_text: str | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run a command with a timeout, retrying transient failures.

    Args:
        cmd: The full command vector (e.g. ``["gh", "api", ...]``).
        run_fn: Optional injected subprocess runner.
        timeout: Per-attempt timeout in seconds.
        retries: Extra attempts allowed for transient failures (HTTP 500, 502,
            503, 504, network, and timeout). Rate limits, forbidden responses,
            and every other error are never retried.
        stdin_text: Text piped to the command's standard input. When omitted the
            command inherits this process's standard input.

    Raises:
        GhGraphqlUnavailableError: If the environment blocks GitHub GraphQL.
        GhRateLimitError: If GitHub reports a rate limit.
        GhError: For any other failure, including exhausted retries.
    """
    runner = run_fn or subprocess.run
    options: dict[str, Any] = {"capture_output": True, "text": True, "timeout": timeout}
    if stdin_text is not None:
        options["input"] = stdin_text
    attempt = 0
    while True:
        try:
            result = runner(cmd, **options)
        except subprocess.TimeoutExpired as exc:
            if attempt < retries:
                _sleep(gh_policy.retry_backoff_seconds(attempt))
                attempt += 1
                continue
            raise GhError(f"{_label(cmd)} timed out after {timeout}s") from exc
        except FileNotFoundError as exc:
            raise GhError(f"Command not found: {cmd[0]} (is it installed?)") from exc
        except OSError as exc:
            raise GhError(f"Failed to run {_label(cmd)}: {exc}") from exc

        if result.returncode == 0:
            return result

        # Classify on the real output, but never raise a bare "failed:" when the
        # command exited quietly: the exit code is the only clue left.
        detail = (result.stderr or result.stdout or "").strip()
        reported = detail or f"no output (exit code {result.returncode})"
        kind = gh_policy.classify_gh_failure(detail)
        if kind == "graphql_unavailable":
            raise _graphql_refused(cmd, detail)
        if kind == "rate_limit":
            raise GhRateLimitError(
                f"GitHub rate limit hit running {_label(cmd)}: {detail}\n"
                "Wait for the limit window to reset before retrying."
            )
        if kind == "forbidden":
            raise GhError(
                f"{_label(cmd)} was refused: {detail}\n"
                "The token is missing a permission or scope this call needs."
            )
        if kind == "transient" and attempt < retries:
            _sleep(gh_policy.retry_backoff_seconds(attempt))
            attempt += 1
            continue
        raise GhError(f"{_label(cmd)} failed: {reported}")


def run_gh(
    args: list[str],
    *,
    run_fn: RunFunction | None = None,
    timeout: int = DEFAULT_TIMEOUT,
    retries: int = DEFAULT_RETRIES,
    stdin_text: str | None = None,
) -> str:
    """Run ``gh`` with ``args`` and return its stdout."""
    return _run(
        ["gh", *args], run_fn=run_fn, timeout=timeout, retries=retries, stdin_text=stdin_text
    ).stdout


def run_gh_passthrough(
    args: list[str],
    *,
    run_fn: RunFunction | None = None,
    stdin_text: str | None = None,
) -> int:
    """Run ``gh`` with its output on this terminal and return its exit code.

    Commands such as ``gh pr list`` format their output for a terminal, so
    standard output stays attached and nothing is captured or retried. Standard
    error is captured only to recognize the GraphQL-unavailable verdict, and is
    replayed once the command ends.

    Raises:
        GhGraphqlUnavailableError: If the environment blocks GitHub GraphQL.
        GhError: If ``gh`` cannot be started.
    """
    runner = run_fn or subprocess.run
    options: dict[str, Any] = {"stderr": subprocess.PIPE, "text": True}
    if stdin_text is not None:
        options["input"] = stdin_text
    command = ["gh", *args]
    try:
        result = runner(command, **options)
    except FileNotFoundError as exc:
        raise GhError("Command not found: gh (is it installed?)") from exc
    except OSError as exc:
        raise GhError(f"Failed to run {_label(command)}: {exc}") from exc

    stderr = result.stderr or ""
    if result.returncode != 0 and gh_policy.classify_gh_failure(stderr) == "graphql_unavailable":
        raise _graphql_refused(command, stderr.strip())
    if stderr:
        sys.stderr.write(stderr)
    return result.returncode


def run_git(
    args: list[str],
    *,
    run_fn: RunFunction | None = None,
    timeout: int = DEFAULT_TIMEOUT,
) -> str:
    """Run ``git`` with ``args`` and return its stripped stdout (local, no retry)."""
    return _run(["git", *args], run_fn=run_fn, timeout=timeout).stdout.strip()


def gh_json(
    args: list[str],
    *,
    run_fn: RunFunction | None = None,
    timeout: int = DEFAULT_TIMEOUT,
    retries: int = DEFAULT_RETRIES,
) -> Any:
    """Run ``gh`` with ``args`` and parse its stdout as JSON."""
    stdout = run_gh(args, run_fn=run_fn, timeout=timeout, retries=retries)
    try:
        return json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise GhError(f"gh returned invalid JSON: {exc}") from exc


def _field_args(key: str, value: object) -> list[str]:
    """Return the ``gh api`` field arguments that send ``key`` as ``value``.

    Integers and booleans are typed parameters (``-F``), lists become repeated
    ``key[]`` fields, and everything else is a string (``-f``).
    """
    # bool is a subclass of int, so both go through -F (typed parameters).
    # gh expects JSON booleans, so serialize bool as lowercase true/false
    # rather than Python's True/False, which gh would send as a string.
    if isinstance(value, bool):
        return ["-F", f"{key}={str(value).lower()}"]
    if isinstance(value, int):
        return ["-F", f"{key}={value}"]
    if isinstance(value, list | tuple):
        return [arg for item in value for arg in _field_args(f"{key}[]", item)]
    return ["-f", f"{key}={value}"]


def graphql(
    query: str,
    *,
    variables: Mapping[str, object] | None = None,
    run_fn: RunFunction | None = None,
    timeout: int = DEFAULT_TIMEOUT,
    retries: int = DEFAULT_RETRIES,
) -> Any:
    """Run a GraphQL ``query`` via ``gh api graphql`` and return its ``data``.

    Args:
        query: The GraphQL document. Reference variables as ``$name``.
        variables: Values bound to the query variables. Integers and booleans
            are passed as typed parameters (``-F``); everything else is passed
            as a string (``-f``).
        run_fn: Optional injected subprocess runner.
        timeout: Per-attempt timeout in seconds.
        retries: Extra attempts for transient failures. Pass ``0`` for
            non-idempotent mutations so a lost response never double-applies.

    Returns:
        The ``data`` object from the GraphQL response.

    Raises:
        GhGraphqlUnavailableError: If the environment blocks GitHub GraphQL.
        GhRateLimitError: If the response reports a rate limit.
        GhError: If the response contains other errors or is missing ``data``.
    """
    if graphql_unavailable():
        raise GhGraphqlUnavailableError("GitHub GraphQL is unavailable here; use the REST API.")
    args = ["api", "graphql", "-f", f"query={query}"]
    for key, value in (variables or {}).items():
        args += _field_args(key, value)

    payload = gh_json(args, run_fn=run_fn, timeout=timeout, retries=retries)
    if not isinstance(payload, dict):
        raise GhError("Unexpected GraphQL response shape")
    # gh exits non-zero on GraphQL errors (handled above), but a 200 response
    # can still carry an errors array alongside partial data; catch that too.
    errors = payload.get("errors")
    if errors:
        message = json.dumps(errors)
        # Trust the structured error type first; fall back to string heuristics
        # only when the type is absent or unrecognized.
        rate_limited = any(
            isinstance(error, dict) and error.get("type") == "RATE_LIMITED" for error in errors
        )
        if rate_limited or gh_policy.classify_gh_failure(message) == "rate_limit":
            raise GhRateLimitError(f"GitHub rate limit reported by GraphQL: {message}")
        raise GhError(f"GraphQL errors: {message}")
    if "data" not in payload:
        raise GhError("GraphQL response missing data")
    return payload["data"]


def rest_text(
    endpoint: str,
    *,
    method: str = "GET",
    fields: Mapping[str, object] | None = None,
    headers: Sequence[str] = (),
    run_fn: RunFunction | None = None,
    timeout: int = DEFAULT_TIMEOUT,
    retries: int | None = None,
) -> str:
    """Call a REST ``endpoint`` through ``gh api`` and return the raw response body.

    Args:
        endpoint: The path below ``api.github.com``, such as ``repos/o/n/pulls``.
        method: The HTTP method. ``fields`` become the query string for ``GET``
            and the JSON body for every other method.
        fields: Request parameters. ``GET`` sends them as query arguments (see
            :func:`_field_args` for the typing rules). Other methods send them
            as a JSON body on standard input, so a long comment or PR body
            never meets the operating system's per-argument size limit.
        headers: Extra ``Name: value`` request headers, such as an ``Accept`` type.
        run_fn: Optional injected subprocess runner.
        timeout: Per-attempt timeout in seconds.
        retries: Extra attempts for transient failures. Defaults to the shared
            budget for ``GET`` and to none for mutations, so a lost response
            never applies a write twice.
    """
    args = ["api", "--method", method, endpoint]
    stdin_text = None
    if method == "GET":
        for key, value in (fields or {}).items():
            args += _field_args(key, value)
    elif fields:
        args += ["--input", "-"]
        stdin_text = json.dumps(dict(fields))
    for header in headers:
        args += ["-H", header]
    if retries is None:
        retries = DEFAULT_RETRIES if method == "GET" else 0
    return run_gh(args, run_fn=run_fn, timeout=timeout, retries=retries, stdin_text=stdin_text)


def rest(
    endpoint: str,
    *,
    method: str = "GET",
    fields: Mapping[str, object] | None = None,
    run_fn: RunFunction | None = None,
    timeout: int = DEFAULT_TIMEOUT,
    retries: int | None = None,
) -> Any:
    """Call a REST ``endpoint`` and parse its JSON response (``None`` for an empty body)."""
    stdout = rest_text(
        endpoint, method=method, fields=fields, run_fn=run_fn, timeout=timeout, retries=retries
    )
    if not stdout.strip():
        return None
    try:
        return json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise GhError(f"gh api {endpoint} returned invalid JSON: {exc}") from exc


def rest_pages(
    endpoint: str,
    *,
    items_key: str | None = None,
    fields: Mapping[str, object] | None = None,
    limit: int | None = None,
    accept: Callable[[dict[str, Any]], bool] | None = None,
    run_fn: RunFunction | None = None,
) -> list[dict[str, Any]]:
    """Return every object of a paginated REST list, optionally capped at ``limit``.

    Pages through ``per_page``/``page`` explicitly instead of ``gh api
    --paginate`` so each page parses as one JSON document. ``items_key`` names
    the array inside an envelope response such as ``check_runs``. Objects that
    ``accept`` rejects are skipped and do not count toward ``limit``.
    """
    per_page = 100 if limit is None else max(1, min(limit, 100))
    items: list[dict[str, Any]] = []
    page = 1
    while True:
        payload = rest(
            endpoint, fields={**(fields or {}), "per_page": per_page, "page": page}, run_fn=run_fn
        )
        batch = payload.get(items_key) if items_key and isinstance(payload, dict) else payload
        if not isinstance(batch, list) or not all(isinstance(item, dict) for item in batch):
            raise GhError(f"Unexpected list response shape from {endpoint}.")
        items.extend(item for item in batch if accept is None or accept(item))
        if limit is not None and len(items) >= limit:
            return items[:limit]
        if len(batch) < per_page:
            return items
        page += 1


def as_object(value: object) -> dict[str, Any]:
    """Return ``value`` when it is a mapping, else an empty one (for optional nested objects)."""
    return value if isinstance(value, dict) else {}


def split_list(value: str) -> list[str]:
    """Split a comma-separated option into its non-empty, trimmed items."""
    return [item.strip() for item in value.split(",") if item.strip()]


def default_branch(slug: str, *, run_fn: RunFunction | None = None) -> str:
    """Return the default branch name of the ``owner/name`` repository."""
    branch = as_object(rest(f"repos/{slug}", run_fn=run_fn)).get("default_branch")
    if not isinstance(branch, str) or not branch:
        raise GhError("Could not read the default branch from the repository.")
    return branch


def with_rest_fallback[T](primary: Callable[[], T], fallback: Callable[[], T]) -> T:
    """Run the GraphQL-backed ``primary``; use the REST ``fallback`` when GraphQL is blocked.

    Only the GraphQL-unavailable verdict switches paths. Rate limits, ordinary
    403s, and every other failure from ``primary`` propagate unchanged, and an
    error from ``fallback`` is never retried against GraphQL. Once the verdict
    is remembered, later calls skip ``primary`` entirely.
    """
    if not graphql_unavailable():
        try:
            return primary()
        except GhGraphqlUnavailableError:
            pass
    return fallback()


def gh_or_rest(
    args: list[str],
    fallback: Callable[[], int],
    *,
    run_fn: RunFunction | None = None,
    stdin_text: str | None = None,
) -> int:
    """Run ``gh args`` on this terminal, or ``fallback`` when GraphQL is blocked.

    Returns the exit code of whichever path ran.
    """
    return with_rest_fallback(
        lambda: run_gh_passthrough(args, run_fn=run_fn, stdin_text=stdin_text), fallback
    )


def resolve_repo(*, run_fn: RunFunction | None = None) -> str:
    """Return the ``owner/name`` slug for the current repository.

    Tries the GitHub-aware ``gh repo view`` first, then falls back to parsing
    the ``origin`` git remote (which also covers the rate-limited case and a
    blocked GraphQL endpoint, which ``gh repo view`` needs).
    """
    owner_name = ""
    if not graphql_unavailable():
        try:
            repo_view = gh_json(["repo", "view", "--json", "nameWithOwner"], run_fn=run_fn)
            if isinstance(repo_view, dict):
                owner_name = str(repo_view.get("nameWithOwner", ""))
        except GhError:
            owner_name = ""

    if not owner_name:
        owner_name = _repo_from_remote(run_fn=run_fn)

    if not _is_owner_name(owner_name):
        raise GhError("Could not resolve owner/name; set a GitHub remote or run inside a repo.")
    return owner_name


def _repo_from_remote(*, run_fn: RunFunction | None = None) -> str:
    """Extract ``owner/name`` from the ``origin`` remote URL.

    Handles both SSH (``git@github.com:octo/Hello.git``,
    ``ssh://git@github.com:22/octo/Hello.git``) and HTTPS forms. ``owner/name``
    are always the final two path segments, so any leading ``:`` separator or
    host port is skipped.
    """
    try:
        url = run_git(["remote", "get-url", "origin"], run_fn=run_fn)
    except GhError:
        return ""
    remote_path = _github_remote_path(url)
    if not remote_path:
        return ""
    segments = [segment for segment in remote_path.removesuffix(".git").split("/") if segment]
    if len(segments) < 2:
        return ""
    owner_name = "/".join(segments[-2:])
    return owner_name if _is_owner_name(owner_name) else ""


def _github_remote_path(url: str) -> str:
    """Return the path part from an origin URL only when it is hosted on GitHub."""
    if url.startswith("git@github.com:"):
        return url.removeprefix("git@github.com:")

    parsed = urlparse(url)
    if parsed.hostname != "github.com":
        return ""
    return parsed.path


def _is_owner_name(value: str) -> bool:
    """Return whether ``value`` looks like an ``owner/name`` slug."""
    parts = value.split("/")
    return len(parts) == 2 and all(parts)


def current_pr_number(*, run_fn: RunFunction | None = None) -> int:
    """Return the pull-request number for the current branch."""
    return with_rest_fallback(
        lambda: _current_pr_number_gh(run_fn=run_fn),
        lambda: _current_pr_number_rest(run_fn=run_fn),
    )


def _current_pr_number_gh(*, run_fn: RunFunction | None = None) -> int:
    """Read the current branch's PR number with ``gh pr view``."""
    try:
        data = gh_json(["pr", "view", "--json", "number"], run_fn=run_fn)
    except (GhRateLimitError, GhGraphqlUnavailableError):
        raise
    except GhError as exc:
        detail = str(exc).lower()
        if "no pull request" in detail or "could not resolve to a" in detail:
            raise GhError("No pull request found for the current branch.") from exc
        raise
    try:
        return int(data["number"])
    except (KeyError, TypeError, ValueError) as exc:
        raise GhError("Could not read PR number from gh output.") from exc


def _current_pr_number_rest(*, run_fn: RunFunction | None = None) -> int:
    """Find the open PR whose head is the current branch through the REST API."""
    slug = resolve_repo(run_fn=run_fn)
    branch = current_branch(run_fn=run_fn)
    pulls = rest(
        f"repos/{slug}/pulls",
        fields={"head": f"{slug.split('/')[0]}:{branch}", "state": "open"},
        run_fn=run_fn,
    )
    if not isinstance(pulls, list) or not pulls:
        raise GhError("No pull request found for the current branch.")
    try:
        return int(pulls[0]["number"])
    except (KeyError, TypeError, ValueError) as exc:
        raise GhError("Could not read PR number from the pull request list.") from exc


def current_branch(*, run_fn: RunFunction | None = None) -> str:
    """Return the current git branch name."""
    return run_git(["rev-parse", "--abbrev-ref", "HEAD"], run_fn=run_fn)
