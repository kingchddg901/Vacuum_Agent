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
| `[OPEN]` | 63 | still present in the tree exactly as described |
| `[OPEN-DRIFTED]` | 4 | real, but **the text below it is WRONG** — a corrected-mechanism line follows the entry |
| `[NEEDS-RULING]` | 0 | blocked on a decision, not on work |
| `[FIXED]` | 3 | gone, **and** a named test goes red if it returns |
| `[FIXED-UNPROVEN]` | 9 | gone, but nothing would notice if it came back |
| `[ACCEPTED]` | 2 | **a real defect, ruled not worth fixing, and stated AT THE SITE** — not a backlog item |
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
  - **2026-08-23: the MIGRATION half landed** (`D2`, `core/battery_aggregates_migration.py`). C17 was correct only for buckets that start empty; an upgraded bucket kept an all-time denominator against a numerator restarting at 0.0. Measured ARMED on the live install — the next run would have published 0.0 and 0.0066 %/min against honest 0.292 and 0.4613 — and unfired only because C17 had not been deployed to that box. See `.claude/notes/REPAIR-BACKLOG.md`.
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
- [ACCEPTED] **C30 nothing ever deletes a stall capture.** Zero `rmtree`/`shutil` hits in the package. The PNG
  survives disarming the switch, deleting the vacuum, and removing the integration.
  ⟵ **DISPOSITION 2026-08-21 — NEEDS-RULING.** The finding is factually correct — nothing deletes the capture — but whether that is a defect is a retention policy call, and the gap is not stall-capture-specific.
  **⚠ THE LEDGER'S MECHANISM IS WRONG — repair from THIS, not from the text above:** The entry frames this as a stall-capture gap; it is the whole on-disk learning tree. `async_remove_entry` leaves `<config>/eufy_vacuum/learning/` entirely intact — the stall PNG, the pose ring (pose_store.py, which has its own age-based expiry at :165 but no removal hook), the job records and the battery store all survive integration removal by the same omission. Any ruling should be made once, for the tree, not for the PNG.
  **✅ RULED 2026-08-22 — NO PURGE. The tree is NOT MANAGED FOR DELETION, and that is now
  stated at the site and in `02-ha-integration.md`.** The data is the user's own recorded
  history of their own home, it is the only copy, and nothing in HA would put it back, so
  the recoverable outcome wins: inherited data can be cleared by hand, a purge cannot be
  undone. Deleting `<config>/eufy_vacuum/` is a documented manual step.
  **The inherit-on-reinstall risk is what made this safe to rule:** learned rows are keyed
  by `(map_id, room_slug)`, and a recreated map takes a new `map_id` in practice — so stale
  rows go INERT rather than silently informing estimates.
  **⚠ WHAT WAS ACTUALLY WRONG HERE WAS THE DOCSTRING, and it was wrong under either ruling:**
  `async_remove_entry` said *"Clear persistent storage when the entry is deleted"* while
  clearing one of two layers. Fixed. The entry's stall-capture framing is also too narrow —
  it is the whole tree, 1.9 MB across four directories on the live box.
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
- [OPEN] **D36 `docs/dev/design/shipped/notation-anchors.md` — the SPEC and the REGISTRY disagree about `PN`,
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
  **✅ SEMANTIC HALF RULED 2026-08-22 — `PN` IS THE POINTER; the spec was right and the
  registry had drifted.** Confirmed by the spec's own worked example `PN3W7F6D`, which is used
  as a pointer — definition and example agreed with each other, and only the registry
  diverged. A THIRD divergent copy was found during the fix: `doc_anchor.py`'s
  prose-declaration comment also defined PN as the no-code-site class, so tooling and registry
  agreed against the spec.
  **NEW CLASS `EN` (enforcement notation) minted for the class the registry actually held:** a
  rule that binds a PERSON, not the program. Discriminator is positive — WHO BREAKS IT? The
  three rules were RE-MINTED, not re-prefixed (`PN1E8AZT`→`ENMKYC3F`,
  `PNWJZYYR`→`ENFV9F37`, `PNN14JRN`→`ENQZV7VH`), so a stale old token cannot keep looking
  well-formed. All live citations swept, including `_ablate_ratchet.py` which pins one and
  would have broken silently.
  **⚠ STILL OPEN — THE COUNT HALF, WHICH IS AUTOMATION, NOT A RULING.** Every line of the
  status block is false, not just the two D36 named: `CN` claims 9 (is 138), `IN` claims 1 (is
  35), `RN` claims 2 (is 37), and `SN`/`HN`/`PN` are claimed "reserved and unused" (are 2/1/4).
  ⚠ **`doc_anchor.py --show` does NOT regenerate this** — it takes a single token. There is no
  count-producing command; that is new code.
  **A PREREQUISITE WAS FIXED ALONG THE WAY:** a counter written before 2026-08-22 would have
  counted `check_bn_boundaries.py`'s self-test fixtures as real anchors — they were minting
  phantom BN declarations and all 4 of `--check`'s problems. Fixtures are now assembled at
  runtime so the file spells no anchor; `--check` reports 0 problems and BN declarations are
  genuinely 0.
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

### C54 — **FIXED 2026-08-23.** Session `avg_rate_per_min` divided a guarded sum by an unguarded count

Found 2026-08-22 during the battery doc pass; verified directly against source and reproduced
with the repo's own `.claude/notes/_proof_battery.py`, which drives the real `_update_session`
and `_close_session`.

`battery/manager.py::BatteryHealthManager._update_session` increments `session["samples"]`
for **every** charging sample, then increments `rate_sum` (and `rate_min` / `rate_max`) only
inside `if rate_per_min is not None and rate_per_min > 0`.
`battery/manager.py::BatteryHealthManager._close_session` computed `avg = rate_sum / samples`.

> **FIXED 2026-08-23.** A partnered `rate_samples` is incremented in the same branch as
> `rate_sum`, and `_close_session` divides by it. Re-running **this entry's own proof script
> unchanged** now reports `1.000 %/min`, understated by 0%. A session in flight across the
> upgrade has no `rate_samples` and closes `None` rather than falling back to `samples`, which
> would have reinstated the value being removed. Tests `BM-29`/`BM-30`/`BM-31`, ablated four
> ways. Doc 16 §5 and `docs/testing/subsystems/08-battery.md` updated; see
> `.claude/notes/REPAIR-BACKLOG.md`. **Note the sanity line the proof prints:** the old number
> was total gain over total duration (0.476), which is a real statistic — just not the one
> `avg_rate_per_min` names, and not one comparable to the `min`/`max` printed beside it.

    charging samples counted (session.samples) : 21
    samples that produced a rate               : 10
    rate_sum                                   : 10.000
    TRUE mean of observed rates                : 1.000 %/min
    reported avg_rate_per_min                  : 0.476 %/min   (52% low)

**This is C17's defect, one function away and still live.** The session opens with
`samples: 1, rate_sum: 0.0`, so the opening sample contributes to the denominator and not the
numerator by construction; so does every sample where the integer percentage did not tick, and
every sample dropped by `MAX_RATE_INTERVAL_SEC` or `MAX_PLAUSIBLE_RATE_PCT_PER_MIN`.

The tell is in the row itself: **`avg_rate_per_min` can read below `min_rate_per_min`**, because
min and max are taken over observed rates only. In the run above, min is 1.0 and the average is
0.476.

⚠ **Blast radius is wider than the CSV.** The value flows to `sessions.csv`, to
`last_job.post_job_charge.avg_rate_per_min` (rendered by `src/renderers/metrics.js`), and into
`mid_job_recharge_stats.rate_mean_per_min` via
`battery/manager.py::BatteryHealthManager._update_mid_job_rate_stat` — the sensor whose docstring
calls it the cleanest health signal available. That last mean is lifetime and un-resettable, so
the bias is baked in permanently once accumulated.

**Contrast within the same session dict**, which is what makes this a miss rather than a
convention: `low_zone_rate_sum`/`low_zone_rate_samples`, its high-zone twin, and the
`cc_duration_min`/`cc_delta_pct` pair (and CV) are all incremented in the same branch as their
partner. The discipline is applied three times here and missed once.

Under a uniform cadence the value collapses to total gain over total duration — a defensible
number, but not the one the name promises, and not what min/max are measured over. Under a
non-uniform cadence it is neither.

Documented as current behaviour in `docs/dev/16-battery-record.md` §5, explicitly labelled an
open defect rather than an invariant.

### C55 — **OPEN.** Reconciliation pairs any 1-and-1 leftover and calls it an identity

Found 2026-08-22 by the rooms comment audit; verified directly against source.

`rooms/reconciliation.py::compute_reconciliation` matches a fresh discovery against saved rooms
by slug, then by id. Whatever is left over falls to a final branch:

    if len(unmatched_existing) == 1 and len(unmatched_discovered) == 1:

It emits a `renamed_and_renumbered` review pairing the two. **There is no similarity test of any
kind** — no name or slug comparison, no geometry, no area. A grep for `similar|ratio|difflib|
fuzz|distance|geometry|area` over the file returns only the module docstring.

The comment above it states the justification as a logical guarantee:

> When exactly one existing room and exactly one discovered room are left unclaimed, **they can
> only be each other**

They can not. A stored room DELETED plus an unrelated room ADDED in the same re-map produces
exactly the 1-and-1 shape, and the code cannot tell that case from a rename.

⚠ **`plan_migration` mirrors the pairing and acts on it.** It does `carried = dict(source)` —
carrying every durable setting (profile, floor type, clean mode, fan speed, passes, edge mopping)
onto the new id — and writes `id_remap[old_id] = new_id`, which rewrites `grants_access_to`
across the access graph so the new room inherits the old one's position in it.

**The real mitigation, and it is worth stating precisely:** this is a REVIEW the user confirms,
not an auto-apply. The failure is therefore not silent. What it does instead is present a
fabricated identity *as a determination*, and ask the user to confirm it — which is the shape
`f/accept_defect_when_discarded` says to check: the bad input is not discarded, it is persisted
and dispatched.

**Remedy is not obvious and should not be guessed at.** Refusing to pair at all loses a genuine
rename-and-renumber, which is the case REC-3/RP-019 exists to catch. A similarity floor needs a
threshold nobody has measured. Bring it to Chris before choosing.

Documented as current behaviour in the rooms NOW doc, stated as an open defect.

## ROOMS COMMENT AUDIT — 2026-08-22. 27 findings. NOT APPLIED.

Run alongside the `rooms/` doc pass (docs 17 + 18). Two auditors, both clusters read in full,
read-only. Severity: {'high': 1, 'medium': 15, 'low': 11}. Kind: {'over-scoped': 15, 'stale-reference': 7, 'false': 2, 'reason-obsolete': 3}.

**55% over-scoped** (15 of 27) — true of most cases, wrong at an edge the comment presents as
covered. That tracks the battery pass's 67% and makes it two subsystems where SCOPE, not
falsehood, is the dominant comment defect. It is also the kind that survives review, because a
statement true of the common case reads as correct.

The one HIGH was promoted to its own entry — see **C55** above (reconciliation's 1-and-1 pairing).

⚠ **Nothing here is applied.** A doc pass stays clean of code edits; these are for a repair
window. Each carries the comment verbatim and what the code does instead, so applying is
mechanical — but re-verify before editing: an audit finding is a claim, not a fact.

---

### R1 · HIGH · over-scoped — `rooms/reconciliation.py::compute_reconciliation`

**SAYS.** REC-3 (RP-019): a room renamed AND renumbered in the same re-map matches NEITHER a
slug nor an id, so it is invisible to both branches above. When exactly one existing room and
exactly one discovered room are left unclaimed, they can only be each other — anything more than
one on either side is genuinely ambiguous and is deliberately left unpaired (no auto changes
without a confident match; drift/new-room handling takes it from there, same as any other
unmatched room).

**DOES.** Pairs ANY 1-and-1 leftover unconditionally (lines 192-208): `if
len(unmatched_existing) == 1 and len(unmatched_discovered) == 1:` emits a renamed_and_renumbered
review. It never tests whether the two are plausibly the same physical room — no name/slug
similarity, no geometry, no area. A stored room DELETED plus an unrelated room ADDED in the same
re-map lands in exactly this 1-and-1 shape, so 'they can only be each other' is false.
plan_migration lines 314-326 mirror the same pairing and carry the old room's durable settings
and access-graph position onto the new id.

**MISLEADS.** A reader takes 'they can only be each other' as a logical guarantee and stops
looking for a confirmation guard. The load-bearing justification for a data-migration heuristic
is a claim the code cannot support, and the resulting review presents a fabricated identity as a
determination the user is asked to confirm.

### R2 · MEDIUM · over-scoped — `rooms/access_graph.py::AccessGraphManager.INDETERMINATE_STATE_VALUES`

**SAYS.** RP-008 (GUARD-1): states that mean "the sensor is not answering", not a value of the
world. A rule is a statement about the world; it cannot bind to ignorance — so NO operator
(including the negating ones and `missing`) may match while the rule entity reads one of these.

**DOES.** _room_rule_matches_known returns for `exists` at lines 1193-1195, BEFORE the sentinel
check at 1205: `if operator == "exists": return (state_obj is not None, True)`. An entity whose
state is literally "unavailable" or "unknown" still yields a state object, so `exists` returns
(matched=True, known=True) and _room_rule_matches returns True. The carve-out is deliberate —
the inline comment beside it says 'Presence of the entity is an observable fact either way' —
but the class-level comment says NO operator, without exception.

**MISLEADS.** A blocker rule with operator `exists` on a door sensor keeps blocking (and a
modifier keeps mutating fan speed/water level) while that sensor is reading `unavailable` — the
exact dropout the GUARD-1 rule was written to stop. Anyone auditing dropout safety, or
implementing the promised per-rule `when_unavailable` opt-in, will read 'NO operator ... may
match' and skip `exists` as already covered.

### R3 · MEDIUM · over-scoped — `rooms/access_graph.py::AccessGraphManager._access_graph_state`

**SAYS.** blank — no dock room and no grants anywhere; basic runs are allowed.

**DOES.** access_graph_block_code, 28 lines below in the same file, returns a BLOCK for the
blank state whenever any room carries rules: `if state == "blank" and
AccessGraphManager._any_rooms_have_rules(managed_rooms): return
"access_graph_required_for_rules"`. _any_rooms_have_rules tests `bool(room.get("rules"))` only —
it does not check `enabled` — and run_plan.py:1158-1187 turns any non-None block code into
`blocked: True, available: False` and returns before the queue is built. So on a blank graph
with a single rule anywhere, even a disabled one, every run is refused.

**MISLEADS.** The state docstring is the definition sheet for the three states; it tells the
reader blank is the permissive state. A user or automation reading `state: "blank"` off
get_access_graph_health concludes runs are allowed while every Start is being refused with
access_graph_required_for_rules — and the same field is what a maintainer would reason from when
deciding whether a blank graph needs a block path at all.

### R4 · MEDIUM · over-scoped — `rooms/reconciliation.py::plan_migration`

**SAYS.** Saved rooms whose slug vanished from discovery (merged/deleted in the re-map) are
dropped and reported under ``dropped`` — the user confirmed the re-map, and drift surfaces
genuine removals separately.

**DOES.** The REC-3 singleton pairing at lines 314-326 is a third carry path the docstring never
mentions, and it carries a saved room whose slug DID vanish: it takes the one leftover existing
slug, writes `new_rooms[str(new_id)] = carried`, and then
`carried_slugs.add(leftover_existing_slugs[0])`, which removes it from `dropped` (computed at
345-349 as slugs not in carried_slugs). Worked case — stored {16: kitchen, 17: den}, discovered
[{16: kitchen}, {20: study}]: 'den' is absent from discovery yet is carried onto id 20 and
`dropped` comes back empty. Separately, a saved room whose `room_id` is missing or non-coercible
is carried into `rooms` at line 299 but skips the carried_slugs add (guarded by `if old_id is
not None` at 300), so it is reported under `dropped` while its data was in fact carried.

**MISLEADS.** The docstring is the contract for the function and for the `dropped` list that
room_crud.py:376 hands straight back to the caller as the service response. A reader concludes a
rename+renumber loses the room's settings — the precise loss REC-3 exists to prevent — and a
caller treating `dropped` as the authoritative removal list gets both a false negative and, in
the missing-room_id case, a false positive.

### R5 · MEDIUM · stale-reference — `rooms/source_refresh.py::module docstring`

**SAYS.** Public surface: async_refresh_room_source(hass, vacuum_entity_id) -> None (async)
get_cached_room_source(hass, vacuum_entity_id) -> dict[str, list[dict]]
set_cached_room_source(hass, vacuum_entity_id, per_map) -> None flatten_maps_response(response,
*, discovery) -> dict[str, list[dict]] (pure)

**DOES.** async_refresh_room_source is declared `-> dict[str, Any]` (line 358) and its own
docstring documents seven distinct {ok, reason, refreshed_at} exits — the RP-007/SRC-1 fix whose
whole point was that it no longer returns None. dispatch/manager.py:383 depends on the dict
(`refresh_result.get("ok")`). The list is also stale in membership: it omits
get_cached_room_source_with_age, invalidate_room_source_cache and select_segments_for_map, all
public and all imported by other modules (dispatch/manager.py, __init__.py:823,
room_discovery.py:49). flatten_maps_response's listed signature also omits its vacuum_entity_id
and active_map_id keyword params.

**MISLEADS.** A caller reading the module header — the first thing you see in the file — writes
`await async_refresh_room_source(...)` and discards the result, or treats a returned value as a
bug. The `-> None` claim is the exact defect A4-SRC-1 describes, still asserted at the top of
the file that fixed it, while the R2-STALE-6 note 330 lines below shows this same return
contract has already drifted once.

### R6 · MEDIUM · over-scoped — `rooms/access_graph.py::AccessGraphManager.access_graph_block_rooms`

**SAYS.** # cycle_detected / multiple_dock_rooms name a SET of rooms; a cycle # chain repeats
its entry room, so dedup below is load-bearing.

**DOES.** Collects `issue.get("room_id")` and `issue.get("rooms")` only (lines 1114-1120).
multiple_inbound also names a set of rooms — _validate_room_access_graph emits it as `{"type":
"multiple_inbound", "room_id": target_id, "source_room_ids": sorted(sources)}` (lines 914-920) —
and `source_room_ids` is never read here, so only the inbound TARGET is named and neither source
room appears. The same file treats that field as load-bearing elsewhere: structural_issue_key
puts it in the key ('The payload fields are load-bearing, not decoration') and _names_edge scans
it. The docstring's parenthetical '(``type`` + ``room_id``)' is also wrong: `type` is never
inspected — every issue's room_id and rooms are harvested regardless of type.

**MISLEADS.** multiple_inbound makes the graph invalid, so state is partial and run_plan refuses
every Start naming these rooms (reason_params.rooms, run_plan.py:1135-1172). The two source
rooms are exactly where the user must delete a grant, and they are the two rooms not named. The
comment's two-type enumeration reads as the complete set of set-valued issues, so the gap looks
already handled.

### R7 · MEDIUM · over-scoped — `rooms/access_graph.py::AccessGraphManager._validate_room_access_graph`

**SAYS.** # Single-inbound constraint: each non-dock room may only be # granted access by
exactly one other room.

**DOES.** The check at lines 907-920 builds inbound_count over every target in grants_map and
flags `len(sources) > 1` — with no dock-room exemption. Nothing prevents a grant targeting the
dock room (_normalize_grants_access_to excludes only self-reference and non-positive ids), so
two rooms granting access to the dock room DO trip multiple_inbound on the dock room. The rule
is also 'at most one', not 'exactly one': a room with zero inbound sources is not caught here at
all — it is caught by the separate missing_dependency pass, which only runs when
`len(dock_room_ids) == 1`, so with zero or multiple dock rooms a zero-inbound room is flagged by
neither.

**MISLEADS.** Both halves are wrong in the direction that makes the check look narrower than it
is. Someone debugging an unexpected multiple_inbound on the dock room reads this comment,
concludes the dock is exempt, and looks for the bug elsewhere; someone relying on 'exactly one'
assumes zero-inbound is caught by this pass.

### R8 · MEDIUM · false — `rooms/reconciliation.py::module docstring`

**SAYS.** This module compares a fresh discovery against the stored (saved) rooms by slug and
reports what changed: - ``id_changed`` — a known slug now carries a different segment id (the
re-segment case). Confirming migrates the durable data to the new id. - ``renamed`` — a known
segment id now carries a different name/slug (the same physical room was renamed in the app).

**DOES.** compute_reconciliation emits a THIRD kind the list omits: `renamed_and_renumbered`
(lines 198-208), added by REC-3/RP-019, and its own function docstring at 100-106 correctly
documents all three. plan_migration carries data for it too (314-326). The module header still
describes the pre-REC-3 two-case world.

**MISLEADS.** The header presents itself as the exhaustive statement of what this module
reports, and the third kind is the one with the weakest evidential basis and the largest data-
migration consequence (see the singleton-pairing finding). A consumer switching on
review['kind'] from this list has no branch for renamed_and_renumbered.

### R9 · MEDIUM · reason-obsolete — `rooms/access_graph.py::get_room_access_editor._issue_applies`

**SAYS.** The ``is not None`` filter is load-bearing rather than tidiness:
_format_access_graph_issue's multiple_inbound branch can emit a literal None inside room_ids,
and a ``[None]`` list is truthy — without the filter it would read as "scoped to some room" and
wrongly suppress the widening.

**DOES.** The multiple_inbound branch can no longer emit None. It was changed to
`([str(room_id)] if room_id > 0 else []) + [str(s) for s in source_ids]` (lines 420-423), and
the A6-AGX-4 comment immediately above it says so in past tense: 'this used to be [str(room_id)
if room_id > 0 else None] + [...] which put a literal None into the contract'. No branch of
_format_access_graph_issue can now place None in room_ids — every one either filters or builds
from ids already screened `> 0`. The stated reason for the guard was fixed 330 lines earlier in
the same file.

**MISLEADS.** Two comments in one file assert opposite things about the same branch, and this
one names the other as its source. A maintainer chasing a None in the issue contract goes
hunting in a branch that cannot produce one; conversely, anyone who checks and finds the filter
dead may delete it along with the only note explaining why the None case was ever possible.

### R10 · MEDIUM · over-scoped — `rooms/vocabulary_migration.py::_unadjudicated_targets`

**SAYS.** An absent block reliably means "not registered YET", never "this brand declares
nothing": ``registry._validate_room_profiles`` rejects an adapter whose ``room_profiles`` is
missing or empty, so a registered adapter always presents one. That is what makes the two states
safely distinguishable here.

**DOES.** adapters/registry.py's register_adapter_config (and its legacy shim at line 621) only
HARD-RAISES on validation issues when `config.get("source") == "config"`. A CODE-sourced adapter
— which the registry's own docstring names as "the two shipped brand adapters, registered at
startup" and any future code adapter — is logged at WARNING and then registered anyway.
get_adapter_config() therefore CAN return a live config with no `room_profiles` block, which is
exactly the state the comment says is impossible.

**MISLEADS.** The whole deferred-latch design rests on this distinction. A reader would believe
a registered code adapter that omits `room_profiles` cannot exist, so `_unadjudicated_targets`
returning a vacuum can only mean "adapters not up yet, retry later". In fact such an adapter
parks that vacuum in `pending` permanently: `migrate_room_vocabulary` never latches, emits its
WARNING on every single start forever, and the state that means "this brand genuinely declares
nothing" is indistinguishable from "not registered yet" — the exact ambiguity the comment claims
is closed.

### R11 · MEDIUM · over-scoped — `rooms/room_discovery.py::get_active_map_id`

**SAYS.** - Entity absent from BOTH state machine and registry → the sensor is never created: an
attribute-mode device (e.g. Eufy on the scalar/Tuya transport) that surfaces its room list as a
vacuum attribute. Fall back to the adapter's single implicit map id (see
_implicit_attribute_map_id). Returns None when no path yields an id.

**DOES.** After `_implicit_attribute_map_id` returns None the function does NOT return None — it
falls through to `return _single_cached_map_id(hass, vacuum_entity_id, config)`, a fourth
resolution path added for ISSUE #46 that serves a SERVICE-RESPONSE brand (Roborock) whose cached
room source holds exactly one map. That path is absent from the enumeration, and it contradicts
the bullet's characterisation of this branch as attribute-mode-only.

**MISLEADS.** The docstring presents the three bullets as the complete resolution ladder
("Resolution therefore keys off whether the entity actually exists:") and closes with an
absolute "Returns None when no path yields an id." A reader debugging why a Roborock with no
map-selector entity resolves a map id — or auditing whether this function can invent a map
anchor — would conclude from this docstring that it cannot, and would miss the one path that
can.

### R12 · MEDIUM · over-scoped — `rooms/room_crud.py::RoomMapManager.discover_rooms`

**SAYS.** Does not create a map bucket. Map buckets are created only when ``save_managed_rooms``
is called after the user confirms the room list.

**DOES.** Sentence one is true (discover_rooms uses get_map_bucket, which is non-mutating).
Sentence two is not: `ensure_map_bucket` — which persists a skeleton via setdefault — is also
called by `reconcile_room` in BOTH arms (action="ignore" line 192, action="migrate" line 326) in
this same class, and by `rebuild_map` through `rebuild_map_bucket`. maps/map_manager.py's own
`map_ids_with_rooms` docstring states ensure_map_bucket "is called from ~38 sites ... and it
persists a skeleton the moment anything touches an id".

**MISLEADS.** The "only" is the load-bearing word. A reader auditing where empty skeleton
buckets come from — a known live problem ("a live install carried maps 7, 11 and 12 where only
12 was ever configured") — would rule out every path but save_managed_rooms on the strength of
this line, including reconcile_room(action="ignore"), which creates a bucket for a map the user
has never confirmed just to stamp a dismissal timestamp on it.

### R13 · MEDIUM · stale-reference — `rooms/room_defaults.py::resolve_new_room_defaults`

**SAYS.** ``catalog`` is a resolved ``room_profiles`` block (``resolve_profile_catalog``); None
resolves the framework's in-code catalog, which is what a brand that declares no
``room_profiles`` block gets today.

**DOES.** There is no framework in-code catalog. `resolve_profile_catalog(None)` returns
builtins={}, custom_template={} and default_profile="vacuum_quick" — its own docstring says
"There is NO framework default" and "an undeclared key resolves EMPTY rather than to somebody
else's words" (anchor IN40W49E), and get_default_room_profiles says "There are no in-code built-
ins to fall back to". So `resolve_new_room_defaults(None)` looks up "vacuum_quick" in an empty
builtins dict, finds nothing, and returns exactly {"profile_name": "vacuum_quick"} — a profile
NAME pointing at a profile that does not exist, and zero setting fields.

**MISLEADS.** This is the module whose entire purpose is killing the Eufy fallback catalog, and
its own API docstring still describes that catalog as live. A reader would believe the None path
yields a working set of default room settings; it yields a name and nothing else, so every field
silently falls through to build_managed_rooms' own literals. The same phrase repeats in the
sibling `resolve_new_room_defaults_for_vacuum`: "an unregistered adapter resolves the framework
catalog, exactly as a brand declaring no ``room_profiles`` block does."

### R14 · MEDIUM · over-scoped — `rooms/room_manager.py::build_managed_rooms`

**SAYS.** Q5 (verbatim): a room with NO existing match — the room this discovery pass has never
seen before — is enabled on a FIRST import (``existing_rooms`` was empty before this call) and
DISABLED+unconfirmed on incremental discovery (DQ-Q-5/CRUD-6); it never silently joins an
already-active queue.

**DOES.** "DISABLED" holds. "unconfirmed" holds only when `enabled_room_ids` is supplied. When
`enabled_room_ids is None` (has_explicit_enabled_ids False), line 181 sets `is_configured =
True` unconditionally for every discovered room, including one never seen before — so a brand-
new room on an incremental save comes out enabled=False but is_configured=True. The same
docstring's later paragraph concedes this ("is_configured keeps its unconditional True, as
before"), contradicting the Q5 clause above it.

**MISLEADS.** Production-reachable, not hypothetical: services/setup.py:358 passes
`data.get("enabled_room_ids")`, which is None when the caller omits it, and
room_crud.save_managed_rooms defaults it to None. Per models.py, is_configured is "True iff the
user has explicitly approved this room via the save_rooms step" and gates entity creation and
drift signals — so a never-approved room gets entities created and counts toward drift, which is
precisely what the quoted requirement exists to prevent. A reader auditing approval flow would
treat Q5 as the settled contract.

### R15 · MEDIUM · stale-reference — `rooms/room_discovery.py::discover_rooms_for_vacuum`

**SAYS.** Reads discovery config from the adapter registry: room_list_entity — "vacuum_entity"
or a full entity ID room_list_attribute — attribute name that holds the room list room_id_key —
key in each room dict for the room ID room_name_key — key in each room dict for the room name
Returns an empty list when the adapter is not registered, discovery config is absent, or the
room list attribute is missing/invalid.

**DOES.** The function reads `discovery["source"]` FIRST and branches on it, and also reads
`discovery["room_list_shape"]`; neither is listed. On the SOURCE_SERVICE_RESPONSE branch it
never reads room_list_entity or room_list_attribute at all — it goes to `get_cached_room_source`
+ `select_segments_for_map` — and returns [] when the cache holds nothing for that map, a
condition unrelated to "the room list attribute is missing/invalid".

**MISLEADS.** The list reads as the complete config contract for this function. A porter
configuring a new adapter from it would declare all four keys, omit `source`, silently land on
the attribute branch, and discover zero rooms — which is the same failure the file's own line
283-289 comment records happening to Dreame when SHAPE was conflated with SOURCE. The docstring
was never updated when the two axes were split on 2026-08-07.

### R16 · MEDIUM · false — `rooms/room_crud.py::RoomMapManager.remove_map`

**SAYS.** # RP-016/RF-20 (INJ7VXE7): consume the SAME registry RP-017's id-remap walker # reads,
so a bucket added there is reachable here too without a # second hand-maintained list -- the
defect this packet closes # (run_profiles/queue/onboarding survived remove_map for however #
long they existed as real per-map stores nobody added here).

