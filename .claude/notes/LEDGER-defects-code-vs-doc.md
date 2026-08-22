# Defect ledger — CODE vs DOC

## ⟵ DISPOSITION PASS 2026-08-21 — READ THIS BEFORE SCOPING ANYTHING FROM THIS FILE

**Every one of the 84 entries below was re-judged against the TREE, not against this file.**
Eleven were already done and this ledger never recorded it — three of those were closed the
same day they were re-read. That is the failure mode this pass exists to end: the ledger is an
append-only DISCOVERY log, it records findings and never records outcomes, so *finish the
backlog* had no finish line anyone could compute.

**The token on each entry is the answer. `grep -c '\[OPEN\]'` is the count.**

| token | n | means |
|---|---:|---|
| `[OPEN]` | 62 | still present in the tree exactly as described |
| `[OPEN-DRIFTED]` | 4 | real, but **the text below it is WRONG** — a corrected-mechanism line follows the entry |
| `[NEEDS-RULING]` | 2 | blocked on a decision, not on work |
| `[FIXED]` | 3 | gone, **and** a named test goes red if it returns |
| `[FIXED-UNPROVEN]` | 9 | gone, but nothing would notice if it came back |
| `[ACCEPTED]` | 1 | **a real defect, ruled not worth fixing, and stated AT THE SITE** — not a backlog item |
| `[NOT-A-DEFECT]` | 1 | verified by-design or explicitly accepted |
| `[SUPERSEDED]` | 1 | overtaken by another entry or a redesign |
| `[UNVERIFIABLE]` | 1 | undecidable from the repo alone |

**Actual remaining work: 66 entries** — 18 user-visible, 32 trivial, 30 small, 4 medium, **0 large.** (C17 and C15 were closed after the pass ran; their rows are current.)

⚠ **A `[FIXED]` CALL WAS OVERTURNED BY THE ADVERSARIAL PASS AND THAT IS WHY THERE WAS ONE.**
Every close was independently attacked, defaulting to overturning when the evidence could not
be reproduced — because the direction is asymmetric. A wrongly-OPEN row costs a re-read; a
wrongly-CLOSED row means known work is dropped and never looked at again. C17 was called FIXED
and was not: the fix had partnered the numerators and left the denominators, so the same
substitution still ran in the mirror direction. Closed properly in `2c008cdd`.

⚠ **DO NOT TRUST A STATED MECHANISM IN THIS FILE WITHOUT RE-READING THE SITE.** Across the
verification tranches the ledger's stated mechanism was wrong more often than it was right,
and wrong in ways that would misdirect a repair — C40's names a helper the actual fix
deliberately avoided, because putting the check there stops every stored profile from loading.
The findings were sound; the explanations rotted. Line numbers have drifted by dozens: navigate
by SYMBOL, never by the cited line.

---

RULING 2026-08-20 (Chris): **code defects must be found and fixed before the authoritative
docs are written.** Doc defects are fixable at doc-build time and gate nothing.

Consequence for sequencing: a doc written over a known-broken code path documents either the
bug or the intent, and goes stale the moment the code is fixed. So the code list below is a
GATE on the doc-rewrite phase, not a parallel track.

Everything here was found as a side effect of the invariant harvest (batches 1–2, 12 files).
It is NOT a scoped code audit — see "Coverage" at the bottom.

Status: nothing fixed. Nothing written to `00b-h`.

---

## CODE — gates the doc rewrite

| # | Site | Defect | Severity |
|---|---|---|---|
| C1 | `button.py:84` | Entity deletion by `unique_id.startswith(prefix)` then `registry.async_remove()`. The other three platforms (`switch`, `number`, `sensor`) all route through `entity_belongs_to`; `switch.py:72` carries the comment "never a unique_id prefix". `button.py` has neither the import nor the `IN4CW5Y9` token. Has condition 1 (complement of a forward-built set), lacks condition 2 (the remainder guard at `entity_helpers.py:180`). Structural cause: `EufyVacuumSavedRunProfileButton` copied the SN-4 half of the pattern and not the ownership half, so it has no public `vacuum_entity_id`/`map_id` and *cannot* call `entity_belongs_to`. | HIGH |
| C2 | `room_entities.py:103`, `:133` | Both `apply_room_profile` and `update_room_fields` are called with the return discarded, then `async_save()` + `async_write_ha_state()` run unconditionally. Callees return `{"ok": False, "error": "room_not_found"}` (`manager.py:1877`), `"no_dock_room"`, `"invalid_access_graph"`, `"profile_not_found"`. Reachable: toggle a room deleted between state write and press — user sees a successful toggle. Shape of `IN5BRA39` / `INT62M7A`. | HIGH |
| C3 | `user_fonts.py:168-170` | `except Exception` → `return set(), False`. Caller (`:303`) sees a non-None value → `status = "verified"`. An unreadable font is catalogued as a completed verification. Sharpest case: two-face font, face A parses, face B corrupt → `cpsA & set()` → `verified`, `locales: []`. Directly collapses the distinction `:165-166` says must not be conflated. | HIGH |
| C4 | `user_fonts.py:162` | `except ImportError` wraps the whole parse block, so ANY ImportError from a lazily-imported fontTools table module returns None and sets `fonttools_missing = True` (`:296`) — firing an INFO line asserting fontTools is not installed when it is. The branch logs nothing itself, so the real cause is lost and only the asserted one survives. | MED |
| C5 | `rooms/vocabulary_migration.py:135` vs `:171` | Predicate gap. `_unadjudicated_targets` asks "is the block a non-empty dict?"; the planner asks "did `declared_profile_fields` return anything?". A non-empty block declaring no profile fields is skipped unjudged by the planner AND counted adjudicated by the latch — the one shot burns having judged nothing. Same species as the rule stated at `:70`. | MED |
| C6 | `receipts` gate | `scripts/check_receipts.py` captures station / outcome / prov as VALUES but facts only as a COUNT (`:63-64`, `max(0, len(args) - 4)`). `DECLINE_REASONS` and `READABILITY` ride as positional facts, so the gate cannot see them. Probe-proven with an ablation (a derived station correctly yields `None`, so the probe can bite). Symptom already in tree: `"no_map"` declared, emitted by nothing, invisible. | MED |
| C7 | `.github/workflows/tests.yml` | `check_receipts.py` is not run by CI or any test — `tests.yml:69` runs only `check_generated_docs.py`. The gate is author-time-and-remembered. A gate you added is not one you have run. | MED |
| C8 | `receipts/__init__.py:109` | Station `"core"` is misaligned by construction: the hub is `core/manager.py`, so the gate derives `core.manager` and would REFUSE `"core"` the first time it speaks. Three of seven declared stations never emit (`core`, `pose_store`, `mapping.stall_capture_render`) and the gate has no dead-station check (it has one for catalog keys and outcomes). | LOW/latent |
| C9 | `room_entities.py:156-159` | Generic merge writes `current` straight into `rooms[room_key]`, bypassing `_finalize_room_update` and so the carpet/mop protection rules. `floor_type` is a protection input (`profiles/manager.py:141-147`) and is NOT in `managed_field_names`. No caller writes `floor_type` this way today — latent, but that is the input that makes it bite. | LOW/latent |
| C10 | `rooms/vocabulary_migration.py` + `__init__.py:537` | A run that latches with zero changes writes nothing (`if _migration["changes"] or ...: await manager.async_save()`), so `"latched": True` is not evidence the flag survived a restart — it rides the next unrelated save. Fails safe (harmless re-run). | LOW |
| C11 | `adapters/roborock/vocabulary.py:95` | `MOP_MODE_OPTIONS` — zero consumers anywhere. Never placed in the `vocabulary` block, so the card cannot see it either. Dead constant; its comment claims it is "kept here for the card". Decision needed: wire or delete. | LOW ⟵ **RESOLVED 2026-08-21 as LEAVE-WITH-A-NOTE (Chris).** No code change: not deleted, not wired. A note now sits above `MOP_MODE_OPTIONS` recording that it is callerless BY DESIGN and verified so across twelve declaration surfaces, that `git log -S` returns ONE commit (callerless SINCE BIRTH — never wired, not unwired), that the deferral is stated twice independently, and — the part that matters — that **the real risk is the NEIGHBOUR**: a block-level tidy of "the unused option lists in this file" takes `PATH_TYPE_OPTIONS` with it, which is live. Wiring is five layers, starting with a schema that rejects the key today. |
| C12 | `services/stall_capture.py:82` | `manager.data.setdefault("vacuums", {})` mutates before the authorization decision; the canonical `is_managed_vacuum` is non-mutating. Leaves `data["vacuums"] = {}` on the refusal path. Also drops the `translation_key="unmanaged_vacuum"` the canonical refusal carries (`INNPA4ZV`). Only service module in the package that hand-rolls the check. | LOW |
| C13 — **ACCEPTED, NOT A DEFECT (Chris, 2026-08-21). No code change. Remedy is a DOC LINE, and it does NOT gate the doc rewrite — it is an item FOR it.** RULING: *"we're going to log that as an accepted non... if somebody tries to make an impossible shape, we can note about it — all shapes are reduced to 4-point shapes."* **THE FRAMING THAT IS ACTUALLY RIGHT (Chris, 2026-08-21): a door that opens into a NARROW HALLWAY. We do not need a map from the door to the end of the hall.** The protection here is STRUCTURAL and DOWNSTREAM, not documentary: both shipped brands take exactly 4 points, and dispatch reduces every stored shape to its bbox before the wire. A permissive door costs nothing while the hallway past it is narrow. The doc line is a courtesy to the reader, NOT the safeguard — do not record it as the safeguard. ⚠ **REOPENING CONDITION, and it is not hypothetical — it is the exact thing the polygon storage was left open FOR: the day any brand declares a zone shape richer than a 4-point rect, the hallway widens and this becomes a REAL bad-input problem requiring validation.** At that moment `CREATE_SAVED_ZONE_SCHEMA`'s `Length(min=3)` stops being harmless, because a malformed polygon can then actually reach a device instead of being flattened. PLACEMENT OF THE TRIGGER MATTERS MORE THAN THIS LEDGER LINE: nobody reads a ledger at the moment they add a brand. It belongs as an inline note at the WIDENING SITE — the adapter `dispatch` contract in `config_schema.py` beside `zone_command`/`zone_coords`, where a `zone_shape` key would be added. The file already uses exactly this pattern one field over: the `kind` allow-list carries *"widen this allow-list only alongside a real dispatch-side consumer for the new kind"*. Same shape, same file, proven. NOT APPLIED — a code comment is trivial but unrequested. THE COST REASONING, which is secondary to the above and must not be mistaken for the whole of it: *"the only reason I'm willing to call that a non-defect is the amount of effort it takes to generate an incorrect shape THAT IS THEN THROWN AWAY. It's easier to tell somebody don't make the effort than for us to make the effort to prevent it."* ⚠ **THE LOAD-BEARING CLAUSE IS "THEN THROWN AWAY", NOT "HARD TO REACH".** Reachability alone is NOT grounds to accept a defect here — SETUP-REJ-2 was also hard to reach and nearly deleted a real room. What makes this one acceptable is that the malformed input is DISCARDED rather than persisted or dispatched: the bbox is computed fresh at dispatch, the polygon is never acted on, nothing downstream trusts it. Flip that clause and the calculus flips — if a bad shape were STORED as authoritative or reached the device, cost-of-prevention would stop being the deciding factor. This is also NOT in tension with "rarely-used is not OK to half-build": that governs FEATURES, this governs a discarded bad INPUT. So the reduction stops being a silent downgrade by being STATED: the documented contract is that a saved zone is stored as a polygon and **every shape is reduced to its 4-point bounding rectangle at dispatch**, because that is the only shape either brand's command can represent (Eufy `zone_clean` `[[x0,y0,x1,y1],...]`, Roborock `app_zoned_clean` `[[x0,y0,x1,y1,repeat],...]`). Polygon storage is deliberately left open for a future brand that could take a richer shape; the `zone_shape` adapter-contract seam remains UNBUILT and is not required until such a brand exists. DOC TARGET when the corpus is rebuilt: wherever `create_saved_zone` and the saved-zone clean handlers are described — one sentence, stating the reduction as behaviour rather than leaving a reader to infer their polygon survives. | `mapping/mapping_services.py:371` (schema), `:2960-2975` + the single-zone twin (bbox reduction), `dispatch/zone_dispatch.py` | **Saved-zone storage accepts a shape no brand can dispatch, and degrades it SILENTLY.** `CREATE_SAVED_ZONE_SCHEMA` takes `vol.All([_SAVED_ZONE_POINT], vol.Length(min=3))` — any polygon of 3+ points. Both shipped brands are rectangle-only: Eufy `zone_clean` `{zones:[[x0,y0,x1,y1],...]}`, Roborock `app_zoned_clean` `[[x0,y0,x1,y1,repeat],...]`. Both clean handlers reduce the stored polygon to its bbox (`[min(xs),min(ys),max(xs),max(ys)]`) and dispatch that, so a non-rectangular zone cleans its notch with no signal to the caller. ⚠ This CONTRADICTS the dispatch module's own stated contract — `zone_dispatch.py:11-15` declares **"refuse rather than mis-dispatch"** and honours it for the affine fit (returns `None`, caller refuses); the bbox reduction does the opposite on the same axis. ⚠ SAME BUG, SAME SCHEMA, ALREADY FIXED ONE FIELD OVER: the `kind` key three lines below carries `RP-032/RF-28 (INJSETB0) (A6-ZONE-C-7)` — *"an unconstrained string (e.g. `no_go`) got persisted and was then dispatched as a clean anyway. Restrict to what dispatch actually honors"*. `geometry` has the identical storage-wider-than-dispatch mismatch and was not narrowed. ⚠ AND THE CONTRACT HAS NO SEAM: the adapter `dispatch` block declares `zone_command`, `zone_coords`, `zone_max`, `zone_max_side_m`, `zone_min_side_m`, `zone_max_area_m2`, `zone_min_area_m2` — and NO shape. A brand can declare where its coordinates live and how big a zone may be, but not what shape it accepts. The precedent is `config_schema.py:912` `room_list_shape`, whose own text says *"SHAPE … declared independently of the SOURCE … conflated until 2026-08-07"* — that conflation was fixed for room lists and still stands for zones. REACHABILITY (Chris, 2026-08-21): **no UI path reaches it.** `src/bindings/saved-zones.js:110` builds geometry via `rectToPolygon` (`zone-geometry.js`), which returns exactly 4 corners or `null`, and the card has no polygon editor. Reachable ONLY by a hand-crafted `create_saved_zone` service call from an automation, script or dev-tools. FIX (not applied — schema narrowing on a user-data service is stop-and-approve): either `vol.Length(min=4, max=4)` plus a rect check, or — better, and matches the expansion rule — add `zone_shape` to the adapter contract with both brands declaring `"rect"`, keep the polygon storage for a future brand, and make dispatch REFUSE an undeclared shape instead of bbox-ing it. ⚠ NO DEVICE-FACING EXPOSURE — established 2026-08-21 by reading, NOT by dispatching. Two independent guards reject a non-4-element zone before the wire: `dispatch/manager.py:178` `if not isinstance(_z,(list,tuple)) or len(_z)!=4: raise ValueError("zone must be [x0,y0,x1,y1], got ...")`, and `zone_dispatch.normalized_rects_to_mm` returns `None` on the same test (caller must then refuse). **Neither ever fires from the saved-zone path**, because the upstream bbox reduction always yields exactly four numbers — so a 6-point L never arrives as an L, it arrives as its bounding rect and cleans. The failure is a SILENT GEOMETRIC DOWNGRADE, not a malformed command, not a crash, and not a robot-safety case. The guards are sound; they simply protect a different input (a direct malformed `dispatch_zone_clean` call). Chris's triage, and it is the right one: reaching this at all requires doing the coordinate transform mentally, then hand-authoring a DevTools/automation call for a shape no device can represent. | LOW — contract tidiness. Not a live user-facing bug, no device exposure. Value is the PATTERN (3rd instance of storage-wider-than-dispatch in one schema), not the defect |

### Coverage gap (code-class work, not a defect)
- No test in `tests/` invokes either `stall_capture` service handler. Both guards (`:83`, `:114`) are unablated, so `INKV8ZQD`'s 2026-08-18 ablation table does not reach this hand-rolled copy.
- Only 2 of the 6 `receipts` decline sites are test-asserted. `no_runtime`, `no_room`, `unusable`, `no_pillow` could each go silent with the suite green AND the gate green.

---

## DOC — fixable at build time, gates nothing

