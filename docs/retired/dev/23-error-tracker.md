# 23 — Error Tracker

> **Scope:** Behavioral specification for `core/error_tracker.py` — the storage shapes,
> the edge-detection rules, the timing, and the public API. Error tracking is mostly
> *edges*: what counts as an error starting, what counts as it ending, and what a
> restart is allowed to assume about the run it woke up in the middle of. Those are
> hard to recover by reading the module, because each one is a decision rather than a
> mechanism, which is what this doc is for.

---

## 1. Overview

The error tracker watches vacuum error signals in real time and latches them into
per-device state so the learning system can harvest a meaningful error payload at
job-end. It is read by the job finalizer (via an injected accessor — §6.2) and
surfaced through three HA entities that poll it and subscribe to its update
notifications:

- `sensor.<obj>_active_run_error`
- `sensor.<obj>_last_device_error`
- `binary_sensor.<obj>_active_run_has_error` (`is_on` = the active-run latch's
  `error_count > 0`; stays on through `recovered`)

**Invariants:**

- Detect rising and falling error edges across three independent channels at once
  (§5).
- Tolerate firmware timing gaps: some devices flip a status entity to "error" before
  the error-message entity updates, so a grace window defers finalizing a placeholder
  error (§5.5).
- Never lose an error that arrives during a run, even if the descriptive message
  arrives after the error condition has already cleared.
- Carry no brand-specific string or entity-naming convention of its own — every
  sentinel value and entity ID comes from the per-vacuum adapter registry
  (`adapters/registry.py::get_adapter_config`), so a brand that declares nothing gets
  documented, safe defaults rather than a crash.

Two buffers are capped at a module-fixed **50** entries each (not
adapter-configurable, oldest dropped first): the `active_run_error` latch's
`errors[]` list (§3.1) and the `recent_errors` ring (§3.3). Every other tunable
(grace window, sentinel sets, default messages, etc.) is adapter-configurable — full
list with defaults in §7.

---

## 2. Storage & Persistence

All state lives at `manager.data["error_tracker"][<vacuum_entity_id>]`, where
`manager` is the object injected as `runtime_manager` at construction (its `.data`
is a plain dict; it exposes an async `.async_save()`). The per-device record has
exactly three keys:

```
{
    "active_run_error":  {...} | None,   # single latch for the current run, or None
    "last_device_error": {...} | None,   # single most-recent-error dict, or None
    "recent_errors":     [...],          # rolling ring buffer of error dicts, oldest→newest
}
```

`active_run_error` and `last_device_error` are single dicts (or `None`) — never
lists. `recent_errors` is the only list. The record is created lazily (all three
keys defaulted) the first time it's touched, and an existing record missing a key
gets that key backfilled — an old record from an earlier version is upgraded in
place, not replaced.

**Persistence.** Every mutation (rising/falling edge, harvest, commit, acknowledge)
schedules a save of `manager.data["error_tracker"]` via `manager.async_save()`.
Because some callers reach this module from a worker thread (the finalizer's
synchronous path), the save must be scheduled thread-safely onto the event loop
rather than awaited or created directly from off-thread.

**Does NOT survive a restart:** per-vacuum entity-ID lookups, listener
subscriptions, and any pending grace-window timer. A mid-error restart drops the
pending grace window — the secondary channel(s) must still read "error" after
restart for a fresh secondary rising edge to re-arm it.

---

## 3. Record Shapes

### 3.1 `active_run_error` — the run latch

A single dict, or `None`. Formed on the first rising edge observed **while a run is
in flight** — this includes an app-started/external run, not only a run this
integration dispatched (the question is about the robot, not the dispatch queue; use
the shared run-in-flight predicate already defined in `jobs/active_job.py`).
Extended on every subsequent rising edge. Cleared only by a harvest, a commit, or an
acknowledge (§6.2–6.3) — never automatically.

