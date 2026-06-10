"""Unit tests for queue/dispatch_engines.py — the pluggable dispatch seam.

Coverage targets
----------------
[DE-1]  get_dispatch_engine: resolves a registered template by name.
[DE-2]  get_dispatch_engine: absent template (None/"") -> Eufy fallback (legacy default).
[DE-3]  get_dispatch_engine: unknown template -> Eufy fallback.
[DE-4]  known_dispatch_templates includes the registered engines.
[DE-5]  Eufy engine fidelity: build_payload == build_room_clean_payload byte-for-byte.
[DE-6]  Roborock engine: flat segments list + batch repeat scalar.
[DE-7]  Ecovacs (generic) engine: flat rooms list + batch cleanings scalar via field config.
[DE-8]  Batch passes = max requested across rooms, clamped to passes_max.
[DE-9]  resolved_rooms preserved (canonical per-room settings survive for learning).
[DE-10] Dreame engine: positional parallel arrays, index-aligned, value-mapped.
[DE-11] Dreame engine: undeclared/null fields are omitted (clean_mode global, etc.).
[DE-12] Dreame engine: per-room repeats array (not a batch scalar), clamped.
"""

from __future__ import annotations

from custom_components.eufy_vacuum.queue.dispatch_engines import (
    DreameSegmentEngine,
    EufyRoomCleanEngine,
    GenericRoomIdsEngine,
    RoborockSegmentEngine,
    get_dispatch_engine,
    known_dispatch_templates,
)
from custom_components.eufy_vacuum.queue.queue_engine import build_room_clean_payload


_VAC = "vacuum.alfred"
_MAP = "6"


def _managed():
    return {
        "1": {"room_id": 1, "name": "Kitchen", "enabled": True,
              "clean_mode": "vacuum", "fan_speed": "Max", "order": 1},
        "2": {"room_id": 2, "name": "Bath", "enabled": True,
              "clean_mode": "vacuum", "fan_speed": "Standard", "order": 2},
    }


def test_resolves_registered_template():
    """[DE-1]"""
    engine = get_dispatch_engine("eufy_room_clean")
    assert isinstance(engine, EufyRoomCleanEngine)
    assert engine.template_name == "eufy_room_clean"


def test_absent_template_falls_back_to_eufy():
    """[DE-2] None and "" both route to the Eufy engine (legacy default)."""
    assert isinstance(get_dispatch_engine(None), EufyRoomCleanEngine)
    assert isinstance(get_dispatch_engine(""), EufyRoomCleanEngine)


def test_unknown_template_falls_back_to_eufy():
    """[DE-3] a genuinely unregistered name falls back to Eufy."""
    assert isinstance(get_dispatch_engine("totally_made_up"), EufyRoomCleanEngine)


def test_known_templates():
    """[DE-4]"""
    known = known_dispatch_templates()
    assert "eufy_room_clean" in known
    assert "roborock_segment_clean" in known
    assert "generic_room_ids" in known


def test_roborock_and_generic_registered():
    """[DE-1] the new templates resolve to the flat-id engine."""
    assert isinstance(get_dispatch_engine("roborock_segment_clean"), RoborockSegmentEngine)
    assert isinstance(get_dispatch_engine("generic_room_ids"), GenericRoomIdsEngine)


def test_eufy_engine_fidelity():
    """[DE-5] the engine produces byte-identical output to the legacy builder."""
    kwargs = dict(
        vacuum_entity_id=_VAC,
        map_id=_MAP,
        managed_rooms=_managed(),
        queue_room_ids=[1, 2],
        stored_profiles=None,
        capabilities={"supports_mop_features": False},
        dispatch={},
    )
    via_engine = get_dispatch_engine("eufy_room_clean").build_payload(**kwargs)
    via_legacy = build_room_clean_payload(**kwargs)
    assert via_engine == via_legacy


# --- flat-id-list brands (Roborock / Ecovacs) -------------------------------


def _flat_kwargs(dispatch):
    return dict(
        vacuum_entity_id=_VAC,
        map_id=_MAP,
        managed_rooms=_managed(),
        queue_room_ids=[1, 2],
        stored_profiles=None,
        capabilities={},
        dispatch=dispatch,
    )


def test_roborock_flat_segments_repeat():
    """[DE-6] Roborock shape: {segments:[ints], repeat:n}, not a list of dicts."""
    result = get_dispatch_engine("roborock_segment_clean").build_payload(
        **_flat_kwargs({"template": "roborock_segment_clean"})
    )
    payload = result["payload"]
    assert payload["segments"] == [1, 2]            # flat int list, order preserved
    assert isinstance(payload["repeat"], int)        # batch scalar, not per-room
    assert result["room_count"] == 2