**DOES.** There IS a second hand-maintained list: `FLAG_NAMES`, declared 45 lines above,
enumerating the same eight store keys. The loop body does `flag = FLAG_NAMES[store_key]` with a
bare subscript. Adding a ninth entry to PER_MAP_STORES without also adding it to FLAG_NAMES does
not merely leave it unreported — it raises KeyError and takes remove_map down entirely, deleting
nothing.

**MISLEADS.** The comment tells a future maintainer that registering a new per-map store in
maps/map_manager.py is sufficient for remove_map to handle it. The FLAG_NAMES block's own
comment even admits it is maintained by hand ("New buckets (run_profiles/queue/onboarding) get
their own flags in `removed` too"), so the two comments contradict each other. Acting on the
RP-016 one converts a silent-survival bug into a hard crash on the delete-map service path.

### R17 · LOW · reason-obsolete — `rooms/access_graph.py::structural_issue_key`

**SAYS.** A6-AGX-2. ``update_room_fields`` validates the WHOLE graph after an edit and rejects
the edit if any structural issue exists — absolute, not a delta. So a violation already stored
... rejects edits that have nothing to do with it: a fan-speed change, an enable toggle, a
colour.

**DOES.** Present tense, but core/manager.py:1940-1961 is delta-scoped now: it captures
`baseline_keys` from a pre-mutation validation, then rejects only `new_structural_issues =
[issue for issue in structural_issues if structural_issue_key(issue) not in baseline_keys]`. The
comment sitting on that code says the opposite of this one — 'used to refuse on any structural
issue at all'. A pre-existing violation no longer rejects a fan-speed change, an enable toggle
or a colour; the one remaining absolute gate is A5-DOCK-1, and it fires only when
grants_access_to is being edited.

**MISLEADS.** Written as the current behaviour of a named function, not as history — the file
marks history explicitly elsewhere ('this used to be'). A reader concludes the absolute gate is
still live and that structural_issue_key is only aspirational, or duplicates the delta fix
believing it was never applied.

### R18 · LOW · reason-obsolete — `rooms/source_refresh.py::module invariant header`

**SAYS.** A4-SRC-4: No in-flight coalescing or lock on the refresh: triggers spawn unbounded
concurrent get_maps cloud calls, and an older response landing last becomes the resident cached
snapshot — including one that started before a map switch and lands after it

**DOES.** All three of the unmarked entries describe code this file no longer contains. SRC-4:
`_INFLIGHT` coalescing (lines 92, 384-396) plus the `_GENERATION` commit guard (461-468), both
labelled '(SRC-4)' in the code. SRC-1: the function returns a seven-exit dict and the cache is
stamped with refreshed_at/refreshed_mono. SRC-3: flatten_maps_response detects duplicate map
names and suffixes them with a warning (330-341). Meanwhile the two sibling entries in the same
block carry an explicit status marker — 'A4-SRC-2 (closed RP-006)' and 'A4-SRC-5 (closed
RP-007)' — which is the convention this block uses to say a finding is fixed.

**MISLEADS.** The differential marking is the status signal: with two entries marked closed and
three not, the unmarked three read as still live in a file that visibly fixed them. The block's
own header warns 'Verify before citing one as closed' but says nothing about the reverse —
citing an already-closed one as open, which is what this shape produces.

### R19 · LOW · over-scoped — `rooms/access_graph.py::get_room_access_editor`

**SAYS.** # Now genuinely a last resort: every known structural type is handled above # and
_names_edge reaches all of them.

**DOES.** The structural set defined at lines 1010-1018 is {self_reference, duplicate_edge,
cycle_detected, multiple_inbound, multiple_dock_rooms}. The if/elif chain at 691-703 handles
cycle_detected, duplicate_edge, missing_room, self_reference and multiple_inbound —
multiple_dock_rooms has no branch and falls to the else. It is wrong in the other direction too:
missing_room HAS a branch but is not in the structural set, so candidate_issue can never carry
it and that branch is unreachable.

**MISLEADS.** 'every known structural type is handled above' is checkable in twenty seconds
against a frozenset in the same file and is wrong, so the else really is reachable in principle.
In practice multiple_dock_rooms is filtered out by baseline_keys (dock rooms are identical in
the candidate graph, so the key matches the baseline) — but that is the reason, and it is not
the reason the comment gives.

### R20 · LOW · over-scoped — `rooms/source_refresh.py::flatten_maps_response`

**SAYS.** If there is no active-map value, use Roborock's numeric flag as the same "Map <flag>"
fallback HA shows.

**DOES.** The flag branch is `elif` on `if active_map_id and len(maps) == 1:` (lines 306-310),
so it is taken whenever the active-map fallback did not apply — including when there IS an
active-map value but the response carries more than one map. The comment's stated condition ('no
active-map value') is narrower than the code's. The comment and the function docstring also both
omit the third fallback the code actually has: `else: map_name = f"Map {index}"`.

**MISLEADS.** The `len(maps) == 1` restriction is the deliberate part — you cannot tell which of
N maps the active-map name belongs to — and it is the part neither the comment nor the docstring
states. Someone reconciling a multi-map cache key that came back as 'Map 3' instead of the
select value will look for a bug that isn't there, and the 'Map {index}' key is documented
nowhere at all.

### R21 · LOW · stale-reference — `rooms/access_graph.py::module docstring`

**SAYS.** Owns: - _normalize_grants_access_to / _normalize_room_rule / _normalize_room_rules -
_normalized_managed_rooms_with_automation - _build_room_access_views -
_format_access_graph_issue / _room_access_context - get_room_access_editor -
get_access_graph_health - _validate_room_access_graph - _structural_access_graph_issues
(staticmethod) - _access_graph_state (staticmethod) - _any_rooms_have_rules (staticmethod) -
_normalize_rule_operand / _room_rule_matches

**DOES.** The inventory has not kept up with what the module gained. Missing:
access_graph_block_code and access_graph_block_rooms (both public staticmethods, called from
core/manager.py:2872/2879 and planning/run_plan.py:1125/1135 — arguably the module's most-
consumed surface), structural_issue_key (module-level, imported by core/manager.py:101),
_room_rule_matches_known (called from listeners/path_blockers.py:203 and
planning/run_plan.py:1805) and _room_rule_value_matches. Every symbol listed does still exist;
the list is incomplete, not wrong.

**MISLEADS.** This header is the module's map, and the A6-AGX-1/A5-AG-2/RP-008 additions are
exactly the parts a reader needs to find. Someone looking for where 'do runs block on the access
graph?' is answered will not find it named here — the same discoverability problem A6-AGX-1 was
opened to fix.

### R22 · LOW · over-scoped — `rooms/access_graph.py::AccessGraphManager.get_access_graph_health`

**SAYS.** # The rooms that will become missing_dependency the MOMENT a dock room # is set — i.e.
the cost of following this report's own advice.

**DOES.** unlinked_room_ids (lines 825-832) is every room in requires_map with no inbound
parents, minus rooms already in dock_room_ids. On a blank graph dock_room_ids is empty, so it is
EVERY room. _validate_room_access_graph's missing_dependency pass skips the dock room itself
(`if room_id == dock_room_id: continue`, line 942), so once the user sets a dock the count is
N-1, not N — the room they promote is in this list and will not become missing_dependency.

**MISLEADS.** The list is offered as the exact cost of acting on the report, and it always over-
states that cost by one on a blank graph. The code cannot know which room becomes the dock, so
this is a wording problem, not a fixable computation — which is precisely why the comment should
say 'all but the one you promote' rather than asserting the list is what will fire.

### R23 · LOW · over-scoped — `rooms/room_crud.py::RoomMapManager.reconcile_room`

**SAYS.** Requires a prior ``discover_rooms`` to have cached the discovery payload.

**DOES.** True for action="migrate" (it returns skipped="no_discovery" without one). False for
action="ignore", which returns at line 222 before any such requirement: with no cached discovery
it reads `discovery.get("rooms", [])` off an empty dict, computes a plan token over an EMPTY
discovered set, and stamps `reconciliation_dismissed_at` + `reconciliation_dismissed_token` into
a bucket it creates via ensure_map_bucket.

**MISLEADS.** The sentence is unqualified and sits below a docstring that has just described
both actions, so it reads as binding on both. It hides that an `ignore` with no cached discovery
persists a dismissal token fingerprinting nothing — which, per compute_reconciliation's
dismissed_plan_token contract, suppresses only an identical (empty) review set, so the dismissal
is effectively inert rather than doing what the user asked.

### R24 · LOW · stale-reference — `rooms/vocabulary_migration.py::migrate_room_vocabulary`

**SAYS.** Apply the migration once, recording that it ran. Idempotent. Returns ``{"ran": bool,
"changes": [...], "rooms_touched": int}``. The caller is responsible for persisting ``data``;
nothing here writes to disk.

**DOES.** Two disagreements. (1) It does not necessarily record that it ran: the deferred-latch
block at line 263-294 sets migrations[MIGRATION_KEY] only when `_unadjudicated_targets` is
empty, otherwise it logs a WARNING and deliberately declines. (2) The stated return shape is
stale — the ran path returns a FOURTH key, "latched", added with that block; and the early
return at line 245 omits "latched" entirely, so a caller reading result["latched"] KeyErrors on
the already-migrated path.

**MISLEADS.** The one-line summary is the opposite of the file's most carefully argued behaviour
("missing runtime information is DEFERRED, never SUCCESS"), and it is the part a caller reads.
The enumerated return shape is the contract a caller codes against; "latched" — the only signal
that the run deferred — is invisible in it, and is not present on every return path.

### R25 · LOW · over-scoped — `rooms/room_discovery.py::discover_rooms_for_vacuum`

**SAYS.** # anchor: INCFMPP1 one slug derivation, at ONE admission boundary, unique within # its
map -- lowest room_id keeps the bare slug, colliding siblings get _r{room_id}

**DOES.** The disambiguation pass groups by slug and rewrites `group[1:]` to
f"{slug}_r{room_id}", but never re-checks the rewritten value against slugs already present in
the same map. Two rooms named "Kitchen" (ids 3 and 7) plus a third named "Kitchen r7" (id 9)
yield slugs kitchen, kitchen_r7, kitchen_r7 — a duplicate inside one map, which is the state the
anchor asserts cannot occur.

**MISLEADS.** This anchor is cited as a system invariant, and downstream code is written on the
strength of it — _existing_by_slug in room_manager.py exists specifically to cope with "a store
that still holds a pre-RP-015 duplicate slug (from before admission-time uniqueness existed)",
i.e. it treats post-RP-015 duplicates as impossible. A reader would take "unique within its map"
as guaranteed at admission and not defend against a duplicate arriving fresh. The triggering
input is contrived, so this is a boundary defect, not a live one.

### R26 · LOW · stale-reference — `rooms/room_discovery.py::module`

**SAYS.** Adapter config shape consumed here (adapters/config_schema.py § discovery):
room_list_entity: "vacuum_entity" | <full entity_id> room_list_attribute: str — attribute name
on the entity room_id_key: str — key in each room dict for the room ID room_name_key: str — key
in each room dict for the room name When the adapter is not registered or discovery config is
absent, both functions degrade gracefully (return None / empty list).

**DOES.** The module consumes seven discovery keys, not four: it also reads `source` (which
selects the entire branch), `room_list_shape`, and `implicit_map_id`. And "both functions" is
stale — the module now exposes three public functions; the third, `discover_rooms_payload`,
returns a dict, not None or an empty list.

**MISLEADS.** Same over-narrow key list as the discover_rooms_for_vacuum docstring, restated at
the module level where it reads as the file's declared interface with the adapter schema. "Both
functions" additionally dates the paragraph to before discover_rooms_payload and the four
private helpers were added, so a reader cannot tell which functions the degradation guarantee
actually covers.

### R27 · LOW · stale-reference — `rooms/__init__.py::module`

**SAYS.** The existing room_discovery.py, room_manager.py, and utils.py modules are unchanged
and continue to be importable directly.

**DOES.** The package now contains access_graph.py, reconciliation.py, room_crud.py,
room_defaults.py, room_discovery.py, room_manager.py, source_refresh.py, utils.py and
vocabulary_migration.py. room_discovery.py in particular has been substantially rewritten since
this line was written — the source/shape branch split (2026-08-07), the _single_cached_map_id
ISSUE #46 fallback, the _implicit_attribute_map_id path, and the INCFMPP1 slug-disambiguation
pass are all later additions.

**MISLEADS.** It is the package docstring, so it is the first thing a reader opens to learn what
`rooms/` holds. It names three of nine modules and asserts the three are unchanged, which reads
as "nothing here has moved since the split" — the opposite of the truth for room_discovery.py,
and it gives no pointer at all to room_defaults.py, reconciliation.py, source_refresh.py or
vocabulary_migration.py.

---

## ROOMS MAP — reader-would-get-wrong (from the same pass, not comment defects)

29 items the map flagged as things a reader would conclude wrongly. Several are real
code findings rather than comment problems and are worth reading before the repair window:

