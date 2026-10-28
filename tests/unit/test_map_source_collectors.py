"""Unit tests for the map_state_source candidate COLLECTORS.

The collectors in ``mapping/map_source_runtime.py`` are the HA-aware glue that
gathers candidate ROOTS (the in-memory provider objects the defensive introspectors
then walk) from ``hass.data[domain]``, each config-entry's ``runtime_data``, and — for
Roborock — the live map IMAGE entity object. They never raise: a config-entry lookup
that blows up degrades to the remaining sources.

Covered here (previously ~0%):
  [MSC-1] eufy_inmem_candidates  — hass.data bucket + per-entry runtime_data; degrade.
  [MSC-2] roborock_candidates    — image entity + runtime_data + hass.data bucket; degrade.
  [MSC-3] image_entity_object    — entity-component registry lookup vs None.

These assert the documented return shape ``[(origin_label, key, root_obj), ...]`` — the
exact tuples the introspectors consume — not merely "doesn't crash".
"""
from custom_components.eufy_vacuum.mapping.map_source_runtime import (
    dreame_coordinator,
    eufy_inmem_candidates,
    image_entity_object,
    roborock_candidates,
)

# The collectors carry NO brand default — the adapter ALWAYS declares hass_data_domain
# (adapters/eufy/adapter.py + adapters/roborock/adapter.py), so the tests declare it too.
_EUFY = {"hass_data_domain": "robovac_mqtt"}
_RB = {"hass_data_domain": "roborock"}


# ---------------------------------------------------------------------------
# Minimal fakes: just enough hass surface for the collectors.
# The collectors touch ONLY hass.data (a dict) and
# hass.config_entries.async_entries(domain).
# ---------------------------------------------------------------------------

class _Entry:
    """A fake config entry exposing .entry_id and (optionally) .runtime_data."""

    def __init__(self, entry_id, runtime_data=None, has_runtime=True):
        self.entry_id = entry_id
        if has_runtime:
            self.runtime_data = runtime_data


class _ConfigEntries:
    """Fake hass.config_entries — async_entries(domain) returns seeded entries,
    or raises when ``raise_exc`` is set (defensive-degradation path)."""

    def __init__(self, entries=None, raise_exc=None):
        self._entries = entries or []
        self._raise_exc = raise_exc

    def async_entries(self, domain):
        if self._raise_exc is not None:
            raise self._raise_exc
        return list(self._entries)


class _ImageComponent:
    """Fake entity_components['image'] with a get_entity(entity_id) map lookup."""

    def __init__(self, entities=None, raise_exc=None):
        self._entities = entities or {}
        self._raise_exc = raise_exc

    def get_entity(self, entity_id):
        if self._raise_exc is not None:
            raise self._raise_exc
        return self._entities.get(entity_id)


class _Hass:
    """Minimal hass: a .data dict + .config_entries with async_entries(domain)."""

    def __init__(self, data=None, entries=None, raise_exc=None):
        self.data = {} if data is None else data
        self.config_entries = _ConfigEntries(entries=entries, raise_exc=raise_exc)


# ---------------------------------------------------------------------------
# [MSC-1] eufy_inmem_candidates
# ---------------------------------------------------------------------------

def test_eufy_inmem_hass_data_bucket_only():
    """[MSC-1] a hass.data[domain] bucket -> the ('hass_data', domain, bucket) candidate."""
    bucket = {"coordinators": ["x"]}
    hass = _Hass(data={"robovac_mqtt": bucket})
    out = eufy_inmem_candidates(hass, _EUFY)
    assert out == [("hass_data", "robovac_mqtt", bucket)]
    # the third tuple element is the SAME object (a root to walk), not a copy
    assert out[0][2] is bucket


def test_eufy_inmem_runtime_data_only():
    """[MSC-1b] a config entry with runtime_data -> ('runtime_data', entry_id, rd)."""
    rd = object()
    hass = _Hass(entries=[_Entry("entry_abc", runtime_data=rd)])
    out = eufy_inmem_candidates(hass, _EUFY)
    assert out == [("runtime_data", "entry_abc", rd)]
    assert out[0][2] is rd


