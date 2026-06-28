# Release checklist

Cutting a release = bump the version, land it on `master`, tag it, and publish a
GitHub release. **HACS** serves whatever the latest GitHub release tag points at;
it reads the version from `custom_components/eufy_vacuum/manifest.json`.

> `scripts\deploy-live.ps1` hand-copies the working tree to the live HA for
> **test iteration** — that is *not* a release. A release is the tag + GitHub
> release below.

## 1. Pre-flight (on the release branch, before merge)

- [ ] Backend tests green — `scripts\test.bat --no-cov` (Docker; pytest-homeassistant needs Linux).
- [ ] i18n contract green — `npm run check:i18n` (key parity, placeholders, plurals, escape, draft-gate).
- [ ] Docs build clean — `python -m mkdocs build --strict` (the link gate).
- [ ] Card + reference rebuilt — `npm run build:deploy` regenerates the served bundle
      (`custom_components/eufy_vacuum/frontend/eufy-vacuum-command-center.js`) and
      `…/locales/en.reference.jsonc`. **Commit them** so the served bundle matches `src/`.
- [ ] CI green on the PR — `tests`, `node-test`, `Validate` (hassfest + HACS), `card visual regression`, `docs`.

## 2. Version + changelog

- [ ] Bump `custom_components/eufy_vacuum/manifest.json` → `"version": "X.Y.Z"`. **This is the only
      version HACS reads** — the npm `package.json` version is unrelated and stays as-is.
- [ ] `CHANGELOG.md` — finalize the `## [X.Y.Z] - YYYY-MM-DD` section (dated), and leave a fresh
      empty `## [Unreleased]` above it.
- [ ] Commit: `release: vX.Y.Z`.

## 3. Merge + tag

- [ ] Merge the PR to `master` (keep the rebuilt-bundle / reference commit in the merge).
- [ ] Tag from `master`: `git tag vX.Y.Z && git push origin vX.Y.Z`.

## 4. Publish the GitHub release

- [ ] `gh release create vX.Y.Z --title "vX.Y.Z — <headline>" --notes-file <notes>`
      (or via the GitHub UI from the tag). Use the CHANGELOG section as the notes.
- [ ] The **`release assets`** workflow (`.github/workflows/release.yml`) auto-attaches
      `en.reference.jsonc` to the release — confirm it appears under **Assets** so translators
      can download it.

## 5. Post-release

- [ ] HACS detects the new tag (a few minutes; users get the update banner). Spot-check a cold
      HACS install for a notable release.
- [ ] If the release adds languages or notable card UI, mention it in the
      [translate discussion](https://github.com/kingchddg901/Vacuum_Agent/discussions/25).

## Gotchas

- A locally-built bundle pushed straight to a branch **bypasses** the hassfest/visual CI gates —
  they only run on PR to `master`, so don't skip the PR.
- HACS reads `manifest.json` `version` + `hacs.json` (`name`, `homeassistant` minimum). It does
  **not** read `package.json`.
- Card visual-regression baselines are generated in the pinned Playwright image; if a real UI
  change trips them, re-bless from the CI artifact (see `docs/dev/27-render-harness/`), don't
  hand-edit PNGs.