| # | Site | Defect |
|---|---|---|
| D1 | `services.yaml:3796-3799` (+ `docs/dev/deltas/README.md`, `services/stall_capture.py:31-33`) | **User-facing.** Claims an injected stall "will be recorded as having stalled when it did not, and the card's snapshot will say so. Do not call this on a run whose learning data you care about." The dependency runs the other way: `detect_run_anomalies` FIRES `EVENT_STALL_DETECTED` (`active_job.py:1186`) and never subscribes; the event has exactly one subscriber (`listeners/stall_capture.py:412`). The service cannot pollute learning data. This text scares users off a maintainer tool for no reason. |
| D2 | `adapters/roborock/vocabulary.py:47` | "the framework never reads these" — refuted by `active_job.py:1892` (`vocabulary.get(options_key)` filtering at dispatch), `vocabulary_migration.py:167`, `config_schema.py:474-545`. The same file contradicts it at `:60-64` and `:108`. Consequence of believing it: dropping an entry looks card-only and safe, but silently stops that setting reaching the robot — the exact bug narrated at `adapter.py:897`. |
| D3 | `adapters/registry.py:462-463` | "The framework merges it over the in-code defaults (`resolve_profile_catalog`), so a partial block is fine." `resolve_profile_catalog`'s own docstring opens **"There is NO framework default"** and explains the merge was removed because a brand inherited `"Max"` and applied no suction. The comment names the function that refutes it. Tells a porter a partial block is safe when it now resolves EMPTY — `IN40W49E`'s exact failure. |
| D4 | `room_entities.py:145` | Premise false: "update_room_fields only understands the managed subset above". `manager.py:1847-1851` shows the callee also accepts `color`, `is_dock_room`, `is_transition`, `grants_access_to`, `rules` — `color` being the comment's own example of an unmanaged field. `managed_field_names` (`:113-121`) is a hand-copy drifted from the callee signature. True sentence: "this call site only PASSES the managed subset." |
| D5 | `rooms/vocabulary_migration.py:115-120` | Overstates: claims `_validate_room_profiles` rejects an adapter whose `room_profiles` is missing/empty. It only REPORTS; `register_adapter_config` hard-raises only for `source == "config"` (`INYA5T84`'s deliberate asymmetry). A code-sourced adapter missing the block registers anyway. |
| D6 | `receipts/__init__.py:45-48` | "these are tuples, and the gate rejects anything outside them" — true for `STATIONS`/`OUTCOMES`/`PROVENANCE`, **false for the two it sits directly above** (`DECLINE_REASONS`, `READABILITY`). **Coupled to C6** — which way C6 is fixed determines the words. |
| D7 | `user_fonts.py:148-150` | Docstring: "A present-but-unreadable face returns an empty set — which correctly verifies as covering nothing." `:165-166`, same function: "This is 'cannot verify', never 'covers nothing': the two verdicts must not be conflated." **Coupled to C3.** |
| D8 | `tests/unit/test_receipts_criterion.py:59-60` + `PROTOCOL-semantic-flight-recorder.md:957-961` | ":59-60 says "everything it causes inherits the marker"; `:83-84` in the SAME test asserts the opposite ("provenance is not inherited forward"), and the code agrees with `:83`. The spec item 8 it derives from still states the reversed rule, while the module docstring at `receipts/__init__.py:3-5` still instructs "Read item 8 before changing anything here." |
| D9 | `docs/dev/frontend/styles-system.md:204-209` (+ `.claude/notes/synthesis/DOC-PASS-TRIAGE.md:170-171`) | Says the requirement is `fonttools[woff2]`; `manifest.json` declares `fonttools>=4.47.0` + `brotli>=1.1.0`. The source comment is right and the doc is stale — the exact drift `user_fonts.py:165-166` exists to prevent. |

**D6 and D7 are not independently fixable.** They describe behaviour that is itself defective (C6, C3). Writing authoritative words for them requires the code decision first — they are gated, same as the code list.

---

## Coverage — read this before treating the code list as complete

Per `f/coverage_from_scopes_not_findings`: these 12 code defects came from reading 12 files
chosen because they had *invariant candidates*, not because they were risky. An unaudited
subsystem yields zero findings and reads identically to a clean one.

Files read so far (12 of 29 .py with candidates; 29 of ~180 in the package):
batch 1 (6, test batch) + batch 2: `adapters/roborock/vocabulary.py`, `receipts/__init__.py`,
`rooms/vocabulary_migration.py`, `services/stall_capture.py`, `room_entities.py`,
`user_fonts.py`.

So the honest statement is: **the code list is a floor, not a total.** If code-complete is the
gate on doc work, the gate needs a sweep scoped by subsystem, not the residue of a doc harvest.

---

# BATCH 3 — 6 files, 20 rows (2026-08-20). Every item verified by me against the tree.

## DOMINANT SHAPE: partial guards — 4 independent hits in 6 files
Four agents, no visibility of each other, same shape. `f/partial_guard_blind_spot` is the MODAL
defect here, not an occasional one.

- [OPEN] **C13 `core/error_tracker.py:326` `_safe_int`** — the `int()` guard fires at COMPARISON
  (`_code_key`); `_safe_int` is `try: int(value)` with no bool/float check, at `:892` on the
  CAPTURE path. `int(3.7)` → `3` is minted when the code is read off the entity. Needs an
  upstream entity exposing `error_code` as float/bool: mechanism certain, occurrence unobserved.
  ⟵ **DISPOSITION 2026-08-21 — OPEN.** Error codes are captured through an unguarded int() while the bool/float guard lives only on the comparison path.
- [OPEN] **C14 `core/capabilities.py:314-318`** — the ROLE override path checks existence and records
  `REASON_OVERRIDE_UNRESOLVED` (`:900-902`). The MAINTENANCE path does `sources[component] =
  chosen; continue` — no check, no reason. A stale maintenance override PINS A DEAD ID, the exact
  outcome `:70` says is not on offer. Only the precedence half of `live:ENT-7` was carried across.
  Reachable: `services/setup.py:281` takes `role` as free text.
  ⟵ **DISPOSITION 2026-08-21 — OPEN.** The maintenance override path accepts a user-chosen entity id with no existence check and records no reason, so a stale override pins a dead id — the outcome the ROLE path exists to prevent.
- [ACCEPTED] **C15 `battery/manager.py:806`** — `advance_anchor` guards two of three anchor fields;
  `record["last_charging"]` is written OUTSIDE the block and `_update_session` runs before it, so
  an out-of-order sample can still open or close a charge session. `_proof_closing_batch.py:81`
  knew; the source comment never said.
  ⟵ **DISPOSITION 2026-08-21 — ACCEPTED. Real, verified by execution, deliberately NOT fixed
  (`5351d933`, doc-only).** The anchor is three fields and the guard holds two: `_update_session`
  has already run when `if advance_anchor:` is reached, and `last_charging` is written below it
  unconditionally — so an out-of-order sample still opens or closes a charge session with its
  own stale ts and level, which can leave a `session_history_recent` entry and a sessions.csv
  row whose `end_ts` precedes its `start_ts`. Nothing repairs those.
  **⚠ THE ARCHIVE DECIDED IT, NOT THE ARGUMENT.** `elapsed_sec <= 0` needs the wall clock to step
  BACKWARDS — `ts` is minted per-sample from `datetime.now()` and never inherited from a state
  object, so co-timed samples cannot collide. 104 vacuum-days of `samples.jsonl` across alfred
  and ivy hold no such step; 387 archived sessions hold no inverted row. Mechanism certain,
  occurrence unobserved.
  **⚠ IF ANYONE EVER CLOSES IT, BOTH STATEMENTS MOVE TOGETHER.** `_update_session` alone makes
  each repeated stale sample RE-OPEN the session; `last_charging` alone makes the next genuine
  sample read a false transition and RESTART a live one. Either half is worse than neither. The
  site now says all of this — read the comment, not this row.
  **⚠ THE CITED LINE WAS CORRECT WHEN WRITTEN** and is stale by 11 lines (now `:808` + `:817`).
  Navigate by symbol.
- [OPEN] **C16 `mapping/stall_capture_render.py:323`** — `_norm_to_px` filters NaN and NOT inf.
  `seg = inf` → `while d < seg` (`:189`) never terminates: **a HANG, on an executor thread, on a
  job-lifecycle path.** `pose_store.read_range:214` uses bare `json.loads`, which accepts the
  non-standard `Infinity` literal (verified). Proven by ablation.

  ⟵ **DISPOSITION 2026-08-21 — OPEN.** `_norm_to_px` still rejects NaN and passes inf, and I reproduced the infinite loop — the call did not return in 30 s.
## CODE — new
- [FIXED] **C17 `battery/manager.py:1442-1446` — docstring asserts the INVERSE of its code.** Says only
  non-null inputs contribute to the count; `bucket["count"] += 1` is the FIRST line, unconditional,
  and the means never use `count` (they are `d_sum / t_sum`). `battery_used_pct=12,
  duration_min=None` adds 12 to the numerator and 0 to the denominator, INFLATING
  `drain_per_min_mean`. `battery/job_metrics.py:66-73` documents partial dicts by design.
  ⟵ **DISPOSITION 2026-08-21 — FIXED (`1e2ba0d7` then `2c008cdd`; it took two goes).**
  **⚠ THE FIRST FIX WAS HALF A FIX AND ITS OWN TESTS COULD NOT SEE IT.** `1e2ba0d7` partnered
  the NUMERATORS and left `duration_min_sum` / `area_m2_sum` accumulating on their own, so the
  substitution still ran in the mirror direction: a job with a duration and NO drain grew the
  denominator alone and DEFLATED the mean, where the original defect INFLATED it. `[BM-5b]` and
  `[BM-5c]` both supply a drain and vary the other field, so both pass against the half-fix —
  proven by ablation, which fails `[BM-5d]` and nothing else. Closed in `2c008cdd`; the bias
  left in records written before the pairing is DOCUMENTED, not migrated (docs §9.2), and
  `eufy_vacuum.rebuild_learning_stats` is the repair.
  **⚠ AN EARLIER PASS CALLED THIS FIXED AND WAS OVERTURNED:** The fix partnered the NUMERATORS only. `duration_min_sum` and `area_m2_sum` still accumulate on their own presence with no drain check: `if duration is not None: bucket["duration_min_sum"] = ... + float(duration)` and the identical area line, both above the `# THE PAIRING` comment. So the defect's own stated class — a ratio whose top and bottom count different jobs — survives intact in the mirror direction: a job with a measured duration/area but NO drain adds to the denominator and nothing to…
- [FIXED-UNPROVEN] **C18 — FIXED 2026-08-21.** `_int_set` and `_exact_int` deleted from `core/error_tracker.py` (24 lines). Confirmed dead by two independent routes: this ledger's own wave-3 finding (*"`_int_set` (:250) has no callers anywhere in the tree"*) and a fresh reachability trace — `_exact_int`'s only live reference was inside `_int_set`, and `_int_set` had none at all. No dynamic access (`et._exact_int` / `error_tracker._exact_int`: zero hits), no `__all__`, no star imports. The live path is `_code_key` -> `_code_set` (14 references), which superseded them under `live:RB-ERR-1` so core could carry ENUM-STRING codes; the int-only pair was left behind. Both int guards it documented survive verbatim in `_code_key`'s docstring — *"Both int guards are preserved because both are load-bearing"* — so nothing was lost with the deletion. Suite green.
  only occurrence in the tree is its own `def`. `coverage.json`: 252-255 and 314-323 never execute
  in a module at 90%. Fix is deletion.
  ⟵ **DISPOSITION 2026-08-21 — FIXED-UNPROVEN.** The dead int-coercion island is genuinely deleted, but nothing in the repo would notice if it came back.
- [FIXED-UNPROVEN] **C19 `adapters/eufy/vocabulary.py:57`** — `HA_ACTIVE_VACUUM_STATES` imported and never ⟵ **FIXED 2026-08-21 (reading A, Chris's ruling: "the stronger proof is there").** Deleted `HA_ACTIVE_VACUUM_STATES` from `adapters/eufy/vocabulary.py` and its import from `adapters/eufy/adapter.py`; the dangling cross-reference above `ACTIVE_RUN_TASK_STATES` now states the boundary instead of pointing at a deleted symbol. **THE PROOF THAT SETTLED IT:** `git log -S` returns ONE commit — the constant was born with all four values marked `[HA standard]` and has NEVER held a `[Eufy]` value, despite its own comment providing for them. A brand file that has never contained a brand value is a category error. Corroborated three times in code: `job_monitor.py:26` ("not brand-specific firmware strings... regardless of brand"), `job_monitor.py:174` (`active_vacuum_states` defaults to the platform standard while the three genuinely brand-specific sets "must pass values from the adapter registry"), and `core/manager.py:162` ("defined by the HA vacuum integration, not by any specific brand"). ⚠ THE WIRING DIRECTION WAS REJECTED FOR A REASON WORTH KEEPING: declaring it as `active_vacuum_states` would have made a platform-universal concept brand-supplied — behaviour-identical, boundary-INVERTED — and left a trap where a future editor adds a state to a set core never consults and assumes it took effect.
  referenced; core uses its own copy. **Editing this set does nothing at all.**
  ⟵ **DISPOSITION 2026-08-21 — FIXED-UNPROVEN.** The dead HA_ACTIVE_VACUUM_STATES is gone from the Eufy brand file and lives once in const.py — but nothing would catch it coming back.
- [OPEN] **C20 `adapters/eufy/vocabulary.py:564`** — `_exact_error_code` has NO production caller; the ⟵ **DISPOSITION SETTLED 2026-08-21, after TWO wrong answers of mine.** The observation always stood (no production caller). ⚠ FIRST WRONG ANSWER: I queued them for deletion beside the dead core island (C18). ⚠ SECOND WRONG ANSWER: told they related to upstream error work, I reclassified them as PENDING on **jeppesens/eufy-clean PR #161, "feat: capture and persist the full ErrorCode proto", opened 2026-07-26, still OPEN.** Until it lands the fork does not surface the fault detail these tables classify, so a caller would classify data that never arrives. Built ahead of the source deliberately — the tables and their reasoning were authored while the codes were in hand, which is the only cheap moment to write that reasoning down. ⚠ **NEAR MISS, AND THE REASON THIS ENTRY NOW CARRIES A WARNING:** a reachability sweep the same day queued these three for deletion beside the genuinely dead int island (C18, correctly removed). **The two cases are INDISTINGUISHABLE to any tool** — identical zero callers, identical green suite when broken. Only the upstream PR separates them, and nothing in the code said so. A banner now sits above the functions in `adapters/eufy/vocabulary.py` stating the dependency, because a ledger is not read at the moment someone runs a dead-code sweep. **GENERAL RULE THIS EARNS: "no callers" is not a disposition. Callerless code is either DEAD or PENDING, the difference lives outside the repo, and the pending case must say so AT THE SITE or it will be deleted by someone doing good work.** — and that was also wrong. **THE TRUTH: the TABLES are LIVE and the FUNCTIONS are SUPERSEDED.** Every set (`EUFY_DOCK_SOURCED_ERROR_CODES` etc.) is wired into core by the adapter DECLARATION at `adapters/eufy/adapter.py` and read generically by `core.error_tracker.error_source_for_code`. The adapter's own comment records the history: *"eufy_error_source() had built these tables and had ZERO callers until this declaration wired them."* The function built the tables, the declaration wired the tables, the function stayed. **`adapters/roborock/vocabulary.py` is the proof and the correct pattern — same five table kinds, no equivalent functions.** #161 is real and matters (today the fork reads only `warn[0]`; #161 delivers `error[]`/`warn[]`/history to the Error Message sensor) but that data flows into CORE's lookup via the declared tables — MORE CODES TO CLASSIFY, SAME CLASSIFIER. It creates no caller for these functions. ⚠ **THE REAL HAZARD, which neither wrong answer captured: the live tables and the dead functions SHARE A FILE AND A SUBJECT.** A sweep that deletes "the dead error stuff here" takes fault classification for every Eufy vacuum with it. The banner in the file now names which half is which. DISPOSITION: functions deletable on their own merits, with their tests, which test only them. Not urgent. **Never by a sweep.** ⚠ **METHOD NOTE — I got this wrong twice in opposite directions and neither error was detectable from the repo alone.** "No callers" told me DEAD. A pointer to an upstream PR told me PENDING. Only reading the adapter DECLARATION — a different file, wiring by data rather than by call — gave the answer. Callerless code has at least three states (dead / pending / superseded-but-load-bearing-neighbours) and the distinguishing evidence is routinely NOT at the call site.
  adapter consumes the SETS. Rule right, site powerless.
  ⟵ **DISPOSITION 2026-08-21 — OPEN.** eufy_error_source / eufy_error_invalidates_cleaning / _exact_error_code are still callerless in the tree; only the warning banner landed, not the deletion.
  **⚠ THE LEDGER'S MECHANISM IS WRONG — repair from THIS, not from the text above:** Ledger cites `:564`; `_exact_error_code` is now at `:602`. Also note the entry line is internally inconsistent after two rounds of appending — the appended prose ends "the TABLES are LIVE and the FUNCTIONS are SUPERSEDED", while the entry's original tail two lines still read "adapter consumes the SETS. Rule right, site powerless." Both happen to agree with the tree, but a reader hitting the tail first gets the pre-correction framing.
- [OPEN] **C21 `battery/manager.py:1278-1282`** — `rebaseline` clears 5 of 7 `stats` fields, missing
  `cc_/cv_charge_speed_rejected_pct`. Diagnostics-only today.
  ⟵ **DISPOSITION 2026-08-21 — OPEN.** rebaseline leaves the two *_charge_speed_rejected_pct stats behind, so a swapped battery inherits the old battery's rejected figures.
- [OPEN-DRIFTED] **C22 `button.py:84`** — batch-2 finding, now with the MECHANISM: the prefix scan cannot simply
  be swapped for `entity_belongs_to`, because `EufyVacuumSavedRunProfileButton` keeps
  `_vacuum_entity_id`/`_map_id` private, so `entity_belongs_to` returns False for EVERY run-profile
  button. Reachability narrower than DR-SETUP-1: the literal `_run_profile_` segment blocks the
  canonical input, so it needs a map_id containing an underscore — accepted by `services.yaml`
  (`selector: text: {}`, no pattern), emitted by nothing in discovery.

  ⟵ **DISPOSITION 2026-08-21 — OPEN-DRIFTED.** button.py still deletes registry entries by unique_id PREFIX; the ledger's mechanism is right but its "unreachable from discovery" clause is false on Roborock.
  **⚠ THE LEDGER'S MECHANISM IS WRONG — repair from THIS, not from the text above:** The clause "accepted by services.yaml (selector: text: {}, no pattern), emitted by nothing in discovery" is WRONG on Roborock. map_id is not always a discovery-minted number: core/manager.py:3620 sets `active_map_id=active_map_state.state`, and adapters/roborock/adapter.py:253 states outright that `select.{id}_selected_map` "reports the map NAME (\"Main floor\")". listeners/stall_capture.py:113-115 says the same and adds that the id "can carry separators" — which is why capture_path sanitises it. So an underscore-bearing map_id arrives through ORDINARY Roborock discovery (the user's typed map name), not only through the unvalidated text selector. What genuinely keeps reachability narrow is…
## TEST HOLES that make a stated claim decorative
- [OPEN] **T1 SC-11 (`tests/unit/test_stall_capture_render.py:486`)** — docstring names the NEGATION as
  the whole point; assertions check DIMENSIONS only. 90 and 270 swap axes identically, so the sign
  is untested and it passes either way. Prose better than the assertion is the deceptive form.
  ⟵ **DISPOSITION 2026-08-21 — OPEN.** SC-11's docstring makes the negated rotation angle the whole point; the assertions compare PNG dimensions only, and I proved the test stays green with the sign flipped.
- [OPEN] **T2** `health_qualifying_sessions` and `SESSION_MAX_HOURS`: ZERO hits in `tests/`. Delete
  `battery/manager.py:1288` and the suite stays green.
  ⟵ **DISPOSITION 2026-08-21 — OPEN.** Neither health_qualifying_sessions nor SESSION_MAX_HOURS is touched by any pytest test; both claims are decorative.
  **⚠ THE LEDGER'S MECHANISM IS WRONG — repair from THIS, not from the text above:** The cited line 1288 is now 1299 — navigate by the `health_qualifying_sessions` assignment inside `rebaseline`, not by line number.
- [OPEN] **T3** DR-BAT-2 untested; `test_charge_rates` works AROUND it, nulling the anchor fields.
  ⟵ **DISPOSITION 2026-08-21 — OPEN.** The DR-BAT-2 out-of-order anchor guard has no test; the only test that gets near it deliberately nulls the anchor to avoid it.
- [OPEN] **T4** No rename test on the button platform (the sensor sibling exists, INIT-13/SN-4).
  ⟵ **DISPOSITION 2026-08-21 — OPEN.** The button platform's rename-swap branch (the SN-4 sibling fix) exists in code and is completely untested.
- [OPEN] **T5** `ro_dx`/`ro_dy`/`flip_y` never reach `render_room_capture` in ANY test.

  ⟵ **DISPOSITION 2026-08-21 — OPEN.** ro_dx/ro_dy/flip_y are tested on both sides of the seam but never through it — no test passes them to render_room_capture.
## DOC / RELATIONAL
- [OPEN] **D10 `adapters/eufy/vocabulary.py:249` — the campaign thesis in one line.** `a38cac4a` wrote
  "total_error_seconds is subtracted from cleaning_time_seconds" describing the then-current
  arithmetic; `5b21a1a3`, same day, same RP-046 series, changed it to deduct only the invalidating
  subset and never returned for the sentence. Accurate at birth, invalidated by the fix it was
  written to justify. The ONLY remaining assertion in the tree that this subtraction happens is the
  comment itself. **AND THE DOC IS RIGHT WHERE THE COMMENT IS WRONG**
  (`docs/dev/10-learning-system.md:104`) — a counterexample to the harvest's founding premise that
  prose at the site outranks a document. Replicated at `job_finalizer.py:938-943` and
  `tests/adapters/eufy/test_error_source.py:3-4`.
  ⟵ **DISPOSITION 2026-08-21 — OPEN.** Comment at the RF-DOCK fault table still says the FULL error window is subtracted from cleaning_time_seconds; only the invalidating subset is.
  **⚠ THE LEDGER'S MECHANISM IS WRONG — repair from THIS, not from the text above:** The ledger names three replica sites. There is a FOURTH live one it misses: `docs/testing/subsystems/15-adapters.md:349` carries the same sentence (`total_error_seconds` is subtracted from `cleaning_time_seconds`, so a fault…). A fifth copy sits in `docs/dev/maintenance/highly-aggressive-audit.md:1816`, but that is a historical audit record describing the pre-fix state and should be left alone. So the fix is 4 sites, not 3.
- [OPEN] **D11 `src/i18n/en.js:2645`** — annotates `fault.eufy.base_station_power_off` with
  `// Eufy code 5014`; `vocabulary.py:753` maps 5014 to `fault.eufy.power_low_shutdown` and `:463`
  puts it in the ROBOT set on Eufy's own protos. The next editor re-maps it and reintroduces the
  bug `64b3c577` fixed — a robot battery death filed as a dock fault, so learning accepts a
  dead-battery run as complete.
  ⟵ **DISPOSITION 2026-08-21 — OPEN.** `en.js` still annotates `base_station_power_off` with `// Eufy code 5014` after 5014 was re-mapped away from it and moved into the robot set.
- [OPEN] **D12 `core/capabilities.py:719-745`** — the `RNF2RCXP` replica block says the rescue runs in
  THREE places and **names itself as one of the other two**, dropping `_rescue_maintenance_source`.
  The canonical anchor at `adapters/entity_resolve.py:249-256` has it right. **A replica anchor
  naming the wrong replica set.**
  ⟵ **DISPOSITION 2026-08-21 — OPEN.** The RNF2RCXP replica comment inside `augment_candidates_from_device` names itself as one of the other two copies and drops `_rescue_maintenance_source`.
  **⚠ THE LEDGER'S MECHANISM IS WRONG — repair from THIS, not from the text above:** The ledger cites one site; the identical wrong text is pasted at a SECOND site — `adapters/entity_resolve.py:595-607`, inside `resolve_declared_entities` (def at :432) — where it likewise names itself and omits `_rescue_maintenance_source`. Only the third copy, `core/capabilities.py:258-270` inside `_rescue_maintenance_source`, happens to be correct ("this one" there resolves to the missing member). So it is 2 wrong copies of 3, not 1.
- [OPEN] **D13 `core/capabilities.py:858-866`** — the `live:ENT-1` comment pasted three times verbatim.
  ⟵ **DISPOSITION 2026-08-21 — OPEN.** The three-line `live:ENT-1` comment is pasted three times verbatim in `detect_capabilities`.
- [OPEN] **D14 `docs/testing/subsystems/07-mapping.md:84-88`** — claims SC-2 pins "must NOT be flipped";
  SC-2 tests only the opposite half.
  ⟵ **DISPOSITION 2026-08-21 — OPEN.** The mapping test doc still sells SC-2 as the pin for "anchor and trail must NOT be flipped"; SC-2 only exercises the raster half.
- [UNVERIFIABLE] **D15 `button.py:181-183`** — rule right, NAMED CONSEQUENCE WRONG: claims a silent collapse;
  measured against pinned HA 2026.5.3 it raises loudly. A reader trusting "silent" mis-triages.
  ⟵ **DISPOSITION 2026-08-21 — UNVERIFIABLE.** Cannot settle whether HA's Entity.name raises or returns a falsy sentinel pre-platform, which is the single fact separating OPEN from NOT-A-DEFECT.
- [OPEN] **D16 `adapters/eufy/vocabulary.py:564`** — cross-ref to `get_battery_level`'s `-> int` is stale;
  `core/charging.py:42` reads `-> int | None`.

  ⟵ **DISPOSITION 2026-08-21 — OPEN.** vocabulary.py's `_exact_error_code` docstring cites `get_battery_level`'s `-> int` as its parallel; that signature is now `-> int | None`.
## THE int() FAMILY — what the relational pass bought
One rule, four sites; two guard nothing and the dangerous path is unguarded.
`error_tracker._code_key` LIVE+tested · `_exact_int`/`_int_set` **DEAD** ·
`eufy/vocabulary._exact_error_code` **NO PRODUCTION CALLERS** · `_safe_int` **LIVE, UNGUARDED**.

## VERDICTS — nothing written to 00b-h
`error_tracker:285` INVARIANT new · `:311` STALE(dead) · `:655` CITATION `IN40W49E` ·
`capabilities:70`+`:896` ONE RULE, INVARIANT new · `:764` INVARIANT new (argued off `INR2F03P`
and `IN11T0FS`) · `button:103` CITATION `IN5ATBW9` · `:325` CONVENTION (Python's rule — a token
would be uncitable) · `battery:800` INVARIANT new · `:866` CITATION `INNJ6SGC` · `:1231` INVARIANT
new · `:1285` CITATION `IN5ATBW9` · `eufy/vocabulary:250` STALE · `:274/:275` INVARIANT new ·
`:564` INVARIANT new · `stall_capture_render:162` CONVENTION · `:426` INVARIANT new · `:496`
INVARIANT new.

## A PREMISE I GOT WRONG — do not re-issue it
I briefed two agents that a CLOSED `live:<ID>` makes a comment stale. Both pushed back with
evidence: `live:<ID>` marks the FIELD DEFECT A PIECE OF CODE REPAIRS, cited as provenance —
`live:` is the RUN name (`{"run": "live", "id": "BATT-CV-1"}`), parallel to `{"run": "direct
read", "id": "DR-BAT-2"}`. ENT-1/ENT-9/ENT-12 are all closed and all still correctly cited.
**Closed is the EXPECTED state of a cited id.**

---

# BATCH 4 — 7 files, 9 rows (2026-08-20). Verified by me unless marked.

## THE CALIBRATION RESULT — the method works
`learning/room_attribution_engines.py` was given, BLIND, the two questions I had already answered
from five overnight captures. Reading only code it independently found the SPAN COLLAPSE
(`external_ingest.py:702-711` keeps first/last per room and emits ONE span covering everything
between; measured 50 s real span vs 65 s summed per-room wall) — and then improved on my
diagnosis in two directions:
  - traced it FORWARD: `time_wall_s` -> `build_graduated_job:1076` -> `cleaning_wall_seconds` and
    `duration_minutes`, on a record stamped `used_for_learning: True`, read by `stats_rebuilder`
    for avg_duration / avg_drift / overhead. ~30% inflated on that stream, grows with interleaving.
  - BOUNDED IT BETTER THAN I DID: per-room learned minutes are SAFE by design, because
    `stats_rebuilder._captured_minutes` prefers `cleaning_seconds` (correctly-summed ticks) and
    falls back to wall only at 0 — the documented `live:PHASE-ATTR-3` repair. Damage is JOB-LEVEL
    aggregates only, NOT the per-room timings that drive completion detection. I had said "time
    but not area"; the truer cut is job-level time but not per-room time.

## CODE — new, Roborock-specific and operationally live
- [OPEN] **C23 Lever B fixture disagrees with the callee (`f/test_discipline` verbatim).** The LRR fixture
  registers `SupportsResponse.OPTIONAL` (4 sites); upstream Roborock `services.py:27,37` registers
  `ONLY`. `test_dispatch_live_room_refresh.py:130` asserts `returns_response is True` against the
  TEST FILE's own `_LRR` dict (`:51-57`), never the shipped adapter (`roborock/adapter.py:570`).
  Nothing joins them. **Delete the shipped flag and the suite stays green while core raises
  `ServiceValidationError` before the handler, sticky-disabling Lever B for the session** — and the
  only success breadcrumb is on the success path, so the failure is silent.
  ⟵ **DISPOSITION 2026-08-21 — OPEN.** Lever B's test fixture contradicts the real callee and asserts against its own copy of the adapter block, so the shipped returns_response flag is unpinned.
- [OPEN] **C24 `vol.Invalid` escapes the permanent window.** `live_refresh/manager.py` classifies
  permanence BY EXCEPTION TYPE. `vol.MultipleInvalid` is not a `HomeAssistantError` (proven by
  import), so a schema mismatch skips all three classified clauses into
  `except Exception:  # pragma: no cover` — ERROR + traceback every `interval_s` forever, no
  sticky-disable. The most literally-permanent failure is the one the permanent branch cannot see,
  and it lands in a branch its own pragma calls untestable.
  ⟵ **DISPOSITION 2026-08-21 — OPEN.** A voluptuous schema rejection of the pulse service falls past all three classified except-clauses into the defensive `except Exception`, so the most permanent failure never sticky-disables.
- [OPEN] **C25 Roborock external runs take the UNREPAIRED attribution path.** The presence fallback that
  rescues a first room dropped by stale `cleaning_area` lives only on the counter-enrich path.
  `build_attributed_job` gates hard (`if rid is None or rid not in cleaned: continue`) with no
  fallback and returns None when `cleaned` is empty. Roborock declares `job_segmenter: noop`
  EXPLICITLY, so every Roborock external run is on the unrepaired path.
  ⟵ **DISPOSITION 2026-08-21 — OPEN.** Every Roborock external run routes to build_attributed_job, which drops any room the swept-area gate missed instead of rescuing it by presence.
- [OPEN-DRIFTED] **C26 `dwell_min_ticks` is DEAD for Roborock.** Declared `3` with a comment explaining it means a
  15 s minimum hold. No anchor means `winding` is structurally `0.0`, so the transit branch always
  wins first — measured: 60 ticks in one room, `cleaned = []`, verdict "straight pass".
  `validate_tuning` accepts it (only checks positive-number-ness). A knob with no reachable effect.
  ⟵ **DISPOSITION 2026-08-21 — OPEN-DRIFTED.** dwell_min_ticks really is inert for Roborock in normal operation, but not for the reason given — the anchor premise the entry rests on was invalidated nine days before the ledger was written.
  **⚠ THE LEDGER'S MECHANISM IS WRONG — repair from THIS, not from the text above:** Roborock pose samples DO carry anchors since dd690f44 (2026-08-09), so `winding` is not structurally 0.0 and the anchor-only dwell gate IS reachable whenever `cleaning_area` is unreadable for a whole run. The real reason `dwell_min_ticks: 3` has no effect in normal operation is that `_classify` consults it ONLY in the anchor-only branch, and Roborock declares a `cleaning_area` entity so its runs classify in ROBUST mode. Two comments at the declaration site are now false and were not flagged: adapters/roborock/adapter.py:766 says "No decoded-map pose is decoded here (anchor/heading stay None)", and :785 says "dwell_min_ticks x interval_s = 15 s minimum hold to count a room" — which describes…
- [OPEN] **C27 attribution merges two DIFFERENT aggregations into one row.** `_swept_area_by_room` SUMS
  across sightings; `_best_run_by_room` keeps ONE sighting. Merged at `_classify:213-217`, so
  `dwell_s`/`spread`/`winding` are one sighting while `swept_area_m2` is all of them. Measured:
  a room in-room 7 ticks reports `dwell_s` 4.0, BELOW a room with 8.0 — ordering inverted. Latent
  (`dwell_s` has no consumer outside the module) but a trap for the next one. Related: for a
  `native_current_room` brand `spread` is always 0.0, so "max spread = strongest evidence"
  degenerates to FIRST-WINS — the selector's stated rationale is structurally false for Roborock.
  ⟵ **DISPOSITION 2026-08-21 — OPEN.** The per_room row still mixes a summed-across-sightings swept area with a single-sighting dwell/spread/winding; the entry's trailing spread claim has gone stale.
  **⚠ THE LEDGER'S MECHANISM IS WRONG — repair from THIS, not from the text above:** The trailing "Related" clause is stale: `spread` is NOT always 0.0 for a native_current_room brand any more. dd690f44 (2026-08-09) declared Roborock's `map_state_source.live_pose` (adapters/roborock/adapter.py:729-732) and listeners/pose_sampler.py:280 now banks `robot_anchor` on that path, so `_run_metrics` produces a real spread and `_best_run_by_room` no longer degenerates to first-wins for Roborock. The primary aggregation-mismatch mechanism is unaffected and remains exactly as described.
- [OPEN] **C28 onboarding remap purges SOURCES, never TARGETS.** `remap_confirmed_floor_types:245-250`
  filters `key not in remap` (source keys). A pre-existing confirmation sitting on an id that
  BECOMES a remap target survives, so a room reads `confirmed` the user never confirmed — start
  gate opens, robot runs it on an unverified floor type (mop-on-carpet). The docstring documents
  the OPPOSITE resolution. `room_crud.py:344-346` pops BOTH directions; this is the weaker copy.
  No test: OB-6c passes because both its keys are sources.
  ⟵ **DISPOSITION 2026-08-21 — OPEN.** remap_confirmed_floor_types filters only SOURCE keys, so a stale confirmation sitting on an id that becomes a remap TARGET survives and the migrated room reads confirmed.
- [OPEN] **C29 `_write_atomic` is the shortest of FOUR copies.** No `fsync`, no tmp cleanup, where
  `history_store.write_json` documents both as `IO-7`. Power loss leaves a ZERO-LENGTH PNG at the
  path the docs tell users to hardcode, after the receipt already reported success. An
  `os.replace` failure strands a full rendered floor-plan of the user's home at `.tmp`, outside the
  one-file-per-map contract, where nothing reclaims it.
  ⟵ **DISPOSITION 2026-08-21 — OPEN.** The stall-capture atomic write still has no fsync and no tmp cleanup, while the copy that documents both sits four files away.
  **⚠ THE LEDGER'S MECHANISM IS WRONG — repair from THIS, not from the text above:** "Shortest of FOUR copies" is right on the count and on the substance but not on the superlative: `os.replace` appears in four places (learning/history_store.py:491, core/water_amendment.py:189, debug_capture.py:559, listeners/stall_capture.py:224), and core/water_amendment.py:189 is the shorter body (`tmp.write_text(...); os.replace(tmp, path)`). Both water_amendment.py:189 and debug_capture.py:559 share BOTH omissions with _write_atomic, so history_store is the lone correct copy and the fix has two siblings, not zero.
- [NEEDS-RULING] **C30 nothing ever deletes a stall capture.** Zero `rmtree`/`shutil` hits in the package. The PNG
  survives disarming the switch, deleting the vacuum, and removing the integration.
  ⟵ **DISPOSITION 2026-08-21 — NEEDS-RULING.** The finding is factually correct — nothing deletes the capture — but whether that is a defect is a retention policy call, and the gap is not stall-capture-specific.
  **⚠ THE LEDGER'S MECHANISM IS WRONG — repair from THIS, not from the text above:** The entry frames this as a stall-capture gap; it is the whole on-disk learning tree. `async_remove_entry` leaves `<config>/eufy_vacuum/learning/` entirely intact — the stall PNG, the pose ring (pose_store.py, which has its own age-based expiry at :165 but no removal hook), the job records and the battery store all survive integration removal by the same omission. Any ruling should be made once, for the tree, not for the PNG.
  **⚠ DECISION NEEDED:** Should removing the integration (or deleting a vacuum) purge `<config>/eufy_vacuum/learning/<vacuum>/` — or is leaving the user's own data on disk after removal the intended behaviour, in which case C30 closes as by-design?
- [OPEN] **C31 zone dispatch rotation mismatch (FRONTEND, hardware).** The panel RENDERS at
  `effectiveMapRotation()` but DISPATCHES zones at raw `mapRotation()`; they differ when VA render
  is wanted but absent, and `canDrawZone()` does not gate on that. A zone dispatched a quarter-turn
  from where it was drawn. Derived from predicates, NOT executed.
  ⟵ **DISPOSITION 2026-08-21 — OPEN.** Panel renders the map at effectiveMapRotation() but un-rotates dispatched zones at raw mapRotation(); the two diverge when VA render is wanted but its raster is absent.
- [OPEN] **C32 adapter-config schema check runs on WRITE, not LOAD.** `_validate_adapter` never calls
  `validate_against_schema`; the schema walk has ONE caller (`services/adapter_config.py:106`). So
  `save_adapter_config` refuses a config carrying `entity_overrides` while the startup load path
  registers it silently, and the code adapter then clobbers it — the exact silent failure
  `const.py:43` describes, through the door its enforcement does not cover.
  ⟵ **DISPOSITION 2026-08-21 — OPEN.** The full ADAPTER_CONFIG_SCHEMA walk runs only on the save service; the startup load path validates with _validate_adapter, which has no unknown-key check, so a config the write door refuses loads silently.
  **⚠ THE LEDGER'S MECHANISM IS WRONG — repair from THIS, not from the text above:** The ledger's `const.py:43` citation has drifted: the ENTITY_OVERRIDES_KEY contract block is now const.py:48-72, with the clobber sentence at :68-71. Mechanism as described is exact.
- [OPEN] **C33 `"unusable"` means five different things.** `listeners/stall_capture.py` emits it from TWO
  sites for missing raster / undecodable base64 / zero dimensions / empty room — in the module
  whose comment at `:320` condemns exactly that collapse and split `no_pillow` out to fix it. The
  four-way guess moved one layer down.
  ⟵ **DISPOSITION 2026-08-21 — OPEN.** "unusable" is still one receipt reason for four distinct causes across two sites, in the module whose own comment condemns exactly that collapse.
- [NOT-A-DEFECT] **C34 `setup/protection.py:42` is UNREACHABLE from every caller.** `status.py:127` filters the ⟵ **RESOLVED 2026-08-21 as LEAVE-WITH-A-NOTE (Chris).** Guard left byte-for-byte. A note now records that no live caller reaches it (status.py:127 pre-filters by isinstance and landed 2.5 months BEFORE this guard; delete.py:68 raises upstream), that it stands as a BOUNDARY NORMALIZER for the next caller, and that the cost of being wrong is asymmetric: one malformed bucket in a user's `.storage` would raise out of a function `get_setup_status` calls once per map per vacuum, taking out the entire Setup tab. **Filed as dead twice; the note exists so there is no third time.**
  non-dict bucket first (landed 2.5 months BEFORE this guard); `delete.py:68` raises upstream of
  the call. Three of the four guards that commit added are live; the annotated one is dead.

  ⟵ **DISPOSITION 2026-08-21 — NOT-A-DEFECT.** Confirmed unreachable, and confirmed explicitly accepted — the leave-with-a-note ruling is landed in the tree, not just in the ledger.
## DOC
- [OPEN] **D17 `const.py:98-100` documents the REJECTED DRAFT.** Claims `dev_inject_stall` is "registered
  only when `<config>/eufy_vacuum/dev_mode` exists… Never registered on a normal install." The
  token `dev_mode` appears EXACTLY ONCE in the whole codebase — in that comment.
  `services/stall_capture.py:24` says outright: "IT IS REGISTERED UNCONDITIONALLY, AND FLAGGED HARD
  INSTEAD (Chris, 2026-08-08). An earlier draft gated it behind a marker file." Combined with D1,
  BOTH pieces of documentation about this service are wrong, in opposite directions.
  ⟵ **DISPOSITION 2026-08-21 — OPEN.** const.py still documents the rejected marker-file draft for dev_inject_stall; the service is registered unconditionally.
- [OPEN] **D18 `const.py:190` "display only — never affects dispatch" is STALE.** `live_map_rotation`
  reaches `start_zone_clean` via `draftsToNormalizedRects(..., this._mapRotation())`. Zone clean is
  by GEOMETRY, not room id, so the "cleaning is by room id" rationale died when zone-draw-at-any-
  rotation shipped 5 days after the comment. Test ZG-9 already proves the negation. Replicated with
  the same dead rationale at `mapping_services.py:2460`, `services.yaml:3083` (USER-FACING),
  `src/state/map.js:102`.
  ⟵ **DISPOSITION 2026-08-21 — OPEN.** "Display only — never affects dispatch" is still asserted at all four sites while live_map_rotation is an input to the start_zone_clean geometry.
  **⚠ THE LEDGER'S MECHANISM IS WRONG — repair from THIS, not from the text above:** Path drift only, not mechanism: the ledger's `mapping_services.py:2460` is actually `custom_components/eufy_vacuum/mapping/mapping_services.py:2460` (same line number, deeper path — there is no top-level mapping_services.py). const.py:190 is now const.py:214-216; src/state/map.js:102 is the middle of the :100-103 block. Worth noting alongside C31, which is the executable consequence of the same coupling (panel renders at effectiveMapRotation() but dispatches at raw mapRotation()).
- [OPEN] **D19 `listeners/stall_capture.py:60`** — the event carries RAW `map_id` while the filename is
  SANITISED, so an automation reconstructing the path from the event's own fields gets the wrong
  path TODAY on Roborock ("Main floor" vs "Main_floor.png"). The comment warns of a hypothetical
  future break and misses the shipped one.
  ⟵ **DISPOSITION 2026-08-21 — OPEN.** The EVENT_STALL_CAPTURED comment warns only about a future layout move and never mentions that the event's map_id is raw while the filename is sanitised — a mismatch that is live on Roborock today.
- [OPEN] **D20 `setup/protection.py:38` parity claim is doubly stale.** It copied only the `isinstance`
  half of drift.py's two-part idiom on day one; drift.py then centralised the predicate into
  `map_manager.map_ids_with_rooms` (MAP-GHOST-1), leaving protection.py the un-migrated 4th copy.
  ⟵ **DISPOSITION 2026-08-21 — OPEN.** Both halves of the ledger's claim hold: protection.py copied only the isinstance half of drift.py's idiom, and it never migrated to map_ids_with_rooms.
- [OPEN] **D21 three stale line references in `onboarding/manager.py`** (`:217`, `:238`, `:344`) — drifted
  17-70 lines. Constructs still exist; the parity claim at `:217` is substantively wrong, not just
  mislocated.

  ⟵ **DISPOSITION 2026-08-21 — OPEN.** All three stale line citations are still in onboarding/manager.py, and the one at :217 also claims a parity with room_crud that the code does not have.
  **⚠ THE LEDGER'S MECHANISM IS WRONG — repair from THIS, not from the text above:** Measured drift in today's tree is 21 / 21 / 70 lines, not "17-70"; the third citation is prose-form ("(line 218)"), not a `path.py:NNN` form, so it is invisible to a path-based citation grep.
## VERDICTS
`const.py:43` CITATION `INYA5T84` · `:190` STALE · `stall_capture.py:60` CONVENTION · `:65`
INVARIANT new (privacy default — nothing in the 36 covers that class; 9 paths verified fail-closed)
· `room_attribution_engines:223` INVARIANT new · `counter_segmentation:507` INVARIANT new ·
`onboarding/manager:237` CITATION `INMKEHPQ` · `setup/protection:38` CONVENTION ·
`live_refresh/manager:172` CONVENTION.

## STRONGEST UNREGISTERED RULE FOUND SO FAR
`listeners/stall_capture.py:20-27` — the image goes to `learning/`, deliberately NOT `www/`, which
is served at `/local/` WITHOUT AUTHENTICATION; otherwise the feature "would publish a cropped
floor-plan of the user's home at a fetchable URL on every stall." No test. A one-line assertion
(`"www" not in capture_path(...)`) would pin it.

---

# BATCH 5 — 6 files + 1 blind duplicate (2026-08-20). CLOSES THE PRODUCTION .py SWEEP: 29 files, 57 rows.

## LIVE DATA DEFECT — measured on Chris's store, verified by me
- [OPEN] **C35 learning teaches the COARSE duration when the refined one is in the same record.**
  `build_room_stats_payload:481` reads `job_info["duration_minutes"]`; `history_store.py:1932`
  writes `room_cleaning_minutes` = cleaning time minus overhead. **Verified on
  `ivy/jobs/job_2026-06-15T12-57-43.json`: `room_count=1`, `duration_minutes=5.4`,
  `room_cleaning_minutes=3.36`** — learns 5.4 for a 3.36 room, +61%. Agent measured the store:
  74 learning jobs, 23 fall back to the coarse value, **16 of those are single-room jobs that
  carried the refined one**; one case 2.53 vs 0.51 (+396%). The SAME FILE already prefers the
  refined value for single-room jobs in `build_job_stats_payload:329` and
  `build_jobs_index_payload:959` — only the learning path does not. This double-counts approach
  and drive-home into the room's own minutes, which `_captured_minutes:97-99` says are modelled
  separately as `overhead_observed` / `transit_seconds`.
  **REFINES THE MORNING FINDING:** I said per-room learned minutes were protected from the span
  collapse. True for THAT route only. This is a second, unprotected path into the same numbers.

  ⟵ **DISPOSITION 2026-08-21 — OPEN.** Per-room learning still divides the COARSE job duration across rooms even when the refined single-room value sits in the same record.
## CODE
- [FIXED] **C36 `core/manager.py:4925` reads the wrong key — the guard is permanently inert.** ⟵ **FIXED 2026-08-21 (b4b0bf80).** Independently re-derived before acting: run_plan stamps `phase_type` (:887/:961/:968/:986), queue_engine:512 passes it verbatim, a bare `type` is stamped on a PHASE nowhere. Fix is one key. Two tests landed IN THE SAME COMMIT as the precondition the reviewer required — [SWT-4] parametrised over all three of NON_CLEANING_PHASE_TYPES and built with `phase_type` so it CAN fail (a test written with `type` would pass against the bug), and [SWT-5] asserting a cleaning phase does NOT exempt, so the fix cannot be a blanket mute. Bite proven: fix reverted -> 3 red, restored -> green, sha256-identical.
  `(phases[idx] or {}).get("type")`, but live phases are stamped `phase_type`
  (`run_plan.py:887/961/968/986`) and a bare `type` is stamped ZERO times. `ptype` is always `""`,
  so the stall-watch exemption never fires and a small zone phase under the ~1 m² floor is flagged
  stalled. The comment above it warns about a hypothetical FUTURE silent inheritance while sitting
  in an actual present one.
  ⟵ **DISPOSITION 2026-08-21 — FIXED.** The stall-watch phase exemption read `type` on a dict stamped `phase_type`, so it was inert; fixed and tested on 2026-08-21.
- [OPEN] **C37 Roborock's two active-state lists disagree.** `ACTIVE_RUN_TASK_STATES` (9) vs
  `CANCEL_DETECTION_STATES["active"]` (5); the difference is `docking`, `going_to_target`,
  `returning_home`, `starting`. Two are justified (they are the return side). **`starting` and
  `going_to_target` are not.** A run cancelled before reaching the first room emits
  `going_to_target -> returning_home`, misses `from_state in _active_states`, and exits
  `no_cancel_like_transition` — ABOVE the `_MIN_FLOOR_MINUTES` check written to catch false
  starts. It archives `completed`, `used_for_learning: True`, and graduates into the baselines.
  ⟵ **DISPOSITION 2026-08-21 — OPEN.** Roborock's cancel-detection active list (5 states) omits `starting`/`going_to_target`, so a run cancelled before the first room escapes cancel detection above the floor check and graduates into the baselines.
- [OPEN] **C38 `history_store.py:1692` answers the return question with a frozen literal.**
  `== "returning"`, no entity filter, feeding `actual_cleaning_minutes` -> per-room learning. The
  finalizer answers the identical question adapter-driven AND entity-filtered. Works for Roborock
  only by accident (the vacuum entity's HA state also passes through `returning`).
  ⟵ **DISPOSITION 2026-08-21 — OPEN.** The single-room return-time derivation still matches a hardcoded `"returning"` against transitions from EVERY watched entity.
- [OPEN] **C39 index and CSV disagree on the same record.** `stats_rebuilder:1057` carries the
  `True if is_external` guard; `:1264` and `:1331` are bare `bool(outcome.get(...))` into a column
  named `sanity_passed`, and `rebuild_all` feeds them the same records. CSV headers carry no
  `origin` column, so a consumer cannot apply the repair. **No test asserts the rebuilt value at
  all — all 7 `sanity_passed` hits in `tests/` are seeding.**
  ⟵ **DISPOSITION 2026-08-21 — OPEN.** One rebuilt record yields two different sanity_passed answers — the jobs index forces True for external origin, both CSV writers emit the raw flag, and the CSVs carry no origin column to reconcile it.
- [FIXED] **C40 zone-first / zone-last run profiles silently lose the zone.** The break-trim uses the
  dock-polled set; `_reject_unbracketed_break` refuses only `charge_wait`/`wait` at the edges. A
  profile starting or ending with a zone is legal to save and the zone never runs. Every zone test
  sandwiches it between room groups.
  ⟵ **DISPOSITION 2026-08-21 — FIXED.** A leading zone is now refused on the write path and reported (not silently dropped) on apply; the ledger's zone-LAST half was already legal and works.
  **⚠ THE LEDGER'S MECHANISM IS WRONG — repair from THIS, not from the text above:** The ledger's mechanism is half wrong on two counts. (1) It is not `_reject_unbracketed_break` that loses the zone — that helper only ever policed charge_wait/wait, correctly, and the fix was deliberately NOT put there. The loss happened in apply_run_profile's break derivation, which anchors each break by `after_index = rooms emitted so far` and skips any step emitted before the first room. (2) "zone-first / zone-last" is wrong on the zone-last half: set_queue_breaks explicitly permits after_index == room_count for a zone, so a trailing zone never went missing. The ledger's opening clause "The break-trim uses the dock-polled set" does not correspond to anything in this code path.
- [OPEN] **C41 entity-override merge is defeated through the other store.** `config_flow` merges within
  `config_entry.options`; the panel writes `manager.data[ENTITY_OVERRIDES_KEY]`;
  `__init__.py:409-412` reconciles them with a shallow merge keyed by VACUUM, not by ROLE. Set
  role A via the panel, then save the options flow having picked role B — role A is dropped. That
  is the "install oscillating between fixed and broken" the comment says merging prevents,
  arriving through the store it does not cover. `ENTITY_OVERRIDES_KEY` appears nowhere in
  `test_config_flow.py`.
  ⟵ **DISPOSITION 2026-08-21 — OPEN.** The two entity-override stores are reconciled with a merge keyed by vacuum, so saving the options flow replaces the panel's whole role map for that vacuum.
- [OPEN] **C42 the setup form pre-fills a Eufy model for every brand.** `config_flow.py:76`
  `vol.Required(CONF_TESTED_MODEL, default=SUPPORTED_TESTED_MODEL)` -> `"Eufy X10 Pro Omni"`, on
  the first screen a Roborock user sees. `f/eufy_is_not_the_default`. The field is also WRITE-ONLY
  — collected, stored, read by nothing.
  ⟵ **DISPOSITION 2026-08-21 — OPEN.** Setup form's model field defaults to the Eufy model for every brand, and nothing ever reads the value.
- [OPEN] **C43 `manifest.json` does not declare `single_config_entry`.** HA 2026.5.3 supports it and
  aborts at `async_init`. Without it the user completes the whole form before `already_configured`.
  The premise itself holds, but it carries six domain-scoped singletons in `hass.data[DOMAIN]` and
  two `entries[0]` lookups in `services/setup.py`.
  ⟵ **DISPOSITION 2026-08-21 — OPEN.** manifest.json still omits single_config_entry, so a second setup attempt is only refused after the whole form is filled in.
  **⚠ THE LEDGER'S MECHANISM IS WRONG — repair from THIS, not from the text above:** The supporting count has drifted: services/setup.py now has THREE domain-scoped first-entry lookups, not two — :257/:260 and :301/:304 (`entries[0].entry_id` reloads) plus :494/:496 (`_entries[0].entry_id` for the panel ledger).
- [OPEN] **C44 no Python linter runs anywhere.** No ruff/flake8/pylint/mypy in any workflow; no
  `pyproject.toml`, `setup.cfg`, `.flake8`, `.pylintrc` or `.pre-commit-config.yaml`. At least two
  of today's findings are plain F401. (Note the asymmetry: `f/external_pr_lessons` runs pylint on
  code sent to OTHER people's repos.)
  ⟵ **DISPOSITION 2026-08-21 — OPEN.** No Python linter runs anywhere in this repo — no tool in CI, no config file of any kind.
- [SUPERSEDED] **C45 — SPLIT 2026-08-21 (Chris approved). One bullet invited ONE action across five items with
  THREE different answers.** Verified read-only; no edits made. Sub-entries below stand alone.

  - **C45a — `adapters/eufy/adapter.py:27` `STORAGE_KEY` imported and unused. SAFE.** Change
    `from .const import ADAPTER_ID, STORAGE_KEY` to `from .const import ADAPTER_ID`. Nothing else in
    the file references it, there is no `__all__`, and `core/storage.py`'s own import from
    `adapters/eufy/const.py` is the LIVE path and is untouched. True deadness, one line.  ⟵ **DONE 2026-08-21.** `from .const import ADAPTER_ID, STORAGE_KEY` -> `from .const import ADAPTER_ID`. `core/storage.py`'s own import from `adapters/eufy/const.py` is the live path and is untouched.

  - **C45b — `learning/stats_rebuilder.py` `total_estimated_minutes` written, never emitted. TRUE,
    but DO IT DELIBERATELY, never as part of a sweep.** Four lines: initialisers `:597`, `:638`;
    accumulations `:608`, `:655`. ⚠ It sits inside two accumulator dicts beside SIX live `total_*`
    siblings (`total_estimated_battery_used`, `total_robot_water_used_ml`, `total_water_overhead_ml`,
    `total_water_used_ml`, …). A block-level tidy of "the unused total_ keys" takes live ones with
    it. At `:654-655` the whole now-empty `if rid not in allocated_rids:` arm goes, but the
    identically-predicated LIVE block at `:627-632` must be left alone.  ⟵ **DONE 2026-08-21, carefully.** Five lines: two initialisers, one accumulation, and the two-line `if rid not in allocated_rids:` arm whose ENTIRE body was the dead key. ⚠ The indentation was read RAW first — the arm guarded only its one statement; `:656` onward sits outside it, so removing the pair is clean. ⚠ AND THE VERIFIER UNDERCOUNTED: it named ONE live identically-predicated block; there are THREE (`baseline_samples` + else, `pass_bucket`, `edge_bucket`). Removal was matched on CONTENT, not line number, so the count being wrong did not matter — the one removed was the only one whose whole body was the dead key. Six live `total_*` siblings in the same dicts untouched (31 references remain).

  - **C45c — `tests/adapters/test_adapter_isolation.py:102` `OWN_DOMAIN_KEYS`. A DECISION, NOT A
    DELETION — CHRIS'S CALL.** Two honest options: (a) delete the constant and KEEP the two-line
    comment above it, because that comment is the only written form of the rule; or (b) build
    **ISO-6**, the fence the constant was written for, and let it earn itself. Verifier's preference
    is (b): it is cheap, and both adapters already carry the cross-domain `hass.data` comments
    (`eufy/adapter.py:792`, `roborock/adapter.py:695`) that ISO-6 would have to allow. Per
    `f/claim_must_be_able_to_bite`, a constant no test consumes is a PREFERENCE, not a claim.  ⟵ **DONE 2026-08-21 — ISO-6 BUILT (Chris's ruling: "iso 6").** Two tests: `test_iso_6_no_brand_file_reads_vas_own_hass_data` fences VA's OWN `hass.data` domain (reaching into robovac_mqtt/roborock stays the adapter's job), and `test_iso_6b_the_own_domain_detector_detects` proves the instrument the way ISO-5 does — a manufactured violation, plus a negative case so a detector that flagged EVERYTHING would fail too. ⚠ ZERO SUBJECTS TODAY: no adapter touches `hass.data` at all, so without 6b this would be a fence indistinguishable from a broken one. AST not grep, because the only `hass.data[DOMAIN]` mentions under adapters/ are DOCSTRINGS in registry.py and a text fence would fail on prose describing its own rule. `OWN_DOMAIN_KEYS` now has a consumer; per `f/claim_must_be_able_to_bite` it was a PREFERENCE until today.

  - **C45d — `allocation_excluded_count` / `partial_excluded_count`. ⚠ THE DEADNESS CLAIM IS WRONG.
    Re-file as DOC-class, not code.** They are emitted; the original finding mis-read the surface.
    Do NOT delete.  ⟵ **RE-FILED 2026-08-21 as DOC-CLASS, not code (Chris: "doc").** The deadness claim was WRONG: `allocation_excluded_count` / `partial_excluded_count` ARE emitted. Nothing to delete. What remains is a documentation question — whether the emitted fields are described where a consumer would look — and it does NOT gate the code phase.

  - **C45e — `CONF_TESTED_MODEL`. ⚠ NOT A DELETION. STOP-FOR-APPROVAL.** This is the one that would
    have cost a feature. Removing the constant removes a REQUIRED FIELD from the setup form every
    new user completes, orphans **19 translation entries** (`strings.json` + 18 packs), and changes
    the shape of config-entry data **already persisted on every existing install, including the live
    box**. `f/large_change_workflow` trips on "persisted key" — approval, not a sweep. A user
    mid-setup would meet a schema its translations no longer match. Removal also reddens
    `test_config_flow.py:83` and three conftest fixtures.  ⟵ **LEAVE IT BE — Chris, 2026-08-21. Closed as NOT A DEFECT.** Verified independently: `config_flow.py:76` makes it `vol.Required` on the setup form; `async_create_entry(data=user_input)` persists it; and `diagnostics.py:985` dumps `dict(entry.data)` into EVERY diagnostics download. **So it is not write-only — its consumer is a HUMAN reading a diagnostics dump**, which is exactly what a "tested model" field is for: the first question on any bug report, answered without asking. ⚠ A FIFTH STATE for the deadness taxonomy: CONSUMED BY A PERSON, NOT BY CODE. No caller graph sees it and no ablation can either — break it and nothing goes red, because no test asserts what a human reads. Deleting it would drop a required field from every new user's setup, orphan 19 localized labels (strings.json + 18 packs), and change the shape of config-entry data already persisted on every install.

  **THE LESSON THIS EARNS, and it is why the split mattered:** five findings arrived under one
  number because they shared a SHAPE ("declared, not read"). Acting on the shape would have deleted
  a persisted user-facing setup field. **A batch entry is only safe to action as a batch if every
  member shares a DISPOSITION, not merely a symptom.**
  (`test_adapter_isolation.py:102`, defined once, referenced nowhere) · `STORAGE_KEY` imported and
  unused in `adapters/eufy/adapter.py:27` · `total_estimated_minutes` written in two accumulators,
  emitted in neither output · `allocation_excluded_count` / `partial_excluded_count` emitted with
  no reader · `CONF_TESTED_MODEL` write-only.
  ⟵ **DISPOSITION 2026-08-21 — SUPERSEDED.** The parent 'declared, not read' bundle no longer stands on its own — it was split into C45a-e on 2026-08-21 and every sub-entry is resolved in the tree.
  **⚠ THE LEDGER'S MECHANISM IS WRONG — repair from THIS, not from the text above:** The parent line as written still reads as one open five-item finding; it is now purely a header for C45a-e and should not be actioned as a batch — which is the lesson recorded at ledger :396-399.
- [OPEN] **C46 silent drop in `build_graduated_job`** (`external_ingest.py:1050-1052`): an assignment
  whose `segment_orders` match no segment hits `continue` WITHOUT appending to `blocked`, so the
  atomic "graduate only when all pass" contract at `:1027` does not cover it — the assignment
  vanishes and the record graduates without it.

  ⟵ **DISPOSITION 2026-08-21 — OPEN.** build_graduated_job still drops an assignment whose segment_orders match no segment, silently, and graduates without it.
## DOC
- [OPEN] **D22 `step_types.py:40`** claims `STEPPED_STEP_TYPES` is used by the `add_queue_break` schema.
  `services/queue.py` never imports `step_types`, and that schema deliberately uses the OTHER set.
  ⟵ **DISPOSITION 2026-08-21 — OPEN.** step_types.py:40 still claims the add_queue_break schema uses STEPPED_STEP_TYPES; nothing outside step_types.py uses that constant at all.
  **⚠ THE LEDGER'S MECHANISM IS WRONG — repair from THIS, not from the text above:** The schema does not use "the OTHER set" either: it uses a bare literal `["charge_wait", "wait"]`, which happens to match DOCK_POLLED_PHASE_TYPES' membership but is not that constant — so the two are free to drift, exactly the drift this module was created to stop.
- [OPEN] **D23 `capabilities.py:1093`** — *"Both are diagnostics-facing only; nothing branches on them."*
  `config_flow.py:282` reads `entity_resolution_reasons` and branches on it to decide which
  override pickers render. The `CNAYBZY3` anchor was placed on the READER side only.
  ⟵ **DISPOSITION 2026-08-21 — OPEN.** capabilities.py still says entity_resolution_reasons is diagnostics-only with nothing branching on it, while the options flow branches on it to decide which pickers render.
- [OPEN-DRIFTED] **D24 two live citations of the RETIRED numeric invariant scheme** — `stats_rebuilder.py:508`
  "Invariant 4" and `:1400` "Invariant 8". The only numbered-invariant references left in the
  tree; a reader cannot resolve either. `f/retirement_isnt_done_until_uncited`, inside the
  campaign's own subject matter.
  ⟵ **DISPOSITION 2026-08-21 — OPEN-DRIFTED.** Both numbered-invariant citations are still live and still unresolvable — but there are four such citations in the tree, not two.
  **⚠ THE LEDGER'S MECHANISM IS WRONG — repair from THIS, not from the text above:** "The only numbered-invariant references left in the tree" is false, and acting on the entry as written leaves half the job undone. Two more exist: custom_components/eufy_vacuum/jobs/phase_runner.py:602 `# Per-phase battery bounds (invariant 3: one child must not inherit another's counters)` and tests/unit/test_learning_stats_rebuilder.py:871 `# Wave 3 / invariant 4 — an ALLOCATED timing is arithmetic, never an observation`. Four sites, three distinct numbers.
- [OPEN] **D25 `config_flow.py:65-69`** — the drop-blank-vacuum branch is dead twice over: no consumer
  does a key-presence check (all use truthiness/equality), and the selector rejects `""`/`None`
  before the branch runs, so the falsy case is reachable only when the key is already absent.
  ⟵ **DISPOSITION 2026-08-21 — OPEN.** The drop-blank-vacuum branch and the comment justifying it are both dead — proven by running the selector.
- [OPEN] **D26 `config_flow.py:63`** — the behaviour is right, the causal claim is wrong.
  `reload_on_update=False` is never read, because `updates=None` makes the branch that consults it
  dead. The comment credits the flag; the call shape does the work.
  ⟵ **DISPOSITION 2026-08-21 — OPEN.** The comment credits `reload_on_update=False` for suppressing the reload; the flag is never read because `updates=None`.
- [OPEN] **D27 `manager.py:2120-2123`** states *"the index stores the key as None"* — false since v0.9.0;
  `stats_rebuilder:1057` emits `bool(...)`. The guard it justifies cannot bite on index data.
  ⟵ **DISPOSITION 2026-08-21 — OPEN.** The comment justifying the `is False` sanity guard still rests on a None the index cannot contain.
  **⚠ THE LEDGER'S MECHANISM IS WRONG — repair from THIS, not from the text above:** The stated premise is false but the code is fine, and the ledger's inference ("the guard it justifies cannot bite") overstates: `is False` still fires on a genuine False. What is dead is the None-vs-False DISTINCTION the comment claims to preserve; the old-external-run rescue is done upstream by the is_external force, not here. The emitter is stats_rebuilder:1084, not :1057.
- [OPEN] **D28 `adapters/eufy/room_profiles.py:20`** cites `tests/unit/test_profile_catalog.py` as pinning
  the values; that file is synthetic and imports nothing from `adapters.eufy`. The version
  described exists only in a stale worktree. Also `[RP-8]` is now VACUOUS — with the hard-floor arm
  removed nothing can make it red.
  ⟵ **DISPOSITION 2026-08-21 — OPEN.** The Eufy catalog still cites a synthetic core test as pinning its values, and [RP-8]'s hard-floor claim has no counterparty left.
  **⚠ THE LEDGER'S MECHANISM IS WRONG — repair from THIS, not from the text above:** "The version described exists only in a stale worktree" is wrong on both halves — no worktree copy imports adapters.eufy (checked all 8 under .claude/worktrees), and the version that made the sentence TRUE is in git history, not a worktree: `git show 33df98e2:tests/unit/test_profile_catalog.py` asserts `cat["builtins"] is BUILT_IN_ROOM_PROFILES` imported from profiles/room_profiles.py, back when core still carried Eufy's words. Commit ad8c074c ("core owns the key space, not a brand's words") moved the values out and rewrote the test synthetic, which is what falsified the citation.
- [OPEN] **D29 `adapters/roborock/vocabulary.py:190`** — the LONGER copy is the stale one: it still opens
  *"hard floors get a per-surface water default"*, contradicting the retirement note three lines
  below IN THE SAME BLOCK. The Eufy copy lacks that sentence. **Counterexample to "the shorter copy
  is the bug."**

  ⟵ **DISPOSITION 2026-08-21 — OPEN.** The Roborock water-defaults comment still opens by asserting the per-surface rule it retires three lines later.
## A CLAIM CLASS WORTH AUTOMATING
"Nothing reads / nothing branches on this" was refuted THREE times today
(`roborock/vocabulary.py:47`, `capabilities.py:1093`, and the `entity_helpers.py` case where an
agent wrongly called a live citation dead). Its inverse — declared-and-reaches-nothing — hit six
times. **Negative claims about consumers are the most rot-prone thing in the codebase**: true when
written, never revisited because the new consumer lands in a different file, and load-bearing
because people cite them to justify skipping work. Every instance was settled by a grep.

## VERDICTS
`eufy/const:44` CONVENTION (the rule cannot be violated — `f"{DOMAIN}.storage"` is byte-identical
to the literal, so no input distinguishes the forms) · `eufy/room_profiles:115` CITATION
`IN11T0FS` — **reproduced independently across batches on the byte-identical Roborock twin** ·
`roborock/adapter:344` CITATION `IN40W49E` · `config_flow:63` CONVENTION · `step_types:11` CITATION
`IN6VSBJ1` · `stats_rebuilder:996` **CONTESTED — primed says CITATION `INFJXSM4`, blind says
CONVENTION with `INFJXSM4` rejected. Needs Chris's ruling.**

## GUARD PLACEMENT IS INVERTED IN `step_types.py`
`STEPPED_STEP_TYPES` and `NON_CLEANING_PHASE_TYPES` are byte-identical today
(`frozenset({"charge_wait", "wait", "zone"})`). The test ratchet pins the pair that visibly
DIFFERS; the identical pair — the one anyone tidying would actually merge, and which `:87-90`
explicitly warns against merging — has no test.

## EXPERIMENT 2: primed vs blind on the SAME file (`stats_rebuilder`)
**Opposite verdicts on the same line.** Blind's rejection of `INFJXSM4` argues: the invariant
prescribes NO value while `:1057` resolves to a definite value on both branches; its "where a
boolean is unavoidable" escape fails because `:1060` three lines below emits `None` to preserve
indeterminacy and both consumers use identity comparison; and the registry scopes it to entity
state, handing on-disk absent-vs-unreadable to `IN2QDNB3`.
Blind also went OUTWARD — `git merge-base --is-ancestor` proving no tagged release ever wrote an
external record without the key, and 110 live records with **0 missing it**. The guard protects an
empty cohort.
**BUT the yields are non-overlapping in BOTH directions, on BOTH pairs.** Primed-only on
`live_refresh`: `ServiceNotSupported` on an unreadable capability, the zero-match breadcrumb, the
five silent `return False` sites. Primed-only here: `area_over_attributed:1055`. **Neither
dominates.** Calling blind "better" was an opinion from a non-neutral judge (Chris caught it) —
the supported statement is TWO DIFFERENT DETECTORS.
**Refined hypothesis, testable:** the split is not primed-vs-blind, it is **INWARD vs OUTWARD**.
Primed attention went to control flow; blind wandered to git history, the live store, and
consumers. So the second detector should be EXPLICITLY OUTWARD — verify every claim against the
commit it cites, the consumer it names, the data on disk — with an honourable null ("checked,
resolves correctly").
RULING (Chris, 2026-08-20): run both. *"The better this goes, the better the detection. The cleaner
the detection, the less this has to be run."*

---

# BATCH 6 — 4 scripts files, 7 rows, BOTH detectors each (2026-08-20).
# **THE .py CORPUS IS NOW COMPLETE: 33 files, 64 rows.**

## THE UNIFYING FINDING: GATES THAT REPORT CLEAN BECAUSE THEY CANNOT LOOK
Four gates examined. **Three have a branch that cannot fire, or a vocabulary they cannot see.**
Every one of them exits 0 today and reads as verification.

- [OPEN] **G1 `check_receipts.py` — 11 ablation probes run against the real `main()` with vocabularies
  rebound in memory (zero file edits).** What BITES: phantom catalog key (exit 1), dead outcome on
  a key (exit 1), removed station that IS emitted (exit 1, 14 problems). What DOES NOT: delete
  `pose_store` from `STATIONS` -> **exit 0 OK**; delete `no_room` from `DECLINE_REASONS` while a
  live site still emits it -> **exit 0 OK**; delete `lc` from `READABILITY` -> **exit 0**; delete
  `replay` from `PROVENANCE` -> **exit 0**. The only check touching those vocabularies fires when
  the tuple is EMPTY — to make it red you must declare a vocabulary with no members, which is a
  preference, not a claim.
  **Dead declarations it cannot see: 4 of 7 STATIONS never transmit** (`core`, `pose_store`,
  `mapping.stall_capture_render`, and `mapping.map_source` which is addressed but never speaks),
  `no_map` decline reason, `replay` provenance. Gate output: *"OK — catalog and call sites agree in
  both directions."*
  ⟵ **DISPOSITION 2026-08-21 — OPEN.** The receipts gate has no declared-but-never-emitted direction for its four vocabularies; four dead declarations sit in the tree and it exits 0.
  **⚠ THE LEDGER'S MECHANISM IS WRONG — repair from THIS, not from the text above:** One over-statement worth correcting: "the only check touching those vocabularies fires when the tuple is EMPTY" is not quite right. STATIONS is also touched by the membership check at :123-127 and the self-alignment check at :137-144, and all four are touched by the duplicate-members check at :186-188. None of those can bite on a DELETION, so the finding stands — but the accurate statement is 'no check runs in the declared-to-emitted direction', not 'no check touches them'.
- [OPEN] **G2 `"core"` IS UNSATISFIABLE BY CONSTRUCTION.** VERIFIED: `own_station = ".".join(rel.parts)`
  so `core/manager.py` -> `core.manager`. Emit `frm="core"` -> fails the alignment check ("a
  station may only transmit as itself"). Emit `frm="core.manager"` -> fails the membership check
  ("not declared in STATIONS"). No file in the package can produce `core` as `own_station`. The
  gate cannot report it because it only inspects stations that WERE emitted.
  ⟵ **DISPOSITION 2026-08-21 — OPEN.** The station `"core"` is declared in STATIONS but no file in the package can ever transmit as it, and the receipt gate structurally cannot notice.
  **⚠ THE LEDGER'S MECHANISM IS WRONG — repair from THIS, not from the text above:** One refinement the ledger leaves implicit: `"core"` is unsatisfiable only as a TRANSMITTER (`frm`). As an address (`to=`) it would pass, because the alignment check at :136 is applied to `frm` alone. Today nothing addresses it either — the only non-broadcast `to=` in the tree is `mapping.map_source` — so the declaration is entirely inert, but the "by construction" impossibility is specific to the transmit side.
- [OPEN-DRIFTED] **G3 `check_doc_citations.py` — the live ablation: 0 OF 5 drifted references flagged.** Four are
  out of corpus: it reads `docs/**/*.md` ONLY (citations in `.py` comments are never scanned) and
  **backticks are mandatory** (an unbackticked citation gets no check AND appears in no
  denominator). Neither limit is documented. The fifth IS parsed and silently downgraded to WEAK
  because `nearby_symbol` searches ONE PHYSICAL LINE and the naming symbols sit across a markdown
  wrap. Live coverage: **3 strong / 38 weak of 41 line citations = 7%.**
  ⟵ **DISPOSITION 2026-08-21 — OPEN-DRIFTED.** All four structural blind spots in the citation gate are still there; the headline coverage figure is now stale by 3x.
  **⚠ THE LEDGER'S MECHANISM IS WRONG — repair from THIS, not from the text above:** The measured numbers no longer hold: live today it is 14 strong / 56 weak of 70 line citations = 20%, not 3/38/41 = 7%. The denominator moved because commit 79927582 (2026-08-21, "teach check_doc_citations.py to read JavaScript") added "src" to SOURCE_ROOTS (:63) — the frontend line citations that previously failed to resolve now enter the tally. That commit changed WHICH citations are countable; it changed none of the four limits G3 names. The specific "0 of 5 drifted references" ablation is not reproducible from the repo — the five references are not named in the entry — but each of the five stated reasons is verified structurally above.
- [FIXED-UNPROVEN] **G4 the `NO-ANCHOR` branch has executed on 0 of 12 candidates.** All twelve `#anchor` citations
  are ID-form and hit the early-out; `body.count(anchor)` has never run on this tree — the
  identical shape to the `::` bug memorialised 70 lines above. Worse, the footer prints those
  twelve as **"refactor-proof"**, a positive claim for citations that received no check.
  ⟵ **DISPOSITION 2026-08-21 — FIXED-UNPROVEN.** The NO-ANCHOR branch is no longer unexercised — 12 non-ID-form anchor citations now flow through body.count(), and an ablation shows the branch bites.
- [OPEN] **G5 a missing docs directory exits 0 with a fully-formed clean report.** MEASURED by setting
  `DOC_ROOTS = ("doc",)` and running `main()`: *"0 docs · 0 citations checked · 0 wrong"*, exit 0.
  Asymmetry: `SOURCE_ROOTS` has an `is_dir()` check and fails LOUD; `DOC_ROOTS` has none.
  ⟵ **DISPOSITION 2026-08-21 — OPEN.** A missing/typo'd docs directory makes check_doc_citations.py print a fully-formed clean report and exit 0.
  **⚠ THE LEDGER'S MECHANISM IS WRONG — repair from THIS, not from the text above:** Minor: the ledger says SOURCE_ROOTS "has an is_dir() check and fails LOUD". The is_dir() check itself makes SOURCE_ROOTS fail QUIETLY (it `continue`s); the loudness is a downstream consequence — an empty index turns every citation into an UNRESOLVED problem and exit 1. The asymmetry and the DOC_ROOTS half of the claim are exactly right.
- [OPEN] **G6 `EVT-3` CANNOT GO RED.** It asserts the blind-spot ledger is non-empty;
  `gen_event_docs.py:647-655` appends three blinds UNCONDITIONALLY. Proven: a probe that hid six
  real shapes rendered a ledger of exactly the three hardcoded rows, EVT-3 green.
  ⟵ **DISPOSITION 2026-08-21 — OPEN.** EVT-3's non-empty assertion is satisfied by three hardcoded blind rows; it still cannot go red.
  **⚠ THE LEDGER'S MECHANISM IS WRONG — repair from THIS, not from the text above:** One addition the ledger does not make: docs/testing/04-patterns-and-conventions.md:498-503 repeats EVT-3's guarantee in prose ("`EVT-3` asserts the blind-spot ledger is present **and non-empty**") as though it bites. The false confidence is not confined to the test — it is documented as a covered case, which is the campaign's own unifying finding aimed at this gate.
- [OPEN] **G7 `hass.bus.fire()` and `async_fire_internal()` are invisible to the event generator** —
  `:503` matches `async_fire` exactly. Worse than silence: such an event lands under *"an `EVENT_*`
  constant that nothing fires"*, an affirmative false negative. (Currently benign — MEASURED, only
  `async_fire` is used in the package.)

  ⟵ **DISPOSITION 2026-08-21 — OPEN.** The event-doc generator matches the attribute name `async_fire` exactly, so hass.bus.fire() / async_fire_internal() sites are invisible and their constants get listed as "nothing fires".
## DOC
- [FIXED-UNPROVEN] **D30 `docs/testing/04-patterns-and-conventions.md:459` — THE SELF-ROTTED EXAMPLE.** The document
  that TEACHES the ban on line citations uses one as its example: *"`capabilities.py:187` lands on
  `return entry.entity_id`"*. VERIFIED: `:187` is now `continue`, and `_sweep_siblings` moved to
  `:199`. The example of a rotted citation has itself rotted, inside the doc defining the rule, and
  the gate passes it green as weak-only.
  ⟵ **DISPOSITION 2026-08-21 — FIXED-UNPROVEN.** The self-rotted `capabilities.py:187` example was migrated to a symbol citation on 2026-08-21.
  **⚠ THE LEDGER'S MECHANISM IS WRONG — repair from THIS, not from the text above:** Residual introduced by the fix, worth one line to whoever closes this: the passage's job is to show what a rotted LINE citation looks like ("a rotted line number still resolves… real code, in the right file, plausible"), and it now illustrates that with a `::symbol` citation, which cannot rot that way. The recorded defect is gone; the example no longer demonstrates its own point.
- [OPEN] **D31 `EVENTS.md:374-377` makes a false statement about itself.** Ships *"Line numbers here are
  current by construction… the only reason a reference is allowed to cite them at all"* in a
  document containing **ZERO** line citations (measured, grep exits 1). Last survivor of the
  line->symbol migration, emitted with no `---` separator so it renders inside the
  `stall_detected` section.
  ⟵ **DISPOSITION 2026-08-21 — OPEN.** EVENTS.md still ships the "line numbers are current by construction" blockquote in a file with zero line citations.
  **⚠ THE LEDGER'S MECHANISM IS WRONG — repair from THIS, not from the text above:** "Makes a FALSE statement about itself" is a shade too strong and would mislead whoever fixes it. The generator can still emit `file.py:NNN` — `where = f"{fname}:{site_line}"` at :409, plus `line {node.lineno}` in eight blind-detail strings (:507, :510, :522, :529, :545 and others), all of which render into the blind-spot site list. On a tree with an unresolvable fire site the sentence would be doing real work. The accurate charge is VESTIGIAL AND UNCONDITIONAL: a justification for citations this tree happens not to produce, emitted whether or not any exist, and positioned so it reads as a claim about the `::symbol` table immediately above it.
- [OPEN] **D32 `STATE-documentation-restructure.md` names the WRONG FILE.** It records `EVENTS.md` as
  carrying line citations and being the source of the gate firing on unrelated commits. Measured:
  `EVENTS.md` has zero. The real source is **`THEME_TOKEN_USAGE.md` with 2,310 bare `file:line`
  citations** — which is the file I regenerated this morning (`dcc24ccb`) after the anchor pass
  shifted 163 of them. I fixed the symptom without knowing the recorded diagnosis pointed elsewhere.
  ⟵ **DISPOSITION 2026-08-21 — OPEN.** STATE-documentation-restructure.md still blames EVENTS.md for gate churn in two places; the migration it lists as pending shipped on 08-16.
- [OPEN] **D33 `gen_floor_masks.py:34-37` "NOT TOUCHED" misdescribes 9 of 11 outputs.** Names wood,
  carpet and granite as hand-authored and left alone; `main()` overwrites all of them. Only marble
  and the tile grout line are genuinely untouched.
  ⟵ **DISPOSITION 2026-08-21 — OPEN.** The script's "NOT TOUCHED" list still names wood, carpet and granite as hand-authored while `main()` overwrites all nine of their masks.
  **⚠ THE LEDGER'S MECHANISM IS WRONG — repair from THIS, not from the text above:** The same docstring has a SECOND, unrecorded instance of the identical drift that the ledger does not mention: the PURPOSE section at :8-13 still says "Regenerate the TWO floor-texture luminance masks" and lists only `tile/tile-mask.png` and `concrete/concrete-micro-mask.png`. It is 11 masks. A reader who fixes only :34-37 leaves the file still claiming it writes two files.
- [OPEN] **D34 `check_receipts.py:11-12` — one outward claim REFUTED, and INHERITED.** Claims it adds a
  direction `check:i18n` lacks; `check-i18n.mjs:565` HAS a dead-key check — it is just non-fatal.
  The true novelty is fatality, not direction. The same overstatement is in the source doc
  (`PROTOCOL-semantic-flight-recorder.md:823-826`), so it was propagated, not invented.
  ⟵ **DISPOSITION 2026-08-21 — OPEN.** check_receipts' docstring still claims a direction check:i18n lacks; check-i18n.mjs has it, just non-fatally.
- [OPEN] **D35 stale 512-era figures in three places** — `gen_floor_masks.py:92`,
  `src/styles/floor-texture-styles.js:23`, `docs/dev/frontend/module-reference.md:270`. Assets are
  2048; a 4x discrepancy.

  ⟵ **DISPOSITION 2026-08-21 — OPEN.** All three sites still state 512 px for masks that are measurably 2048x2048.
## CODE / ASSETS
- [OPEN] **C47 a regeneration would DESTROY provenance stored in the assets.** MEASURED: all 22 masks are
  2048x2048 (two independent methods: raw IHDR parse + Pillow) and all 11 generated ones reproduce
  with ZERO differing pixels — but **two are not byte-identical**. `carpet-high-base-mask.png` and
  `-detail-mask.png` carry a hand-added PNG `tEXt` chunk: *"re-encoded 2026-07-04 to bump asset-ver
  and bypass a poisoned service-worker cache entry."* Pixel data identical, bytes differ. So
  "byte-identical output keeps the cache-bust token stable" is FALSE for those two, a re-run
  silently strips the note, and `__ASSET_VER__` changes.
  ⟵ **DISPOSITION 2026-08-21 — OPEN.** Regenerating the floor masks silently strips a hand-added PNG provenance note from two carpet masks.
- [OPEN] **C48 the canvas invariant holds by authoring luck and nothing checks it.** `gen_tile_base` never
  references `SIZE` at all — it inherits its source's dimensions. Where a mismatch BITES is
  `src/bindings/map.js`: `FLOOR_TEXTURE_MASK_SCALE` constants are hardcoded, tuned by eye against
  2048, and the code never reads `bmp.width`. An off-canvas mask changes tile period AND feature
  size, and same-material layers desynchronize — silent misalignment. Zero tests, zero CI, zero
  build steps check mask dimensions. A hand-authored replacement at the wrong canvas ships green.
  ⟵ **DISPOSITION 2026-08-21 — OPEN.** Mask feature scale is a hardcoded constant, the bitmap's own width is never read, and nothing anywhere asserts 2048.
- [OPEN] **C49 the floor-mask candidate is STALE for an unusually clean reason.** The named consequence
  CANNOT occur: percentage `mask-position` under `mask-size: cover` is scale-invariant, so a 1024
  mask lands byte-for-byte where a 2048 one lands. The rule is real but lives at a different site
  with a different mechanism. **New taxonomy entry: RIGHT RULE, RIGHT-SOUNDING CONSEQUENCE,
  WRONG SITE.**
  ⟵ **DISPOSITION 2026-08-21 — OPEN.** gen_floor_masks.py:58-59 justifies a real rule with a consequence that cannot happen; the comment is untouched.
- [FIXED-UNPROVEN] **C50 `marble/marble-vein-mask.png`** — referenced by no registry entry, still feeds `hashDir()` ⟵ **FIXED 2026-08-21 (03ecb1c3).** Deleted. 0 references vs 32/18/2/2 for the four siblings, all of which are registered layers in `src/textures/floor-texture-registry.js`. Shipped bundles reference it zero times. ⚠ NO `--deploy` REBUILD, against the reviewer's advice: `__ASSET_VER__` is a cache-buster on texture URLs, no URL points at the deleted file, no gate asserts bundle freshness, and a 2 MB+ binary diff is a worse trade than a stale cache-buster the release rebuild will refresh.
  and therefore `__ASSET_VER__`.
  ⟵ **DISPOSITION 2026-08-21 — FIXED-UNPROVEN.** marble-vein-mask.png is gone from the tree; the ledger's own inline FIXED annotation checks out.
- [OPEN] **C51 `check_receipts.py` visitor tuple has 7 fields**; `:44` docstring says 4, `:48` comment says
  6. Two stale descriptions of one structure, in the same file.

  ⟵ **DISPOSITION 2026-08-21 — OPEN.** _Emits appends a 7-tuple; its docstring says 4 fields and the adjacent comment says 6.
## VERDICTS
`check_doc_citations:74` CONVENTION — and it SPLITS: *"must be spelled with two colons"* is TRUE
and load-bearing (the one-colon pattern genuinely never matched `::symbol`), *"MUST come first"* is
**FALSE** — reordering the branches gives byte-identical group dicts, because they are mutually
exclusive on their first character. **Welding a false necessity to a true one is worse than
either alone: the next person who reorders for readability will hunt a bug that is not there.**
`check_receipts:81` CONVENTION · `:166` CONVENTION · `gen_event_docs:387` CONVENTION (correct
action is a `00-documentation-standard.md` §6 cross-reference, not a mint) · `gen_floor_masks:59`
**STALE**.

## WHAT THE OUTWARD DETECTOR PROVED ABOUT ITSELF
First deliberate outing. On `check_doc_citations` it checked **21 outward claims: 16 VERIFIED
outright**, 3 refuted as minor drift, 1 partial, 1 unreproducible — and concluded *"no claim is
materially wrong about behaviour."* On `gen_event_docs` it found **zero mismatches** in a full
26-site / 11-event / 92-key-slot reconciliation. **The honourable null works**: given
"VERIFIED — resolves correctly" as a first-class answer, it returned mostly those, and the sharp
finds it did produce are believable BECAUSE it was willing to say clean.
It also ran a **clean negative** on the version trap — five Python minors, byte-identical output —
with the exposure surface named and the caveats stated (3.12.13 is a late patch; earlier 3.12.x
unmeasurable).

## ONE MORE PREMISE I GOT WRONG
An agent reported `queue_engine.py:365` cites a file that does not exist. **`entity_helpers.py`
EXISTS** (10.9 KB), has `get_floor_type_label` at `:239` and `"granite": "Granite / Natural Stone"`
at `:250` — exactly what the comment claims it offers. Right instinct (the citation is imprecise),
false fact (the file is live). It would have entered this ledger as a stale-pointer finding if I
had not checked. **Second confirmed agent factual error of the campaign.**

---

# THE INVERSE CLASS — a gate that reports BROKEN when it is not (2026-08-20)

Every other gate defect in this ledger is a FALSE PASS. This one is a FALSE FAILURE, and it is
arguably worse: a lenient gate is trusted wrongly, but a gate that cries wolf gets ignored, and
then it is worth nothing when it is right.

**C52 `tests/test_replica_ratchet.py` scans git-ignored BUILD OUTPUT.**

- MEASURED on clean master (`dab1af7e`), PR #53 reverted, tree clean:
  `test_replica_sets_are_well_formed` FAILS with
  `['RN1RX2AT: 2 primary, 1 replica', 'RNCCB8J2: 2 primary, 1 replica', 'RNG7V2Y3: 2 primary, 1 replica']`
- The duplicate primary for all three is **`harness/dist/mount.js`** — the built harness bundle,
  which inlines `src/` and therefore carries a second copy of every `anchor: RN……` comment.
- `harness/dist/` is git-ignored (`.gitignore:27`) with **zero tracked files**, and the ratchet has
  no exclusion for it — no SKIP list, no dist filter.
- **CI never sees it.** `tests.yml`'s pytest job never builds the harness, so the bundle does not
  exist there. `card-visual.yml` builds it, but in a different job with a different checkout. CI on
  `dab1af7e` was green while this was red locally.
- **Cause, and it was mine:** `mount.js` mtime 14:45, my CSS-fix commit 14:46 — I built it by
  running `node harness/build.mjs` as part of the visual-regression verification. Before that the
  bundle predated the anchor commits and contained no markers, which is why the morning's full
  suite passed at 4438.
- Resolved locally by deleting the artifact (3.0 MB, git-ignored, rebuilt by
  `node harness/build.mjs`); ratchet then 6/6 green.

**FIX SHAPE:** one exclusion for `harness/dist/` — or better, for any path `git check-ignore`
would match, since the general defect is that the scan cannot tell SOURCE from GENERATED. Any
marker-counting test that walks the tree has this exposure, not just this one.

**WHY IT MATTERS BEYOND THE ONE TEST:** a bundle is a second copy of every file it inlines. Any
gate that counts occurrences across the tree — anchors, citations, declarations, i18n keys — will
double-count for a developer who has built, and not for CI. The failure is environment-dependent,
which is the hardest kind to trust.

**NOT A DEFECT IN PR #53** — recorded here because that PR's suite run is how it surfaced. The PR
itself was clean and merged as `953c9aca`.

---

# 2026-08-21 — surfaced while drafting the 18 rulings

## DOC
- [NEEDS-RULING] **D36 `docs/dev/design/shipped/notation-anchors.md` — the SPEC and the REGISTRY disagree about `PN`,
  and the spec is the one you would reach for.** Its status block (lines 3–7) states **`SN`, `HN` and
  `PN` remain reserved and unused** — three `PN`s are live in `00b` — and **`IN` in use (1)** — 33 are
  live, with 35 `anchor: IN` sites planted across the tree. Measured 2026-08-21 by grep, not by
  reading the doc's own claim.
  **The semantic half is the worse half.** The spec defines `PN` as *Prose Notation* — "a local
  implementation… has a deeper canonical explanation elsewhere", i.e. a POINTER. `00b` uses `PN` for
  something else entirely: **a rule whose enforcement lives outside the code**, and each of the three
  entries carries its own *"Why this can never be an `IN`"* paragraph making that the discriminator.
  Those are not the same class. The registry's is the working definition.
  **WHY IT BITES:** this is the doc you consult to answer *"is this an `IN` or a `PN`?"* — and it is
  wrong on exactly that question. It was consulted for that purpose on 2026-08-21 and its answer
  would have misfiled a row. A stale STATUS BLOCK is the highest-leverage staleness in a spec: it is
  read first, believed, and it contradicts the artifact it indexes.
  **FIX SHAPE:** refresh the counts (they are computable — `doc_anchor.py --show`), and reconcile the
  `PN` definition in ONE direction. Either the spec adopts the registry's meaning, or the registry's
  three entries are a different class that needs its own prefix. **Not a fix to make silently — the
  prefix is a type system and this is a type change.**
  **CLASS:** matches [[feedback_drift_hides_in_output_shapes]] — the algorithm prose in this doc is
  fine; what drifted is the block that REPORTS STATE. And it matches the campaign's unifying finding:
  the status block reports clean because nothing recounts it.

  ⟵ **DISPOSITION 2026-08-21 — NEEDS-RULING.** The spec's status block is still wrong on IN and PN counts, and its PN definition still contradicts how 00b uses PN.
  **⚠ DECISION NEEDED:** The question for Chris, one sentence: does `PN` mean "a pointer to a deeper canonical explanation" (the spec's definition, in which case 00b's three entries are mis-prefixed and need a new class) or "a rule whose enforcement lives outside the code" (the registry's working definition, in which case the spec's §PN is rewritten)? The count half needs no ruling — `doc_anchor.py --show` regenerates it…
## NOT A DEFECT — recorded so it is not re-derived
- **Single-site `IN` entries are NORMAL.** Measured: 33 registry entries, ~35 planted `anchor:` sites
  — roughly one primary site each, with bodies discussing 1–9 files. I had been using "spans multiple
  sites" as an unstated test for whether a row earns an entry. It is not the test. The test is the
  established one: **states a rule AND its consequence, with an input that makes it red.**
- **A row can carry the shape and still not need filing.** `stall_capture.py:65` has a site, a test
  (`test_absent_arming_is_off`), and a tag (`[SL-1]`). Which class it files under changes no code and
  no test. Chris, 2026-08-21: *"we do not have to force them to be anything. If they carry the shape,
  they carry the shape."*

## THE ANCHOR SYSTEM: the CODE half works, the TEST half does not exist

Chris's ruling 2026-08-21: *"If it's an in, it can carry a tag. If it's a pn, there has to be 2 at
least. Instantly find them and later on. We can link them to their tests."* Measured against the
tree the same day.

**THE TAGGING HALF IS HEALTHY. 328 token references** across `custom_components/` + `src/`, and
**0 of 36 entries has no code site.** Range 1–30 refs (`INKV8ZQD` 30, `INT62M7A` 27, `IN40W49E` 20).
Grep-findable now and after any refactor, which is the whole point of an opaque anchor. Note the
`anchor:` PREFIX appears only ~35 times — the other ~293 are plain citations. Declaration and
citation are different acts and only the former uses the keyword.

**THE TEST HALF IS ONE ENTRY OUT OF THIRTY-SIX.** Only `INKV8ZQD` has a test that names it, and it
is the model for what the rest should look like: `tests/integration/test_services_unmanaged_vacuum.py`
opens its module docstring with **`INKV8ZQD — durable per-vacuum state is minted only for a MANAGED
vacuum`** followed by a `Coverage targets` block, and `conftest.py:163` names the fixture for it too.

⚠ **TWO APPARENT HITS ARE FALSE AND I ALMOST REPORTED THEM.** `INMKEHPQ` and `INSJM6KC` appear in
`tests/test_replica_ratchet.py:27-28` — inside a PROSE DOCSTRING explaining why the ratchet imports
`doc_anchor` instead of re-scanning. That is the ratchet's own bookkeeping, not a test of either
rule. First count said 3/36; the true number is **1/36**. `INTERIOR` and `INSTANCE` also match the
token regex and are ordinary capitalised words.

**WHAT THIS IS AND IS NOT.** It is a FINDABILITY gap: you cannot get from a rule to its test, or from
a test to the rule it defends. **It is NOT proof the invariants are untested** — 35 entries may have
perfectly good tests that simply do not name the token. Which of the 35 genuinely lack a test is
SEPARATE WORK and must not be inferred from this number. Per
[[feedback_coverage_from_scopes_not_findings]]: an unlinked-but-tested rule and an untested one look
identical here, which is the campaign's unifying finding pointed at our own tooling.

**THE `PN` RULE HAS A CONSEQUENCE FOR ALL THREE EXISTING `PN`s.** Under *a `PN` needs at least 2*,
every one is currently under-cited at exactly ONE site: `PN1E8AZT` → `core/storage.py:26`,
`PNWJZYYR` → `dispatch/manager.py:103`, `PNN14JRN` → `src/actions/review.js:80`.
**`PNWJZYYR` already has a real second, found in the harvest and never linked:**
`src/cards/dashboard-card.js:751` — *"a stale scene must never fire select_option (selecting IS the
run)"*. VERIFIED by reading it. Same rule, different words, across the language boundary — which is
precisely the case a token exists to join and a name-based search would never find.

**FIX SHAPE (not started, needs Chris):** the link wants to be mechanical, not prose, or it rots like
any other citation. `INKV8ZQD`'s docstring-header convention is already in-tree and costs nothing to
copy. A gate that asserts every registry entry is named by ≥1 test would then have BITE — but it must
land AFTER the backfill, or it fails 35/36 on day one and gets deleted for crying wolf, which is the
exact failure the ratchet's own docstring warns about.

## DOC — the frontend corpus, and WHAT KIND of sentence rots
- [OPEN] **D37 `docs/dev/frontend/responsive-shell.md` — a STALE COVERAGE CLAIM, the worst class of
  CURRENT-DRIFT.** It states: *"The shortest viewport any harness test uses is 780px, so none of
  the `(max-height: 500px)` rules fire in the visual gate — landscape has no baseline coverage and
  must be checked on a device."* **FALSE since 2026-08-14.** `34f8bc9e` added a `720x344` case to
  `harness/tests/theme-mobile-layout.spec.mjs`, whose own comment says it exists precisely because
  *"LANDSCAPE is a viewport this gate could not see"*. The doc was written `7b2bb2e8` on 08-13 and
  went stale **the next day**.
  **WHY THIS CLASS IS THE WORST:** a stale constant is wrong; a stale COVERAGE claim DIRECTS
  BEHAVIOUR. It tells a reader to distrust a gate that works and to go re-test by hand. And it is
  the exact mirror of the campaign's unifying finding — not "a check that exists reads as covered"
  but **"a check that exists reads as NOT covering"**. The very test file it is wrong about names
  the forward version of that shape and ties it to issue #49.
  **ALSO D37b, same doc:** *"`(max-height: 500px)` also appears in three media queries"* — it is now
  ten occurrences across four files (`styles/index.js`, `mobile.js`, `theme-preview.js`, `theme.js`).

  ⟵ **DISPOSITION 2026-08-21 — OPEN.** Both perishable sentences in responsive-shell.md are still there and still wrong; the doc has never been touched since it was written.
  **⚠ THE LEDGER'S MECHANISM IS WRONG — repair from THIS, not from the text above:** D37b's own correction figure has itself drifted since the ledger measured it. The ledger says "ten occurrences across four files (`styles/index.js`, `mobile.js`, `theme-preview.js`, `theme.js`)". Measured today: ELEVEN occurrences across FIVE files — src/renderers/theme.js, src/styles/mobile.js, src/styles/modal-host.js, src/styles/theme-preview.js, src/styles/theme.js. src/styles/index.js now carries ZERO (verified, `grep -c` = 0), and modal-host.js and renderers/theme.js are new. Do not paste the ledger's list into the fix — recount. That the correction rotted in under a day is itself the entry's thesis.
## NOT A DEFECT — a measurement worth keeping
- **WHAT ROTS IS THE SENTENCE THAT ASSERTS CURRENT STATE. Nothing else.** Verified by hand on two
  frontend docs 2026-08-21. `floor-texture-map-view.md`: all eight `FLOOR_TEXTURE_MASK_SCALE_BY_TYPE`
  values exact, `70 * (attempt + 1)` exact. `responsive-shell.md`: `MOBILE_MAX_WIDTH=600`,
  `COMPACT_MAX_HEIGHT=500`, `CHROME_TOP_ZONE=24`, `CHROME_REVEAL_TRAVEL=140`, the allowlist — all
  exact. **Both drift instances found were CURRENT-DRIFT; 100% of the RATIONALE was intact.**
  Matches WAVE 1 at corpus scale: **156 of 185 HIGH findings (84%) are CURRENT-DRIFT**;
  INTENT-INVERTED is 3%, FRAME 12%.
- **THE ACTIONABLE FORM: a MIXED doc is the defect.** A reader cannot tell by looking which sentence
  is a durable reason and which is a perishable fact — they sit in the same paragraph in the same
  voice. Separate them and the rationale never needs touching again while the facts regenerate.
  That is `DESIGN-generated-doc-layer.md`'s split (facts generated, reasons hand-written), and
  `responsive-shell.md` is its proof case: ~90% durable, 2 perishable sentences, both wrong.
- **The rationale in these docs is NOT RECOVERABLE FROM CODE** — `img.decode()` failing randomly
  under burst, "random per load means the concurrency race, don't chase a re-encode",
  `querySelector` returning the first allowlisted match which is `overflow:hidden` in the one view
  that scrolls 53,000px, allowlist-not-denylist as "the safe direction to be wrong in". Rewriting a
  backend doc from code loses little because it restates the code. **Rewriting these from code
  destroys the only thing they contain.**
- **HYPOTHESIS TESTED AND NULL:** carrying the retired D-13 scope bar does NOT predict findings —
  37.7 per DR-bar doc vs 38.0 for the rest. D-13 is a FRAMING defect, not a drift driver. Do not
  re-derive this.
- ⚠ **METHOD, cost me a wrong claim:** I asserted "landscape has zero visual coverage" from
  `grep -E 'height: ?[0-9]{3,4}'`. The landscape case uses object shorthand `{ width, height }`, so
  the literal 344 never appears as `height: 344`. **Grep the CLAIM, not the spelling** — same rule as
  [[feedback_retirement_isnt_done_until_uncited]]. Chris caught it from memory.

## THE DISCRIMINATOR: a doc that describes a BOUNDARY is self-policing

**`backend-contract-and-data-shapes.md` verified 2026-08-21 and it is CLEAN** — despite being the
doc most exposed by the drift taxonomy (it is literally named for serialized shapes, the class
carrying 156 of 185 HIGH findings). **It has never been audited: zero WAVE 1 findings.**
  - `get_dashboard_snapshot` documented as a **42-key** read model → **exactly 42** in
    `core/manager.py:5862`. The three keys it names as 2.1.0 additions (`resolved_entities`,
    `entity_bindings`, `stall_capture_enabled`) are all present, and 42−3=39 as stated.
  - Claim: the shipped card has **no call sites** for the five adapter-config services →
    **0 in `src/` for all five**. Exact.
  - Where it disagrees with `services.yaml`, **the DOC is right**: 19 services are registered in
    python and absent from the descriptor, including the whole 10-service `setup_*` family, while
    `debug_capture_*` / `dev_inject_stall` ARE declared — so it is not a hide-the-maintainer-surface
    policy. ⚠ **This is NOT a new finding: `INJSETB0` already states it verbatim** — *"ten `setup_*`
    services have neither descriptor nor translation — so they exist, work, and are undiscoverable."*
    Do not re-report it as new; it is a registered invariant violation awaiting repair.

**WHY IT SURVIVED — the generalisation worth keeping.** A doc that describes a **boundary between two
independently-maintained things** is self-policing: when `get_dashboard_snapshot` grows a key the
card needs it, so somebody touches both sides. **A seam has two parties, and two parties notice.**
A doc that describes the INSIDE of one subsystem has one party and no such pressure.

That predicts the whole frontend/backend split better than "the frontend is more mechanical":
  - BOUNDARY docs (self-policing): `backend-contract-and-data-shapes` (card↔backend),
    `animal-svg` (external creature-pack authors — every structural claim verified exact),
    `i18n-system`, `theme-system`.
  - INTERNAL docs (no second party): `responsive-shell` — and it is precisely the one carrying **two
    stale sentences** (D37/D37b). Also `render-cycle`, `state-management`,
    `event-binding-and-modal-host` — UNTESTED, and the prediction says these are the exposed ones.

**TESTABLE, CHEAP, NOT YET RUN:** classify the remaining 17 frontend docs boundary-vs-internal and
spot-check one of each. If the prediction holds it tells us which docs to keep WITHOUT reading all
20 — and it applies to the backend too (`22-adapter-config-reference` and `03-services` are boundary
docs and should be the healthiest numbered ones).

⚠ **METHOD — three wrong turns on one file, all the same shape.** I nearly reported (1) 40 phantom
services (my regex swept event names and capability flags out of neighbouring tables), (2) the five
adapter-config services as undocumented (they are documented in PROSE, not a table row), and (3)
`services.yaml` as the authority for what is registered (it is one of three declaration sites and
the least complete). **Every one was my extraction, not the doc.** Before calling a doc wrong,
establish which artifact is actually authoritative for the claim.

## VERDICT: the three render docs SURVIVE — repair cost is a rounding error against recreation

Chris's criterion 2026-08-21: *"i think this may be able to be saved with about = effort to
recreation maybe less"*. Measured on `map-render-layers.md` (148 ln) + `render-cycle.md` (96 ln) +
`floor-texture-map-view.md` (323 ln) = **567 lines, 16 checkable claims, ONE content error.**

VERIFIED EXACT: `VIEWS` enum (10/10 entries, names + order), `ROOM_FILL_N`=12, 600 ms deferred
debounce, 220 ms click timer, `mask-mode: luminance`, `cache_headers=True`, `isolation:isolate` +
`z-index:-1`, four floor-texture file paths, all eight `FLOOR_TEXTURE_MASK_SCALE_BY_TYPE` values,
`70 * (attempt + 1)`, and the selection-scrim `Set` **quoted verbatim byte-identical** with its
`bindings/map.js:269-288` citation landing on BOTH endpoints.

- [OPEN] **D38 `render-cycle.md` inlines a STALE `_scheduleRender` body.** The live version at
  `src/main.js:1548` opens with a `_furnishedGestureActive` guard the snippet does not have. The
  doc's CLAIMS about it (microtask, coalescing, `_renderScheduled` as the dedup flag) are all still
  true — only the transcription rotted. Drift-rule category 2: a late-added feature in the doc's
  newest corner.
  ⟵ **DISPOSITION 2026-08-21 — OPEN.** render-cycle.md still inlines a _scheduleRender body missing the _furnishedGestureActive guard
- [FIXED-UNPROVEN] **D38b `map-render-layers.md` cites `bindings/map.js:376-377`** for the palette slot; the real
  line is **389**. ⚠ **NOT a content error** — the claim `(((rid-1) % ROOM_FILL_N) + ROOM_FILL_N) %
  ROOM_FILL_N` is exact. The claim survived, the LINE NUMBER rotted. Precisely the failure the
  notation-anchor scheme exists to retire; fix by anchoring, not by rewriting.

**AUTHORING RULE, and the data behind it: TRANSCRIBE CLOSED SETS, NEVER FUNCTION BODIES.** Every
transcribed closed set survived (10-entry enum, 8-row table, palette count); the one transcribed
function body is the single content error. A closed set changes by a deliberate act; a function body
ACCRETES GUARDS, which is the drift predicate exactly. Describe what a function guarantees, quote
only what cannot grow.

**MODEL CORRECTED — boundary-vs-internal was too narrow.** I predicted `render-cycle.md` would be
exposed because it is internal; it came back clean but for the snippet. Chris: *"the card is a
contract to show the front end"*. **A layer stack, a render cycle, a colour cascade are CONTRACTS —
anything more than one piece of code must AGREE on.** Internal and still an agreement.
`map-render-layers.md` states its own role that way: *"read it before touching room fills… so you
don't re-derive it from code (it has bitten us)"*.

**WHY RECREATION WOULD DESTROY VALUE — the concrete case.** `map-render-layers.md` §2 (R2-BUG-5)
resolves a code comment asserting *"the raster rid and our stored room.id are DIFFERENT id spaces on
real devices (empirically verified)"* against **its own commit `c4207b9`** describing
*"rid==room.id==room_names identity"* — same commit, opposite claims. Resolving it took git
forensics plus the observation that only Eufy HAS a raster. **Recreating from code reproduces the
CONTRADICTION, not the resolution** — and the doc names where that leads: an auditor "fixing"
correct code to satisfy an unsourced comment.

  ⟵ **DISPOSITION 2026-08-21 — FIXED-UNPROVEN.** the stale bindings/map.js:376-377 palette-slot cite was converted to anchor #CNYVDQ9S, which resolves
  **⚠ THE LEDGER'S MECHANISM IS WRONG — repair from THIS, not from the text above:** Two small numbers in the ledger are already stale: the real palette-slot expression is at bindings/map.js:392 (not 389, as the ledger asserts), and the anchor that replaced the cite sits at :378.
## FRONTEND CORPUS VERIFIED — 14 docs, agent pass 2026-08-21

**394/465 claims verified = 15.3% drift.** SOLID 2 (`dashboard-card`, `furnished-render`) /
MINOR_DRIFT 10 / SIGNIFICANT_DRIFT 2 (`styles-system`, `i18n-system`).
⚠ **THE EARLIER 'THE FRONTEND IS DURABLE' READ WAS A BIASED SAMPLE** — the six hand-checked docs
were CHRIS'S PICKS and four came back clean. Selection, not a property of the corpus.

**FAILURE KINDS:** CONTENT-ERROR 29 · LATE-ADDED-VARIANT 23 · STALE-LINE-CITATION 12 ·
STALE-TRANSCRIPTION 3. Severity: 3 HIGH / 26 MED / 38 LOW.

**THE DECOMPOSITION (total drift = claim count x P(drift|claim)) — MEASURED:**
  `corr(claims_checked, ABSOLUTE failures) = +0.52`  ·  `corr(claims_checked, drift RATE) = +0.05`
  Per-claim rate is INDEPENDENT of doc size, so **length is GUILTY for total defect count** — 2x the
  claims accrues ~2x the defects even though individual claims are no more fragile. But rate spans
  **0%-38%** (fewest-claims doc `themeable-map-palette` has the WORST rate; `furnished-render` has 34
  claims and zero), so claim KIND is live too. Both terms matter. ⚠ I earlier stated this INVERTED
  ("equal rates means length is innocent") — wrong; GPT caught it.

**ALL THREE HIGHs ARE ONE SHAPE: A LIFTED LIMITATION STILL DOCUMENTED AS CURRENT.**
  `module-reference` says `clearRoomAccessGraph` is a live bug (FIXED, `actions/rooms.js:553-562`);
  `theme-system` says deleting a built-in theme is undone on restart (now TOMBSTONED,
  `themes/manager.py:425-433`); `i18n-system` says OpenDyslexic maps to English only (TWELVE locales,
  `i18n/font-store.js:60-62`). A reader concludes a working feature is broken.
  ⚠ **THIS BREAKS 'RATIONALE IS THE DURABLE CLASS'.** These are reasoned rationale and they rotted.
  The real split: *"we chose X over Y because Z"* is a historical decision and stays true forever;
  *"X doesn't work because Y"* is a claim about a CURRENT LIMIT and dies the moment Y is fixed —
  and nobody goes back. **A doc template must invite capability and contract, never current
  limitation.**

## D39 — `check_doc_citations.py` CANNOT SEE JAVASCRIPT AT ALL
Its symbol index is built with `base.rglob("*.py")` and Python's `ast` module. There is no JS
parser. **All 240 frontend line citations are unresolvable to it** — consistent with the 3-strong /
38-weak of 41 measured 2026-08-20, which were the Python-targeting ones.
**THIS EXPLAINS THE CORPUS ASYMMETRY:** frontend carries **12.0 line citations per doc** against the
backend's **1.4** (240 vs 45 absolute). The backend's were pruned by a gate that could see them; the
frontend's were invisible and multiplied. The unifying finding inside the citation gate itself.

**THE REPAIR IS SMALLER THAN 240.** Triaged: **120 already name a symbol beside the citation** — fix
is DELETE THE LINE NUMBER, the symbol is the anchor. The other 120 point inside functions or at
inline definitions (`_bindToasts` at `bindings/index.js:149` — no module, no export, nothing to
name), which is exactly what `CN` exists for. **`CN` HAS NO REGISTRY BY DESIGN** (`test_replica_
ratchet.py`: *"CN (code notation) has no registry by design, so requiring one would invent a rule"*),
so it costs one mint plus one comment line, cited as `path/file.js#CN……`. Already live in five docs.
**LADDER: symbol name (free) > CN anchor (cheap, no registry) > IN/RN (registry + a rule + a
consequence).** Most of the 240 stop at rung one.

## THE DOC RULE THAT FALLS OUT: CITE IDENTITY, NOT COORDINATES

**"Cite identity, not coordinates. Add coordinates only when identity cannot express the
distinction."** Corollary, made concrete by the 50/50 split below: **precision beyond need is a
liability.** Half the frontend citations already carry the durable locator NEXT TO the perishable
one — they say it twice and one copy rots. They are not careless; they assert more location
information than any reader needs.

**REMEDIATION LADDER (only rung 4 needs registry machinery):**
  1. existing named symbol -> **delete the physical line number**. No mint, no infrastructure.
  2. nameable but unnamed -> cite the function/class/constant explicitly. Still no minted notation.
  3. exact interior location where the enclosing symbol is insufficient -> **`CN`**. Cheap,
     deliberately non-semantic, **no registry by design**.
  4. an actual rule or replica relationship -> `IN` / `RN`. Only these earn a registry entry and a
     stated consequence.

## D39b — `src/` IS NOT IN THE CITATION CHECKER'S SCOPE AT ALL
`SOURCE_ROOTS = ("custom_components", "scripts", "tests", "harness")`. **The frontend tree is not
merely unparsed — it is UNLISTED**, so the gate cannot answer even *"does this file exist?"* about
any of the 240 frontend citations. Worse than the missing JS parser (D39) and the same root cause:
a gate reporting clean because it cannot look.

⚠ **CORRECTION — I overstated this once already.** I wrote that symbols are "the only form anything
can check" for JS. **Nothing about a JS citation is machine-checked today** — a JS symbol and a JS
`CN` anchor are equally invisible to a Python-only index. Symbols are better on INTRINSIC grounds
(stable under line shifts, grep-findable by a human), not verifiable ones. Letting "better" slide
into "checked" is the exact conflation this campaign exists to catch. GPT caught it.

**THE FIX IS SMALL — MEASURED, NOT ESTIMATED.** `nearby_symbol(text, upto, syms)` is already
LANGUAGE-AGNOSTIC (it consumes a symbol dict); only `symbol_ranges()` is Python-bound via `ast`. So
the extension is: add `"src"` to `SOURCE_ROOTS` + one `symbol_ranges_js()` returning the same
`dict[str, list[(start,end)]]` shape. Nothing downstream changes.
A **crude regex index built in seconds — 5,278 symbols across 275 files — resolves 58% of the
symbol-naming citations immediately.** The misses are ONE pattern, not a tail: `_bindMap`, `_on`,
`_onAll` are PROTOTYPE-MIXIN methods (assigned, not declared — a deliberate architecture
`architecture-overview.md` documents). Two more regex patterns should clear most. `scrollTop` is a
CORRECT miss (a DOM property, not a symbol).
**KEEP THE CHECKER DUMB.** It only needs: does the file exist · does the named symbol exist · does
this `CN` fragment appear exactly once · has a cited anchor disappeared · is a bare `:123` citation
deprecated. Do NOT build a semantic JS analyser to delete line numbers.

**TRIAGE OF THE 234 js/mjs FRONTEND CITATIONS:** 65 resolve against the crude index today (rung 1) ·
46 name a symbol the regex misses (fix regex, then rung 1) · 119 name no symbol (rung 2 or 3) ·
**4 cite a file that does not exist in `src/` — genuine broken references.**

## RETRACTION + a HARD CONSTRAINT on the proposed citation gate

⚠ **RETRACTED: "4 genuine broken references" in the frontend corpus. The real number is ZERO.**
Every hit was my own extraction error, four different ways in one sitting:
  - the four -> `scripts/build-card.mjs`, a real file; I had globbed only `src/`
  - `guide-frequency-translations.js` -> my regex alternation matched `.js` INSIDE `.json`
  - `badge-marks.js` / `theme-preview-registry.js` / `i18n-accepted-english.json` -> all present;
    `find ... | head -1` returned a `.claude/worktrees/` copy first and I read it as the only one
  - `my-panel.js`, `animals/myanimal.js` -> deliberate TUTORIAL PLACEHOLDERS
  - `harness/dist/mount.js` -> git-ignored build output (same class as C52)
**Pattern across all four: I keep calling a doc wrong when the fault is my search scope.** Third time
today. Establish the authoritative artifact AND the full search scope before reporting a defect.

**BUT CHRIS'S RECALL WAS RIGHT AND IT FOUND THE REAL LESSON.** He asked whether the dead citations
pointed at Map Bounds Review, *"one of the few pieces I've actually completely removed"*. Bounds
Review IS still named in `module-reference.md` twice (lines 205, 217) — and it is named **CORRECTLY,
as a deletion**: *"its `src/` importers (the Map Bounds Review renderer + `styles/mapping-review.js`)
were deleted in the mapping shelve — only the render harness still consumes it"*.
**That sentence is LOAD-BEARING.** `badge-marks.js` has no `src/` importer, so it reads as dead code;
the only thing preventing its deletion is this doc explaining why the orphan exists. Delete the
sentence and someone deletes the file and breaks the render harness.

## D40 (DESIGN CONSTRAINT, not a defect) — "does this file exist?" IS NOT A SAFE DUMB CHECK
The proposed JS-aware citation gate treats file-existence as the safest mechanical question. It is
not. A doc legitimately names a path that does not exist in **three** cases:
  1. **tutorial placeholders** — `check_doc_citations.py` already carries a `PLACEHOLDERS` set
     (`file.py`, `path/to/file.py`, `module.py`) for exactly this;
  2. **deleted-thing references** — *"X was removed, which is why Y is orphaned"*;
  3. **build output** — `harness/dist/` exists only after a build (CI never builds; see C52).
**Case 2 is the dangerous one: it attaches to the HIGHEST-VALUE sentences in the corpus** — the ones
explaining why something looks wrong but is not. A gate that flags those trains authors to delete the
explanation, which is the opposite of what the campaign wants. **Needs an escape hatch** (a
was-deleted/removed-in proximity test, or an explicit marker) before file-existence can be enforced.

## INVARIANT ABLATION SWEEP — COMPLETE 2026-08-21. 27 of 33 DEFENDED, 6 HOLES.

Chris's ruling: *"if it's a claim that must be true, which is an invariant, it should be tested."*
Method: break the invariant on disk, run the FULL suite, see what goes red — **ablation as the
SEARCH, not just the oracle** (his refinement: *"if we can't find its dedicated test"*). 31 ablations
+ 2 pilot, **0 patch failures**, ~2.7 h unattended. Raw data: `_invariant-ablation-results.json`.

**ALL 3 `PN`s came back CANNOT_ABLATE from three independent agents** — testability IS the IN/PN
discriminator, confirmed empirically.

### THE 6 HOLES — **ALL CLOSED 2026-08-21.** Ten tests, each PROVEN to bite.

Method: six agents in isolated worktrees, each required to produce RED BEFORE GREEN —
baseline pass, apply an ablation, the new test must FAIL, restore byte-exactly, pass again,
with real pytest output captured at each step. Then a separate adversarial pass that ran
nothing and only read, hunting the `[DE-W1]` shape. Five survived. One did not, and it is
the finding worth keeping:

⚠ **`IN5ATBW9` WAS REFUTED ON THE RULE, NOT ON THE TEST.** The test was sound by every
check — real manager, real disk, `create_autospec` on real bound methods, positive
assertions, and the author HAD run the empty/None/absent ablations. It failed for a reason
no care in the writing would catch: **the invariant enumerates FOUR steps and the test's
ledger started at step two.** `rebuild_all` runs one line after the archive write, inside
the manager method, and nothing observed it. The refuter proved it by deleting
`self.rebuilder.rebuild_all(...)` from `exclude_learning_job` — both tests stayed GREEN
while all four derived files went stale and the response still said "stats rebuilt".
Extended here to a four-step ledger and re-proven against that exact attack (RED with
`ran ['accumulators','invalidate','preload']`, restored sha256-identical, GREEN).

**This is `f/partial_guard_blind_spot` one level up: not a guard that stops a line short,
but a TEST whose window opens a step late.** It is only visible by reading the RULE and the
TEST as two separate claims and diffing them — no coverage number, no mutation score and no
degenerate-input check can see it, because the test is correct about everything it looks at.
Fixing it also upgraded what the ordering assertion proves: from "the sequence runs" to
"the sequence runs AFTER the write", which is the clause the invariant rests on.

    INNPA4ZV  3 tests  tests/integration/test_access_graph.py            (+4 degenerate ablations)
    IN5TNKMD  1 test   tests/integration/test_cancel_chokepoint.py
    INYA5T84  2 tests  tests/integration/test_services_adapter_config.py
    INKR1TW7  1 test   tests/integration/test_init_provider_readiness.py (new file)
    INJW5J2A  3 tests  tests/unit/test_learning_history_store.py
    IN5ATBW9  2 tests  tests/integration/test_learning_processing_toggle.py

⚠ `INYA5T84` was previously written off as DECORATIVE — "its predicted test exists and stays
green". That was wrong. It was not decorative; the existing test asked the wrong question.
Two tests now defend it, one checking that registration severity is decided by the config's
SOURCE — the half nothing was looking at.

Production untouched throughout: every ablation restored byte-exact, verified by sha256.

### THE `NEVER int()` RULE — TWO live implementations and one DEAD one (corrected 2026-08-21)

The clearest evidence in the repo for why `RN` matters more than `IN`. Ablation of each copy,
full suite each, byte-exact restore verified by sha256:

    adapters/eufy/vocabulary.py:564  _exact_error_code   3 FAILED   <- DEFENDED
        test_unknown_never_invalidates[3.7]
        test_unrecognised_is_unknown_not_robot[3.7]
        test_unrecognised_is_unknown_not_robot[2112.9]
    core/error_tracker.py:314        _exact_int          4472 passed, NOTHING RED
    core/error_tracker.py:~287       string variant      nothing red either

**The rule:** never `int()` a float — `int(3.7)` is 3, a real Eufy code (SIDE BRUSH STUCK), so a
malformed reading classifies as a genuine fault and gets SUBTRACTED from cleaning time. The
consequence is dated and real: alfred `job_2026-08-01T23-23-35` cleaned 4 m² in 360 s and
recorded `cleaning_time_seconds` 0, `used_for_learning` true — the model learned that 4 m²
takes no time.

**The adapter tests are not incidental.** They are parametrised on `3.7` and `2112.9` — the exact
values the comment names — and their docstrings restate the consequence. Someone did this
properly. At ONE of the three sites. The core copies inherited the comment, the reasoning and
the worked example, and none of the tests.

⚠ **THIS IS THE FALSE-ASSURANCE SHAPE.** A search for "is this rule tested?" finds three tests
named for it and answers yes. Edit the adapter copy → red, fixed. Edit either core copy →
ships. The existing tests make the untested siblings HARDER to notice, not easier.

⚠ **AND THE COPIES HAVE ALREADY DRIFTED IN EXPRESSION.** Three implementations, three shapes:
the adapter names its parameter `code` (the others use `value`, which is why a literal search
for the guard found only two of three), and `error_tracker.py:~287` handles empty/whitespace
EXPLICITLY — *"absence, not a code named ''"* — while the other two rely on `int("")` raising.
Same behaviour today; different reasoning recorded at each site.

⚠ **THE CLASSIFICATION PASS DID NOT SEE THEM AS ONE RULE.** In `00b-h` they appear three times
under TWO verdicts: owed ruling #2 (`vocabulary.py:564`), owed ruling #9 (`error_tracker.py:285`)
and **STALE** #4 (`error_tracker.py:311`). One rule, judged three times, inconsistently — the
replica problem reproducing itself inside the audit of replicas.

⚠ **CORRECTION, SAME DAY, AND IT DISSOLVES THE RULING.** "Three copies" was wrong on both
counts. `error_tracker.py:~287` (`_code_key`) is NOT a copy — it returns `text.lower()` for
non-numeric input, a code-OR-ENUM-KEY coercion that exists so brands whose faults are strings
(`bumper_stuck`) can declare tables at all. It shares the two int guards DELIBERATELY and says
so. And `_exact_int` was not an undefended invariant — **it was UNREACHABLE**, the only caller of
which (`_int_set`) had no callers itself. Ablation cannot tell "unguarded" from "unreachable":
both read as nothing-red. See C18 — both deleted.

So the real picture is ONE live implementation of the exact-int rule (`_exact_error_code`, in the
Eufy adapter, defended by 3 tests) plus one live RELATIVE that shares its guards (`_code_key`, in
core, defended by the `live:RB-ERR-1` tests). **No replica, no ruling owed, nothing to unify.**

**What the episode is actually worth keeping:** One implementation, the
adapter tests pointed at it, `RN` unnecessary because the replica stops existing. Alternative if
the copies are deliberate: declare an `RN` at the adapter (the defended primary) and add
core-side tests. NOT APPLIED — this is a real code change and a ruling is owed.

#### The holes as originally recorded
  - **`INNPA4ZV`** — pre-joining a list with the English `", "` bakes an untranslated separator.
    `no string without i18n` at invariant level; 18 locales ship past it silently. **Fix first.**
  - **`IN5TNKMD`** — the chokepoint re-checks a stale snapshot instead of the store. **A cancel race.**
  - **`INYA5T84`** — the production entry point stops running the schema walk ENTIRELY.
    ⚠ **Its predicted test EXISTS and stayed green**: `tests/integration/test_services_adapter_config.py`.
    A test named for the thing that does not test the claim — the DECORATIVE-TEST shape, found by
    PREDICTION rather than by reading. This is the strongest argument for the method.
  - **`INKR1TW7`** — re-detection inline at setup caches a cold-registry answer forever.
  - **`IN5ATBW9`** — a write reaches four derived files but skips the incremental index.
  - **`INJW5J2A`** — memo never fires; six `mkdir` syscalls per call on the event loop.
    (A performance invariant — plausibly the one genuinely expensive to gate.)

### ⚠ 'DEFENDED' IS NOT UNIFORM — 12 of 25 HANG ON EXACTLY ONE TEST
  `INT79PB7`, `INFJXSM4`, `INJ7VXE7`, `INMKEHPQ`, `INQ619A6`, `IN76GE4W`, `INZKT2QF`, `INGZFYXX`, `INNJ6SGC`, `INPQ6ZE7`, `IN1FX8EH`, `INJBNQ2Q`
  Against `INSJM6KC` with 28 red and `IN11T0FS` with 18. **Delete that single test — including via a
  refactor that looks unrelated — and the invariant goes silent with no signal.** The real
  distribution is 6 undefended / 12 single-threaded / 13 solidly covered, not 27-vs-6.

### WHAT IT PRODUCED
**The backfill map.** All 27 defended invariants now have a KNOWN test file, discovered rather than
searched for — `docs/testing/` was never needed. Backfill = one docstring line per test naming its
token (the `INKV8ZQD` convention, already in-tree at
`tests/integration/test_services_unmanaged_vacuum.py`). **The link is still 1 of 36; the coverage is
27 of 33. Those are different numbers and the gap between them is pure bookkeeping.**
⚠ **A gate asserting every entry names a test must land AFTER the backfill**, or it fails 35/36 on
day one and gets deleted for crying wolf — the exact failure `test_replica_ratchet.py`'s own
docstring warns about.

## RULING 2026-08-21 — THE ANCHOR SYSTEM IS THE UNIFYING SYSTEM, AND THE MIGRATION IS ADDITIVE

Chris: *"the anchor system will be our unifying system... one family, the XN notation system, tests
could be TN."* **Agreed, and the scheme already specified almost all of it.**

**SEVEN IDENTIFIER SCHEMES ARE LIVE; ONE IS ENFORCED.** notation anchors (87 distinct / 717 uses,
enforced by `doc_anchor.py` + ANC-1..3 + RR-1..4) · `[XX-N]` test tags (~2,877 / 6,511) · `RP-NNN`
(63 / 1,655) · `RF-NN` (47 / 391) · `live:XXX-N` (34 / 271) · `DR-XXX-N` (35 / 131) · `QN` (~16,
⚠ contaminated — `Q\d{1,2}` matches the Roborock **Q5 Pro**, which is itself an argument for one
grammar: an ambiguous scheme cannot even be COUNTED).

**THE MAPPING IS ALREADY IN THE DESIGN. Only ONE new prefix is needed.**
  `IN` invariants · `RN` replicas · `CN` code sites · `PN` principles — all live.
  **`HN` — reserved, DEFINED, unused — is exactly `RP-`/`RF-`/`live:`/`DR-`**: *"how or why a
  behavior, decision, migration, REPAIR, or architectural constraint came to exist."* Its own
  definition also kills the ordering objection I raised: *"Historical meaning can accumulate without
  requiring the implementation anchor itself to encode chronology."*
  **`TN` is the one genuinely new class** (tests). One dict entry at `doc_anchor.py:99`.
  Free under the `?N` convention (17): AN BN DN EN FN GN JN KN MN NN QN TN VN WN XN YN ZN.
  Alphabets: suffix `0123456789ABCDEFGHJKMNPQRSTVWXYZ` (32, Crockford — I/L/O/U excluded);
  prefix `ABCDEFGHJKMNPQRSTVWXYZ` (22 letters, no digits). 484 namespaces x 1,073,741,824 each.

**THE DECIDING ARGUMENT — `doc_anchor.py`'s FIVE LAYERS, and it resolves the whole debate:**
    prefix            identifier class
    opaque suffix     permanent identity
    descriptive name  current taxonomy — `live:ENT-13`, MUTABLE, may be re-cut freely
    prose             the claimed meaning and contract
    code              the current implementation
*"`live:ENT-13` can evolve into something entirely different, or be retired. `CN7K3M9Q` does not
care. That separation is what makes the anchor a DRIFT-REVIEW SEAM."*
**So `[SR-4]` / `RP-031` / `live:ENT-4` were NEVER COMPETITORS to the anchor system — they are LAYER
THREE, and the design wants both.** Readable name and permanent identity sit side by side.

**CONSEQUENCE, and it is large: THE MIGRATION IS ADDITIVE, NOT A REWRITE.** We both assumed 2,877
test tags get converted. They do not. `[SR-4]` stays; a `TN` anchor is planted BESIDE it only where
something needs to cite that test durably — today that is the **27 defended invariants wanting their
defender named**. Twenty-seven anchors, not two thousand eight hundred.

**REJECTED: digits in the suffix.** A `PP+DD+4random` token still gives 104,857,600 per prefix and
collisions are moot (`--mint` retries), but it pushes MUTABLE TAXONOMY into PERMANENT IDENTITY —
the exact merge the layer split exists to prevent. `doc_anchor.py` is blunt on the failure mode:
rewriting a key "silently changes an identity and breaks every citation pointing at it, in a way
that looks like a cleanup."

## D41 — THREE CONTENT ERRORS FOUND BY REFUSING TO CONVERT BLIND
Surfaced while resolving the 21 collapsing citations. **Each would have been made PERMANENT by
minting an anchor at the cited line.**
- **`design/shipped/eufy-native-transition.md:110`** cites `core/manager.py:85-110` for *"the
  `_PHASE_*` timing constants"*. Line 85 is an **import block**; the constants are at **133-158**.
  Fix is a symbol cite (`::_PHASE_SETTLE_SECONDS`), not an anchor.
- **`22-adapter-config-reference.md:1985`** says *"base_station at `:3950`, map_bounds at `:3961`"*.
  **NEITHER STRING EXISTS ANYWHERE IN `core/manager.py`** (grep count 0 for both).
- **`29-roborock-adapter.md:126`** names `core/manager.py::get_dashboard_snapshot` beside
  `core/manager.py:3949-3963`. That range is inside **`get_start_status`** (def at 3792);
  `get_dashboard_snapshot` starts at **5632**. The doc names the wrong function.

**RULE EARNED: NEVER CONVERT A CITATION YOU HAVE NOT VERIFIED.** A durable citation to a wrong place
is worse than a fragile one — **the fragility was the signal**. Converting first freezes the error
into a form that never rots and therefore never gets caught.

### D41 — RESOLVED 2026-08-21, and ONE THIRD OF IT WAS MY ERROR

⚠ **RETRACTED: "base_station and map_bounds exist nowhere in `core/manager.py`".** They exist as
`supports_base_station` (5729) and `supports_map_bounds` (5740). My grep was `base_station` —
**`` cannot match inside `supports_base_station` because `_` is a word character.** Fifth
scoping/regex error of the session, and the fourth time a doc I called wrong was right.

**What was ACTUALLY wrong: the line numbers, by ~1,780 lines.** Both docs name the right function
(`get_dashboard_snapshot`) and the right symbols; they cite `:3949-3963`, which lands inside
`get_start_status` (def 3792). `get_dashboard_snapshot` is at 5632, its return dict at 5911-5912.

**FIXES APPLIED (2 mints, 4 doc edits, all verified — 70 tests green, anchors 84 declared / 95
cited / 0 problems):**
- [FIXED-UNPROVEN] **D41a** `design/shipped/eufy-native-transition.md` cited `core/manager.py:85-110` for the
  `_PHASE_*` timing constants. Line 85 is an **import block**; the constants are at 133-158.
  → minted **`CN3AX4QG`** at the block head (a group of 6 constants is a real target with no single
  symbol — exactly the `#anchor` case). `#_PHASE_SETTLE_SECONDS` was NOT usable: 2 occurrences.
  ⟵ **DISPOSITION 2026-08-21 — FIXED-UNPROVEN.** eufy-native-transition.md's import-block cite for the _PHASE_* constants is now anchor #CN3AX4QG at the real block head
- [FIXED-UNPROVEN] **D41b/c** `22-adapter-config-reference.md` + `29-roborock-adapter.md` → `#CN585YGW` (which
  ALREADY EXISTED at 5728 and was already cited correctly by `21-adapter-system.md:336` — two docs
  simply never got updated) and a new **`CN5APNA9`** at the `supports_map_bounds` derivation.
  ⟵ **DISPOSITION 2026-08-21 — FIXED-UNPROVEN.** 22- and 29- now cite #CN585YGW/#CN5APNA9 inside get_dashboard_snapshot, but 21- (called 'already correct') carries two dead line cites
  **⚠ THE LEDGER'S MECHANISM IS WRONG — repair from THIS, not from the text above:** The parenthetical '`#CN585YGW` … was already cited correctly by `21-adapter-system.md:336` — two docs simply never got updated' is only half true and hides a live residual. 21-adapter-system.md:336 does cite `core/manager.py#CN585YGW` correctly, but the SAME SENTENCE (lines 337-339) still carries two bare line citations, both now dead: `supports_map_bounds` (`:4993`) — manager.py:4993 is a BLANK LINE, the real derivation is at 5745 under anchor CN5APNA9 — and `supports_va_render` (`:5113`) — line 5113 is `total += int(est.get("seconds") or 0)` inside an unrelated estimate tally, while `supports_va_render = isinstance(_adapter_cfg.get("map_render"), dict)` is at 5864. So it was THREE docs ne…
- [FIXED-UNPROVEN] **D41c second half:** *"no card surface consumes it for either brand today"* was evidenced by
  `core/manager.py:3945-3947`. That is a claim about the CARD, cited to the backend.
  **The claim is TRUE — `supports_map_bounds` has ZERO hits in `src/`** — so the claim stayed and
  the citation was removed. **An absence is not citable to a line.**

**METHOD NOTE, the reason to keep doing it this way:** all three were found by REFUSING TO CONVERT
BLIND. Every one would have been frozen into a permanent anchor pointing at the wrong place. The
rule holds: *never convert a citation you have not verified — the fragility was the signal.*

  ⟵ **DISPOSITION 2026-08-21 — FIXED-UNPROVEN.** The card-absence claim's bogus backend line citation is gone from both docs, the anchors resolve, and the claim itself is still true — but no gate would catch a reversion.
## FULL FRONTEND PASS — 12 docs, completed 2026-08-21 after sign-off. NOT APPLIED.

Raw data: `.claude/notes/_frontend-pass2-verified.json` (per-doc, with `evidence` on every entry).
12 agents, one per doc, each re-deriving its recorded findings from code and judging every citation.

**FINDINGS: 52 CONFIRMED · 1 ALREADY_FIXED · 0 WRONG_FINDING · 0 UNSURE.**
**PLUS 30 NEW** (16 MED / 14 LOW, no HIGH). **So the real defect count for these 10 docs is 82, not 53.**
**CITATIONS: 29 CORRECT · 5 REPLACE · 1 ANCHOR_NEEDED** — i.e. **29 of the 35 mechanically-converted
citations were right**, which retires that worry.

⚠ **THE 0 WRONG_FINDING IS THE NUMBER TO DISTRUST FIRST.** The prompt named WRONG_FINDING a valuable
answer and cited two agent errors caught the same day, and still not one of 53 came back. That is the
confirmation-bias signature. **I hand-checked four independently and all four were exact**: 17 `draft`
locales (doc said seven), 25 `VacuumCardRenderers.prototype` mixins, 14 exports in `styles/fonts.js`,
3 modules in `src/textures/`. Two more (`clearRoomAccessGraph`, the textures count) I had already
verified myself earlier the same day. So the rate looks GENUINE — but it was checked, not assumed.

**WHY THE COUNT GREW.** The first pass sampled ~33 claims per doc; this one worked a supplied list AND
looked further. 30 new defects in docs already audited once is [[feedback_drift_hides_in_output_shapes]]
exactly: *audited-once does not persist*, and a second look after hardening still finds things.

**WORST CONFIRMED (all with `old_text`/`new_text` ready to apply):**
- `module-reference.md` **12** — incl. `clearRoomAccessGraph` documented as a LIVE BUG that is FIXED (a
  reader would chase a ghost or 'fix' correct code); `src/textures/` called a two-module pair when it is
  three; `styles/fonts.js` described by 2 of its 14 exports, omitting the entire USER DROP-IN FONT intake
  gate (`sanitizeUserFontDef`, `loadUserFonts`); "the seven drafts" against 17.
- `render-harness.md` 6 · `theme-system.md` 6 · `custom-segment-composer.md` 5 · `saved-zones.md` 5 ·
  `state-management.md` 5 · `card-topology-and-bundles.md` 4 · `i18n-system.md` 4 ·
  `themeable-map-palette.md` 4 · `architecture-overview.md` 1.

⚠ **NOTHING WAS APPLIED.** Chris had signed off; 82 unsupervised content edits is precisely the move
that produced four failed passes earlier the same day. Every CONFIRMED entry carries a verbatim
`old_text`/`new_text` pair, so applying is mechanical once he says go — but the `old_text` strings must
be checked for uniqueness first, and a sample re-verified, exactly as the citation pass was.

### C53 — **FIXED 2026-08-21 (495e2642).** `_HA_ACTIVE_VACUUM_STATES` existed twice in core

Collapsed to one public `const.py::HA_ACTIVE_VACUUM_STATES`, imported by `core/manager.py` and
`jobs/job_monitor.py`. ⚠ **THE BACK-TRACE CHRIS ASKED FOR BEFORE LANDING CHANGED WHAT WE KNOW:**
no adapter declares `active_vacuum_states`, and it is NOT a key in `ADAPTER_CONFIG_SCHEMA`'s
vocabulary section — a schema that REJECTS undeclared keys. So core's ownership is enforced by a
GATE, not merely asserted in comments, and there was no third source to reconcile. That also
retroactively settles C19: the wiring option was not just boundary-inverting, it was BLOCKED.

Original finding, kept for the record:

Not previously recorded; found while resolving C19 and left unfixed deliberately.

    core/manager.py:164        _HA_ACTIVE_VACUUM_STATES  {cleaning, returning, paused, error}
    jobs/job_monitor.py:29     _HA_ACTIVE_VACUUM_STATES  {cleaning, returning, paused, error}

Byte-identical sets of the same four HA-platform states, in two files, each with its own comment
explaining that these are platform-universal. `job_monitor`'s copy is the DEFAULT for its
`active_vacuum_states` parameter (:179); `core/manager.py` passes its own copy down the same
parameter (:3589-3590, :3634) — so on the live path the manager's copy WINS and job_monitor's is a
fallback that production never reaches.

**This is `RN`-shaped, not dead code.** Both are live by declaration, they must agree, and nothing
makes them agree. If HA adds or renames a vacuum platform state, updating one leaves the other
silently wrong on whichever path uses it. `f/centralize_question_not_vocabulary`'s ladder says
CONSTANT here — one definition, imported by both — which is the cheapest rung and the obvious fix.

⚠ **Deliberately NOT fixed in the C19 commit.** C19 removed a brand-file category error; collapsing
two core copies is a different change with a different blast radius, and bundling them would make
the C19 diff say something it does not mean. Also note the irony worth recording: C19's whole
argument was that the platform set belongs to core and not to a brand — and core holds it twice.