def test_eufy_inmem_both_sources_ordered():
    """[MSC-1c] both present -> hass_data candidate FIRST, then each runtime_data."""
    bucket = {"b": 1}
    rd1, rd2 = object(), object()
    hass = _Hass(
        data={"robovac_mqtt": bucket},
        entries=[_Entry("e1", rd1), _Entry("e2", rd2)],
    )
    out = eufy_inmem_candidates(hass, _EUFY)
    assert out == [
        ("hass_data", "robovac_mqtt", bucket),
        ("runtime_data", "e1", rd1),
        ("runtime_data", "e2", rd2),
    ]


def test_eufy_inmem_runtime_data_none_skipped():
    """[MSC-1d] an entry whose runtime_data is None contributes no candidate."""
    hass = _Hass(entries=[
        _Entry("e_none", runtime_data=None),     # rd is None -> skipped
        _Entry("e_real", runtime_data=object()),
    ])
    out = eufy_inmem_candidates(hass, _EUFY)
    assert [(o, k) for o, k, _ in out] == [("runtime_data", "e_real")]


def test_eufy_inmem_neither_present_empty():
    """[MSC-1e] no bucket and no entries -> []."""
    hass = _Hass()
    assert eufy_inmem_candidates(hass, _EUFY) == []


def test_eufy_inmem_custom_domain_from_cfg():
    """[MSC-1f] the DECLARED hass_data_domain selects the bucket — the collector carries no
    brand default, so a different domain's bucket is NOT consulted."""
    bucket = {"x": 1}
    hass = _Hass(data={"my_fork": bucket})
    out = eufy_inmem_candidates(hass, {"hass_data_domain": "my_fork"})
    assert out == [("hass_data", "my_fork", bucket)]
    assert eufy_inmem_candidates(_Hass(data={"robovac_mqtt": bucket}),
                                 {"hass_data_domain": "my_fork"}) == []


def test_eufy_inmem_no_domain_declared_returns_empty():
    """[MSC-1j] no hass_data_domain -> [] even with a bucket + entries present (no brand
    fallback: an adapter that declares no domain can't locate candidates)."""
    hass = _Hass(data={"robovac_mqtt": {"x": 1}}, entries=[_Entry("e", runtime_data=object())])
    assert eufy_inmem_candidates(hass, {}) == []


def test_eufy_inmem_async_entries_raises_degrades_to_hass_data():
    """[MSC-1g] async_entries() raising degrades to [] for the entry source but STILL
    returns the hass_data candidate (never aborts the whole collection)."""
    bucket = {"b": 1}
    hass = _Hass(data={"robovac_mqtt": bucket}, raise_exc=RuntimeError("HA internals shifted"))
    out = eufy_inmem_candidates(hass, _EUFY)
    assert out == [("hass_data", "robovac_mqtt", bucket)]


def test_eufy_inmem_async_entries_raises_no_bucket_empty():
    """[MSC-1h] async_entries() raising and no bucket -> [] (clean degrade, no raise)."""
    hass = _Hass(raise_exc=ValueError("boom"))
    assert eufy_inmem_candidates(hass, _EUFY) == []


def test_eufy_inmem_hass_data_none():
    """[MSC-1i] hass.data is None -> the (hass.data or {}) guard yields no bucket -> []."""
    hass = _Hass()
    hass.data = None
    assert eufy_inmem_candidates(hass, _EUFY) == []


# ---------------------------------------------------------------------------
# [MSC-2] roborock_candidates
# ---------------------------------------------------------------------------

def test_roborock_image_entity_candidate():
    """[MSC-2] when image_entity_id resolves to an object -> the image_entity candidate
    is FIRST (the parsed MapData most likely lives on the image entity)."""
    ent = object()
    hass = _Hass(data={"entity_components": {"image": _ImageComponent(
        {"image.ivy_map": ent})}})
    out = roborock_candidates(hass, _RB, image_entity_id="image.ivy_map")
    assert out == [("image_entity", "image.ivy_map", ent)]
    assert out[0][2] is ent


def test_roborock_image_entity_unresolved_omitted():
    """[MSC-2b] image_entity_id given but get_entity returns None -> no image candidate."""
    hass = _Hass(data={"entity_components": {"image": _ImageComponent({})}})
    out = roborock_candidates(hass, _RB, image_entity_id="image.missing")
    assert out == []


def test_roborock_runtime_data_and_hass_data_order():
    """[MSC-2c] full collection order: image_entity, then each runtime_data, then hass_data."""
    ent, rd = object(), object()
    bucket = {"b": 1}
    hass = _Hass(
        data={
            "roborock": bucket,
            "entity_components": {"image": _ImageComponent({"image.ivy_map": ent})},
        },
        entries=[_Entry("e1", rd)],
    )
    out = roborock_candidates(hass, _RB, image_entity_id="image.ivy_map")
    assert out == [
        ("image_entity", "image.ivy_map", ent),
        ("runtime_data", "e1", rd),
        ("hass_data", "roborock", bucket),
    ]


