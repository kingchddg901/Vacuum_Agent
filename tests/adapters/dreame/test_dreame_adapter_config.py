"""Dreame adapter config-shape assertions — the wires that route the brand's NATIVE
current-room signal to the subsystems that must consume it.

Dreame publishes the live room directly on ``sensor.<id>_current_room`` (the
``active_cleaning_target`` entity). Three consumers must ride that ONE signal, and each
was a declared-but-unwired gap at some point:

  * the map current-room HIGHLIGHT (``room_attribution.source: native_current_room`` +
    the coordinator injection — see tests/unit/test_current_room_resolve.py),
  * the pose sampler's attribution, and
  * the room ROLLOVER that writes ``completed_rooms``.

[DAC-1] native_transition_source is declared True -> rollover follows the native signal,
        NOT Eufy's counter_plateau. BITE: drop it and the rollover falls back to
        counter_plateau, which mis-attributes the whole run's area to the first room and
        drops the LAST room ("Not reached"), the live-observed failure this fixes.
[DAC-2] room_attribution.source is native_current_room (the highlight + attribution wire).
[DAC-3] the two wires agree — a brand that declares the native attribution source but not
        the native rollover would split its signal across subsystems (the drift these guard).
[DAC-4] the counter tool is DROPPED for the finalize: job_segmenter declares noop +
        finalize_source=native_current_room (per-room timings cut at the native boundaries).
[DAC-5] brand_facts exposes native_finalize=True — the flag the finalize actually reads.
[DAC-6] "no_error" is a not-error sentinel, so the error tracker does not read the clear as a
        fresh fault (the live phantom-second-error); a real fault ("brush") still latches.
[DAC-7] a Dreame fault names itself from the error-entity STATE slug -> fault.dreame.<slug>
        (the harvested locale keys), + a "robot" default source; sentinels yield no key.
[DAC-8] external (app-started) capture vocab: active_run_task_states carries the live clean,
        and external_mid_run_statuses holds the grace-finalize open through a station cycle.
[DAC-9] external_run.queue_from_active_segments is declared, so the app-run finalizer reads the
        device's own queue snapshot (active_segments) as ground truth for queued/not-reached.
"""

from __future__ import annotations

import pytest

from custom_components.eufy_vacuum.adapters.dreame.adapter import (
    register_dreame_adapter_for_vacuum,
)
from custom_components.eufy_vacuum.adapters.registry import get_adapter_config

_DVAC = "vacuum.robin_cfg"


@pytest.fixture
def dreame_config(hass):
    register_dreame_adapter_for_vacuum(hass, _DVAC)
    return get_adapter_config(_DVAC)


def test_native_transition_source_declared(dreame_config):
    """[DAC-1] the native rollover path is enabled for Dreame."""
    lt = dreame_config.get("live_transition") or {}
    assert lt.get("native_transition_source") is True
    assert lt.get("enabled") is True


def test_room_attribution_is_native(dreame_config):
    """[DAC-2] attribution + highlight both key off the native current-room entity."""
    assert (dreame_config.get("room_attribution") or {}).get("source") == "native_current_room"


def test_rollover_and_attribution_agree(dreame_config):
    """[DAC-3] declaring the native attribution source WITHOUT the native rollover would
    leave the rollover on counter_plateau — the exact split this fixes. Assert both, together."""
    native_attr = (dreame_config.get("room_attribution") or {}).get("source") == "native_current_room"
    native_roll = (dreame_config.get("live_transition") or {}).get("native_transition_source") is True
    assert native_attr and native_roll


def test_counter_tool_dropped_for_finalize(dreame_config):
    """[DAC-4] the eufy counter segmenter is dropped for Dreame's finalize — it returns one
    segment for Dreame's cumulative counters + sub-30s transits (whole run -> first room, last
    room "Not reached"). noop + finalize_source route the atomic per-room timings through the
    native current_room boundaries instead. BITE: restore engine=counter_plateau_v1 -> red."""
    js = dreame_config.get("job_segmenter") or {}
    assert js.get("engine") == "noop_job_fallback"
    assert js.get("finalize_source") == "native_current_room"