| Field | Type | Description |
|---|---|---|
| `active_job_id` | str \| None | Job ID in flight when the latch first formed. `None` for an app-started run — no job ID exists yet at that point. |
| `first_seen_at` | str | ISO-8601 UTC timestamp of the first rising edge. |
| `last_seen_at` | str | ISO-8601 UTC timestamp of the most recent rising *or* falling edge. |
| `first_seen_job_elapsed_seconds` | int | Seconds into the run when the first error fired. **0** when no run is in flight or the run's start timestamp is missing/unparseable. Clamped `>= 0`. A start timestamp with no timezone is read as UTC (not rejected). |
| `error_count` | int | Number of rising edges folded into this latch — counts *observations*, not distinct faults (§5.1). |
| `current_message` | str | Latest error text; `""` once recovered. |
| `current_code` | int \| str \| None | Latest error's normalized code (§4); `None` once recovered or undeterminable. |
| `errored_room_id` | str \| None | Active job's current room when the first error fired, or `None`. |
| `recovered` | bool | `True` once the error clears while the run is still active. Flips back to `False` on a fresh rising edge. |
| `acknowledged` | bool | Set to `True` only when `acknowledge()` marks (rather than clears) the latch mid-run — §6.3. Not present on a freshly-formed latch. **Write-only**: nothing else in this module or its documented callers reads this flag back — no behavior specified here is conditional on it, and its clearing behavior is unspecified. |
| `errors` | list[dict] | One entry per rising edge, oldest→newest, capped at 50 (§1). |

**Per-edge entry inside `errors[]`:** `message` (str), `code` (int\|str\|None, §4),
`captured_at` (ISO-8601), `job_elapsed_seconds` (int, same clamp/timezone rules as
above), `room_id` (str\|None), `recovered_at` (str\|None — ISO-8601 once this edge
recovers, else `None`).

**Falling-edge behavior** (no-op if no latch exists): sets `current_message = ""`,
`current_code = None`, `recovered = True`, updates `last_seen_at`, and stamps
`recovered_at` on the **single newest entry in `errors[]` that doesn't already have
one** (search newest→oldest, stamp the first unstamped hit, stop). A falling edge
never touches `last_device_error` or `recent_errors`.

### 3.2 `last_device_error` — most recent error

A single dict, or `None`. Overwritten in full on **every** rising edge regardless of
whether a run is in flight — unaffected by falling edges or by any run's
acknowledge/harvest.

Fields: `message` (str), `code` (int\|str\|None, §4), `captured_at` (ISO-8601),
`vacuum_state_at_capture` (str\|None — the vacuum entity's `state` at capture),
`was_during_active_run` (bool), `active_job_id_at_capture` (str\|None).

### 3.3 `recent_errors` — ring buffer

A list, append-only on every rising edge, capped at 50 (oldest dropped first). Never
cleared by acknowledge or harvest — entries only leave by aging out past the cap.

Entry fields: `message` (str), `code` (int\|str\|None, §4), `captured_at`
(ISO-8601), `active_job_id` (str\|None), `vacuum_state` (str\|None).

---

## 4. Error-Code Extraction & Classification

### 4.1 Capturing a code

A **numeric** code is read from `extra_state_attributes` — checking the declared (or
default `("error_code", "code", "errorCode")`) attribute names, in order, first
against the `error_message` entity's attributes, then the vacuum entity's. The first
attribute holding a non-zero int wins; non-int values are skipped. **`0` is treated
as "no code captured"** and normalizes to `None` (every per-model error enum
observed starts its "no error" member at `0`, so a captured `0` reads as
stale/absent rather than real).

Some brands' error-message entity **state itself is the code** (an enum string like
`"bumper_stuck"`) rather than prose. This path activates **only when the adapter
declares it** (`error_tracking.message_is_code: true`) — never sniffed from the
value's shape. When declared, and the numeric-attribute route above yielded nothing,
the message-channel rising edge's `code` becomes the message text, normalized per
§4.2. The attribute route always wins when it finds something.

A rising edge produced by grace-window expiry (§5) always carries `code = None` —
there is no message text to read a code from at that point.

### 4.2 Code normalization

Every raw code — captured live, or read out of an adapter-declared code list — is
normalized to a comparable key before any comparison:

- `bool` → `None` (no code) — `bool` is a subtype of `int` in Python and must not
  collide with integer code `1`/`0`.
- `int` → itself, unchanged.
- `str` → stripped first; if the stripped text parses as an integer, use that
  integer (so a value round-tripped through JSON storage still matches an integer
  table); else, if non-empty, a lowercased, stripped string key. Empty/whitespace →
  `None`.
- Anything else (notably `float`) → `None`. A code is **never** produced by
  truncating a float (`int(3.7) == 3` could silently collide with a real integer
  code).

`None` after normalization means "no code" / "absence," never a code named `""` or
`0`.

### 4.3 Classification seams

