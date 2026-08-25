# Coverage walk — 17 uncovered blocks, read and classified

**Method:** not a percentage sweep. Every module carrying a run of **≥8 consecutive
uncovered STATEMENTS** (`python scripts/coverage_triage.py`), each block read in full and
classified as real logic or not. The goal was Chris's, verbatim: *"high or low coverage
final number is irrelevant … no real logic missed is."*

**Reachability was checked, not assumed.** An uncovered path that is also unreachable is
dead code, not a gap. Every HIGH below was confirmed live — registered, declared, and
called.

**No ablations were run, deliberately.** Ablation proves a test *fails to catch* a change;
for a block with zero coverage there is nothing to catch, and coverage already proves it.
Ablation is the right instrument for the *other* question — whether COVERED code is
vacuously covered — which this walk did not attempt.

Source: `coverage.json`, 2026-08-25, 92.3% overall, 4676 passed / 2 skipped.

---

## HIGH — shipped, user-reachable, real consequence

### 1. `services/setup.py:370-400` — `set_entity_override`, 21 statements, the largest run in the repo

The entire handler. **Shipped in 2.1.0 and named in the release notes.** Fully wired:
registered at `setup.py:656`, declared in `services.yaml:43`, referenced from
`src/constants.js`.

It mutates persistent storage (`ENTITY_OVERRIDES_KEY`), splits on set-vs-clear (a blank
`entity_id` clears the role), prunes the per-vacuum dict when it empties, and reloads the
config entry.

⚠ **It also `setdefault`s a store bucket for `vacuum_entity_id` with no managed-vacuum
check.** That is the phantom-bucket shape `services/stall_capture.py`'s own comment names
as `C12` — a call for an unmanaged id leaves a container behind. Here there is no
authorization check at all, so it is the C12 pattern without even the hand-rolled guard.

**PROVEN, not inferred (2026-08-25).** Two services in this same module, the same ghost id:

```
setup_set_map_camera  -> error       (refuses; [SVS-10] already pins this)
set_entity_override   -> success     and persists {'vacuum.ghost': {'filter': 'sensor.nope'}}
```

So it is an inconsistency, not a policy — a guard present in one sibling and absent in the
other, with a test already pinning the strict side. `feedback_partial_guard_blind_spot`.

**Chris, 2026-08-25 — deferred, leaning REFUSE:** *"an unmanaged vacuum has nothing to deal
with… I don't know [why] I was even creating panels for unmanaged vacuums."* Not fixed here
because it changes a service shipped in 2.1.0 and touches a persisted key. Before changing
it, answer the one question that decides whether it is a fix or a regression: **can the
panel reach this service before a vacuum is managed?** If not, matching
`setup_set_map_camera` is a five-line change and its test is the template.

⚠ The tests added in `9299c857`+ deliberately do NOT assert the ghost behaviour either way.
Pinning it would freeze the bug; leaving it unpinned keeps all three options open.

Also noticed: the module docstring lists twelve `setup_*` services and does not mention
`set_entity_override` at all — stale since it shipped.

### 2. `jobs/phase_runner.py:1562-1587` — strict-order wedge prevention, 11 statements

RP-007 step 6. When live resolution REFUSES a phase (room gone from the current map, or
freshness unprovable), this logs it, records `skipped_rooms` on the stored job, releases
the dispatch guard and advances. Its own comment states the purpose: *"advance to the next
phase instead of wedging the run."*

**The code that stops a strict-order run from wedging has no test** — in the subsystem the
audit calibration picked for worst blast radius, for a feature shipped in 2.1.0.

### 3. `services/stall_capture.py:78-105` — `_set_stall_capture`, 9 statements

The whole handler, and it *contains a defect its own comment documents as open* (`C12`):
hand-rolled authorization instead of `require_managed_vacuum`, diverging twice —
`setdefault` mutates `manager.data` BEFORE the decision so a refused call leaves
`data["vacuums"] = {}` behind, and the raise carries no `translation_key`, so the refusal
reaches users in English in all 18 locales. Neither is tested, so neither can regress
loudly.

### 4. `adapters/roborock/dock.py:76-95` and `145-172` — 14 + 8 statements, module at 53.3%

**Shipped in 2.1.0** (dock consumables, release notes). Uncovered: the device-registry walk
that FINDS the dock device, the success path (`RoborockDockFeatures.from_dock_type` and its
return), and the forward-compat branch for a dock newer than the installed
`python-roborock`.

The feature's happy path is exercised on Chris's hardware and nowhere else. It works; nothing
would tell us if it stopped.

### 5. `rooms/reconciliation.py:465-475` — second single-pair carry, 11 statements

Carries every durable setting to a new room id and rewrites the access graph through
`id_remap`. Its own comment: *"a confirmation given on a mis-stated finding is expensive."*

