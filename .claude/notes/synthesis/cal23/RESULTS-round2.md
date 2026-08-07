# CAL-23 round 2 — examination results

Subjects:
- `sandbox-b2a/custom_components/eufy_vacuum/core/error_tracker.py` (787 lines)
- `sandbox-b2b/custom_components/eufy_vacuum/core/error_tracker.py` (828 lines)

Ground truth: `C:\Users\CKing\Documents\GITHUB\eufy-vacuum-manager\custom_components\eufy_vacuum\core\error_tracker.py`

## 0. Apparatus derivation (re-verified, not assumed)

**Behavioral subset.** Rederived by script against
`tests/integration/test_core_error_tracker.py` at repo HEAD (43 test
functions), applying the stated rule — a test is behavioral iff its body
never matches `\.\s*_[a-z]`. Result: **8 behavioral / 35 quarantined**,
identical to the set listed in the round-1 `RESULTS.md`:

1. `test_ensure_record_and_recent_limit`
2. `test_wired_event_routing`
3. `test_error_source_for_code_reads_the_adapter_tables`
4. `test_error_source_for_code_undeclared_brand_reports_unknown`
5. `test_enum_string_codes_classify_for_a_string_code_brand`
6. `test_string_codes_are_matched_case_insensitively_and_trimmed`
7. `test_an_undeclared_string_code_still_degrades_safely`
8. `test_int_guards_survive_the_string_support`

**Retired pins.** Per `REVIEW.md` (Opus adjudication), 3 of the 12 certified
pins carry a **C** verdict (detected the divergence but asserted a
non-contract — no consumer, no invariant, no stated design) and are
excluded from round 2:

- `test_pin_acknowledged_does_not_hide_a_fresh_rising_edge` (RED-1, C)
- `test_pin_negative_grace_window_seconds_fires_almost_immediately` (RED-2, C)
- `test_pin_primary_channel_message_text_is_captured_verbatim` (RED-4, C)

`test_pin_error_label_key_requires_a_real_non_empty_string_value` (RED-3)
carries a **D** verdict (NEVER-PRESENT provenance — a real, newly-earned
invariant) and is **retained** as the headline pin. Surviving set: **9 of
12** pins.

## 1. Method

Per subject: copied `runner-original/` (tests/ + custom_components/ from the
repo, already proven correct against the original — 49 passed in round 1),
overlaid the subject's `core/error_tracker.py`, kept
`tests/integration/pins/test_cal23_pins.py` as-is (identical to
`pins/test_cal23_pins.py` in this workspace), cleared stale
`__pycache__`, ran in the certified docker image:

```
docker run --rm -v "<scratch>:/workspace" -w /workspace eufy-vacuum-test \
  pytest tests/integration/test_core_error_tracker.py -k "<8 behavioral names>" --no-cov -v

docker run --rm -v "<scratch>:/workspace" -w /workspace eufy-vacuum-test \
  pytest tests/integration/pins/test_cal23_pins.py -k "not <3 retired pin names>" --no-cov -v
```

Scratch dirs: `round2-b2a/`, `round2-b2b/` (this workspace).

## 2. Results — sandbox-b2a (787 lines)

**Behavioral subset: 8/8 PASS.**

```
test_ensure_record_and_recent_limit PASSED
test_wired_event_routing PASSED
test_error_source_for_code_reads_the_adapter_tables PASSED
test_error_source_for_code_undeclared_brand_reports_unknown PASSED
test_enum_string_codes_classify_for_a_string_code_brand PASSED
test_string_codes_are_matched_case_insensitively_and_trimmed PASSED
test_an_undeclared_string_code_still_degrades_safely PASSED
test_int_guards_survive_the_string_support PASSED
======================= 8 passed, 41 deselected in 1.64s =======================
```

**Surviving pins: 9/9 PASS.** RED-3 pin
(`test_pin_error_label_key_requires_a_real_non_empty_string_value`): **PASS.**

```
test_pin_zero_valued_attribute_does_not_stop_the_code_scan PASSED
test_pin_zero_valued_entity_does_not_stop_the_code_scan PASSED
test_pin_primary_edge_arriving_after_secondary_cancels_the_grace_window PASSED
test_pin_explicit_zero_grace_window_is_honored_not_treated_as_unset PASSED
test_pin_error_label_key_requires_a_real_non_empty_string_value PASSED
test_pin_commit_active_run_refuses_a_stale_peek PASSED
test_pin_harvest_active_run_ignores_a_job_id_mismatch PASSED
test_pin_update_listener_fires_for_every_mutation_kind PASSED
test_pin_read_accessors_never_schedule_a_save PASSED
======================= 9 passed, 3 deselected in 2.58s ========================
```

No reds. Confirmed by inspection: `error_label_key` (line 157) explicitly
resolves any declared value that "isn't a non-empty string (a number, "",
a nested structure)" to `None` — the RED-3 invariant is implemented, not an
accidental pass.

## 3. Results — sandbox-b2b (828 lines)

**Behavioral subset: 8/8 PASS.**

```
test_ensure_record_and_recent_limit PASSED
test_wired_event_routing PASSED
test_error_source_for_code_reads_the_adapter_tables PASSED
test_error_source_for_code_undeclared_brand_reports_unknown PASSED
test_enum_string_codes_classify_for_a_string_code_brand PASSED
test_string_codes_are_matched_case_insensitively_and_trimmed PASSED
test_an_undeclared_string_code_still_degrades_safely PASSED
test_int_guards_survive_the_string_support PASSED
======================= 8 passed, 41 deselected in 1.54s =======================
```

**Surviving pins: 9/9 PASS.** RED-3 pin
(`test_pin_error_label_key_requires_a_real_non_empty_string_value`): **PASS.**

```
test_pin_zero_valued_attribute_does_not_stop_the_code_scan PASSED
test_pin_zero_valued_entity_does_not_stop_the_code_scan PASSED
test_pin_primary_edge_arriving_after_secondary_cancels_the_grace_window PASSED
test_pin_explicit_zero_grace_window_is_honored_not_treated_as_unset PASSED
test_pin_error_label_key_requires_a_real_non_empty_string_value PASSED
test_pin_commit_active_run_refuses_a_stale_peek PASSED
test_pin_harvest_active_run_ignores_a_job_id_mismatch PASSED
test_pin_update_listener_fires_for_every_mutation_kind PASSED
test_pin_read_accessors_never_schedule_a_save PASSED
======================= 9 passed, 3 deselected in 2.50s ========================
```

No reds. Confirmed by inspection: `error_label_key` (line 142) checks
`isinstance(table, dict)` and requires a non-empty-string declared value,
resolving anything else (including a coerced int/empty string) to `None`.

## 4. Summary

| Subject | Behavioral 8 | Pins 9 (RED-3 retained) | RED-3 pin | Reds |
|---|---|---|---|---|
| sandbox-b2a (787 lines) | 8/8 PASS | 9/9 PASS | PASS | none |
| sandbox-b2b (828 lines) | 8/8 PASS | 9/9 PASS | PASS | none |

Both round-2 reconstructions clear the full apparatus with zero reds,
including the retained headline pin (RED-3, `error_label_key` value-type
discipline) that failed round 1's build.
