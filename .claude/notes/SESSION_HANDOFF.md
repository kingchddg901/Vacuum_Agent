# SESSION HANDOFF — 2026-08-24 (release push, audit running)

**Read this first on resume.** Compaction happened; this survived it. Branch
`do-not-push` (never push it). Release push against Chris's Sep-1 sub-tier drop.
**Ultracode ON.**

---

## COMMITS ON `do-not-push` SINCE `8e7e4cd3` (10 commits)

```
89195039 feat(card): sequence-toggle row — five states, three verification signals   ← latest
1f153481 fix(card): three release-critical i18n/RTL defects — Chinese, Arabic, C17 story
9fa77ed7 fix: R6 + B17 + B27 + B31 — tier D polish before release
ba926a7f fix(rooms): R16 — PER_MAP_STORES becomes single source of truth (3-tuple)
1a8e10e8 feat(clean-order): Override Order switch + apply/clear services, autospec'd
2ff79c35 feat(clean-order): the WRITE, model-gated, ack-verified — Roborock V1 only
0f3628bb docs+schema: the declaration seam — 3 seam labels + 1 declaration
98596dac fix: a dead matcher, an unapproved room, gates that rewarded staleness
c598119a fix: an arrival is not a transition — three guards that read as complete
286643cb fix: issue #54, a hang, and 9 more defects from the comment audits
8e7e4cd3 pre-session base
```

**Working tree clean.**

Full pytest at last full run: **4641 passed / 2 skipped**. Node units after task 4:
**1000 pass** (+9 SEQ). Four doc gates green. Bundle rebuilt at 89195039.

---

## RUNNING IN BACKGROUND WHEN COMPACTION FIRED

1. **Full pytest suite `b6mgfkf9a`** — kicked off after task 4 committed. Would land
   at ~4650 passed (added [SEQ-*] × 9 for task 4). Read result:
   ```
   grep -E "passed|failed" C:/Users/CKing/AppData/Local/Temp/claude/--192-168-4-104-config-/0818c3b5-98f2-471d-9a08-a12127b4b5e5/tasks/b6mgfkf9a.output
   ```

2. **5-dim pre-release audit workflow `wf_3d15bb27-18c`** — Chris said "the checks I
   needed were the missing keys and RTL format issues" (tasks 15/16/17 — all landed
   in `1f153481`), so task 5 was cleared to run as designed. Ultracode-on workflow,
   5 investigators + 5 adversaries + 1 synthesis. Result comes back as a task
   notification with `synthesis` (GO / HOLD / STOP + ranked findings + draft CHANGELOG).
   Script at:
   `C:\Users\CKing\.claude\projects\C--Users-CKing-Documents-GITHUB-eufy-vacuum-manager\0818c3b5-98f2-471d-9a08-a12127b4b5e5\workflows\scripts\pre-release-audit-2110-wf_3d15bb27-18c.js`

   When the audit lands: read `synthesis.recommendation`. GO → task 6 (version bump +
   tag). HOLD → work the ranked findings, then re-audit or spot-check. STOP → surface
   to Chris before continuing.

---

## TASK LIST (14 of 17 complete)

```
[c]  1  switch + services (1a8e10e8)
[c]  2  R16 (ba926a7f, incl. R12/R23)
[c]  3  B4 (9fa77ed7) + B21 (1f153481)
[c]  4  sequence-toggle card row (89195039)
[·]  5  pre-release audit  ← running as wf_3d15bb27-18c
[ ]  6  version bump + tag  (blocked on 5's GO)
[ ]  7  ledger housekeeping  (blocked on 6)
[c]  8  R6 (9fa77ed7)
[c]  9  R12 (ba926a7f)
[c]  10 B17 (9fa77ed7)
[c]  11 R23 (ba926a7f)
[c]  12 B27 (9fa77ed7)
[c]  13 B31 (9fa77ed7)
[ ]  14 triage remaining ~129 audit findings  (deferred post-release)
[c]  15 zh-Hans/zh-Hant split-bug (1f153481)
[c]  16 component labels bypass i18n (1f153481)
[c]  17 metrics.js RTL / bidi isolation (1f153481)
```

---

## WHAT THE THREE FRONTEND DEFECTS WERE (1f153481) — for context after compact

* **Task 15** — `_localizedGuide` at `src/renderers/maintenance.js:85` did
  `.split("-")[0]`, so `zh-Hans` → `zh`. `GUIDE_TRANSLATIONS` map keyed by full ID,
  lookup missed, both Chinese variants fell back to English silently. Fix pattern
  matches `src/i18n/index.js:277`. `[LG-1..4]` uses Han-script detection.

* **Task 17** — six sites in `src/renderers/metrics.js` composed `"46 min"` as bare
  literal; RTL flipped to "min 46". Extracted `formatUnitValue(v, unit, escape)`
  returning `<bdi>{v}</bdi>&nbsp;{unit}`. Three new i18n keys
  (`metrics.unit_percent`, `unit_square_meters`, `unit_per_hour`). `[UV-1..4]`
  in new file `src/renderers/metrics-unit-value.test.mjs`.

