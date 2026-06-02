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
"""

from __future__ import annotations

from custom_components.eufy_vacuum.queue.dispatch_engines import (
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