def test_brand_facts_exposes_native_finalize(dreame_config):
    """[DAC-5] brand_facts.native_finalize is the flag learning/history_store reads to pick the
    native builder over the counter path. Drop finalize_source and this + the finalize go red."""
    from custom_components.eufy_vacuum.learning.brand_facts import brand_facts_for

    assert brand_facts_for(_DVAC).native_finalize is True


def test_no_error_is_a_sentinel_no_phantom_latch(dreame_config):
    """[DAC-6] "no_error" (dreame_vacuum's ERROR_NO_ERROR clear value) is declared a not-error
    sentinel, so the error tracker fires on the fault RISE but NOT on the clear. Observed live:
    without it, one brush jam recorded TWO faults — the rise AND the clear-to-"no_error" (which
    read as a fresh error). A real fault slug ("brush") still latches. BITE: drop "no_error"
    from not_error_sentinels and the "no_error" assert flips True — the phantom is back."""
    from custom_components.eufy_vacuum.core.error_tracker import (
        _get_not_error_set,
        _is_error_value,
    )

    sentinels = _get_not_error_set(_DVAC)
    assert "no_error" in sentinels
    assert _is_error_value("no_error", not_error=sentinels) is False  # the clear — no phantom
    assert _is_error_value("brush", not_error=sentinels) is True      # a real fault still latches


def test_slug_faults_name_themselves_from_state(dreame_config):
    """[DAC-7] Dreame's fault is the error-entity STATE slug (dreame_vacuum's ERROR_* value), not
    a numeric code, so the fault names itself fault.dreame.<slug> — the harvested locale keys. A
    sentinel/empty state yields no key. Source defaults to "robot" (component-side faults). BITE:
    drop fault_label_from_message and the "brush" assert returns None; drop default_error_source
    and the source assert flips to None."""
    from custom_components.eufy_vacuum.core.error_tracker import (
        default_error_source,
        error_label_key_from_message,
    )

    assert error_label_key_from_message(_DVAC, "brush") == "fault.dreame.brush"
    assert error_label_key_from_message(_DVAC, "side_brush") == "fault.dreame.side_brush"
    assert error_label_key_from_message(_DVAC, "no_error") is None  # sentinel -> no key
    assert error_label_key_from_message(_DVAC, "") is None
    assert default_error_source(_DVAC) == "robot"


def test_external_run_task_status_vocab(dreame_config):
    """[DAC-8] External (app-started) capture rides the generic detection + native attribution;
    the Dreame-specific wiring is the task_status vocab. active_run_task_states carries the live
    clean (so the pose sampler doesn't null a cleaning tick as parked); external_mid_run_statuses
    holds the grace-finalize open through a mid-run station cycle (mop wash / dock) so it doesn't
    end the capture early. BITE: drop external_mid_run_statuses and mid_run_statuses goes empty."""
    from custom_components.eufy_vacuum.learning.brand_facts import brand_facts_for

    active = set((dreame_config.get("vocabulary") or {}).get("active_run_task_states") or [])
    assert {"room_cleaning", "cleaning"} <= active
    mid = brand_facts_for(_DVAC).mid_run_statuses
    assert {"station_cleaning", "returning_to_install_mop"} <= mid


def test_external_queue_from_active_segments_declared(dreame_config):
    """[DAC-9] the app-run finalizer reads the device's own queue snapshot (active_segments) as
    the GROUND TRUTH for the external record — which rooms were selected + the tap order — rather
    than inferring only the cleaned set from swept area. BITE: drop the flag and the finalizer
    reverts to pose-only (no queued_room_ids / not_reached on the record)."""
    assert (dreame_config.get("external_run") or {}).get("queue_from_active_segments") is True