* **Task 16** — 16 component labels ("Main Brush" etc.) were English literals in
  `adapters/{roborock,eufy}/maintenance_components.py`, rendered verbatim.
  `maintenance.component_label.<key>` in all 18 packs. Card's
  `_maintenanceItemName` prefers key, falls through to backend label when key
  returns unchanged. `[MIN-1..4]`.

**Common defect class named in `f/pre_release_audit_pattern`**: `check:i18n` verifies
pack completeness — cannot see strings that never enter the system, lookup logic that
never asks, or English suffix literals in composed strings.

---

## TASK 4 (89195039) — the sequence-toggle card row

Row appears only when the vacuum's adapter+model declares the write
(switch entity presence gates visibility). Five states derived by pure
`deriveSequenceRowState()` in `src/state/sequence-override.js`
(9 tests `[SEQ-1..7]`). Card renders via `_renderSequenceOverrideRow(rooms)`
in `dashboard-card.js`, wired into the room list next to `_renderStrictOrder`.

Three event handlers:
- toggle flips `switch.<obj>_clean_order_override`
- Apply → `eufy_vacuum.apply_clean_sequence`
- Clear → `eufy_vacuum.clear_clean_sequence` (window.confirm gates because it may
  destroy a sequence the user set in their Roborock app)

11 i18n keys under `rooms.override_order.*`, translated for
ar/he/ru/zh-Hans/zh-Hant/ja/ko, English-identical + accepted-listed for Latin.

CSS uses semantic tokens (`--evcc-sem-warning`, `--evcc-sem-success`,
`--evcc-text-muted`) and `border-inline-start` for RTL correctness. Regenerated
`docs/dev/reference/THEME_TOKEN_USAGE.md`.

---

## RELEASE STATE — 2.1.0 IS CUT LOCALLY AND NOT PUSHED

Five 5-dimensional audits ran. All findings closed; the deliberate-and-not-a-bug
list is `.claude/notes/POST-2.1.0-deferred.md` — feed it to any further audit or it
re-derives settled questions.

**Local tree is release-ready and CLEAN:**
- `manifest.json` = `2.1.0` (`c256bba8`). It is the ONE version file, and
  `release.yml` refuses to build `eufy_vacuum.zip` on a tag/manifest mismatch —
  which for a `zip_release` repo means the release cannot be INSTALLED, not that it
  installs something wrong.
- `CHANGELOG.md` heading is `## [2.1.0] - 2026-08-24`, one merged section.
- Gates all green at `c256bba8`: 4676 python (+2 skipped), 1035 node, 317 harness
  (+31 skipped), 31 visual re-run in the pinned Linux image with no baseline
  movement, `check:styles`, `check:i18n`.
- Deployed full-tree to `Z:\` and HA restarted 2026-08-24 20:44. Clean load, no
  eufy/roborock errors. The only warnings are the loader's custom-integration
  notice and the Dreame refusal for `vacuum.robin` — the latter is the shipped
  behaviour, not a fault.

**NOT DONE, and deliberately waiting on Chris:**
1. `git push origin master` — **61 commits**, nothing on this release has ever been
   pushed. Branch is `master` tracking `origin/master`, 0 behind.
2. Tag `v2.1.0` and publish the GitHub release. The tag carries a leading `v`; the
   manifest does not; `release.yml` strips it.
3. Release body is written and final: `scratchpad/RELEASE-2.1.0.md` in this
   session's scratchpad (suite count already updated to 4676).

⚠ The handoff previously said "push tag only, do not merge `do-not-push` → master".
That predates the branch situation and does NOT describe the tree now: the work is
ON master and the push is a normal master push.

⚠ Publishing WITHOUT the pre-release flag is correct here and is checked: the
second gate in `release.yml` only rejects a `-beta` version published as stable.
`2.1.0` has no suffix, so it is meant to go out as latest to every HACS
default-store user. That is the audience — see `p/hacs_plan`.

---

## RECIPES FOR RESUME

**Tests only in Docker** (Windows `python -m pytest` dies at `import fcntl`; piped
to tail reports exit 0 for a suite that never ran):

Use **PowerShell** — Git-Bash mangles `-w /workspace` to `C:/Program Files/Git/workspace`.

```
docker run --rm -v "C:\Users\CKing\Documents\GITHUB\eufy-vacuum-manager:/workspace" -w /workspace eufy-vacuum-test python -m pytest tests --no-cov -p no:cacheprovider
```

**Bundle rebuild** after any `src/**` change: `npm run build:deploy`.

**Commit protocol**: private `GIT_INDEX_FILE`, `read-tree HEAD`, add + commit, then
`git reset -q HEAD -- <SPECIFIC PATHS>`. NEVER `-- .` (broadcasts a false-delete
across the whole tree; recover with `git reset --mixed HEAD`).

**Both ratchets live**:
- New test file → `docs/testing/subsystems/*.md` row required.
- Bare `MagicMock()` for a handler dependency → `create_autospec(spec_set=True, instance=True)`.

---

## MODEL / STABILITY

Started on Opus 5. Dropped to 4.7 for stability around the workflow phase. 4.7 needs
the ratchets working harder (both mock and docs ratchets caught bare-mock shortcuts
this session that Opus 5 might have avoided authoring). Suite alone is not enough —
always run the four doc gates + `npm run test:units` before commit.
