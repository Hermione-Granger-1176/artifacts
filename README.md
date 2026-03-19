# Artifacts

A collection of interactive HTML artifacts built with AI tools (Claude, ChatGPT, Gemini, etc.). Each artifact is a self-contained web application with its own page.

**Live site:** https://hermione-granger-1176.github.io/artifacts/

<!-- AUTO:TOTAL_BADGE --><img src="https://img.shields.io/badge/Total-1-D97706?style=for-the-badge" alt="Total"><!-- /AUTO:TOTAL_BADGE -->

## Topics

<!-- AUTO:TAG_BADGES_START -->
<img src="https://img.shields.io/badge/Finance-27AE60?style=flat-square" alt="Finance">&nbsp;
<img src="https://img.shields.io/badge/Calculator-2E86C1?style=flat-square" alt="Calculator">&nbsp;
<img src="https://img.shields.io/badge/Visualization-E67E22?style=flat-square" alt="Visualization">
<!-- AUTO:TAG_BADGES_END -->

## AI Tools

<!-- AUTO:TOOL_BADGES_START -->
<img src="https://img.shields.io/badge/Claude-D97706?style=flat-square&logo=anthropic&logoColor=white" alt="Claude">
<!-- AUTO:TOOL_BADGES_END -->

## Artifacts (<!-- AUTO:TOTAL_COUNT -->1<!-- /AUTO:TOTAL_COUNT -->)

<!-- AUTO:ARTIFACTS_TABLE_START -->
| Artifact | Description | Tools | Live Link |
|----------|-------------|-------|-----------|
| Loan Amortization Schedule | Interactive loan amortization calculator with charts, extra payment scenarios, and detailed repayment schedules. | Claude | [Open](https://hermione-granger-1176.github.io/artifacts/apps/loan-amortization/) |
<!-- AUTO:ARTIFACTS_TABLE_END -->

## Structure

Each artifact lives in its own directory under `apps/` with an `index.html` entry point. This allows future refactoring into multi-file projects without breaking URLs.

```
apps/
  artifact-name/
    index.html        # Entry point (currently single-file, can be split later)
    name.txt          # Display name
    description.txt   # Short description
    tags.txt          # Content tags (one per line)
    tools.txt         # AI tools used (one per line)
    thumbnail.png     # Auto-generated screenshot
```

## Adding a new artifact

1. Create a kebab-case directory under `apps/`
2. Add `index.html` and metadata files
3. Push to `main` — everything else is automated

## License

[MIT](LICENSE)
