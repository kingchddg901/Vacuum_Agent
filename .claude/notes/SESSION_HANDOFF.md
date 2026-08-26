# SESSION HANDOFF — 2026-08-25 (Dreame guide families, then issue #55)

**Read this first on resume.** Index = durable facts, this = current state.

**Branch: `master`. Pushed through `52ba1c4b`.** ⚠ An older handoff said "branch
`do-not-push` (never push it)" — that was the 2.1.0 release session and is NO LONGER
the working state. `do-not-push` still exists as a branch; we are not on it.

⚠ This file went stale on issue #55 within an hour of being written (it said "body not
opened, no reply drafted" while #55 was being diagnosed and fixed). Handoffs rot ONE
WAY — written at the pause, never at the resume. Re-read the git log before trusting a
status line here.

---

## WHERE THIS STOPPED

Seven Dreame upkeep-guide families authored, every downloaded manual now transcribed.
**Nothing is wired** — there is still no `BRAND_REGISTRARS` row, and that row is the
release. Paused cleanly: working tree committed and pushed, suite green.

```
6f64d557  author l20, x40, l50 — every manual in hand is now a family
d9f67af7  author x50; split x60 into the two families it always was
7b58f441  correct the family rule — a family is a MANUAL PAGE, not an r-code
67cad893  pin the Dreame family scope (superseded by 7b58f441)
```

**4730 passed / 2 skipped locally.** CI was green on `b39b7395`; `52ba1c4b`'s run was
not checked before this was written — check it, do not assume it.

---

## THE OPEN QUESTION CHRIS ASKED, AND THE ANSWER

> "is that English only?"

**Yes.** All 264 authored strings come from EN sections. There is **no
`upkeep_guides_i18n/` for Dreame at all**, while Eufy and Roborock each carry 17 packs
plus the EN base. That is a standing gap against `f/no_string_without_i18n`.

Chris said **"record this for now"** — so it is recorded, NOT started. The i18n rollout
is marked LOCKED at 18 languages (`p/i18n_rollout`), so adding Dreame packs is a
decision, not cleanup. **Do not begin translation work without his explicit go.**

Measured coverage of translated MANUFACTURER text already in hand, by family
(`.claude/notes/SCOPE-dreame-guide-families.md` holds the full matrix):

```
EN 7/7 · DE 6/7 · FR 6/7 · IT 5/7 · ES/NL/PL 3/7 · HE/PT 2/7
AR/ID/JA/TR/ZH-Hant 1/7 (l10s_gen2 only) · CS 0 · ZH-Hans 0
KO — present for x50 and x60_ultra, see the correction below
```

---

## THE CORRECTION THAT CAME OUT OF IT

`synthesis/dreame-port/MANUAL-INVENTORY.md` records **`ko` as absent, with evidence** —
Dreame Korea publishes exactly 12 manuals and no L10s of any generation, adjacent ids
probed to prove the list complete. **That finding is correct and it is scoped to the
L10s Ultra Gen 2**, which is the only device that inventory was ever about.

But those 12 Korean entries are X60 / Aqua10 / Matrix10 / X50s — and
`durable/dreame-port-fixture/manuals/korean-vocabulary-source/` holds **R2489F and
R5089F**, the Korean editions of the X50 and the X60 Ultra. Both are families authored
today. So Korean IS in hand for two of the seven.

**Same shape as two other errors this session: a correct negative that outlived its
scope.** The inventory has been annotated rather than rewritten — its Gen 2 finding
stands.

---

## STANDING LESSONS FROM THIS SESSION

⚠ **A probe that answers uniformly is broken, not informative.** Three times:

1. Provenance check v1 used `difflib` longest-contiguous-match and flagged **all 156**
   strings including verbatim ones — PDF extraction interleaves columns, so no long
   contiguous run survives. Bigrams survive it.
2. The language probe returned **zero languages for every manual**. It sliced only the
   tail of the extracted text; footers are not last in content-stream order.
3. Its fixed version still under-reported, because **single-language regional editions
   carry no ASCII footer code at all**. RU / JA / ZH-Hant were nearly reported absent
   with the Cyrillic, Kana and Han plainly in the file.

**The fix that generalises: ablate the probe against something independently known.**
The language probe is trustworthy only because it recovers exactly what each filename
claims (`R2489A-X50_Series-EN_DE_FR` → EN, DE, FR).

