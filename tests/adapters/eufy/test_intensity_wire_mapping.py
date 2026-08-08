"""Eufy's three cleaning intensities must reach three DISTINCT device values.

VA declares `clean_intensity_options` as Quick / Narrow / Deep, ordered fastest to
slowest per the option-order standard (index 0 = least effort). The device stores an
enum, and robovac_mqtt resolves the payload string through CLEAN_EXTENT_MAP:

    quick | fast      -> CleanExtent.QUICK  (2)
    normal | standard -> CleanExtent.NORMAL (0)
    narrow | deep     -> CleanExtent.NARROW (1)

"narrow" and "deep" are the SAME value there — "deep" is a legacy alias. So sending
VA's names through unmapped collapsed Narrow and Deep onto NARROW and left NORMAL
unreachable: three chips in the card, two distinct pass densities on the floor, and
the middle one (the Eufy app's "Medium") impossible to select.

Verified against hardware 2026-08-08 by setting the Eufy app and reading
`select.<vac>_cleaning_intensity`, cross-checked against the protobuf enum
(clean_param_pb2: NORMAL=0, NARROW=1, QUICK=2):

    VA Quick  -> quick  -> QUICK  (2) -> app Low     (widest spacing)
    VA Narrow -> normal -> NORMAL (0) -> app Medium
    VA Deep   -> narrow -> NARROW (1) -> app High    (densest)

Note the enum is NOT ordered by density — 0 is the middle — so nothing anywhere may
interpolate or pick a "nearest" value on it.

The card carries the matching half in `_profileIntensityToEditorIntensity`. Both must
agree, or the editor displays a density the wire does not send.

Coverage targets
----------------
[CIW-1] each declared intensity maps to a distinct wire value.
[CIW-2] every wire value is one robovac_mqtt's CLEAN_EXTENT_MAP accepts.
[CIW-3] the declared option ORDER stays fastest -> slowest (the VA standard).
"""

from __future__ import annotations

from custom_components.eufy_vacuum.queue.queue_engine import _write_room_field

#: robovac_mqtt CLEAN_EXTENT_MAP, keyed lowercase as that code does. Reproduced rather
#: than imported: it lives in a different integration that need not be installed, and a
#: silent drift there is exactly what this test exists to notice.
CLEAN_EXTENT_MAP = {
    "fast": "QUICK", "standard": "NORMAL", "deep": "NARROW",
    "quick": "QUICK", "normal": "NORMAL", "narrow": "NARROW",
}


def _eufy_config():
    from custom_components.eufy_vacuum.adapters.eufy import adapter as eufy_adapter

    src = open(eufy_adapter.__file__, encoding="utf-8").read()
    assert '"clean_intensity": {' in src
    return src


def _declared_intensities():
    from custom_components.eufy_vacuum.adapters.eufy.room_profiles import (
        BUILT_IN_ROOM_PROFILES,
    )

    return BUILT_IN_ROOM_PROFILES


def _wire(value: str, value_map: dict[str, str] | None):
    payload: dict = {}
    _write_room_field(
        payload,
        {"clean_intensity": {"field_name": "clean_intensity", "value_map": value_map}},
        "clean_intensity",
        value,
    )
    return payload.get("clean_intensity")


VALUE_MAP = {"Narrow": "normal", "Deep": "narrow"}
DECLARED = ["Quick", "Narrow", "Deep"]


def test_ciw_1_each_intensity_reaches_a_distinct_wire_value():
    """[CIW-1] Three declared options, three distinct device values."""
    wire = [_wire(v, VALUE_MAP) for v in DECLARED]
    extents = [CLEAN_EXTENT_MAP[str(w).lower()] for w in wire]
    assert len(set(extents)) == 3, f"collision: {dict(zip(DECLARED, extents))}"
    assert extents == ["QUICK", "NORMAL", "NARROW"], extents


def test_ciw_1b_without_the_map_two_of_them_collide():
    """[CIW-1b] The mutation control — what the bug actually was.

    Unmapped, VA's own names go straight to the wire, and CLEAN_EXTENT_MAP reads
    "narrow" and "deep" as the same value. Without this the fix above could pass for
    the wrong reason (e.g. if the map were a no-op) and nobody would know.
    """
    wire = [_wire(v, None) for v in DECLARED]
    extents = [CLEAN_EXTENT_MAP[str(w).lower()] for w in wire]
    assert len(set(extents)) == 2, extents
    assert extents == ["QUICK", "NARROW", "NARROW"], extents


def test_ciw_2_every_wire_value_is_one_the_device_accepts():
    """[CIW-2] A value outside CLEAN_EXTENT_MAP is logged and DROPPED upstream —
    the setting silently does nothing, which is the failure this whole seam guards."""
    for value in DECLARED:
        assert str(_wire(value, VALUE_MAP)).lower() in CLEAN_EXTENT_MAP, value


def test_ciw_3_the_declared_order_is_fastest_to_slowest():
    """[CIW-3] The VA option-order standard: index 0 = least effort.

    For pass density that is widest spacing first. Pinned because the wire values are
    an arbitrary enum (NORMAL=0 sits between NARROW=1 and QUICK=2), so the ordering
    cannot be recovered from the device — it exists only in the declaration.
    """
    density_rank = {"QUICK": 0, "NORMAL": 1, "NARROW": 2}   # widest -> closest
    ranks = [density_rank[CLEAN_EXTENT_MAP[str(_wire(v, VALUE_MAP)).lower()]] for v in DECLARED]
    assert ranks == sorted(ranks), f"declared order is not fastest->slowest: {ranks}"


def test_ciw_4_the_built_in_profiles_only_use_declared_intensities():
    """[CIW-4] A built-in profile naming an undeclared intensity would dispatch a
    value the device drops, and the card would render no selected chip for it."""
    for name, profile in _declared_intensities().items():
        value = profile.get("clean_intensity")
        if value:
            assert value in DECLARED, f"{name} declares clean_intensity={value!r}"