def test_ecovacs_field_names_via_config():
    """[DE-7] Ecovacs spot_area shape via dispatch field config: {rooms, cleanings}."""
    result = get_dispatch_engine("generic_room_ids").build_payload(
        **_flat_kwargs({
            "template": "generic_room_ids",
            "rooms_field": "rooms",
            "clean_passes_field": "cleanings",
        })
    )
    payload = result["payload"]
    assert payload["rooms"] == [1, 2]
    assert "cleanings" in payload and "segments" not in payload


def test_batch_passes_is_max_clamped():
    """[DE-8] per-room passes collapse to the max, clamped to passes_max."""
    rooms = {
        "1": {"room_id": 1, "name": "A", "enabled": True, "clean_passes": 1, "order": 1},
        "2": {"room_id": 2, "name": "B", "enabled": True, "clean_passes": 5, "order": 2},
    }
    result = GenericRoomIdsEngine().build_payload(
        vacuum_entity_id=_VAC, map_id=_MAP, managed_rooms=rooms,
        queue_room_ids=[1, 2], capabilities={},
        dispatch={"template": "roborock_segment_clean", "passes_max": 3},
    )
    # room 2 asked for 5 → collapsed to max(1,5)=5 → clamped to 3
    assert result["payload"]["repeat"] == 3


def test_flat_engine_preserves_resolved_rooms():
    """[DE-9] canonical per-room records survive even though the wire is flat."""
    result = get_dispatch_engine("roborock_segment_clean").build_payload(
        **_flat_kwargs({"template": "roborock_segment_clean"})
    )
    resolved = result["resolved_rooms"]
    assert [r["room_id"] for r in resolved] == [1, 2]
    # canonical per-room settings are kept for learning/history (off-wire)
    assert all("clean_mode" in r and "fan_speed" in r for r in resolved)


# --- Dreame parallel-array engine -------------------------------------------


_DREAME_DISPATCH = {
    "template": "dreame_room_clean",
    "rooms_field": "segments",
    "clean_passes_field": "repeats",
    "room_fields": {
        "fan_speed": {"field_name": "suction_level",
                      "value_map": {"Quiet": 0, "Standard": 1, "Turbo": 2, "Max": 3}},
        "water_level": {"field_name": "water_volume",
                        "value_map": {"Low": 1, "Medium": 2, "High": 3}},
        "clean_mode": {"field_name": None},        # global on Dreame
        "clean_intensity": {"field_name": None},
        "edge_mopping": {"field_name": None},
        "path_type": {"field_name": None},
    },
}


def _dreame_rooms():
    return {
        "3": {"room_id": 3, "name": "Kitchen", "enabled": True, "order": 1,
              "clean_mode": "vacuum_mop", "fan_speed": "Quiet",
              "water_level": "Low", "clean_passes": 1},
        "2": {"room_id": 2, "name": "Bath", "enabled": True, "order": 2,
              "clean_mode": "vacuum_mop", "fan_speed": "Max",
              "water_level": "High", "clean_passes": 2},
    }


def test_dreame_parallel_arrays_aligned_and_mapped():
    """[DE-10] index-aligned arrays with canonical->int value mapping."""
    result = DreameSegmentEngine().build_payload(
        vacuum_entity_id=_VAC, map_id=_MAP, managed_rooms=_dreame_rooms(),
        queue_room_ids=[3, 2],
        capabilities={"supports_mop_features": True, "supports_water_control": True},
        dispatch=_DREAME_DISPATCH,
    )
    p = result["payload"]
    assert p["segments"] == [3, 2]
    assert p["suction_level"] == [0, 3]   # Quiet->0, Max->3
    assert p["water_volume"] == [1, 3]    # Low->1, High->3
    assert p["repeats"] == [1, 2]
    # every emitted array is the same length as segments (positional alignment)
    n = len(p["segments"])
    assert all(len(p[k]) == n for k in ("suction_level", "water_volume", "repeats"))


def test_dreame_omits_null_fields():
    """[DE-11] clean_mode (global) + intensity/edge/path are not on the wire."""
    result = DreameSegmentEngine().build_payload(
        vacuum_entity_id=_VAC, map_id=_MAP, managed_rooms=_dreame_rooms(),
        queue_room_ids=[3, 2], capabilities={"supports_water_control": True},
        dispatch=_DREAME_DISPATCH,
    )
    p = result["payload"]
    for absent in ("clean_mode", "clean_intensity", "edge_mopping", "path_type"):
        assert absent not in p


