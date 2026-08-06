from __future__ import annotations

import json

import pytest

import scripts.ci.repo_audit as repo_audit
import scripts.ci.workflow_helpers as workflow_helpers


def test_collect_named_items_rejects_non_lists_and_non_dict_entries() -> None:
    """Malformed Actions list responses must not be treated as empty lists."""
    with pytest.raises(RuntimeError, match="must include a variables list"):
        repo_audit.collect_named_items({"variables": "invalid"}, "variables")
    with pytest.raises(RuntimeError, match="non-object entry"):
        repo_audit.collect_named_items({"variables": ["bad", {"name": "APP_ID"}]}, "variables")
    with pytest.raises(RuntimeError, match="without a name"):
        repo_audit.collect_named_items({"variables": [{"name": 9}]}, "variables")


def test_collect_named_items_returns_non_empty_names() -> None:
    """Valid Actions list entries are collected without coercion."""
    assert repo_audit.collect_named_items(
        {"variables": [{"name": "APP_ID"}, {"name": "AUDIT_APP_ID"}]}, "variables"
    ) == {"APP_ID", "AUDIT_APP_ID"}


def test_extract_required_checks_handles_contexts_and_checks() -> None:
    """Extract required checks handles contexts and checks."""
    assert repo_audit.extract_required_checks(
        {
            "required_status_checks": {
                "contexts": ["verify", "secret-scan"],
                "checks": [{"context": "dependency-review"}, {"context": 9}],
            }
        }
    ) == {"verify", "secret-scan", "dependency-review"}


def test_extract_required_checks_handles_missing_data() -> None:
    """Extract required checks handles missing data."""
    assert repo_audit.extract_required_checks(None) == set()
    assert repo_audit.extract_required_checks({}) == set()


def test_extract_required_checks_rejects_malformed_status_checks() -> None:
    """Malformed required checks fail closed instead of looking like no checks."""
    with pytest.raises(RuntimeError, match="required status checks must be a JSON object"):
        repo_audit.extract_required_checks({"required_status_checks": []})
    with pytest.raises(RuntimeError, match="contexts must be a JSON array"):
        repo_audit.extract_required_checks({"required_status_checks": {"contexts": {}}})
    with pytest.raises(RuntimeError, match="checks must be a JSON array"):
        repo_audit.extract_required_checks({"required_status_checks": {"checks": {}}})


def test_ruleset_targets_branch_detects_exact_refs() -> None:
    """Ruleset targets branch detects exact refs."""
    assert repo_audit.ruleset_targets_branch(
        {
            "target": "branch",
            "conditions": {"ref_name": {"include": ["main", "refs/heads/gh-pages"]}},
        },
        "gh-pages",
    )


def test_ruleset_targets_branch_rejects_non_matching_rulesets() -> None:
    """Ruleset targets branch rejects non matching rulesets."""
    assert (
        repo_audit.ruleset_targets_branch(
            {
                "target": "tag",
                "conditions": {"ref_name": {"include": ["refs/heads/gh-pages"]}},
            },
            "gh-pages",
        )
        is False
    )
    assert repo_audit.ruleset_targets_branch({}, "gh-pages") is False


def test_ruleset_targets_branch_rejects_malformed_conditions() -> None:
    """Ruleset targets branch rejects malformed conditions."""
    assert (
        repo_audit.ruleset_targets_branch({"target": "branch", "conditions": []}, "gh-pages")
        is False
    )
    assert (
        repo_audit.ruleset_targets_branch(
            {"target": "branch", "conditions": {"ref_name": []}}, "gh-pages"
        )
        is False
    )
    assert (
        repo_audit.ruleset_targets_branch(
            {
                "target": "branch",
                "conditions": {"ref_name": {"include": "refs/heads/gh-pages"}},
            },
            "gh-pages",
        )
        is False
    )


def test_extract_ruleset_rule_types_handles_missing_and_malformed_data() -> None:
    """Extract ruleset rule types handles missing and malformed data."""
    assert repo_audit.extract_ruleset_rule_types(None) == set()
    assert repo_audit.extract_ruleset_rule_types({}) == set()
    assert repo_audit.extract_ruleset_rule_types({"rules": ["bad", {"type": 9}]}) == set()


