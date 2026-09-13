"""Integration tests for maintenance/manager.py — MaintenanceManager + helpers.

Pure status helpers are tested directly; the manager methods run against the
real `manager` fixture with capabilities monkeypatched to map components to
source entities.

Coverage targets
----------------
[MNT-1]  _safe_int / _safe_float sentinel handling.
[MNT-2]  _display_label: explicit map + title case + None.
[MNT-3]  _hours_text: singular/plural/fractional/negative/None.
[MNT-4]  maintenance_status buckets.
[MNT-5]  replacement_status buckets.
[MNT-6]  get_maintenance_state creates/returns the per-vacuum dict.
[MNT-7]  reset_maintenance: success snapshots usage_hours.
[MNT-7b] reset_maintenance: preserves a user interval_hours override (CS-1).
[MNT-8]  reset_maintenance: no source / unavailable / invalid usage.
[MNT-9]  get_maintenance_remaining computes remaining from usage - reset.
[MNT-10] get_maintenance_remaining: no source → source_available False.
[MNT-11] get_upkeep_snapshot returns a structured dict (no components).
[MNT-12] get_upkeep_snapshot populates items from an adapter maintenance component.
[MNT-13] _get_upkeep_item_guide enriches a library entry with source model info + maintenance/replacement sub-dicts; display picks by item_kind.
[MNT-14] _get_replacement_reset_entity: token_sets registry fallback resolves a differently-named reset button when no entity_suffix matches.
[MNT-14c] _get_replacement_reset_entity: entity_suffixes primary route — states-table hit + unconfigured component → None.
[MNT-14d] _get_replacement_reset_entity: entity_suffixes primary route — registry-only hit (no live state).
[MNT-15] get_upkeep_snapshot surfaces v1.11.0 lifetime totals + dock firmware from device sensors.
[MNT-16] get_upkeep_snapshot: no lifetime sensors → device_totals/dock_firmware None.
[MNT-17] get_upkeep_snapshot: placeholder/absent sensor → that field None, the rest still surface.
[MNT-18] RF-33 cont'd: get_upkeep_snapshot never triggers capability detection —
         reads get_vacuum_capabilities_snapshot, not get_vacuum_capabilities(refresh=False).
[MNT-19] RF-33 cont'd: get_maintenance_remaining reuses a passed-in `capabilities`
         dict instead of re-fetching — the seam get_upkeep_snapshot's per-component
         loop relies on to stay inert.
[MNT-20] an OVERDUE consumable (negative hours) does not crash get_upkeep_snapshot —
         the summary call sites must guard the RESULT of _hours_text, not the input.
"""

from __future__ import annotations

import pytest

from custom_components.eufy_vacuum.maintenance.manager import (
    MaintenanceManager,
    _display_label,
    _hours_text,
    _safe_float,
    _safe_int,
    maintenance_status,
    replacement_status,
)


_VAC = "vacuum.alfred"
_SRC = "sensor.alfred_main_brush"


@pytest.fixture
def mnt(manager) -> MaintenanceManager:
    return MaintenanceManager(manager)


def _caps(manager, monkeypatch, sources):
    payload = {"maintenance_sources": sources, "sources": {}}
    # RF-33 cont'd: get_upkeep_snapshot now reads get_vacuum_capabilities_snapshot
    # (the genuinely read-only accessor) while reset_maintenance/get_maintenance_remaining
    # (called directly, not through get_upkeep_snapshot) still read get_vacuum_capabilities
    # — stub both so this helper works for every call site under test.
    monkeypatch.setattr(manager, "get_vacuum_capabilities", lambda **kw: payload)
    monkeypatch.setattr(manager, "get_vacuum_capabilities_snapshot", lambda **kw: payload)


# ---------------------------------------------------------------------------
# pure helpers
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("value,expected", [(5, 5), ("3.9", 3), (None, 0), ("unknown", 0)])
def test_safe_int(value, expected):
    """[MNT-1]"""
    assert _safe_int(value) == expected


def test_safe_float():
    """[MNT-1]"""
    assert _safe_float("2.5") == pytest.approx(2.5)
    assert _safe_float("unavailable") == pytest.approx(0.0)


@pytest.mark.parametrize("value,expected", [
    ("replace_now", "Replace Now"), ("by_time", "By Time"),
    ("main_brush", "Main Brush"), ("", None),
])
def test_display_label(value, expected):
    """[MNT-2]"""
    assert _display_label(value) == expected


@pytest.mark.parametrize("value,expected", [
    (1, "1 hour"), (3, "3 hours"), (2.5, "2.5 hours"), (-1, None), (None, None),
])
def test_hours_text(value, expected):
    """[MNT-3]"""
    assert _hours_text(value) == expected


@pytest.mark.parametrize("remaining,interval,expected", [
    (100, 0, "unknown"), (0, 150, "replace_now"),
    (10, 150, "replace_soon"), (30, 150, "warning"), (100, 150, "good"),
])
def test_maintenance_status(remaining, interval, expected):
    """[MNT-4]"""
    assert maintenance_status(remaining_hours=remaining, interval_hours=interval) == expected


@pytest.mark.parametrize("value,expected", [
    (3, "replace_now"), (8, "replace_soon"), (12, "warning"), (50, "good"),
    (None, "unknown"), ("x", "unknown"),
])
def test_replacement_status(value, expected):
    """[MNT-5] Percentage-based buckets (issue #38) — a full-life part reads good."""
    assert replacement_status(remaining_percent=value) == expected


# ---------------------------------------------------------------------------
# state / reset / remaining
# ---------------------------------------------------------------------------

def test_get_maintenance_state(mnt):
    """[MNT-6]"""
    state = mnt.get_maintenance_state(vacuum_entity_id=_VAC)
    assert isinstance(state, dict)
    state["main_brush"] = {"x": 1}
    assert mnt.get_maintenance_state(vacuum_entity_id=_VAC)["main_brush"] == {"x": 1}


