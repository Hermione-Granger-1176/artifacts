from __future__ import annotations

import json

import pytest

import scripts.ci.workflow_helpers as workflow_helpers


def test_collect_named_items_skips_non_lists_and_non_dict_entries() -> None:
    assert (
        workflow_helpers._collect_named_items({"variables": "invalid"}, "variables")
        == set()
    )
    assert workflow_helpers._collect_named_items(
        {"variables": ["bad", {"name": "APP_ID"}, {"name": 9}]}, "variables"
    ) == {"APP_ID"}


def test_extract_required_checks_handles_contexts_and_checks() -> None:
    assert workflow_helpers._extract_required_checks(
        {
            "required_status_checks": {
                "contexts": ["verify", "secret-scan"],
                "checks": [{"context": "dependency-review"}, {"context": 9}],
            }
        }
    ) == {"verify", "secret-scan", "dependency-review"}


def test_extract_required_checks_handles_missing_data() -> None:
    assert workflow_helpers._extract_required_checks(None) == set()
    assert workflow_helpers._extract_required_checks({}) == set()


def test_ruleset_targets_branch_detects_exact_refs() -> None:
    assert workflow_helpers._ruleset_targets_branch(
        {
            "target": "branch",
            "conditions": {"ref_name": {"include": ["main", "refs/heads/gh-pages"]}},
        },
        "gh-pages",
    )


def test_ruleset_targets_branch_rejects_non_matching_rulesets() -> None:
    assert (
        workflow_helpers._ruleset_targets_branch(
            {
                "target": "tag",
                "conditions": {"ref_name": {"include": ["refs/heads/gh-pages"]}},
            },
            "gh-pages",
        )
        is False
    )
    assert workflow_helpers._ruleset_targets_branch({}, "gh-pages") is False


def test_ruleset_targets_branch_rejects_malformed_conditions() -> None:
    assert (
        workflow_helpers._ruleset_targets_branch(
            {"target": "branch", "conditions": []}, "gh-pages"
        )
        is False
    )
    assert (
        workflow_helpers._ruleset_targets_branch(
            {"target": "branch", "conditions": {"ref_name": []}}, "gh-pages"
        )
        is False
    )
    assert (
        workflow_helpers._ruleset_targets_branch(
            {
                "target": "branch",
                "conditions": {"ref_name": {"include": "refs/heads/gh-pages"}},
            },
            "gh-pages",
        )
        is False
    )


def test_extract_ruleset_rule_types_handles_missing_and_malformed_data() -> None:
    assert workflow_helpers._extract_ruleset_rule_types(None) == set()
    assert workflow_helpers._extract_ruleset_rule_types({}) == set()
    assert (
        workflow_helpers._extract_ruleset_rule_types({"rules": ["bad", {"type": 9}]})
        == set()
    )


def test_extract_ruleset_rule_types_collects_rule_names() -> None:
    assert workflow_helpers._extract_ruleset_rule_types(
        {
            "rules": [
                {"type": "update"},
                {"type": "required_signatures"},
                {"type": "required_linear_history"},
            ]
        }
    ) == {"required_linear_history", "required_signatures", "update"}


def test_ruleset_id_handles_missing_and_string_values() -> None:
    assert workflow_helpers._ruleset_id(None) is None
    assert workflow_helpers._ruleset_id({}) is None
    assert workflow_helpers._ruleset_id({"id": 42}) == 42
    assert workflow_helpers._ruleset_id({"id": "43"}) == 43
    assert workflow_helpers._ruleset_id({"id": "gh-pages"}) is None


