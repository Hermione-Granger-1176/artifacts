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
    "GITLEAKS_LICENSE",
}
EXPECTED_PAGES_BUILD_TYPE = "workflow"
EXPECTED_ACTIONS_ALLOWED = "selected"
EXPECTED_ACTIONS_SHA_PINNING = True
EXPECTED_GITHUB_OWNED_ACTIONS = True
EXPECTED_VERIFIED_ACTIONS = False
EXPECTED_ACTION_PATTERNS = {
    "astral-sh/setup-uv@*",
    "gitleaks/gitleaks-action@*",
    "marocchino/sticky-pull-request-comment@*",
}
PAGES_ENVIRONMENT_NAME = "github-pages"
EXPECTED_PAGES_DEPLOYMENT_POLICIES = {
    "gh-pages:branch",
    "main:branch",
    "refs/pull/*/merge:branch",
}
# GitHub's own secret scanning, which is free on public repositories. It is the
# layer the gitleaks job cannot provide: push protection refuses the push that
# carries a secret, rather than reporting it once it is already in history and
# the credential has to be rotated regardless. The three GitHub App private keys
# in EXPECTED_REPOSITORY_SECRETS are what makes that distinction matter here.
EXPECTED_SECURITY_ANALYSIS = {
    "secret_scanning",
    "secret_scanning_push_protection",
}
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
        raise RuntimeError(f"Actions {key} response must include a {key} list")

    names: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            raise RuntimeError(f"Actions {key} response contains a non-object entry")
        name = item.get("name")
        if not isinstance(name, str) or not name:
            raise RuntimeError(f"Actions {key} response contains an entry without a name")
        names.add(name)
    return names


def append_missing_items(
    issues: list[str], *, actual: set[str], expected: set[str], label: str
) -> None:
    """Append a formatted issue when expected items are missing."""
    missing_items = expected - actual
    if missing_items:
        issues.append(f"missing {label}: " + ", ".join(sorted(missing_items)))


def append_unexpected_items(
    issues: list[str], *, actual: set[str], expected: set[str], label: str
) -> None:
    """Append a formatted issue when unexpected items are present."""
    unexpected_items = actual - expected
    if unexpected_items:
        issues.append(f"unexpected {label}: " + ", ".join(sorted(unexpected_items)))


def extract_allowed_action_patterns(payload: object) -> set[str]:
    """Return the non-GitHub action patterns from a selected-actions response."""
    if not isinstance(payload, dict):
        raise RuntimeError("Selected Actions settings must be a JSON object")

    raw_patterns = payload.get("patterns_allowed")
    if not isinstance(raw_patterns, list):
        raise RuntimeError("Selected Actions patterns_allowed must be a JSON array")

    patterns: set[str] = set()
    for pattern in raw_patterns:
        if not isinstance(pattern, str):
            raise RuntimeError("Selected Actions patterns_allowed must contain strings")
        if not pattern:
            raise RuntimeError("Selected Actions patterns_allowed must contain non-empty strings")
        patterns.add(pattern)
    return patterns


def extract_deployment_branch_policies(payload: object) -> set[str]:
    """Return normalized name and type pairs from an environment policy response."""
    if not isinstance(payload, dict):
        raise RuntimeError("Deployment branch policies must be a JSON object")

    raw_policies = payload.get("branch_policies")
    if not isinstance(raw_policies, list):
        raise RuntimeError("Deployment branch policies must include a JSON array")

    policies: set[str] = set()
    for policy in raw_policies:
        if not isinstance(policy, dict):
            raise RuntimeError("Deployment branch policies contain a non-object entry")
        name = policy.get("name")
        if not isinstance(name, str) or not name:
            raise RuntimeError("Deployment branch policies contain an entry without a name")
        policy_type = policy.get("type")
        if not isinstance(policy_type, str) or not policy_type:
            raise RuntimeError("Deployment branch policies contain an entry without a type")
        policies.add(f"{name}:{policy_type}")
    return policies


