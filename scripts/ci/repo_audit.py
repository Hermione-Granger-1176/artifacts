from __future__ import annotations

from typing import TYPE_CHECKING, cast

from scripts.lib.gh_api import run_gh_api_json

if TYPE_CHECKING:
    from collections.abc import Callable

EXPECTED_REQUIRED_CHECKS = {"verify", "secret-scan", "dependency-review"}
EXPECTED_REPOSITORY_VARIABLES = {"APP_ID", "ESCALATION_APP_ID", "AUDIT_APP_ID"}
EXPECTED_REPOSITORY_SECRETS = {
    "APP_PRIVATE_KEY",
    "ESCALATION_APP_PRIVATE_KEY",
    "AUDIT_APP_PRIVATE_KEY",
}
EXPECTED_PAGES_BUILD_TYPE = "workflow"
EXPECTED_PAGES_RULESET_RULES = {
    "creation",
    "deletion",
    "non_fast_forward",
    "required_linear_history",
    "required_signatures",
    "update",
}


def require_response_type(value: object, expected_type: type, message: str) -> None:
    """Raise when a GitHub API response does not match the expected JSON shape."""
    if not isinstance(value, expected_type):
        raise RuntimeError(message)


def collect_named_items(payload: dict[str, object], key: str) -> set[str]:
    """Collect string ``name`` fields from a GitHub API list payload."""
    items = payload.get(key)
    if not isinstance(items, list):
        return set()

    return {
        item["name"]
        for item in items
        if isinstance(item, dict) and isinstance(item.get("name"), str)
    }


def append_missing_items(
    issues: list[str], *, actual: set[str], expected: set[str], label: str
) -> None:
    """Append a formatted issue when expected items are missing."""
    missing_items = expected - actual
    if missing_items:
        issues.append(f"missing {label}: " + ", ".join(sorted(missing_items)))


def extract_required_checks(protection: object) -> set[str]:
    """Return the normalized set of required status checks from branch protection."""
    if not isinstance(protection, dict):
        return set()

    required_status_checks = protection.get("required_status_checks")
    if not isinstance(required_status_checks, dict):
        return set()

    contexts = required_status_checks.get("contexts")
    checks = required_status_checks.get("checks")
    names = {str(context) for context in (contexts or []) if isinstance(context, str) and context}
    names.update(
        str(item.get("context"))
        for item in (checks or [])
        if isinstance(item, dict) and isinstance(item.get("context"), str)
    )
    return names


def ruleset_targets_branch(ruleset: object, branch_name: str) -> bool:
    """Return whether a ruleset explicitly targets the given branch name."""
    if not isinstance(ruleset, dict) or ruleset.get("target") != "branch":
        return False

    conditions = ruleset.get("conditions")
    if not isinstance(conditions, dict):
        return False

    ref_name = conditions.get("ref_name")
    if not isinstance(ref_name, dict):
        return False

    include = ref_name.get("include")
    if not isinstance(include, list):
        return False

    expected_refs = {branch_name, f"refs/heads/{branch_name}"}
    return any(isinstance(value, str) and value in expected_refs for value in include)


def extract_ruleset_rule_types(ruleset: object) -> set[str]:
    """Return normalized rule types from one ruleset payload."""
    if not isinstance(ruleset, dict):
        return set()

    rules = ruleset.get("rules")
    if not isinstance(rules, list):
        return set()

    return {
        str(rule.get("type"))
        for rule in rules
        if isinstance(rule, dict) and isinstance(rule.get("type"), str)
    }


def ruleset_id(ruleset: object) -> int | None:
    """Return the numeric ruleset id when one is present."""
    if not isinstance(ruleset, dict):
        return None

    ruleset_value = ruleset.get("id")
    if isinstance(ruleset_value, int):
        return ruleset_value
    if isinstance(ruleset_value, str) and ruleset_value.isdigit():
        return int(ruleset_value)
    return None


def load_ruleset_detail(
    repo: str,
    ruleset: object,
    *,
    run_gh_api_json_fn: Callable[..., object] = run_gh_api_json,
) -> object:
    """Fetch one ruleset detail payload when the summary response is incomplete."""
    if isinstance(ruleset, dict) and isinstance(ruleset.get("conditions"), dict):
        return ruleset

    ruleset_value = ruleset_id(ruleset)
    if ruleset_value is None:
        return ruleset

    detail = run_gh_api_json_fn(
        f"repos/{repo}/rulesets/{ruleset_value}",
        description=f"reading ruleset {ruleset_value} for {repo}",
        required_permission="administration: read",
    )
    require_response_type(detail, dict, f"Ruleset detail for {ruleset_value} must be a JSON object")
    return cast("dict[str, object]", detail)