def test_roborock_no_image_id_runtime_and_bucket():
    """[MSC-2d] no image_entity_id -> just runtime_data + hass_data (declared domain 'roborock')."""
    rd = object()
    bucket = {"b": 1}
    hass = _Hass(data={"roborock": bucket}, entries=[_Entry("e1", rd)])
    out = roborock_candidates(hass, _RB)
    assert out == [
        ("runtime_data", "e1", rd),
        ("hass_data", "roborock", bucket),
    ]


def test_roborock_custom_domain_from_cfg():
    """[MSC-2e] the DECLARED hass_data_domain selects both entries+bucket (no brand default)."""
    rd = object()
    bucket = {"b": 1}
    hass = _Hass(data={"rr2": bucket}, entries=[_Entry("e1", rd)])
    out = roborock_candidates(hass, {"hass_data_domain": "rr2"})
    assert out == [
        ("runtime_data", "e1", rd),
        ("hass_data", "rr2", bucket),
    ]


def test_roborock_no_domain_declared_keeps_image_only():
    """[MSC-2g] no hass_data_domain -> the image candidate is still gathered (domain-independent),
    but the runtime_data / hass_data sources are skipped (no brand fallback)."""
    ent = object()
    hass = _Hass(
        data={"roborock": {"b": 1},
              "entity_components": {"image": _ImageComponent({"image.ivy_map": ent})}},
        entries=[_Entry("e1", object())],
    )
    out = roborock_candidates(hass, {}, image_entity_id="image.ivy_map")
    assert out == [("image_entity", "image.ivy_map", ent)]


def test_roborock_async_entries_raises_keeps_image_and_hass_data():
    """[MSC-2f] async_entries() raising degrades the entry source but STILL returns the
    image_entity and hass_data candidates (the introspector still has roots to walk)."""
    ent = object()
    bucket = {"b": 1}
    hass = _Hass(
        data={
            "roborock": bucket,
            "entity_components": {"image": _ImageComponent({"image.ivy_map": ent})},
        },
        raise_exc=RuntimeError("entries unavailable"),
    )
    out = roborock_candidates(hass, _RB, image_entity_id="image.ivy_map")
    assert out == [
        ("image_entity", "image.ivy_map", ent),
        ("hass_data", "roborock", bucket),
    ]


def test_roborock_runtime_data_none_skipped():
    """[MSC-2g] an entry with runtime_data None contributes nothing; bucket still added."""
    bucket = {"b": 1}
    hass = _Hass(data={"roborock": bucket}, entries=[_Entry("e_none", runtime_data=None)])
    out = roborock_candidates(hass, _RB)
    assert out == [("hass_data", "roborock", bucket)]


def test_roborock_empty_when_nothing_present():
    """[MSC-2h] no image id, no entries, no bucket -> []."""
    assert roborock_candidates(_Hass(), {}) == []


def test_roborock_hass_data_none():
    """[MSC-2i] hass.data None -> the (hass.data or {}) guard yields no bucket -> []
    (no image id given, no entries)."""
    hass = _Hass()
    hass.data = None
    assert roborock_candidates(hass, _RB) == []


# ---------------------------------------------------------------------------
# [MSC-3] image_entity_object
# ---------------------------------------------------------------------------

def test_image_entity_object_resolves():
    """[MSC-3] entity_components['image'].get_entity(id) -> the entity object."""
    ent = object()
    hass = _Hass(data={"entity_components": {"image": _ImageComponent(
        {"image.ivy_map": ent})}})
    assert image_entity_object(hass, "image.ivy_map") is ent


def test_image_entity_object_unknown_id_none():
    """[MSC-3b] an id the component doesn't know -> None."""
    hass = _Hass(data={"entity_components": {"image": _ImageComponent({})}})
    assert image_entity_object(hass, "image.nope") is None


def test_image_entity_object_no_entity_components():
    """[MSC-3c] no 'entity_components' bucket at all -> None (not a KeyError)."""
    assert image_entity_object(_Hass(), "image.ivy_map") is None