Three pure functions of `(vacuum_entity_id, code)` classify a normalized code
against **adapter-declared** tables (§7) — core holds no brand-specific code
knowledge; a brand that declares nothing gets the stated default for every code.
Each declared table accepts both ints and lowercase enum strings, coerced through
§4.2 the same way a captured code is.

| Function | Returns | Reads (in order) | Default |
|---|---|---|---|
| `classify_error_code(vacuum_entity_id, code) -> str` | `"invalidating"` / `"safe"` / `"unclassified"` | `evidence_invalidating_error_codes`, then `evidence_safe_error_codes` | `"unclassified"` (a code with no normalized key also short-circuits here) |
| `error_source_for_code(vacuum_entity_id, code) -> str` | `"dock"` / `"robot"` / `"unknown"` | `dock_sourced_error_codes`, then `robot_sourced_error_codes` | `"unknown"` |
| `error_label_key(vacuum_entity_id, code) -> str \| None` | i18n key, or `None` | `error_label_keys` (`dict`; looked up by both the normalized key and its string form) | `None` |

`classify_error_code`'s result is consumed downstream to decide which error seconds
may be deducted from a completed job's cleaning time; `error_source_for_code` is a
second, independent axis reported alongside it, never used to decide a deduction;
`error_label_key` is resolved fresh on every call, never persisted. **`error_label_key`
returns a declared label only when the adapter's label map stores a non-empty string
for that code; any other stored value — a number, an empty string, a nested
structure — resolves to `None`, exactly as an absent entry does. A label is never
manufactured from a non-conforming entry.**

---

## 5. Error Detection — Channels & Edges, and the Grace Window

Three independent signals are watched simultaneously per vacuum.

### 5.1 Primary channel — `error_message`

The adapter's declared `entities.error_message` entity (skipped entirely if
undeclared — no brand-name guessing fallback).

A **rising edge** fires on **any** state-change whose **new** value looks like an
error — there is no "must differ from the old value" guard, so a repeated error
value (including an attribute-only re-emission that repeats the same state), or a
change from one error string straight to a different one, each count as their own
rising edge. `error_count` counts error **observations**, not not-error→error
**transitions**.

A value "looks like an error" when, stripped and lowercased, it is non-empty and not
in the not-error sentinel set: the adapter's declared `vocabulary.not_error_sentinels`
(each entry stripped/lowercased) when present — **replacing** the default set
entirely, never merging — else the default `{"", "unknown", "unavailable"}`. An
adapter that declares its own vocabulary must re-include the generic HA values
itself if it wants them treated as non-errors.

A **falling edge** fires on a transition **from** an error value **to** a non-error
value (same stripped/lowercased comparison) — see §3.1 for effect.

### 5.2 Secondary channel A — vacuum entity state

The vacuum's own entity. "In error" when its state, stripped/lowercased, equals
exactly `"error"`. **Hardcoded, not adapter-configurable** — Home Assistant's own
vacuum-activity vocabulary, not a brand's.

### 5.3 Secondary channel B — `task_status`

The adapter's declared `entities.task_status` entity, if any (skipped if
undeclared). "In error" when its state, stripped/lowercased, equals the adapter's
declared `error_tracking.task_status_error_value` (default `"error"`) — this
comparison **is** adapter-configurable, and the lowercasing is required (some
firmware reports capitalized `"Error"`).

Combined: the vacuum is "in secondary error" whenever **either** channel currently
reads as an error (OR, not both required).

### 5.4 What a secondary-channel change does

Re-evaluate the combined predicate on every state change of either channel:

- **Entering** secondary error, no grace timer already pending: if the primary
  channel already currently holds an error value, do nothing (it owns latching).
  Otherwise start a grace-window timer — unless the re-arm guard below blocks it. If
  a timer is already pending, re-entering is a no-op.
- **Leaving** secondary error (both channels clear): cancel any pending grace timer.
  Additionally, if there is an unrecovered `active_run_error` latch **and** the
  primary channel does not currently hold an error value, emit a falling edge — the
  only clearing signal for firmware that never populates the primary channel for
  some fault types.

### 5.5 Grace window

Some firmware flips a secondary channel to "error" measurably before the primary
channel updates with real text, so latching is deferred to give the real message a
chance to arrive first.

- Duration: the adapter's declared `error_tracking.grace_window_seconds` if present
  — **including an explicit `0`**, which fires on the very next event-loop tick
  rather than being read as "unset" — else the default **5 seconds**.
