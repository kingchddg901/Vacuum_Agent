# CAL-23 — blind-reconstruction test results

Subject: `sandbox-b1/custom_components/eufy_vacuum/core/error_tracker.py`
(867 lines), reconstructed from `sandbox-b1/DR-SECTION.md` ("23 — Error
Tracker"). Builder's own gap log: `sandbox-b1/RECONSTRUCTION-NOTES.md` (12
doc-gap decisions, 3 declared low-confidence areas).

Ground truth for pin authoring / mutation certification throughout:
`C:\Users\CKing\Documents\GITHUB\eufy-vacuum-manager\custom_components\eufy_vacuum\core\error_tracker.py`
(the real, original implementation).

---

## 1. Runner proof

Scratch dirs (all under this workspace):
- `runner-original/` — `tests/` + `custom_components/` copied verbatim from
  the repo.
- `runner-recon/` — same, with `core/error_tracker.py` overlaid by the
  sandbox reconstruction.
- `mut-*/` — eleven single-mutation copies of `runner-original`, one per
  certified pin's guarded behavior (see `pins/CERTIFICATION-LOG.md`).

Command: `docker run --rm -v "<dir>:/workspace" -w /workspace
eufy-vacuum-test pytest tests/integration/test_core_error_tracker.py
--no-cov -q`

| Target | Result |
|---|---|
| Full legacy suite vs. **original** | `49 passed in 8.98s` — runner proven correct before touching the reconstruction. (43 test *functions*; 49 test *items* because `test_is_error_value` is `@pytest.mark.parametrize`d ×7.) |
| Full legacy suite vs. **reconstruction** | `40 failed, 9 passed in 9.80s` |

## 2. Behavioral-subset derivation

Ruling: a test counts as behavioral iff its body never matches
`\.\s*_[a-z]` (a `.` — a private/dunder-style attribute or method access,
optionally through whitespace — followed by a lowercase letter). Applied by
hand to each of the 43 test functions in
`tests/integration/test_core_error_tracker.py`:

- **35 quarantined** (touch a `._name` on the tracker, or call a `._`-prefixed
  module function like `et._is_error_value`, `et._job_elapsed_seconds`,
  `et._get_not_error_set`). This matches the stated 81% (35/43) white-box
  ratio.
  - One quarantined test (`test_job_finished_without_a_record_does_not_clear_the_latch`,
    via `et._ensure_record(...)`) happens to also PASS against the
    reconstruction, but per the ruling it is not evidence either way — it is
    excluded from the behavioral count regardless of its pass/fail status.
- **8 behavioral** (public surface only — `get_record`, `recent_errors`,
  `start`/`stop`, and the free functions `classify_error_code` /
  `error_source_for_code` / `error_label_key` accessed without a leading
  underscore):
  1. `test_ensure_record_and_recent_limit`
  2. `test_wired_event_routing`
  3. `test_error_source_for_code_reads_the_adapter_tables`
  4. `test_error_source_for_code_undeclared_brand_reports_unknown`
  5. `test_enum_string_codes_classify_for_a_string_code_brand`
  6. `test_string_codes_are_matched_case_insensitively_and_trimmed`
  7. `test_an_undeclared_string_code_still_degrades_safely`
  8. `test_int_guards_survive_the_string_support`

### Behavioral-subset result vs. reconstruction

All 8/8 **PASS**. (Verified via `pytest tests/integration/test_core_error_tracker.py
--no-cov -v` against `runner-recon/`; these 8 names are exactly 8 of the 9
`PASSED` lines in the full-suite run, the 9th being the quarantined
`test_job_finished_without_a_record_does_not_clear_the_latch` noted above.)

The legacy suite's behavioral subset gives the reconstruction a clean bill
of health — it is far too small and far too general (module defaults,
enum-code plumbing, one fully-wired happy path) to touch any of the
declared low-confidence areas or most of the DR's central contracts. That
gap is what the new pins in §3 exist to close.

## 3. New pins

Authored: **12** (targeting the 3 declared low-confidence areas plus DR
central public-surface contracts). Certified: **12/12** (0 discarded — every
pin passed against the original and was made to fail against a
purpose-built mutant of the original; see `pins/CERTIFICATION-LOG.md` for
the full guarded-behavior / mutant / pass-fail table, including two pins
that needed a redesign before their first mutant attempt actually bit).

File: `pins/test_cal23_pins.py`. No `._name` access on the tracker anywhere
in the file — every pin drives `ErrorTracker` through its constructor,
`start`/`stop`, `harvest_active_run`/`peek_active_run`/`commit_active_run`,
`acknowledge`, `add_update_listener`, the four `get_*`/`recent_errors`
accessors, the three free classification functions, and
`hass.states.async_set`/`async_fire_time_changed` for wiring and timing.

## 4. Pin results vs. reconstruction (verdict run)

Command: `docker run --rm -v "<runner-recon>:/workspace" -w /workspace
eufy-vacuum-test pytest tests/integration/pins/test_cal23_pins.py --no-cov -v`

**Result: 8 passed, 4 failed.**

