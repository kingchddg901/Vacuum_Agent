# Theme gallery — drop-in previews

Commit a theme **export** JSON here (the export/import schema:
`{ ok, version, exported_at, scope, theme: { name, tokens, colors, alpha } }`)
and CI renders a preview of the real card recolored by it — see
`.github/workflows/theme-intake.yml`. PRs and manual runs come back as workflow
artifacts; on push to master the whole gallery (a static `index.html` + per-theme
previews) is published to GitHub Pages. One-time: enable Pages with the *GitHub
Actions* source in repo settings.

Every upload runs through the **ingest gate** first
(`window.__evcc.ingestTheme`, the same validate + clamp path as
`import_theme`): only known registry `--evcc-*` keys are kept, bounded
scalars are clamped to range, malformed / unknown-namespace exports are
skipped, and nothing is eval'd. So a shared export is data, not code.

Locally: `node harness/preview.mjs gallery/themes/<file>.json`.