⚠ **The module has TWO sibling single-pair predicates and only one is tested.** Line 297 is
well covered — inverting it turns 20 tests red. This one has zero coverage. That is
`feedback_partial_guard_blind_spot` exactly: diff a predicate against its copies.

### 6. `diagnostics.py:440-495` — the entity census, 13 statements

Behind **Setup → System**, the screen shipped in 2.1.0 that users are told to open when a
value reads unavailable. Uncovered, including the two-scope (device + config-entry) sweep
that was the fix for issue #49.

Its comment is the reason this ranks HIGH rather than MEDIUM: *"A blank census on a naming
problem is worse than no census, because it reads as 'this device exposes nothing'."* A
broken census actively misleads instead of failing quietly.

---

## MEDIUM

### 7. `mapping/map_source_coordinator.py:803-826` + `learning/external_run.py:386-400`

**A two-module chain, both ends uncovered** — 15 + 14 statements. The coordinator's
`async_get_map_data_dict` (backend gating, memory-primary path, `.storage` fallback) and its
caller computing room footprints by area for external-run attribution.

The whole external-run area-attribution path — vendor-app cleans folded into learning, a
README feature — is untested end to end, and **both ends swallow exceptions and return
empty**. A break degrades attribution silently, with no signal anywhere.

`async_get_map_data_dict` has **five** caller modules, including `dispatch/manager.py`.

### 8. `maintenance/manager.py:263-270` — guide translation overlay, 8 statements

Applies the localized guide (steps, notes, clean/replace frequencies) over the English base.
This is the code behind the `Filter_*.png` screenshots in 18 languages. If it breaks, every
language falls back to English guide prose **silently**.

⚠ Double blind spot: it is untested here, AND the screenshot-freshness gate explicitly does
not watch guide prose (it is not in `en.js`). Nothing covers this path from either side.

### 9. `config_flow.py:314-329` — options-flow resolution gaps, 9 statements

Computes which entity roles are unresolved or ambiguous, feeding the options form.

**Thematic finding:** with #1 and #6, the entity-override feature shipped in 2.1.0 has **all
three of its surfaces uncovered** — the gaps display that tells you something needs an
override, the service that sets it, and the census that explains why.

### 10. `mapping/mapping_services.py:880-888` — image conversion, 9 statements

base64 decode, PNG magic check, PIL conversion fallback for non-PNG.

⚠ **A finding beyond coverage: the failure reason is ambiguous between two very different
causes.** Pillow is optional and undeclared, so `from PIL import Image` raises ImportError on
a plain install, is caught by the bare `except Exception`, and returns
`{"saved": False, "reason": "unsupported_format"}` — the same reason a genuinely corrupt
image produces. A user who uploaded a valid JPEG on an install without Pillow is told their
image format is unsupported. That is the absence-reads-alike trap.

---

## LOW — real logic, small consequence

| block | what | why LOW |
|---|---|---|
| `mapping/tracker.py:319-329` | `_compact_dock_drift` — rolls a JSONL to its last N lines, preserving `_meta`, atomic tmp-replace | diagnostic instrument, not a control path. Off-by-one risk is real. **Trivially testable** — pure file in, file out |
| `debug_capture.py:644-655` | `stop` / `dump` service handlers | maintainer tooling — but it is the instrument you reach for *during* a live-bug hunt, so a break surfaces at the worst moment |
| `diagnostics.py:387-406` | live-map-image pattern resolution | diagnostic display only |
| `services/stall_capture.py:114-170` | `_dev_inject_stall` | maintainer tool. Does fire a real bus event and has two user-visible refusals, both untranslated |
| `button.py:100-131` | profile-rename → button entity swap | **already known — ledger T4, open.** The comment says it verbatim: *"delete this branch and the suite stays green"* |

`button.py` is worth noting for a second reason: the block metric **rediscovered a gap the
team had already logged**, independently. Weak evidence, but evidence, that the instrument
points at real things.

---

## What this walk did NOT cover

* **Vacuously-covered code.** Every finding here is a zero-coverage block. Code that is
  covered by isolated, mocked tests is the *other* failure mode and is invisible to this
  method — see the mock/partial-branch signals in `scripts/coverage_triage.py`, whose
  discriminating power is unvalidated and whose one mutation test went against it.
* **Boundary values.** Found incidentally during that mutation test: `core/charging.py`
  sits at **100% with zero partial branches**, and `battery_level == 0` — a dead battery —
  passes silently when the comparison is broken. Neither coverage nor this walk sees that.
* **Blocks under 8 statements**, by construction.

## Suggested order, if tests get written