def test_image_entity_object_no_image_component():
    """[MSC-3d] entity_components present but no 'image' key -> None."""
    hass = _Hass(data={"entity_components": {}})
    assert image_entity_object(hass, "image.ivy_map") is None


def test_image_entity_object_get_entity_raises_none():
    """[MSC-3e] get_entity raising (defensive over HA internals) is swallowed -> None."""
    hass = _Hass(data={"entity_components": {"image": _ImageComponent(
        raise_exc=RuntimeError("registry shifted"))}})
    assert image_entity_object(hass, "image.ivy_map") is None


def test_image_entity_object_component_without_get_entity():
    """[MSC-3f] a component object lacking get_entity -> None (hasattr guard)."""
    class _NoGetEntity:
        pass

    hass = _Hass(data={"entity_components": {"image": _NoGetEntity()}})
    assert image_entity_object(hass, "image.ivy_map") is None


# ---------------------------------------------------------------------------
# [MSC-4] dreame_coordinator — route 1, the device -> config entry hop
#
# ISSUE #69 changed this hop from `device.config_entries` (deprecated in HA 2026.8,
# removed in 2027.10) to `device_config_entry_ids`. The function had NO tests, and its
# body is wrapped in a blanket `except Exception` — so a hop that raised, or returned
# nothing, would be swallowed and the "exactly one coordinator loaded" fallback would
# answer instead. The tests below therefore load TWO coordinators, which disables that
# fallback: anything that reaches it returns None and the test fails.
# ---------------------------------------------------------------------------

_DREAME = "dreame_vacuum"


class _Coord:
    def __init__(self, name):
        self.device = object()
        self.name = name


def _two_dreame_entries(hass):
    """A real device + entity registry with TWO loaded dreame coordinators.

    Returns (vacuum_entity_id, wanted_coordinator). The second coordinator exists only
    to make the single-coordinator fallback decline, so route 1 has to do the work.
    """
    from homeassistant.helpers import device_registry as dr, entity_registry as er
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    mine = MockConfigEntry(domain=_DREAME, entry_id="msc4_mine")
    mine.add_to_hass(hass)
    other = MockConfigEntry(domain=_DREAME, entry_id="msc4_other")
    other.add_to_hass(hass)

    device = dr.async_get(hass).async_get_or_create(
        config_entry_id=mine.entry_id, identifiers={(_DREAME, "msc4_duid")},
    )
    vac = er.async_get(hass).async_get_or_create(
        "vacuum", _DREAME, "msc4_uid",
        suggested_object_id="msc4", device_id=device.id, config_entry=mine,
    )

    wanted = _Coord("mine")
    hass.data[_DREAME] = {mine.entry_id: wanted, other.entry_id: _Coord("other")}
    return vac.entity_id, wanted, device


def test_msc4_route1_resolves_the_entry_that_owns_the_device(hass):
    """[MSC-4] With two coordinators loaded, only the device's own entry can answer.

    ABLATION: make `device_config_entry_ids` return an empty set and this goes red —
    the fallback declines at two coordinators, so there is nothing to mask the break.
    """
    vacuum_entity_id, wanted, _ = _two_dreame_entries(hass)

    got = dreame_coordinator(hass, vacuum_entity_id, None, _DREAME)

    assert got is wanted, "route 1 must pick the entry the device belongs to"


def test_msc4b_route1_emits_no_deprecation_report(hass):
    """[MSC-4b] The hop must not go through the deprecated property.

    The returned coordinator is the same either way, so the ANSWER cannot tell the two
    code paths apart — only the report can. `_report_deprecated_config_entries_property`
    is what prints the warning ISSUE #69 was filed about.

    ABLATION: put `device.config_entries` back in `dreame_coordinator` and this goes
    red while [MSC-4] stays green.
    """
    from homeassistant.helpers import device_registry as dr

    vacuum_entity_id, wanted, _ = _two_dreame_entries(hass)

    reports = []
    original = dr._report_deprecated_config_entries_property
    dr._report_deprecated_config_entries_property = (
        lambda *a, **k: reports.append(a) or original(*a, **k)
    )
    try:
        got = dreame_coordinator(hass, vacuum_entity_id, None, _DREAME)
    finally:
        dr._report_deprecated_config_entries_property = original

    assert got is wanted
    assert reports == [], f"deprecated property read on the dreame hop: {reports}"