def test_reset_success(mnt, manager, hass, monkeypatch):
    """[MNT-7]"""
    _caps(manager, monkeypatch, {"main_brush": _SRC})
    hass.states.async_set(_SRC, "100", {"usage_hours": 120})
    result = mnt.reset_maintenance(vacuum_entity_id=_VAC, component="main_brush")
    assert result["reset"] is True
    assert result["reset_at_usage_hours"] == pytest.approx(120.0)
    # snapshot persisted
    stored = mnt.get_maintenance_state(vacuum_entity_id=_VAC)["main_brush"]
    assert stored["reset_at_usage_hours"] == pytest.approx(120.0)


def test_countdown_brand_maintenance_counter_moves(mnt, manager, hass, monkeypatch):
    """[MNT-7c] the maintenance COUNTER on a countdown brand, end to end.

    Roborock and Dreame publish hours REMAINING as the sensor state and no
    `usage_hours` attribute at all. Reading only the attribute defaulted current
    usage to 0, so `used_since_reset` was always 0 and `remaining` was always the
    full interval -- every part on both brands reported "300 hours left of 300
    hours", permanently, however much the robot had cleaned.

    It has to be an END-TO-END pair (reset, then advance) rather than one read:
    the snapshot and the comparison are two separate call sites reading the same
    value, and a fix to either alone still produces nonsense.
    """
    from custom_components.eufy_vacuum.adapters.registry import register_adapter_config
    register_adapter_config(_VAC, {
        "adapter_id": "test", "source": "test",
        "maintenance_components": {
            "main_brush": {"label": "Main Brush", "default_interval_hours": 300.0},
        },
    })
    _caps(manager, monkeypatch, {"main_brush": _SRC})

    # ⚠ THE SNAPSHOT IS 0, NOT 7, SINCE 2026-09-12 — and that is the accumulator, not a
    # regression. This used to read `300 - 293 = 7`, which was never a count: it was arithmetic
    # against a life WE declared, and on a brand whose declared number is a cleaning cadence
    # rather than a service life it is simply wrong. A countdown device keeps no total, so we
    # start counting from now and say so. Chris, accepting it: "yes the reset because of the
    # math change i understand... this makes it cleaner for less brand in the core."
    #
    # What this test actually asserts is unchanged and is the point: THE COUNTER MOVES.
    hass.states.async_set(_SRC, "293")
    assert mnt.reset_maintenance(
        vacuum_entity_id=_VAC, component="main_brush")["reset_at_usage_hours"] == pytest.approx(0.0)

    # ⚠ THE FIRST MOVEMENT IS SPENT LEARNING, and it is visible here on purpose. Roborock
    # publishes NO `state_class` on any sensor, so nothing declares which way this source
    # counts and the first move is what teaches us. Booking on a guess instead would risk
    # counting every reset as runtime for the life of the install — silently. One tick is the
    # whole price and it is paid once per source.
    hass.states.async_set(_SRC, "291")
    assert mnt.get_maintenance_remaining(
        vacuum_entity_id=_VAC, component="main_brush",
        interval_hours=30.0)["used_since_reset_hours"] == pytest.approx(0.0)

    # Now it knows. Eight more cleaning hours: the device counts DOWN, our total rises by 8.
    hass.states.async_set(_SRC, "283")
    got = mnt.get_maintenance_remaining(
        vacuum_entity_id=_VAC, component="main_brush", interval_hours=30.0)
    assert got["used_since_reset_hours"] == pytest.approx(8.0)
    assert got["remaining_hours"] == pytest.approx(22.0)   # the user's 30 h cadence, not the device's
    assert got["source_available"] is True


def test_countdown_brand_unreadable_source_is_not_zero(mnt, manager, hass, monkeypatch):
    """[MNT-7d] an unreadable countdown must be UNKNOWN, never "never used".

    The old `float(attributes.get("usage_hours", 0))` turned every unreadable
    source into a confident zero. A reset then baselined the part at "fresh" and
    the counter could never move again -- the failure mode that hides itself.
    """
    from custom_components.eufy_vacuum.adapters.registry import register_adapter_config
    register_adapter_config(_VAC, {
        "adapter_id": "test", "source": "test",
        "maintenance_components": {
            "main_brush": {"label": "Main Brush", "default_interval_hours": 300.0},
        },
    })
    _caps(manager, monkeypatch, {"main_brush": _SRC})
    hass.states.async_set(_SRC, "unavailable")

    assert mnt.reset_maintenance(
        vacuum_entity_id=_VAC, component="main_brush")["reason"] == "invalid_usage_hours"
    assert mnt.get_maintenance_remaining(
        vacuum_entity_id=_VAC, component="main_brush",
        interval_hours=30.0)["source_available"] is False


def test_reset_preserves_interval_override(mnt, manager, hass, monkeypatch):
    """[MNT-7b] CS-1: a reset re-snapshots the usage baseline but must NOT wipe a
    user's interval_hours override — the entry used to be replaced wholesale."""
    _caps(manager, monkeypatch, {"main_brush": _SRC})
    mnt.get_maintenance_state(vacuum_entity_id=_VAC)["main_brush"] = {
        "reset_at_usage_hours": 10.0, "reset_at": "2026-01-01", "interval_hours": 250.0,
    }
    hass.states.async_set(_SRC, "100", {"usage_hours": 120})
    result = mnt.reset_maintenance(vacuum_entity_id=_VAC, component="main_brush")
    assert result["reset"] is True
    stored = mnt.get_maintenance_state(vacuum_entity_id=_VAC)["main_brush"]
    assert stored["reset_at_usage_hours"] == pytest.approx(120.0)   # baseline updated
    assert stored["interval_hours"] == pytest.approx(250.0)          # override preserved