def test_extract_ruleset_rule_types_collects_rule_names() -> None:
    """Extract ruleset rule types collects rule names."""
    assert repo_audit.extract_ruleset_rule_types(
        {
            "rules": [
                {"type": "update"},
                {"type": "required_signatures"},
                {"type": "required_linear_history"},
            ]
        }
    ) == {"required_linear_history", "required_signatures", "update"}


def test_ruleset_id_handles_missing_and_string_values() -> None:
    """Ruleset id handles missing and string values."""
    assert repo_audit.ruleset_id(None) is None
    assert repo_audit.ruleset_id({}) is None
    assert repo_audit.ruleset_id({"id": 42}) == 42
    assert repo_audit.ruleset_id({"id": "43"}) == 43
    assert repo_audit.ruleset_id({"id": "gh-pages"}) is None


def test_load_ruleset_detail_uses_summary_when_conditions_exist(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Load ruleset detail uses summary when conditions exist."""
    calls: list[str] = []

    def fail_if_called(
        endpoint: str, _description: str, _required_permission: str | None = None
    ) -> object:
        calls.append(endpoint)
        raise AssertionError("ruleset detail fetch should not be used")

    monkeypatch.setattr(workflow_helpers, "_run_gh_api_json", fail_if_called)

    summary = {
        "id": 42,
        "target": "branch",
        "conditions": {"ref_name": {"include": ["refs/heads/gh-pages"]}},
    }
    assert workflow_helpers._load_ruleset_detail("owner/repo", summary) is summary
    assert calls == []


def test_load_ruleset_detail_fetches_detail_for_summary_only_ruleset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Load ruleset detail fetches detail for summary only ruleset."""
    monkeypatch.setattr(
        workflow_helpers,
        "_run_gh_api_json",
        lambda *_args, **_kwargs: {
            "id": 99,
            "target": "branch",
            "conditions": {"ref_name": {"include": ["refs/heads/gh-pages"]}},
            "rules": [{"type": "update"}],
        },
    )

    assert workflow_helpers._load_ruleset_detail("owner/repo", {"id": 99, "target": "branch"}) == {
        "id": 99,
        "target": "branch",
        "conditions": {"ref_name": {"include": ["refs/heads/gh-pages"]}},
        "rules": [{"type": "update"}],
    }


def test_load_ruleset_detail_returns_input_when_ruleset_has_no_numeric_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Load ruleset detail returns input when ruleset has no numeric id."""
    calls: list[str] = []

    def fail_if_called(
        endpoint: str, _description: str, _required_permission: str | None = None
    ) -> object:
        calls.append(endpoint)
        raise AssertionError("ruleset detail fetch should not be used")

    monkeypatch.setattr(workflow_helpers, "_run_gh_api_json", fail_if_called)

    ruleset = {"id": "gh-pages-ruleset", "target": "branch"}
    assert workflow_helpers._load_ruleset_detail("owner/repo", ruleset) is ruleset
    assert calls == []


def test_load_ruleset_detail_rejects_non_object_rulesets() -> None:
    """Ruleset summaries must be objects before their fields are inspected."""
    with pytest.raises(RuntimeError, match="non-object entry"):
        repo_audit.load_ruleset_detail("owner/repo", [])


def _minimal_audit_responses() -> dict[str, object]:
    """Return typed API responses that reach the settings checks under test."""
    return {
        "repos/owner/repo": {"default_branch": "main"},
        "repos/owner/repo/pages": {"build_type": "workflow", "https_enforced": True},
        "repos/owner/repo/branches/main/protection": {},
        "repos/owner/repo/actions/variables": {"variables": []},
        "repos/owner/repo/actions/secrets": {"secrets": []},
        "repos/owner/repo/rulesets": [],
    }


def _patch_audit_responses(monkeypatch: pytest.MonkeyPatch, responses: dict[str, object]) -> None:
    """Route repository audit API calls to a local response map."""
    monkeypatch.setattr(
        workflow_helpers,
        "_run_gh_api_json",
        lambda endpoint, *_args, **_kwargs: responses[endpoint],
    )


def test_audit_repo_settings_rejects_malformed_core_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Malformed metadata, Pages, and HTTPS fields fail closed."""
    responses = _minimal_audit_responses()
    responses["repos/owner/repo"] = {"default_branch": 9}
    _patch_audit_responses(monkeypatch, responses)
    with pytest.raises(RuntimeError, match="default_branch"):
        workflow_helpers.audit_repo_settings(repo="owner/repo")

    responses = _minimal_audit_responses()
    responses["repos/owner/repo/pages"] = {"build_type": None, "https_enforced": True}
    _patch_audit_responses(monkeypatch, responses)
    with pytest.raises(RuntimeError, match="build_type"):
        workflow_helpers.audit_repo_settings(repo="owner/repo")

    responses = _minimal_audit_responses()
    responses["repos/owner/repo/pages"] = {"build_type": "workflow", "https_enforced": "yes"}
    _patch_audit_responses(monkeypatch, responses)
    with pytest.raises(RuntimeError, match="https_enforced"):
        workflow_helpers.audit_repo_settings(repo="owner/repo")

    responses = _minimal_audit_responses()
    responses["repos/owner/repo/pages"] = {
        "build_type": "workflow",
        "https_enforced": True,
        "source": {"branch": 9},
    }
    _patch_audit_responses(monkeypatch, responses)
    with pytest.raises(RuntimeError, match="source branch"):
        workflow_helpers.audit_repo_settings(repo="owner/repo")

    responses = _minimal_audit_responses()
    responses["repos/owner/repo/pages"] = {
        "build_type": "workflow",
        "https_enforced": True,
        "source": {"path": {}},
    }
    _patch_audit_responses(monkeypatch, responses)
    with pytest.raises(RuntimeError, match="source path"):
        workflow_helpers.audit_repo_settings(repo="owner/repo")

    responses = _minimal_audit_responses()
    responses["repos/owner/repo/pages"] = {
        "build_type": "workflow",
        "https_enforced": True,
        "source": [],
    }
    _patch_audit_responses(monkeypatch, responses)
    with pytest.raises(RuntimeError, match="Pages source"):
        workflow_helpers.audit_repo_settings(repo="owner/repo")

    responses = _minimal_audit_responses()
    responses["repos/owner/repo/pages"] = {"build_type": "legacy", "https_enforced": True}
    _patch_audit_responses(monkeypatch, responses)
    with pytest.raises(RuntimeError, match="source branch"):
        workflow_helpers.audit_repo_settings(repo="owner/repo")

    responses = _minimal_audit_responses()
    responses["repos/owner/repo/pages"] = {
        "build_type": "legacy",
        "https_enforced": True,
        "source": {"branch": "gh-pages"},
    }
    _patch_audit_responses(monkeypatch, responses)
    with pytest.raises(RuntimeError, match="source path"):
        workflow_helpers.audit_repo_settings(repo="owner/repo")


@pytest.mark.parametrize(
    ("protection", "error", "message"),
    [
        ({}, ValueError, "does not require at least 1 approving review"),
        ({"required_pull_request_reviews": []}, RuntimeError, "review settings"),
        (
            {"required_pull_request_reviews": {"required_approving_review_count": "1"}},
            RuntimeError,
            "approval count",
        ),
    ],
    ids=["missing", "wrong-type", "wrong-count-type"],
)
def test_audit_repo_settings_validates_review_settings(
    monkeypatch: pytest.MonkeyPatch,
    protection: dict[str, object],
    error: type[Exception],
    message: str,
) -> None:
    """Review requirements must be present and typed before they are trusted."""
    responses = _minimal_audit_responses()
    responses["repos/owner/repo/branches/main/protection"] = protection
    _patch_audit_responses(monkeypatch, responses)

    with pytest.raises(error, match=message):
        workflow_helpers.audit_repo_settings(repo="owner/repo")


def test_audit_repo_settings_returns_expected_summary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Audit repo settings returns expected summary."""
    responses = {
        "repos/owner/repo": {
            "default_branch": "main",
            "security_and_analysis": {
                "secret_scanning": {"status": "enabled"},
                "secret_scanning_push_protection": {"status": "enabled"},
            },
        },
        "repos/owner/repo/pages": {
            "build_type": "workflow",
            "https_enforced": True,
        },
        "repos/owner/repo/branches/main/protection": {
            "required_status_checks": {"contexts": ["verify", "secret-scan", "dependency-review"]},
            "required_pull_request_reviews": {"required_approving_review_count": 1},
            "required_signatures": {"enabled": True},
            "required_linear_history": {"enabled": True},
            "required_conversation_resolution": {"enabled": True},
        },
        "repos/owner/repo/actions/variables": {
            "variables": [
                {"name": "APP_ID"},
                {"name": "ESCALATION_APP_ID"},
                {"name": "AUDIT_APP_ID"},
            ]
        },
        "repos/owner/repo/actions/secrets": {
            "secrets": [
                {"name": "APP_PRIVATE_KEY"},
                {"name": "ESCALATION_APP_PRIVATE_KEY"},
                {"name": "AUDIT_APP_PRIVATE_KEY"},
                {"name": "GITLEAKS_LICENSE"},
            ]
        },
        "repos/owner/repo/rulesets": [{"id": 14, "target": "branch"}],
        "repos/owner/repo/rulesets/14": {
            "id": 14,
            "target": "branch",
            "conditions": {"ref_name": {"include": ["refs/heads/gh-pages"]}},
            "rules": [
                {"type": "update"},
                {"type": "deletion"},
                {"type": "creation"},
                {"type": "non_fast_forward"},
                {"type": "required_linear_history"},
                {"type": "required_signatures"},
            ],
        },
    }

    monkeypatch.setattr(
        workflow_helpers,
        "_run_gh_api_json",
        lambda endpoint, *_args, **_kwargs: responses[endpoint],
    )

    assert workflow_helpers.audit_repo_settings(repo="owner/repo") == {
        "default-branch": "main",
        "gh-pages-rules": [
            "creation",
            "deletion",
            "non_fast_forward",
            "required_linear_history",
            "required_signatures",
            "update",
        ],
        "gh-pages-ruleset": True,
        "pages-branch": None,
        "pages-build-type": "workflow",
        "pages-https-enforced": True,
        "pages-path": "/",
        "required-checks": ["dependency-review", "secret-scan", "verify"],
        "security-features": ["secret_scanning", "secret_scanning_push_protection"],
    }


def test_enabled_security_features_reads_only_enabled_entries() -> None:
    """Anything short of an explicit enabled status is not treated as enabled."""
    repository = {
        "security_and_analysis": {
            "secret_scanning": {"status": "enabled"},
            "secret_scanning_push_protection": {"status": "disabled"},
            "secret_scanning_validity_checks": "enabled",
            # A non-string key cannot come back from GitHub's JSON, but the value
            # is typed as object, so the guard keeps the set[str] return honest.
            9: {"status": "enabled"},
        }
    }

    assert repo_audit.enabled_security_features(repository) == {"secret_scanning"}


def test_enabled_security_features_treats_a_missing_block_as_nothing_enabled() -> None:
    """The block is absent without administration access, which must read as drift.

    Reporting an unreadable setting as satisfied would let the audit certify
    push protection it never actually observed.
    """
    assert repo_audit.enabled_security_features({}) == set()
    assert repo_audit.enabled_security_features({"security_and_analysis": None}) == set()


def test_audit_repo_settings_flags_disabled_push_protection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Push protection off is drift, since it is the layer that blocks the push."""
    responses = {
        "repos/owner/repo": {
            "default_branch": "main",
            "security_and_analysis": {"secret_scanning": {"status": "enabled"}},
        },
        "repos/owner/repo/pages": {"build_type": "workflow", "https_enforced": True},
        "repos/owner/repo/branches/main/protection": {
            "required_status_checks": {"contexts": ["verify", "secret-scan", "dependency-review"]},
            "required_pull_request_reviews": {"required_approving_review_count": 1},
            "required_signatures": {"enabled": True},
            "required_linear_history": {"enabled": True},
            "required_conversation_resolution": {"enabled": True},
        },
        "repos/owner/repo/actions/variables": {
            "variables": [
                {"name": "APP_ID"},
                {"name": "ESCALATION_APP_ID"},
                {"name": "AUDIT_APP_ID"},
            ]
        },
        "repos/owner/repo/actions/secrets": {
            "secrets": [
                {"name": "APP_PRIVATE_KEY"},
                {"name": "ESCALATION_APP_PRIVATE_KEY"},
                {"name": "AUDIT_APP_PRIVATE_KEY"},
                {"name": "GITLEAKS_LICENSE"},
            ]
        },
        "repos/owner/repo/rulesets": [],
    }

    monkeypatch.setattr(
        workflow_helpers,
        "_run_gh_api_json",
        lambda endpoint, *_args, **_kwargs: responses[endpoint],
    )

    with pytest.raises(ValueError, match="secret_scanning_push_protection") as excinfo:
        workflow_helpers.audit_repo_settings(repo="owner/repo")

    assert "security and analysis features" in str(excinfo.value)


def test_audit_repo_settings_rejects_unexpected_response_types(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Audit repo settings rejects unexpected response types."""
    responses = {
        "repos/owner/repo": [],
        "repos/owner/repo/pages": {
            "build_type": "workflow",
            "https_enforced": True,
            "source": {"branch": "gh-pages", "path": "/"},
        },
        "repos/owner/repo/branches/main/protection": {},
        "repos/owner/repo/actions/variables": {"variables": []},
        "repos/owner/repo/actions/secrets": {"secrets": []},
        "repos/owner/repo/rulesets": [],
    }
    monkeypatch.setattr(
        workflow_helpers,
        "_run_gh_api_json",
        lambda endpoint, *_args, **_kwargs: responses[endpoint],
    )

    with pytest.raises(RuntimeError, match="Repository metadata must be a JSON object"):
        workflow_helpers.audit_repo_settings(repo="owner/repo")


def test_audit_repo_settings_rejects_invalid_pages_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Audit repo settings rejects invalid pages response."""
    responses = {
        "repos/owner/repo": {"default_branch": "main"},
        "repos/owner/repo/pages": [],
        "repos/owner/repo/branches/main/protection": {},
        "repos/owner/repo/actions/variables": {"variables": []},
        "repos/owner/repo/actions/secrets": {"secrets": []},
        "repos/owner/repo/rulesets": [],
    }
    monkeypatch.setattr(
        workflow_helpers,
        "_run_gh_api_json",
        lambda endpoint, *_args, **_kwargs: responses[endpoint],
    )

    with pytest.raises(RuntimeError, match="Pages settings must be a JSON object"):
        workflow_helpers.audit_repo_settings(repo="owner/repo")


def test_audit_repo_settings_rejects_invalid_protection_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Audit repo settings rejects invalid protection response."""
    responses = {
        "repos/owner/repo": {"default_branch": "main"},
        "repos/owner/repo/pages": {
            "build_type": "workflow",
            "https_enforced": True,
            "source": {"branch": "gh-pages", "path": "/"},
        },
        "repos/owner/repo/branches/main/protection": [],
        "repos/owner/repo/actions/variables": {"variables": []},
        "repos/owner/repo/actions/secrets": {"secrets": []},
        "repos/owner/repo/rulesets": [],
    }
    monkeypatch.setattr(
        workflow_helpers,
        "_run_gh_api_json",
        lambda endpoint, *_args, **_kwargs: responses[endpoint],
    )

    with pytest.raises(RuntimeError, match="Branch protection settings must be a JSON object"):
        workflow_helpers.audit_repo_settings(repo="owner/repo")


def test_audit_repo_settings_rejects_invalid_variables_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Audit repo settings rejects invalid variables response."""
    responses = {
        "repos/owner/repo": {"default_branch": "main"},
        "repos/owner/repo/pages": {
            "build_type": "workflow",
            "https_enforced": True,
            "source": {"branch": "gh-pages", "path": "/"},
        },
        "repos/owner/repo/branches/main/protection": {},
        "repos/owner/repo/actions/variables": [],
        "repos/owner/repo/actions/secrets": {"secrets": []},
        "repos/owner/repo/rulesets": [],
    }
    monkeypatch.setattr(
        workflow_helpers,
        "_run_gh_api_json",
        lambda endpoint, *_args, **_kwargs: responses[endpoint],
    )

    with pytest.raises(RuntimeError, match="Actions variables response must be a JSON object"):
        workflow_helpers.audit_repo_settings(repo="owner/repo")


def test_audit_repo_settings_rejects_invalid_secrets_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Audit repo settings rejects invalid secrets response."""
    responses = {
        "repos/owner/repo": {"default_branch": "main"},
        "repos/owner/repo/pages": {
            "build_type": "workflow",
            "https_enforced": True,
            "source": {"branch": "gh-pages", "path": "/"},
        },
        "repos/owner/repo/branches/main/protection": {},
        "repos/owner/repo/actions/variables": {"variables": []},
        "repos/owner/repo/actions/secrets": [],
        "repos/owner/repo/rulesets": [],
    }
    monkeypatch.setattr(
        workflow_helpers,
        "_run_gh_api_json",
        lambda endpoint, *_args, **_kwargs: responses[endpoint],
    )

    with pytest.raises(RuntimeError, match="Actions secrets response must be a JSON object"):
        workflow_helpers.audit_repo_settings(repo="owner/repo")


def test_audit_repo_settings_rejects_invalid_rulesets_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Audit repo settings rejects invalid rulesets response."""
    responses = {
        "repos/owner/repo": {"default_branch": "main"},
        "repos/owner/repo/pages": {
            "build_type": "workflow",
            "https_enforced": True,
            "source": {"branch": "gh-pages", "path": "/"},
        },
        "repos/owner/repo/branches/main/protection": {},
        "repos/owner/repo/actions/variables": {"variables": []},
        "repos/owner/repo/actions/secrets": {"secrets": []},
        "repos/owner/repo/rulesets": {},
    }
    monkeypatch.setattr(
        workflow_helpers,
        "_run_gh_api_json",
        lambda endpoint, *_args, **_kwargs: responses[endpoint],
    )

    with pytest.raises(RuntimeError, match="Rulesets response must be a JSON array"):
        workflow_helpers.audit_repo_settings(repo="owner/repo")


def test_audit_repo_settings_reports_configuration_drift(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Audit repo settings reports configuration drift."""
    responses = {
        "repos/owner/repo": {"default_branch": "trunk"},
        "repos/owner/repo/pages": {
            "build_type": "legacy",
            "https_enforced": False,
            "source": {"branch": "docs", "path": "/site"},
        },
        "repos/owner/repo/branches/main/protection": {
            "required_status_checks": {"contexts": ["verify"]},
            "required_pull_request_reviews": {"required_approving_review_count": 0},
            "required_signatures": {"enabled": False},
            "required_linear_history": {"enabled": False},
            "required_conversation_resolution": {"enabled": False},
        },
        "repos/owner/repo/actions/variables": {"variables": [{"name": "APP_ID"}]},
        "repos/owner/repo/actions/secrets": {"secrets": []},
        "repos/owner/repo/rulesets": [{"id": 7, "target": "branch"}],
        "repos/owner/repo/rulesets/7": {
            "id": 7,
            "target": "branch",
            "conditions": {"ref_name": {"include": ["refs/heads/gh-pages"]}},
            "rules": [{"type": "update"}],
        },
    }
    monkeypatch.setattr(
        workflow_helpers,
        "_run_gh_api_json",
        lambda endpoint, *_args, **_kwargs: responses[endpoint],
    )

    with pytest.raises(ValueError, match="Repository settings audit failed") as exc_info:
        workflow_helpers.audit_repo_settings(repo="owner/repo")

    message = str(exc_info.value)
    assert "default branch is 'trunk' instead of 'main'" in message
    assert "Pages source branch is 'docs' instead of 'gh-pages'" in message
    assert "Pages source path is '/site' instead of '/'" in message
    assert "Pages build type is 'legacy' instead of 'workflow'" in message
    assert "Pages HTTPS is not enforced" in message
    assert "missing repository variables: AUDIT_APP_ID, ESCALATION_APP_ID" in message
    assert (
        "missing repository secrets: APP_PRIVATE_KEY, "
        "AUDIT_APP_PRIVATE_KEY, ESCALATION_APP_PRIVATE_KEY, GITLEAKS_LICENSE" in message
    )
    assert (
        "'gh-pages' ruleset is missing rules: creation, deletion, non_fast_forward, "
        "required_linear_history, required_signatures" in message
    )


def test_audit_repo_settings_reports_only_build_type_for_compliant_legacy_source(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Audit repo settings reports only build type for compliant legacy source."""
    responses = {
        "repos/owner/repo": {"default_branch": "main"},
        "repos/owner/repo/pages": {
            "build_type": "legacy",
            "https_enforced": True,
            "source": {"branch": "gh-pages", "path": "/"},
        },
        "repos/owner/repo/branches/main/protection": {
            "required_status_checks": {"contexts": ["verify", "secret-scan", "dependency-review"]},
            "required_pull_request_reviews": {"required_approving_review_count": 1},
            "required_signatures": {"enabled": True},
            "required_linear_history": {"enabled": True},
            "required_conversation_resolution": {"enabled": True},
        },
        "repos/owner/repo/actions/variables": {
            "variables": [
                {"name": "APP_ID"},
                {"name": "ESCALATION_APP_ID"},
                {"name": "AUDIT_APP_ID"},
            ]
        },
        "repos/owner/repo/actions/secrets": {
            "secrets": [
                {"name": "APP_PRIVATE_KEY"},
                {"name": "ESCALATION_APP_PRIVATE_KEY"},
                {"name": "AUDIT_APP_PRIVATE_KEY"},
                {"name": "GITLEAKS_LICENSE"},
            ]
        },
        "repos/owner/repo/rulesets": [{"id": 14, "target": "branch"}],
        "repos/owner/repo/rulesets/14": {
            "id": 14,
            "target": "branch",
            "conditions": {"ref_name": {"include": ["refs/heads/gh-pages"]}},
            "rules": [
                {"type": "update"},
                {"type": "deletion"},
                {"type": "creation"},
                {"type": "non_fast_forward"},
                {"type": "required_linear_history"},
                {"type": "required_signatures"},
            ],
        },
    }

    monkeypatch.setattr(
        workflow_helpers,
        "_run_gh_api_json",
        lambda endpoint, *_args, **_kwargs: responses[endpoint],
    )

    with pytest.raises(ValueError, match="Repository settings audit failed") as exc_info:
        workflow_helpers.audit_repo_settings(repo="owner/repo")

    message = str(exc_info.value)
    assert "Pages build type is 'legacy' instead of 'workflow'" in message
    assert "Pages source branch" not in message
    assert "Pages source path" not in message


def test_audit_repo_settings_requires_ruleset_targeting_pages_branch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Audit repo settings requires ruleset targeting pages branch."""
    responses = {
        "repos/owner/repo": {"default_branch": "main"},
        "repos/owner/repo/pages": {
            "build_type": "workflow",
            "https_enforced": True,
            "source": {"branch": "gh-pages", "path": "/"},
        },
        "repos/owner/repo/branches/main/protection": {
            "required_status_checks": {"contexts": ["verify", "secret-scan", "dependency-review"]},
            "required_pull_request_reviews": {"required_approving_review_count": 1},
            "required_signatures": {"enabled": True},
            "required_linear_history": {"enabled": True},
            "required_conversation_resolution": {"enabled": True},
        },
        "repos/owner/repo/actions/variables": {
            "variables": [
                {"name": "APP_ID"},
                {"name": "ESCALATION_APP_ID"},
                {"name": "AUDIT_APP_ID"},
            ]
        },
        "repos/owner/repo/actions/secrets": {
            "secrets": [
                {"name": "APP_PRIVATE_KEY"},
                {"name": "ESCALATION_APP_PRIVATE_KEY"},
                {"name": "AUDIT_APP_PRIVATE_KEY"},
                {"name": "GITLEAKS_LICENSE"},
            ]
        },
        "repos/owner/repo/rulesets": [{"id": 99, "target": "branch"}],
        "repos/owner/repo/rulesets/99": {
            "id": 99,
            "target": "branch",
            "conditions": {"ref_name": {"include": ["refs/heads/docs"]}},
            "rules": [
                {"type": "update"},
                {"type": "deletion"},
                {"type": "creation"},
                {"type": "non_fast_forward"},
                {"type": "required_linear_history"},
                {"type": "required_signatures"},
            ],
        },
    }

    monkeypatch.setattr(
        workflow_helpers,
        "_run_gh_api_json",
        lambda endpoint, *_args, **_kwargs: responses[endpoint],
    )

    with pytest.raises(ValueError, match="no branch ruleset explicitly targets 'gh-pages'"):
        workflow_helpers.audit_repo_settings(repo="owner/repo")


def test_main_audit_repo_settings_prints_json(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Main audit repo settings prints json."""
    monkeypatch.setattr(
        workflow_helpers,
        "audit_repo_settings",
        lambda repo, default_branch, pages_branch: {
            "default-branch": default_branch,
            "pages-branch": pages_branch,
            "repo": repo,
        },
    )

    exit_code = workflow_helpers.main(
        [
            "audit-repo-settings",
            "--repo",
            "owner/repo",
            "--default-branch",
            "main",
            "--pages-branch",
            "gh-pages",
        ]
    )

    assert exit_code == 0
    assert json.loads(capsys.readouterr().out) == {
        "default-branch": "main",
        "pages-branch": "gh-pages",
        "repo": "owner/repo",
    }


def test_report_checked_is_a_noop_without_github_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Local command use does not require a GitHub Actions output file."""
    monkeypatch.delenv("GITHUB_OUTPUT", raising=False)

    workflow_helpers._report_checked("checked", True)


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (None, "settings_checked=true"),
        (ValueError("drift"), "settings_checked=true"),
        (RuntimeError("unreadable"), "settings_checked=false"),
    ],
    ids=["healthy", "drift", "setup-failure"],
)
def test_audit_handler_records_whether_settings_were_checked(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
    error: Exception | None,
    expected: str,
) -> None:
    """The workflow can distinguish settings drift from an unreadable audit response."""
    output = tmp_path / "github-output"
    monkeypatch.setenv("GITHUB_OUTPUT", str(output))

    def fake_audit(**_kwargs: object) -> dict[str, object]:
        if error is not None:
            raise error
        return {"ok": True}

    monkeypatch.setattr(workflow_helpers, "audit_repo_settings", fake_audit)
    args = ["audit-repo-settings", "--repo", "owner/repo"]

    if error is None:
        assert workflow_helpers.main(args) == 0
    else:
        with pytest.raises(type(error), match=str(error)):
            workflow_helpers.main(args)

    assert output.read_text(encoding="utf-8") == f"{expected}\n"


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (None, "previews_checked=true"),
        (ValueError("drift"), "previews_checked=true"),
        (RuntimeError("unreadable"), "previews_checked=false"),
    ],
    ids=["healthy", "drift", "setup-failure"],
)
def test_preview_handler_records_whether_previews_were_checked(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
    capsys: pytest.CaptureFixture[str],
    error: Exception | None,
    expected: str,
) -> None:
    """Preview audit failures distinguish drift from an unreadable response."""
    output = tmp_path / "github-output"
    monkeypatch.setenv("GITHUB_OUTPUT", str(output))

    def fake_audit(**_kwargs: object) -> list[str]:
        if error is not None:
            raise error
        return ["pr-preview/pr-12"]

    monkeypatch.setattr(workflow_helpers, "audit_previews", fake_audit)
    args = ["audit-previews", "--repo", "owner/repo"]

    if error is None:
        assert workflow_helpers.main(args) == 0
        assert json.loads(capsys.readouterr().out) == {"open-previews": ["pr-preview/pr-12"]}
    else:
        with pytest.raises(type(error), match=str(error)):
            workflow_helpers.main(args)

    assert output.read_text(encoding="utf-8") == f"{expected}\n"