# ---------------------------------------------------------------------------
# [MSC-5] eufy_inmem_candidates — PER-VACUUM scoping (issue #77)
#
# Two Eufy vacuums made every in-memory read answer with the first one. The bucket the
# collector returns is `hass.data[domain][entry_id]["coordinators"]` — a LIST per entry,
# and the bucket spans ENTRIES — so the attr-matching introspectors downstream stopped at
# whichever coordinator came first and used it for every vacuum: pose, rooms and raster.
#
# The shape below is the provider's real one, read from robovac_mqtt/__init__.py:
#     hass.data.setdefault(DOMAIN, {})
#     hass.data[DOMAIN][entry.entry_id] = {"coordinators": coordinators}
# and the id attr is EufyCleanCoordinator.device_id (the serial), which is also the
# (robovac_mqtt, <serial>) device-registry identifier eufy_store_path already keys on.
# ---------------------------------------------------------------------------

from custom_components.eufy_vacuum.mapping.map_source_runtime import (  # noqa: E402
    eufy_live_pose_from_candidates,
)

_EUFY_IDS = {"hass_data_domain": "robovac_mqtt", "device_id_attrs": ["device_id"]}


class _EufyCoord:
    """An EufyCleanCoordinator stand-in: a serial plus the two pose attrs the
    introspector matches on (PRESENCE, not value — the fork nulls the robot pixel
    while docked, which is why _is_pose_holder tests for the attrs existing)."""

    def __init__(self, device_id, robot, dock):
        self.device_id = device_id
        self._robot_pixel = robot
        self._dock_pixel = dock


def _two_vacuums_one_entry():
    """HAL and Cogsworth on ONE config entry — the reporter's setup."""
    hal = _EufyCoord("SERIAL_HAL", (10, 10), (1, 1))
    cogs = _EufyCoord("SERIAL_COGS", (90, 90), (99, 99))
    bucket = {"entry_1": {"coordinators": [hal, cogs]}}
    return _Hass(data={"robovac_mqtt": bucket}), hal, cogs


def _two_vacuums_two_entries():
    """The same two vacuums on SEPARATE config entries. The issue title says one
    account; the bucket is keyed by entry and the collector returns the WHOLE bucket,
    so the collision never depended on sharing one."""
    hal = _EufyCoord("SERIAL_HAL", (10, 10), (1, 1))
    cogs = _EufyCoord("SERIAL_COGS", (90, 90), (99, 99))
    bucket = {"entry_1": {"coordinators": [hal]}, "entry_2": {"coordinators": [cogs]}}
    return _Hass(data={"robovac_mqtt": bucket}), hal, cogs


def _pixel(cands):
    """The reader normalises a pixel tuple to a LIST, so compare like with like."""
    return _pose(cands).get("robot_pixel")


def _pose(cands):
    return eufy_live_pose_from_candidates(
        cands, robot_attrs=["_robot_pixel"], dock_attrs=["_dock_pixel"],
    )


def test_msc5_unscoped_reproduces_the_bug():
    """[MSC-5] THE DEFECT, pinned: with no serial both vacuums resolve to the FIRST
    coordinator. This is the pre-fix behaviour and the fallback path, so it must stay
    exactly as it was for single-vacuum installs — asserted, not merely tolerated."""
    hass, hal, cogs = _two_vacuums_one_entry()
    out = eufy_inmem_candidates(hass, _EUFY_IDS)              # no device_id
    assert [(o, k) for o, k, _ in out] == [("hass_data", "robovac_mqtt")]
    # The introspector walks that one root and stops at HAL — for every caller.
    assert _pixel(out) == list(hal._robot_pixel)
    assert _pixel(out) != list(cogs._robot_pixel)


def test_msc5b_each_serial_selects_its_own_coordinator():
    """[MSC-5b] THE FIX: each serial resolves to its own coordinator, one entry."""
    hass, hal, cogs = _two_vacuums_one_entry()
    for want in (hal, cogs):
        out = eufy_inmem_candidates(hass, _EUFY_IDS, device_id=want.device_id)
        assert len(out) == 1
        origin, key, root = out[0]
        assert (origin, key) == ("device", want.device_id)
        assert root is want
        assert _pixel(out) == list(want._robot_pixel)


