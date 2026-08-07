# CAL-23 pin certification log

Every pin below was (i) run against the **original** `core/error_tracker.py`
(`custom_components/eufy_vacuum/core/error_tracker.py` in
`C:\Users\CKing\Documents\GITHUB\eufy-vacuum-manager`) and PASSED, then (ii)
run against a hand-built mutant of that same original file and FAILED. All
mutants are one-line-or-so behavioral changes to the original, never to the
pins. No pin was discarded — all 12 bit cleanly on the first correctly-scoped
mutant (PIN 3, PIN 11 needed a redesign after their first mutant attempt did
not bite — see notes below).

Runner used for every row: `docker run --rm -v "<dir>:/workspace" -w
/workspace eufy-vacuum-test pytest tests/integration/pins/test_cal23_pins.py
--no-cov -q`, `<dir>` = a fresh copy of `tests/` + `custom_components/` from
the repo with the named mutation applied to `core/error_tracker.py` only.

| # | Pin | Guarded behavior | Mutant (one-line description) | original | mutant |
|---|-----|-------------------|--------------------------------|----------|--------|
| 1 | `test_pin_acknowledged_does_not_hide_a_fresh_rising_edge` | `acknowledged: True` set by `acknowledge()` mid-run survives a later fresh rising edge on the same latch (never popped) | `m1_ack`: add `latch.pop("acknowledged", None)` to the latch-extend branch of `_record_rising_edge` | PASS | FAIL |
| 2a | `test_pin_zero_valued_attribute_does_not_stop_the_code_scan` | A captured `0` on an earlier declared attribute name is skipped, not a scan-stopper — the scan continues to the next declared name on the same entity | `m2_zeroscan`: in `_read_error_code_attr`, `return None` immediately the first time a declared attribute yields `0` instead of continuing the loop | PASS | FAIL |
| 2b | `test_pin_zero_valued_entity_does_not_stop_the_code_scan` | Same guarded behavior, cross-entity: a `0` on the `error_message` entity does not stop the scan before it reaches the vacuum entity's own attributes | `m2_zeroscan` (same mutant — stops the scan unconditionally on any zero, so it breaks both the same-entity and cross-entity case in one shot) | PASS | FAIL |
| 3 | `test_pin_primary_edge_arriving_after_secondary_cancels_the_grace_window` | A real rising edge on the primary channel cancels a pending grace timer; a fresh error that then recovers before the window elapses does not later get a stray placeholder edge appended | `m3_gracecancel`: remove the `self._cancel_grace(vacuum_entity_id)` call from `_handle_error_message_change`'s rising-edge branch | PASS | FAIL |
| 4 | `test_pin_negative_grace_window_seconds_fires_almost_immediately` | A declared negative `grace_window_seconds` is clamped to the scheduling floor (fires almost immediately), not to the 5s default | `m4_neggrace`: clamp `_grace_s < 0` to `_ERROR_MESSAGE_GRACE_SECONDS` (5) instead of leaving it for the existing `max(0.0, _grace_s)` floor | PASS | FAIL |
| 5 | `test_pin_explicit_zero_grace_window_is_honored_not_treated_as_unset` | An explicit `grace_window_seconds: 0` is honored as a real (near-zero) window, not read as "unset" | `m5_zerograce`: change `float(_declared) if _declared is not None else DEFAULT` to `float(_declared) if _declared else DEFAULT` (truthiness instead of `is not None`) | PASS | FAIL |
| 6 | `test_pin_error_label_key_requires_a_real_non_empty_string_value` | `error_label_key` only ever returns a value that was ALREADY a non-empty string in the declared map — it never coerces an int / empty-string value into a fake key | `m6_labelkey`: change `return value if isinstance(value, str) and value else None` to `return str(value) if value is not None else None` | PASS | FAIL |
| 7 | `test_pin_primary_channel_message_text_is_captured_verbatim` | `current_message` / `last_device_error.message` store the primary channel's raw state text verbatim (stripping is only for the internal "looks like an error" comparison, never for the stored value) | `m7_msgws`: change `message=str(new_state)` to `message=str(new_state).strip()` in `_handle_error_message_change`'s rising-edge branch | PASS | FAIL |
| 8 | `test_pin_commit_active_run_refuses_a_stale_peek` | `commit_active_run` only clears the latch if it is still identity-equal (`first_seen_at` + `error_count`) to what was peeked; a latch that moved on is left untouched and `False` is returned | `m8_commit`: delete the `moved_on` identity check in `commit_active_run` so it always clears | PASS | FAIL |
| 9 | `test_pin_harvest_active_run_ignores_a_job_id_mismatch` | `harvest_active_run` returns (and clears) the latch even when the passed `job_id` doesn't match `active_job_id` | `m9_harvest`: `return None` on a `job_id` mismatch instead of falling through to return the latch | PASS | FAIL |
| 10 | `test_pin_update_listener_fires_for_every_mutation_kind` | `add_update_listener`'s callback fires on every mutation kind, including `acknowledge` | `m10_listener`: in `acknowledge()`, replace the closing `self._persist_and_notify(...)` with a save-only call that never invokes `self._notify(...)` | PASS | FAIL |
| 11 | `test_pin_read_accessors_never_schedule_a_save` | `get_record` (and the other three read accessors, which route through it) never schedules `manager.async_save()` merely from creating/backfilling a record | `m11_readsave`: add a `call_soon_threadsafe(..., manager.async_save())` call inside `get_record` | PASS | FAIL |

## Notes on pins that needed a redesign before they bit

- **PIN 3** (same-tick ordering / low-confidence #3): the first design only
  checked that the real message "won" and that `error_count` stayed at 1
  immediately and after the grace window elapsed. Removing the
  `_cancel_grace` call in the `m3_gracecancel` mutant did **not** break that
  version, because DR §5.5's *separate*, redundant expiry-time recheck ("if
  it now holds a real error, do nothing") independently suppressed the
  placeholder as long as the primary channel was *still* showing the real
  error at expiry time — so an uncancelled-but-otherwise-harmless timer was
  unobservable. The pin was redesigned to have the message **recover**
  (go back to a non-error value) before the grace window elapses, while the
  vacuum entity stays in "error" — that removes the redundant guard's cover
  and isolates the cancel-on-arrival behavior specifically. Re-run against
  `m3_gracecancel` after the redesign: FAIL, as required.

- **PIN 11** (`Doc was silent #8` — read accessors never schedule a save):
  the first version was a plain (non-`async`) test that called the accessors
  and immediately asserted `mgr.async_save.assert_not_awaited()`. The
  `m11_readsave` mutant schedules the save via `call_soon_threadsafe` +
  `async_create_task` (the same fire-and-forget mechanism the real
  mutation-worthy code paths use), which only actually runs once the event
  loop gets a chance to turn — a synchronous test that never awaits
  anything never gives it that chance, so the mutant's extra save call was
  silently never observed and the pin passed against both the original
  *and* the mutant (a false negative). The pin was made `async` and now
  calls `await hass.async_block_till_done()` after the accessor calls,
  before asserting. Re-run against `m11_readsave` after the fix: FAIL, as
  required.

## Result

12/12 pins certified. 0 discarded.