def extract_required_checks(protection: object) -> set[str]:
    """Return the normalized set of required status checks from branch protection."""
    if not isinstance(protection, dict):
        return set()

    required_status_checks = protection.get("required_status_checks")
    if required_status_checks is None:
        return set()
    if not isinstance(required_status_checks, dict):
        raise RuntimeError("Branch protection required status checks must be a JSON object")

    contexts = required_status_checks.get("contexts")
    checks = required_status_checks.get("checks")
    if contexts is not None and not isinstance(contexts, list):
        raise RuntimeError("Branch protection contexts must be a JSON array")
    if checks is not None and not isinstance(checks, list):
        raise RuntimeError("Branch protection checks must be a JSON array")

    names = {context for context in (contexts or []) if isinstance(context, str) and context}
    names.update(
        item["context"]
        for item in (checks or [])
        if isinstance(item, dict) and isinstance(item.get("context"), str) and item["context"]
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
    if isinstance(ruleset_value, int) and not isinstance(ruleset_value, bool) and ruleset_value > 0:
        return ruleset_value
    if isinstance(ruleset_value, str) and ruleset_value.isdigit() and int(ruleset_value) > 0:
        return int(ruleset_value)
    return None


def load_ruleset_detail(
    repo: str,
    ruleset: object,
    *,
    run_gh_api_json_fn: Callable[..., object] = run_gh_api_json,
) -> object:
    """Fetch one ruleset detail payload when the summary response is incomplete."""
    if not isinstance(ruleset, dict):
        raise RuntimeError("Rulesets response contains a non-object entry")
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


def enabled_security_features(repository: dict[str, object]) -> set[str]:
    """Return the security_and_analysis features reported as enabled.

    The block is absent for callers without administration access, which reads
    the same as every feature being off. That is the safe direction: the audit
    reports it as drift rather than certifying a setting it could not see.
    """
    raw = repository.get("security_and_analysis")
    if not isinstance(raw, dict):
        return set()
    enabled: set[str] = set()
    for name, setting in raw.items():
        if (
            isinstance(name, str)
            and isinstance(setting, dict)
            and setting.get("status") == "enabled"
        ):
            enabled.add(name)
    return enabled


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
    actions_permissions = run_gh_api_json_fn(
        f"repos/{repo}/actions/permissions",
        description=f"reading Actions permissions for {repo}",
        required_permission="administration: read",
    )
    selected_actions = run_gh_api_json_fn(
        f"repos/{repo}/actions/permissions/selected-actions",
        description=f"reading selected Actions for {repo}",
        required_permission="administration: read",
    )
    pages_environment = run_gh_api_json_fn(
        f"repos/{repo}/environments/{PAGES_ENVIRONMENT_NAME}",
        description=f"reading {PAGES_ENVIRONMENT_NAME} environment for {repo}",
        required_permission="administration: read",
    )
    pages_deployment_policies = run_gh_api_json_fn(
        f"repos/{repo}/environments/{PAGES_ENVIRONMENT_NAME}/deployment-branch-policies",
        description=f"reading {PAGES_ENVIRONMENT_NAME} deployment policies for {repo}",
        required_permission="administration: read",
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
    require_response_type(actions_permissions, dict, "Actions permissions must be a JSON object")
    require_response_type(selected_actions, dict, "Selected Actions settings must be a JSON object")
    require_response_type(
        pages_environment, dict, f"{PAGES_ENVIRONMENT_NAME} environment must be a JSON object"
    )
    require_response_type(protection, dict, "Branch protection settings must be a JSON object")
    require_response_type(variables, dict, "Actions variables response must be a JSON object")
    require_response_type(secrets, dict, "Actions secrets response must be a JSON object")
    require_response_type(rulesets, list, "Rulesets response must be a JSON array")
    require_response_type(
        pages_deployment_policies,
        dict,
        f"{PAGES_ENVIRONMENT_NAME} deployment policies must be a JSON object",
    )

    repository = cast("dict[str, object]", repository)
    pages = cast("dict[str, object]", pages)
    actions_permissions = cast("dict[str, object]", actions_permissions)
    selected_actions = cast("dict[str, object]", selected_actions)
    pages_environment = cast("dict[str, object]", pages_environment)
    protection = cast("dict[str, object]", protection)
    variables = cast("dict[str, object]", variables)
    secrets = cast("dict[str, object]", secrets)
    rulesets = cast("list[object]", rulesets)
    pages_deployment_policies = cast("dict[str, object]", pages_deployment_policies)
    detailed_rulesets = [
        load_ruleset_detail(repo, ruleset, run_gh_api_json_fn=run_gh_api_json_fn)
        for ruleset in rulesets
    ]

    issues = []
    actual_default_branch = repository.get("default_branch")
    if not isinstance(actual_default_branch, str) or not actual_default_branch:
        raise RuntimeError("Repository metadata must include a string default_branch")
    if actual_default_branch != default_branch:
        issues.append(f"default branch is {actual_default_branch!r} instead of {default_branch!r}")

    raw_pages_source = pages.get("source")
    if raw_pages_source is not None and not isinstance(raw_pages_source, dict):
        raise RuntimeError("Pages source must be a JSON object when present")
    pages_source = raw_pages_source if isinstance(raw_pages_source, dict) else {}
    pages_source_branch = pages_source.get("branch")
    pages_source_path = pages_source.get("path")
    if pages_source_branch is not None and (
        not isinstance(pages_source_branch, str) or not pages_source_branch
    ):
        raise RuntimeError("Pages source branch must be a non-empty string when present")
    if pages_source_path is not None and (
        not isinstance(pages_source_path, str) or not pages_source_path
    ):
        raise RuntimeError("Pages source path must be a non-empty string when present")
    pages_build_type = pages.get("build_type")
    if not isinstance(pages_build_type, str) or not pages_build_type:
        raise RuntimeError("Pages settings must include a string build_type")
    pages_https_enforced = pages.get("https_enforced")
    if not isinstance(pages_https_enforced, bool):
        raise RuntimeError("Pages settings must include a boolean https_enforced value")
    if pages_build_type == "legacy":
        if pages_source_branch is None:
            raise RuntimeError("Legacy Pages settings must include a source branch")
        if pages_source_path is None:
            raise RuntimeError("Legacy Pages settings must include a source path")
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

    pages_source_path = pages_source_path or "/"

    actions_enabled = actions_permissions.get("enabled")
    if actions_enabled is not True:
        issues.append("GitHub Actions are not enabled")
    actions_allowed = actions_permissions.get("allowed_actions")
    if actions_allowed != EXPECTED_ACTIONS_ALLOWED:
        issues.append(
            f"Actions allowed policy is {actions_allowed!r} instead of {EXPECTED_ACTIONS_ALLOWED!r}"
        )
    actions_sha_pinning = actions_permissions.get("sha_pinning_required")
    if actions_sha_pinning is not EXPECTED_ACTIONS_SHA_PINNING:
        issues.append("Actions are not required to use full-length commit SHAs")

    github_owned_allowed = selected_actions.get("github_owned_allowed")
    if github_owned_allowed is not EXPECTED_GITHUB_OWNED_ACTIONS:
        issues.append("GitHub-owned Actions are not allowed")
    verified_allowed = selected_actions.get("verified_allowed")
    if verified_allowed is not EXPECTED_VERIFIED_ACTIONS:
        issues.append("Verified Marketplace Actions are allowed")
    allowed_action_patterns = extract_allowed_action_patterns(selected_actions)
    append_missing_items(
        issues,
        actual=allowed_action_patterns,
        expected=EXPECTED_ACTION_PATTERNS,
        label="allowed Actions patterns",
    )
    append_unexpected_items(
        issues,
        actual=allowed_action_patterns,
        expected=EXPECTED_ACTION_PATTERNS,
        label="allowed Actions patterns",
    )

    environment_policy = pages_environment.get("deployment_branch_policy")
    if not isinstance(environment_policy, dict):
        raise RuntimeError(
            f"{PAGES_ENVIRONMENT_NAME} environment deployment policy must be a JSON object"
        )
    if environment_policy.get("custom_branch_policies") is not True:
        issues.append(f"{PAGES_ENVIRONMENT_NAME} does not use selected deployment policies")
    if environment_policy.get("protected_branches") is not False:
        issues.append(f"{PAGES_ENVIRONMENT_NAME} allows protected-branch-only deployment policy")
    deployment_policies = extract_deployment_branch_policies(pages_deployment_policies)
    append_missing_items(
        issues,
        actual=deployment_policies,
        expected=EXPECTED_PAGES_DEPLOYMENT_POLICIES,
        label=f"{PAGES_ENVIRONMENT_NAME} deployment policies",
    )
    append_unexpected_items(
        issues,
        actual=deployment_policies,
        expected=EXPECTED_PAGES_DEPLOYMENT_POLICIES,
        label=f"{PAGES_ENVIRONMENT_NAME} deployment policies",
    )

    security_features = enabled_security_features(repository)
    append_missing_items(
        issues,
        actual=security_features,
        expected=EXPECTED_SECURITY_ANALYSIS,
        label="security and analysis features",
    )

    required_checks = extract_required_checks(protection)
    branch_label = f"{default_branch} branch protection"

    missing_checks = EXPECTED_REQUIRED_CHECKS - required_checks
    if missing_checks:
        issues.append(
            f"{branch_label} is missing required checks: " + ", ".join(sorted(missing_checks))
        )

    review_settings = protection.get("required_pull_request_reviews")
    if review_settings is None:
        issues.append(f"{branch_label} does not require at least 1 approving review")
    elif not isinstance(review_settings, dict):
        raise RuntimeError("Branch protection review settings must be a JSON object")
    else:
        approvals = review_settings.get("required_approving_review_count", 0)
        if not isinstance(approvals, int) or isinstance(approvals, bool):
            raise RuntimeError("Branch protection approval count must be an integer")
        if approvals < 1:
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
        "actions-allowed": actions_allowed,
        "actions-selected-patterns": sorted(allowed_action_patterns),
        "actions-sha-pinning-required": actions_sha_pinning,
        "gh-pages-rules": sorted(extract_ruleset_rule_types(pages_ruleset)),
        "github-pages-deployment-policies": sorted(deployment_policies),
        "pages-branch": pages_source_branch,
        "pages-build-type": pages_build_type,
        "pages-https-enforced": pages_https_enforced,
        "pages-path": pages_source_path,
        "required-checks": sorted(required_checks),
        "security-features": sorted(security_features),
        "gh-pages-ruleset": True,
    }