def test_a_reset_moves_the_bookmark_without_wiping_the_counter(mnt, manager, hass, monkeypatch):
    """[MNT-8b] a reset must not restart the accumulator. Found by MNT-7c going red.

    `reset_maintenance` REPLACES the component entry, and the file already carried a note about
    that eating `interval_hours`. Fixing one field made the guard READ as complete while the
    wholesale replace went on eating anything added later — so the accumulator's baseline was
    wiped on every reset, the next reading became a FIRST reading, and the counter restarted
    from zero forever. Silent: every number still looked plausible.

    A reset moves the BOOKMARK (`reset_at_usage_hours`). It must not touch the thing being
    bookmarked.

    THE INPUT THAT MAKES THIS RED: drop `usage_baseline` from the carried list and the second
    leg books 0 instead of 5.
    """
    from custom_components.eufy_vacuum.adapters.registry import register_adapter_config
    register_adapter_config(_VAC, {
        "adapter_id": "test", "source": "test",
        "maintenance_components": {
            "main_brush": {"label": "Main Brush", "default_interval_hours": 300.0},
        },
    })
    _caps(manager, monkeypatch, {"main_brush": _SRC})

    hass.states.async_set(_SRC, "300")
    mnt.get_maintenance_remaining(
        vacuum_entity_id=_VAC, component="main_brush", interval_hours=300.0)
    hass.states.async_set(_SRC, "298")          # the learning tick — teaches DOWN, books 0
    mnt.get_maintenance_remaining(
        vacuum_entity_id=_VAC, component="main_brush", interval_hours=300.0)
    hass.states.async_set(_SRC, "288")          # 10 h of real use, counted
    mnt.get_maintenance_remaining(
        vacuum_entity_id=_VAC, component="main_brush", interval_hours=300.0)

    bucket = mnt.get_maintenance_state(vacuum_entity_id=_VAC)["main_brush"]
    assert bucket["usage_total"] == pytest.approx(10.0)
    assert bucket["usage_baseline"] == pytest.approx(288.0)

    mnt.reset_maintenance(vacuum_entity_id=_VAC, component="main_brush")
    bucket = mnt.get_maintenance_state(vacuum_entity_id=_VAC)["main_brush"]
    assert bucket["usage_total"] == pytest.approx(10.0), "the reset wiped our counter"
    assert bucket["usage_baseline"] == pytest.approx(288.0), "the reset wiped our baseline"
    assert bucket["usage_moves_down"] == 2, "the reset wiped the learned direction"
    assert bucket["reset_at_usage_hours"] == pytest.approx(10.0), "the bookmark is the total"

    # and the counter keeps going from where it was, rather than starting over
    hass.states.async_set(_SRC, "283")
    got = mnt.get_maintenance_remaining(
        vacuum_entity_id=_VAC, component="main_brush", interval_hours=300.0)
    assert got["used_since_reset_hours"] == pytest.approx(5.0)
    assert mnt.get_maintenance_state(
        vacuum_entity_id=_VAC)["main_brush"]["usage_total"] == pytest.approx(15.0)


def test_reset_failure_modes(mnt, manager, hass, monkeypatch):
    """[MNT-8]"""
    _caps(manager, monkeypatch, {})  # no source mapping
    assert mnt.reset_maintenance(
        vacuum_entity_id=_VAC, component="main_brush")["reason"] == "no_source_entity"

    _caps(manager, monkeypatch, {"main_brush": _SRC})  # source mapped but no state
    assert mnt.reset_maintenance(
        vacuum_entity_id=_VAC, component="main_brush")["reason"] == "source_unavailable"

    # Nothing readable anywhere: no usable attribute AND a non-numeric state.
    hass.states.async_set(_SRC, "abc", {"usage_hours": "abc"})
    assert mnt.reset_maintenance(
        vacuum_entity_id=_VAC, component="main_brush")["reason"] == "invalid_usage_hours"

    # ⚠ CHANGED 2026-09-12, and it is a degradation rather than a failure. A GARBAGE ATTRIBUTE
    # beside a NUMERIC STATE used to be refused outright. The accumulator reads direction from
    # the entity, so an unusable `usage_hours` simply means "not a count-up entity" and the
    # state is counted as a countdown instead — which is right, because a Eufy state IS hours
    # remaining. A sensor whose attribute breaks keeps working rather than going dead.
    hass.states.async_set(_SRC, "100", {"usage_hours": "abc"})
    assert mnt.reset_maintenance(
        vacuum_entity_id=_VAC, component="main_brush")["reset"] is True


def test_remaining_computes(mnt, manager, hass, monkeypatch):
    """[MNT-9] remaining = interval - (current_usage - reset_snapshot)."""
    _caps(manager, monkeypatch, {"main_brush": _SRC})
    hass.states.async_set(_SRC, "0", {"usage_hours": 120})
    mnt.get_maintenance_state(vacuum_entity_id=_VAC)["main_brush"] = {
        "reset_at_usage_hours": 100.0, "reset_at": "2026-01-01"}
    result = mnt.get_maintenance_remaining(
        vacuum_entity_id=_VAC, component="main_brush", interval_hours=150.0)
    assert result["used_since_reset_hours"] == pytest.approx(20.0)
    assert result["remaining_hours"] == pytest.approx(130.0)
    assert result["source_available"] is True


def test_remaining_no_source(mnt, manager, monkeypatch):
    """[MNT-10]"""
    _caps(manager, monkeypatch, {})
    result = mnt.get_maintenance_remaining(
        vacuum_entity_id=_VAC, component="main_brush", interval_hours=150.0)
    assert result["source_available"] is False
    assert result["remaining_hours"] == pytest.approx(150.0)


def test_upkeep_snapshot(mnt, manager, monkeypatch):
    """[MNT-11]"""
    _caps(manager, monkeypatch, {})
    snap = mnt.get_upkeep_snapshot(vacuum_entity_id=_VAC)
    assert isinstance(snap, dict)
    assert snap["replacement_items"] == []
    assert snap["maintenance_items"] == []
    assert snap["highest_priority_status"] == "good"


def test_upkeep_snapshot_with_component(mnt, manager, hass, monkeypatch):
    """[MNT-12] an adapter maintenance component drives the replacement-item loop."""
    from custom_components.eufy_vacuum.adapters.registry import register_adapter_config
    register_adapter_config(_VAC, {
        "adapter_id": "test", "source": "test",
        "maintenance_components": {"main_brush": {"label": "Main Brush"}},
    })
    _caps(manager, monkeypatch, {"main_brush": _SRC})
    # remaining-life 40 / 300 h total = 13% → replacement_status "warning" (%-based, issue #38)
    hass.states.async_set(_SRC, "40", {"usage_hours": 260, "total_life_hours": 300})

    snap = mnt.get_upkeep_snapshot(vacuum_entity_id=_VAC)
    items = {i["component"]: i for i in snap["replacement_items"]}
    assert "main_brush" in items
    assert items["main_brush"]["status"] == "warning"
    assert snap["highest_priority_status"] in {"warning", "replace_soon", "replace_now"}


