# SESSION HANDOFF — 2026-08-26 (evening) — Dreame pre-stage; `room_profiles` landed

**Read this first on resume.** Index = durable facts, this = current state.

**Branch: `master`. 10 commits AHEAD of `origin/master`, NOT pushed.** ⚠ The previous
handoff said "Pushed through `52ba1c4b`" — that is no longer true, and five of the ten
commits have DIFFERENT HASHES than they did this morning (see THE GIT REPAIR below).
`do-not-push` still exists as a branch; we are not on it.

⚠ Handoffs rot ONE WAY — written at the pause, never at the resume. Re-read the git log
before trusting a status line here. **This file proved it again today**: its corpus line
said "229 manuals / 2.8 GB" when the corpus on disk was 2,369 PDFs / 20 GB.

---

## ⭐ READ FIRST

1. `.claude/notes/STATE-dreame-manual-corpus.md` — the durable record. Four new sections
   were appended today; the newest supersedes older arithmetic in the same file.
2. `.claude/notes/STATE-dreame-corpus-extraction.md` — supersedes the manual-corpus
   arithmetic wherever they disagree.

**Corpus lives OUTSIDE the repo** at `C:/Users/CKing/Documents/durable/dreame-port-fixture/`
— 2,369 PDFs, 20 GB. Chris's ruling: **"those pdfs are not going to the repo."** There is
still NO `.gitignore` guard for `*.pdf` or `durable/`.

⚠ **NEVER RENDER A VERDICT ON AN EMPTY SAMPLE.** A check that measured nothing printed a
confident pass in a previous session (`0 <= 0 * 0.25`). Guard every summary with "did I
measure anything at all?"

---

## ⚠ THE GIT REPAIR — READ BEFORE ANY COMMIT

**HEAD's tree contained exactly ONE file this morning.** The five unpushed
`notes(dreame)` commits had each written a tree containing only
`STATE-dreame-manual-corpus.md`; every other file was recorded as deleted. `origin/master`
was intact; the working tree was intact; only the commits were wrong.

Repaired by replaying all five with `commit-tree` onto `496a57d6`'s tree, preserving
messages, authors and dates:

```
9a735705 -> 905cf190    2c0a33ab -> a2aad2ca    5096d3f2 -> d267d59c
e08944cb -> 460a4c0d    9b8c77d7 -> 19740ffb
```

Verified after: note blob identical (`2a0ca784`), all five messages preserved, 1345 files,
0 PDFs, clean tree. Old tip `9b8c77d7` is recoverable via reflog. Nothing on disk changed.

⚠ **THE LIKELY CAUSE, AND IT IS STILL LIVE.** `git add` on a TRACKED file under
`.claude/` **succeeds but exits 1** — `.gitignore:83` carries `.claude/` and git prints
ignored-path advice regardless of the file already being tracked. Any `git add ... && git
commit ...` chain therefore stages the file and then SILENTLY SKIPS THE COMMIT. That is
almost certainly how the `read-tree HEAD` seeding step got skipped five times in a row.

**Do not chain add and commit with `&&` for anything under `.claude/`.** Run them as
separate statements and check `git ls-tree -r HEAD --name-only | wc -l` (expect 1346)
after every commit.

---

## WHERE THIS STOPPED

Paused cleanly. Working tree clean except six untracked `scripts/dreame_*.py`. Suite not
re-run this session — no Python behaviour changed until the last commit, and that commit
is inert data with no importer.

```
38ede994  feat(dreame): room-profile vocabulary, captured from a live device
a6bb183e  notes(dreame): correct the -1 rule - it is a (robot, dock) pairing
de8d7129  notes(dreame): the 51% caveat was pointed the wrong way - it is a floor
5b7ceb11  notes(dreame): the document is the unit - one code, up to six SKUs
80b2ffa2  notes(dreame): coverage vs the supported surface, and where the wandering was
```

plus the five replayed commits beneath them. Tree: **1346 files, 0 PDFs.**

---

## THE FRAMING CHRIS GAVE, WHICH REFRAMES EVERYTHING ABOVE

> "this was a pre stage i was trying to have it all ready for when upstream lands the fix
> for all others to be able to use VA"

