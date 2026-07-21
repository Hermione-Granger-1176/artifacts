<h1 align="center">Artifacts</h1>

<p align="center">
  Interactive HTML artifacts built with AI tools.<br>
  <sub>Self-contained web apps: calculators, visualizers, explainers, and more.</sub>
</p>

<p align="center">
  <!-- AUTO:TOTAL_BADGE --><img src="https://img.shields.io/badge/Total-4-D97706?style=for-the-badge" alt="Total"><!-- /AUTO:TOTAL_BADGE -->
</p>

<p align="center">
<!-- prettier-ignore-start -->
<!-- AUTO:TAG_BADGES_START -->
<img src="https://img.shields.io/badge/Finance-27AE60?style=flat-square" alt="Finance">&nbsp;
<img src="https://img.shields.io/badge/Calculator-2E86C1?style=flat-square" alt="Calculator">&nbsp;
<img src="https://img.shields.io/badge/Visualization-E67E22?style=flat-square" alt="Visualization">&nbsp;
<img src="https://img.shields.io/badge/Education-F39C12?style=flat-square" alt="Education">&nbsp;
<img src="https://img.shields.io/badge/AI-A0C8E8?style=flat-square" alt="AI">&nbsp;
<img src="https://img.shields.io/badge/LLM-E8C8A0?style=flat-square" alt="LLM">&nbsp;
<img src="https://img.shields.io/badge/Sampling-E8C8A0?style=flat-square" alt="Sampling">&nbsp;
<img src="https://img.shields.io/badge/Tokenization-F5E6A3?style=flat-square" alt="Tokenization">
<!-- AUTO:TAG_BADGES_END -->
<!-- prettier-ignore-end -->
</p>

<p align="center">
<!-- prettier-ignore-start -->
<!-- AUTO:TOOL_BADGES_START -->
<img src="https://img.shields.io/badge/Claude-D97706?style=flat-square&logo=anthropic&logoColor=white" alt="Claude">
<!-- AUTO:TOOL_BADGES_END -->
<!-- prettier-ignore-end -->
</p>

<br>

## What it is

Each directory under `apps/` is a standalone HTML page on a focused topic: bond math, token sampling, loan schedules, prompt caching, and more. Browse the live site at <!-- AUTO:SITE_URL -->https://hermione-granger-1176.github.io/artifacts/<!-- /AUTO:SITE_URL --> for searchable thumbnails, multi-select filters, and detail overlays.

<!-- AUTO:TOTAL_COUNT -->4<!-- /AUTO:TOTAL_COUNT --> artifacts published so far.

<br>

## Quick start

```bash
make setup          # install Python + Node toolchain
make check          # full local CI gate
make new name=my-artifact   # scaffold a new artifact
```

<br>

## Add an artifact

```text
apps/<slug>/
├── index.html        # Entry point
├── css/
│   └── app.css       # App-local styles
├── js/
│   └── app.js        # App-local behavior
├── README.md         # App overview
├── name.txt          # Display name
├── description.txt   # Short description
├── tags.txt          # Content tags (one per line)
├── tools.txt         # AI tools used (one per line)
└── docs/             # Architecture, verification, decisions
```

Two scaffolding flows:

- **Fresh placeholder:** `make new name=my-artifact` emits a complete, passing structure.
- **Drop in existing HTML:** `make new name=my-artifact src=path/to/file.html` installs the file as `index.html`, injects the CSP meta and shared stylesheet links when absent, and reports any off-origin references to vendor or remove.

After scaffolding, fill in the metadata files, run `make validate`, and push to `main`. CI generates thumbnails, builds the site, and deploys. See [`docs/architecture.md`](docs/architecture.md) for the full pipeline and PR preview workflow.

<br>

## Documentation

- [Workspace](docs/workspace.md)
- [Architecture](docs/architecture.md)
- [Frontend](docs/frontend.md)
- [Operations](docs/operations.md)
- [Maintenance](docs/maintenance.md)
- [Style Guide](docs/style.md)
- [ADRs](docs/adr/)
- [Contributing](.github/CONTRIBUTING.md)
- [Security](.github/SECURITY.md)
- [Code of Conduct](.github/CODE_OF_CONDUCT.md)

<br>

## License

[MIT](LICENSE)

---

<p align="center">
  <sub>Created by <a href="https://github.com/Hermione-Granger-1176">Aditya Kumar Darak</a></sub>
</p>
