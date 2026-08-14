# Development deltas — the current epoch's diff against the DR baseline

Per [00a — Documentation Epoch and Reconciliation Model](../00a-documentation-epoch-lifecycle.md):
the numbered docs in `docs/dev/` are the **Disaster-Recovery baseline** — the reconciled,
present-tense rebuild truth as of the last epoch close. Files in THIS directory are the
current epoch's **deltas** against that baseline.

Reading rule: read the relevant DR section first, then the matching delta here. A delta
overrides the baseline only where it explicitly says it differs. **No delta file for a
subsystem means the DR baseline is authoritative, full stop.**

Deltas may be painfully honest — hypotheses, competing interpretations, unadjudicated
evidence, known gaps. Their job is to preserve active engineering reasoning accurately
enough for the next epoch-closing audit to adjudicate it.

---

## Epoch ledger

| epoch | closed | closing operation |
|---|---|---|
| **Epoch 1** | **2026-08-08** (v2.0.0, the Phoenix Release — the audit closes the epoch, the release ships it) | The hostile-audit campaign — **516 corpus records / 484 verified findings / 22 killed**, collapsed into 33 accepted repair families (6 candidates rejected) and landed as 60 packets (figures from `corpus/audit-findings-canonical.jsonl`, the frozen corpus; the `464 / 67` pair quoted elsewhere is the AUDIT-2 *gate rebase* from `49e6e3b`, a different measure — do not mix them) + the DR reconciliation passes that established this baseline: batch 1 (`5940830` + siblings) and the 17-cluster adversarially-verified workflow pass (runs `wf_c3085752-b7b` + `wf_16fa0e1a-3f3`, applied 2026-08-06). Includes the rebuilt Phased Jobs (docs 06/30 reconciled + Opus-verified in `6a87c13`, per the §13 epoch-edge ruling) and the full `live:FONT-1` resolution (fix `ecbe77f`/`d3f81e6`, user-confirmed; typeface mechanism + drop-in fonts documented same-commit, styles-system §4/§4b). Provenance: the audit record (`.claude/notes/synthesis/`, closure ledgers, the postmortem corpus). |
| Epoch 2 | open | Accumulating. **19 commits since v2.0.0, of which 8 carry a DR delta** — enumerated below. The row previously read *"No known code-vs-DR deltas at open"*; that was written on 2026-08-09 at `3d04ff4f` and was already false by 2026-08-13, having gone unrevisited across sixteen further commits including a shipped release (2.0.1). Corrected rather than appended to, per [00 §5.4](../00-disaster-recovery-standard.md) — a superseded normative statement is edited in place. |

### Epoch 2 delta candidates — detail

**`live:STALL-PROV-1` — stall captures record no provenance, and the write overwrites.**
Opened 2026-08-09. **ANSWERED 2026-08-13 by `9659a7d5` — see D-8 below.** The entry is kept
because its reasoning predicted the shape the fix took (provenance recorded, never branched
on; the capture inherits it from the correlation context rather than knowing the concept
exists) and because the RETENTION half — a synthetic capture still overwrites the real one at
a stable path — is untouched and still open.

Note what kind of item this is, because it is the same shape as `RB-ERR-2` below: it is
**not a current divergence**. [04 §6a](../04-listeners.md) describes the write accurately and
deliberately — "one file per (vacuum, map), overwritten each time, so there is no
accumulation, no pruning, and a **stable path** an automation can hardcode" — and that
rationale is sound for the automation case it was written for. DR is authoritative and
correct today.

The gap is a consequence the baseline does not draw out. `dev_inject_stall` sets
`"injected": True` in the event payload (`services/stall_capture.py:136`) and **nothing
reads it** — one writer, zero readers, verified by grep. Combined with the overwrite, a
synthetic stall silently replaces a real capture and the resulting PNG is
byte-indistinguishable from one produced by a genuine fault. 04 §6a already explains why the
injector must run the real consumer path — "with the switch off, an injected stall still
fires the event and still reports anomalies, so 'no picture' localizes to the consumer" —
and `services.yaml` warns that an injected stall makes a clean run report as anomalous. What
neither states is that the *artifact* loses its provenance, and the artifact is the thing a
user forwards to their phone and reads as evidence.