**VA = the integration itself** (`docs/dev/design/shipped/map-state-source.md`: "VA-owned
reader", "the VA owns the frame"). NOT Voice Assist — the `VA:` in
`voice-assist-wizard.md` is only a speaker label in a transcript. Do not confuse them.

So the whole Dreame campaign is the **gate-independent half**, exactly as
`adapters/dreame/__init__.py` already says: *"upkeep guides, and later the model/family
metadata"*. The gate is a RELEASED upstream build carrying Tasshack **#1707**.

**#1707 is still OPEN** (checked 2026-08-26, last updated 2026-08-18): `_init_data()`
clears `_capability` and `_aes_iv`, permanently breaking map decoding after an empty map.
That is a VA blocker — no decode means no `map_state_source`.

⚠ **Chris HAS the patch applied locally** — `Z:\custom_components\dreame_vacuum\dreame\map.py`,
marked `# --- VA LOCAL TEST 2026-08-11: upstream suggested fix from #1707`. So local
validation is unblocked; PUBLIC RELEASE IS NOT. Adding the `BRAND_REGISTRARS` row now
would break every user without the patch.

---

## WHAT LANDED TODAY: `adapters/dreame/vocabulary.py`

`room_profiles` is the ONE adapter block where registration HARD-FAILS if absent
(`docs/contributing/porting-guide.md` §10) and Dreame had none. It now exists, DATA ONLY,
still no `adapter.py` and still no registrar row. `BRAND_REGISTRARS` is still
`['roborock', 'eufy']` — verified after the commit.

**Every value was read off the live device**, not a manual — `vacuum.robin`, via
`Z:\.storage\core.entity_registry`. The manuals do NOT carry these enums; the Aqua10
manual defers to "Cleaning Mode settings in the app". Captured vocabulary is kept at
`scratchpad/dreame_live_vocabulary.json` (scratchpad is session-local — re-capture rather
than trust a copy).

Three traps found in the capture, all documented in the file:

1. **The vacuum entity disagrees with the select.** `fan_speed_list` says `Silent`;
   `select.*_suction_level` takes `quiet`. A different WORD, not casing.
2. **Per-room lists are not the global lists.** `cleaning_mode` is 4 globally / 3 per
   room; `cleaning_route` is `quick|standard` globally / `standard|intensive|deep` per
   room.
3. **Dreame has NO no-water word.** `mop_pad_humidity` is three wet states;
   `wetness_level` bottoms out at **1**, not 0.

`FLOOR_TYPE_WATER_DEFAULTS` is therefore **declared EMPTY** rather than inventing an
`"off"` the dispatch `options_key` filter would silently drop (the Roborock capital-O
"Off" defect). The carpet-water-off guarantee still holds via the MODE DOWNGRADE in
`profiles/manager.py` — a carpet room's `clean_mode` is rewritten to `"vacuum"`, which
maps to Dreame's `sweeping`; after that `is_mop` is False so `queue_engine` never writes
water either. Two gates, neither needing a no-water value.

⚠ **DO NOT "FIX" THIS WITH VERSALIFT.** Chris's ruling: *"versa lift is pretty good but
not every vacuum has it."* Mop lift is a PER-MODEL fact; leaning on it moves a framework
safety property onto firmware that may be absent. Same reasoning as the Roborock
`edge_mopping` ruling. The mode downgrade works on every Dreame ever made.

---

## COVERAGE, MEASURED AGAINST CHRIS'S SCOPE RULING

Scope: *"we will support in general what they have listed"* — Tasshack's
`supported_devices.md`, held locally at `durable/dreame-port-fixture/catalogue/`.
**741 models / 386 names.** (A WebFetch of the same page returned 344 models and asserted
a total of 511. Both wrong. The local copy is authoritative.)

| | models | of 741 |
|---|---|---|
| guide authored (7 families) | 202 | 27% |
| manual held | 383 | 51% |
| **held but NOT authored** | **261** | **35%** |
| no manual, no guide | 278 | 38% |

**The 261 is the cheapest work left** — 98 names, no sourcing needed, and not fringe
hardware: `matrix10ultra` (13 models), `p70proultra` (8), `s70ultraroller` (7).

Every authored guide is `dreame.*`; all 154 non-Dreame IDs (mova 102, xiaomi 25,
trouver 13, ijai 11, deerma 2, szkj 1) are uncovered — but 85 of them are authorable from
manuals already on disk.

---

## THE DOCUMENT IS THE UNIT

A manual is scoped to a SERIES and declares one base regulatory code plus N numbered SKU
variants. **N reaches 6.** `RLX85CE` covers X50 / X50 Ultra / X50 Ultra Complete /
GoVac 800 in one document. So ~202 open names is ~100 documents, not 202.

**Track vs Roller costs exactly ONE part.** 27 maintenance rows shared with identical
intervals; the delta is `Fluffing roller` (Roller only), a washboard-filter interval, and
a relabel. A Track manual is ~96% of the upkeep content for the whole Aqua family.

**The code collapses rebadges** — the census payoff:
`RLX95CE` = Matrix10 Ultra = X50 Ultra MatriX · `RLX63CE` = X40 Ultra = GoVac 508 ·
`RLX85CE` = X50 = GoVac 800 · `RLM83HE` = mova lr10 prime / nutripal10 / pf10 / lb10.

⚠ **`-N` IS A (ROBOT, DOCK) PAIRING, NOT A BUNDLE.** An earlier commit today
(`5b7ceb11`) generalised "one robot, one dock" from the Aqua10 case; an adversarial pass
refuted it and `a6bb183e` corrected it. `doc_facts.json` measures 5 families with
DIFFERENT docks vs 3 sharing one. **The S-series rule is the norm; Aqua10 Track is the
exception.**

X-series shape, for reference: X20 predates the `RL*` scheme entirely (no code);
X30 Ultra `RLX56CE` (1); X40 Ultra `RLX63CE` (4); X40 Master `RLX73CE` (separate machine);
X50 `RLX85CE` (6). And **`RLX` does not mean "X-series"** — it also carries L20 Ultra
(`RLX41CE`) and L40 Ultra (`RLX53SE`). Weak hint, not identity.

---

## ⚠ THE MAPPING ALREADY EXISTS — DO NOT RE-DERIVE IT

This session wasted effort regex-scanning `manual_text_cache.json` to build a 64-code map.
The background jobs had already written better:

* `derived/corpus-manifest.json` — 2,015 entries; 365 with `reg_codes`, 326 with
  `names_printed`, 251 with BOTH; 96 distinct codes; yields **84 code→names groups**.
* `derived/doc_facts.json` — **351 Declaration-of-Conformity certificates** →
  `{model, base, product}`; 156 distinct models, 170 distinct base stations. This is the
  AUTHORITATIVE model→dock source.

These ARE the "model/family metadata" the adapter docstring names as the next
gate-independent deliverable. **Read the manifest; do not re-derive from text.**

---

## CORRECTIONS MADE TODAY — DO NOT RE-BREAK THEM

1. **The 51% is a FLOOR, not an inflated figure.** Resolved by READING
   `scripts/dreame_corpus_name.py` rather than inferring: `--devices` is required and the
   matcher is built from `supported_devices.md`, so the namer cannot emit a name outside
   the catalogue. That makes "0 corpus names outside their list" a TAUTOLOGY, not evidence
   of circularity. The 51% counts only COVERED (manual TEXT names the model), excludes
   ATTESTED (filename-only claims), and can only MISS. Earlier guidance not to spend it
   was wrong in DIRECTION.
2. **`matrix10ultra` was ALWAYS in the held-but-not-authored bucket**, never "uncovered".
   A restatement in conversation said otherwise; that was a slip.
3. **"Aqua 10 Pro Roller" is NOT corpus-attested.** No document prints it. The held Roller
   manual prints "Aqua10 Ultra Roller" (`RLH71DE` / `RLH71DE-1`). The only "Pro Roller"
   anywhere in the corpus is S70 Pro Roller (`RLZ11HE`), a different machine. The
   Pro/Ultra-share-a-code pattern IS evidenced on the TRACK side (R2527 vs R2527B) but not
   for Roller. Chris's find stands alone — needs a second source.
4. **A code merge CANNOT expand coverage** — tested, +0 models, +0 names. Codes are
   observable only through manuals already held, whose names are already counted. Only the
   registry can grow the number beyond the corpus.

---

## SCOPE-CREEP VERDICT (Chris: "my god we had some massive creep")

**The hunting list never wandered.** All 202 open names on the Dreame Hunting List
artifact are on the supported list — 202/202, zero off-list, 287 models behind them. The
fence held exactly.

What grew past its brief was the identity apparatus around it (CCC census, registry walks,
code taxonomy, the 2,133-article support-site walk). **The corpus and the open hunting list
overlap by SIX names** — 20 GB answered the easy half; the hard tail was never going to
come from PDFs, which is what the notes' own "reg codes matter more than manuals" already
said.

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

* **261 supported models (98 names) have a manual on disk and NO guide written.**
  This supersedes the old "22 of 26 platforms" line — that count predated the 741-model
  supported surface. No sourcing needed for any of them; see COVERAGE above. Two of the
  98 are ready to author right now from manuals Chris hand-delivered today:
  `aqua10_ultra_track` (R9528A, RLR81CE/-1) and `aqua10_ultra_roller` (R9535,
  RLH71DE/-1). Costs ~15 components, of which FOUR are new to the library:
  `fluffing_roller` (Roller only), `omnidirectional_wheel`, `retractable_legs`,
  `clean_water_tank`.
* **`BRAND_REGISTRARS` row — still the release, still gated.** See THE FRAMING above:
  #1707 open upstream. Chris's local patch makes it TESTABLE, not shippable.
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

⚠ **AND `git add` EXITS 1 ON A TRACKED `.claude/` FILE EVEN THOUGH IT SUCCEEDS.**
`.gitignore:83` carries `.claude/`, so git prints ignored-path advice and returns
non-zero regardless of the file already being tracked. `git add X && git commit ...`
therefore stages the file and SILENTLY SKIPS THE COMMIT. This is the most likely cause
of the tree corruption described at the top of this file. Run add and commit as
SEPARATE statements, and verify with:

```
git ls-tree -r HEAD --name-only | wc -l     # expect 1346
git ls-tree -r HEAD --name-only | grep -c '\.pdf$'   # expect 0
```

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