def test_replacement_life_falls_back_to_the_declared_interval(mnt, manager, hass, monkeypatch):
    """[MNT-12c] issue #51: no `total_life_hours` attribute -> use the adapter's own.

    `total_life_hours` is a robovac_mqtt attribute. Roborock's consumable sensors
    publish the remaining hours and nothing else, so `remaining_percent` stayed
    None on EVERY Roborock part and `replacement_status` returned "unknown" for
    all of them -- 6 items, 6 "attention", 0 healthy, with "232.3 hours
    remaining" printed next to the word Unknown.

    The numbers here are the reporter's, from his vendor dump:
    `mainBrushWorkTime` 243607 s = 67.67 h used, against the 300 h life this
    adapter declares -- and 300 - 67.67 = 232.33, exactly what his card showed.
    77% is comfortably "good", which is the whole point: nothing was ever wrong
    with the part.
    """
    from custom_components.eufy_vacuum.adapters.registry import register_adapter_config
    register_adapter_config(_VAC, {
        "adapter_id": "test", "source": "test",
        "maintenance_components": {
            "main_brush": {"label": "Main Brush", "default_interval_hours": 300.0},
        },
    })
    _caps(manager, monkeypatch, {"main_brush": _SRC})
    hass.states.async_set(_SRC, "232.3")  # no attributes at all, as Roborock sends

    items = {i["component"]: i
             for i in mnt.get_upkeep_snapshot(vacuum_entity_id=_VAC)["replacement_items"]}
    assert items["main_brush"]["total_life_hours"] == 300.0
    assert items["main_brush"]["remaining_percent"] == 77.43
    assert items["main_brush"]["status"] == "good"
    # THE OTHER HALF OF THE SAME EUFY-ISM, and it shipped broken for a year because
    # this test asserted the denominator and not the numerator. `usage_hours` is a
    # robovac_mqtt attribute too; reading only the attribute left it None on every
    # countdown brand, and the card rendered that as "0 hours used of 300 hours"
    # beside a perfectly correct 77%. The reporter's own figure is in the docstring
    # above -- 67.67 h used -- and nothing here ever checked it.
    assert items["main_brush"]["usage_hours"] == pytest.approx(67.7, abs=0.05)


def test_replacement_life_prefers_the_attribute_over_the_declaration(
    mnt, manager, hass, monkeypatch
):
    """[MNT-12d] the fallback is a fallback -- a published attribute still wins.

    Eufy publishes `total_life_hours`, so it must be untouched by MNT-12c. Uses a
    declared interval that DISAGREES with the attribute, because agreeing values
    cannot tell the two paths apart.
    """
    from custom_components.eufy_vacuum.adapters.registry import register_adapter_config
    register_adapter_config(_VAC, {
        "adapter_id": "test", "source": "test",
        "maintenance_components": {
            "main_brush": {"label": "Main Brush", "default_interval_hours": 999.0},
        },
    })
    _caps(manager, monkeypatch, {"main_brush": _SRC})
    hass.states.async_set(_SRC, "40", {"usage_hours": 260, "total_life_hours": 300})

    items = {i["component"]: i
             for i in mnt.get_upkeep_snapshot(vacuum_entity_id=_VAC)["replacement_items"]}
    assert items["main_brush"]["total_life_hours"] == 300.0
    assert items["main_brush"]["status"] == "warning"


def test_replacement_with_no_life_anywhere_stays_unknown(mnt, manager, hass, monkeypatch):
    """[MNT-12e] no attribute AND no declared interval -> still "unknown".

    The fallback must not manufacture a denominator. An item nothing can measure
    is unknown, and unknown is what the card needs in order to say so instead of
    printing "0% remaining".
    """
    from custom_components.eufy_vacuum.adapters.registry import register_adapter_config
    register_adapter_config(_VAC, {
        "adapter_id": "test", "source": "test",
        "maintenance_components": {"main_brush": {"label": "Main Brush"}},
    })
    _caps(manager, monkeypatch, {"main_brush": _SRC})
    hass.states.async_set(_SRC, "232.3")

    items = {i["component"]: i
             for i in mnt.get_upkeep_snapshot(vacuum_entity_id=_VAC)["replacement_items"]}
    assert items["main_brush"]["total_life_hours"] is None
    assert items["main_brush"]["remaining_percent"] is None
    assert items["main_brush"]["status"] == "unknown"


def test_maintenance_only_component_excluded_from_replacements(mnt, manager, hass, monkeypatch):
    """[MNT-12b] a maintenance_only component is surfaced ONLY as a Maintenance item,
    never a Replacement row, and contributes no Replacement status (issue #38 tray)."""
    from custom_components.eufy_vacuum.adapters.registry import register_adapter_config
    register_adapter_config(_VAC, {
        "adapter_id": "test", "source": "test",
        "maintenance_components": {
            "cleaning_tray": {"label": "Cleaning Tray", "maintenance_only": True},
        },
    })
    _caps(manager, monkeypatch, {"cleaning_tray": _SRC})
    # Freshly reset (100%): the old absolute-hours bug would have flagged this warning.
    hass.states.async_set(_SRC, "30", {"usage_hours": 0, "total_life_hours": 30})

    snap = mnt.get_upkeep_snapshot(vacuum_entity_id=_VAC)
    replacement = {i["component"] for i in snap["replacement_items"]}
    maintenance = {i["component"] for i in snap["maintenance_items"]}
    assert "cleaning_tray" not in replacement
    assert "cleaning_tray" in maintenance
    assert snap["attention_count"] == 0


