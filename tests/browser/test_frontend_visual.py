"""Tolerant visual-regression baseline check for the hero states.

Captures a fixed-viewport screenshot of the root gallery and each mature app's
hero (above-the-fold) state and compares it against a committed baseline with a
generous tolerance (see ``scripts/ci/visual_regression.py``). Set
``ARTIFACTS_UPDATE_VISUAL_BASELINES=1`` (via ``make visual-baselines``) to
rewrite the baselines after an intentional visual change.

Baselines are environment sensitive (system font rendering differs between
hosts), so this suite is a local and on-demand tool. It is intentionally not
part of the blocking CI browser gate; regenerate the baselines in the same
environment where the check runs.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from scripts.ci import visual_regression
from tests.browser.frontend_helpers import REPO_ROOT, MonitoredPage, discover_app_slugs

if TYPE_CHECKING:
    from tests.browser.conftest import AppBrowserHarness

BASELINE_DIR = REPO_ROOT / "tests" / "browser" / "baselines"
UPDATE_ENV = "ARTIFACTS_UPDATE_VISUAL_BASELINES"
VIEWPORT = (1200, 800)

# The root gallery renders an animated 3D book scene whose anti-aliased frames
# vary a few percent even after animations are frozen, so it gets a looser
# total-diff tolerance than the static app heroes. Both still catch gross
# regressions (layout collapse, missing hero, inverted colors).
MAX_DIFF_FRACTION = {"root": 0.18}
DEFAULT_MAX_DIFF_FRACTION = 0.05

# "root" plus every app slug: the five hero states under baseline control.
VISUAL_TARGETS = ["root", *discover_app_slugs()]


def _target_path(target: str) -> str:
    return "/" if target == "root" else f"/apps/{target}/"


def _capture_hero(app_browser: AppBrowserHarness, target: str) -> bytes:
    """Return a fixed-viewport screenshot of one hero state."""
    with MonitoredPage(
        app_browser.playwright,
        app_browser.server_url,
        name=f"visual-{target}",
        viewport=VIEWPORT,
        reduced_motion="reduce",
        bypass_csp=True,
        browser=app_browser.browser,
    ) as session:
        page = session.page
        assert page is not None
        session.goto(_target_path(target))
        if target == "root":
            page.wait_for_selector(".artifact-card")
        else:
            page.wait_for_function("window.__ARTIFACT_READY__ === true")
        # Settle web fonts, then freeze animation so the capture is deterministic:
        # kill CSS animations/transitions and fast-forward Web Animations (the
        # gallery book scene) to a stable resting frame.
        page.evaluate("async () => { await document.fonts.ready; }")
        page.add_style_tag(
            content=(
                "*, *::before, *::after { animation-duration: 0s !important; "
                "animation-delay: 0s !important; transition: none !important; "
                "caret-color: transparent !important; }"
            )
        )
        page.evaluate(
            "() => { document.getAnimations().forEach((animation) => { "
            "try { animation.finish(); } catch (error) { animation.pause(); } }); }"
        )
        page.wait_for_timeout(200)
        return page.screenshot(full_page=False)


@pytest.mark.parametrize("target", VISUAL_TARGETS)
def test_hero_matches_baseline(app_browser: AppBrowserHarness, tmp_path: Path, target: str) -> None:
    """Each hero state matches its committed baseline within tolerance."""
    image_bytes = _capture_hero(app_browser, target)
    baseline = BASELINE_DIR / f"{target}.png"

    if os.environ.get(UPDATE_ENV) == "1":
        BASELINE_DIR.mkdir(parents=True, exist_ok=True)
        baseline.write_bytes(image_bytes)
        pytest.skip(f"Updated visual baseline {baseline.name}")

    assert baseline.exists(), (
        f"Missing visual baseline {baseline}. Run `make visual-baselines` to create it."
    )

    candidate = tmp_path / f"{target}.png"
    candidate.write_bytes(image_bytes)
    result = visual_regression.compare_images(
        baseline,
        candidate,
        max_diff_fraction=MAX_DIFF_FRACTION.get(target, DEFAULT_MAX_DIFF_FRACTION),
    )
    if not result.passed:
        failed_copy = tmp_path / f"{target}-candidate.png"
        failed_copy.write_bytes(image_bytes)
        pytest.fail(f"{target}: {result.message} (candidate saved at {failed_copy})")