def test_msc5c_scoping_works_across_config_entries():
    """[MSC-5c] and across SEPARATE entries — the defect never needed one account."""
    hass, hal, cogs = _two_vacuums_two_entries()
    # Unscoped: the whole bucket, so the walk still finds HAL for both.
    assert _pixel(eufy_inmem_candidates(hass, _EUFY_IDS)) == list(hal._robot_pixel)
    for want in (hal, cogs):
        out = eufy_inmem_candidates(hass, _EUFY_IDS, device_id=want.device_id)
        assert out[0][2] is want
        assert _pixel(out) == list(want._robot_pixel)


def test_msc5d_scoped_root_REPLACES_the_shared_roots():
    """[MSC-5d] the design decision, pinned. Returning the scoped root merely FIRST would
    leave the shared bucket behind it, and the introspectors fall through on a miss — so a
    vacuum whose own map is briefly absent would silently inherit its neighbour's. The
    scoped root must be the ONLY one, making a miss resolve to absent (the storage path
    behind it is per-vacuum keyed and answers correctly)."""
    hal = _EufyCoord("SERIAL_HAL", (10, 10), (1, 1))
    blind = _EufyCoord("SERIAL_BLIND", None, None)
    del blind._robot_pixel, blind._dock_pixel          # this vacuum's map is not loaded yet
    hass = _Hass(data={"robovac_mqtt": {"e": {"coordinators": [hal, blind]}}})

    out = eufy_inmem_candidates(hass, _EUFY_IDS, device_id="SERIAL_BLIND")
    assert [o for o, _, _ in out] == ["device"], "the shared bucket must not ride along"
    got = _pose(out)
    assert got["present"] is False and got["reason"] == "no_pose"
    assert got.get("robot_pixel") != list(hal._robot_pixel), "must never answer with the neighbour"


def test_msc5e_unknown_serial_degrades_to_the_unscoped_roots():
    """[MSC-5e] a serial that matches nothing (provider renamed the attr, registry
    mismatch) degrades to today's roots rather than to an empty list — a single-vacuum
    install must not lose its map because the match failed."""
    hass, hal, _ = _two_vacuums_one_entry()
    out = eufy_inmem_candidates(hass, _EUFY_IDS, device_id="SERIAL_NOT_HERE")
    assert [(o, k) for o, k, _ in out] == [("hass_data", "robovac_mqtt")]
    assert _pixel(out) == list(hal._robot_pixel)


def test_msc5f_declared_attr_names_are_honoured():
    """[MSC-5f] the id attr is DECLARED, not hardcoded — a provider that calls it
    something else is a config change, not a core change."""
    class _Odd:
        def __init__(self):
            self.serial_no = "SERIAL_ODD"
            self._robot_pixel, self._dock_pixel = (5, 5), (0, 0)

    odd = _Odd()
    hass = _Hass(data={"robovac_mqtt": {"e": {"coordinators": [_EufyCoord("OTHER", (1, 1), (2, 2)), odd]}}})
    assert eufy_inmem_candidates(hass, _EUFY_IDS, device_id="SERIAL_ODD") != [("device", "SERIAL_ODD", odd)]
    out = eufy_inmem_candidates(
        hass, _EUFY_IDS, device_id="SERIAL_ODD", device_id_attrs=["serial_no"],
    )
    assert out[0][2] is odd


def test_msc5g_raising_id_attr_degrades_to_a_non_match():
    """[MSC-5g] a provider property that raises must not abort the search — the other
    coordinators still get matched. These walks run ON THE EVENT LOOP inside the
    dashboard snapshot, so a raise here would take the whole snapshot down."""
    class _Boom:
        @property
        def device_id(self):
            raise RuntimeError("provider internals")

    hal = _EufyCoord("SERIAL_HAL", (10, 10), (1, 1))
    hass = _Hass(data={"robovac_mqtt": {"e": {"coordinators": [_Boom(), hal]}}})
    out = eufy_inmem_candidates(hass, _EUFY_IDS, device_id="SERIAL_HAL")
    assert out[0][2] is hal