def test_guide_only_component_regime_gated(mnt, manager, monkeypatch):
    """[MNT-12c] a guide-only cleanable (maintenance_only + no sensor) is surfaced ONLY when
    the model's REGIME documents it — so a station component shows on a station model and
    stays hidden on a base robot. Sensor-backed ones always show.

    WAS family-gated until 2026-09-12. The gate is the same idea against a sharper key: a
    regime is MEASURED from the model's hardware, where a family was a name someone assigned.
    """
    from custom_components.eufy_vacuum.adapters.registry import register_adapter_config
    monkeypatch.setattr(mnt, "_get_upkeep_model_meta", lambda **kw: {"code": "test.model"})
    register_adapter_config(_VAC, {
        "adapter_id": "test", "source": "test",
        "maintenance_components": {
            "main_brush": {"label": "Main Brush", "sensor_suffix": "x"},        # sensor-backed
            "mop": {"label": "Mop", "maintenance_only": True},                  # guide-only, in regime
            "cleaning_tray": {"label": "Cleaning Tray", "maintenance_only": True},  # NOT in regime
        },
        "upkeep_catalog": {
            "model_key_regimes": {"test.model": "cloth|charge_only|no"},
            "key_guides": {"cloth|charge_only|no": {
                "mop": {"steps": ["mop.cloth_module_off"], "notes": []},
                "main_brush": {"steps": ["access.brush_guard"], "notes": []},
            }},
        },
    })
    _caps(manager, monkeypatch, {})

    comps = {i["component"] for i in mnt.get_upkeep_snapshot(vacuum_entity_id=_VAC)["maintenance_items"]}
    assert "main_brush" in comps          # sensor-backed -> always shown
    assert "mop" in comps                 # guide-only + in regime -> shown
    assert "cleaning_tray" not in comps   # guide-only + NOT in regime -> gated out


def test_an_unresolved_model_gates_the_cleanables_closed(mnt, manager, monkeypatch):
    """[MNT-12d] no regime means the hardware is UNKNOWN, and unknown must not mean "show
    everything". The retired prose routing had a `standard` family to fall back on, so an
    unrecognised model still landed on real content; a regime has no generic member. Without
    this gate an unknown model renders every cleanable ever declared — a cleaning tray on a
    robot that may have no dock at all.
    """
    from custom_components.eufy_vacuum.adapters.registry import register_adapter_config
    monkeypatch.setattr(mnt, "_get_upkeep_model_meta", lambda **kw: {"code": "who.knows"})
    register_adapter_config(_VAC, {
        "adapter_id": "test", "source": "test",
        "maintenance_components": {
            "main_brush": {"label": "Main Brush", "sensor_suffix": "x"},
            "cleaning_tray": {"label": "Cleaning Tray", "maintenance_only": True},
        },
        "upkeep_catalog": {
            "model_key_regimes": {"test.model": "cloth|charge_only|no"},
            "key_guides": {"cloth|charge_only|no": {"main_brush": {"steps": ["s"], "notes": []}}},
        },
    })
    _caps(manager, monkeypatch, {})

    comps = {i["component"] for i in mnt.get_upkeep_snapshot(vacuum_entity_id=_VAC)["maintenance_items"]}
    assert "main_brush" in comps, "sensor-backed rows are honest for any model"
    assert "cleaning_tray" not in comps, "an unresolved model must not be shown a dock part"


def _caps_with_entities(manager, monkeypatch, entities):
    """Capabilities mock that also carries the adapter 'entities' map."""
    payload = {"maintenance_sources": {}, "sources": {}, "entities": entities}
    monkeypatch.setattr(manager, "get_vacuum_capabilities", lambda **kw: payload)
    monkeypatch.setattr(manager, "get_vacuum_capabilities_snapshot", lambda **kw: payload)


def test_upkeep_snapshot_device_totals_and_firmware(mnt, manager, hass, monkeypatch):
    """[MNT-15]"""
    _caps_with_entities(manager, monkeypatch, {
        "total_cleaning_area": "sensor.alfred_total_cleaning_area",
        "total_cleaning_time": "sensor.alfred_total_cleaning_time",
        "total_cleaning_count": "sensor.alfred_total_cleaning_count",
        "dock_firmware_version": "sensor.alfred_dock_firmware_version",
    })
    hass.states.async_set("sensor.alfred_total_cleaning_area", "152.5")
    hass.states.async_set("sensor.alfred_total_cleaning_time", "36000")   # 10 h in seconds
    hass.states.async_set("sensor.alfred_total_cleaning_count", "42")
    hass.states.async_set("sensor.alfred_dock_firmware_version", "1.2.3")

    snap = mnt.get_upkeep_snapshot(vacuum_entity_id=_VAC)
    assert snap["device_totals"] == {"area_m2": 152.5, "time_s": 36000.0, "count": 42}
    assert snap["dock_firmware"] == "1.2.3"


def test_upkeep_snapshot_device_totals_absent(mnt, manager, monkeypatch):
    """[MNT-16]"""
    _caps_with_entities(manager, monkeypatch, {})
    snap = mnt.get_upkeep_snapshot(vacuum_entity_id=_VAC)
    assert snap["device_totals"] is None
    assert snap["dock_firmware"] is None


def test_upkeep_snapshot_device_totals_partial(mnt, manager, hass, monkeypatch):
    """[MNT-17] a placeholder/absent sensor → that field None; present ones still surface."""
    _caps_with_entities(manager, monkeypatch, {
        "total_cleaning_area": "sensor.alfred_total_cleaning_area",
        "total_cleaning_time": "sensor.alfred_total_cleaning_time",
        "dock_firmware_version": "sensor.alfred_dock_firmware_version",
    })
    hass.states.async_set("sensor.alfred_total_cleaning_area", "200")
    hass.states.async_set("sensor.alfred_total_cleaning_time", "unavailable")  # placeholder
    hass.states.async_set("sensor.alfred_dock_firmware_version", "unknown")    # placeholder
    # no total_cleaning_count entity declared at all

    snap = mnt.get_upkeep_snapshot(vacuum_entity_id=_VAC)
    assert snap["device_totals"] == {"area_m2": 200.0, "time_s": None, "count": None}
    assert snap["dock_firmware"] is None


