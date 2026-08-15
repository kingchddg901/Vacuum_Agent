<!-- GENERATED FILE — DO NOT EDIT BY HAND.
     Source of truth: every hass.bus.async_fire() call site in
     custom_components/eufy_vacuum/, the EVENT_* constants they name
     (f-strings resolved), and the payload builders those call sites reach.
     Regenerate after adding, removing or repayloading an event:
       python scripts/gen_event_docs.py -->

# Event Reference

> Generated reference — the facts. The *reasons* live in the prose docs: [Events](../../advanced/02-events.md) for automation authors, [HA Integration](../02-ha-integration.md) §7 and [Job Lifecycle](../06-job-lifecycle.md) §10 for why each one exists. Regenerate with `python scripts/gen_event_docs.py`; CI fails if this file is not what the generator emits.

The integration fires **11 events** on `hass.bus` from **26 call sites**, carrying **92 payload key slots** (54 distinct key names). Every event name below was resolved from the constant that names it, not read as a literal.

Listen with the `event` trigger platform; every payload is a plain dict.

`Payload` is derived, not declared: an event whose every key is an identifier (`vacuum_entity_id`, `map_id`, `job_id`) tells a consumer only THAT something happened and must be followed by a state-inspection service call; the rest carry the state in the event itself. Home Assistant's event bus has no `supports_response` — this is the nearest fact a caller actually needs, and it is computed from the resolved payload.