Why this is delta-shaped rather than a hotfix. There are two fixes and they differ in what
they cost the baseline. Recording provenance is additive and changes no behaviour, so it
touches nothing DR promises. Changing *retention* — writing a synthetic capture beside the
real one rather than over it — breaks the "stable path an automation can hardcode" contract
that 04 §6a states explicitly, so it is a DR change and needs adjudicating rather than
patching.

Constraint carried from the design work (`PROTOCOL-semantic-flight-recorder.md` item 8):
**provenance may be recorded but must never be branched on.** `dev_inject_stall` exists so
every downstream consumer runs for real; gating the consumer on the caller would produce an
injector that exercises a path the real event never takes, which is an instrument that
certifies itself. If the fix lands as part of the semantic recorder, provenance rides the
correlation context and is inherited — the capture would carry `[synth]` without knowing the
concept exists. That is the preferred shape, but it does not need to wait for it.

**`live:RB-ERR-2` — CLOSED 2026-08-07, folded into Epoch 1 instead.** Chris pulled it into
the epoch-closing release: shipping "clean" meant shipping the capture, not documenting it
as a known gap while 48 keys and 816 translated strings sat unreachable for every Roborock
user. `error_tracking.message_is_code` + `_read_error_code_for_message()`; docs 22/23/29
reconciled in the same change, so DR describes the shipped system rather than carrying a
delta. The note below is kept as the reasoning that predicted its shape.

**Original entry —** Chain and fix shape:
`.claude/notes/synthesis/FINDING-roborock-error-code-carrier.md`; queued as
`DOC-PASS-TRIAGE.md` open item 2.

Note carefully what kind of item this is. It is **not** a current divergence — doc 23
was reconciled to describe what capture writes *today* (`code` is `int | None`), which
is accurate. The delta arrives when the fix lands: once the message-channel rising edge
carries the brand's error enum into `code`, doc 23's field type, the classification-seam
reachability statements, and 22/29's five Roborock `error_tracking` blocks all change
meaning at once. Until then DR is authoritative and correct, and the five declared
Roborock tables are correctly documented as declared-but-unreachable.