- **`_issue_applies`'s docstring states its `is not None` filter is "load-bearing rather than
  tidiness" because "_format_access_graph_issue's multiple_inb** — That branch no longer can.
  The comment ten lines above it in the SAME file describes the fix in the past tense ("this
  used to be … which put a literal None into the contract") and the current code is
  `([str(room_id)] if room_id > 0 else []) + [str(s) for s in source_ids]`. All nine formatter
  branches now filter. The fi

- **`_names_edge`'s docstring says the fallback reason is "now genuinely a last resort: every
  known structural type is handled above and _names_edge reach** — Wrong in both directions.
  `multiple_dock_rooms` IS in the structural set and is NOT handled by the reason ladder — it
  falls to the contentless `graph_illegal`. And `missing_room` IS in the reason ladder but is
  NOT in the structural set, so that branch is dead. Harmless in practice — the candidate graph
  only changes `gr

- **source_refresh.py's module docstring declares the public surface as
  `async_refresh_room_source(hass, vacuum_entity_id) -> None (async)`.** — It returns `dict[str,
  Any]` with a seven-exit contract (`ok`/`reason`/`refreshed_at`), and that return value is
  load-bearing — dispatch/manager.py:390 gates a HomeAssistantError on
  `refresh_result.get("ok")`. The `-> None` signature is the pre-RP-007 shape, i.e. the exact
  defect the file's own invariant block records a

- **room_crud.py's invariant header records A2-REC-5 as "(closed RP-019): migrate applies a plan
  the user never saw: it never re-checks the reviews, and r** — Only the first half closed. The
  plan_token gate re-checks the reviews. There is no `if not current_reviews: return` anywhere
  in the migrate arm — a migrate with ZERO reviews computes a matching token and proceeds to
  replace `map_bucket["rooms"]` wholesale from `plan_migration`. That is not a no-op:
  `plan_migration` dro

- **The `reason_code` field is annotated "the localizable half — A6-AGX-4's card resolver keys
  on it" and "the card resolver keys on this instead".** — No consumer exists.
  `get_room_access_editor` has zero callers in the repo outside its own service registration —
  `grep -rn "editable_targets|get_room_access_editor" src/` returns nothing, and the card
  renders the room-access modal from its own `src/state/access-graph-model.js` and
  `src/state/access-issue-label.js`. The

- **`set_room_access_graph`'s docstring justifies replace-all because "N per-room
  update_room_fields calls cannot honour that: the map is observably half-** — The rationale is
  sound but the card is not using the service it argues for. `src/bindings/room-access.js`
  routes a normal Save through `saveRoomAccess` → `update_room_fields` (one room at a time) and
  calls `set_room_access_graph` ONLY when releasing the dock (the clear path). A reader would
  conclude the atomic path is

- **`set_room_access_graph` returns `issues` — implying one shape.** — Two shapes from one
  service. The refusal path returns FORMATTED issues (`{code, message, params, room_ids}`,
  manager.py:2188-2191); the success path returns the RAW validation issues (`{type, room_id,
  …}`, manager.py:2234). The card's `accessIssueLabel` keys on `issue.code`, so a success-path
  issue would resolve to the

- **The cache accessor comment says "Legacy raw per_map dicts are still readable", and
  `get_cached_room_source_with_age` documents "an entry that predates** — That branch cannot
  fire in production. The cache lives only in `hass.data`, which dies with the process, and the
  sole writer is `set_cached_room_source`, which always stamps. There is no upgrade path across
  which an unstamped entry could survive. Worse, the discriminator is `"per_map" in value` — a
  Roborock map literal

- **`_refresh_result(ok, reason)` stamps `refreshed_at` whenever `ok` is True, and
  `setup/workflow.py` surfaces that whole dict as the support-capture exp** — Two of the three
  ok=True exits refreshed nothing: `not_service_source` (attribute brand — there is nothing to
  refresh) and `superseded_by_newer_refresh` (a different task committed). Both report
  `refreshed_at = utc_now_iso()` — a timestamp for a commit this call did not make, and one that
  does not correspond to the cac

- **`plan_migration`'s `dropped` list is documented as "Saved rooms whose slug vanished from
  discovery (merged/deleted in the re-map)".** — `carried_slugs` is only populated inside `if
  old_id is not None` (:300-305), but the room is written into `new_rooms` before that check
  (:299). A stored room with a missing or non-coercible `room_id` is therefore CARRIED and
  simultaneously reported as DROPPED, and it inflates `leftover_existing_slugs` — which can
  eithe

- **`discover_rooms` always attaches a `plan_token` the caller can round-trip back to
  `reconcile_room`.** — When a dismissal suppressed the reviews, `compute_reconciliation`
  returns `{"reviews": [], "has_changes": False, "dismissed": True}` and the token is then
  computed over `reviews=[]`. `reconcile_room` recomputes WITHOUT the dismissal arguments, so it
  fingerprints the real (non-empty) reviews — the two can never match, a

- **`_room_slug` "returns a room's slug, deriving it from the name when absent" — implying the
  derived value is interchangeable with the stored one.** — It is not, for collided names.
  Discovery's admission boundary disambiguates duplicate slugs by appending `_r{room_id}` to
  every sibling but the lowest id (room_discovery.py:369-380); `_room_slug`'s fallback calls
  bare `slugify_room_name`. A stored room missing its `slug` field whose name collides derives
  the BARE slug

- **`flatten_maps_response`'s docstring: "Map keys are the map NAME when present, or the active-
  map select value / map flag fallback when HA's Roborock re** — There is a third fallback the
  docstring omits — `f"Map {index}"` when there is no name, no usable active-map value, and no
  `flag`. That key is a positional identity that changes if the response reorders, and it will
  not match any active-map select value, so the map is effectively undiscoverable rather than
  merely unnam

- **`update_room_fields`'s `no_dock_room` refusal reaches the user like any other refusal.** —
  It returns no `issues` array, only `reason_detail` — English prose. The card's error handler
  falls through `issues → reason_detail → message → reason → tRaw(...)`, so this refusal renders
  untranslated in all 18 locales, unlike `invalid_access_graph`, which carries coded+param'd
  issues. Whether the card's own client-sid

- **room_crud.py lines 357-358: "Room-history is a rebuildable cache derived from slug-tagged
  job files; invalidate so it re-ingests under the new ids." —** — The operative half is false.
  `_ingest_completed_job_into_room_history` keys every entry on `room.get("room_id",
  room.get("id"))` — the RAW numeric id recorded in the job file — and never reads the slug,
  even though resolved_rooms DOES carry one. So the re-ingest rebuilds under the OLD ids, not
  the new ones. Worse, `asy

- **room_crud.py lines 591-594 and maps/map_manager.py lines 11-18 both state that
  PER_MAP_STORES has a second consumer — "RP-017's id-remap walker" — so ** — No such walker
  exists. `grep -rn PER_MAP_STORES` over custom_components returns exactly one consumer:
  remove_map. `grep -rn id_remap` returns only reconciliation.py (produces it), room_crud.py
  (consumes it at two hand-written sites) and onboarding/manager.py (the floor-type re-key). So
  the id-remap side of the registry

- **`RoomMapManager.rebuild_map` is a live CRUD operation on a par with save_managed_rooms — the
  invariant comment in room_manager.py names it as one of t** — It has ZERO production callers.
  The only references are the `core/manager.rebuild_map(**kwargs)` delegate, tests
  (tests/integration/test_manager_delegation.py, test_room_crud.py) and comments. It is not
  registered in services.yaml, not in services/rooms.py's SERVICES tuple, and does not appear in
  any frontend bundle un

- **room_defaults.py::resolve_new_room_defaults docstring: "None resolves the framework's in-
  code catalog, which is what a brand that declares no room_pro** — There is no framework in-
  code catalog any more — that is the whole point of anchor IN40W49E.
  `resolve_profile_catalog(None)` returns `builtins: {}`, so `resolve_new_room_defaults(None)`
  yields exactly `{"profile_name": "vacuum_quick"}` and NO setting fields at all. The
  degradation is correct; the sentence describes a m

- **services/setup.py lines 370-371: "is_configured stamping is handled by build_managed_rooms —
  every room returned by save_managed_rooms now carries Tru** — Not since CRUD-3. When
  `enabled_room_ids` IS supplied (which is exactly what setup_save_rooms does when the user
  selects rooms) a room with no matching `floor_types` entry and no prior confirmation gets
  `is_configured=False`. The service nonetheless records the `save_rooms` step complete.
  Compounding it: save_managed_r

- **build_managed_rooms' comment: "A call with no enabled_room_ids at all is not asking an
  approval question in the first place (e.g. re-syncing an alread** — The example given is not
  the only such call site, and the other one is the opposite case.
  `setup/workflow.py::import_active_map` — the FIRST import of a map, the moment before any user
  has ever seen the room list — calls `save_managed_rooms(enabled_room_ids=None,
  floor_types={})`, so every discovered room is stamped `i

- **The RP-018/D5 rule — "an ambiguous slug is excluded here entirely ... never a guess" — reads
  as a property of slug-led carry across the cluster.** — It is implemented in two of the three
  copies. `room_manager._existing_by_slug` and `rebuild_map_bucket`'s inline copy both build
  `{slug: room}` only `if len(rooms) == 1`. `reconciliation.compute_reconciliation` and
  `reconciliation.plan_migration` build the same map with `existing_by_slug.setdefault(slug,
  room)` over th

- **The discovery cache key and the discovered rooms' own `map_id` field always agree, so
  `save_managed_rooms`/`reconcile_room`'s `str(room.get("map_id"))** — They diverge whenever the
  active map is unresolvable. `room_crud.discover_rooms` computes the cache key as
  `str(payload.get("active_map_id") or map_id or "")` → the EMPTY STRING, while
  `discover_rooms_for_vacuum` independently stamps each room's map_id as `map_id or
  get_active_map_id(...) or "unknown"` → the literal "u

- **profiles/room_profiles.py::declared_profile_fields: "The discriminator is shared with that
  repair so the two cannot diverge again" — reading this, the** — "The two" is exact and the
  scope is narrower than it reads: only `vocabulary_migration` and
  `ProfileManager._finalize_room_update` share it. `build_managed_rooms` and
  `rebuild_map_bucket` build every room through `RoomConfig`, which writes
  `clean_intensity=str(_default("clean_intensity",""))` unconditionally, and `as_d

- **`slugify_room_name` returns "a stable, URL-safe slug" (its own first line).** — It is not
  URL-safe, and the docstring says so itself three lines later: it "never strips non-ASCII, so
  Cyrillic / Greek / CJK / emoji room names keep distinct, non-empty slugs". Those require
  percent-encoding. It also leaves typographic quotes (U+2018/2019/201C/201D — only the ASCII '
  and " are deleted), tabs, and non-

- **The `_r{room_id}` collision suffix (anchor INCFMPP1) makes same-named rooms safe
  everywhere.** — It makes name→slug non-invertible, and two live-attribution consumers still
  invert it. `jobs/active_job.py` (native current-room rollover) and `listeners/pose_sampler.py`
  both compute `signal_slug = slugify_room_name(live_name)` from the device's active-cleaning-
  target state and compare it to the room's STORED slug. Wi

- **`get_managed_rooms` recomputes a missing summary — `map_bucket.get("summary",
  build_room_selection_summary(managed_rooms=rooms))`.** — The default is dead in two senses.
  Python evaluates it EAGERLY, so `build_room_selection_summary` runs on every call and its
  result is discarded whenever the key exists; and the key always exists, because
  `ensure_map_bucket` seeds `"summary": {}` with the rest of the bucket and `get_map_bucket`'s
  miss-path literal does

- **room_discovery.py lines 57-60: `_ACTIVE_MAP_SENTINELS` is "derived from the shared
  vocabulary so it cannot drift again".** — The VOCABULARY was centralised; the QUESTION was
  not. room_discovery asks it through `is_blank_state`, which strips and lowercases; its one
  importer, diagnostics.py, asks `active_map_state not in _ACTIVE_MAP_SENTINELS` — raw set
  membership on an unstripped, uncased string. Failure input: a provider publishing `"Unknown

- **models.py's `RoomRecord` TypedDict is "the canonical shape for a stored room configuration
  dict".** — It omits three fields every writer in this cluster persists: `is_transition`,
  `is_configured` and `configured_at`. All three come out of `RoomConfig.as_dict()` on every
  save and rebuild, and `is_configured` in particular gates entity creation and drift signals. A
  reader treating RoomRecord as the storage contract will

- **onboarding/manager.py's cross-references into this cluster ("That matches
  rooms/room_crud.py:323-325", "reconcile_room's migrate branch (rooms/room_cr** — Both line
  numbers are stale. The rule-status purge is now room_crud.py:339-346 and the
  `remap_confirmed_floor_types` call is at :351-355. The CLAIMS are still correct — the purge
  does run in both directions, and reconcile_room is still the only caller — but the citations
  point at the wrong lines, which is the failure m

## LISTENERS COMMENT AUDIT — 2026-08-22. 26 findings (UNION OF TWO RUNS). NOT APPLIED.

Severity {'high': 2, 'medium': 13, 'low': 11}. Kind {'over-scoped': 7, 'false': 7, 'reason-obsolete': 3, 'stale-reference': 8, 'adopted-alternative': 1}.

⚠ **THIS IS A UNION, AND THAT IS THE POINT.** The workflow's first run lost one map agent to the
StructuredOutput retry cap. On resume the two AUDIT agents did NOT replay from cache — they re-ran
with identical prompts and returned a DIFFERENT set: 22 findings then 20, with only 16 in common.

    reproduced by both runs   16/26
    appeared in ONE run only  10/26  (38%)

One of the two HIGHs — `lifecycle.py`'s dormant-seam claim — exists in run 1 ONLY. Taking the
later run as authoritative would have silently dropped a finding already verified against source.

**A single audit pass is a SAMPLE, not an enumeration.** The battery pass (33 findings) and the
rooms pass (27) were each single runs, so both should be assumed to under-enumerate by a similar
margin. This is the `loop-until-dry` shape: keep sampling until a round returns nothing new.

**Over-scoped share is 26% here** against battery's 67% and rooms' 55% — but this subsystem fails
differently: 7 `false` and 8 `stale-reference` out of 26. Both HIGHs are the same shape and it is
one worth naming — **a comment asserting a code path is DORMANT when it ships.**

⚠ **Not applied.** A doc pass stays clean of code edits. Re-verify before editing; an audit
finding is a claim, not a fact. The two HIGHs below I verified against source myself.

---

### L1 · HIGH · over-scoped · seen in run1+run2 — `listeners/lifecycle.py:407-408`

**SAYS.** # Sequenced job model: a completed phase advances to the next # phase (re-dispatch)
instead of finalizing. Atomic jobs — # every adapter today — return False here and finalize as #
before. Each phase finalizes only when it is the last.

**DOES.** The sequenced branch is a live, shipped production path, not a dormant seam.
adapters/roborock/adapter.py:491 declares dispatch.template "roborock_segment_clean" ->
RoborockSegmentEngine(GenericRoomIdsEngine) (queue/dispatch_engines.py:309), which OVERRIDES
build_phases to emit one phase PER ROOM when strict_order is set (dispatch_engines.py:244-260).
core/manager.py:6973-6975 then stamps `_phase_dispatch_pending` and spawns the phase watchdog
for any job carrying `phases`, and queue_engine.advance_active_job_phase returns the advanced
dict -> `await manager_local.maybe_advance_phase(...)` returns True. strict_order is user-facing
and shipped: `strict_order_on_label` / `strict_order_on_text` exist in all 18 frontend locale
packs, worded "rooms will be cleaned one at a time in the order shown (a trip to the dock
between rooms)".

**MISLEADS.** A maintainer reads this as "the maybe_advance_phase branch never returns True in
production today" and treats the whole phase-advance path — plus jobs/phase_runner.py and the
`_phase_dispatch_pending` guard 30 lines above it — as unreachable expansion scaffolding: safe
to simplify away, safe to leave untested, and not a suspect when a Roborock strict-order run
misbehaves between rooms. The same file at lines 364-374 contradicts it directly, describing a
Roborock docking between phases as live behaviour.

### L2 · HIGH · adopted-alternative · seen in run1+run2 — `listeners/pose_sampler.py:388-391 (register())`

**SAYS.** # LIMITATION (F4, deferred): if a future 2nd brand declares a DIFFERENT interval, its
# slower vacuums get over-sampled vs the engine's dwell = n*interval_s assumption. Each # sample
already carries a wall-clock `t`, so the fix is per-vacuum tickers (or have the # engine derive
dwell from `t` deltas). Unreachable while only Eufy declares attribution.

**DOES.** Both halves are dead. (1) The "future 2nd brand" shipped:
adapters/roborock/adapter.py:759 declares a room_attribution block with tuning interval_s 5.0
against Eufy's 2.0 (adapters/eufy/adapter.py:901), so the condition is reachable today, not
"unreachable while only Eufy declares attribution". (2) The deferred fix was ADOPTED 14 lines
below: _handle_pose_tick (lines 405-425) keeps a per-vacuum _last_sample_ts and skips any vacuum
whose own _room_attribution_interval_s has not elapsed, and its own POSE-1 comment describes the
identical failure as already remedied — "each vacuum is sampled only at its OWN declared
interval", citing the observed 2.5x over-weighting, which is exactly Roborock's 5.0 over Eufy's
2.0.

**MISLEADS.** A maintainer reads this as a known-live sampling defect that is merely out of
reach, and either re-implements per-vacuum tickers that already exist in effect, or distrusts
every Roborock external-run attribution as over-sampled. It also asserts a false fact about the
adapter set — that only Eufy declares room_attribution — which is exactly the premise anyone
scoping a third brand would build on.

### L3 · MEDIUM · false · seen in run1 — `listeners/lifecycle.py:194-195`

**SAYS.** # Vocabulary params omitted — manager reads them from the # adapter registry directly,
with brand-specific fallbacks.

**DOES.** core/manager.py:3578-3594 reads the vocabulary from the adapter registry, but every
fallback is deliberately EMPTY or generic, never brand-specific:
`_vocab_frozenset("hard_service_states", frozenset())`, `_vocab_frozenset("drying_states",
frozenset())`, `_vocab_frozenset("active_run_task_states", frozenset())` — all fall back to an
empty frozenset — and `active_vacuum_states` falls back to const.py's HA_ACTIVE_VACUUM_STATES =
{"cleaning","returning","paused","error"}, a generic Home Assistant vocabulary with no brand in
it. An adapter that declares no vocabulary gets nothing, by design
(profiles/room_profiles.py:208 anchor IN40W49E: "core holds no brand's vocabulary - undeclared
resolves EMPTY").

**MISLEADS.** It asserts core carries per-brand vocabulary defaults, which is the exact
inversion of the invariant this codebase enforces — and which this very file insists on 20 lines
later ("No hardcoded Eufy-literal vocabulary fallback either ... an adapter that declares no
vocabulary gets no wash detection, rather than silently inheriting Eufy's 'washing'/'washing
mop'"). Someone porting a new brand reads this and expects sensible defaults from core when
their adapter omits `vocabulary`; they will instead get an empty set and a lifecycle that never
reads mid_job_service, with no error. Worse, someone "restoring" the documented behaviour would
add brand literals into core.

### L4 · MEDIUM · reason-obsolete · seen in run1+run2 — `listeners/job_metrics.py:128-132`

**SAYS.** # RP-013e/METRICS-2/REC-5: battery has NO writer today even though both # shipped
adapters declare entities.battery — every counter sample reads # last_battery_percent, and with
nothing ever setting it, every sample # carries battery=None, which is OBS-B-3's null per-room
battery_delta # at source. Same declared-entity pattern as cleaning_time/cleaning_area.

**DOES.** The three lines immediately below the comment ARE the writer: `battery_entity =
entities.get("battery")` / `if battery_entity: watch_map[battery_entity] = (vacuum_entity_id,
"last_battery_percent", "int", None)`. That entry drives `_handle_metrics_change` ->
`record_active_job_sensor_value(key="last_battery_percent", ...)` on every battery state change,
so last_battery_percent is set and counter samples carry a real battery value. The file's own
convention marks history in the past tense (METRICS-5: "the annotation WAS a stale 3-tuple";
METRICS-4: "PREVIOUSLY wired on an entity KEY GUESS alone"); this one is present tense.

**MISLEADS.** A maintainer investigating null per-room battery_delta reads "every sample carries
battery=None" as a current statement of fact, concludes the metrics listener is the root cause,
and goes looking for a missing writer that is on the next line — while the real cause (adapter
not declaring entities.battery, entity unavailable, or a downstream consumer) goes unexamined.
The wrong direction of error: it accuses working code.

### L5 · MEDIUM · stale-reference · seen in run1 — `listeners/job_metrics.py:75-82`

**SAYS.** """Register listeners that push job-metric sensor values into active_job_state. Tracks
cleaning_time, cleaning_area, and station water level. ...""" — and the module docstring at line
1-2: "Job metrics listeners — push cleaning_time / cleaning_area / station water sensor values
into active_job_state as they update."

**DOES.** register() builds watch_map with FOUR writers, not three: cleaning_time (line 106),
cleaning_area (line 122), battery -> `last_battery_percent` (lines 133-135), and station water
(lines 154-162). Battery is absent from both enumerations.

**MISLEADS.** Both docstrings read as a complete enumeration of what this listener owns. Someone
tracing "who sets last_battery_percent?" consults the module and function contracts, sees
battery is not listed, and looks elsewhere — or, registering a new metric, assumes the battery
watcher is vestigial and prunes it. It also compounds the stale METRICS-2 comment above: the
docstring appears to corroborate "battery has no writer".

### L6 · MEDIUM · over-scoped · seen in run1+run2 — `listeners/lifecycle.py:373-374`

**SAYS.** # No-op for non-sequenced jobs (the flag is only set on a phase # advance,
queue_engine.advance_active_job_phase).

**DOES.** `_phase_dispatch_pending = True` is set in THREE places, only one of which is a phase
advance: queue/queue_engine.py:615 (advance — the named one), core/manager.py:6975 at INITIAL
dispatch of phase 0, whose own comment says "Sequenced (strict-order) job: guard + confirm the
FIRST phase exactly like an advanced one", and jobs/phase_runner.py:372-373, which re-asserts
the flag after an HA restart cleared it ("Re-assert the dispatch guard the restart cleared").
The "No-op for non-sequenced jobs" half is correct — all three sites are gated on `phases` — but
"only set on a phase advance" is not.

**MISLEADS.** It tells the reader the flag cannot be set before the first advance. A maintainer
debugging a strict-order run that will not finalize at the START of the job (phase 0, or the
first tick after an HA restart mid-run) would rule this suppression branch out on the strength
of the parenthetical, when it is exactly the branch holding finalization off — and would not
think to look at manager.py:6975 or phase_runner.py:373 because the comment names one owner.

### L7 · MEDIUM · over-scoped · seen in run1+run2 — `listeners/dock_events.py:3-4`

**SAYS.** Subscribes to each managed vacuum's dock_status entity (per adapter config). When the
state transitions into a configured trigger value, records the event into the manager's
persistent dock-events store.

**DOES.** register() skips any vacuum whose `dock_events.enabled` is not truthy BEFORE it ever
looks at dock_status (lines 77-80), and the fallback is False (`fallback=False`, matching
config_schema.py:778-784 "Default: False"). Of the two shipped adapters only Eufy declares
`"enabled": True` (adapters/eufy/adapter.py:582); adapters/roborock/adapter.py:893 lists
dock_events among the blocks it deliberately omits entirely — so a managed Roborock gets no
dock_status subscription at all. "Each managed vacuum" is true of no adapter by default and
false of one shipped adapter today.

**MISLEADS.** Someone asking "why are no dock events recorded for my Roborock / my new brand?"
reads the module contract, sees subscription promised for each managed vacuum, and hunts
downstream — the trigger vocabulary, the edge test, record_dock_event — instead of the one-line
enabled gate that returned before any of it ran. The REG-4 comment inside register() states the
real rule, but the module docstring is what a reader opens first.

### L8 · MEDIUM · false · seen in run1+run2 — `listeners/lifecycle.py:80-82 (above _DEFAULT_COMPLETION_TASK_STATUS / _DEFAULT_CLEAR_SENTINELS)`

**SAYS.** # Generic completion fallbacks. Used by get_adapter_value when the adapter # registry
is absent. The task_status value is the normalized "job done" # string; the clear sentinels are
standard HA empty/unavailable states.

**DOES.** Two errors. (a) Wrong function: `_DEFAULT_CLEAR_SENTINELS` is passed to
`get_adapter_vocab`, not `get_adapter_value` (lifecycle.py:322-326); only
`_DEFAULT_COMPLETION_TASK_STATUS` goes through `get_adapter_value` (lifecycle.py:317-321). (b)
Wrong condition: both helpers return the fallback whenever the key path is missing, not only
when the registry is absent (listeners/_common.py:67-76 and :97-99, which delegates to
adapters/registry.get_adapter_value "if registry is absent, path is missing, or any error
occurs"). adapters/roborock/adapter.py:378-392 registers a `completion` block containing
`task_status_value` and `require_job_active_clear` but NO `secondary_clear_sentinels`, so on
live Roborock hardware `_DEFAULT_CLEAR_SENTINELS` is in force with the registry fully present.

**MISLEADS.** A maintainer changing `_DEFAULT_CLEAR_SENTINELS` believes the blast radius is
limited to vacuums with no registered adapter, when the constant actually governs the live
Roborock completion gate's degradation path — the sentinel check
`completion_secondary_satisfied` falls through to (listeners/_common.py:292-300) exactly when
`entities.job_active` is undeclared or resolves to nothing, i.e. the issue #46 / #51 shape the
surrounding code is built around. Grepping for `get_adapter_value` to find the fallback's
consumers also misses the real call site.

### L9 · MEDIUM · over-scoped · seen in run1+run2 — `listeners/_common.py:243-249 (completed_finalize_signals, the job_active_present comment)`

**SAYS.** # PRESENCE, not value. `completion_secondary_satisfied` used to accept a # DECLARED
job_active key as proof the signal existed; on a localized install # the declared id resolves to
nothing and the gate reported "satisfied" about # an entity that was not there (issue #51). An
entity that is absent or # unavailable reads "" above, so this is False exactly when there is no
# signal to trust.

**DOES.** The local _state() (lines 230-236) returns "" only when entity_id is falsy, when
hass.states.get() returns None, or when state.state is None. An entity that EXISTS but currently
reads "unavailable" (or "unknown") returns the string "unavailable", so bool(...) is True and
job_active_present is True. The absent case works as described; the unavailable case does the
opposite of what the comment says, and "False exactly when there is no signal to trust"
therefore does not hold.

**MISLEADS.** completion_secondary_satisfied (line 292-296) short-circuits to True whenever the
flag is set AND job_active_present is truthy — skipping the clear-sentinel check entirely. A
Roborock job_active binary that blips to "unavailable" mid-run therefore reports the completion
secondary as satisfied on the strength of a signal that is currently unreadable. Someone
auditing the issue #51 fix reads this comment and concludes the indeterminate case is already
covered.

### L10 · MEDIUM · false · seen in run1+run2 — `listeners/_common.py:219-222 (completed_finalize_signals docstring)`

**SAYS.** Reads entity IDs from the adapter registry. Returns empty strings for absent or
unavailable entities — the caller compares values against configured sentinels and task_status
values.

**DOES.** _state() returns "" for an absent entity id and for a missing state object, but
returns the lowercased state string for an entity that exists and reads "unavailable"/"unknown".
All five returned keys (vacuum_state, task_status, dock_status, active_target,
job_active_present) carry that behaviour — e.g. active_target for an unavailable entity comes
back as "unavailable", not "".

**MISLEADS.** The docstring names the callers' contract ("the caller compares values against
configured sentinels"). listeners/lifecycle.py:322-344 and jobs/active_job.py:3087-3142 compare
active_target against clear_sentinels; a caller trusting this docstring would not think to
include "unavailable" in its sentinel handling, because it believes the helper already collapsed
it to "".

### L11 · MEDIUM · false · seen in run1+run2 — `listeners/discovery.py:166-168 (_on_vacuum_state)`

**SAYS.** # Only fire on transition INTO docked — filter out # repeat docked-to-docked attribute
updates and unknown # → docked startup noise.

**DOES.** The predicate is `if new_state == "docked" and old_state != "docked":`. It filters
docked→docked as claimed, but "unknown" != "docked" so an unknown→docked transition PASSES and
fires a full discovery pass; so does None→docked (no prior state at all, i.e. the first sighting
after a restart) and unavailable→docked. The sibling predicate in the same package,
_common.is_dock_trigger_edge (lines 133-141), refuses exactly these cases (`if old_val in ("",
"unavailable", "unknown"): return False`) — this is the shorter copy of that guard.

**MISLEADS.** The comment states the startup case is handled, so nobody looks here when a
discovery pass (async_refresh_room_source + run_discovery_pass + async_save, lines 122-127)
fires on every HA restart where the vacuum comes back docked. Drift history is written on that
path, and drift accrues the removal strikes that decide which rooms are flagged gone.

### L12 · MEDIUM · stale-reference · seen in run1+run2 — `listeners/discovery.py:14-16 (module docstring)`

**SAYS.** Manual rescan via ``setup_discover_rooms`` service also updates drift history (wired
separately in services.py — the service path is always available regardless of which auto
triggers are declared).

**DOES.** There is no `setup_discover_rooms` service anywhere in the integration. The service is
`discover_rooms` — const.py:80 `SERVICE_DISCOVER_ROOMS = "discover_rooms"`, declared at
services.yaml:22, handled by `_handle_discover_rooms` in services/rooms.py:169 (which does run
the drift update, at line 178). There is also no services.py: services/ is a package, and the
discover_rooms wiring lives in services/rooms.py.

**MISLEADS.** `eufy_vacuum.setup_discover_rooms` fails with "Action not found", and the name
looks plausible because a `setup_unreject_rooms` service really does exist (services.yaml:80) —
so a reader assumes the setup_ prefix is the convention and that the call is correct. The
"services.py" pointer sends anyone verifying the claim to a file that does not exist.

### L13 · MEDIUM · reason-obsolete · seen in run1+run2 — `listeners/discovery.py:11 (module docstring, trigger list)`

**SAYS.** - ``config_entry_reload`` — one-shot pass right now (setup time)

**DOES.** register() wraps that trigger in `async_at_started(hass, callback(lambda _hass,
_run=run_pass: _run()))` (lines 149-153), i.e. it is DEFERRED until HA has finished starting,
and only runs immediately when HA is already running. The inline comment 130 lines below states
the opposite of the docstring, deliberately: "Run it once HA has fully started, not at raw setup
time: a service-response source (Roborock get_maps) may not be registered yet then ('Action ...
not found'), so an at-setup pass logs a spurious warning and falls back to the cached source."

**MISLEADS.** The docstring is the summary a reader hits first, and it directly contradicts the
code and the inline rationale. Someone debugging why the room list is still stale immediately
after a config-entry setup at boot would conclude the pass already ran; someone 'restoring' the
documented behaviour would reintroduce the Roborock get_maps warning the deferral exists to
avoid.

### L14 · MEDIUM · reason-obsolete · seen in run1 — `adapters/roborock/adapter.py:765-766 (room_attribution block) — adjacent file, found while verifying pose_sampler`

**SAYS.** `source: native_current_room` makes the pose sampler read that entity, slugify # the
name, and match it to a managed room id (listeners/pose_sampler.py). No # decoded-map pose is
decoded here (anchor/heading stay None).

**DOES.** pose_sampler._read_native_current_room_sample (lines 267-282) reads
async_get_map_live_pose and banks both anchor and heading whenever the adapter declares
map_state_source.live_pose — which this same adapter does, 35 lines above at line 729
(`"live_pose": {"backend": "parsed_mapdata", "pose_refresh_s": 30.0}`). pose_sampler's own
docstring (lines 250-255) records the change explicitly: "``anchor`` used to be the literal
``None`` here, with the standing rationale that this source has 'no pixel pose' ... the literal
was the only thing keeping the pose ring anchor-less, which in turn is why a stall capture had
no trail to draw."

**MISLEADS.** This is the surviving copy of the rationale that pose_sampler retired. Read as
authority it says Roborock captures carry no position — which is precisely the "a brand having
no dot for months" state stall_capture.py:275-277 now emits a receipt to detect. Anyone
reasoning about whether the pose ring holds Roborock anchors would conclude it does not.

### L15 · MEDIUM · over-scoped · seen in run1+run2 — `listeners/path_blockers.py:55-58 (_PATH_BLOCKER_INFLIGHT)`

**SAYS.** #: RP-008 (A6-GUARD-2): per-run single-flight for _process — a burst of blocker #:
edges used to spawn one unbounded task per event. One evaluation runs; one #: re-check is queued
behind it; further arrivals coalesce into that re-check.

**DOES.** The single-flight state is not per-run and not per-entity — it is one dict for the
whole integration: `inflight = hass.data.setdefault(DOMAIN,
{}).setdefault(_PATH_BLOCKER_INFLIGHT, {"running": False, "rerun": False})` (lines 263-265),
keyed by a bare string with no vacuum, map, job or entity in the key.
_handle_path_blocker_change is the single shared callback for every watched blocker entity
(registered over list(watch_map.keys()) at line 282-286), and it builds a FRESH _process closure
per event, bound to that event's entity_id and new_state (lines 159-161, 170). So when entity B
is mid-evaluation and entity A's edge arrives, A's _process_single_flight sets inflight["rerun"]
= True and returns (lines 268-270) — and what the while loop at 274-276 then re-runs is B's
closure, over watch_map[B] with B's trigger state. A's own _process is discarded and never runs.

**MISLEADS.** 'Further arrivals coalesce into that re-check' is true only for arrivals on the
same trigger entity; a cross-entity arrival is dropped, not coalesced. Two door sensors on
different maps (or two vacuums) sharing this one flag means a genuine blocker edge on one is
swallowed by an in-flight evaluation of the other, and its (vacuum, map) targets from watch_map
are never visited at all — no report, no EVENT_PATH_BLOCKED, no configured pause_and_event or
cancel_and_event. 'per-run' is the specific word that hides it: a reader assumes the flag is
scoped to a job and that concurrent runs are independent, so the missed cancel looks like a
manager bug rather than the coalescer, and the very GUARD-2 double-cancel window the constant
cites is only actually closed for a single trigger entity.

### L16 · LOW · stale-reference · seen in run1+run2 — `listeners/lifecycle.py:3-4`

**SAYS.** Watches the vacuum entity + adapter-declared lifecycle entities (task_status,
dock_status, active_cleaning_target, active_map).

**DOES.** The watch set comes from `get_lifecycle_watch_entities`
(listeners/_common.py:162-171), which appends FIVE keys: task_status, dock_status,
active_cleaning_target, active_map, and `job_active`. job_active is omitted from the docstring's
list despite being load-bearing — _common.py:159-161 explains it is watched precisely so "its
clear at the true finish re-triggers finalization", and lifecycle.py:359-362 consumes exactly
that transition as the recharge-resume guard.

**MISLEADS.** The parenthetical reads as the exhaustive watch list. Someone debugging why a
Roborock run never re-evaluates finalization when binary_sensor.<vac>_cleaning clears would
conclude from this docstring that the binary is not watched and that a new subscription is
needed — when it is already in the set and the fault lies elsewhere (e.g. the HA 2026.7 never-
created case documented in job_active_signal.py).

### L17 · LOW · stale-reference · seen in run1+run2 — `listeners/pause_timeout.py:212`

**SAYS.** """Cancel paused jobs that exceed their configured timeout."""

**DOES.** register() installs a 1-minute ticker that runs `_reap_one_slot`, which does three
things, only one of which is cancelling timed-out paused jobs: (0) reconciles the job's paused
flag with the robot's actual state in BOTH directions, including calling `resume_active_job` on
a job marked paused when the robot is not (lines 97-127); (1) the paused-timeout cancel; and (2)
the stranded-`started` reap, which finalizes a NEVER-paused run as `interrupted` and fires
EVENT_JOB_FINISHED + EVENT_RUN_INCOMPLETE (lines 167-207). The module docstring documents all of
this; the function docstring was not updated when FN-1 landed.

**MISLEADS.** register()/remove() are the module's declared public surface, so this one line is
the contract a caller reads. It hides that unloading this listener also disables stranded-run
reaping and the app/robot-side pause reconciliation — someone disabling "the pause timeout" to
stop unwanted cancels would silently also strand every interrupted run, with no indication from
the contract that they had done so.

### L18 · LOW · over-scoped · seen in run1 — `listeners/pose_sampler.py:95-97 (_FALLBACK_INTERVAL_S)`

**SAYS.** # Absolute last-resort cadence — only if the resolved engine declares no interval_s
default # at all (e.g. the noop engine). The OPERATIVE default comes from the engine's
DEFAULT_TUNING # (single source, no duplicated literal); the OPERATIVE value from the adapter's
tuning.

**DOES.** _room_attribution_interval_s returns _FALLBACK_INTERVAL_S on two paths, not one. Line
116 is the documented one (no engine default). Line 117-118 is not: `except (TypeError,
ValueError): return _FALLBACK_INTERVAL_S` fires whenever the adapter DID declare an interval_s
that float() cannot parse. That is reachable — adapters/registry.py:163-183 hard-raises only for
`source == "config"`; a code-sourced adapter (both shipped brands) with a bad tuning value is
warn-only and registers anyway.

**MISLEADS.** "only if ... (e.g. the noop engine)" reads as a dead defensive branch, since a
noop-engine vacuum is not sampled at all. In fact a malformed interval_s on a non-Eufy brand is
silently replaced with Eufy's 2.0 s — the over-sampling POSE-1 exists to prevent — with no
signal beyond a registration warning.

### L19 · LOW · over-scoped · seen in run1 — `listeners/path_blockers.py:4 (module docstring)`

**SAYS.** Watches every blocker rule's trigger entity across all managed rooms.

**DOES.** register() (lines 91-113) skips any map whose id normalizes to "unknown" (line 93),
skips rules with `enabled` false (line 103), skips rules whose kind is not "blocker" (line 105),
and skips rules with an empty entity_id (line 107). So rooms carried on the "unknown" map
pseudo-id have their blocker rules unwatched entirely, and disabled rules are not watched.

**MISLEADS.** "every ... across all" invites the reader to treat a missing path-block event as a
delivery or timing problem rather than a registration exclusion. The "unknown" map skip is the
silent one — a configured blocker on a room that has not yet been bound to a real map id never
gets a watcher, and nothing logs that.

### L20 · LOW · false · seen in run1+run2 — `listeners/stall_capture.py:8-10 (module docstring)`

**SAYS.** ``EVENT_STALL_DETECTED`` is NOT this feature's event. It already feeds
``detect_run_anomalies``, which sets the ``stall`` / ``running_long`` / ``skipped`` fields the
card's snapshot reads.

**DOES.** The dependency runs the other way. detect_run_anomalies (jobs/active_job.py:1073) is
the PRODUCER: it computes the stall/running_long/skipped fields and, when emit=True, fires
EVENT_STALL_DETECTED itself (line 1186). Nothing subscribes to the event to derive those fields
— the only listeners are this module (line 412) and sensor wiring for other events.

**MISLEADS.** A reader looking for the second consumer that the paragraph's whole argument rests
on will not find one, and may conclude the paragraph is stale in some larger way. The argument
itself is sound — the detector does fire unconditionally and gating it would break anomaly
reporting — only the stated direction of flow is inverted.

### L21 · LOW · false · seen in run1 — `listeners/pose_sampler.py:377 (register docstring)`

**SAYS.** Sample pose into external runs at the adapter's room_attribution cadence.

**DOES.** _SAMPLED_STATUSES = ("external", "started") (line 94), and _sample_vacuum_once samples
DISPATCHED runs too. The module docstring states why that matters: the dispatched samples feed
"``reconcile_dispatched_identity``'s 'rescued' branch — the room identity stamped on a
DISPATCHED run's timings".

**MISLEADS.** The one-line summary is what shows in an editor's hover and in generated API docs.
Anyone gating or short-circuiting this listener on "is this an external run" would silently
break the dispatched-run identity reconcile, which the module docstring warns is not an inert
capture buffer.

### L22 · LOW · stale-reference · seen in run1+run2 — `listeners/_common.py:15 (module docstring, Public surface)`

**SAYS.** - completed_finalize_signals(hass, vacuum_entity_id) -> dict[str, str]

**DOES.** The function is annotated `-> dict[str, Any]` (line 217) and the returned dict is not
homogeneous: the job_active_present key holds a bool
(`bool(_state(entities.get("job_active")))`, line 249), added when the issue #51 presence check
landed. The other eight entries in this Public surface list match their functions.

**MISLEADS.** A caller trusting the listed type would treat job_active_present as a string — and
`"False"` is truthy, so a str()-shaped guard written against this signature would invert the
presence check it is guarding.

### L23 · LOW · false · seen in run2 — `listeners/job_metrics.py:1-2 (module docstring) and :77 (register docstring)`

**SAYS.** Module: "Job metrics listeners — push cleaning_time / cleaning_area / station water
sensor values into active_job_state as they update." register(): "Tracks cleaning_time,
cleaning_area, and station water level."

**DOES.** `register()` builds four kinds of watch_map entry, not three: cleaning_time
(:106-120), cleaning_area (:122-126), **battery** (:133-135, key `last_battery_percent`), and
station water (:154-162). Both docstrings present a closed three-item enumeration that omits the
battery watcher entirely.

**MISLEADS.** Battery is the input to per-room battery_delta in the learning pipeline
(jobs/active_job.py:2272). A reader trusting either enumeration concludes battery is sourced
somewhere else — or, when battery_delta comes out wrong, does not look in this file at all. It
is also the one watcher of the four with no unit/normalization handling, so it is the one most
likely to need attention.

### L24 · LOW · stale-reference · seen in run2 — `listeners/job_progress.py:22-23 (module docstring)`

**SAYS.** can refresh its snapshot if it's open. Cost per tick: one method call and one event
per active vacuum/map; negligible.

**DOES.** The tick body now makes up to three manager calls per in-flight slot, not one:
`maybe_pulse_live_room_refresh` (job_progress.py:127), `apply_job_progress_tick` (:135), and
`apply_stuck_watch_tick` (:156) — plus the one `EVENT_JOB_PROGRESS_TICK` fire (:167). The stuck-
watch call was added after this sentence was written and carries its own justification 9 lines
above it ("Stuck detection rides THIS ticker rather than a fourth timer", :147).

**MISLEADS.** The sentence is the stated cost budget for the 5-second cadence, and it is the
thing anyone weighing "can we add one more thing to this ticker?" or "is 5s too aggressive at N
vacuums?" will quote. It now understates the per-tick work by roughly 3x, and
`apply_stuck_watch_tick` in particular is documented as deliberately synchronous throughout
(core/manager.py:4776-4786) — i.e. it holds the event loop, which is exactly the property a
"negligible" budget invites people to stop checking.

### L25 · LOW · stale-reference · seen in run2 — `listeners/_common.py:270-272 (completion_secondary_satisfied docstring, the require_job_active_clear bullet)`

**SAYS.** RP-033/COMMON-2: only honored when ``entities.job_active`` is actually declared — the
flag names the entity that supplies the real signal, so a config that sets it without declaring
the entity used to short-circuit to True unconditionally with nothing backing it.

**DOES.** Declaration is necessary but no longer sufficient. The body (lines 292-296) requires
BOTH `get_adapter_value(vacuum_entity_id, "entities", "job_active", fallback=None)` AND
`completion_signals.get("job_active_present")` before returning True. The inline comment
immediately above it (lines 283-291) says so explicitly and names the docstring as out of date:
'RP-033/COMMON-2 tightened this from "flag set" to "entity declared", which is one step short'.

**MISLEADS.** The docstring documents the tightening it has already been superseded by, and the
correction lives only in a body comment a reader of the contract never reaches. Someone
reasoning about why a Roborock run failed to finalize checks only that entities.job_active is
declared, finds it is, and rules this branch out — when the actual refusal came from the second
condition. It also under-sells the guard to anyone auditing whether issue #51 is closed.

### L26 · LOW · stale-reference · seen in run2 — `listeners/pose_sampler.py:7-8 (module docstring, opening paragraph)`

**SAYS.** buffers one ``{current_room, anchor, cleaning_area}`` sample per tick into the
external slot's ``pose_samples`` (via ``record_pose_sample``).

**DOES.** The sample carries four fields, not three. _read_live_pose_sample (lines 230-235) and
_read_native_current_room_sample (lines 283-288) both build and return a "heading" alongside the
other three, _sample_vacuum_once passes heading=sample["heading"] to record_pose_sample (line
326), and ActiveJobTracker.record_pose_sample takes it as a real parameter
(jobs/active_job.py:2423, heading: float | None = None). pose_store._FIELDS likewise lists
heading.

**MISLEADS.** The braces read as the sample's shape, not as an example, so anyone consuming
pose_samples from this docstring — writing an engine, a fixture, or an export — omits heading.
The stale triple has already propagated: pose_store.py's own module docstring repeats the
identical three-field set, so a second file now corroborates the wrong shape and a reader who
cross-checks gets agreement rather than the correction.

## BATTERY COMMENT AUDIT — 2026-08-22. 33 findings. NOT APPLIED.

Severity {'high': 5, 'medium': 17, 'low': 11}. Kind {'false': 6, 'over-scoped': 22, 'reason-obsolete': 2, 'adopted-alternative': 1, 'stale-reference': 2}.

⚠ **RECOVERED LATE.** These were produced by the battery doc pass and lived only in a session
scratchpad temp file and the handoff — neither durable. Written into the ledger 2026-08-22 once
that was noticed. If a future pass produces findings, log them the same day.

**67% over-scoped** (22 of 33) — the highest of the three subsystems audited (rooms 55%,
listeners 26%). Only 6 were plainly false. Over-scoping is the defect that survives review,
because a statement true of the common case reads as correct.

⚠ **SINGLE RUN.** The listeners pass proved that re-running an audit with an identical prompt
returns a different set — 38% of its union appeared in one run only. This pass was run ONCE and
should be assumed to under-enumerate by a similar margin.

The highest-value item was promoted to **C54** (session `avg_rate_per_min` divides a guarded sum
by an unguarded count). The `_update_health` CC-direction inversion below is the other one I
verified against source myself.

⚠ **Not applied.** Re-verify before editing.

---

### B1 · HIGH · false — `battery/manager.py::_update_health (docstring, L1111-1113)`

**SAYS.** - cc_charge_speed_pct: capacity proxy (50→80). Aged cells hold less energy per
percent, so %/min rises with age and ratio falls below 100. Higher = healthier.

**DOES.** The ratio is `value = round(baseline_value / current * 100.0, 1)` (_compute_regime_pct
L1269) where both terms are cc_min_per_pct = MINUTES PER PERCENT (`round(cc_dur / cc_pct, 4)`,
L1008). If %/min rises with age, min/pct FALLS, so `current` shrinks and the quotient RISES
ABOVE 100. The same docstring's CV bullet (falling %/min -> ratio below 100) is correct, and the
two cannot both fall below 100 through the one shared formula when the file itself states at
L205-207 that 'capacity loss raises %/min in CC, resistance rise lowers %/min in CV'.
battery/sensors.py's module docstring states the same physics and pointedly does NOT draw the
'falls below 100' conclusion for CC.

**MISLEADS.** A reader (or a card/sensor author) concludes a LOW cc_charge_speed_pct means an
aged pack. It is the inverse: capacity loss drives the CC index UP past 100. Anyone diagnosing a
degraded battery would read the CC sensor exactly backwards, and 'Higher = healthier' is wrong
for that half of the pair.

### B2 · HIGH · false — `battery/manager.py::module docstring 'Persistence' (L69-72) and _schedule_save (docstring, L1616-1617)`

**SAYS.** module: "It reads/writes via the main ``EufyVacuumManager``'s storage helpers so it
benefits from the existing debounced save loop." _schedule_save: "Saves are idempotent, so even
rapid-fire calls just coalesce in the storage layer."

**DOES.** _schedule_save calls `self._manager.async_save()` (L1625). core/manager.py:1153
`async_save` awaits `self.storage.async_save(self.data)`, and core/storage.py:60 is documented
"Save stored data immediately." -> `self._store.async_save(data)`. Nothing coalesces. The
debounced path exists and is a DIFFERENT method the battery manager never calls:
core/manager.py:1162 `async_save_delayed` -> core/storage.py:64 `async_save_delayed`, whose own
docstring says 'rapid successive callers collapse into ONE write `delay` seconds after the last
call, instead of one write per call.'

**MISLEADS.** _process_sample calls _schedule_save on EVERY accepted battery sample (and every
state event on two entities). Both comments tell a reader that is cheap because the storage
layer coalesces. It does not — each sample is a full-integration-data disk write. Anyone
auditing write amplification, or deciding whether it is safe to add another _schedule_save call,
is told the wrong thing by the two comments that exist to answer exactly that question.

### B3 · HIGH · over-scoped — `battery/manager.py::module docstring 'Charge sessions' (L34-45)`

**SAYS.** "...and closes when one of: - ``charging`` transitions to False - battery reaches 100%
- a sanity timeout (``SESSION_MAX_HOURS``) elapses without a closing event Closed sessions are
summarized (start/end battery, duration, avg/min/max rate) and: - written to ``sessions.csv`` -
appended to a recent-history ring buffer in storage (size ``HISTORY_LIMIT``)"

**DOES.** The timeout path is NOT a close. _update_session L889-898 sets
`record["current_session"] = None` directly, logs "battery: discarding stale session", and sets
`session_was_discarded = True`. It never calls _close_session, so no summary is built,
`raw_store.append_session` is never invoked (no sessions.csv row), and nothing is appended to
session_history_recent. The local variable is literally named `session_was_discarded`. Only the
other two listed events reach _close_session (L952-953).

**MISLEADS.** A reader debugging 'why is there no CSV row for that overnight dock?' is told by
the front-door docstring that a timed-out session is summarized and persisted like any other. It
is silently thrown away. Two of the three listed close events persist; the third destroys — and
the list presents them as equivalent.

### B4 · HIGH · over-scoped — `battery/sensors.py::_bucket_means / _MEAN_SAMPLE_FIELD`

**SAYS.** #: Which honest denominator belongs to which mean (C17). ``count`` counts every job #:
in the bucket; a mean is computed only over the jobs that carried BOTH of its #: inputs.
Publishing the pair without this was the second half of the defect — the #: card showed "3.333
%/m2 — Jobs: 10" where the mean was over six. ...and in _bucket_means: "``count`` stays, because
it is a true and separate fact about the bucket — but it is no longer the only number next to a
mean it does not describe."

**DOES.** The samples/mean pairing is applied ONLY to the by_clean_mode / by_fan_speed /
by_water_level buckets (sensors.py:451-453, via _bucket_means). Twenty lines earlier in the SAME
dict literal, LastJobMetricSensor.extra_state_attributes publishes `"all_jobs_mean":
all_jobs.get(mean_field)` (line 448) beside `"all_jobs_count": all_jobs.get("count")` (line 449)
with no samples sibling — exactly the pair the comment names as the defect. The data is
available: `all_jobs` is a `_new_aggregate_bucket()` (manager.py:275, 292-317) and carries
`samples_duration` and `samples_area` just like every by_* bucket. So `count` IS still the only
number next to a mean it does not describe, in the same function, for the aggregate the card
headlines.

**MISLEADS.** A reader auditing the C17 repair reads "no longer the only number next to a mean
it does not describe" as a completed fix and stops. They will not notice that the all_jobs row —
the one the comment's own worked example ("Jobs: 10" over six) is about — was never given a
samples field, even though `all_jobs["samples_area"]` exists and is one `.get()` away. This is
the partial-guard-reads-as-complete shape: the guard exists, so it reads as total.

### B5 · HIGH · over-scoped — `battery/sensors.py::LastJobMetricSensor`

**SAYS.** """Generic sensor exposing one of the last-job battery_metrics fields. State is the
most recent completed job's metric (None if no job yet).

**DOES.** native_value returns None in three distinct situations, only one of which is "no job
yet": (1) `last_job` is absent; (2) `last_job` exists but the metric is None. For the
`drain_per_m2` instance, job_metrics.py:77 computes `drain / area` only `if drain is not None
and area`, so the metric is None on every recorded job whose cleaning_area_m2 was missing — and
manager.py:1500-1502 states outright that "Area is the read that goes missing in practice: it
loses the same finalize-time race job_finalizer.py documents for cleaning_time, and no learning-
blocker stops such a job being recorded." For the per_min/per_hour instances, `_safe_drain`
(job_metrics.py:124-131) returns None whenever `end > start`, i.e. any job that finished with
more battery than it started — precisely a mid-job-recharge run — and `_positive_float` returns
None for a zero/absent duration.

**MISLEADS.** The parenthetical states what a None means, and it states the wrong thing. A user
(or an automation, or a card) seeing sensor `last_job_drain_per_m2` unavailable concludes no job
has run since restart, when the routine cause is a recorded job whose area read lost the
finalize race. The module the sensor reads from documents that exact failure as common; the
sensor docstring hides it behind "no job yet".

### B6 · MEDIUM · reason-obsolete — `battery/manager.py::REGIME_PCT_MIN / REGIME_PCT_MAX (L117-120)`

**SAYS.** "The ceiling is the load- bearing one: charging measurably FASTER than when the
baseline was taken is something a cell cannot do, so anything above it is a measurement
artefact." (and, for the floor) "a genuinely tired pack reading 30 is grim but real"

**DOES.** The band is enforced by _compute_regime_pct (L1276), which is called for BOTH regimes
— cc at L1182 and cv at L1185. The justification only holds for CV. The file's own L205-207 says
'capacity loss raises %/min in CC', and an aged pack therefore charges measurably faster PER
PERCENT in the CC window — precisely the thing the comment says a cell cannot do. Symmetrically,
the floor's 'a tired pack reading 30' is a CV story; a tired pack's CC index moves the other
way.

**MISLEADS.** The comment presents an out-of-band CC value as necessarily a measurement
artefact. On the CC side a ratio climbing toward 150 is the degradation signal, and rejecting it
(into None + a 'rejected' field) hides exactly what the proxy exists to show. Someone widening
or removing the ceiling would be arguing against a rationale that was never evaluated for the
regime it is applied to.

### B7 · MEDIUM · false — `battery/manager.py::_compute_regime_pct (docstring, L1240-1241)`

**SAYS.** "Exactly one of the two is ever non-None."

**DOES.** Three separate paths return `(None, None)` — no baseline (L1244), no usable session
value (L1264), and `current <= 0` (L1268). On a fresh install (None, None) is the normal,
dominant return. Only 'at most one of the two is ever non-None' is true.

**MISLEADS.** A caller reading 'exactly one' would treat `(None, None)` as impossible and could
infer 'value is None, therefore rejected is populated, therefore a figure WAS computed and
thrown out'. That is the precise confusion the adjacent live:BATT-CV-1 comments say RP-045
'spent a whole packet undoing' — rejected vs never-computed.

### B8 · MEDIUM · over-scoped — `battery/manager.py::compute_time_to_target_pct (docstring, L411-417)`

**SAYS.** " 2. The cross-session ``stats.rate_*_zone_per_min`` — but ONLY when there ISN'T a
currently open session that could have produced its own sample for this zone and simply hasn't
yet. ... Source ``"zone_rate"``."

**DOES.** _span_minutes L506 is `rate = stats.get(stats_rate_key) or
stats.get("rate_overall_per_min")`. When the zone stat is absent it silently falls back to
`rate_overall_per_min` — the UNZONED instantaneous rate, which may have been measured anywhere
on the curve (mid zone, or the opposite zone) — and still labels the result `"zone_rate"`
(L508). The enumerated 4-tier precedence never mentions this tier, and `source` reports a zoned
measurement that was not zoned.

**MISLEADS.** The docstring is written as an exhaustive precedence ladder, and the whole point
of `source` is documented at L428-430 as telling the card 'is this number still anchored to a
frozen reading, or not'. A CV-span ETA computed from a low-zone overall rate is reported to the
card as a high-zone measurement. Anyone reasoning about RP-044's cold-start contract from this
docstring cannot see the fallback.

### B9 · MEDIUM · false — `battery/manager.py::_update_mid_job_rate_stat (docstring, L1082-1084) and _new_record L280-281 / _close_session L1026-1028`

**SAYS.** "These sessions are the cleanest health signal we get — same start/end zone, same
thermal state — so a drop in the mean is an early sign of capacity loss before the 0→100
baseline shifts." (and, at the call site) "Mid-job recharges are gold-standard data — tight,
consistent 15→75 charge zone, in pure CC region."

**DOES.** No start/end zone gate exists anywhere on this path. _close_session L1029 admits a
session on `kind == "mid_job" and avg is not None and avg > 0 and delta_pct > 0` only —
start_battery and end_battery are never consulted. _classify_session_kind returns 'mid_job'
purely from _has_active_job. A 60→63 top-up during a paused job and a 15→75 deep recharge both
fold into the same running mean via `stats["rate_sum"] += avg` (L1094). The mean is over
whatever windows happened to occur, not over a consistent one.

**MISLEADS.** The comparability claim ('same start/end zone') is the entire justification for
treating a drop in this mean as a capacity-loss signal. Nothing enforces it, so the mean mixes
shallow high-zone top-ups (slow %/min, CV taper) with deep CC recharges (fast %/min); the mean
moves with charge-window mix, not cell health. A reader would trust this stat as a 'high-quality
second opinion' it is not, and would not think to add the gate because the comment says it is
already the case.

### B10 · MEDIUM · over-scoped — `battery/manager.py::record_job_metrics (docstring, L1431-1433)`

**SAYS.** "- Single-bucket runs additionally feed ``by_clean_mode``, ``by_fan_speed``, and
``by_water_level`` aggregates — only those jobs can be cleanly attributed to a single setting."

**DOES.** _apply_metrics_to_aggregates gates all three per-config buckets on `single_ok = not
bool(metrics.get("mid_job_recharge"))` (L1358, then L1360/1366/1372). A single-clean-mode run
that took a mid-job recharge is NOT folded into any per-config bucket. The docstring names
single-bucketness as the whole criterion and gives a reason ('only those jobs can be cleanly
attributed to a single setting') that does not cover the mid-job exclusion at all — that
exclusion has its own, different reason, documented only at the call site (L1355-1357).

**MISLEADS.** Someone reconciling by_clean_mode's `count` against the number of single-mode jobs
they know ran will find it short and go hunting for a lost-write bug. The exclusion is
deliberate; the public docstring of the entry point does not say so.

### B11 · MEDIUM · adopted-alternative — `battery/manager.py::module docstring 'Battery health proxy' (L48-51)`

**SAYS.** "We compute "minutes per 1% gained" for each completed deep-enough session (start ≤
50%, end ≥ 90%). The FIRST such session this install observes anchors the baseline. Average of
the LAST 14-day window of similar sessions is "current". ``health_pct = round(baseline / current
* 100, 1)``."

**DOES.** That whole-session model was replaced by the regime split. health_pct is now an alias
of cv_charge_speed_pct (L1199), computed only from `cv_min_per_pct` = minutes per percent WITHIN
the 80→90 window (L1009), over `cv_qualifying` = sessions passing _session_cv_qualifies (end >=
90 AND cv attribution present — the start battery is irrelevant to the cv side, per RP-045(ii)
at L1132-1136). The session-wide field this paragraph describes is explicitly retired: L256-259
says "The legacy session-wide `min_per_pct` field is intentionally absent". The 14-day window
also silently falls back to the single most recent qualifying session when nothing is in the
window (L1256-1264), which this paragraph does not mention.

**MISLEADS.** The file's front-door explanation of its headline number describes a model the
file elsewhere declares retired. A reader sizes health_pct as a whole-charge rate ratio and
looks for a start<=50 gate on the comparison set; there is none on the CV side. It also makes
the 'start ≤ 50%' criterion look like it governs health_pct, when it governs only the CC index
and the baseline anchor.

### B12 · MEDIUM · over-scoped — `battery/manager.py::module docstring 'Battery health proxy' (L53-54)`

**SAYS.** "While the baseline is being seeded (no qualifying sessions yet), health_pct is None."

**DOES.** Reads as the sole cause; there are at least three. health_pct is also None when a
figure WAS computed and rejected as outside REGIME_PCT_MIN..MAX (_compute_regime_pct L1276-1284,
the live:BATT-CV-1 path that sets health_unavailable_reason='implausible_regime_ratio'); when
the baseline is anchored but no retained session carries `cv_min_per_pct` (L1264); and when
`current <= 0` (L1268). The module docstring never mentions the plausibility guard at all,
despite it having its own 24-line constant comment at L104-126.

**MISLEADS.** A user or maintainer seeing health unavailable concludes 'still seeding, wait for
a deep charge' and waits — when the real state may be 'a value was computed and rejected as
impossible', which points at the session data, not at charging habits. That is exactly the
distinction L1206-1209 says the reason-code exists to preserve.

### B13 · MEDIUM · over-scoped — `battery/manager.py::compute_time_to_target_pct (docstring, L421-424)`

**SAYS.** "4. None of the above -> ``minutes=None`` — a cold-start install, where the caller
shows a live wall-clock "charging..." instead of a fabricated ETA (the charge-rate baseline
fills passively from every dock, so this self-heals within a sample or two of the session
opening)."

**DOES.** The CV span's tier-1 accumulator only fills while `zone == "high"`, i.e. battery_level
>= HIGH_ZONE_MIN (80) — _process_sample L765-771 via _zone_for. With a session open, tier 2 is
deliberately skipped (session_open_without_own_sample, L503-505), so a cold-start install
charging from e.g. 20% toward 95% gets cv_minutes=None until the pack actually reaches 80%, and
L464-465 then returns minutes=None for the WHOLE estimate. That is hours, not 'a sample or two'.

**MISLEADS.** Anyone triaging 'the ETA has said nothing for two hours on a new install' is told
by this docstring that the condition clears within a sample or two, so they look for a bug in
the accumulators rather than recognising expected behaviour. The claim is true of the CC span
and false of the CV span, and the docstring makes it about the estimate as a whole.

### B14 · MEDIUM · over-scoped — `battery/manager.py::_is_charging (docstring, L635-636)`

**SAYS.** "The local ``except`` branch below only fires for a legacy runtime manager that
doesn't expose ``_is_charging`` at all."

**DOES.** L640 is a bare `except AttributeError:` around
`self._manager._is_charging(vacuum_entity_id)`. The delegation is two hops deep —
core/manager.py:1251 `_is_charging` -> `self.active_job._is_charging(...)` ->
core/charging.is_charging — so an AttributeError raised ANYWHERE inside that chain (e.g.
`self.active_job` not yet assigned during setup ordering, which the surrounding comments
elsewhere in this file treat as a real condition) is caught identically and silently routes to
the substring fallback.

**MISLEADS.** The docstring states the delegate has 'no substring fallback' because substring
matching on task_status has known false negatives, then assures the reader the local substring
branch is unreachable outside legacy managers. If any AttributeError arises mid-chain the
integration silently reverts to the exact heuristic the design rejected, with no log line — and
the comment is what stops anyone looking for that.

### B15 · MEDIUM · false — `battery/store.py::_SAMPLES_FIELDS`

**SAYS.** # Non-null only when the per-sample MAX_DELTA_PCT guard rejected the # observed
raw_delta (firmware X-to-0 / 0-to-X flip, HA restart gap, # multi-hour self-discharge, etc.).
Carries the rejected magnitude # for post-hoc analysis. Grep `rejected_delta_pct` in
samples.jsonl # to find every rejection.

**DOES.** Two separate defects. (a) The grep instruction cannot work: append_sample writes
`json.dumps({k: sample.get(k) for k in _SAMPLES_FIELDS})` (store.py:81), a comprehension over
ALL of _SAMPLES_FIELDS using `.get()`, so the literal key `rejected_delta_pct` is emitted on
EVERY line, null when there was no rejection. `grep rejected_delta_pct samples.jsonl` matches
100% of lines. The working grep is `grep -v '"rejected_delta_pct": null'`. (b) "every rejection"
is over-scoped even for the field itself: the MAX_DELTA_PCT guard is not the only per-sample
rejection. manager.py:713-722 discards an implausible charge rate (>
MAX_PLAUSIBLE_RATE_PCT_PER_MIN) and records it as `record["stats"]["rejected_rate_per_min"]` — a
key that is NOT in _SAMPLES_FIELDS, so that rejection leaves no trace in samples.jsonl at all.
Out-of-order samples (elapsed_sec <= 0, manager.py:690) are also silently dropped from delta
accounting with both delta_pct and rejected_delta_pct left None, indistinguishable in the JSONL
from a first-ever sample.

**MISLEADS.** Someone doing post-hoc analysis runs the documented grep, gets back the entire
file, and either concludes every sample was rejected or gives up on the field. Worse, if they
filter correctly they still believe they are seeing every rejection, while an entire second
rejection class (implausible rate) is invisible in the audit trail the module docstring calls
"the long-term raw audit trail".

### B16 · MEDIUM · over-scoped — `battery/sensors.py::BatteryHealthSensor`

**SAYS.** Headline alias of cv_charge_speed_pct (the resistance-proxy regime). Kept under the
_battery_health entity_id for continuity with installs that pre-date the regime split. None
until the baseline is anchored.

**DOES.** health_pct is None in at least three states, only one of which is an un-anchored
baseline. manager.py:1230-1276 (_compute_regime_pct): returns None when `baseline_value is None`
(un-anchored — the documented case), when no retained qualifying session carries
`cv_min_per_pct` despite an anchored baseline, AND when the computed ratio falls outside
REGIME_PCT_MIN..REGIME_PCT_MAX (25.0–150.0), in which case it logs a warning and returns `(None,
value)`. The third state can only occur WITH an anchored baseline. The same docstring's own
attribute block two paragraphs down exposes `health_unavailable_reason`, whose value
`"implausible_regime_ratio"` (manager.py:1212) names exactly that anchored-but-None state.

**MISLEADS.** A reader debugging an unavailable health sensor with an anchored baseline
(baseline_anchored_at populated, baseline_cv_min_per_pct populated, state unknown) is told by
this docstring that the combination is impossible, so they look for a persistence or anchoring
bug. The actual cause — the plausibility rejection that the whole RP-045(iii) / live:BATT-CV-1
machinery exists to explain — is described nowhere in this class's prose, only in an attribute
the docstring does not connect to the None.

### B17 · MEDIUM · over-scoped — `battery/sensors.py::RegimeChargeSpeedSensor`

**SAYS.** Reads ``stats.<stat_key>`` and surfaces the matching baseline anchor in attributes.
Returns None until the baseline is anchored. Two instances live side-by-side (CC and CV) so
users can read the capacity and resistance signals independently.

**DOES.** Same over-scope as BatteryHealthSensor, and with no compensating attribute.
`cc_charge_speed_pct` / `cv_charge_speed_pct` are set from `_compute_regime_pct`, which returns
None for an anchored baseline whenever the ratio lands outside 25–150% (manager.py:1268-1276) or
no retained session carries the regime field. The rejected figure is stored as
`stats["cc_charge_speed_rejected_pct"]` / `stats["cv_charge_speed_rejected_pct"]`
(manager.py:1195-1196), explicitly "kept so the failure is diagnosable" — but this sensor's
extra_state_attributes (sensors.py:379-385) exposes only baseline_min_per_pct,
baseline_session_count and baseline_anchored_at. Neither rejected field is surfaced on any
entity for the CC regime.

**MISLEADS.** The docstring makes the None self-explanatory ("still waiting for the baseline"),
so nobody looks further. For the CC instance there is nowhere further to look anyway — the
rejected value that manager.py deliberately preserved for diagnosability reaches no entity — so
the docstring's confident account of the None is the only account a user gets, and it is the
wrong one.

### B18 · MEDIUM · stale-reference — `battery/sensors.py::BatteryHealthSensor`

**SAYS.** A raw reading above 100 (the cell charging faster than its install baseline, common
while the baseline is young) is clamped for this headline; the uncapped value stays on the
_cv_charge_speed diagnostic sensor and in the ``uncapped_pct`` attribute here.

**DOES.** There is no diagnostic sensor. `grep -rn "entity_category|EntityCategory"
custom_components/eufy_vacuum/battery/` returns nothing — neither RegimeChargeSpeedSensor nor
any other class in the battery package sets `_attr_entity_category`, so `_cv_charge_speed`
registers as an ordinary sensor alongside the headline, not under the device page's Diagnostic
section. The clamping claim itself is correct (`min(float(value), 100.0)`, sensors.py:312) and
`uncapped_pct` does carry the raw value (line 323).

**MISLEADS.** A user told to find the uncapped value on "the _cv_charge_speed diagnostic sensor"
looks in the Diagnostic section of the device page, finds nothing there, and concludes the
entity was not created. Separately, anyone acting on the docstring by adding
`_attr_entity_category = EntityCategory.DIAGNOSTIC` to make the code match would silently move a
live entity out of the default dashboard and out of recorder defaults for existing installs.

### B19 · MEDIUM · over-scoped — `battery/sensors.py::LastChargeDurationSensor`

**SAYS.** """Minutes the most recent completed charge session took.""" (and in the module
docstring: "- {object_id}_last_charge_duration — minutes for the last completed session")

**DOES.** The sensor reads `stats["last_charge_duration_min"]`, which manager.py:1020-1022
writes under a gate: `if delta_pct > 0 and duration_min > 0:`. A completed session with zero or
negative net delta — the common case of a vacuum already at 100% sitting on the dock and cycling
charging on/off — closes normally, gets a sessions.csv row and a session_history_recent entry,
but never updates these stats. The sensor keeps displaying the duration of an older session
while newer sessions have completed since.

**MISLEADS.** A user comparing this sensor against sessions.csv sees the CSV's newest row
disagree with "the most recent completed charge session" and reports a persistence or ordering
bug. The correct statement is "the most recent completed charge session that gained battery" —
and the paired `last_charge_delta_pct` attribute is stale in lockstep, so the two agreeing with
each other gives false reassurance that they are current.

### B20 · MEDIUM · over-scoped — `battery/job_metrics.py::module docstring (WEIGHTING)`

**SAYS.** Per-room m² is not reported by the device. We prorate the total m² across rooms by
``estimated_minutes`` (from the learning enrichment). When estimates aren't available we fall
back to equal-weight per room. Either way the per-bucket area shares sum to the job total.

**DOES.** _prorate_weights (job_metrics.py:155-168) falls back to equal weight only when the
TOTAL across all rooms is zero (`if total_est > 0: return [e / total_est ...]`). Partial
availability takes the estimates branch: any room whose `estimated_minutes` is missing, zero or
unparseable gets `est = 0.0` and therefore weight 0.0, is credited 0 m² and 0.0 share, and
`weighted_by` is still reported as `"estimated_minutes"`. A ten-room job where the learning
store enriched one room produces one room holding 100% of the area and nine holding none. The
final sentence remains true (weights still sum to 1.0), which is what makes the paragraph read
as complete.

**MISLEADS.** A reader seeing `weighted_by: "estimated_minutes"` on a job takes it, per this
docstring, as "every room was weighted by its own estimate" and trusts the resulting per-bucket
area shares. In a partially-enriched job those shares are concentrated on the enriched rooms and
the unenriched rooms' buckets report `rooms: N, share: 0.0` with no `area_m2` key at all (line
209 only writes area when the weight-product is truthy). Nothing in the label distinguishes a
fully-estimated job from a one-room-estimated one.

### B21 · MEDIUM · reason-obsolete — `battery/sensors.py::_bucket_means`

**SAYS.** Emits ``samples`` beside ``mean``: the number of jobs the mean was actually computed
over. ``count`` stays, because it is a true and separate fact about the bucket — but it is no
longer the only number next to a mean it does not describe.

**DOES.** The `samples` key this function emits has no consumer.
src/renderers/metrics.js:945-958 renders each bucket row's Jobs column from `obj[k]?.count`, and
the All-jobs row (lines 961-962, 978-980) from `all_jobs_count`; `samples` appears nowhere in
metrics.js, eufy-vacuum-command-center.js or eufy-vacuum-map.js. On the rendered card, `count`
is still the only number beside every mean — including the very table the _MEAN_SAMPLE_FIELD
comment cites as the symptom ("the card showed 3.333 %/m2 — Jobs: 10").

**MISLEADS.** Read narrowly, the sentence is about the attribute dict and is true for the by_*
buckets. But it is written in the past tense of a repair ("no longer") directly beneath a
comment whose evidence is a card screenshot, so it reads as "the card no longer misleads". It
does. Anyone verifying the C17 fix by looking at the card would see the original symptom and be
unable to tell whether the fix landed. Flagging as medium confidence because the sentence's
subject is arguably the attribute payload, not the render.

### B22 · MEDIUM · over-scoped — `battery/store.py::module docstring`

**SAYS.** - ``sessions.csv`` — every completed charge session as a CSV row. Reviewable in any
spreadsheet for trend charting. ... The files are the long-term raw audit trail.

**DOES.** _SESSION_HEADER (store.py:44-56) carries 11 of the 18 keys the session summary
actually holds. Omitted are `kind` (idle / mid_job / post_job — the field that gates mid-job
recharge stats at manager.py:1029) and all six regime fields: cc_duration_min, cc_delta_pct,
cv_duration_min, cv_delta_pct, cc_min_per_pct, cv_min_per_pct (manager.py:995-1010).
`cc_min_per_pct` / `cv_min_per_pct` are the sole inputs to the health baseline and to every
charge-speed sensor. Their only durable home is the .storage record, where
session_history_recent is a 50-item ring (HISTORY_LIMIT) and health_qualifying_sessions is
capped at 500.

**MISLEADS.** "Long-term raw audit trail" tells a reader that if a health figure looks wrong
they can go back to sessions.csv and re-derive it. They cannot: the numerator and denominator of
every health computation are absent from the CSV, and once a session rotates out of both in-
storage rings the values are gone. The claim is true of the session-level trend data it names
(durations, deltas, rates) and false of the regime data the health sensors are built on.

### B23 · LOW · over-scoped — `battery/manager.py::module docstring 'Charge sessions' (L34-35) and _update_session comment (L887)`

**SAYS.** module: "A session opens on the first sample where ``charging=True`` after a non-
charging sample" · _update_session: "# Force-close stale sessions"

**DOES.** Two mismatches. (a) L907 is `if charging and (not prev_charging or
session_was_discarded)` — DR-BAT-3 adds a second opening path where charging was ALREADY true
and the previous session was just discarded as stale; the docstring's single condition would say
the branch cannot fire there. (b) 'Force-close' names an operation the block does not perform —
it discards without summarizing (see the separate finding on the timeout).

**MISLEADS.** A reader tracing why a session appears with prev_charging already True concludes
the record is corrupt. And 'force-close' primes the reader to expect _close_session semantics —
the very confusion that makes the timeout-discard finding above possible.

### B24 · LOW · over-scoped — `battery/manager.py::module docstring 'Charge sessions' (L45)`

**SAYS.** "- contribute to the baseline + current health windows" (as one of three things that
happen to every closed session)

**DOES.** Only sessions passing _session_cc_qualifies or _session_cv_qualifies are promoted into
`health_qualifying_sessions` (L1152-1154), and the baseline anchor needs the stricter both-
windows-plus-both-regimes test (L1169-1175). The other two bullets in the same list
(sessions.csv, the HISTORY_LIMIT ring) genuinely do apply to every closed session, so the third
reads as universal by company.

**MISLEADS.** A reader expects a closed 60→100 charge to move health_pct. It cannot — it never
crosses the 50→80 CC window and may carry no cv attribution either. The health proxy looks
broken when it is behaving as designed.

### B25 · LOW · over-scoped — `battery/manager.py::rebaseline (docstring, L1292-1297)`

**SAYS.** "Does not touch cycles, aggregates, session history, mid-job stats, or job metrics —
only the health proxy's anchor point (and, per RP-045, the separately-retained qualifying-
session set it's compared against — see below). The next qualifying recharge (start <=
HEALTH_QUALIFY_START_MAX, end >= HEALTH_QUALIFY_END_MIN) will seed a fresh baseline."

**DOES.** Two gaps. (a) The reset leaves `stats["cc_charge_speed_rejected_pct"]` and
`stats["cv_charge_speed_rejected_pct"]` (written at L1194-1195) — and
`stats["rejected_rate_per_min"]` (L721) — populated with pre-swap figures, so a 'cleared' record
still carries a rejected health number from the old cell. (b) The re-anchor is NOT just
start<=50/end>=90: L1173-1174 additionally requires `cc_min_per_pct is not None and
cv_min_per_pct is not None`, so a qualifying-by-endpoints recharge assembled from samples the
MAX_DELTA_PCT / MAX_RATE_INTERVAL_SEC guards rejected will not re-anchor.

**MISLEADS.** After a battery swap a user reads a stale rejected figure attributed to the new
cell, and expects the first deep recharge to re-anchor when it may not. _update_health's own
docstring (L1136-1138) states the stricter anchor rule correctly — rebaseline's is the copy that
drifted, and it is the one the service points at.

### B26 · LOW · over-scoped — `battery/manager.py::_process_sample, MAX_PLAUSIBLE_RATE_PCT_PER_MIN warning (L714-720)`

**SAYS.** "battery: implausible charge rate %.4f %%/min (%.2f%% over %.0fs, zone=%s) — above
%.2f, discarding the sample rather than publishing it"

**DOES.** Only the RATE is discarded (`rate_per_min = None`, L722). The sample itself is still
fully processed: it reaches _update_session, which increments `session["samples"]`
unconditionally while charging (L943), so it enlarges the denominator of `avg = rate_sum /
samples` (L968-971) and DEFLATES the session's reported average rate; and it is still appended
to samples.jsonl with its delta_pct intact (L854-871).

**MISLEADS.** This is a user-visible log line. It says the observation was dropped whole; in
fact the artefactual sample still silently drags the closed session's avg_rate_per_min down —
which then feeds session summaries and, for mid_job sessions, the mid-job rolling mean. Someone
auditing why a session average looks low would rule this path out on the strength of the word
'discarding'.

### B27 · LOW · stale-reference — `battery/manager.py::BASELINE_SAMPLE_COUNT (L186-190)`

**SAYS.** "#: Qualifying sessions used to anchor the baseline. The baseline is #: per-install
... so the first valid session #: anchors it. CURRENT_WINDOW_DAYS smooths comparison-side
noise."

**DOES.** BASELINE_SAMPLE_COUNT has no reader anywhere in the tree (grep over src/,
custom_components/ and tests/ returns only this definition line). The anchor logic hardcodes the
count instead: `baseline["session_count"] = 1` at L1178, and the loop `break`s after the first
seed. Changing the constant changes nothing.

**MISLEADS.** The comment reads as documentation of a live tunable — 'Qualifying sessions used
to anchor the baseline' next to `= 1`. Someone wanting a 3-session anchor would set it to 3, see
no change, and have to discover by grep that the value is dead and the real decision is the
hardcoded 1 and the `break`.

### B28 · LOW · over-scoped — `battery/manager.py::_new_aggregate_bucket (L302-304)`

**SAYS.** "# Total drain over every job in the bucket. A real quantity, but NOT a ratio #
numerator — the two partnered sums below are. See C17."

**DOES.** L1515-1516 gates it: `if drain is not None: bucket["drain_pct_sum"] += float(drain)`.
Jobs that reported no battery_used_pct are in the bucket (they increment `count` unconditionally
at L1505) but contribute nothing here. The parallel comment at L1511-1512 gets it right — "A raw
total over every job that reported a drain" — so the two descriptions of the same field
disagree.

**MISLEADS.** 'over every job in the bucket' invites dividing drain_pct_sum by `count`, which is
the population mismatch the C17 repair was about. The field's other comment states the correct,
narrower population; this one is the copy that reads as complete.

### B29 · LOW · over-scoped — `battery/job_metrics.py::module docstring (PER-BUCKET DRAIN)`

**SAYS.** The cross-job aggregator (BatteryHealthManager) feeds per-bucket drain stats only from
jobs that were **single-bucket** for that key — i.e. every room used the same clean_mode (resp.
fan_speed, water_level). The ``is_single_*`` flags flip those gates.

**DOES.** There are two gates, not one. _apply_metrics_to_aggregates (manager.py:1356-1376)
computes `single_ok = not bool(metrics.get("mid_job_recharge"))` and requires `single_ok AND
metrics.get("is_single_X") AND metrics.get("single_X")` before folding into any per-bucket
aggregate. `mid_job_recharge` is not produced by this module at all — job_finalizer.py:1166
attaches it after compute_job_battery_metrics returns. So a genuinely single-mode job with
is_single_clean_mode True is silently excluded from by_clean_mode whenever the vacuum recharged
mid-run.

**MISLEADS.** "The is_single_* flags flip those gates" presents the flags as the switch. Someone
tracing why a single-mode job never reached by_clean_mode would check is_single_clean_mode, find
it True, and look for a bug in the aggregator. The exclusion is deliberate and is documented at
the manager end ("A mid-job recharge nets out of the raw start−end drain") but this docstring —
the one that owns the explanation of the gating — does not know about it.

### B30 · LOW · false — `battery/sensors.py::module docstring`

**SAYS.** All sensors pull from the same in-memory record; a single update listener fans out
state writes whenever the manager processes a new sample.

**DOES.** There is no single listener. Each of the 13 entities built by build_battery_sensors
calls `self._manager.add_update_listener(self._on_manager_update)` in its own
async_added_to_hass (sensors.py:137), appending to `BatteryHealthManager._update_listeners`
(manager.py:350-361); `_notify` iterates the whole list and every entity filters by
vacuum_entity_id itself (sensors.py:157-158). Nor is the trigger only "a new sample": `_notify`
is called from five sites in manager.py — 873 (_process_sample), 1329 (rebaseline), 1417
(rebuild_job_aggregates), 1479 (record_job_metrics) and 1602 — so job finalization and
rebaseline also drive state writes.

**MISLEADS.** Someone optimising the fan-out, or debugging a leaked listener after entity
removal, would look for one registration and find thirteen per vacuum. And someone diagnosing
why the job-metric sensors update outside charging would be told by this docstring that they
shouldn't.

### B31 · LOW · over-scoped — `battery/store.py::append_sample`

**SAYS.** """Append one sample as a JSONL line. Best-effort; logs and swallows errors."""

**DOES.** The handler is `except OSError` (store.py:84). Anything else propagates out of
append_sample. The call site is `hass.async_add_executor_job(partial(raw_store.append_sample,
...))` (manager.py:855-870) whose returned Future is deliberately not retained
("async_add_executor_job returns a Future that runs on the executor pool whether or not we hold
the reference"), so a non-OSError would surface as an unretrieved-exception traceback rather
than being logged and swallowed as promised. append_session (line 105) has the same narrow
handler but its docstring makes no swallow claim.

**MISLEADS.** "Swallows errors" is the contract a caller relies on when deciding this call needs
no guard of its own — which is exactly what the manager's fire-and-forget executor submission
does. In practice the reachable failure modes here are OSError, so the gap is narrow; flagging
at low severity because the promise is broader than the code and someone widening what goes into
`sample` (a value whose repr raises, a circular structure) would be relying on a guarantee that
isn't there.

### B32 · LOW · over-scoped — `battery/job_metrics.py::_bucketed_share`

**SAYS.** # ISSUE #48, and this one is already on disk. _bucket_key folds case and # nothing
else, so "Vacuum and mop" and "vacuum_mop" bucket separately

**DOES.** _bucket_key (job_metrics.py:234-238) does `str(value).strip().lower()` and
additionally maps both None and the empty string to the literal `"unknown"`. So it folds case,
strips surrounding whitespace, and normalises two distinct absence states into one bucket key.
The comment's point (it does not canonicalise spellings) is correct; the absolute "and nothing
else" is not.

**MISLEADS.** Minor, but it is an absolute in a comment that a reader will trust when reasoning
about what the helper is safe to feed. It matters most for the "unknown" fold: a job in which no
room reported a clean_mode produces `by_clean_mode == {"unknown": ...}`, len 1, so
is_single_clean_mode is True, single_clean_mode is the truthy string "unknown", and
manager.py:1360 folds it into a real by_clean_mode bucket named "unknown" — behaviour the
comment's "folds case and nothing else" gives no hint of.

### B33 · LOW · over-scoped — `battery/sensors.py::MidJobRechargeRateSensor`

**SAYS.** """Mean charge rate observed during mid-job recharges (the 15→75 window). The cleanest
health signal available: tight start/end zone, pure CC charging region, consistent thermal load.

**DOES.** No 15→75 window is enforced anywhere. A session is tagged mid_job purely by
_classify_session_kind (manager.py:1051-1053): `if self._has_active_job(vacuum_entity_id):
return "mid_job"`. _update_mid_job_rate_stat is then called on `kind == "mid_job" and avg is not
None and avg > 0 and delta_pct > 0` (manager.py:1029-1030) — any positive-delta charge that
happened while a job was in progress, at any start and end percentage. A user who docks a job-
paused vacuum at 60% and undocks at 64% contributes to the mean identically to a full 15→75
auto-resume cycle.

**MISLEADS.** UNSURE — 15→75 is plausibly the firmware's return-to-dock and resume thresholds,
in which case the docstring is describing device behaviour rather than claiming a code guard,
and manager.py:281 and 1027 make the same statement independently. Flagging at low confidence
because the parenthetical "(the 15→75 window)" and the guarantees drawn from it ("tight
start/end zone", "consistent thermal load") are what justify calling this "the cleanest health
signal available", and a manual mid-job dock satisfies none of them while still moving the mean.
If the 15→75 figure is a firmware observation rather than an invariant, saying so would cost one
clause and stop a reader treating the window as enforced.

### C56 — **OPEN (FRONTEND).** The `@media (hover: hover)` preview rule rests on a false premise

Found 2026-08-22 and verified directly. **Frontend — parked by Chris pending the frontend pass.**

`src/styles/theme-preview.js` lets preview specimens receive real hover states, and justifies it:

> `--evcc-border-strong` has SIX consumers and every one of them is a :hover rule
> (rooms.js:352, foundation.js:105, maintenance.js:316, map.js:1802, theme.js:339; the sixth,
> modals.js:382, reaches it only as a third-level fallback).

**Both halves are wrong.** A tree-wide walk finds **22 references**, not six. And the universal
fails: `src/styles/map.js:64` — `.evcc-rooms-view-toggle-btn.active` — consumes it in a RESTING
state, as does `src/styles/theme-preview.js:220` (`.evcc-theme-preview-border-sample--strong`).
`src/styles/metrics.js:192` uses it under `:focus`, not `:hover`. Consumers the list misses
entirely: `base-station.js:102`, `map.js:1118`, `map.js:1739`, `order.js:101`.

⚠ **The premise is what the rule rests on** — "a preview that renders the product truthfully
cannot show it standing still". The token DOES render standing still, so the argument for making
specimens hoverable is weaker than stated. The rule may still be right; the reason given is not.

**Four of the six cited line numbers have also rotted:**

    styles/theme.js:537   claims .evcc-theme-editor-scrollbox   -> a BLANK LINE (it is at 763)
    styles/theme.js:339   claims a :hover consumer              -> a closing brace (it is at 534)
    styles/mobile.js:831  claims a 44px touch-target floor      -> a comment about TABLES
    bindings/index.js:237 claims the open-order-selector bind   -> `});`  (it is at 239)

⚠ **Nothing verifies a line citation living in a source COMMENT.** `check_doc_citations.py` gates
`docs/` only. This is the unaudited-scope shape: zero findings, because nothing ever looked.

**Bare basenames make it worse and are their own hazard:** five files are named `theme.js`, six
`map.js`, five `rooms.js`. A comment citing `rooms.js:352` is under-specified before the line
number even rots — resolve sibling-first or you get the wrong file. I got this wrong on the first
attempt and only caught it with a control case.

## PROFILES COMMENT AUDIT — 2026-08-22. 37 findings (UNION OF FOUR PASSES). NOT APPLIED.

Severity {'high': 6, 'medium': 17, 'low': 14}. Kind {'reason-obsolete': 4, 'adopted-alternative': 1, 'false': 10, 'over-scoped': 14, 'stale-reference': 8}.

**THE FIRST PASS RUN AS A DELIBERATE EXPERIMENT.** Each cluster was audited TWICE with different
traversal orders — one walking files top-to-bottom for uniform coverage, one working outward from
the most-referenced symbols to reach load-bearing claims first. 46 raw findings, 37 distinct.

**The result changes the advice in `REPAIR-BACKLOG.md`, and it is the useful number:**

    severity   found   found by BOTH passes   rate
    high           6                      5    83%
    medium        17                      4    23%
    low           14                      0     0%

**A single pass is RELIABLE for HIGHs and samples the tail at random.** So the earlier worry —
that battery and rooms under-enumerate because they were single runs — is right about their TAILS
and wrong about their important findings. Do not re-run a pass hoping for a missed HIGH; re-run it
if you want the tail.

Within-cluster agreement, which is the honest comparison (the two clusters cover different files,
so a manager finding can never be reproduced by a room-profiles pass): manager 3 of 19 shared,
room_profiles 6 of 18. All four room_profiles HIGHs were found by both passes.

⚠ **One correction to the agents' framing.** Two HIGHs report the module banner's brand-neutrality
claim as FALSE because `registry._validate_room_profiles` never inspects `builtins`. Verified
directly: the validator fails three states — block absent, not a dict, or `{}` — and its own
docstring says outright "The gate is the block, not each key." The convention is real and stated;
the gap is that `room_profiles: {legacy_aliases: {}}` is non-empty, PASSES, and resolves nothing —
exactly the state the validator's rationale exists to catch. That is a partial guard, not a false
comment, and it should be filed as one.

⚠ **Not applied.** Re-verify before editing.

---

### P1 · HIGH · reason-obsolete · passes=2 — `profiles/manager.py:1184 (_enrich_saved_run_profile, has_stops)`

**SAYS.** # The step-type tuple MUST mirror the stepped-path gates at #
profiles/manager.py:1308, planning/run_plan.py:1348/1353 and # core/manager.py:1647 — "zone" was
added to those and missed here.

**DOES.** There is no step-type tuple at this site any more, and nothing is missing. The gate is
`plan_requires_stepped_execution(steps) or len(_room_group_steps) > 1`, and
step_types.STEPPED_STEP_TYPES is `frozenset({"charge_wait", "wait", "zone"})` — zone IS
included. step_types.py's own module docstring records the fix: "On 2026-07-30 the SAME missing
``\"zone\"`` was found and fixed twice in one day ...
``profiles.manager._enrich_saved_run_profile``'s ``has_stops`` gate (backend) and
``_deriveHasStops`` (card)." All three cited locations are also stale: profiles/manager.py:1308
is `"profile": self._enrich_saved_run_profile(...)` inside save_run_profile's return (the real
sibling gate is :1904); planning/run_plan.py:1348/1353 is blocked-room access-dependency logic
(`blocked_by_room_id = next(...)`) — the tuple there is at :1535/:1540; core/manager.py:1647 is
adapter `_entity_candidates` assembly (the real gate is :2584).

**MISLEADS.** It reads as an open bug report at the defect site. A maintainer either (a) "fixes"
has_stops by re-introducing a local `("charge_wait", "wait", "zone")` tuple beside the helper
call — re-creating precisely the hand-copied drift step_types.py was built to remove and which
its docstring forbids ("a caller that reaches for the set is one ``and`` clause away from re-
creating the drift this module removes") — or (b) follows three file:line pointers into
unrelated code and concludes the gates have been deleted.

### P2 · HIGH · reason-obsolete · passes=1 — `profiles/manager.py:1886 (start_run_profile)`

**SAYS.** # Stash the profile's step sequence so the plan builder materializes a multi-phase job
# (e.g. [clean, charge_wait, clean] or [clean, zone]). Consumed (popped) in #
run_plan._build_effective_start_plan; absent -> normal atomic dispatch. The gate MUST # mirror
run_plan's stepped-path gate (charge_wait/wait/zone) — a zone is a real clean # step, so a
rooms->zone profile fired here (the automation entry point) has to stash or # apply_run_profile,
which never writes queue_breaks, would drop the zone to a flat clean.

**DOES.** apply_run_profile writes queue_breaks unconditionally on every successful apply. At
profiles/manager.py:1794 it calls `self._manager.set_queue_breaks(vacuum_entity_id=...,
map_id=..., breaks=_derived_breaks)`, and core/manager.py:2756 assigns
`map_bucket["queue_breaks"] = out`. The `_derived_breaks` list is built at :1782 from every non-
room_group step, zone included. The RP-021c comment 140 lines earlier in the same method
(:1742-1760) is the landed fix and says so explicitly: "Derive the breaks from the profile's own
steps and write them through set_queue_breaks, the single replace-ALL primitive."
start_run_profile only reaches this comment after `applied.get("applied")` is truthy, i.e. after
that write has already happened.

**MISLEADS.** A maintainer reads this as the current division of labour — apply_run_profile
touches only room selection, the stash is the sole carrier of structure — which is exactly the
pre-RP-021c world. Acting on it means either adding a redundant second queue_breaks write, or
(worse) judging the RP-021c set_queue_breaks call at :1794 as unnecessary duplication and
deleting it, which restores the original defect: a plain Start from a reloaded dashboard or a
second tab runs the profile FLAT with no charge stop. The claim is also the stated JUSTIFICATION
for including "zone" in the stash gate, so disproving it invites removing zone from the gate
too.

### P3 · HIGH · false · passes=2 — `profiles/room_profiles.py:84-89 (module banner above PROTECTED_ROOM_PROFILE_NAMES)`

**SAYS.** There is NO framework default catalog and no fallback. An adapter declares its own
profiles, or declares the contract supported with none (``builtins: {}``). A MISSING key is
neither — it is an incomplete declaration, and ``registry._validate_adapter`` reports it. Absent
must not quietly mean empty, or "this brand has no profiles" becomes indistinguishable from "the
porter forgot", which is the fail-soft ambiguity this change exists to remove.

**DOES.** registry._validate_adapter does NOT report a missing ``builtins`` key. Its room-
profile gate is _validate_room_profiles, which fails only three states: `room_profiles` absent
from the config, not a dict, or an empty dict. Its own docstring states the opposite of this
comment: "The gate is the block, not each key. ... An adapter that declares SOME keys has
engaged with the contract, and its undeclared keys resolve empty". The only per-key check in
_validate_adapter (registry.py:475-485) is a type check — `room_profiles.{key} must be a dict if
present` — which an absent key skips entirely. tests/adapters/test_declaration_contract.py::test
_a_partially_declared_adapter_registers_and_resolves_empty pins that a partial block registers
with no room_profiles issue.

**MISLEADS.** A porter ships `room_profiles: {"legacy_aliases": {}, "normalize_defaults":
{...}}` with no `builtins`, believing registration will flag the incomplete declaration. It
registers clean. resolve_profile_catalog then yields `builtins: {}`, and the failure surfaces
hours later as UndeclaredProfileCatalogError on the first room resolution — precisely the "loud
but hours later and far from the cause" outcome DC-2c says the registration gate exists to
prevent. A maintainer trusting this line would also see no reason to add the per-key check that
would actually deliver it.

### P4 · HIGH · false · passes=2 — `profiles/room_profiles.py:224-227 (resolve_profile_catalog docstring)`

**SAYS.** Absent and declared-empty resolve the SAME WAY here, and that is deliberate — this
function's job is resolution, not judgement. The two states are distinguished where the
distinction is actionable: ``registry._validate_adapter`` reports a missing ``builtins`` as an
incomplete declaration, and the brand-agnostic contract suite makes it a hard failure.

**DOES.** Second occurrence of the same false claim, here naming `builtins` explicitly and using
it as the justification for collapsing absent and declared-empty. registry._validate_adapter
never inspects whether `builtins` is present — see _validate_room_profiles
(registry.py:313-350), which gates on the block only, and the key loop at registry.py:475-485,
which type-checks `builtins` solely `if present`. The contract-suite half is only partly true:
DC-2c tests an adapter with no `room_profiles` block at all, and
test_adapter_contract.py:448-452 asserts non-empty builtins for already-registered brands; no
test makes a block that omits `builtins` a failure.

**MISLEADS.** This is the load-bearing rationale for why it is safe for resolve_profile_catalog
to treat absent and `{}` identically. A reader auditing the absent-vs-empty design concludes the
distinction is caught upstream and stops looking; it is not caught anywhere, so the fail-soft
ambiguity the surrounding prose says was removed is still open for the `builtins` key
specifically.

### P5 · HIGH · stale-reference · passes=2 — `profiles/room_profiles.py:586-588 (resolve_room_profile_for_room docstring)`

**SAYS.** ``catalog`` (a resolved adapter ``room_profiles`` block) sources the built-ins, legacy
aliases, and floor-type fan/water defaults; None uses the in-code constants (byte-identical).

**DOES.** There are no in-code constants left to use. catalog=None flows to get_room_profile →
get_default_room_profiles(None) → `{}`; merge_profile_dicts yields `{}`; both `merged.get(...)`
lookups miss and the function RAISES UndeclaredProfileCatalogError ("core holds no catalog").
The module banner at lines 84-85 states "There is NO framework default catalog and no fallback",
and tests/adapters/test_declaration_contract.py::test_an_undeclared_catalog_fails_loudly_not_sil
ently pins the raise for exactly this call with `catalog=resolve_profile_catalog(None)`.

**MISLEADS.** A caller reads "None uses the in-code constants (byte-identical)" and treats
catalog as an optional convenience — the signature's `catalog: ... | None = None` default
reinforces it. Any such call raises at resolution time instead of falling back. The claim
survived the removal of the in-code Eufy catalog it describes.

### P6 · HIGH · stale-reference · passes=2 — `profiles/room_profiles.py:808-812 (apply_room_profile_to_config docstring)`

**SAYS.** ``catalog`` (the adapter's resolved room-profile catalog) supplies the
``normalize_defaults`` for any field the profile omits, so a non-Eufy brand's rooms fill from
ITS defaults rather than the in-code Eufy ones (fan ``"Max"`` / water ``"Off"`` / intensity
``"Standard"``). Absent catalog → the in-code Eufy defaults (byte-identical to the pre-catalog
behaviour for Eufy).

**DOES.** With no catalog the function does not produce Eufy defaults — it produces empty
strings. normalize_room_profile(profile, catalog=None) sets `brand_defaults = {}`, so fan_speed,
water_level, clean_intensity and path_type each fall back to "" (lines 297-309). The three named
in-code literals no longer exist in this module at all; they live in
adapters/eufy/room_profiles.py::DEFAULT_CUSTOM_ROOM_PROFILE, which the Eufy adapter declares as
`normalize_defaults` (adapter.py:945) — and its intensity value is "Quick", not "Standard".

**MISLEADS.** A caller invoking this without a catalog expects Eufy-shaped rooms and instead
writes empty vocabulary into every omitted axis — the same shape as the shipped Roborock "no
suction applied at all" incident this module's rework exists to prevent. The parenthetical also
hands a reader three literals to grep for that were deliberately deleted from core.

### P7 · MEDIUM · adopted-alternative · passes=1 — `profiles/manager.py:439-440 (get_effective_room_details, mop_required)`

**SAYS.** # If that tolerance is ever wanted back it belongs in # is_mop_clean_mode, once, not
in a fourth private copy.

**DOES.** profiles/room_profiles.py already ships that tolerance as its own owner:
`may_wet_floor` (:546) is documented as "THE SECOND QUESTION", is "DELIBERATELY LOOSER THAN
is_mop_clean_mode, and must stay so", returns True for a mode that "merely MENTIONS mopping",
and states "``wash`` counts". `is_mop_clean_mode` (:531) carries the opposite instruction: "For
the other question — 'might this put water on the floor' — use ``may_wet_floor`` below. They are
not the same question and must not be collapsed into one."

**MISLEADS.** Someone acting on this comment would widen `is_mop_clean_mode` to tolerate
substring/wash modes — the exact collapse the canonical owner forbids — loosening a STRICT
predicate that gates dispatch payloads and the carpet mop-downgrade, while the tolerant sibling
that already answers this question (`may_wet_floor`) goes unnoticed and unused.

### P8 · MEDIUM · false · passes=1 — `profiles/manager.py:112 and :117 (_generate_room_profile_id / _generate_run_profile_id)`

**SAYS.** """Generate a stable unique key for a new custom room profile.""" / """Generate a
stable unique key for a new saved run profile."""

**DOES.** Returns `f"user_{datetime.now().strftime('%Y%m%dT%H%M%S')}"` / `f"rp_{...}"` — a
local-time, one-second-resolution string with no collision check, and neither caller checks for
an existing key: save_user_room_profile assigns
`self._data["profiles"]["room_profiles"][target_profile_name] = profile` (:503) and
save_run_profile assigns `library[profile_id] = {...}` (:1298). Two saves in the same second
silently overwrite the first. The file's own header records exactly this as A3-PP-CRUD-8 and
A4-PP-RP-5 (:43-46), neither marked closed.

**MISLEADS.** A caller reading "unique key" trusts these as identity generators and skips an
exists check — which is precisely why both save paths have none. The header of this same file
documents the resulting silent data loss, so the docstring contradicts the file's own finding
list.

### P9 · MEDIUM · false · passes=2 — `profiles/manager.py:1339-1342 (set_run_profile_steps docstring)`

**SAYS.** """Replace one saved profile's ordered steps (room_group | charge_wait). The steps
list holds the sequence — room groups and the charge boundaries between them. Requires at least
one room_group (a run must clean something). """

**DOES.** The method accepts four step types, not two: _normalize_steps_reporting handles
"room_group", "charge_wait", "wait" and "zone", and this same method carries zone-specific
write-path logic 25 lines below (the C40 leading-zone refusal at :1361-1380). The shipped card
sends wait steps through this service (src/state/steps-order.js::insertWaitStep, persisted via
setRunProfileSteps in src/bindings/run-profiles.js).

**MISLEADS.** The parenthetical reads as the accepted closed set for the `steps` parameter. A
caller (or a YAML author reading the generated service docs) would believe wait and zone steps
are not accepted here, and a maintainer could "tidy" the normalizer to match the docstring —
which would drop every wait/zone step the card already saves through this path.

### P10 · MEDIUM · over-scoped · passes=2 — `profiles/manager.py:1764 (apply_run_profile, break derivation)`

**SAYS.** # set_queue_breaks clamps # to an interior slot and drops breaks entirely below two
rooms, which is # also where a leading/trailing break resolves -- unsupported per RP-021a #
(Q17), and handled there consistently rather than by a second rule here.

**DOES.** set_queue_breaks does NOT clamp a zone to an interior slot — a zone is allowed to
TRAIL. core/manager.py:2751 reads `max_after = room_count if btype == "zone" else room_count -
1`, with the inline comment "A zone may trail (after_index == room_count); a charge/wait is
capped to an interior slot (void at the tail). Neither leads." The `_derived_breaks` list this
comment sits on appends zone steps too (:1783 `_derived_breaks.append({**_step, "after_index":
_rooms_emitted})` runs for every non-room_group step), so a rooms->zone profile hands
set_queue_breaks `after_index == room_count` and the trailing zone is KEPT, not resolved away as
unsupported. core/manager.py:2547 documents the same: "Trailing inserted steps (after_index ==
room count) — a zone cleaned AFTER the last room ... (Only zones can trail; charge/wait are
capped to an interior slot.)" Only the "drops breaks entirely below two rooms" half is
unconditionally true.

**MISLEADS.** The universal phrasing makes trailing steps look impossible after apply. A
maintainer either adds a redundant trailing-step drop "for consistency with RP-021a" here —
silently deleting the zone phase of every rooms->zone profile applied through this path, the
exact C40 failure the code below is trying to surface — or, debugging a trailing zone that did
survive, concludes set_queue_breaks is broken and tightens its zone clamp to room_count-1.

### P11 · MEDIUM · false · passes=1 — `profiles/manager.py:482 (save_user_room_profile)`

**SAYS.** # ISSUE #48, the fifth and last copy — and the worst-placed, because #
get_effective_room_details forty lines up produces the SAME mop_required # field through the
shared owner. Two producers of one field, disagreeing by # construction, in one file. They agree
on every value that exists today, # which is exactly how the original defect stayed invisible: a
substring test # and a canonical test give the same answer right up until a brand ships a # mode
that only one of them recognises.

**DOES.** The two producers are the identical expression, so they cannot disagree by
construction and neither is "a substring test" versus "a canonical test". Line 441
(get_effective_room_details): `"mop_required": is_mop_clean_mode(clean_mode) or "wash" in
clean_mode`. Line 490 (here): `_mop_required = is_mop_clean_mode(_clean_mode_l) or "wash" in
_clean_mode_l`. Both are canonical-owner-plus-"wash"-tolerance, character for character; the
only difference is the local variable name. The sibling comment at :434-440 confirms the intent
— "that narrowing was already the sibling's choice — inherited here rather than introduced,
because the two answering differently is worse than either answer."

**MISLEADS.** A maintainer takes the comment at face value, decides line 490 is the "substring
test" that must be aligned with the "canonical" one at :441, and rewrites :490 to bare
`is_mop_clean_mode(_clean_mode_l)`. That STRIPS the "wash" tolerance from one producer while
:441 keeps it — manufacturing the exact divergence the comment claims already exists. The
comment is an accusation against a currently-consistent pair.

### P12 · MEDIUM · over-scoped · passes=1 — `profiles/manager.py:198 (_catalog_for docstring)`

**SAYS.** Every resolution path goes through here. Core ships no catalog of its own, so a caller
that cannot name a vacuum cannot resolve a profile — which is the point: the four call sites
that used to omit this were silently resolving every brand's rooms against Eufy's vocabulary

**DOES.** Three resolution paths bypass this method. queue/queue_engine.py:254 re-implements it
verbatim for the dispatch path — `_catalog =
resolve_profile_catalog((get_adapter_config(vacuum_entity_id) or {}).get("room_profiles"))`,
threaded into per-room resolution and the capability gate. rooms/room_defaults.py:73 calls
`resolve_profile_catalog(catalog if isinstance(catalog, dict) else None)` directly. And in this
same class, get_room_profiles at :362 does `self._catalog_for(vacuum_entity_id) if
vacuum_entity_id else resolve_profile_catalog(None)` — resolving a catalog without passing
through _catalog_for.

**MISLEADS.** It presents this method as the single chokepoint for brand-catalog resolution.
Anyone adding a guard, a log, a cache or a brand-mismatch assertion here will believe it covers
every path and will not touch queue_engine.py:254 — which is the path that actually reaches the
wire. The dispatch-time resolution would keep whatever behaviour the chokepoint was added to
change, invisibly.

### P13 · MEDIUM · stale-reference · passes=1 — `profiles/manager.py:428 (get_effective_room_details)`

**SAYS.** # ISSUE #48: the LAST private copy of the predicate. [...] If that tolerance is ever
wanted back it belongs in # is_mop_clean_mode, once, not in a fourth private copy.

**DOES.** It is not the last, and a further private copy exists 49 lines below it in the same
file. The inline `is_mop_clean_mode(x) or "wash" in x` predicate appears at :148
(_protected_room_config), :441 (here) and :490 (save_user_room_profile). The copy at :490 is the
one that self-describes at :482 as "ISSUE #48, the fifth and last copy" — so the two comments
both claim to be last, and disagree on the count (three implied here by "a fourth private copy",
five there).

**MISLEADS.** Someone auditing or consolidating the #48 predicate reads "the LAST private copy",
stops searching at line 441, and never reaches the copy at :490 — leaving the one occurrence the
file itself calls "the worst-placed" in the tree. The contradictory counts also make either
comment unusable as a completeness check for the consolidation work.

### P14 · MEDIUM · over-scoped · passes=1 — `profiles/room_profiles.py:67 (EffectiveRoomSettings field annotation)`

**SAYS.** path_type: str # always present after Wave 2

**DOES.** path_type is not always present. The docstring 11 lines above, on the same TypedDict,
says the opposite verbatim: "``path_type`` is brand-conditional, NOT always present — it is
carried only by a brand that declares the axis, and ``apply_capability_gate`` drops the key
outright for a device without path control rather than clamping it to a value."
apply_capability_gate (lines 790-795) does exactly that: `if path_type: gated["path_type"] =
path_type else: gated.pop("path_type", None)`. queue_engine.py:322-324 guards accordingly: "#
.get, not [] — the gate omits this key entirely for a brand with no path axis, which is now the
normal case rather than an error."

**MISLEADS.** A caller reading the field list writes `settings["path_type"]` on a gated dict and
gets a KeyError on every Eufy device and on any Roborock model without path control — the normal
case, not the edge case. The neighbouring `# always present after Wave 2` also makes the correct
`.get` guard in queue_engine look like defensive redundancy someone could tidy away.

### P15 · MEDIUM · false · passes=2 — `profiles/room_profiles.py:582-583 (resolve_room_profile_for_room docstring)`

**SAYS.** Resolution order: selected profile → floor-type defaults → hard constraints (carpet
forces vacuum-only) → per-room overrides.

**DOES.** Per-room overrides are not last, and general floor-type defaults no longer exist. The
body reads room-explicit values first (lines 617-630, `room_config.get(k,
resolved_profile.get(k, ...))`), then the carpet clamp at lines 646-648 unconditionally
OVERWRITES resolved_fan_speed and resolved_water_level from the catalog tables — so a room-
explicit water level loses to carpet. The function's own anchor comment 13 lines below states
the real rule and contradicts the docstring: "settings resolve room-explicit > profile > ABSENT;
the carpet clamp is the only rule above that ladder". The "floor-type defaults" stage is also
carpet-only now: the per-surface hard-floor rows were retired 2026-08-17 (lines 640-645; both
brands' FLOOR_TYPE_WATER_DEFAULTS carry carpet rows only).

**MISLEADS.** A reader tracing why a user's explicit water level did not reach a carpeted room
follows a stated order in which per-room overrides win last and concludes the clamp is a bug —
or, restoring "floor-type defaults" as a general stage, re-adds the per-surface water table that
was deliberately retired.

### P16 · MEDIUM · over-scoped · passes=1 — `profiles/room_profiles.py:407 (get_available_profile_names docstring)`

**SAYS.** Mop profiles are excluded entirely when the vacuum does not support mopping.

**DOES.** Mop profiles require BOTH flags: `if supports_mop and supports_water: return [4
names]` else return the two vacuum-only names. A device with supports_mop_features=True and
supports_water_control=False also loses vacuum_mop_quick / vacuum_mop_deep, which the docstring
never says. That combination ships: adapters/roborock/adapter.py:798-799 sets
supports_mop_features from `profile["has_mop"]` while supports_water_control comes from
`mop_settable`, and core/capabilities.py:996-1011 lets the declared False win ("the Roborock S6
declares supports_water_control False because its mop/water is unsettable").

**MISLEADS.** Someone debugging why a mop-capable Roborock S6 shows only two profiles in the
picker reads a single stated condition, confirms supports_mop_features is True, and looks for
the bug elsewhere — or "fixes" the code to match the docstring by dropping the supports_water
conjunct, restoring mop profiles on hardware that rejects every mop command.

### P17 · MEDIUM · over-scoped · passes=1 — `profiles/room_profiles.py:732-733 (inline comment on the mop-downgrade block in apply_capability_gate)`

**SAYS.** A brand that declares only one of the two axes carries only that one through the
downgrade; the other stays "" and is dropped below.

**DOES.** Only path_type is dropped. clean_intensity is written into the output unconditionally
by the gated.update at lines 779-789, empty or not; the drop logic at lines 792-795 covers
path_type alone. So on Roborock — which declares path_type and omits clean_intensity from every
profile — the downgraded payload dict carries `"clean_intensity": ""` rather than omitting the
key, exactly the state the comment says is dropped.

**MISLEADS.** A reader takes "absent stays distinguishable from declared-empty downstream" (the
stated purpose at lines 790-791) to hold for both brand-conditional axes. It holds for one.
Anything downstream that distinguishes an absent key from an empty value — the same distinction
_finalize_room_update and vocabulary_migration are built around — sees clean_intensity as
declared-empty on a brand that has no intensity axis at all.

### P18 · MEDIUM · stale-reference · passes=2 — `profiles/__init__.py:7-9 (module docstring)`

**SAYS.** The existing room_profiles.py module (built-in presets, normalize helpers, resolve
logic) is unchanged and continues to be importable directly via profiles.room_profiles.

**DOES.** room_profiles.py contains no built-in presets and has been substantially changed. Its
own banner reads "There is NO framework default catalog and no fallback";
get_default_room_profiles returns `deepcopy(cat.get("builtins") or {})` with the docstring
"There are no in-code built-ins to fall back to". The presets moved to
adapters/eufy/room_profiles.py on 2026-08-07 ("Moved out of ``profiles/room_profiles.py``").
Only the last clause — importable via profiles.room_profiles — still holds.

**MISLEADS.** This is the package's front door. A reader looking for the built-in profile
catalog is sent to room_profiles.py and finds none, and the word "unchanged" positively
discourages checking whether the module still works the way this paragraph describes — which is
the whole point of the core-owns-keys-not-words split.

### P19 · MEDIUM · false · passes=1 — `profiles/room_profiles.py:179-183 — no_water_value docstring`

**SAYS.** ``resolve_room_profile_for_room`` already reads it this way; ``apply_capability_gate``
did not, and assigned the literal ``"Off"`` at three sites. Roborock's value is ``"off"``, which
is not in its declared ``water_level_options``, so dispatch filtered the setting out and mop
intensity was never applied on a mop-settable model.

**DOES.** Roborock's `WATER_LEVEL_OPTIONS` (adapters/roborock/vocabulary.py:72-77) is `off / low
/ medium / high`, and adapters/roborock/adapter.py:371 declares it under `water_level_options`
on exactly the mop-settable models this sentence names. So `"off"` IS in Roborock's declared
options. The value that was not declared — and that dispatch's `options_key` filter dropped — is
the Eufy literal `"Off"` that `apply_capability_gate` used to assign, named earlier in the same
paragraph.

**MISLEADS.** It reads as "this brand's own no-water word is invalid against this brand's own
option list", which inverts the lesson. The plausible "fix" is to change the carpet entry in
`FLOOR_TYPE_WATER_DEFAULTS` or add a value to `WATER_LEVEL_OPTIONS` — either of which breaks the
carpet-water-off guarantee this very helper exists to source. The distinction that actually
matters (case: "Off" vs "off") is destroyed by the sentence.

### P20 · MEDIUM · stale-reference · passes=1 — `profiles/room_profiles.py:53-55 vs 67 — EffectiveRoomSettings`

**SAYS.** Docstring: "``path_type`` is brand-conditional, NOT always present — it is carried
only by a brand that declares the axis, and ``apply_capability_gate`` drops the key outright for
a device without path control rather than clamping it to a value." Field annotation 14 lines
below: "path_type: str # always present after Wave 2"

**DOES.** The two statements about one field are direct opposites, and neither is right for both
producers. `resolve_room_profile_for_room` ALWAYS emits the key — line 693 writes `"path_type":
resolved_path_type` unconditionally, with `""` when nobody declared the axis — and this
TypedDict is documented as "Output shape of resolve_room_profile_for_room()".
`apply_capability_gate` is the one that conditionally removes it (`if path_type:
gated["path_type"] = path_type else: gated.pop("path_type", None)`, lines 791-794).

**MISLEADS.** queue_engine.py:325 reads `gated.get("path_type", "")` specifically because the
key can be absent post-gate; a reader who takes the "# always present after Wave 2" annotation
at face value writes `settings["path_type"]` against a gated payload and gets a KeyError on
every Eufy device. Conversely a reader taking the docstring at face value adds a needless
presence check to resolver output. One of the two will get "fixed" on the strength of the other.

### P21 · MEDIUM · over-scoped · passes=1 — `profiles/room_profiles.py:405-407 — get_available_profile_names docstring`

**SAYS.** Return the list of profile names allowed for the given vacuum capabilities. Mop
profiles are excluded entirely when the vacuum does not support mopping.

**DOES.** The gate is a conjunction, not the single condition stated: `if supports_mop and
supports_water: return [4 names]` else the 2 vacuum-only names. Mop profiles are therefore also
excluded from a vacuum that DOES support mopping whenever `supports_water_control` is False —
which is a shipped configuration, not a hypothetical: the Roborock S6 declares `has_mop: True`
(model_catalog.py:39) so `supports_mop_features` is True, while adapter.py:799 sets
`supports_water_control: mop_settable` = False, and core/capabilities.py:1011 lets that explicit
hint win.

**MISLEADS.** On Chris's own S6 the profile sensor reports 2 profiles for a vacuum that has a
mop, and this docstring says that cannot happen. Anyone debugging "why did the mop profiles
disappear on a mop-equipped robot" is sent away from the actual predicate; anyone changing the
condition will believe they are preserving documented behaviour when they are not.

### P22 · MEDIUM · over-scoped · passes=1 — `profiles/room_profiles.py:433 — get_available_profiles docstring`

**SAYS.** Return normalized profiles filtered to those allowed by the vacuum's capabilities.

**DOES.** Two filters are applied, only one of which is capabilities. `allowed_names` comes from
`get_available_profile_names`, a hardcoded whitelist of the four framework built-in keys, and
the comprehension keeps only `if name in allowed_names`. Every stored custom profile merged in
by `merge_profile_dicts` — saved under an arbitrary name, defaulting to `"user_1"`
(profiles/manager.py:455) — is dropped regardless of capabilities, and so is any brand builtin
declared under a different key. The sole caller, sensor/profile.py:67, then publishes that count
as `profile_count` and the set as `profiles`.

**MISLEADS.** The diagnostic sensor's `capability_filtered: True` plus this docstring assert
that everything missing was removed by a capability. A user who saved three custom room profiles
sees none of them in the sensor and no stated reason; a maintainer reading this docstring has no
cue that the function silently discards user data, and would "fix" the sensor rather than the
whitelist.

### P23 · MEDIUM · over-scoped · passes=1 — `profiles/room_profiles.py:455-460 — resolve_profile_name_for_constraints docstring`

**SAYS.** Resolve the final profile name after applying hard constraints. Rule: - carpet floor
forces vacuum-only behavior - vacuum_mop_quick -> vacuum_quick - vacuum_mop_deep -> vacuum_deep

**DOES.** The function remaps three hardcoded names, not a category: the two listed plus an
undocumented `if normalized_name == "vacuum_mop_standard": return "vacuum_quick"` (line 472-473,
reachable for any brand whose `legacy_aliases` does not map it — Roborock declares
`legacy_aliases: {}`). Every other name returns unchanged, including a user-saved custom profile
whose clean_mode is `vacuum_mop`, and including any brand builtin declared under a different
key. The function also never touches clean_mode at all — it returns a NAME — so "forces vacuum-
only behavior" is not something this function can do for anything outside those three literals.

**MISLEADS.** Universal phrasing over a three-literal whitelist. A caller that relies on "carpet
forces vacuum-only" and skips its own mop check will dispatch a mop clean_mode on carpet for any
custom or brand-specific profile — the carpet water clamp in the caller still holds, but the
mode does not. The undocumented third mapping also means a reader enumerating the rules from
this docstring will miss a live branch.

### P24 · LOW · false · passes=1 — `profiles/manager.py:428-429 (get_effective_room_details, mop_required)`

**SAYS.** # ISSUE #48: the LAST private copy of the predicate. Expressed exactly as #
_protected_room_config expresses it — same file, same question

**DOES.** Two more byte-identical private copies of the same predicate live in this file —
`is_mop_mode = is_mop_clean_mode(clean_mode) or "wash" in clean_mode` at :148, and
`_mop_required = is_mop_clean_mode(_clean_mode_l) or "wash" in _clean_mode_l` at :490, whose own
comment calls itself "ISSUE #48, the fifth and last copy" (:483). Two comments in one file each
claim to sit on the last copy, and the one claiming "LAST" is followed by another 50 lines
later.

**MISLEADS.** A maintainer auditing ISSUE #48 stops at this site believing the sweep is
complete, and misses the copy at :490 (and the one at :148). The two comments also disagree
about the same line: :483 describes :441 as produced "through the shared owner", while :428
calls it a private copy.

### P25 · LOW · over-scoped · passes=1 — `profiles/manager.py:1095-1097 (_reject_unbracketed_break)`

**SAYS.** # single-entry list (every ``queue_breaks`` call site normalizes one already- #
positioned break in isolation) is never "leading" or "trailing" in this sense,

**DOES.** Not every queue_breaks call site does. core/manager.get_queue_steps normalizes the
WHOLE derived multi-step queue through this same function (`steps =
self.profiles.normalize_run_profile_steps(steps)` at core/manager.py:2555, retried at :2573) and
wraps it in `except ServiceValidationError` to strip a stranded leading/trailing break — proof
that this path routinely normalizes a real sequence, not one break in isolation. Only
_map_queue_breaks (:2464), add_queue_break (:2606) and set_queue_breaks (:2746) pass single-
entry lists.

**MISLEADS.** The parenthetical is the stated justification for the `len(out) > 1` guard. A
reader takes it to mean no queue_breaks path can ever trip the leading/trailing rejection, and
could drop get_queue_steps' self-heal except-block as dead code — the one place that recovers a
break stranded by a room being disabled after placement.

### P26 · LOW · stale-reference · passes=1 — `profiles/manager.py:1789-1791 (apply_run_profile, C40 dropped-leading-zone comment)`

**SAYS.** # this reports the ones already saved, which is the case the comment # at :1723 says
this method exists to serve: "an automation that calls # apply_run_profile then start_cleaning
... a zone step was never # cleaned at all".

**DOES.** Line 1723 is `"profile": profile,` inside the no_matching_rooms return dict; the
quoted passage is at :1747-1751. The same rot sits at :1364 — "only emits a break once at least
one room has gone out (:1758)" — where :1758 is mid-comment prose ("from an earlier composition.
That was the finding's other half --"); the code meant is `if _rooms_emitted >= 1:` at :1782.
Both pointers are ~25 lines short, consistent with an insertion above them.

**MISLEADS.** A reader following either in-file pointer lands on a dict literal or on unrelated
prose and concludes the cited rule was removed. Both quote enough text to be re-found by grep,
which is the only reason this is low rather than worse.

### P27 · LOW · over-scoped · passes=1 — `profiles/manager.py:1828-1831 (apply_run_profile return, unsnapshotted_room_ids)`

**SAYS.** # RP-021b / #8:A4-PP-RP-1: rooms the profile had no saved settings # snapshot for, so
they kept their CURRENT settings. Empty for any # profile saved since settings were snapshotted,
and for every # legacy rooms-only profile (whose group IS profile["rooms"]).

**DOES.** _unsnapshotted is populated by matching each STEP room_id against _saved_by_id, which
is built only from profile["rooms"] (:1633-1638). set_run_profile_steps replaces
`existing["steps"]` without touching `existing["rooms"]` (:1391), and step room ids are
validated for shape only — its own docstring says "existence + brand caps are enforced at
dispatch" (:993-995). So a profile saved yesterday whose steps were later edited (a shipped
service, SERVICE_SET_RUN_PROFILE_STEPS) to name a room absent from the snapshot reports that
room as unsnapshotted.

**MISLEADS.** "Empty for any profile saved since settings were snapshotted" invites treating a
non-empty list as proof of a legacy profile, so the real cause — steps and rooms desynced by a
steps-only write — gets misdiagnosed as "old profile, just re-save it", which does not fix the
desync.

### P28 · LOW · reason-obsolete · passes=1 — `profiles/manager.py:1361-1362 (set_run_profile_steps, C40 comment)`

**SAYS.** # C40: a profile whose FIRST step is a zone is saveable today and its # zone never
runs.

**DOES.** The guard this comment introduces sits 11 lines below and refuses exactly that: `if
len(normalized) > 1 and str(normalized[0].get("type") or "").strip().lower() == "zone": raise
ServiceValidationError(... translation_key="leading_zone_unsupported")` (:1373-1380); a lone
zone step is separately refused by the no_room_group check (:1388); and save_run_profile only
copies queue steps, whose breaks all carry after_index >= 1 (core/manager.py:2467), so no write
path admits a leading zone. The sibling comment at :1786-1787 states the current position
correctly: "The write path refuses new ones; this reports the ones already saved".

**MISLEADS.** Every other pre-fix narrative in this file is written in the past tense ("This
used to be a bare `steps: []`", "an unconditional write put path_type=...", "Was `clean_mode in
{...}`"), so present-tense "is saveable today" reads as live shipped behaviour. A reader would
file or chase a defect that the line below already closes, or add a duplicate guard on another
path.

### P29 · LOW · over-scoped · passes=1 — `profiles/manager.py:987 (normalize_run_profile_steps docstring)`

**SAYS.** Invalid/empty entries are dropped.

**DOES.** Not all of them are dropped — some RAISE. normalize_run_profile_steps returns
`ProfileManager._reject_unbracketed_break(out)`, which for any list of 2+ entries raises
`ServiceValidationError("A run profile cannot start with a charge/wait break")` or `"...cannot
end with a charge/wait break"` when the first/last normalized step is a charge_wait or wait
(:1098-1110). Its own comment states the intent: "it is unsupported, not silently droppable".
The docstring documents no exception at all, yet both in-tree multi-entry callers must catch it
— run_profile_steps at :1120 and core/manager.py:2554 (`try: steps =
self.profiles.normalize_run_profile_steps(steps) / except ServiceValidationError:`).
run_profile_steps' own recovery is not airtight either: its `_is_break` trim inspects RAW
entries, so a stored `[invalid_zone, charge_wait, room_group]` trims nothing, and the re-
normalize at :1143 — which sits inside the except block — raises uncaught.

**MISLEADS.** A new caller written against this docstring treats the function as total and wraps
nothing. On a stored profile with an edge break it raises out of a read path, and the failure
surfaces as "saved run profile will not load" rather than as a validation result.

### P30 · LOW · over-scoped · passes=1 — `profiles/manager.py:1094 (_reject_unbracketed_break)`

**SAYS.** # A # single-entry list (every ``queue_breaks`` call site normalizes one already- #
positioned break in isolation) is never "leading" or "trailing" in this sense, # so the check
only applies once there is a real sequence to be first/last in.

**DOES.** Not every queue_breaks call site passes a single entry. core/manager.py:2555, inside
get_queue_steps — the function that derives the queue FROM `map_bucket["queue_breaks"]` — passes
the whole assembled steps list, and has to catch the resulting raise: "except
ServiceValidationError: # after_index is clamped to an interior slot whenever a break is added,
so this should be unreachable — but a room disabled AFTER a break was placed can strand it at
the edge." Only core/manager.py:2464 (_map_queue_breaks), :2606 (add zone step) and :2746
(set_queue_breaks) are the single-entry form.

**MISLEADS.** "every queue_breaks call site" makes the raise look unreachable from the
queue_breaks store, so the self-heal try/except in get_queue_steps reads as dead defensive code
and gets deleted. It is not dead — disabling a room after a break was placed strands the break
at an edge, and the handler is what keeps the derived queue readable instead of throwing on
every fetch.

### P31 · LOW · false · passes=1 — `profiles/manager.py:14 (module docstring)`

**SAYS.** Receives a reference to the parent EufyVacuumManager so it can call
get_effective_room_details (from room profile save-from-room), _notify_run_profiles_updated,
_notify_rooms_updated, and _refresh_room_derived_state without re-implementing them.

**DOES.** get_effective_room_details is not reached through the parent — it is ProfileManager's
own method (defined at :376, and listed as owned by this class eight lines earlier in the same
docstring), and save_room_profile_from_room calls it at :593 as
`self.get_effective_room_details(...)`. The delegation runs the other way:
core/manager.py:1785-1787 defines a thin `get_effective_room_details(self, **kwargs)` that
returns `self.profiles.get_effective_room_details(**kwargs)`. The enumeration is also stale as a
list of what the parent ref is for: the class additionally reaches through `self._manager` for
get_queue_steps (:1318, :1442), set_queue_breaks (:1794), build_queue (:1911),
build_room_payload (:1915), start_selected_rooms (:1919) and _room_history_cache_ready (:912).

**MISLEADS.** A reader looking for the effective-room-details implementation goes to
core/manager.py, finds a two-line delegator, and may "restore" the described direction by moving
logic onto the core manager — inverting the ownership the same docstring's "Owns:" section
asserts. The stale enumeration also understates the coupling for anyone assessing how
extractable this subsystem is.

### P32 · LOW · over-scoped · passes=1 — `profiles/manager.py:258 (_match_profile_from_fields)`

**SAYS.** # Only this leg. The other five compare a BRAND's vocabulary, which # core does not
own and has no canonical form for; widening the shared # normalizer would assert a framework
opinion about words like "Max" # and "Quick" that belong to the adapter.

**DOES.** Only three of the five are brand vocabulary. The five non-clean_mode legs are
fan_speed, water_level, clean_intensity, clean_passes and clean_passes' neighbour edge_mopping
(:263-273). clean_passes is compared as an int and edge_mopping as a bool, and the constant this
same module imports says so in its own comment — profiles/room_profiles.py:138: "#: Per-room
settings whose VALUES are a brand's vocabulary. ``clean_passes`` / ``edge_mopping`` are
numeric/boolean and belong to no vocabulary." VOCABULARY_FIELDS accordingly excludes both.
profiles/room_profiles.py:271 agrees from the other side, listing clean_passes and edge_mopping
among the "Framework-canonical fields".

**MISLEADS.** The comment is the standing argument against widening
_normalize_profile_match_value. Applied to clean_passes/edge_mopping it blocks a change the
codebase's own doctrine permits — core does own those two — so a real matching bug in the
numeric/boolean legs would be left alone on a stated brand-ownership ground that does not apply
to them.

### P33 · LOW · stale-reference · passes=1 — `profiles/manager.py:1364 and :1789 (C40 comments)`

**SAYS.** :1363-1364 — "# `after_index = rooms emitted so far` and only emits a break once at\n#
least one room has gone out (:1758)". :1788-1789 — "# this reports the ones already saved, which
is the case the comment\n# at :1723 says this method exists to serve".

**DOES.** Both intra-file line pointers are stale. The `if _rooms_emitted >= 1:` gate is at
:1782, not :1758 — line 1758 falls in the middle of the RP-021c prose block ("# derives an empty
list, which WIPES whatever breaks the map was carrying"). The RP-021c comment whose text is
quoted ("an automation that calls apply_run_profile then start_cleaning ... a zone step was
never cleaned at all") begins at :1742, not :1723 — line 1723 is `"profile": profile,` inside
the no_matching_rooms return dict.

**MISLEADS.** A reader jumping to the cited line lands on unrelated code and either concludes
the referenced logic was removed, or reads the wrong construct as the anchoring gate. Low cost
individually, but these two are the file's only same-file line pointers and both are wrong, so
the convention cannot be trusted anywhere in it.

### P34 · LOW · over-scoped · passes=1 — `profiles/room_profiles.py:613-616 (inline comment above the last-resort fallbacks in resolve_room_profile_for_room)`

**SAYS.** Last-resort fallbacks are "" ("nobody said"), NOT Eufy display literals. They fire
only when the room AND the brand's profile both omit the key; a value here would be this module
quietly becoming a fourth source of Eufy vocabulary, which is the exact thing
rooms/room_defaults.py exists to stop.

**DOES.** The very next line does not fall back to "": `resolved_clean_mode =
str(room_config.get("clean_mode", resolved_profile.get("clean_mode", "vacuum")))` — a literal
"vacuum". (clean_intensity, path_type and the fan/water lines below it do use "", and
edge_mopping uses False.) "vacuum" is a framework canonical token rather than brand vocabulary,
so the comment's intent holds; its universal phrasing does not.

**MISLEADS.** A reader takes "Last-resort fallbacks are ''" as a rule covering the block it
heads and either believes clean_mode resolves to "" when nobody declared it, or narrows the
exception by changing "vacuum" to "" — which would be a real regression, since clean_mode is a
framework-owned field per the ProfileRecord docstring. The fix belongs in the comment, not the
code.

### P35 · LOW · false · passes=1 — `profiles/room_profiles.py:756-758 (inline comment on the vacuum-only block in apply_capability_gate)`

**SAYS.** The two halves failed in opposite directions from one root — the mop test UNDER-fired,
this one under-fired too, and only the canonical spelling ever exercised either.

**DOES.** The sentence contradicts itself: it asserts opposite directions and then states both
halves under-fired. It is also the second reading that matches the described history — the old
`clean_mode in {"mop", "vacuum_mop"}` failed to match "Vacuum and mop" so the mop downgrade
never ran, and the old `clean_mode == "vacuum"` failed to match the display label "Vacuum" so
the water/edge clear never ran. Both are missed firings of the same case-sensitivity root, not
opposite failure directions.

**MISLEADS.** Someone reasoning about the ISSUE #48 blast radius from this comment looks for an
over-firing half that never existed, and may conclude one of the two predicates needs loosening
in the other direction. The remedy is deleting three words from the comment; no code is at risk.

### P36 · LOW · stale-reference · passes=1 — `profiles/room_profiles.py:132-133 (coerce_clean_intensity docstring, closing paragraph)`

**SAYS.** Kept as its own name because nine call sites read as intensity questions; the coercion
is ``coerce_axis_value``, shared with every other axis.

**DOES.** There are seven call sites in the package, not nine: profiles/manager.py:628, 956,
1691 and profiles/room_profiles.py:299, 618, 724, 749. Adding the test file
(tests/unit/test_profiles_room_profiles.py, four assertions) gives eleven, not nine either. The
"nine" figure is present-tense here, whereas the earlier paragraph's "executed on every read
from nine call sites" describes the retired normalize_clean_intensity and is history.

**MISLEADS.** Nothing breaks, but the count is the entire stated justification for keeping a
one-line alias rather than calling coerce_axis_value directly. Someone re-evaluating that
decision counts seven, and the rationale reads as already stale — or they hunt for two call
sites that no longer exist.

### P37 · LOW · reason-obsolete · passes=1 — `profiles/room_profiles.py:271-280 — normalize_room_profile docstring`

**SAYS.** Framework-canonical fields (label/clean_mode/clean_passes/ edge_mopping/mop_required)
fall back to the catalog's ``normalize_defaults`` (the adapter's ``normalize_defaults``; empty
when the adapter declares none, since is None — byte-identical). Q2/RP-025 clause (i): the
DISPLAY-AXIS fields (fan_speed/water_level/ clean_intensity) do NOT fall through to that same
in-code default — it is Eufy's own vocabulary ("Max"/"Off"/"Quick") ...

**DOES.** The contrast the docstring draws no longer exists in the code: `d` and
`brand_defaults` are assigned the identical expression on consecutive lines (`d = (catalog or
{}).get("normalize_defaults") or {}`, `brand_defaults = (catalog or
{}).get("normalize_defaults") or {}`), so both groups read the same source. The "same in-code
default" carrying "Max"/"Off"/"Quick" was deleted from this module; what the framework-canonical
fields actually fall through to at the third level is `"vacuum"` / `1` / `False` / `""`, none of
which is brand vocabulary. The first sentence is also truncated mid-clause ("since is None"),
leaving "byte-identical" with no referent.

**MISLEADS.** The stated outcome is still right, but the mechanism described is gone, so the
docstring reads as documenting a live two-tier distinction that a maintainer will try to
preserve — or will "clean up" by re-merging `d` and `brand_defaults` under one name without
realising the duplicate pair is the only trace of the removed tier. The dangling "byte-
identical" belongs to the same retired-fallback family as lines 588 and 812.

## ADAPTER CONTRACT COMMENT AUDIT — 2026-08-23. 30 findings (UNION OF THREE PASSES). NOT APPLIED.

Severity {'high': 5, 'medium': 15, 'low': 10}. Kind {'false': 7, 'reason-obsolete': 1, 'over-scoped': 11, 'stale-reference': 7, 'adopted-alternative': 4}.
34 raw across three passes -> 30 distinct; 4 seen by more than one.

⚠ **ALL FIVE HIGHs WERE SINGLE-PASS.** That is a data point AGAINST the profiles measurement,
where 5 of 6 HIGHs reproduced across two lenses (83%). Two passes covered the same files here
(schema + registry) and none of the HIGHs appeared in both. Samples are small on both sides — 6
there, 5 here — so do not treat either rate as established. The safe reading remains: a union
beats a single pass, and severity does not reliably predict reproducibility.

**The two most consequential findings are DEAD DECLARATIONS on a porter-facing surface**, and I
verified both directly: `vocabulary.blocked_work_mode_states` and `blocked_task_status_states`
have zero readers anywhere in the tree — their only occurrences outside the schema are the Eufy
adapter declaring real values for them.

⚠ **CORRECTED 2026-08-23 — I had the conclusion backwards.** The generator archaeology shows the
check EXISTED: arm 4 of the pre-flight ladder was `work_mode in ['Smart Follow','Auto','Room']`,
the exact values still declared today, and arm 5 was the task-status twin. These declarations are
survivors of a real gate, NOT a feature someone specified and never built. Treat A1/A2
as "restore a lost gate", not "remove a dead key" — the vocabulary is already right.

⚠ **RE-CORRECTED 2026-08-23, second pass — "lost in the port" was still wrong.** The 2026-04-02
integration snapshot (_artifacts/2026-04-02-early-integration/) shows the ladder ported to Python
INTACT — queue_engine.build_start_block_reason, same three strings, same message text, called by
manager.get_start_status. It survived the port. The CALLER was dropped inside the pre-git window,
so the function entered git already orphaned at eae291fa and 2bfda655 deleted it as a "dead
orphan" — correctly, by then. Four stages: live in Jinja, live in Python, orphaned invisibly,
deleted. Nothing but the pre-git snapshot can show stages 2-3. Full account:
docs/dev/22-adapter-contract.md §5.

The schema's stated degradation, "work mode block check
skipped", describes a check that was never implemented. `entities.work_mode` IS read, but by
`core/capabilities.py` for capability detection, not by any start-blocker.

⚠ **Not applied.** Re-verify before editing.

---

### A1 · HIGH · false · passes=1 — `adapters/config_schema.py:271-279 (entities.work_mode)`

**SAYS.** "Work mode sensor. Used by the start-blocker check in core/manager.py to detect
blocked work modes. Degradation: work mode block check skipped."

**DOES.** No start-blocker check reads work_mode anywhere. `grep -rn work_mode --include=*.py`
over the whole integration returns only: adapters/eufy/adapter.py:209/308 (entity candidate +
role declaration), core/capabilities.py:928/939/1138 (capability detection entity resolution),
diagnostics.py:536/551 (probe commentary), and this schema entry. core/manager.py never reads
the entity's state; its start-blocker path (`build_start_blocker_from_lifecycle`,
manager.py:3920, reasons job_paused / onboarding_required / all_selected_rooms_blocked) has no
work-mode arm.

**MISLEADS.** A porter declares entities.work_mode expecting the framework to refuse a job start
while the robot is in a blocked work mode, and gets no protection. Worse in the other direction:
someone debugging "why did a job start during Smart Follow?" goes looking for a bug inside a
core/manager.py check that does not exist, instead of discovering the feature was never wired.

### A2 · HIGH · false · passes=1 — `adapters/config_schema.py:348-365 (vocabulary.blocked_work_mode_states, vocabulary.blocked_task_status_states)`

**SAYS.** blocked_work_mode_states: "Work mode strings that block job start. These are raw (non-
normalized) values from the work_mode sensor. Degradation: work mode block check skipped." —
blocked_task_status_states: "Task status strings that block job start. Raw (non-normalized)
values. Degradation: task status block check skipped."

**DOES.** Neither key has any reader. The only occurrences in the tree are these two schema
entries and adapters/eufy/adapter.py:445-446, which declares real values for both (`["Smart
Follow", "Auto", "Room"]` and `["Cleaning", "Returning", "Washing Mop"]`). There is no dynamic
access either — every `get("vocabulary")` call site in the tree uses literal sub-keys, and the
only `blocked_*_states` read is jobs/active_job.py:3103, which reads the third sibling,
`blocked_dock_status_states`. The declared 'degradation' state is therefore the permanent state.

**MISLEADS.** The block reads as shipped vocabulary with a graceful-degradation fallback, and
one shipped adapter populates it, so it looks proven in the field. An auditor counting adapter-
declared safety vocabulary counts these as live; a brand-3 porter transcribes them and believes
job start is guarded against mid-wash / mid-clean dispatch. The sibling key one entry below IS
read, which makes the dormancy of these two invisible on a skim.

### A3 · HIGH · reason-obsolete · passes=1 — `adapters/registry.py:462-464 (room_profiles catalog check comment)`

**SAYS.** "# Room-profile catalog check — a declared block must be a dict with sane field // #
types. The framework merges it over the in-code defaults (resolve_profile_catalog), // # so a
partial block is fine; this only catches a malformed declaration."

**DOES.** `resolve_profile_catalog` (profiles/room_profiles.py:209-244) has no in-code defaults
to merge over. Its docstring opens "There is NO framework default" and its body returns
`_catalog_key(block, <key>, {})` for all six vocabulary keys — an undeclared key resolves to
`{}`, not to a framework value. `default_profile` is the single exception and is explicitly not
vocabulary. The merge-over-Eufy-defaults behaviour this comment describes was REMOVED on
2026-08-07; rooms/vocabulary_migration.py:3-8 exists solely to heal the rooms it corrupted, and
this same file's `_validate_room_profiles` docstring (registry.py:322-328) narrates the removal
and the NO SUCTION AT ALL bug it caused.

**MISLEADS.** It restates, as current framework behaviour, the exact inheritance that was torn
out because it silently gave Roborock rooms Eufy's words. A reviewer weighing whether an adapter
may omit `builtins` or `normalize_defaults` reads 'a partial block is fine — defaults fill in'
and approves it; what actually happens is those axes resolve empty. The correct reason for 'a
partial block is fine' is one screen away in the same file (undeclared keys resolve empty, which
is a defined answer), so the two comments teach opposite mechanisms for the same conclusion.