| Event | Constant | Fire sites | Keys | Payload |
|---|---|---|---|---|
| [`eufy_vacuum_external_run_pending`](#eufy_vacuum_external_run_pending) | `EVENT_EXTERNAL_RUN_PENDING` | 1 | 5 | carries state |
| [`eufy_vacuum_job_finished`](#eufy_vacuum_job_finished) | `EVENT_JOB_FINISHED` | 6 | 11 | carries state |
| [`eufy_vacuum_job_progress_tick`](#eufy_vacuum_job_progress_tick) | `EVENT_JOB_PROGRESS_TICK` | 1 | 2 | identity only — pull signal |
| [`eufy_vacuum_path_blocked`](#eufy_vacuum_path_blocked) | `EVENT_PATH_BLOCKED` | 2 | 18 | carries state |
| [`eufy_vacuum_room_completed`](#eufy_vacuum_room_completed) | `EVENT_ROOM_COMPLETED` | 1 | 7 | carries state |
| [`eufy_vacuum_room_finished`](#eufy_vacuum_room_finished) | `EVENT_ROOM_FINISHED` | 2 | 10 | carries state |
| [`eufy_vacuum_room_skipped`](#eufy_vacuum_room_skipped) | `EVENT_ROOM_SKIPPED` | 1 | 6 | carries state |
| [`eufy_vacuum_room_started`](#eufy_vacuum_room_started) | `EVENT_ROOM_STARTED` | 3 | 8 | carries state |
| [`eufy_vacuum_run_incomplete`](#eufy_vacuum_run_incomplete) | `EVENT_RUN_INCOMPLETE` | 5 | 5 | carries state |
| [`eufy_vacuum_stall_captured`](#eufy_vacuum_stall_captured) | `EVENT_STALL_CAPTURED` | 1 | 6 | carries state |
| [`eufy_vacuum_stall_detected`](#eufy_vacuum_stall_detected) | `EVENT_STALL_DETECTED` | 3 | 14 | carries state |

An `EVENT_*` constant that nothing fires is listed here rather than above — the name exists, the event does not:

| Constant | Defined | Value |
|---|---|---|
| `EVENT_BOUNDARY_SAVED` | `custom_components/eufy_vacuum/mapping/tracker.py:41` | `eufy_vacuum_boundary_saved` |

---

## eufy_vacuum_external_run_pending

Constant: `EVENT_EXTERNAL_RUN_PENDING` — `custom_components/eufy_vacuum/const.py:291`, f-string `f'{DOMAIN}_external_run_pending'`

Fired from 1 call site(s) in 1 module(s): `custom_components/eufy_vacuum/learning/external_run.py`

### Payload

| Key | Present | Value expression |
|---|---|---|
| `detection_ts` | every site | `detection_ts` |
| `map_id` | every site | `str(map_id)` |
| `record_path` | every site | `result['path']` |
| `segment_count` | every site | `result['segment_count']` |
| `vacuum_entity_id` | every site | `vacuum_entity_id` |

### Fire sites

| Location | Enclosing | Payload built by | Nearest guards |
|---|---|---|---|
| `custom_components/eufy_vacuum/learning/external_run.py:457` | `ExternalRunManager._finalize_external_run` | dict literal at the call site | `result is not None` |

## eufy_vacuum_job_finished

Constant: `EVENT_JOB_FINISHED` — `custom_components/eufy_vacuum/const.py:282`, f-string `f'{DOMAIN}_job_finished'`

Fired from 6 call site(s) in 5 module(s): `custom_components/eufy_vacuum/learning/services.py`, `custom_components/eufy_vacuum/listeners/lifecycle.py`, `custom_components/eufy_vacuum/listeners/path_blockers.py`, `custom_components/eufy_vacuum/listeners/pause_timeout.py`, `custom_components/eufy_vacuum/services/job_control.py`

### Payload

| Key | Present | Value expression |
|---|---|---|
| `actual_cleaning_minutes` | 5 of 6 sites | `job_info.get('actual_cleaning_minutes')` |
| `duration_minutes` | 5 of 6 sites | `job_info.get('duration_minutes')` |
| `finalized_at` | every site | `result.get('completed_job', {}).get('finalized_at')` · `completed_job.get('finalized_at')` |
| `job_id` | every site | `result.get('job_id')` · `finalize_result.get('job_id')` · `result.get('job_id') or result.get('finalize_result', {}).get('job_id')` |
| `job_path` | every site | `result.get('job_path')` · `finalize_result.get('job_path')` · `job_path` |
| `map_id` | every site | `str(call.data['map_id'])` · `str(map_id)` |
| `reason_detail` | every site | `outcome.get('lifecycle_message')` · `outcome.get('lifecycle_message') or outcome.get('status')` |
| `room_count` | every site | `result.get('completed_job', {}).get('job', {}).get('room_count')` · `job_info.get('room_count')` |
| `status` | every site | `status` · `outcome.get('status', 'completed')` |
| `used_for_learning` | every site | `outcome.get('used_for_learning')` |
| `vacuum_entity_id` | every site | `call.data['vacuum_entity_id']` · `vacuum_entity_id` |

Where a key lists more than one expression, the fire sites build it differently. That is how the value is OBTAINED, not a claim that the resulting values differ — types are not inferred.

### Fire sites

| Location | Enclosing | Payload built by | Nearest guards |
|---|---|---|---|
| `custom_components/eufy_vacuum/learning/services.py:471` | `handle_finalize_learning_job` | dict literal at the call site | — |
| `custom_components/eufy_vacuum/listeners/lifecycle.py:463` | `_process` | builder `job_finished_event_data()` | `finalize_result_succeeded(finalize_result)` |
| `custom_components/eufy_vacuum/listeners/path_blockers.py:208` | `_process` | builder `job_finished_event_data()` | `path_block_action == 'cancel_and_event'` ⟶ `bool((action_result or {}).get('cancelled'))` |
| `custom_components/eufy_vacuum/listeners/pause_timeout.py:125` | `_reap_one_slot` | builder `job_finished_event_data()` | `isinstance(timeout_report, dict)` ⟶ `bool(result.get('cancelled'))` |
| `custom_components/eufy_vacuum/listeners/pause_timeout.py:164` | `_reap_one_slot` | builder `job_finished_event_data()` | `isinstance(stranded_report, dict)` ⟶ `bool(result.get('finalized'))` |
| `custom_components/eufy_vacuum/services/job_control.py:265` | `_handle_cancel_active_job` | builder `job_finished_event_payload()` | `payload.get('cancelled')` |

## eufy_vacuum_job_progress_tick

Constant: `EVENT_JOB_PROGRESS_TICK` — `custom_components/eufy_vacuum/const.py:299`, f-string `f'{DOMAIN}_job_progress_tick'`

Fired from 1 call site(s) in 1 module(s): `custom_components/eufy_vacuum/listeners/job_progress.py`

### Payload

| Key | Present | Value expression |
|---|---|---|
| `map_id` | every site | `map_id_str` |
| `vacuum_entity_id` | every site | `vacuum_entity_id` |

### Fire sites

| Location | Enclosing | Payload built by | Nearest guards |
|---|---|---|---|
| `custom_components/eufy_vacuum/listeners/job_progress.py:151` | `_handle_job_progress_tick` | dict literal at the call site | — |

## eufy_vacuum_path_blocked

Constant: `EVENT_PATH_BLOCKED` — `custom_components/eufy_vacuum/const.py:285`, f-string `f'{DOMAIN}_path_blocked'`

Fired from 2 call site(s) in 1 module(s): `custom_components/eufy_vacuum/listeners/path_blockers.py`

### Payload

| Key | Present | Value expression |
|---|---|---|
| `action_result` | conditional | `action_result` |
| `action_taken` | every site | `action_taken` · `'cancel_suppressed_recheck'` |
| `affected_remaining_room_ids` | every site | `[str(item['room_id']) for item in affected_remaining_rooms]` |
| `affected_remaining_room_names` | every site | `[str(item.get('name') or f"Room {item['room_id']}") for item in affected_remaining_rooms]` |
| `affected_rooms` | every site | `affected_remaining_rooms` |
| `directly_blocked_room_ids` | every site | `[str(room_id) for room_id in directly_blocked_remaining_room_ids]` |
| `event_scope` | every site | `'active_job_path_blocked'` |
| `indeterminate_rules` | every site | `indeterminate_rules` |
| `indirectly_blocked_room_ids` | every site | `[str(room_id) for room_id in indirectly_blocked_remaining_room_ids]` |
| `job_id` | every site | `active_job.get('job_id')` |
| `map_id` | every site | `str(map_id)` |
| `path_block_action` | every site | `path_block_action` |
| `reason_codes` | every site | `sorted({str(item.get('reason') or '').strip() for item in affected_remaining_rooms if str(item.get('reason') or '').strip()})` |
| `remaining_room_ids` | every site | `[str(room_id) for room_id in remaining_room_ids]` |
| `requires_attention` | every site | `True` |
| `trigger_entity_id` | every site | `trigger_entity_id` |
| `trigger_entity_state` | every site | `trigger_entity_state` |
| `vacuum_entity_id` | every site | `vacuum_entity_id` |

Where a key lists more than one expression, the fire sites build it differently. That is how the value is OBTAINED, not a claim that the resulting values differ — types are not inferred.

### Fire sites

| Location | Enclosing | Payload built by | Nearest guards |
|---|---|---|---|
| `custom_components/eufy_vacuum/listeners/path_blockers.py:199` | `_process` | local `report`: builder `get_runtime_path_block_report()`; mutated in place | `path_block_action == 'cancel_and_event'` ⟶ `not _still_matches` |
| `custom_components/eufy_vacuum/listeners/path_blockers.py:229` | `_process` | local `report`: builder `get_runtime_path_block_report()`; mutated in place | — |

## eufy_vacuum_room_completed

Constant: `EVENT_ROOM_COMPLETED` — `custom_components/eufy_vacuum/mapping/tracker.py:40`, string literal `'eufy_vacuum_room_completed'`

Fired from 1 call site(s) in 1 module(s): `custom_components/eufy_vacuum/mapping/tracker.py`

### Payload

| Key | Present | Value expression |
|---|---|---|
| `confidence` | every site | `confidence` |
| `duration_seconds` | every site | `round(duration_seconds, 1)` |
| `entered_at` | every site | `entered_at_str` |
| `map_id` | every site | `str(map_id)` |
| `room_id` | every site | `str(room_id)` |
| `room_name` | every site | `room_name` |
| `vacuum_entity_id` | every site | `vacuum_entity_id` |

### Fire sites

| Location | Enclosing | Payload built by | Nearest guards |
|---|---|---|---|
| `custom_components/eufy_vacuum/mapping/tracker.py:586` | `MappingTracker._fire_room_completed` | local `event_data`: dict literal at line 573 | — |

## eufy_vacuum_room_finished

Constant: `EVENT_ROOM_FINISHED` — `custom_components/eufy_vacuum/const.py:284`, f-string `f'{DOMAIN}_room_finished'`

Fired from 2 call site(s) in 1 module(s): `custom_components/eufy_vacuum/jobs/active_job.py`

### Payload

| Key | Present | Value expression |
|---|---|---|
| `actual_duration_minutes` | every site | `round(elapsed_minutes, 2)` |
| `completed_at` | every site | `completed_at` |
| `completed_room_ids` | every site | `updated_active_job.get('completed_room_ids', [])` · `job.get('completed_room_ids', [])` |
| `confidence` | 1 of 2 sites | `round(confidence_score, 4) if confidence_score > 0 else None` |
| `job_id` | every site | `updated_active_job.get('job_id')` · `job.get('job_id')` |
| `map_id` | every site | `str(map_id)` |
| `room_id` | every site | `str(current_room_id)` · `str(complete_room_id)` |
| `room_name` | every site | `room_name` · `finished_name` |
| `source` | every site | `source` · `'native_signal'` |
| `vacuum_entity_id` | every site | `vacuum_entity_id` |

Where a key lists more than one expression, the fire sites build it differently. That is how the value is OBTAINED, not a claim that the resulting values differ — types are not inferred.

### Fire sites

| Location | Enclosing | Payload built by | Nearest guards |
|---|---|---|---|
| `custom_components/eufy_vacuum/jobs/active_job.py:1553` | `ActiveJobTracker._apply_room_rollover` | dict literal at the call site | — |
| `custom_components/eufy_vacuum/jobs/active_job.py:1758` | `ActiveJobTracker._set_native_current_room` | dict literal at the call site | `complete_room_id is not None and complete_room_id >= 0` |

## eufy_vacuum_room_skipped

Constant: `EVENT_ROOM_SKIPPED` — `custom_components/eufy_vacuum/const.py:320`, f-string `f'{DOMAIN}_room_skipped'`

Fired from 1 call site(s) in 1 module(s): `custom_components/eufy_vacuum/jobs/active_job.py`

### Payload

| Key | Present | Value expression |
|---|---|---|
| `completed_room_ids` | every site | `list(completed_room_ids)` |
| `job_id` | every site | `active_job.get('job_id')` |
| `map_id` | every site | `str(map_id)` |
| `room_id` | every site | `_rid` |
| `room_name` | every site | `self._room_name_from_active_job(active_job, _rid) or f'Room {_rid}'` |
| `vacuum_entity_id` | every site | `vacuum_entity_id` |

### Fire sites

| Location | Enclosing | Payload built by | Nearest guards |
|---|---|---|---|
| `custom_components/eufy_vacuum/jobs/active_job.py:1242` | `ActiveJobTracker.detect_run_anomalies` | dict literal at the call site | `emit and skipped_room_ids` ⟶ `_new_skips` |

## eufy_vacuum_room_started

Constant: `EVENT_ROOM_STARTED` — `custom_components/eufy_vacuum/const.py:283`, f-string `f'{DOMAIN}_room_started'`

Fired from 3 call site(s) in 2 module(s): `custom_components/eufy_vacuum/core/manager.py`, `custom_components/eufy_vacuum/jobs/active_job.py`

### Payload

| Key | Present | Value expression |
|---|---|---|
| `completed_room_ids` | every site | `active_job.get('completed_room_ids', [])` · `updated_active_job.get('completed_room_ids', [])` · `job.get('completed_room_ids', [])` |
| `job_id` | every site | `job_id` · `updated_active_job.get('job_id')` · `job.get('job_id')` |
| `map_id` | every site | `str(map_id)` |
| `room_id` | every site | `str(active_job.get('current_room_id'))` · `str(next_room_id)` · `str(new_room_id)` |
| `room_name` | every site | `self._room_name_from_active_job(active_job, _safe_int(active_job.get('current_room_id'), -1))` · `self._room_name_from_active_job(updated_active_job, next_room_id)` · `self._room_name_from_active_job(job, new_room_id)` |
| `source` | every site | `'job_start'` · `source` · `'native_signal'` |
| `started_at` | every site | `started_at` · `updated_active_job.get('current_room_started_at')` · `completed_at` |
| `vacuum_entity_id` | every site | `vacuum_entity_id` |

Where a key lists more than one expression, the fire sites build it differently. That is how the value is OBTAINED, not a claim that the resulting values differ — types are not inferred.

### Fire sites

| Location | Enclosing | Payload built by | Nearest guards |
|---|---|---|---|
| `custom_components/eufy_vacuum/core/manager.py:6767` | `EufyVacuumManager.start_selected_rooms` | dict literal at the call site | `active_job.get('current_room_id') not in (None, '')` |
| `custom_components/eufy_vacuum/jobs/active_job.py:1571` | `ActiveJobTracker._apply_room_rollover` | dict literal at the call site | `next_room_id >= 0` |
| `custom_components/eufy_vacuum/jobs/active_job.py:1784` | `ActiveJobTracker._set_native_current_room` | dict literal at the call site | — |

## eufy_vacuum_run_incomplete

Constant: `EVENT_RUN_INCOMPLETE` — `custom_components/eufy_vacuum/const.py:313`, f-string `f'{DOMAIN}_run_incomplete'`

Fired from 5 call site(s) in 4 module(s): `custom_components/eufy_vacuum/learning/services.py`, `custom_components/eufy_vacuum/listeners/path_blockers.py`, `custom_components/eufy_vacuum/listeners/pause_timeout.py`, `custom_components/eufy_vacuum/services/job_control.py`

### Payload

| Key | Present | Value expression |
|---|---|---|
| `job_id` | every site | `incomplete_log.get('job_id')` |
| `missed_room_ids` | every site | `list(incomplete_log.get('missed_room_ids', []))` |
| `missed_rooms` | every site | `list(incomplete_log.get('missed_rooms', []))` |
| `outcome_status` | every site | `incomplete_log.get('outcome_status')` |
| `vacuum_entity_id` | every site | `call.data['vacuum_entity_id']` · `vacuum_entity_id` |

Where a key lists more than one expression, the fire sites build it differently. That is how the value is OBTAINED, not a claim that the resulting values differ — types are not inferred.

### Fire sites

| Location | Enclosing | Payload built by | Nearest guards |
|---|---|---|---|
| `custom_components/eufy_vacuum/learning/services.py:489` | `handle_finalize_learning_job` | dict literal at the call site | `isinstance(incomplete_log, dict) and incomplete_log.get('missed_room_ids')` |
| `custom_components/eufy_vacuum/listeners/path_blockers.py:223` | `_process` | local `run_incomplete`: builder `run_incomplete_event_data()` | `path_block_action == 'cancel_and_event'` ⟶ `bool((action_result or {}).get('cancelled'))` ⟶ `run_incomplete is not None` |
| `custom_components/eufy_vacuum/listeners/pause_timeout.py:140` | `_reap_one_slot` | local `run_incomplete`: builder `run_incomplete_event_data()` | `isinstance(timeout_report, dict)` ⟶ `bool(result.get('cancelled'))` ⟶ `run_incomplete is not None` |
| `custom_components/eufy_vacuum/listeners/pause_timeout.py:181` | `_reap_one_slot` | local `run_incomplete`: builder `run_incomplete_event_data()` | `isinstance(stranded_report, dict)` ⟶ `bool(result.get('finalized'))` ⟶ `run_incomplete is not None` |
| `custom_components/eufy_vacuum/services/job_control.py:281` | `_handle_cancel_active_job` | local `run_incomplete`: builder `run_incomplete_event_payload()` | `payload.get('cancelled')` ⟶ `run_incomplete is not None` |

## eufy_vacuum_stall_captured

Constant: `EVENT_STALL_CAPTURED` — `custom_components/eufy_vacuum/listeners/stall_capture.py:62`, f-string `f'{DOMAIN}_stall_captured'`

Fired from 1 call site(s) in 1 module(s): `custom_components/eufy_vacuum/listeners/stall_capture.py`

### Payload

| Key | Present | Value expression |
|---|---|---|
| `image_path` | every site | `path` |
| `map_id` | every site | `str(map_id)` |
| `message` | every site | `message` |
| `room_id` | every site | `room_id` |
| `room_name` | every site | `room_name` |
| `vacuum_entity_id` | every site | `vacuum_entity_id` |

### Fire sites

| Location | Enclosing | Payload built by | Nearest guards |
|---|---|---|---|
| `custom_components/eufy_vacuum/listeners/stall_capture.py:372` | `_capture` | dict literal at the call site | — |

## eufy_vacuum_stall_detected

Constant: `EVENT_STALL_DETECTED` — `custom_components/eufy_vacuum/const.py:306`, f-string `f'{DOMAIN}_stall_detected'`

Fired from 3 call site(s) in 3 module(s): `custom_components/eufy_vacuum/core/manager.py`, `custom_components/eufy_vacuum/jobs/active_job.py`, `custom_components/eufy_vacuum/services/stall_capture.py`

### Payload

| Key | Present | Value expression |
|---|---|---|
| `elapsed_minutes` | 2 of 3 sites | `stall_elapsed_minutes` · `None` |
| `error_code` | 1 of 3 sites | `(latch or {}).get('current_code')` |
| `error_message` | 1 of 3 sites | `(latch or {}).get('current_message')` |
| `expected_minutes` | 2 of 3 sites | `stall_expected_minutes` · `None` |
| `injected` | 1 of 3 sites | `True` |
| `map_id` | every site | `str(map_id)` |
| `min_progress_m2` | 1 of 3 sites | `limits['min_progress_m2']` |
| `progress_m2` | 1 of 3 sites | `round(float(result['progress_m2']), 2)` |
| `room_id` | every site | `room_id` · `current_room_id` |
| `room_name` | every site | `room_name` · `_stall_room_name` · `room.get('name') or f'Room {room_id}'` |
| `stall_ratio` | 2 of 3 sites | `stall_ratio` · `None` |
| `trigger` | 2 of 3 sites | `trigger` · `'timing'` |
| `vacuum_entity_id` | every site | `vacuum_entity_id` |
| `window_minutes` | 1 of 3 sites | `limits['window_minutes']` |

Where a key lists more than one expression, the fire sites build it differently. That is how the value is OBTAINED, not a claim that the resulting values differ — types are not inferred.

#### Caller-supplied key groups

These keys are not written at the fire site. The firing helper extends its payload with a dict passed in by its caller, so the set depends on which caller fired it.

| Discriminator | Keys | Passed at |
|---|---|---|
| `trigger='area'` | `window_minutes`, `progress_m2`, `min_progress_m2` | `custom_components/eufy_vacuum/core/manager.py:4661` |
| `trigger='error'` | `error_code`, `error_message` | `custom_components/eufy_vacuum/core/manager.py:4620` |

### Fire sites

| Location | Enclosing | Payload built by | Nearest guards |
|---|---|---|---|
| `custom_components/eufy_vacuum/core/manager.py:4772` | `EufyVacuumManager._fire_stuck_event` | local `payload`: dict literal at line 4764; extended by the caller via `detail=` | — |
| `custom_components/eufy_vacuum/jobs/active_job.py:1160` | `ActiveJobTracker.detect_run_anomalies` | dict literal at the call site | `_stall_threshold > 0 and current_room_elapsed_minutes >= _stall_threshold * _STALL_RATIO` ⟶ `emit` ⟶ `current_room_id not in _notified` |
| `custom_components/eufy_vacuum/services/stall_capture.py:152` | `_dev_inject_stall` | local `payload`: dict literal at line 129 | — |

> **Line numbers here are current by construction.** They are regenerated from
> source and CI fails when this file disagrees with the generator, which is the
> only reason a reference is allowed to cite them at all — prose in this repo
> cites symbols precisely because prose has no such mechanism.

## What this reference cannot see

Declared rather than omitted. An analysis that cannot see a construction site
reports absence with total confidence: this repo's theme-token trace once called
135 live tokens dead for exactly that reason, and deleting them would have broken
theming everywhere. So every limit of the static pass is listed here, grouped,
with its count.

| Blind spot | n | What it means for a reader |
|---|--:|---|
| `builder-self-delegate` | 2 | get_runtime_path_block_report() delegate: `get_runtime_path_block_report` delegates to another definition of the same name — not followed a second time; the keys come from the sibling definition |
| `firing-conditions-not-derived` | 1 | the `if` guards printed per site are the enclosing tests only — dedup ledgers, adapter capability gates and cross-tick state machines that decide whether a site is reached are not modelled |
| `flow-insensitive-mutation` | 1 | in-place payload mutations are attributed by LINE ORDER, not control flow — a mutation in a branch not taken is still counted for any fire site textually below it |
| `no-type-inference` | 1 | payload value TYPES are not inferred; the reference prints the value EXPRESSION for 92 key slots instead |

**`builder-self-delegate`** — 2 site(s):

- `custom_components/eufy_vacuum/core/manager.py` — get_runtime_path_block_report() delegate: `get_runtime_path_block_report` delegates to another definition of the same name — not followed a second time; the keys come from the sibling definition
- `custom_components/eufy_vacuum/core/manager.py` — get_runtime_path_block_report() delegate: `get_runtime_path_block_report` delegates to another definition of the same name — not followed a second time; the keys come from the sibling definition