def test_edge_and_path_per_room_writes_when_caps_enabled():
    """[DE-11b] capability-gated edge_mopping + path_type land on the wire.

    Symmetric with the water_level branch the Dreame tests already cover: when
    a brand declares ``edge_mopping``/``path_type`` as real wire fields AND the
    vacuum advertises supports_edge_mopping/supports_path_control, the mop-mode
    per-room edge write and the unconditional per-room path write must both
    appear in each room dict. No shipped adapter declares these fields, so this
    is the only path that drives ``build_room_clean_payload``'s edge/path
    branches. Asserted on the Eufy list-of-dicts wire shape, where the gated
    writes are directly observable per room.
    """
    rooms = {
        "3": {"room_id": 3, "name": "Kitchen", "enabled": True, "order": 1,
              "clean_mode": "vacuum_mop", "edge_mopping": True, "path_type": "narrow"},
        "2": {"room_id": 2, "name": "Bath", "enabled": True, "order": 2,
              "clean_mode": "vacuum_mop", "edge_mopping": False, "path_type": "wide"},
    }
    dispatch = {
        "room_fields": {
            # Declare edge_mopping/path_type as real wire fields (drop the
            # field_name:None that every shipped adapter uses for these two).
            "edge_mopping": {"field_name": "edge",
                             "value_map": {"True": 1, "False": 0}},
            "path_type": {"field_name": "route"},
            "clean_mode": {"field_name": None},        # still global / off-wire
            "clean_intensity": {"field_name": None},
        },
    }
    result = build_room_clean_payload(
        vacuum_entity_id=_VAC, map_id=_MAP, managed_rooms=rooms,
        queue_room_ids=[3, 2],
        capabilities={
            "supports_mop_features": True,
            "supports_water_control": True,
            "supports_edge_mopping": True,
            "supports_path_control": True,
        },
        dispatch=dispatch,
    )
    wire_rooms = result["payload"]["rooms"]
    assert [r["id"] for r in wire_rooms] == [3, 2]          # order preserved
    # edge branch (queue_engine.py:295-296): value-mapped per room, both present
    assert [r["edge"] for r in wire_rooms] == [1, 0]
    # path branch (queue_engine.py:298-299): per-room path_type written through
    assert [r["route"] for r in wire_rooms] == ["narrow", "wide"]
    # off-wire fields stay off the wire even with caps on
    assert all("clean_mode" not in r and "clean_intensity" not in r
               for r in wire_rooms)


def test_dreame_repeats_is_array_clamped():
    """[DE-12] per-room repeats array, clamped to passes_max (not collapsed)."""
    rooms = {
        "3": {"room_id": 3, "name": "A", "enabled": True, "order": 1, "clean_passes": 1},
        "2": {"room_id": 2, "name": "B", "enabled": True, "order": 2, "clean_passes": 9},
    }
    result = DreameSegmentEngine().build_payload(
        vacuum_entity_id=_VAC, map_id=_MAP, managed_rooms=rooms,
        queue_room_ids=[3, 2], capabilities={},
        dispatch={**_DREAME_DISPATCH, "passes_max": 3},
    )
    # per-room, not a scalar: room A=1, room B clamped 9->3
    assert result["payload"]["repeats"] == [1, 3]


def test_dreame_template_resolves():
    """[DE-10] dreame_room_clean resolves to the parallel-array engine."""
    assert isinstance(get_dispatch_engine("dreame_room_clean"), DreameSegmentEngine)


# --- job model / build_phases (sequencing mechanism) ------------------------


def test_all_engines_atomic_by_default():
    """[DE-13] every registered engine is atomic_batch."""
    for name in known_dispatch_templates():
        assert get_dispatch_engine(name).job_model == "atomic_batch"


def test_build_phases_default_is_single_phase():
    """[DE-13] an atomic engine's build_phases == [build_payload] (one phase)."""
    kwargs = dict(
        vacuum_entity_id=_VAC, map_id=_MAP, managed_rooms=_managed(),
        queue_room_ids=[1, 2], capabilities={}, dispatch={},
    )
    engine = get_dispatch_engine("eufy_room_clean")
    phases = engine.build_phases(**kwargs)
    assert len(phases) == 1
    assert phases[0] == engine.build_payload(**kwargs)


def test_sequenced_engine_emits_multiple_phases():
    """[DE-14] a sequenced engine declares job_model + returns >1 phase."""

    class _SweepThenMopEngine(DreameSegmentEngine):
        template_name = "dreame_room_clean"
        job_model = "sequenced"

        def build_phases(self, **kwargs):
            # phase 1 sweep, phase 2 mop — same rooms, distinct payloads
            sweep = self.build_payload(**kwargs)
            mop = self.build_payload(**kwargs)
            sweep["payload"] = {**sweep["payload"], "phase": "sweep"}
            mop["payload"] = {**mop["payload"], "phase": "mop"}
            return [sweep, mop]

    engine = _SweepThenMopEngine()
    assert engine.job_model == "sequenced"
    phases = engine.build_phases(
        vacuum_entity_id=_VAC, map_id=_MAP, managed_rooms=_managed(),
        queue_room_ids=[1, 2], capabilities={}, dispatch=_DREAME_DISPATCH,
    )
    assert len(phases) == 2
    assert phases[0]["payload"]["phase"] == "sweep"
    assert phases[1]["payload"]["phase"] == "mop"
    # each phase is a complete, independently-finalizable payload envelope
    assert all("resolved_rooms" in p and "payload" in p for p in phases)