### A4 · HIGH · over-scoped · passes=1 — `adapters/config_schema.py:1943 (capability_hints block description)`

**SAYS.** "A hint here is authoritative: it overrides the derived default, and it is what
reaches the room payload gate."

**DOES.** core/capabilities.py splits the hints into two rules. Six of the twelve
KNOWN_CAPABILITY_HINTS are OR'd with entity presence, under the code's own header comment "#
Hint OR entity presence — True from either source is sufficient.": `supports_mop_features =
bool(_hints.get("supports_mop_features")) or bool(water_level_registered or water_level_entity)`
and the same shape for supports_mop_wash, supports_mop_dry, supports_empty_dust,
supports_path_control (:987-994), plus has_attribute_rooms (:969). Only the six routed through
`_hint_wins` — `return bool(_hints[name]) if name in _hints else derived` (:1009) — actually
override; that helper's own docstring says it is "Distinct from the permissive 'hint OR entity
presence' rule above".

**MISLEADS.** A porter declaring `capability_hints: {supports_mop_wash: False}` for a brand that
categorically cannot wash a mop reads this as a binding declaration. It is not: if the wash-mop
button entity resolves (name-token match on any sibling), `_wash_mop_entity_present` is True and
the OR makes supports_mop_wash True anyway, silently ignoring the brand's "I cannot do this".
That is precisely the failure `_hint_wins` was written to prevent ("exactly how
supports_edge_mopping stayed True for a brand declaring it False"), and the schema tells the
author the OR'd half behaves like the override half.

### A5 · HIGH · adopted-alternative · passes=1 — `adapters/registry.py:353-362 (_validate_adapter docstring)`

**SAYS.** "Currently checks:\n - mapping.segmenter_engine resolves to a known engine\n -
mapping.segmenter_tuning passes the engine's own tuning validator\n\n More rules (required
entities, completion block presence, dispatch\n template recognition) land here as the
framework's expectations\n harden."

**DOES.** The same function performs seven block checks, and one of the three explicitly
deferred rules has already landed inside it: `dispatch.template` is validated at :507-517 (`from
..queue.dispatch_engines import known_dispatch_templates` / `if template is not None and
template not in known_dispatch_templates(): issues.append(...)`). Beyond mapping it also
validates room_profiles (:369 via _validate_room_profiles, which HARD-FAILS an absent or empty
block and is the sole reason a stored config can be refused), job_segmenter engine+tuning
(:405-435), room_attribution engine+tuning (:439-469), capability_hints key names (:491-501),
dispatch.phase_timing positivity (:522-540), and setup.steps ids (:544-561). Only "required
entities" and "completion block presence" remain genuinely undone.

**MISLEADS.** This is the contract statement on the framework's central adapter-validation entry
point. A maintainer asked to "add dispatch template recognition to registration" reads the
deferral as still open and adds a second, duplicate template check — or, reading the two-item
"Currently checks" list as exhaustive, concludes a stored config is not validated for
room_profiles/setup/capability_hints and reasons about the save_adapter_config failure path from
a list that is missing the only check that can reject one. config_schema.py:1797-1801 and
:1868-1883 already cite _validate_adapter as validating room_profiles, job_segmenter and
room_attribution, so the two files contradict each other.

### A6 · MEDIUM · over-scoped · passes=2 — `adapters/config_schema.py:1429-1433 (capabilities.supports_zone_repeat)`

**SAYS.** "Whether the zone-clean command accepts a repeat count. False (or omitted
zone_passes_max/passes_max in dispatch) normalizes clean_times to 1 rather than shipping it
verbatim."

**DOES.** `supports_zone_repeat` is read at exactly one place, dispatch/manager.py:308, inside
the `else` (non-`device_mm`) branch of dispatch_zone_clean. On the `device_mm` branch
(dispatch.zone_coords == "device_mm", i.e. Roborock's app_zoned_clean) the flag is never
consulted: lines 253-254 compute `_zone_repeat_max = int(cfg.get("zone_passes_max",
cfg.get("passes_max", 3)) or 3)` and `repeat = max(1, min(int(clean_times), _zone_repeat_max))`,
so a brand declaring `supports_zone_repeat: False` still ships a repeat of up to 3. The
'normalizes to 1' rule is branch-local, not a property of the capability.

**MISLEADS.** The description is written as a property of 'the zone-clean command' generally,
with no mention of the coordinate space. A device_mm brand whose firmware ignores or mishandles
zone repeats declares False, sees the flag documented as authoritative, and still puts repeat>1
on the wire. dispatch/manager.py:299-306 does scope its own comment correctly ('this branch'),
so the schema is the only place that states the rule unconditionally — and the schema is what a
porter reads first.

### A7 · MEDIUM · stale-reference · passes=1 — `adapters/config_schema.py:1431 (zone_passes_max named inside capabilities.supports_zone_repeat)`

**SAYS.** "...(or omitted zone_passes_max/passes_max in dispatch)..."

**DOES.** `zone_passes_max` is read at runtime (dispatch/manager.py:253 and :307) but is NOT a
declared field of the dispatch block. AST-parsing ADAPTER_CONFIG_SCHEMA gives dispatch.fields =
clean_passes_field, command, global_pre_calls, live_room_refresh, map_id_field, map_id_type,
params_as_list, passes_is_global, passes_max, per_room_live_settings, phase_timing,
resolve_live_ids_by_slug, room_fields, room_id_field, rooms_field, service_domain, service_name,
template, zone_command, zone_coords — no zone_passes_max. Because dispatch declares `fields`,
validate_against_schema recurses into it and its unknown-key check (config_schema.py:2051-2058)
fires, so a stored config that declares dispatch.zone_passes_max is rejected by
validate_adapter_config with "dispatch: key(s) not declared in the schema: ['zone_passes_max']"
before services/adapter_config.py:106-111 will persist it.

**MISLEADS.** This is the identical failure the file already documents at lines 1769-1774 for
low_clean_water_margin_ml — a key read by the runtime and named in the docs but absent from the
schema, so a porter following the prose hits save_adapter_config and gets a rejection. Here the
misdirecting prose is inside the schema itself, which makes it read as a declaration of the key
rather than a reference to an undeclared one. Code adapters never notice because they bypass the
schema walk.

### A8 · MEDIUM · over-scoped · passes=1 — `adapters/config_loader.py:7-9 (module docstring)`

**SAYS.** "Called from async_setup_entry before code adapter registration so that code adapters
always take precedence over stored configs for the same vacuum."

**DOES.** The ordering claim is true only for startup. __init__.py:379 calls
load_stored_adapter_configs, then :419/:481 call register_brand_adapter, so at setup the code
adapter overwrites. But services/adapter_config.py:113-118 (_handle_save_adapter_config) calls
`_save_stored(...)` and then `_register(vacuum_entity_id, config)` directly — registering the
stored config over whatever code adapter is live, for the rest of the session.
registry.py:153-158 and config_schema.py:2119 both describe this in the opposite direction, as a
stored config 'shadowing the live adapter'.

**MISLEADS.** 'always' states an invariant the system does not hold. The real behaviour is a
flip-flop: a save_adapter_config call takes effect immediately and then silently stops applying
at the next restart, when the startup ordering hands the vacuum back to the code adapter. A
maintainer who trusts this line will not look for that as the cause of 'my saved adapter config
works until I reboot Home Assistant', and may skip the ordering question entirely when touching
either registration path.

### A9 · MEDIUM · false · passes=1 — `adapters/config_schema.py:570-577 (completion.secondary_clear_entity)`

**SAYS.** "Entity key from entities dict whose cleared state is required alongside
task_status_value for completion. Default: 'active_cleaning_target'."

**DOES.** Nothing reads `secondary_clear_entity`. Its only two occurrences in the tree are this
schema entry and adapters/eufy/adapter.py:522, which declares the value
"active_cleaning_target". The completion gate hardcodes the role: listeners/_common.py:242
builds the signal as `"active_target": _state(entities.get("active_cleaning_target"))` and
completion_secondary_satisfied (:297-298) compares that fixed value against the sentinels. The
sibling key `secondary_clear_sentinels` IS honoured (jobs/active_job.py:3088), which makes the
dead one look live by association.

**MISLEADS.** It is documented as a configuration point ('Entity key from entities dict'), so a
brand whose clear signal sits on a different role declares it and the declaration is silently
ignored — completion then keys on active_cleaning_target, which for that brand may be absent or
may never sentinel. The failure surfaces as 'jobs never finalize', with the adapter config
looking correct.

### A10 · MEDIUM · over-scoped · passes=1 — `adapters/config_schema.py:174-181 (entities.cleaning_time)`

**SAYS.** "Cleaning time sensor in seconds. Used by job finalizer for actual duration.
Degradation: duration derived from job timestamps only."

**DOES.** Seconds is the Eufy case only. The same file declares a top-level `cleaning_time_unit`
block (config_schema.py:1916-1924) reading "Unit of the vacuum's bare-number cleaning-time
counter — \"min\" or \"s\" ... Roborock reports minutes; Eufy reports seconds", and
adapters/roborock/adapter.py:332 declares `"cleaning_time_unit": "min"`. Both consumers honour
it: listeners/job_metrics.py:106-120 passes `ct_unit_hint` alongside the cleaning_time entity,
and jobs/active_job.py:2330-2337 converts via `_duration_state_to_seconds(state,
unit_of_measurement or cleaning_time_unit)`.

**MISLEADS.** A porter reading the entities block takes 'in seconds' as the contract and ships a
bare-number minutes sensor without declaring cleaning_time_unit; job_metrics.py's own comment
says the result is stored 60x low. The correcting seam is 1700 lines away in the same file and
is flagged there as 'the ONE BrandFacts property only Roborock declares, so it is the seam most
likely to be missed' — this line is precisely how it gets missed.

### A11 · MEDIUM · over-scoped · passes=1 — `adapters/config_schema.py:183-189 (entities.cleaning_area)`

**SAYS.** "Cleaning area sensor in m². Used by job finalizer. Degradation: area omitted from job
record."

**DOES.** m² is not what the sensor reports on every install. learning/utils.py:31-56 exists
because of this: `_AREA_TO_M2` converts m²/ft²/in²/yd²/cm² and its comment records "an imperial
HA (e.g. country=US) exposes Eufy's cleaning_area in ft² while Roborock's stays m² (confirmed
live: sensor.alfred_cleaning_area unit ft², sensor.ivy_cleaning_area unit m²)". Every consumer
normalizes rather than trusting m²: jobs/active_job.py:2343-2345,
listeners/job_metrics.py:122-125, learning/job_finalizer.py:728, diagnostics.py:798-812 (which
raises an area_units warning), and jobs/phase_runner.py:127-166.

**MISLEADS.** It states a unit as the contract when the framework's actual contract is 'declare
the entity, we read its unit_of_measurement'. Someone adding a new consumer of
entities.cleaning_area takes the schema at its word and reads `state` bare, reintroducing the
~10.76x inflation that learning/utils.py says breaks cross-brand comparison and mis-fires
swept_area_min_m2. The unit is a property of the user's HA locale, not of the adapter, so it
cannot be fixed by the adapter author the line is addressed to.

### A12 · MEDIUM · over-scoped · passes=1 — `adapters/config_schema.py:1077-1086 (setup.steps)`

**SAYS.** "'import_active_map' is needed by brands whose integration surfaces one map at a time
and requires an explicit import operation (Eufy)."

**DOES.** Roborock declares it too, and for the opposite reason.
adapters/roborock/adapter.py:616-625 sets `"steps": ["add_vacuum", "import_active_map",
"save_rooms"]` under a comment reading "Roborock has no Eufy-style one-at-a-time cloud-map
'import', but the integration still needs a map bucket built from the get_maps rooms before
Configure Rooms can show them. import_active_map is the brand-agnostic 'discover + create
bucket' op (it refreshes the get_maps source first), so declare it here to surface the rooms in
setup." Both shipped adapters declare the step; neither of the two matches the stated necessity
condition exclusively, and the brand named as the sole case is one of two.

**MISLEADS.** The stated condition is a test a porter will apply to their own brand: 'my
integration exposes all maps at once, so I drop import_active_map'. Roborock's own comment says
what happens then — no map bucket is built and Configure Rooms shows no rooms. The step is in
practice mandatory for both shipped brands but is documented as a Eufy quirk, and
setup/drift.py's `_DEFAULT_SETUP_STEPS` ("add_vacuum", "save_rooms") omits it, so an adapter
that declares no setup block inherits exactly the broken shape.

### A13 · MEDIUM · adopted-alternative · passes=1 — `adapters/registry.py:355-362 (_validate_adapter docstring)`

**SAYS.** "Currently checks: - mapping.segmenter_engine resolves to a known engine -
mapping.segmenter_tuning passes the engine's own tuning validator. More rules (required
entities, completion block presence, dispatch template recognition) land here as the framework's
expectations harden."

**DOES.** The function now runs seven check groups, and one of the three named as future work
has already landed. Body: _validate_room_profiles (:369), mapping engine + tuning (:373-400),
job_segmenter engine + tuning (:405-430), room_attribution engine + tuning (:435-460),
room_profiles field types (:465-485), capability_hints key validation (:491-502),
dispatch.template recognition against known_dispatch_templates() (:508-517) and
dispatch.phase_timing positivity (:525-539), and setup.steps id validation (:547-567). 'dispatch
template recognition' is implemented at :512-517.

**MISLEADS.** The docstring is the summary a reader trusts before reading 200 lines of body. It
undersells the function by five check groups and lists an already-shipped rule as pending — so
someone adding dispatch-template validation writes a second, duplicate check, and someone
auditing 'what does registration actually reject?' concludes only the mapping block is enforced
and misses that room_profiles absence is a hard ServiceValidationError for stored configs.

### A14 · MEDIUM · false · passes=1 — `adapters/config_schema.py:1736 (water_model_configs.entry_fields.robot_internal_tank_ml description)`

**SAYS.** "Capacity of the robot's onboard water reservoir in ml. Used to convert wash-frequency
intervals into volume."

**DOES.** Nothing converts anything with it. Its only read in the tree is
planning/run_plan.py:545 (`robot_internal_tank_ml =
_safe_float(model_config.get("robot_internal_tank_ml"), 0.0)`), and the value is then only
echoed into the returned estimate dict at :597. The comment sitting directly above that read
states the opposite: "EST-CLAMP-1: schema-required (every adapter's water model must measure
this on real hardware) but reported-only below -- no calculation here consults it. Left as-is
rather than invented; folding it into the estimate is a design question (per-refill capping?
overhead timing?) for a dedicated follow-up, not a one-line fix." The wash-frequency interval ->
volume arithmetic at :550-553 uses dock_wash_overhead_ml_per_cycle and wash_cycle_count, never
this field.

**MISLEADS.** This is a `required: True` entry_field, so every brand port must supply it. A
porter measuring a new model's onboard reservoir believes the number feeds the water estimate
and will size or debug the estimate against it — e.g. treat an estimate that ignores robot tank
capacity as a bug in their measurement. It is inert everywhere except the reported payload.

### A15 · MEDIUM · false · passes=1 — `adapters/registry.py:725-726 (adapter_honors_clean_order docstring, core/manager.py bullet)`

**SAYS.** "- ``core/manager.py`` — clears the bounds-exit gate, and exports the flag\n into the
dashboard snapshot the card reads."

**DOES.** core/manager.py contains exactly one call to adapter_honors_clean_order, at :5797, and
it feeds only the dashboard snapshot (:5939). There is no bounds-exit gate left for it to clear:
the gate was renamed ("NAMED FOR WHAT IT IS. This was `awaiting_bounds_exit`, a fossil of the
retired bounds system", :4418) and the flag's effect on it was deleted — "The
`honors_clean_order` hard-zero that used to sit here is GONE. It set current_room_overdue =
False for any brand whose robot path-optimises" (:4461-4464). The same docstring's next bullet
acknowledges that removal ("the hard-zero that used to gate it was removed in ``26c4b2d7`` (see
the note at ``core/manager.py``'s current_room_overdue block)"), so the two bullets contradict
each other.

**MISLEADS.** This docstring is explicitly positioned as the canonical consumer list ("THE ONE
READ OF capabilities.honors_clean_order") and says at least six doc sites copied from it.
Someone changing the predicate's semantics goes looking in core/manager.py for a gate that the
flag clears, finds only the snapshot export, and either concludes the read is missing (and re-
adds the hard-zero that was deliberately removed for suppressing stall detection on path-
optimising brands) or mis-scopes the blast radius of the change. The bullet also revives the
retired name the code was renamed to stop propagating.

### A16 · MEDIUM · over-scoped · passes=1 — `adapters/config_schema.py:47-50 (source field description)`

**SAYS.** "How this adapter config was produced. 'code' = registered by a code adapter at
startup. 'config' = written by the UI config flow. The framework treats both identically at
runtime."

**DOES.** registry.py branches on this exact field to pick raise-vs-warn at registration, in
both the coordinator method and the bare shim: `if config.get("source") == "config": raise
ServiceValidationError(...)` (:179 and :649). A code-sourced config with the identical
validation issues only logs warnings and registers. register_adapter_config's own docstring
states the asymmetry ("a STORED config (``source == \"config\"``) now HARD-RAISES when issues
are found ... A CODE-sourced config ... stays warn-only"), and this same file's walker anchor
reads "anchor: INYA5T84 runtime validation is the SAME walk as the tests; severity by source"
(:1953) with a block comment at :1874-1879 describing a gap that "only bit the CONFIG path".

**MISLEADS.** An author of a UI/service-authored config reads this and expects no source-
dependent behaviour, then hits a ServiceValidationError from save_adapter_config for an omission
the shipped code adapters get away with as a log warning. The claim is true of every downstream
consumer (nothing else in the tree branches on adapter-config source) but false at the one
boundary where source is the whole point, and the description presents it without that
qualifier.

### A17 · MEDIUM · adopted-alternative · passes=1 — `adapters/entity_resolve.py:532-540 — anchor RNZM4AYY, above the _claimed_by closure in resolve_declared_entities`

**SAYS.** # anchor: RNZM4AYY longest-suffix ownership test — the replica set # # REPLICA, three
copies. The same rule — a candidate belongs to the declaration # that explains the MOST of its
name — is implemented separately in # `capabilities.py::augment_candidates_from_device` (the
probe's suffix universe) # and in `tokens_owned_elsewhere` above (the button token sets). All
three must # agree, or a role resolves one way through the declared map and another way #
through the probe, and a button binds to a sibling that already has an owner. # See 00c. `python
scripts/doc_anchor.py --show RNZM4AYY` lists all three.

**DOES.** There is no separate implementation in capabilities any more — the two suffix sites
are thin wrappers over ONE function. Here: `def _claimed_by(object_id): return
claimed_by(object_id, declared_suffixes)` (entity_resolve.py:541-542). There: `def
_claimed_by(sib_object): return claimed_by(sib_object, universe)` (capabilities.py:665-666),
where `claimed_by` is imported FROM this file (capabilities.py:48-55, under the header 'THE
suffix predicate — one copy, shared with adapters.entity_resolve'). Only
`tokens_owned_elsewhere` is a genuinely separate implementation, so the suffix rule is one
implementation, not three copies that must be kept in agreement. Contradicted twenty lines above
by the same file: 'ONE COPY NOW — see build_suffix_universe. This block and its twin in
capabilities.augment_candidates_from_device were the same predicate written twice; keeping them
literally the same function is the point.' (511-513). The counterpart marker in capabilities was
updated and this one was not: capabilities.py:663-664 reads 'REPLICA RNZM4AYY — the twin of this
rule lives in `entity_resolve.py::resolve_declared_entities`. Changing one means checking it.' —
twin, and no claim of a separate implementation.

**MISLEADS.** A maintainer changing the ownership rule reads 'implemented separately ... All
three must agree' and goes hunting for a second suffix implementation in
capabilities.augment_candidates_from_device to hand-edit into agreement. Finding only a one-line
wrapper, the plausible 'fix' is to re-inline the predicate there so the comment is true again —
restoring exactly the two-copy fork that produced live:ENT-4 (guard added to one twin, not the
other) and that build_suffix_universe/claimed_by were extracted to end. Inverse risk: a reader
who believes the copies are independent may edit only capabilities and not realise the change
lands in every caller of the shared function, including the maintenance path.

### A18 · MEDIUM · stale-reference · passes=1 — `adapters/entity_resolve.py:595-607 — REPLICA RNF2RCXP block inside resolve_declared_entities' suffix-exhausted branch`