def test_load_ruleset_detail_uses_summary_when_conditions_exist(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    def fail_if_called(endpoint: str, description: str) -> object:
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
    monkeypatch.setattr(
        workflow_helpers,
        "_run_gh_api_json",
        lambda endpoint, description: {
            "id": 99,
            "target": "branch",
            "conditions": {"ref_name": {"include": ["refs/heads/gh-pages"]}},
            "rules": [{"type": "update"}],
        },
    )

    assert workflow_helpers._load_ruleset_detail(
        "owner/repo", {"id": 99, "target": "branch"}
    ) == {
        "id": 99,
        "target": "branch",
        "conditions": {"ref_name": {"include": ["refs/heads/gh-pages"]}},
        "rules": [{"type": "update"}],
    }


def test_load_ruleset_detail_returns_input_when_ruleset_has_no_numeric_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    def fail_if_called(endpoint: str, description: str) -> object:
        calls.append(endpoint)
        raise AssertionError("ruleset detail fetch should not be used")

    monkeypatch.setattr(workflow_helpers, "_run_gh_api_json", fail_if_called)

    ruleset = {"id": "gh-pages-ruleset", "target": "branch"}
    assert workflow_helpers._load_ruleset_detail("owner/repo", ruleset) is ruleset
    assert calls == []


def test_audit_repo_settings_returns_expected_summary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    responses = {
        "repos/owner/repo": {"default_branch": "main"},
        "repos/owner/repo/pages": {
            "build_type": "legacy",
            "https_enforced": True,
            "source": {"branch": "gh-pages", "path": "/"},
        },
        "repos/owner/repo/branches/main/protection": {
            "required_status_checks": {
                "contexts": ["verify", "secret-scan", "dependency-review"]
            },
            "required_pull_request_reviews": {"required_approving_review_count": 1},
            "required_signatures": {"enabled": True},
            "required_linear_history": {"enabled": True},
            "required_conversation_resolution": {"enabled": True},
        },
        "repos/owner/repo/actions/variables": {
            "variables": [
                {"name": "APP_ID"},
                {"name": "ESCALATION_APP_ID"},
            ]
        },
        "repos/owner/repo/actions/secrets": {
            "secrets": [
                {"name": "APP_PRIVATE_KEY"},
                {"name": "ESCALATION_APP_PRIVATE_KEY"},
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
        lambda endpoint, description: responses[endpoint],
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
        "pages-branch": "gh-pages",
        "pages-build-type": "legacy",
        "pages-https-enforced": True,
        "pages-path": "/",
        "required-checks": ["dependency-review", "secret-scan", "verify"],
    }


def test_audit_repo_settings_rejects_unexpected_response_types(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    responses = {
        "repos/owner/repo": [],
        "repos/owner/repo/pages": {
            "build_type": "legacy",
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
        lambda endpoint, description: responses[endpoint],
    )

    with pytest.raises(RuntimeError, match="Repository metadata must be a JSON object"):
        workflow_helpers.audit_repo_settings(repo="owner/repo")


def test_audit_repo_settings_rejects_invalid_pages_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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
        lambda endpoint, description: responses[endpoint],
    )

    with pytest.raises(RuntimeError, match="Pages settings must be a JSON object"):
        workflow_helpers.audit_repo_settings(repo="owner/repo")


def test_audit_repo_settings_rejects_invalid_protection_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    responses = {
        "repos/owner/repo": {"default_branch": "main"},
        "repos/owner/repo/pages": {
            "build_type": "legacy",
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
        lambda endpoint, description: responses[endpoint],
    )

    with pytest.raises(
        RuntimeError, match="Branch protection settings must be a JSON object"
    ):
        workflow_helpers.audit_repo_settings(repo="owner/repo")


def test_audit_repo_settings_rejects_invalid_variables_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    responses = {
        "repos/owner/repo": {"default_branch": "main"},
        "repos/owner/repo/pages": {
            "build_type": "legacy",
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
        lambda endpoint, description: responses[endpoint],
    )

    with pytest.raises(
        RuntimeError, match="Actions variables response must be a JSON object"
    ):
        workflow_helpers.audit_repo_settings(repo="owner/repo")


def test_audit_repo_settings_rejects_invalid_secrets_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    responses = {
        "repos/owner/repo": {"default_branch": "main"},
        "repos/owner/repo/pages": {
            "build_type": "legacy",
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
        lambda endpoint, description: responses[endpoint],
    )

    with pytest.raises(
        RuntimeError, match="Actions secrets response must be a JSON object"
    ):
        workflow_helpers.audit_repo_settings(repo="owner/repo")


def test_audit_repo_settings_rejects_invalid_rulesets_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    responses = {
        "repos/owner/repo": {"default_branch": "main"},
        "repos/owner/repo/pages": {
            "build_type": "legacy",
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
        lambda endpoint, description: responses[endpoint],
    )

    with pytest.raises(RuntimeError, match="Rulesets response must be a JSON array"):
        workflow_helpers.audit_repo_settings(repo="owner/repo")


def test_audit_repo_settings_reports_configuration_drift(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    responses = {
        "repos/owner/repo": {"default_branch": "trunk"},
        "repos/owner/repo/pages": {
            "build_type": "workflow",
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
        lambda endpoint, description: responses[endpoint],
    )

    with pytest.raises(
        ValueError, match="Repository settings audit failed"
    ) as exc_info:
        workflow_helpers.audit_repo_settings(repo="owner/repo")

    message = str(exc_info.value)
    assert "default branch is 'trunk' instead of 'main'" in message
    assert "Pages source branch is 'docs' instead of 'gh-pages'" in message
    assert "Pages source path is '/site' instead of '/'" in message
    assert "Pages build type is 'workflow' instead of 'legacy'" in message
    assert "Pages HTTPS is not enforced" in message
    assert "missing repository variables: ESCALATION_APP_ID" in message
    assert (
        "missing repository secrets: APP_PRIVATE_KEY, ESCALATION_APP_PRIVATE_KEY"
        in message
    )
    assert (
        "'gh-pages' ruleset is missing rules: creation, deletion, non_fast_forward, "
        "required_linear_history, required_signatures" in message
    )


def test_audit_repo_settings_requires_ruleset_targeting_pages_branch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    responses = {
        "repos/owner/repo": {"default_branch": "main"},
        "repos/owner/repo/pages": {
            "build_type": "legacy",
            "https_enforced": True,
            "source": {"branch": "gh-pages", "path": "/"},
        },
        "repos/owner/repo/branches/main/protection": {
            "required_status_checks": {
                "contexts": ["verify", "secret-scan", "dependency-review"]
            },
            "required_pull_request_reviews": {"required_approving_review_count": 1},
            "required_signatures": {"enabled": True},
            "required_linear_history": {"enabled": True},
            "required_conversation_resolution": {"enabled": True},
        },
        "repos/owner/repo/actions/variables": {
            "variables": [
                {"name": "APP_ID"},
                {"name": "ESCALATION_APP_ID"},
            ]
        },
        "repos/owner/repo/actions/secrets": {
            "secrets": [
                {"name": "APP_PRIVATE_KEY"},
                {"name": "ESCALATION_APP_PRIVATE_KEY"},
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
        lambda endpoint, description: responses[endpoint],
    )

    with pytest.raises(
        ValueError, match="no branch ruleset explicitly targets 'gh-pages'"
    ):
        workflow_helpers.audit_repo_settings(repo="owner/repo")


def test_main_audit_repo_settings_prints_json(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
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
