# Release checklist

Cutting a release = bump the version, land it on `master`, tag it, and publish a
GitHub release. It reads the version from `custom_components/eufy_vacuum/manifest.json`.

**`hacs.json` sets `zip_release` + `filename`, so HACS installs the
`eufy_vacuum.zip` release ASSET — not the directory contents of the tag.** A
release published without that asset cannot be installed at all, so the tag alone
is not a release. The asset is built and attached by the `release assets`
workflow; §4 is where you confirm it actually arrived.

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
      version HACS reads** — the npm `package.json` version is unrelated and stays as-is. It must
      equal the tag without the leading `v`; the release workflow fails the release if it does not.
      Cutting a stable tag off a tree whose manifest still says `-beta` is the specific mistake
      that guard exists for.
- [ ] `CHANGELOG.md` — finalize the `## [X.Y.Z] - YYYY-MM-DD` section (dated), and leave a fresh
      empty `## [Unreleased]` above it.
- [ ] Commit: `release: vX.Y.Z`.

## 3. Merge + tag

- [ ] Merge the PR to `master` (keep the rebuilt-bundle / reference commit in the merge).
- [ ] Tag from `master`: `git tag vX.Y.Z && git push origin vX.Y.Z`.

## 4. Publish the GitHub release

- [ ] `gh release create vX.Y.Z --title "vX.Y.Z — <headline>" --notes-file <notes>`
      (or via the GitHub UI from the tag). Use the CHANGELOG section as the notes.
- [ ] **Pre-release?** Pass `--prerelease` (or tick *Set as a pre-release*) for any version with
      a `-beta`/`-rc` suffix. Without the flag it becomes *latest* for every HACS default-store
      user. The workflow now refuses to publish assets if the suffix and the flag disagree.
- [ ] The **`release assets`** workflow (`.github/workflows/release.yml`) must finish green. It
      asserts `manifest.json` matches the tag, then attaches:
      - **`eufy_vacuum.zip` — the install payload.** Confirm it is under **Assets**. If it is
        missing, nobody can install or update to this release; fix the workflow and re-run it
        rather than leaving the release published.
      - `en.reference.jsonc`, so translators can download the key reference.

## 5. Post-release

- [ ] HACS offers the new version (a few minutes; users get the update banner). Spot-check a cold
      HACS install for a notable release — that exercises the zip asset, which is the only path
      real users take.
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