**SAYS.** # REPLICA RNF2RCXP — translation_key rescue, 3 copies, must agree # # REPLICA — the
same rescue runs in THREE places, deliberately: this one, plus #
`entity_resolve.resolve_declared_entities` (the declared `entities` map) and #
`capabilities.augment_candidates_from_device` (the roles `detect_capabilities` # probes). ... #
# ⚠ CHANGING ONE MEANS CHECKING THE OTHER TWO.

**DOES.** This block is INSIDE `resolve_declared_entities` (def at line 432; block at 595-607).
So 'this one' IS `entity_resolve.resolve_declared_entities` — the list names the current site
twice and omits the actual third member of the set, `capabilities._rescue_maintenance_source`
(capabilities.py:218). The block is a verbatim paste of the wording that is correct only where
it was written, in capabilities._rescue_maintenance_source (capabilities.py:260-267), whose
'this one' really is the maintenance copy. This file's own header for the same anchor lists the
three sites correctly (lines 249-260: resolve_declared_entities /
capabilities._rescue_maintenance_source / capabilities.augment_candidates_from_device). (The
same paste defect exists at capabilities.py:722-728, outside the audited file.)

**MISLEADS.** The ⚠ line is a checklist, and here it names the wrong two. An editor changing
this rescue follows it, checks augment_candidates_from_device and 'itself', and never opens
`capabilities._rescue_maintenance_source` — reproducing precisely the two-of-three landing the
comment itself warns about ('The first fix (`ef810519`) landed in two of the three and 4381
green tests said nothing'). The maintenance copy is the one that historically had no guard, so
it is the worst one to drop off the list.

### A19 · MEDIUM · over-scoped · passes=1 — `adapters/entity_resolve.py:27-32 — module docstring, SAFETY PROPERTIES item 1`

**SAYS.** SAFETY PROPERTIES, in order of importance: 1. **It never changes a resolution that
already works.** A declared ID present in the state machine is returned untouched, so no working
install can be altered by this.

**DOES.** The overrides pass, added later inside this module's `resolve_declared_entities`,
rewrites the declared id with no state check at all and before the state check that the property
describes: `if isinstance(overrides, dict): for _role, _chosen in overrides.items(): if
isinstance(_chosen, str) and "." in _chosen: entities[_role] = _chosen` (470-473). The 'already
works — never touch it' guard is `if hass.states.get(declared) is not None: continue` at
556-557, i.e. eighty lines later and only over the rescue loop. Both shipping adapters pass a
real overrides map (adapters/eufy/adapter.py:331 and adapters/roborock/adapter.py:301,
`overrides=entity_overrides`), and the function docstring documents the behaviour as intended
('A role is pinned even when the chosen entity has no state'), so the code is deliberate and the
module docstring's universal claim is the stale half.

**MISLEADS.** A role whose declared id resolves perfectly IS altered when the user sets an
override for it, so 'no working install can be altered by this' is false for every install with
an override. Someone auditing a report of 'my binding changed even though the old entity still
exists' would clear this module on the strength of the safety property and look for the cause in
the adapters or the options flow, where it is not. The mirrored claim in
adapters/eufy/adapter.py:353 IS correct at its own site because `_rescue_select_block` passes
`overrides=None`, which makes the module-level version look corroborated.

### A20 · MEDIUM · over-scoped · passes=1 — `adapters/entity_resolve.py:460-463 — comment over the overrides pass in resolve_declared_entities`

**SAYS.** # THE USER'S CHOICE IS A DECLARATION, not a candidate. Pinned before anything else #
runs so it is what the rescue and exclusivity passes below reason about: its # suffix joins
`declared_suffixes` and therefore participates in the ownership # check, exactly as a brand-
declared id would.

**DOES.** The override's suffix joins `declared_suffixes` only when the chosen entity id happens
to be prefixed by the vacuum's own object_id. `declared_suffixes = build_suffix_universe([v for
v in entities.values() ...], vacuum_object_id, reserved_suffixes)` (514-518) derives each suffix
through `_suffix_of`, which bails first: `if not object_part.startswith(vacuum_object_id):
return None` (426-427). An override pointing at a differently-named entity — the case overrides
exist for, and this module's own headline example,
`sensor.dining_room_alfred_total_cleaning_area` against object_id `alfred` (docstring line 12) —
contributes NOTHING to the universe, and because the override has replaced the brand's declared
id in `entities`, that role's brand suffix is also dropped from the universe (masked today only
because both adapters pass `reserved_suffixes=ALL_SUFFIXES`, eufy/adapter.py:332,
roborock/adapter.py:302). The same prefix requirement means the following sentence's 'The rescue
pass below may still repair it' cannot fire for such an override either — the loop exits at
`suffix = _suffix_of(...)` / `if not suffix: continue` (559-560). capabilities.py:684-687
documents the opposite behaviour for its own path as deliberate: 'an override that does not
follow this vacuum's naming cannot pollute the suffix universe.'

**MISLEADS.** 'exactly as a brand-declared id would' reads as unconditional and is true only for
the minority of overrides that follow the derived naming. A maintainer reasoning about whether
role A's rescue can steal role B's overridden entity concludes the ownership check covers it; it
does not — the protection comes entirely from `reserved_suffixes`, which is a per-adapter
argument a third brand can simply omit. That is the live:ENT-4 collision shape (`_cleaning_area`
vs `_total_cleaning_area`) reopening silently at exactly the point the comment promises it is
closed.

### A21 · LOW · adopted-alternative · passes=1 — `adapters/registry.py:504-507 (dispatch template check comment)`

**SAYS.** "# Dispatch template check — a declared template must resolve to a registered // #
dispatch engine. A schema-valid template with no engine yet (e.g. // # dreame_room_clean before
its engine ships) is rejected at registration // # rather than silently falling back to the Eufy
shape and cleaning wrong."

**DOES.** dreame_room_clean's engine has shipped. queue/dispatch_engines.py:345 sets
`template_name = "dreame_room_clean"` on DreameSegmentEngine (a full implementation with
`_ARRAY_FIELDS` and `build_payload`), and :433 registers it: `"dreame_room_clean":
DreameSegmentEngine(), # positional parallel arrays`. It is therefore in
known_dispatch_templates() and the check passes it.

