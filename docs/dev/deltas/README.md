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
| **Epoch 1** | **2026-08-08** (v2.0.0, the Phoenix Release — the audit closes the epoch, the release ships it) | The hostile-audit campaign — **516 corpus records / 484 verified findings / 22 killed**, collapsed into 35 repair families and landed as 60 packets (figures from `corpus/audit-findings-canonical.jsonl`, the frozen corpus; the `464 / 67` pair quoted elsewhere is the AUDIT-2 *gate rebase* from `49e6e3b`, a different measure — do not mix them) + the DR reconciliation passes that established this baseline: batch 1 (`5940830` + siblings) and the 17-cluster adversarially-verified workflow pass (runs `wf_c3085752-b7b` + `wf_16fa0e1a-3f3`, applied 2026-08-06). Includes the rebuilt Phased Jobs (docs 06/30 reconciled + Opus-verified in `6a87c13`, per the §13 epoch-edge ruling) and the full `live:FONT-1` resolution (fix `ecbe77f`/`d3f81e6`, user-confirmed; typeface mechanism + drop-in fonts documented same-commit, styles-system §4/§4b). Provenance: the audit record (`.claude/notes/synthesis/`, closure ledgers, the postmortem corpus). |
| Epoch 2 | open | Accumulating. **No known code-vs-DR deltas at open** — every epoch-edge change landed with its DR statement in the same commit (§13). What remains open is *reconciliation residue*, listed below, not divergence. |

### Epoch 2 delta candidates — detail

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