1. `set_entity_override` (#1) — largest, shipped, storage-mutating, no auth check
2. phase-runner wedge prevention (#2) — worst blast radius
3. `roborock/dock.py` (#4) — shipped feature, happy path unexercised
4. reconciliation second pair (#5) — cheap, and its tested sibling is a ready template
5. `_compact_dock_drift` (LOW) — near-free, pure function, would take minutes

`button.py` T4 is already on the ledger and needs no re-triage.

---

# WAVE 2 — widened to runs of ≥3 statements

Chris: *"walk all files with any lines of 3 or more contiguous skipped to check for logic —
log only is not an issue."*

**99 blocks across 41 modules.** Each uncovered statement mapped to its AST node type, then
read.

⚠ **ZERO blocks are log-only, so the dismissal removes nothing.** The highest log
proportion in any block is 33%; logging appears mixed *into* blocks rather than as
standalone runs. All 99 carry assignments, calls, branches or raises. That result was
checked against the classifier — the ranked-by-log-proportion list is what proves it —
rather than trusted because it was convenient.

## CRITICAL — physical consequence

### `dispatch/manager.py:626-638` — the safe-water abort

Its own comment states the stakes: *"RP-007 step 8 (DQ-ACT-5): the mixed-batch SAFEST-water
push is SAFETY-critical — if it fails, the device keeps its previous (possibly high) water
and the dispatch would wet-mop the dry rooms it exists to protect. Abort the dispatch."*

**The abort that prevents wet-mopping rooms marked dry has no test.** Every other finding
here is data or UX. This one ends with water on a floor configured to stay dry.

## HIGH — new in wave 2

| block | what |
|---|---|
| `core/manager.py` ×4 — `4978-4980`, `5003-5006`, `5020-5032`, `5129-5142` | the **stall-detection FIRING paths**: `_stuck_err_open`, the elapsed-window calculation, the `area` trigger with its progress detail, and the event payload with room-name resolution |
| `switch.py:155-160`, `202-205` | the **`clean_order_override` switch entity** — constructor and `is_on`. The switch the entire 2.1.0 Override Order feature hangs on |
| `learning/history_store.py:2095-2098` | the **`attribution_shift` learning blocker** — the gate marking a run unusable for learning. The guard against the exact failure the audit calibration named worst blast radius: a wrong record poisoning learning permanently |
| `core/capabilities.py:528-532`, `793-801` | entity-resolution heuristics — the BY_MAGNITUDE disambiguator with its *"0 vs 0 is not evidence"* guard, and the translation-key sibling merge with origin tracking. The issue #49 area, shipped in 2.1.0 |
| `core/manager.py:2711-2728` | **stranded-break self-heal.** A room disabled AFTER a break was placed strands it at the queue edge; this drops it rather than letting `get_queue_steps` crash on read |
| `learning/history_store.py:894-900` | phase-slot synthesis when a phase is missing from the planned structure — appends and re-sorts rather than losing the record |
| `learning/manager.py:1004-1018` | `close_phased_job` sealing unrun phases as `cancelled_upstream` — implements **Chris's directive 1** |

### The stall-capture feature is untested end to end

Nine blocks across three modules: detection (`core/manager` ×4) → capture listener
(`listeners/stall_capture` ×3) → arming service (`services/stall_capture` ×2). The README
advertises it — *"fires a Home Assistant event when the vacuum has been in a room
significantly longer than its learned average."*

A larger uncovered feature surface than the entity-override cluster in wave 1.

## Cross-cutting — not about coverage

### The optional-Pillow reason is inconsistent, and one side proves the other is a bug

`listeners/stall_capture.py:377-383` distinguishes the two causes:

```python
"no_pillow" if _scr.Image is None else "unusable"
```

`mapping/mapping_services.py` does not, in **two** places — `880-888` returns
`unsupported_format` for both a corrupt image and a missing Pillow, and `915-921` silently
falls back to the **declared** image dimensions when PIL is absent, so a map image's real
size is never verified on a plain install.

The codebase already knows the distinction matters. Conflating it is an inconsistency, not
a choice.

### `get_active_map_id` guard duplicated verbatim

`mapping_services.py:627-631` and `2523-2527` are the same five statements — one question
answered twice, both uncovered. Fix one and the other rots
(`feedback_centralize_question_not_vocabulary`).

## Dismissed on reading

* `os.remove` / cleanup wrapped in `except OSError: pass` (`mapping_services` ×3).
  **`history_store:506-509` is NOT one of these** — it unlinks a temp file and **re-raises**,
  which is atomic-write correctness.
* `except: log; return None` read-failure paths returning a sentinel no caller branches on.
* Diagnostic dump-formatting branches (`map_source_runtime:377-379`).

Everything else in the 99 was left classified rather than dismissed. The tables above are
what is worth a test — not the whole list. Reproducible: `python scripts/coverage_triage.py`
for ≥8, and the AST walk in this session's scratchpad for ≥3.