- While pending: a real rising edge on the primary channel cancels the timer; no
  placeholder is ever recorded in that case.
- At expiry: re-check the combined secondary predicate — if false, do nothing. If
  still true, re-check the primary channel's current value — if it now holds a real
  error, do nothing (the primary-channel handler already latched it, or will).
  Otherwise, subject to the re-arm guard below, record a rising edge with `message`
  = the adapter's declared (or default) `unknown_error_message` and `code = None`.
- Both the arm-time and expiry-time not-error comparisons use the **adapter's**
  not-error set (§5.1), not the generic default — the generic set would misread a
  brand's own idle value (e.g. `"none"`/`"normal"`) as an error.

**Re-arm guard.** Do **not** start a new grace window if an existing
`active_run_error` latch is unrecovered **and** its `current_message` already
equals the adapter's declared (or default) `unknown_error_message` — i.e. a
placeholder from a previous expiry is still standing. Without this, one sustained
fault that keeps re-writing the secondary channel(s) would re-arm and re-latch on
every write, producing dozens of duplicate placeholder edges for a single physical
fault and flushing real history out of the 50-entry `recent_errors` ring.

---

## 6. Public API

### 6.1 Construction & lifecycle

- `ErrorTracker(hass, *, runtime_manager)` — `runtime_manager` must expose a `.data`
  dict (§2) and an async `.async_save()`.
- `start(vacuum_entity_ids: Iterable[str]) -> None` — wires listeners per vacuum.
  Idempotent per vacuum (re-wiring an already-wired vacuum is a no-op). Never resets
  an existing persisted record.
- `stop() -> None` — unsubscribes every listener and cancels every pending grace
  timer, across all wired vacuums.
- `unregister_vacuum(vacuum_entity_id) -> None` — per-vacuum teardown (listeners +
  grace timer) without affecting other vacuums. **Does not** delete the persisted
  record — that is a separate call the caller makes on its own.

### 6.2 Harvest (job-end)

- `harvest_active_run(vacuum_entity_id, job_id) -> dict | None` — destructive read:
  returns the current `active_run_error` latch and clears it in one step (`None` if
  none). A mismatched `job_id` does **not** suppress the return — the latch comes
  back regardless, since discarding history is worse than misattributing it.
  **Deprecated, zero production callers** — kept only because a legacy test asserts
  this exact semantic; a one-shot destructive read can't be made safe against a
  persistence failure (see below). Do not add new callers.
- `peek_active_run(vacuum_entity_id, job_id) -> dict | None` — non-destructive:
  returns a **deep-copy** snapshot without clearing. Same mismatch tolerance.
- `commit_active_run(vacuum_entity_id, peeked) -> bool` — clears the latch a prior
  `peek_active_run` returned, **only if** the live latch is still the same one:
  identity is `first_seen_at` + `error_count` equality against `peeked`. If the live
  latch moved on (a new edge extended it since the peek), it is left **untouched**
  and this returns `False`; also `False` if `peeked` isn't a dict or no latch
  exists. Returns `True` only when it actually cleared the latch.

Peek+commit exists as a two-step split so a caller can read the latch to build a
durable record, then only destroy the source once that record write has actually
succeeded — a failed write between the two leaves the run's error evidence intact
for a retry. `harvest_active_run` collapses both into one step and loses that
guarantee.

### 6.3 Acknowledge

`acknowledge(vacuum_entity_id, *, scope: str = "both") -> bool` — `scope` is
keyword-only. Returns `True` if a record existed for the vacuum (even if nothing
needed clearing), `False` if no record exists.

| `scope` | Effect |
|---|---|
| `"last_device"` | Clears `last_device_error` to `None`. |
| `"active_run"` | Clears (or **marks**, below) `active_run_error`. |
| `"both"` (default) | Both of the above. |

**Marking instead of clearing, mid-run.** If a run is currently in flight (same
question as §3.1 — includes app-started runs) and a latch exists, the
`"active_run"`/`"both"` scopes do **not** null the latch — instead they set
`acknowledged: True`, `current_message: ""`, `recovered: True`, leaving `errors[]`
and every other field untouched. With no run in flight, the latch clears outright,
exactly as `"last_device"` does for its own field. `recent_errors` is never touched
by `acknowledge` under any scope.

### 6.4 Update listeners