def test_msc5h_the_coordinator_threads_the_serial_and_the_declared_attrs():
    """[MSC-5h] REACHABILITY. eufy_inmem_candidates being correct buys nothing if the six
    call sites don't hand it the vacuum — which is precisely the shape of the original
    defect (`_read_inmem_pose` took `vacuum_entity_id` and used it only in a log line).

    So: record what MapSourceCoordinator._inmem_candidates actually passes. Record rather
    than raise — the pose path wraps its body in `except Exception`, so a raising stub
    there is swallowed and proves nothing (docs/dev/12-map-source.md §1).
    """
    from custom_components.eufy_vacuum.mapping import map_source_coordinator as _c
    from custom_components.eufy_vacuum.mapping import map_source_runtime as _r

    declared = {
        "identifier_domain": "robovac_mqtt",
        "device_id_attrs": ["device_id"],
        "memory": {"hass_data_domain": "robovac_mqtt"},
    }
    seen = {}

    orig_cfg, orig_dev, orig_cand = (
        _c._get_adapter_config, _r.device_identifier_value, _r.eufy_inmem_candidates,
    )
    _c._get_adapter_config = lambda vid: {"map_state_source": declared}
    _r.device_identifier_value = lambda hass, vid, domain: (
        "SERIAL_HAL" if domain == "robovac_mqtt" else None
    )
    _r.eufy_inmem_candidates = lambda hass, cfg, **kw: seen.update(cfg=cfg, **kw) or []
    try:
        coord = _c.MapSourceCoordinator(manager=type("M", (), {"hass": object()})())
        coord._inmem_candidates("vacuum.hal", declared["memory"])
    finally:
        _c._get_adapter_config, _r.device_identifier_value, _r.eufy_inmem_candidates = (
            orig_cfg, orig_dev, orig_cand,
        )

    assert seen.get("device_id") == "SERIAL_HAL", f"serial not threaded: {seen}"
    assert list(seen.get("device_id_attrs") or []) == ["device_id"], (
        f"the adapter's declared device_id_attrs never reached the collector: {seen}"
    )


def test_msc5i_the_eufy_adapter_declares_the_id_attrs():
    """[MSC-5i] and the declaration exists where the coordinator reads it. Without it the
    threading above is live but carries None, every install keeps the unscoped fallback,
    and nothing goes red — a green suite over an unfixed bug.

    The config is assembled inside ``register_eufy_adapter_for_vacuum`` (needs hass + a
    live entity), so this reads the declaration from the adapter SOURCE. That is not a
    proxy here: the thing under test IS a literal in that file, so the literal is the
    artefact, not a stand-in for behaviour. [MSC-5h] covers the behaviour.
    """
    import ast
    from pathlib import Path
    import custom_components.eufy_vacuum.adapters.eufy.adapter as _a

    tree = ast.parse(Path(_a.__file__).read_text(encoding="utf-8"))
    blocks = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Dict)
        and any(
            isinstance(k, ast.Constant) and k.value == "identifier_domain"
            for k in node.keys
        )
    ]
    assert blocks, "no map_state_source-shaped dict found in the eufy adapter"
    block = blocks[0]
    keys = {k.value for k in block.keys if isinstance(k, ast.Constant)}
    assert "device_id_attrs" in keys, (
        "map_state_source.device_id_attrs is not declared — the six in-memory reads "
        "would silently fall back to the unscoped, cross-vacuum roots (issue #77)"
    )

    attrs = dict(zip([k.value for k in block.keys], block.values))["device_id_attrs"]
    assert [e.value for e in attrs.elts] == ["device_id"], (
        "the declared attr must match EufyCleanCoordinator.device_id, which is also the "
        "(robovac_mqtt, <serial>) registry identifier store_key already fills from. "
        "It must ALSO equal map_source_runtime._DEFAULT_DEVICE_ID_ATTRS: the SECOND "
        "scoping layer (eufy_mapdata_obj_from_candidates device_id filter) uses that "
        "default and is not handed the declared names, so declaring anything else makes "
        "layer 1 match and layer 2 refuse -- device_not_found, i.e. a vanished map. If "
        "you are changing this, thread device_id_attrs into that locator too."
    )
    from custom_components.eufy_vacuum.mapping.map_source_runtime import (
        _DEFAULT_DEVICE_ID_ATTRS,
    )
    assert tuple(e.value for e in attrs.elts) == _DEFAULT_DEVICE_ID_ATTRS, (
        "the declaration and the second layer's default have diverged"
    )

    # One declaration, read from the parent — not duplicated into the two nested blocks
    # the six reads pass as `cfg`, which would be a replica with nothing reconciling it.
    for name in ("memory", "live_pose"):
        nested = dict(zip([k.value for k in block.keys], block.values)).get(name)
        if nested is None:
            continue
        nested_keys = {k.value for k in nested.keys if isinstance(k, ast.Constant)}
        assert "device_id_attrs" not in nested_keys, (
            f"device_id_attrs duplicated into {name} — it is read from the parent block"
        )