def test_upkeep_item_guide_builds_sub_dicts(mnt):
    """[MNT-13] _get_upkeep_item_guide enriches a KEY guide with source model info +
    maintenance/replacement sub-dicts; display picks by item_kind.

    A key guide draws no line between cleaning a part and replacing it — the steps are what a
    person does with their hands either way — so both sub-dicts carry the same body. The prose
    routing this replaced had separate clean/replace frequencies; nothing emits those now.
    """
    from custom_components.eufy_vacuum.adapters.registry import register_adapter_config
    register_adapter_config(_VAC, {
        "adapter_id": "test", "source": "test",
        "upkeep_catalog": {
            "model_names": {"X8": "X8 Pro"},
            "model_key_regimes": {"X8": "cloth|charge_only|no"},
            "key_guides": {"cloth|charge_only|no": {"main_brush": {
                "steps": ["access.brush_guard", "tool.remove_tangled_hair"],
                "notes": ["note.side_brush_do_not_yank"],
            }}},
        },
    })
    guide = mnt._get_upkeep_item_guide(
        vacuum_entity_id=_VAC, model_code="X8",
        component="main_brush", item_kind="replacement")
    assert guide["available"] is True
    assert guide["source_model_name"] == "X8 Pro"
    assert guide["steps_keys"] == ["access.brush_guard", "tool.remove_tangled_hair"]
    assert guide["notes_keys"] == ["note.side_brush_do_not_yank"]
    # ADDITIVE ON THE WIRE: the prose fields stay present and EMPTY, so a card that has not
    # been rebuilt renders an empty guide rather than raising.
    assert guide["maintenance"]["steps"] == []
    assert guide["display"] == guide["replacement"]
    # a component the regime does not document has no guide -> None
    assert mnt._get_upkeep_item_guide(
        vacuum_entity_id=_VAC, model_code="X8",
        component="nope", item_kind="maintenance") is None
    # and an unknown MODEL has no regime -> None
    assert mnt._get_upkeep_item_guide(
        vacuum_entity_id=_VAC, model_code="ZZ",
        component="main_brush", item_kind="maintenance") is None


def test_reset_entity_suffix_states_hit(mnt, hass):
    """[MNT-14c] the adapter-declared entity_suffixes list is the PRIMARY route:
    a live states-table entry at button.{object_id}_{suffix} resolves directly
    (no token fallback needed); an unconfigured component resolves to None."""
    from custom_components.eufy_vacuum.adapters.registry import register_adapter_config
    register_adapter_config(_VAC, {
        "adapter_id": "test", "source": "test",
        "maintenance_components": {"main_brush": {"reset_button": {
            "entity_suffixes": ["reset_main_brush", "main_brush_reset"],
            "token_sets": [],
        }}},
    })
    # First declared suffix is present in the states table → returned as-is.
    hass.states.async_set("button.alfred_reset_main_brush", "idle")
    assert mnt._get_replacement_reset_entity(
        vacuum_entity_id=_VAC, component="main_brush",
    ) == "button.alfred_reset_main_brush"
    # A component with no reset_button config falls through every route → None.
    assert mnt._get_replacement_reset_entity(
        vacuum_entity_id=_VAC, component="ghost",
    ) is None


def test_reset_entity_suffix_registry_hit(mnt, hass):
    """[MNT-14d] the entity_suffixes primary route also resolves via the entity
    registry when there is no live state (registry.async_get branch) — the
    suffix-built entity_id is returned even though hass.states has nothing."""
    from homeassistant.helpers import entity_registry as er
    from custom_components.eufy_vacuum.adapters.registry import register_adapter_config
    register_adapter_config(_VAC, {
        "adapter_id": "test", "source": "test",
        "maintenance_components": {"main_brush": {"reset_button": {
            "entity_suffixes": ["reset_main_brush", "main_brush_reset"],
            "token_sets": [],
        }}},
    })
    # No hass.states set — only a registry entry whose entity_id matches the
    # suffix-built id button.alfred_reset_main_brush.
    er.async_get(hass).async_get_or_create(
        "button", "eufy_vacuum", "alfred_reset_main_brush",
        suggested_object_id="alfred_reset_main_brush",
    )
    assert hass.states.get("button.alfred_reset_main_brush") is None
    assert mnt._get_replacement_reset_entity(
        vacuum_entity_id=_VAC, component="main_brush",
    ) == "button.alfred_reset_main_brush"


def test_reset_entity_token_fallback(mnt, hass):
    """[MNT-14] when no reset_button entity_suffix matches, the token_sets
    registry fallback resolves a differently-named reset button."""
    from homeassistant.helpers import entity_registry as er
    from custom_components.eufy_vacuum.adapters.registry import register_adapter_config
    register_adapter_config(_VAC, {
        "adapter_id": "test", "source": "test",
        "maintenance_components": {"main_brush": {"reset_button": {
            "entity_suffixes": ["reset_main_brush"],   # absent
            "token_sets": [["reset", "main", "brush"]],
        }}},
    })
    # The real reset button, differently named, resolved via the token fallback.
    er.async_get(hass).async_get_or_create(
        "button", "eufy_vacuum", "alfred_reset_main_brush_counter",
        suggested_object_id="alfred_reset_main_brush_counter",
    )
    assert mnt._get_replacement_reset_entity(
        vacuum_entity_id=_VAC, component="main_brush",
    ) == "button.alfred_reset_main_brush_counter"


def test_reset_entity_rescued_by_translation_key_on_a_localized_install(
    mnt, hass, mock_config_entry
):
    """[MNT-14b] issue #51: a German reset button, reached by its upstream key.

    The act path had two rungs and both are English: the derived suffix, then token
    sets like ["reset","main","brush"]. On a German install the button is
    `..._hauptbursten_verbrauchsmaterial_zurucksetzen` — it contains no "reset" — so
    every consumable reported `can_reset: false` while the buttons plainly existed.
    Widening the scope buys nothing: the PREFIX is correct there, the rest is German.

    No new vocabulary is needed. Roborock's declared entity_suffixes are
    byte-identical to its upstream translation_keys, which is the same assumption the
    read path already rests on.
    """
    from homeassistant.helpers import entity_registry as er
    from custom_components.eufy_vacuum.adapters.registry import register_adapter_config
    register_adapter_config(_VAC, {
        "adapter_id": "test", "source": "test",
        "maintenance_components": {"main_brush": {"reset_button": {
            "entity_suffixes": ["reset_main_brush_consumable"],
            "token_sets": [["reset", "main", "brush"]],
        }}},
    })
    mock_config_entry.add_to_hass(hass)
    reg = er.async_get(hass)
    # The vacuum and its button share a config entry — the sibling scope the rescue
    # searches. Without the vacuum's own entry there are no siblings to search.
    reg.async_get_or_create(
        "vacuum", "roborock", "uid_vac",
        suggested_object_id="alfred", config_entry=mock_config_entry,
    )
    reg.async_get_or_create(
        "button", "roborock", "uid_reset_main",
        suggested_object_id="alfred_hauptbursten_verbrauchsmaterial_zurucksetzen",
        translation_key="reset_main_brush_consumable",
        config_entry=mock_config_entry,
    )

    assert mnt._get_replacement_reset_entity(
        vacuum_entity_id=_VAC, component="main_brush",
    ) == "button.alfred_hauptbursten_verbrauchsmaterial_zurucksetzen"


