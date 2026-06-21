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
    eufy_inmem_candidates,
    image_entity_object,
    roborock_candidates,
)


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
    out = eufy_inmem_candidates(hass, {})
    assert out == [("hass_data", "robovac_mqtt", bucket)]
    # the third tuple element is the SAME object (a root to walk), not a copy
    assert out[0][2] is bucket


def test_eufy_inmem_runtime_data_only():
    """[MSC-1b] a config entry with runtime_data -> ('runtime_data', entry_id, rd)."""
    rd = object()
    hass = _Hass(entries=[_Entry("entry_abc", runtime_data=rd)])
    out = eufy_inmem_candidates(hass, {})
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
    out = eufy_inmem_candidates(hass, {})
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
    out = eufy_inmem_candidates(hass, {})
    assert [(o, k) for o, k, _ in out] == [("runtime_data", "e_real")]


def test_eufy_inmem_neither_present_empty():
    """[MSC-1e] no bucket and no entries -> []."""
    hass = _Hass()
    assert eufy_inmem_candidates(hass, {}) == []


def test_eufy_inmem_custom_domain_from_cfg():
    """[MSC-1f] hass_data_domain in source_cfg overrides the default 'robovac_mqtt'."""
    bucket = {"x": 1}
    hass = _Hass(data={"my_fork": bucket})
    out = eufy_inmem_candidates(hass, {"hass_data_domain": "my_fork"})
    assert out == [("hass_data", "my_fork", bucket)]
    # the default domain bucket is NOT consulted under the override
    assert eufy_inmem_candidates(_Hass(data={"robovac_mqtt": bucket}),
                                 {"hass_data_domain": "my_fork"}) == []


def test_eufy_inmem_async_entries_raises_degrades_to_hass_data():
    """[MSC-1g] async_entries() raising degrades to [] for the entry source but STILL
    returns the hass_data candidate (never aborts the whole collection)."""
    bucket = {"b": 1}
    hass = _Hass(data={"robovac_mqtt": bucket}, raise_exc=RuntimeError("HA internals shifted"))
    out = eufy_inmem_candidates(hass, {})
    assert out == [("hass_data", "robovac_mqtt", bucket)]


def test_eufy_inmem_async_entries_raises_no_bucket_empty():
    """[MSC-1h] async_entries() raising and no bucket -> [] (clean degrade, no raise)."""
    hass = _Hass(raise_exc=ValueError("boom"))
    assert eufy_inmem_candidates(hass, {}) == []


def test_eufy_inmem_hass_data_none():
    """[MSC-1i] hass.data is None -> the (hass.data or {}) guard yields no bucket -> []."""
    hass = _Hass()
    hass.data = None
    assert eufy_inmem_candidates(hass, {}) == []


# ---------------------------------------------------------------------------
# [MSC-2] roborock_candidates
# ---------------------------------------------------------------------------

def test_roborock_image_entity_candidate():
    """[MSC-2] when image_entity_id resolves to an object -> the image_entity candidate
    is FIRST (the parsed MapData most likely lives on the image entity)."""
    ent = object()
    hass = _Hass(data={"entity_components": {"image": _ImageComponent(
        {"image.ivy_map": ent})}})
    out = roborock_candidates(hass, {}, image_entity_id="image.ivy_map")
    assert out == [("image_entity", "image.ivy_map", ent)]
    assert out[0][2] is ent


def test_roborock_image_entity_unresolved_omitted():
    """[MSC-2b] image_entity_id given but get_entity returns None -> no image candidate."""
    hass = _Hass(data={"entity_components": {"image": _ImageComponent({})}})
    out = roborock_candidates(hass, {}, image_entity_id="image.missing")
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
    out = roborock_candidates(hass, {}, image_entity_id="image.ivy_map")
    assert out == [
        ("image_entity", "image.ivy_map", ent),
        ("runtime_data", "e1", rd),
        ("hass_data", "roborock", bucket),
    ]


def test_roborock_no_image_id_runtime_and_bucket():
    """[MSC-2d] no image_entity_id -> just runtime_data + hass_data (default 'roborock')."""
    rd = object()
    bucket = {"b": 1}
    hass = _Hass(data={"roborock": bucket}, entries=[_Entry("e1", rd)])
    out = roborock_candidates(hass, {})
    assert out == [
        ("runtime_data", "e1", rd),
        ("hass_data", "roborock", bucket),
    ]


def test_roborock_custom_domain_from_cfg():
    """[MSC-2e] hass_data_domain overrides the default 'roborock' for both entries+bucket."""
    rd = object()
    bucket = {"b": 1}
    hass = _Hass(data={"rr2": bucket}, entries=[_Entry("e1", rd)])
    out = roborock_candidates(hass, {"hass_data_domain": "rr2"})
    assert out == [
        ("runtime_data", "e1", rd),
        ("hass_data", "rr2", bucket),
    ]


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
    out = roborock_candidates(hass, {}, image_entity_id="image.ivy_map")
    assert out == [
        ("image_entity", "image.ivy_map", ent),
        ("hass_data", "roborock", bucket),
    ]


def test_roborock_runtime_data_none_skipped():
    """[MSC-2g] an entry with runtime_data None contributes nothing; bucket still added."""
    bucket = {"b": 1}
    hass = _Hass(data={"roborock": bucket}, entries=[_Entry("e_none", runtime_data=None)])
    out = roborock_candidates(hass, {})
    assert out == [("hass_data", "roborock", bucket)]


def test_roborock_empty_when_nothing_present():
    """[MSC-2h] no image id, no entries, no bucket -> []."""
    assert roborock_candidates(_Hass(), {}) == []


def test_roborock_hass_data_none():
    """[MSC-2i] hass.data None -> the (hass.data or {}) guard yields no bucket -> []
    (no image id given, no entries)."""
    hass = _Hass()
    hass.data = None
    assert roborock_candidates(hass, {}) == []


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