The fix is gated on an adapter declaration (Eufy's `error_message` carries prose — "Robot
is stuck" must never become a pseudo-code), so it is an adapter-contract change, not a
local patch. That makes it delta-shaped rather than hotfix-shaped.

---

## Epoch 2 — the delta set, v2.0.0..master (19 commits)

Enumerated 2026-08-13. **Eight entries, D-1..D-8, covering fifteen of the nineteen commits;
six of those entries owe an actual DR edit** (D-1, D-2, D-3, D-4, D-6, D-8 — D-5 and D-7 are
recorded as owing nothing). The remaining **four** commits have no DR surface and are listed at
the end, so the set is provably complete rather than merely sampled: an unexamined commit and a
clean one read identically.

> **⚠ READ THIS BEFORE APPLYING ANY ENTRY BELOW.** A delta is a *pending DR edit*, so it
> presumes the statement it edits is otherwise sound. **That presumption does not currently
> hold.** A full corpus walk against the frozen v2.0.0 source on 2026-08-13 returned **47 of
> 47 documents failing**, with 951 verified findings — 198 of them confidently wrong. So for
> most entries below, "the DR section that must change" is a section that also needs
> reconciling for reasons predating the delta. Apply these *with* that reconciliation, not
> before it. Findings are repo-local, not on this site: `.claude/notes/_dr_findings_wave*.json`.

**D-1 · `051ee7bc` — a second entity-resolution mechanism now exists, and nothing says how
the two interact.** Shipped in 2.0.1. When a declared companion entity id does not resolve in
the state machine, `adapters/entity_resolve.py` searches the vacuum's own config entry for a
domain+suffix match and remaps. **DR edit required in 21 and 22:** doc 22 already documents a
*different* registry fallback — per-role `token_sets` ("all-tokens-must-match") for dock
`action_buttons` and maintenance `reset_button`. There are now two rescue mechanisms with
different scopes, one declared per-role and one global and implicit, and no document states
which runs first. That is capability/adapter semantics, which [00 §2.2](../00-disaster-recovery-standard.md)
puts in DR.
*Known limit:* the rescue refuses when a suffix matches more than one sibling and breaks the
tie with `vacuum_object_id in candidate` — which can never succeed on the naming-mismatch
installs the rescue exists for. Live evidence on issue #49: `cleaning_area` is unrescuable
because `total_cleaning_area` also ends in `_cleaning_area`.

**D-2 · `41537981` — diagnostics reports REGISTERED beside EXISTS, and records `disabled`.**
Shipped in 2.0.1. The device census now walks with `include_disabled_entities=True` and stores
`disabled` per entity. **No DR doc covers diagnostics** — the numbered set runs 00–32 with no
diagnostics entry — so this is an *undocumented subsystem*, not a drifted one. Those need
different treatment: authoring, not reconciliation. Decide which before filing it as a gap.

**D-3 · `c10b0449` — a pasted theme import is scoped, and refusals that arrive as a throw are
surfaced.** Unreleased. **DR edit required in `frontend/theme-system.md`** (the import
contract) **and `frontend/backend-contract-and-data-shapes.md`** (how a service refusal
reaches the user when it arrives as an exception rather than a result envelope).

**D-4 · the mobile token editor — `77b04ae9` `2781d83f` `5b0fd100` `d948d55d` `73f96bdb`
`d788e443` `17ab24ab` `115175f8`.** Unreleased. Legitimate mid-feature churn under §13, which
explicitly protects exactly this. **But the flag is not a flag:** `src/renderers/theme.js`
declares `const MOBILE_TOKEN_EDITOR = true` while its call sites still read "TEST BUILD". Every
mobile user has it unconditionally and the code calls it provisional. That is a decision, not
a documentation task — shipped (drop the constant, reconcile `frontend/styles-system.md` and
`theme-system.md`, deferral ends) or genuinely a test build (say so, and it stays a delta). It
cannot remain both. `17ab24ab` additionally rewrote the layout gate to assert on right-edge
**bleed** rather than overflow, because `.evcc-shell` is `overflow:hidden` so breakage clips
instead of overflowing — a gate that changed what it measures is reconstruction-critical and
belongs in `frontend/render-harness.md`.

**D-5 · `133097a5` — §13-COMPLIANT, no delta owed.** It corrected
`reference/THEME_TOKEN_USAGE.md` in the same commit as the generator that produces it. Recorded
here only so the enumeration is complete. One residual: the *architectural* fact that token
names can be constructed at runtime and are therefore invisible to a `var()` scan is stated
only in a generated file's header.

**D-6 · `5779188e` — a saved run profile persists `strict_order`.** Issue #50. The run-profile
record gains a boolean; `start_run_profile` resolves stored-versus-explicit and forwards it to
dispatch. **DR edit required in 16** (the stored run-profile record shape, and the resolution
rule: explicit argument wins, absent means the stored flag decides). **Migration is inert by
construction** — `_enrich_saved_run_profile` reads it with `.get(..., False)`, so a profile
saved before the key existed dispatches exactly as before. That property is load-bearing and
pinned by `SO-2`; a rebuild that "simplifies" the default changes run duration, adds a dock
trip between rooms, and alters per-room learning attribution for every existing profile.

**D-7 · `de67758f` — two audit documents were published to the site.** `docs/audit-1-closeout.md`
and `docs/how-this-was-audited.md`. No DR statement changes; recorded because it establishes the
convention that a *curated* closeout may be public while the working record stays repo-local,
and that such a document NAMES its private companion in backticks rather than linking it (a link
would break `mkdocs --strict`).

**D-8 · `9659a7d5` — the semantic-receipts subsystem, answering `live:STALL-PROV-1`.**
A new `receipts/` package plus emission from the stall-capture path and provenance marking at
the injection point. **No DR doc covers it** — like D-2 this is authoring, not reconciliation,
and it is the larger of the two. Design lives in `PROTOCOL-semantic-flight-recorder.md` §6–§8
(repo-local). ⚠ **Its implementation has not been reviewed line by line.** 23 tests pass and it
traces to a decided design; that is the whole claim. The retention half of STALL-PROV-1 — a
synthetic capture overwrites a real one at a path automations hardcode — is **not** addressed
here and stays open, because changing retention breaks a contract [04 §6a](../04-listeners.md)
states explicitly and therefore needs adjudicating rather than patching.

### The four with no DR surface

`3d04ff4f` (this ledger's own STALL-PROV-1 entry) · `3e0dbfdd` (NOTICE attribution) ·
`de1d3018` (the 2.0.1 manifest bump) · `3558a083` (changelog).

That accounts for all nineteen: 15 under D-1..D-8, plus these 4.

---

## Epoch 1 reconciliation residue — CLOSED 2026-08-07

The original caveat here ("`docs/dev/frontend/` was not in the reconciliation pass") was
overtaken by events and has been replaced by the evidence-derived state below. The
workflow pass covered all three frontend clusters: 13 frontend docs were diffed and
Opus-verified (`fcb0c4d`, `b8b1a9d`, `c11954b`), and the font-era fixes updated their DR
sections same-commit (`ecbe77f`, `d3f81e6`, `cefc688`, `12e3b63`). Both previously
"absent" DR sections now exist and were verified in place: the **typeface mechanism**
(styles-system §4 chain + §4b drop-ins, TF-1..13 pinned) and the **fault-label seam**
(23-error-tracker §4.5 read-time tables incl. the `None`→raw-code rule, i18n-system
`faultLabel`, and the 22/25/29 adapter blocks — reconciled post-`RB-ERR-2`).

Coverage is claimed from evidence, not diffs — a clean doc produces no diff. The classes,
now all closed:

**Reconciled without a diff, verification recorded** (audit `clean[]` entries, Opus
spot-checked): `frontend/animal-svg` (no drift found, left untouched);
`frontend/floor-texture-map-view` (named sections verified; its remainder closed below).

**Verified since the pass:** `frontend/render-cycle` — read in full during the FONT-1
work, its cache-bust section exercised against `build-card.mjs`, and its one recorded
unverifiable claim (VIEW_ORDER-mismatch frame reset) since confirmed at `main.js:1602`.

**The former residual — RECONCILED 2026-08-07, closed:**

All three were walked statement-by-statement against source per
[00 §4–§5](../00-disaster-recovery-standard.md), source-only (no commit messages), and the
pass is gated by a green `mkdocs build --strict`.

| doc | evidence |
|---|---|
| `frontend/architecture-overview` | Verified against `main.js`, `render-cycle.js`, the four `*/index.js` combiners, `bindings/core.js`, `bindings/nav.js`, `controllers/learning-controller.js`, `renderers/mobile-shell.js`. Fixed **confidently-wrong**: "they reference `this.card._state`" — actions hold `this.hass`/`this.state` and have **no card reference** (the receiver asymmetry behind R2-BUG-1), now a four-constructor table; the controller's "room started/finished, job finished" → the real **five** subscriptions (`room_completed` + `run_incomplete` were missing) plus `loadRoomEstimates`; "all `hass.callService` calls live here" scoped to the panel card (the two standalone cards call `hass` directly); "everything renders into one shadow root" qualified with the two `document.body` portals. Corrected the data-flow diagram to the **diffed** `dataset.renderedHtml` swap (the reason `_on`/`_onAll` are idempotent). Add-a-panel recipe brought to current idiom: `VIEW_ORDER` is what pre-creates the view roots (and why `MAPPING_ARCHIVE` is `VIEWS`-only), i18n'd tab + empty-state labels instead of English literals, the `isViewAvailable` capability gate, the mobile-shell nav (`PRIMARY_MOBILE_TABS` / `OVERFLOW_MOBILE_TABS`) a panel is unreachable without, `_onAll` over raw `addEventListener`, and the real `refresh*()` / `_schedule*Refresh()` scheduler split. |
| `frontend/furnished-render` | Line-by-line against `mapping/map_source.py` `resolve_furnished_render`, the three `mapping_services.py` handlers + `upload_map_image` + `delete_custom_layout` + `_clear_layout_references_to_variant`, and card-side `renderers/map.js`, `state/map.js`, `bindings/map.js`, `styles/map.js`. Added the collapse-zone material: the full projection **return shape** and its three-part `None` gate, the uniform `{saved, reason}` service envelope + every refusal code, the per-field clamp/rounding table (`viewport.cx/cy` `[0,100]`, `zoom` `[0.05,20]` — the doc named only `scale`), the FURNIS-6 empty-`home_art` asymmetry, `upload_map_image`'s `layout_id`-scoped (not active-layout) contract incl. the post-write `layout_not_found` recheck, the `get_map_segments` fixed whitelist, the POSE-6 no-geometry-stamp limitation. Card side: the **`isFurnishedLayoutActive` triple gate** (`backdrop_source === "live"` — strictly narrower than the backend projection, previously undocumented), the `--editable` / `--passthrough` modifier classes (the latter load-bearing for compose placement), exact opacity values `0.45`/`0.02` as classes on the live `<img>` only, the natural-frame transform storage, the absolute (non-compounding) rotation-trim slider, the 2048-px pre-upload fit + auto-flip to `blend`, and the export button's real Content-Type-then-path extension pick. Qualified §5's zone-draw claim with the `frameUngrounded()` suppression. |
| `frontend/floor-texture-map-view` (remainder) | Everything past the previously-verified toggle/render chain, against `bindings/map.js`, `textures/{compositor,registry,resolver}.js`, `renderers/floor-texture-surface.js`, `state/theme.js`, `theme-tokens/floor-textures.js`, `scripts/{build-card,gen_floor_masks}`. Added the missing front half of the pipeline — the rid→material bridge via `rd.room_names` + `resolveFloorType`, the `"default"`/no-assets exclusion, the `S = clamp(round(1200/max(W,H)),1,4)` supersample the cache keys are already stated in. Pinned the composite formula to the real split (the compositor takes `(lum/255)×opacity`; the **caller** folds colour alpha) plus the layer-skip conditions, the `_floorMaskPending` guard and where the zero-luminance sentinel is actually written, the native-res `createPattern` fill and Rec. 601 luminance, `force-cache` + `70×attempt` backoff, and the `__ASSET_VER__` esbuild-define mechanism with its `"dev"` unbundled fallback. Fixed the stale "bare hex parser returns grey" line to the current `_parseCssColor` behaviour, and the "two render models" table to the **three** surfaces that read the registry (the SVG `<pattern>` path was missing) with the real three-level `-opacity-card` chain instead of a flat "~0.85". |

Four doc-vs-code disagreements where the **code** was the wrong side were surfaced rather
than papered over, filed as `R3-BUG-1..3` / `R3-STALE-1` in
`.claude/notes/synthesis/DOC-PASS-TRIAGE.md`, and **all four have since been fixed** — the
docs above describe the post-fix system, per the [00a §13](../00a-documentation-epoch-lifecycle.md)
same-commit rule:

| id | defect | resolution |
|---|---|---|
| `R3-BUG-1` | The panel card's service-failure and service-refusal toasts were inert in production — raised on `VacuumCardActions`, which owned neither `showToast` nor `t`, so `?.` swallowed every one and the whole `service_reasons.*` namespace was unreachable. Six specs passed against a hand-attached mock. | `VacuumCardActions` now takes the host as a third constructor arg and delegates `t` / `esc` / `showToast` to it, mirroring `VacuumCardBindings`. Five specs rebuilt onto the real class via a shared `_test-host.mjs`; `CSF-7` pins the delegation itself, `CSF-9` the escaping of a raw reason code at the sink. |
| `R3-BUG-2` (`FTX-VEIN-1`) | Marble's two vein layers ignored their opacity sliders on the map: `_resolveFloorOpacity` `parseFloat`ed a CSS `clamp(…)` string to `NaN` and fell back to `1`, compositing both veins at full strength while the card rendered 0.5 / 0.38. | Opacity now resolves the way colour already did — assigned to a real `opacity` property on the probe, computed value read back. Verified in Chromium (0.5 / 0.38 default, 0.8 / 0.68 with the master themed). Pinned by `FVO-1..6`. |
| `R3-BUG-3` | Four timer sources survived `disconnectedCallback`, and the `if (!this._state) return` guard that appeared to cover them is vacuous — teardown nulls no layer object — so a late timer ran a real service call and a full render on a detached card. | All four cancelled; the assigned-vs-cancelled handle sets now match 15 ≡ 15. |
| `R3-STALE-1` | `bindings/index.js` claimed "the DOM is fully replaced on each render" — the inverse of the real invariant, and so readable as licence for a raw `addEventListener`. | Rewritten to the diffed behaviour, naming `bindModalHostEvents` as the deliberate exception. |

**Open questions that hold dependent sections** (need Chris, tracked in
`DOC-PASS-TRIAGE.md`): `discovery.py` trigger semantics; Phased-Jobs doc depth — the §13
ruling makes the phased-job record schema DR material, which also decides whether the
drift-checker's queue-break exempt list gets retired by documenting those services.

Why this is logged in the ledger and not just a TODO: per
[00a §9](../00a-documentation-epoch-lifecycle.md), the documentation is part of the
measurement apparatus. An epoch row that overstates its own coverage tells the next
auditor that a stale region is trustworthy prose — which is the same failure class as a
confidently-wrong DR statement, one level up. The named residual is the honest baseline.