**MISLEADS.** The only example given for the guard is now a template that validates cleanly. A
reader testing the comment by declaring dreame_room_clean sees it accepted and may conclude the
check is dead or the comment describes something that never happened — when the guard is live
and correct, it just needs an example that is still unregistered.

### A22 · LOW · stale-reference · passes=2 — `adapters/config_schema.py:1769-1784 (low_clean_water_margin_ml block comment + description)`

**SAYS.** "# Undeclared until 2026-08-15 while being READ by run_plan.py:539 ..." and, in the
description, "Read in planning/run_plan.py (_build_effective_start_plan, the water block)."

**DOES.** The read is at planning/run_plan.py:584 — `_low_margin_ml =
_safe_float(model_config.get("low_clean_water_margin_ml"), 300.0)` — inside
`estimate_job_water_usage`, which is defined at line 393. `_build_effective_start_plan` is a
different method defined at line 1048, i.e. 464 lines below the only read. Line 539 today is
blank, inside the wash-cycle-count block. (The default of 300.0 and the 'one water key that
truly defaults' claim are both correct.)

**MISLEADS.** Both pointers send a reader to the wrong place: the line number to dead space and
the function name to a method that never touches the key. Someone changing the low-water margin
semantics opens _build_effective_start_plan, finds nothing, and either concludes the key is
unused or edits the wrong plan-assembly path.

### A23 · LOW · stale-reference · passes=1 — `adapters/config_schema.py:1826-1828 (map_render)`

**SAYS.** "VA-owned client-side map render declaration (doc 22 §13a.3). Presence is the gate for
supports_va_render (core/manager.py ~:4055) — presence only; the interior is not validated."

**DOES.** The gate is at core/manager.py:5881: `supports_va_render =
isinstance(_adapter_cfg.get("map_render"), dict)`, exported at :5985. core/manager.py:4055 is
`def get_known_vacuum_ids(self) -> list[str]:`, an unrelated singleton-ownership helper under
the `anchor: BNA9T0JJ` block. The gate itself and the 'presence only' claim are correct.

**MISLEADS.** A reader jumping to :4055 to confirm the gate lands in vacuum-id aggregation with
no map_render anywhere in sight, and has to grep anyway. The '~' signals approximation but the
drift is ~1800 lines into a different section of a 7000-line file, which is past what a reader
will scan around.

### A24 · LOW · stale-reference · passes=2 — `adapters/registry.py:726-734 (adapter_honors_clean_order docstring, jobs/active_job.py bullet)`

**SAYS.** "- ``jobs/active_job.py`` — gates RUNNING-LONG (:1185) and SKIPPED (:1223). NOT stall:
the hard-zero that used to gate it was removed in ``26c4b2d7`` ..."

**DOES.** Both cited lines have drifted, and one now points at the construct the sentence
disclaims. The running-long gate is at jobs/active_job.py:1209-1214 (`if (_honors_clean_order
and (not stall_detected) and current_room_id is not None ...)`) and the skipped gate at :1248
(`if _honors_clean_order and current_room_id is not None:`). Line 1185 is now
`self._manager.hass.bus.async_fire(EVENT_STALL_DETECTED, {...})` — the stall emission. The
substance of the bullet (which two branches gate on the flag, and that stall does not) is
correct.

**MISLEADS.** The docstring's whole point is that stall must NOT be gated on honors_clean_order
— and its own citation now lands on the stall event fire. A reader spot-checking ':1185' sees
stall code under a claim about running-long and may 'correct' the docstring, or worse, conclude
stall is still gated and go looking to remove a gate that was already removed in 26c4b2d7.

### A25 · LOW · stale-reference · passes=1 — `adapters/registry.py:541-546 (setup-steps check comment)`

**SAYS.** "# Setup-steps check — RP-033/SETUP-9. Three places in this codebase already // #
claim an unknown step id is \"rejected at registration\" // # (config_schema.py's own
setup.steps description, setup/drift.py:52-53 and // # :102-104's docstring) while nothing here
actually did that."

**DOES.** setup/drift.py:52-53 is the shared 'System invariants that bind in this file' preamble
('# System invariants that bind in this file. Declared and explained elsewhere / #
(docs/dev/00b-invariants.md)...'), not a registration claim. The actual claim now sits at
drift.py:85-86: "# Closed enum of setup step IDs. Adapters must declare a subset of these / #
values; the registry rejects unknown IDs at adapter registration time." Lines 102-104 are three
literal entries of the SETUP_STEP_LABELS dict ('save_rooms': 'Configure rooms', etc.) with no
docstring at all; the nearest prose is the comment at :96-98, which makes a different claim
(that adapters cannot override labels).

**MISLEADS.** The comment's force comes from naming three independent sites that all asserted an
unenforced rule, so the citations are the evidence. Two of the three now resolve to unrelated
boilerplate, which makes the justification unverifiable at the moment someone questions whether
this check is worth keeping — and 'there is no docstring at :102-104' invites the conclusion
that the claim was overstated.

### A26 · LOW · false · passes=2 — `adapters/config_schema.py:2048-2050 (UNKNOWN KEYS scope note)`

**SAYS.** "# Only applied where the schema actually enumerates the shape. Nine blocks are
declared // # as bare `dict` with no `fields` (settings_selects, mapping, map_render,
room_profiles, // # …) and are legitimately open-ended; asserting there would be noise, not a
contract."

**DOES.** Ten, not nine. AST-parsing ADAPTER_CONFIG_SCHEMA gives exactly ten top-level dict
blocks with neither `fields` nor `entry_fields`: settings_selects, mapping, map_state_source,
map_render, device_clean_order, job_segmenter, room_attribution, room_profiles, anomaly,
capability_hints. (The four named in the parenthetical are all genuinely in that set, and the
behavioural claim — that the unknown-key check never reaches them, since recursion only fires on
`fields`/`entry_fields` — is correct.)

**MISLEADS.** A count is checkable and someone will check it. Finding ten where nine is claimed
reads as 'a block was added since this was written and nobody reconciled the note', which
invites either a wrong edit to the count or doubt about the surrounding (correct) reasoning. The
likeliest true history is that map_state_source or device_clean_order landed after the note.

### A27 · LOW · false · passes=1 — `adapters/config_loader.py:4-5 (module docstring)`

**SAYS.** "Reads adapter configs written by the UI wizard from integration storage and registers
them with the adapter registry at startup."

**DOES.** There is no UI wizard. config_flow.py contains no reference to adapters at all, and
`save_adapter_config` appears nowhere in the repo's TypeScript/JavaScript card sources — the
only writers of `data["adapters"]` are this module's own save_adapter_config() and the
`eufy_vacuum.save_adapter_config` service. services/adapter_config.py:3-4 describes the whole
flow as "Six services driving the UI-based adapter-config flow (for future multi-brand setups)",
and config_schema.py:10 says the UI config flow "will generate it in a future pass" — while the
same schema docstring at :19 and the `source` field at :48-50 assert the present tense
("'config' = written by the UI config flow").

**MISLEADS.** Someone tracing 'who writes data["adapters"]' goes hunting for a config-flow step
that does not exist, and may conclude the write path is elsewhere and stop looking at the
service. registry.py:153 gets this right by calling it "UI/service-authored", and
config_schema.py:10 gets it right by marking it future — the three files disagree with each
other about whether the path has shipped.

### A28 · LOW · stale-reference · passes=1 — `adapters/entity_resolve.py:440-443 — resolve_declared_entities docstring, report shape`

**SAYS.** Return ``(entities, report)`` with unresolvable IDs repaired where unambiguous.
``report`` maps role -> ``{"declared": ..., "resolved": ...}`` for each remap, and is empty when
nothing needed rescuing (the overwhelmingly common case).

**DOES.** Every report entry the function writes carries a third key naming the rung that won:
`report[role] = {"declared": declared, "resolved": by_key, "via": "translation_key"}` (621-628)
and `report[role] = {"declared": declared, "resolved": resolved, "via": "suffix"}` (652). The
two-key shape in the docstring predates the translation_key rung; the inline note at 623-626
('Additive: consumers ignore unknown keys today') is accurate on its own terms but was never
reconciled with the docstring above it.

**MISLEADS.** The docstring is the shape spec for a returned structure that crosses into
diagnostics and the card. A consumer written from it — or a test asserting the report dict
equals a two-key literal — is written against a shape the function never produces, and 'via' is
exactly the field a future 'why did this bind?' surface would key off.

### A29 · LOW · over-scoped · passes=1 — `adapters/entity_resolve.py:294-296 — resolve_action_entity docstring, rung 1 of the ladder`

**SAYS.** The ladder, in order — the first rung that answers wins: 1. the derived id
``<domain>.<object_id>_<suffix>``, when it has state;

**DOES.** There is an unstated branch that returns the derived id with NO state. When the vacuum
itself is not in the entity registry, the function falls through to `if entry is None:` and
returns the derived id on registry presence alone: `if registry is not None and
registry.async_get(derived) is not None: return derived, _status(derived)` (334-337). `_status`
inspects only `disabled_by` (320-324), so a registered-but-stateless entity comes back as
"resolved", not "missing" — and the ladder's rungs 2 and 3 are skipped entirely on that branch.

**MISLEADS.** The docstring presents the ladder as the whole algorithm with 'when it has state'
as rung 1's qualifier, so a reader concludes a stateless derived id is never returned.
dock/manager.py:125-126 presses whatever comes back with status "resolved", which for that
branch can be an entity with no state — the silent `log_missing` no-op this function's own
docstring says the disabled/missing split exists to prevent. The branch needs the vacuum entity
to be absent from the registry, so it is rare in production but reachable from tests and from a
partially-set-up install.

### A30 · LOW · over-scoped · passes=1 — `adapters/entity_resolve.py:452-454 — resolve_declared_entities docstring, the argument for applying overrides in the shared resolver`

**SAYS.** while ``detect_capabilities`` sees only a 14-role candidate subset — so an override
applied only there was a no-op for ``battery`` and ten other declared-only roles.

**DOES.** 14 and 'battery and ten other' are exactly Eufy's numbers, presented as a general fact
about detect_capabilities. Counted from source: adapters/eufy/adapter.py:199-217 declares 14
entity_candidates roles against 22 in its `entities` map (lines 264-320), leaving 11 declared-
only roles — battery, error_message, charging, wash_frequency_mode, wash_frequency_value_time,
dry_duration, total_cleaning_area, total_cleaning_time, total_cleaning_count,
dock_firmware_version, scene_select. Roborock's entity_candidates map
(adapters/roborock/adapter.py:177-182) has FIVE roles, so detect_capabilities sees a 5-role
subset there, and both adapters feed the same detect_capabilities.

**MISLEADS.** The paragraph's own thesis is brand symmetry — 'an override cannot work on one
brand and not the other' — and it is argued with a number true of one brand only. A reader
checking the reasoning against the Roborock adapter finds 5 where the docstring says 14 and may
distrust the (correct) conclusion, or may carry '14 roles' forward as a property of
detect_capabilities itself. The underlying argument holds for both brands; only the figure is
Eufy-specific.