⚠ **An exemption needs its own floor.** The provenance checker waved through any
component/kind pair on the recast list — a wholly invented sensor step would have been
labelled "recast" and passed. Now floored at 40%; fabricated text scores 0%.

⚠ **Exit codes lied repeatedly in the previous session too** (`tail`'s status, a
background wrapper's last command, a PowerShell `Select-Object` pipeline). Read the
COUNT LINE (`4720 passed`), never the exit code.

---

## THE ISSUE #55 ARC, IN ONE PLACE

A support report turned into three defects of the same family — **naming a cause we
could not see** — and one architectural gap.

1. **`ServiceNotSupported` folded into "failed"** (`b39b7395`). A permanent refusal was
   dressed as a transient fault with a bug report attached. He filed the report.
2. **The diagnostic could not see WHY** (`52ba1c4b`). The room-source cache recorded
   only SUCCESSES, so a refusal left no trace and the self-check inferred the reason
   from the shape of the entity list. Now the outcome is recorded at the single point
   every service-source exit funnels through, and read rather than deduced.
3. **A fallback that yielded a BRAND'S WORD.** The self-check's `else` branches named
   the Eufy app and the eufy-clean fork unconditionally — issue #46's defect, fixed in
   the import message and left alive in the sibling path. De-branded WITHOUT deleting
   the advice: a Eufy owner on the reduced transport genuinely needs that fork, and the
   honest discriminator is `has_segments` (the transport signature), not the label.
4. **Two causes, one signature.** The job-active warning asserted capability-gating
   (#173282) as fact. For a B01 device that is simply wrong. It now names both and
   asserts neither.

⚠ **BOTH OF MY OWN DEFECTS HERE WERE CAUGHT BY EXISTING TESTS, NOT BY REVIEW** —
`brand.lower()` on an Optional[str] (which would have made the whole self-check vanish
silently, because its caller catches everything into `{"error": ...}`), and de-branding
that dropped real advice for brandless Eufy installs. Both were invisible on a read.

---

## TOOLING BUILT (both durable, both in `scripts/`)

* **`pdf_layout_dump.py`** — reconstructs visual reading order from PDF text matrices.
  **There is no rasteriser in this environment** (no poppler, no PyMuPDF), so the
  `Read` tool cannot render PDF pages; this is how manuals get read. Makes a
  three-column care page legible.
  `python scripts/pdf_layout_dump.py MANUAL.pdf 22-30`
* **`verify_dreame_guide_provenance.py`** — scores every authored string against its
  source manual. 264 strings, 0 defects, 15 known recasts. **Cannot be a CI gate** —
  the manuals are vendor copyright and stay out of the repo.

---

## WHAT IS NOT DONE

* **22 of the 26 current-ish Dreame platforms have no manual and no family.** Next
  family costs a NEW PDF, not a new read; ~13 manual pages would cover the rest.
* **Dreame i18n** — see above. Recorded, not started, needs Chris's go.
* **`ADAPTER-CONFIG.generated.md` is committed but NOT freshness-gated** — see
  `POST-2.1.0-deferred.md` entry 5. Not in `GENERATORS`, generator still untracked,
  measured decay 364 lines in ~2 days. Fix is one `Generator(...)` entry plus a
  force-add. Held out of 2.1.0 deliberately.
* **Issue [#55](https://github.com/kingchddg901/Vacuum_Agent/issues/55)** — DIAGNOSED
  AND FIXED (`b39b7395`, `52ba1c4b`), **REPLIED AND CLOSED 2026-08-26** as
  `NOT_PLANNED` (comment `5418743449`). Nothing outstanding. The text sent is kept at
  `.claude/notes/ISSUE-55-reply-draft.md`, marked POSTED — do not send it again.

  Root cause: a Roborock Q7 M5 is a **B01-protocol** device. HA routes it to
  `RoborockQ7Vacuum`, whose `get_maps()` is a stub raising `ServiceNotSupported`
  unconditionally (`components/roborock/vacuum.py`, 2026.8); the Q10 class is identical
  and only V1 implements it. B01 devices also get no `selected_map` select and no binary
  sensors at all. Our reading of his device was CORRECT; what was wrong was the cause we
  named and what we told him to do about it.

  ⚠ **THE FIX DOES NOT MAKE HIS VACUUM WORK** — it changes what he is TOLD. Chris's
  point, and the draft says it outright: "we fixed it" reading as "your problem is
  solved" would have him update, watch the import stop again, and conclude we lied.
* Background chip pending: split `dreame_upkeep_guides.py` (1099 lines) into a package.
  "Not yet, revisit at N families" is a legitimate answer to record.

* ⚠ **FOR CHRIS — 209 OF 223 NOTES ARE UNTRACKED, AND THE TRACKED INDEX CITES THEM.**
  Measured 2026-08-25, not acted on. `.claude/` is gitignored by design and the 15
  tracked notes were force-added one at a time as they became load-bearing, so this
  may be entirely deliberate. But the shape is worth a decision:

  - `INDEX.md` IS tracked and links to **93** notes. All 93 resolve on disk — the
    corpus is intact and the index is accurate **locally**.
  - **81 of those 93 point at files that do not exist in the repo.** To a fresh clone,
    or after a `git clean -fdx`, the index is 87% dangling pointers.
  - Same class as the `.claude/generated-docs/` finding recorded below, which cost a
    red CI gate on the release tip — a `.gitignore` on `.claude/` silently excluding
    something the tree depends on.

  **Not fixed here, deliberately** — force-adding 209 notes is a decision about what
  becomes public, not a cleanup, and some of it is unfiltered working thinking. Only
  `synthesis/dreame-port/MANUAL-INVENTORY.md` was force-added this pass, because it was
  corrected today and the tracked index now cites it as authority on a live question.
  The options are: leave as is (notes are local memory), track the ones INDEX cites, or
  stop citing untracked notes from a tracked index.

---

## RECIPES FOR RESUME

**Tests only in Docker** (Windows `python -m pytest` dies at `import fcntl`; piped to
`tail` reports exit 0 for a suite that never ran). Use **PowerShell** — Git Bash mangles
`-w`:

```
docker run --rm -v "C:\Users\CKing\Documents\GITHUB\eufy-vacuum-manager:/w" -w /w eufy-vacuum-test:latest python -m pytest tests --no-cov -p no:cacheprovider
```

The `tests` argument is load-bearing; bare `pytest` skips `tests/adapters`.

**Bundle rebuild** after any `src/**` change: `npm run build:deploy`.

**Commit protocol**: private `GIT_INDEX_FILE`, `read-tree HEAD`, add + commit, then
`git reset -q HEAD -- <SPECIFIC PATHS>`. NEVER `-- .` (broadcasts a false-delete across
the tree; recover with `git reset --mixed HEAD`). `.claude/` is gitignored, so notes
need `git add -f`.

**Three ratchets live**:
- New test file → a row in `docs/testing/subsystems/*.md` required.
- Bare `MagicMock()` for a handler dependency → `create_autospec(spec_set=True, instance=True)`.
- Docs are a release gate after 2.1 (Chris's ruling) — not per-push.

---

## RELEASE STATE — 2.1.0 SHIPPED 2026-08-25

Tag `v2.1.0` → `2b03c140`, marked latest, not a pre-release, so it reached every HACS
default-store user. Deployed full-tree to `Z:\`, clean load.

**The two things only the first push could find** (63 commits had accumulated with
nothing pushed, so two gates went red on the release tip that five audits and every
local run had passed):

1. `check_generated_docs.py` — `THEME_TOKEN_USAGE.md` stale from the banner fix's line
   shifts. Fixed `87942de6`.
2. `test_adapter_config_parity.py` — FileNotFoundError on CI ONLY. `.gitignore` carries
   `.claude/` and the file never got its `git add -f`. **All 54 files under
   `.claude/generated-docs/` were untracked — that gate had never run in CI once.**
   Fixed `b101030f`; the on-disk copy was 364 lines stale and was regenerated rather
   than frozen.

⚠ A local visual run without `VISUAL=1` reports `31 skipped, 1 passed` and reads
exactly like a pass. `card-visual.yml` runs `visual device-theme` — BOTH.

Earlier release-session detail (the 17-task list, the three frontend i18n/RTL defects
in `1f153481`, the sequence-toggle row in `89195039`) is in those commit messages and
in `POST-2.1.0-deferred.md`; it is not repeated here now that 2.1.0 has shipped.