| Pin | vs. reconstruction |
|---|---|
| `test_pin_acknowledged_does_not_hide_a_fresh_rising_edge` | **RED** |
| `test_pin_zero_valued_attribute_does_not_stop_the_code_scan` | green |
| `test_pin_zero_valued_entity_does_not_stop_the_code_scan` | green |
| `test_pin_primary_edge_arriving_after_secondary_cancels_the_grace_window` | green |
| `test_pin_negative_grace_window_seconds_fires_almost_immediately` | **RED** |
| `test_pin_explicit_zero_grace_window_is_honored_not_treated_as_unset` | green |
| `test_pin_error_label_key_requires_a_real_non_empty_string_value` | **RED** |
| `test_pin_primary_channel_message_text_is_captured_verbatim` | **RED** |
| `test_pin_commit_active_run_refuses_a_stale_peek` | green |
| `test_pin_harvest_active_run_ignores_a_job_id_mismatch` | green |
| `test_pin_update_listener_fires_for_every_mutation_kind` | green |
| `test_pin_read_accessors_never_schedule_a_save` | green |

Of the 3 declared low-confidence areas: **1 of 3 is a real behavioral
divergence** (acknowledged-flag lifecycle). The other two — zero-value
code-scan continuation, and same-tick primary/secondary ordering — turn out
to be correctly reconstructed; the builder's stated uncertainty there did
not translate into an actual bug.

## 5. Red analysis

### RED 1 — `test_pin_acknowledged_does_not_hide_a_fresh_rising_edge`

**Failing contract.** After `acknowledge(scope="active_run")` marks an
in-flight latch (`acknowledged: True`), a subsequent fresh rising edge on
the *same* latch must leave `acknowledged` as `True` — the original never
touches that key while extending a latch.

**What the reconstruction did instead.** `_record_rising_edge` explicitly
runs `latch.pop("acknowledged", None)` on every rising edge that extends an
existing latch (`core/error_tracker.py:629` in the reconstruction), so the
flag is silently cleared/absent after the very next fault.

**Does the DR section state the required behavior?** **NO — silent.** DR
§3.1's `acknowledged` row only says: *"Present and `True` only after
`acknowledge()` marks (rather than clears) the latch mid-run — §6.3. Absent
otherwise."* It says nothing about what a later rising edge does to an
already-`True` flag. The reconstruction's own `RECONSTRUCTION-NOTES.md`
flags this exact gap as *"the single riskiest guess in the file"* (low-confidence
#1) and states the chosen (and, per this pin, incorrect relative to the
original) behavior explicitly: *"I clear it (`latch.pop("acknowledged",
None)`) on every rising edge."*

### RED 2 — `test_pin_negative_grace_window_seconds_fires_almost_immediately`

**Failing contract.** A declared negative `error_tracking.grace_window_seconds`
must be clamped to the scheduling primitive's floor (fires on the very next
tick, same order of magnitude as an explicit `0`) — not to the 5s default.

**What the reconstruction did instead.** `_start_grace_timer` explicitly
clamps `seconds < 0` to `_DEFAULT_GRACE_WINDOW_SECONDS` (5) — so a
negative-window brand's placeholder edge is delayed by a full 5 seconds
relative to the original.

**Does the DR section state the required behavior?** **NO — silent.** DR
§5.5 and §7 both cover an explicit `0` ("fires on the very next event-loop
tick rather than being read as 'unset'") and the "not declared" case
(default 5s), but neither sentence addresses a declared *negative* number.
`RECONSTRUCTION-NOTES.md` "Doc was silent" #3 names exactly this gap and
states the builder's (here, wrong-relative-to-original) choice: *"I clamp
it to the default (5s) rather than schedule a timer that would fire in the
past."*

### RED 3 — `test_pin_error_label_key_requires_a_real_non_empty_string_value`

**Failing contract.** `error_label_key` must only ever return a value that
was *already* a non-empty string in the adapter's declared
`error_label_keys` map — an int value (e.g. `12345`) or an empty-string
value must resolve to `None`, the same as no entry at all.

**What the reconstruction did instead.** `error_label_key` does `return
str(value) if value is not None else None` — it coerces *any* non-`None`
value into a string, so a malformed `{70: 12345}` entry now resolves to the
fabricated label `"12345"`, and `{71: ""}` resolves to `""` instead of
`None`.

**Does the DR section state the required behavior?** **AMBIGUOUS /
effectively silent.** DR §4.3's `error_label_key` row only documents the
*key*-lookup rule ("looked up by both the normalized key and its string
form"); it says nothing at all about validating the *value*. This gap is
**not** among `RECONSTRUCTION-NOTES.md`'s 12 listed decisions or 3
low-confidence areas — it was found independently by diffing the
reconstruction against the original's source, not flagged by the builder.

### RED 4 — `test_pin_primary_channel_message_text_is_captured_verbatim`

**Failing contract.** `current_message` (and `last_device_error.message`)
must store the primary channel's raw state text verbatim. Stripping is
scoped to the internal "looks like an error" comparison only, never to the
value that gets persisted.

**What the reconstruction did instead.** `_handle_primary_change` does
`message = str(new_state.state).strip() if new_state is not None else ""`
— it strips the text before ever storing it, so a firmware value like
`"  Stuck in dock  "` is persisted as `"Stuck in dock"` instead of
verbatim.

**Does the DR section state the required behavior?** **NO — silent, and
also not one of the 12 declared decisions.** DR §3.1 documents
`current_message` only as *"Latest error text; `""` once recovered"* with
no normalization clause. DR §5.1's stripped/lowercased rule is explicitly
scoped to detection: *"A value 'looks like an error' when, stripped and
lowercased, it is non-empty and not in the not-error sentinel set..."* —
that sentence never claims the stored value itself is affected. Like RED 3,
this was found by diffing implementations, not flagged in
`RECONSTRUCTION-NOTES.md`.