def test_reset_entity_disabled_is_not_offered(mnt, hass, mock_config_entry):
    """[MNT-14c] DISABLED is not MISSING, and must not be offered as pressable.

    All four of the reporter's reset buttons are disabled in the registry, and
    `er.async_entries_for_config_entry` RETURNS disabled entries — so a rescue that
    ignored the flag would bind one and `button.press` would hit the silent
    log_missing no-op that made the mop-intensity failure invisible. Reporting the
    control unavailable is the honest answer; the warning names the entity so the
    user can enable it.
    """
    from homeassistant.helpers import entity_registry as er
    from homeassistant.helpers.entity_registry import RegistryEntryDisabler
    from custom_components.eufy_vacuum.adapters.registry import register_adapter_config
    register_adapter_config(_VAC, {
        "adapter_id": "test", "source": "test",
        "maintenance_components": {"main_brush": {"reset_button": {
            "entity_suffixes": ["reset_main_brush_consumable"],
            "token_sets": [],
        }}},
    })
    mock_config_entry.add_to_hass(hass)
    reg = er.async_get(hass)
    reg.async_get_or_create(
        "vacuum", "roborock", "uid_vac2",
        suggested_object_id="alfred", config_entry=mock_config_entry,
    )
    reg.async_get_or_create(
        "button", "roborock", "uid_reset_disabled",
        suggested_object_id="alfred_hauptbursten_verbrauchsmaterial_zurucksetzen",
        translation_key="reset_main_brush_consumable",
        config_entry=mock_config_entry,
        disabled_by=RegistryEntryDisabler.USER,
    )

    assert mnt._get_replacement_reset_entity(
        vacuum_entity_id=_VAC, component="main_brush",
    ) is None


def test_reset_entity_maintenance_filter_excludes(mnt, hass):
    """[MNT-14b] a token match whose id contains 'maintenance' is excluded
    (the reset button is the upstream counter-reset, not our own sensor)."""
    from homeassistant.helpers import entity_registry as er
    from custom_components.eufy_vacuum.adapters.registry import register_adapter_config
    register_adapter_config(_VAC, {
        "adapter_id": "test", "source": "test",
        "maintenance_components": {"main_brush": {"reset_button": {
            "entity_suffixes": ["reset_main_brush"],   # absent
            "token_sets": [["reset", "main", "brush"]],
        }}},
    })
    # The only token match carries 'maintenance' → filtered out → None.
    er.async_get(hass).async_get_or_create(
        "button", "eufy_vacuum", "alfred_reset_main_brush_maintenance",
        suggested_object_id="alfred_reset_main_brush_maintenance",
    )
    assert mnt._get_replacement_reset_entity(
        vacuum_entity_id=_VAC, component="main_brush",
    ) is None


# ---------------------------------------------------------------------------
# RF-33 cont'd: get_upkeep_snapshot must never trigger capability detection
# ---------------------------------------------------------------------------

def test_upkeep_snapshot_never_triggers_capability_detection(mnt, manager):
    """[MNT-18] get_upkeep_snapshot used to call get_vacuum_capabilities(refresh=False)
    directly -- non-inert despite refresh=False (self-heals/writes when no stored
    snapshot exists, exactly this vacuum's state). It now reads
    get_vacuum_capabilities_snapshot, so a call with nothing ever detected must
    return an empty-shaped snapshot WITHOUT writing to manager.data['capabilities']."""
    manager.ensure_vacuum_record(vacuum_entity_id=_VAC)
    assert _VAC not in manager.data.get("capabilities", {})

    snap = mnt.get_upkeep_snapshot(vacuum_entity_id=_VAC)

    assert snap["replacement_items"] == []
    assert snap["maintenance_items"] == []
    assert _VAC not in manager.data.get("capabilities", {})  # still no write


def test_maintenance_remaining_reuses_passed_capabilities(mnt, manager, monkeypatch):
    """[MNT-19] get_upkeep_snapshot's per-component loop calls get_maintenance_remaining
    internally -- that used to be a THIRD independent get_vacuum_capabilities(refresh=False)
    call site, re-deriving the same source_entity get_upkeep_snapshot had already
    resolved. Passing `capabilities` must skip the internal fetch entirely."""
    def _boom(**kw):
        raise AssertionError("must not re-fetch capabilities when a dict was passed in")
    monkeypatch.setattr(manager, "get_vacuum_capabilities", _boom)

    result = mnt.get_maintenance_remaining(
        vacuum_entity_id=_VAC, component="main_brush", interval_hours=150.0,
        capabilities={"maintenance_sources": {"main_brush": _SRC}, "sources": {}},
    )
    assert result["source_entity"] == _SRC


def test_maintenance_remaining_default_still_self_heals(mnt, manager, monkeypatch):
    """[MNT-19b] omitting `capabilities` (the sensor entity's + service's call
    shape) must still fall back to get_vacuum_capabilities(refresh=False) — a
    maintenance sensor's own poll may be the first thing to run for a
    freshly-added vacuum and needs the self-heal detection, unlike
    get_upkeep_snapshot's own (now read-only) call."""
    calls: list[str] = []
    def _tracked(**kw):
        calls.append(kw.get("vacuum_entity_id"))
        return {"maintenance_sources": {"main_brush": _SRC}, "sources": {}}
    monkeypatch.setattr(manager, "get_vacuum_capabilities", _tracked)

    result = mnt.get_maintenance_remaining(
        vacuum_entity_id=_VAC, component="main_brush", interval_hours=150.0,
    )
    assert calls == [_VAC]
    assert result["source_entity"] == _SRC