`add_update_listener(cb: Callable[[str], None]) -> Callable[[], None]` — `cb` is
called with the affected `vacuum_entity_id` (one positional string argument, not
zero) whenever that vacuum's latch state changes: rising edge, falling edge,
harvest, commit, or acknowledge. Returns an unsubscribe callable.

### 6.5 Read accessors

- `get_record(vacuum_entity_id) -> dict`, `get_active_run_latch(vacuum_entity_id)
  -> dict | None`, `get_last_device_latch(vacuum_entity_id) -> dict | None`,
  `recent_errors(vacuum_entity_id, *, limit: int | None = None) -> list[dict]`.
- All four create the per-device record with default shape if absent (§2) — none
  raises against a never-touched vacuum.
- `get_record` returns the **live** record dict — not a copy; callers must not
  mutate it.
- `get_active_run_latch` / `get_last_device_latch` each return a **deep copy** (or
  `None`). Must be a true deep copy — a shallow copy still shares the nested
  `errors[]` entries with the live latch, which this module keeps mutating in place
  (e.g. stamping `recovered_at`). A caller's returned snapshot must never change
  under it afterward, and mutating a returned copy must never reach back into the
  tracker's own state.
- `recent_errors` returns a plain list copy, tail-trimmed to the most recent `limit`
  entries when `limit` is a non-negative int (`None`/absent/negative = no trim, all
  entries). `limit = 0` is **not** special-cased and returns **all** entries
  (trimming "the last zero" is a no-op), not an empty list.

---

## 7. Adapter Registry Dependencies

Everything below is read from the per-vacuum adapter config; a missing block or key
**never** raises — each caller applies its own stated default.

| Config path | Used for | Default |
|---|---|---|
| `entities.error_message` | Primary channel entity ID | Channel not wired |
| `entities.task_status` | Secondary channel B entity ID | Channel not wired |
| `vocabulary.not_error_sentinels` | Not-error set — **replaces** the generic default, never merges | `{"", "unknown", "unavailable"}` |
| `error_tracking.unknown_error_message` | Placeholder text on grace expiry | `"Unknown error during run"` |
| `error_tracking.task_status_error_value` | Secondary channel B's error value | `"error"` |
| `error_tracking.grace_window_seconds` | Grace duration (explicit `0` honored) | `5` |
| `error_tracking.error_code_attribute_names` | Ordered attribute names for a numeric code | `("error_code", "code", "errorCode")` |
| `error_tracking.message_is_code` | Whether `error_message`'s state IS the code (§4.1) | `False` |
| `error_tracking.evidence_invalidating_error_codes` | §4.3 evidence table | `[]` |
| `error_tracking.evidence_safe_error_codes` | §4.3 evidence table | `[]` |
| `error_tracking.dock_sourced_error_codes` | §4.3 source table | `[]` |
| `error_tracking.robot_sourced_error_codes` | §4.3 source table | `[]` |
| `error_tracking.error_label_keys` | §4.3 label map | `{}` |

Two comparisons are deliberately **not** adapter-configurable, despite looking like
they could be: the vacuum entity's own `state == "error"` check (§5.2 — HA's
vocabulary, not a brand's), and a declared `grace_window_seconds` of `0`, which is
honored as a real, very-short window rather than read as "not set" (§5.5).

---

## 8. Integration Points

| Caller | Calls | When |
|---|---|---|
| Integration setup | `ErrorTracker(hass, runtime_manager=manager)` then `.start(vacuum_entity_ids)` | Integration load |
| Integration unload | `.stop()` | Integration unload |
| Device removal | `.unregister_vacuum(vacuum_entity_id)` (+ a separate persisted-record removal) | A managed vacuum's device is deleted |
| Job finalization | Two injected closures: one calls `peek_active_run(vacuum_entity_id, job_id)` before the completed-job record is built; the other calls `commit_active_run(vacuum_entity_id, peeked)` only after that record is durably saved | Every job finalize |
| Error sensor entities | `get_active_run_latch(...)`, `get_last_device_latch(...)` | Entity state read |
| Error binary-sensor entity | `get_active_run_latch(...)` (`is_on` = `error_count > 0`, sticky through `recovered`) | Entity state read |
| Acknowledge service | `acknowledge(vacuum_entity_id, scope=...)` | User/service action |
| Recent-errors query service | `recent_errors(vacuum_entity_id, limit=...)` | User/service action |
| Classification call sites | `classify_error_code(...)`, `error_source_for_code(...)`, `error_label_key(...)` — free functions, no instance needed | Per stored error code, on demand |
