#!/usr/bin/env python3
"""Scaffold a new artifact directory under ``apps/``.

This module backs `make new name=<artifact-name>`.

It creates a new artifact directory under ``apps/`` with the required metadata
files and a minimal HTML starting point.

Run through the Makefile in normal workflows; direct invocation is mainly for
maintainers working on the build internals.
"""

from __future__ import annotations

import sys
from pathlib import Path

from scripts.build.generate_index import (
    APPS_DIR,
    DESCRIPTION_FILE,
    INDEX_FILE,
    NAME_FILE,
    TAGS_FILE,
    TOOLS_FILE,
    is_kebab_case,
)
from scripts.build.prepare_site import APP_SHARE_IMAGE_PLACEHOLDER, APP_URL_PLACEHOLDER


def _title_from_slug(slug: str) -> str:
    """Convert a kebab-case slug to a human-readable title."""
    return " ".join(word.capitalize() for word in slug.split("-"))


def _index_template(title: str) -> str:
    """Return a mature HTML starting point for a new artifact."""
    return f"""<!DOCTYPE html>
<html lang="en" data-theme="light">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta name="description" content="Replace this description with a concise summary of your artifact.">
  <link rel="canonical" href="{APP_URL_PLACEHOLDER}">
  <meta property="og:title" content="{title} | Artifacts">
  <meta property="og:description" content="Replace this description with a concise summary of your artifact.">
  <meta property="og:type" content="website">
  <meta property="og:url" content="{APP_URL_PLACEHOLDER}">
  <meta property="og:site_name" content="Artifacts">
  <meta property="og:image" content="{APP_SHARE_IMAGE_PLACEHOLDER}">
  <meta property="og:image:secure_url" content="{APP_SHARE_IMAGE_PLACEHOLDER}">
  <meta property="og:image:alt" content="Preview card for the {title} app.">
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="{title} | Artifacts">
  <meta name="twitter:description" content="Replace this description with a concise summary of your artifact.">
  <meta name="twitter:image" content="{APP_SHARE_IMAGE_PLACEHOLDER}">
  <meta name="twitter:image:alt" content="Preview card for the {title} app.">
  <meta name="theme-color" content="rgb(248, 248, 246)">
  <meta name="referrer" content="strict-origin-when-cross-origin">
  <meta http-equiv="Content-Security-Policy"
    content="default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'">
  <title>{title} | Artifacts</title>
  <script src="../../js/app-theme.js"></script>
  <link rel="icon" href="../../assets/icons/favicon.ico" sizes="32x32">
  <link rel="icon" href="../../assets/icons/icon.svg" type="image/svg+xml">
  <link rel="apple-touch-icon" href="../../assets/icons/apple-touch-icon.png">
  <link rel="manifest" href="../../assets/icons/manifest.webmanifest">
  <link rel="stylesheet" href="../../css/app-tokens.css">
  <link rel="stylesheet" href="../../css/app-shell.css">
  <link rel="stylesheet" href="./css/app.css">
</head>
<body>
  <div data-app-shell="header"></div>

  <main class="page-shell">
    <div data-app-shell="runtime-error"></div>

    <header class="page-intro">
      <h1 class="page-title">{title}</h1>
      <p class="page-lede">Replace this scaffold with your artifact and keep shared app styling in the root app system while limiting this local CSS file to page-specific overrides.</p>
    </header>

    <section class="placeholder-card">
      <h2>Get started</h2>
      <p>Build the interaction here, document the architecture in <code>docs/</code>, and keep local styling focused on this app's unique layout.</p>
    </section>
  </main>

  <div data-app-shell="scroll-top"></div>

  <script type="module" src="./js/app.js"></script>
</body>
</html>
"""


def _app_css_template() -> str:
    """Return starter app-specific CSS overrides."""
    return """.placeholder-card {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-surface);
  padding: 1.25rem;
}

.placeholder-card h2 {
  margin-bottom: 0.5rem;
  color: var(--color-text-heading);
  font-size: 1rem;
}

.placeholder-card p {
  color: var(--color-text-secondary);
  line-height: 1.6;
}
"""


def _app_js_template() -> str:
    """Return starter app bootstrap code."""
    return """import { initializeMatureApp } from "../../../js/modules/app-runtime.js";
import { initAppShell, renderAppShell } from "../../../js/modules/app-shell.js";

renderAppShell();

initializeMatureApp({
  run: () => {
    initAppShell();
  }
});
"""


def _readme_template(title: str) -> str:
    """Return starter app documentation."""
    return f"""# {title}

## Purpose

Describe what this artifact does.

## Features

- Replace this with the app's core features

## Structure

- `index.html` - app shell and semantic layout
- `css/app.css` - app-specific visual overrides
- `js/app.js` - app-specific behavior
- `docs/` - internal engineering notes

## Dependencies

- List any runtime dependencies or CDN scripts here

## Development

- Keep shared design decisions in the root app system
- Keep app-local changes scoped to this folder
"""


def _doc_template(title: str, heading: str) -> str:
    """Return a starter internal doc page."""
    return f"""# {heading}

## {title}

Fill in this document as the app grows.
"""


def scaffold_artifact(name: str) -> Path:
    """Create a new artifact scaffold and return the artifact directory path."""
    if not name:
        raise ValueError("Artifact name is required")
    if not is_kebab_case(name):
        raise ValueError("Artifact name must use kebab-case")

    APPS_DIR.mkdir(parents=True, exist_ok=True)
    artifact_dir = APPS_DIR / name
    if artifact_dir.exists():
        raise FileExistsError(f"Artifact directory already exists: {artifact_dir}")

    title = _title_from_slug(name)
    artifact_dir.mkdir()
    (artifact_dir / "css").mkdir()
    (artifact_dir / "js").mkdir()
    (artifact_dir / "docs").mkdir()
    (artifact_dir / INDEX_FILE).write_text(_index_template(title), encoding="utf-8")
    (artifact_dir / "css" / "app.css").write_text(_app_css_template(), encoding="utf-8")
    (artifact_dir / "js" / "app.js").write_text(_app_js_template(), encoding="utf-8")
    (artifact_dir / "README.md").write_text(_readme_template(title), encoding="utf-8")
    (artifact_dir / "docs" / "architecture.md").write_text(
        _doc_template(title, "Architecture"), encoding="utf-8"
    )
    (artifact_dir / "docs" / "verification.md").write_text(
        _doc_template(title, "Verification"), encoding="utf-8"
    )
    (artifact_dir / "docs" / "decisions.md").write_text(
        _doc_template(title, "Decisions"), encoding="utf-8"
    )
    (artifact_dir / NAME_FILE).write_text(title + "\n", encoding="utf-8")
    (artifact_dir / DESCRIPTION_FILE).write_text("\n", encoding="utf-8")
    (artifact_dir / TAGS_FILE).write_text("\n", encoding="utf-8")
    (artifact_dir / TOOLS_FILE).write_text("\n", encoding="utf-8")
    return artifact_dir


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for artifact scaffolding."""
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 1:
        raise ValueError(
            "Usage: make new name=<artifact-name> "
            "(this script is an internal implementation detail)"
        )

    artifact_dir = scaffold_artifact(args[0])
    print(f"Created artifact scaffold: {artifact_dir}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    try:
        raise SystemExit(main())
    except (FileExistsError, ValueError) as exc:
        print(exc, file=sys.stderr)
        raise SystemExit(1) from exc