def test_upkeep_snapshot_overdue_consumable_does_not_raise(hass, manager, mnt, monkeypatch):
    """[MNT-20] an OVERDUE consumable (NEGATIVE hours) must not crash the snapshot.

    Regression for a TypeError found in a real user's diagnostics rather than by
    audit (Roborock Q5, issue #46 thread):

        upkeep_snapshot_error: TypeError("unsupported operand type(s) for +:
                                         'NoneType' and 'str'")

    The four summary call sites guarded the INPUT (``x is not None``) and then
    concatenated ``_hours_text(x) + " suffix"`` — but _hours_text also returns
    None for a NEGATIVE number, which is exactly what an upstream `*_time_left`
    sensor reports once a part is past its service life. The guard was true, the
    helper still returned None, and the concatenation raised.

    It matters beyond diagnostics: diagnostics.py wraps this call in try/except
    (which is the only reason it showed up as a field instead of a stack trace),
    but get_upkeep_snapshot is ALSO on get_dashboard_snapshot's path with no
    guard — so one overdue brush took out the card's whole data source.

    [MNT-3] already asserts _hours_text(-1) is None; nothing exercised a CALL
    SITE with one. This test is deliberately at the snapshot level for that
    reason. State "-12" with no total_life_hours leaves remaining_percent None,
    so remaining_summary takes the hours branch too — both broken sites at once.
    """
    from custom_components.eufy_vacuum.adapters.registry import register_adapter_config
    register_adapter_config(_VAC, {
        "adapter_id": "test", "source": "test",
        "maintenance_components": {"main_brush": {"label": "Main Brush"}},
    })
    _caps(manager, monkeypatch, {"main_brush": _SRC})
    hass.states.async_set(_SRC, "-12", {"usage_hours": -5})

    snap = mnt.get_upkeep_snapshot(vacuum_entity_id=_VAC)

    item = {i["component"]: i for i in snap["replacement_items"]}["main_brush"]
    assert item["remaining_summary"] is None
    assert item["usage_summary"] is None
    # the row still reports, so the card renders an overdue part rather than
    # losing the entire snapshot
    assert item["remaining_hours"] == -12.0


def _clock_candidates(manager, hass, vac="vacuum.alfred"):
    return manager.maintenance.get_maintenance_source_candidates(vacuum_entity_id=vac)


def test_the_current_clock_is_not_labelled_a_part_counter(hass, manager, mock_config_entry):
    """[MNT-CLK-1] THE BUG REAL DATA CAUGHT, and reasoning did not.

    A part counter SATURATES — upstream clamps it at zero (`max(0, max_life - usage)`), so an
    overdue part that has not been reset freezes the clock for every component at once. Those
    entities stay selectable (Chris ruled so) but carry a caveat.

    The naive test for "is this a part counter" is "is it some component's source" — and the
    LIFETIME CLOCK IS, for every uncounted component, because that is its whole job. So that
    test hangs the saturation caveat on the one candidate that cannot saturate. Listing real
    candidates across three machines showed `sensor.ivy_total_cleaning_time` labelled
    "part counter for cleaning_tray"; nothing in the unit tests could see it, because they
    never had a clock set.

    THE INPUT THAT MAKES THIS RED: drop the `_src != _current_clock` guard.
    """
    from custom_components.eufy_vacuum.const import ENTITY_OVERRIDES_KEY
    from custom_components.eufy_vacuum.core.capabilities import MAINTENANCE_CLOCK_ROLE

    clock = "sensor.alfred_total_cleaning_time"
    part = "sensor.alfred_filter_remaining"

    # The candidate sweep is scoped to the vacuum's OWN device / config entry (live:ENT-5), so
    # the siblings have to be REGISTERED, not merely given states. Without the vacuum's own
    # entry there are no siblings to search and the list comes back empty — which is exactly how
    # the first draft of this test passed its own ablation.
    from homeassistant.helpers import entity_registry as er

    mock_config_entry.add_to_hass(hass)
    reg = er.async_get(hass)
    reg.async_get_or_create(
        "vacuum", "eufy", "uid_vac_clk",
        suggested_object_id="alfred", config_entry=mock_config_entry,
    )
    reg.async_get_or_create(
        "sensor", "eufy", "uid_total_cleaning_time",
        suggested_object_id="alfred_total_cleaning_time", config_entry=mock_config_entry,
    )
    reg.async_get_or_create(
        "sensor", "eufy", "uid_filter_remaining",
        suggested_object_id="alfred_filter_remaining", config_entry=mock_config_entry,
    )
    hass.states.async_set(clock, "41.8", {"device_class": "duration", "unit_of_measurement": "h"})
    hass.states.async_set(part, "360", {"device_class": "duration", "unit_of_measurement": "h"})

    manager.data.setdefault(ENTITY_OVERRIDES_KEY, {})["vacuum.alfred"] = {
        MAINTENANCE_CLOCK_ROLE: clock
    }
    manager.data.setdefault("capabilities", {}).setdefault("vacuum.alfred", {})[
        "maintenance_sources"
    ] = {"filter": part, "cleaning_tray": clock, "mop": clock}

    by_id = {c["entity_id"]: c for c in _clock_candidates(manager, hass)}

    # ⚠ ASSERT PRESENCE FIRST. An earlier draft wrapped everything in `if clock in by_id:` and
    # PASSED THE ABLATION — with the guard removed the candidate list was simply empty, so every
    # assertion was skipped and the test proved nothing. `f/claim_must_be_able_to_bite`: a test
    # that cannot name the input that reddens it is a preference.
    assert clock in by_id, (
        f"the clock is not even a candidate, so this test cannot bite: {sorted(by_id)}"
    )
    assert part in by_id, (
        f"the part counter is not even a candidate, so this test cannot bite: {sorted(by_id)}"
    )

    assert by_id[clock]["caveat_key"] is None, (
        "the CURRENT clock must not be labelled a part counter — it is the source for every "
        "uncounted component by design, which is not the same as counting one part"
    )
    assert by_id[clock]["is_current"] is True
    assert by_id[clock]["bound_components"] == []

    assert by_id[part]["caveat_key"] == "maintenance.clock_candidate.saturates_at_zero"
    assert by_id[part]["bound_components"] == ["filter"]
    assert by_id[part]["is_current"] is False
