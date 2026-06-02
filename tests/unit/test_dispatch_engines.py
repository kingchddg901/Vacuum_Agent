"""Unit tests for queue/dispatch_engines.py — the pluggable dispatch seam.

Coverage targets
----------------
[DE-1]  get_dispatch_engine: resolves a registered template by name.
[DE-2]  get_dispatch_engine: absent template (None/"") -> Eufy fallback (legacy default).
[DE-3]  get_dispatch_engine: unknown template -> Eufy fallback.
[DE-4]  known_dispatch_templates includes the registered engines.
[DE-5]  Eufy engine fidelity: build_payload == build_room_clean_payload byte-for-byte.
"""

from __future__ import annotations

from custom_components.eufy_vacuum.queue.dispatch_engines import (
    EufyRoomCleanEngine,
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
    """[DE-3]"""
    assert isinstance(get_dispatch_engine("roborock_segment_clean"), EufyRoomCleanEngine)
    assert isinstance(get_dispatch_engine("totally_made_up"), EufyRoomCleanEngine)


def test_known_templates():
    """[DE-4]"""
    assert "eufy_room_clean" in known_dispatch_templates()


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