def audit_repo_settings(
    *,
    repo: str,
    default_branch: str = "main",
    pages_branch: str = "gh-pages",
    run_gh_api_json_fn: Callable[..., object] = run_gh_api_json,
) -> dict[str, object]:
    """Audit critical repository settings that the release flow depends on."""
    repository = run_gh_api_json_fn(
        f"repos/{repo}",
        description=f"reading repository metadata for {repo}",
        required_permission="metadata: read",
    )
    pages = run_gh_api_json_fn(
        f"repos/{repo}/pages",
        description=f"reading Pages settings for {repo}",
        required_permission="pages: read",
    )
    protection = run_gh_api_json_fn(
        f"repos/{repo}/branches/{default_branch}/protection",
        description=f"reading branch protection for {repo}:{default_branch}",
        required_permission="administration: read",
    )
    variables = run_gh_api_json_fn(
        f"repos/{repo}/actions/variables",
        description=f"listing Actions variables for {repo}",
        required_permission="actions_variables: read",
    )
    secrets = run_gh_api_json_fn(
        f"repos/{repo}/actions/secrets",
        description=f"listing Actions secrets for {repo}",
        required_permission="secrets: read",
    )
    rulesets = run_gh_api_json_fn(
        f"repos/{repo}/rulesets",
        description=f"listing rulesets for {repo}",
        required_permission="administration: read",
    )

    require_response_type(repository, dict, "Repository metadata must be a JSON object")
    require_response_type(pages, dict, "Pages settings must be a JSON object")
    require_response_type(protection, dict, "Branch protection settings must be a JSON object")
    require_response_type(variables, dict, "Actions variables response must be a JSON object")
    require_response_type(secrets, dict, "Actions secrets response must be a JSON object")
    require_response_type(rulesets, list, "Rulesets response must be a JSON array")

    repository = cast("dict[str, object]", repository)
    pages = cast("dict[str, object]", pages)
    protection = cast("dict[str, object]", protection)
    variables = cast("dict[str, object]", variables)
    secrets = cast("dict[str, object]", secrets)
    rulesets = cast("list[object]", rulesets)
    detailed_rulesets = [
        load_ruleset_detail(repo, ruleset, run_gh_api_json_fn=run_gh_api_json_fn)
        for ruleset in rulesets
    ]

    issues = []
    actual_default_branch = repository.get("default_branch")
    if actual_default_branch != default_branch:
        issues.append(f"default branch is {actual_default_branch!r} instead of {default_branch!r}")

    raw_pages_source = pages.get("source")
    pages_source = raw_pages_source if isinstance(raw_pages_source, dict) else {}
    pages_source_branch = pages_source.get("branch")
    pages_source_path = pages_source.get("path") or "/"
    pages_build_type = pages.get("build_type")
    pages_https_enforced = pages.get("https_enforced")
    if pages_build_type == "legacy":
        if pages_source_branch != pages_branch:
            issues.append(
                f"Pages source branch is {pages_source_branch!r} instead of {pages_branch!r}"
            )
        if pages_source_path != "/":
            issues.append(f"Pages source path is {pages_source_path!r} instead of '/'")
    if pages_build_type != EXPECTED_PAGES_BUILD_TYPE:
        issues.append(
            f"Pages build type is {pages_build_type!r} instead of {EXPECTED_PAGES_BUILD_TYPE!r}"
        )
    if pages_https_enforced is not True:
        issues.append("Pages HTTPS is not enforced")

    required_checks = extract_required_checks(protection)
    branch_label = f"{default_branch} branch protection"

    missing_checks = EXPECTED_REQUIRED_CHECKS - required_checks
    if missing_checks:
        issues.append(
            f"{branch_label} is missing required checks: " + ", ".join(sorted(missing_checks))
        )

    review_settings = protection.get("required_pull_request_reviews")
    if (
        not isinstance(review_settings, dict)
        or int(review_settings.get("required_approving_review_count", 0)) < 1
    ):
        issues.append(f"{branch_label} does not require at least 1 approving review")

    for key, message in (
        ("required_signatures", f"{branch_label} does not require signed commits"),
        ("required_linear_history", f"{branch_label} does not require linear history"),
        (
            "required_conversation_resolution",
            f"{branch_label} does not require conversation resolution",
        ),
    ):
        setting = protection.get(key)
        if not isinstance(setting, dict) or setting.get("enabled") is not True:
            issues.append(message)

    variable_names = collect_named_items(variables, "variables")
    append_missing_items(
        issues,
        actual=variable_names,
        expected=EXPECTED_REPOSITORY_VARIABLES,
        label="repository variables",
    )

    secret_names = collect_named_items(secrets, "secrets")
    append_missing_items(
        issues,
        actual=secret_names,
        expected=EXPECTED_REPOSITORY_SECRETS,
        label="repository secrets",
    )

    pages_ruleset = next(
        (ruleset for ruleset in detailed_rulesets if ruleset_targets_branch(ruleset, pages_branch)),
        None,
    )
    if pages_ruleset is None:
        issues.append(f"no branch ruleset explicitly targets {pages_branch!r}")
    else:
        pages_rule_types = extract_ruleset_rule_types(pages_ruleset)
        missing_pages_rules = EXPECTED_PAGES_RULESET_RULES - pages_rule_types
        if missing_pages_rules:
            issues.append(
                f"{pages_branch!r} ruleset is missing rules: "
                + ", ".join(sorted(missing_pages_rules))
            )

    if issues:
        issue_list = "\n- ".join(issues)
        raise ValueError(f"Repository settings audit failed:\n- {issue_list}")

    return {
        "default-branch": actual_default_branch,
        "gh-pages-rules": sorted(extract_ruleset_rule_types(pages_ruleset)),
        "pages-branch": pages_source_branch,
        "pages-build-type": pages_build_type,
        "pages-https-enforced": pages_https_enforced,
        "pages-path": pages_source_path,
        "required-checks": sorted(required_checks),
        "gh-pages-ruleset": True,
    }
