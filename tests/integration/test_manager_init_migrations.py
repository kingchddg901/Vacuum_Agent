"""async_initialize migration / backfill behaviour for core/manager.py.

These tests seed the HA Store with *legacy-shaped* persisted data and then run
EufyVacuumManager.async_initialize() for real (no mocks of the migration code),
asserting on the post-migration shape of manager.data. They cover the schema
fix-ups that run once on load:

  - the deprecated top-level "icons" block is dropped
  - the per-room field-backfill loop skips non-dict map buckets and non-dict
    room values without raising
  - a legacy floor_type=="carpet" + carpet_type sub-field is compacted into the
    single canonical "carpet_<type>" value (and the stray "carpet" flag dropped)
  - an old top-level-"rooms" discovery entry is flattened into the current
    per-map-id dict shape, keyed by active_map_id

Setup mirrors the hass_storage recipe from test_init_setup.py (seed
hass_storage[_STORAGE_KEY] = {"version": 1, "data": {...}}) and the manager
wiring from the conftest `manager` fixture (AdapterCoordinator into hass.data,
then construct + async_initialize), but seeds the store *before* initialize so
the migration paths see the legacy data.

Coverage targets
----------------
[CMI-1] "icons" block dropped; carpet room compacted to "carpet_high_pile"
        (carpet_type + carpet flags removed). (lines 280, 336-337)
[CMI-2] non-dict map bucket and non-dict room value are skipped without error;
        the real sibling room is still backfilled. (lines 322, 325)
[CMI-3] legacy top-level-"rooms" discovery entry flattened to {active_map_id: ...}.
        (lines 346-348)
[CMI-4] _migrate_setup_progress back-fills a rooms-bearing vacuum; skips non-dict
        records, no-managed-rooms vacuums, already-done entries, and non-dict
        map buckets/room values. (lines 392, 394, 402, 418, 421)
"""

from __future__ import annotations

import copy

from custom_components.eufy_vacuum.adapters.registry import AdapterCoordinator
from custom_components.eufy_vacuum.const import DATA_ADAPTER_COORDINATOR, DOMAIN
from custom_components.eufy_vacuum.core.manager import EufyVacuumManager

_VAC = "vacuum.alfred"
_STORAGE_KEY = "eufy_vacuum.storage"


async def _init_manager(hass, mock_config_entry) -> EufyVacuumManager:
    """Construct + async_initialize a manager (mirrors the conftest fixture).

    The store must already be seeded via hass_storage before this is called so
    async_initialize's migration paths see the legacy-shaped data.
    """
    hass.data.setdefault(DOMAIN, {})
    coordinator = AdapterCoordinator(hass, mock_config_entry)
    hass.data[DOMAIN][DATA_ADAPTER_COORDINATOR] = coordinator
    m = EufyVacuumManager(hass)
    await m.async_initialize()
    return m


async def test_init_drops_icons_and_compacts_carpet(
    hass, hass_storage, mock_config_entry
):
    """[CMI-1] icons block dropped (280); carpet floor_type compacted (336-337)."""
    hass_storage[_STORAGE_KEY] = {"version": 1, "data": {
        # Deprecated icon-selects block — must be popped on load.
        "icons": {_VAC: {"some": "legacy-icon-state"}},
        "maps": {_VAC: {"6": {
            "map_id": "6", "metadata": {}, "summary": {},
            "rooms": {
                # Legacy carpet shape: floor_type=="carpet" + carpet_type
                # sub-field + a derived "carpet" flag. All three collapse into
                # the single canonical floor_type value.
                "1": {
                    "room_id": 1, "name": "Den",
                    "floor_type": "carpet",
                    "carpet_type": "high_pile",
                    "carpet": True,
                },
            }}}},
    }}

    m = await _init_manager(hass, mock_config_entry)

    # 280: the deprecated icons block is gone.
    assert "icons" not in m.data

    room = m.data["maps"][_VAC]["6"]["rooms"]["1"]
    # 336-337: carpet + carpet_type compacted into "carpet_<type>".
    assert room["floor_type"] == "carpet_high_pile"
    assert "carpet_type" not in room
    # The derived "carpet" flag is dropped (computed from floor_type at read).
    assert "carpet" not in room


async def test_init_carpet_default_pile(hass, hass_storage, mock_config_entry):
    """[CMI-1b] carpet with no carpet_type defaults to low_pile (336 default)."""
    hass_storage[_STORAGE_KEY] = {"version": 1, "data": {
        "maps": {_VAC: {"6": {
            "map_id": "6", "metadata": {}, "summary": {},
            "rooms": {
                # floor_type=="carpet" but no carpet_type → default "low_pile".
                "1": {"room_id": 1, "name": "Rug", "floor_type": "carpet"},
            }}}},
    }}

    m = await _init_manager(hass, mock_config_entry)

    room = m.data["maps"][_VAC]["6"]["rooms"]["1"]
    assert room["floor_type"] == "carpet_low_pile"
    assert "carpet_type" not in room


async def test_init_skips_non_dict_bucket_and_room(
    hass, hass_storage, mock_config_entry
):
    """[CMI-2] non-dict map bucket (322) + non-dict room value (325) skipped.

    The backfill loop must `continue` past a non-dict bucket and a non-dict room
    value without raising, while still backfilling the genuine sibling room.
    """
    hass_storage[_STORAGE_KEY] = {"version": 1, "data": {
        "maps": {_VAC: {
            # Non-dict bucket → line 321/322 `continue` (no .get on a string).
            "bad_bucket": "not-a-dict",
            "6": {
                "map_id": "6", "metadata": {}, "summary": {},
                "rooms": {
                    # Non-dict room value → line 324/325 `continue`.
                    "bad_room": "not-a-dict",
                    # Genuine room with no backfill fields yet → gets them.
                    "1": {"room_id": 1, "name": "Kitchen"},
                },
            },
        }},
    }}

    # The whole thing must initialize without raising.
    m = await _init_manager(hass, mock_config_entry)

    rooms = m.data["maps"][_VAC]["6"]["rooms"]
    # Non-dict entries survived untouched (skipped, not mutated/dropped).
    assert m.data["maps"][_VAC]["bad_bucket"] == "not-a-dict"
    assert rooms["bad_room"] == "not-a-dict"
    # The real sibling room got the post-release fields backfilled.
    real = rooms["1"]
    assert real["floor_type"] == "hardwood"
    assert real["profile_name"] == "vacuum_quick"
    assert real["path_type"] is None
    assert real["is_dock_room"] is False
    assert real["grants_access_to"] == []
    assert real["rules"] == []


async def test_init_flattens_legacy_discovery(
    hass, hass_storage, mock_config_entry
):
    """[CMI-3] old top-level-"rooms" discovery entry → per-map-id dict (346-348)."""
    legacy_entry = {
        "active_map_id": "6",
        "rooms": [
            {"room_id": 1, "map_id": "6", "name": "Kitchen"},
            {"room_id": 2, "map_id": "6", "name": "Bath"},
        ],
    }
    hass_storage[_STORAGE_KEY] = {"version": 1, "data": {
        # Legacy flat shape: discovery[_VAC] has a top-level "rooms" key.
        "discovery": {_VAC: copy.deepcopy(legacy_entry)},
    }}

    m = await _init_manager(hass, mock_config_entry)

    # 346-348: re-keyed under active_map_id, original payload preserved verbatim.
    assert m.data["discovery"][_VAC] == {"6": legacy_entry}


async def test_init_modern_discovery_unchanged(
    hass, hass_storage, mock_config_entry
):
    """[CMI-3b] already-flattened discovery (no top-level "rooms") is left alone."""
    modern = {"6": {
        "active_map_id": "6",
        "rooms": [{"room_id": 1, "map_id": "6", "name": "Kitchen"}],
    }}
    hass_storage[_STORAGE_KEY] = {"version": 1, "data": {
        "discovery": {_VAC: copy.deepcopy(modern)},
    }}

    m = await _init_manager(hass, mock_config_entry)

    # No top-level "rooms" key on the outer dict → migration skips it.
    assert m.data["discovery"][_VAC] == modern


async def test_init_flattens_legacy_discovery_missing_active_map_id(
    hass, hass_storage, mock_config_entry
):
    """[CMI-3c] legacy discovery with no active_map_id falls back to "unknown" (347).

    The existing [CMI-3] test always supplies active_map_id, so the
    `_disc.get("active_map_id") or "unknown"` fallback on line 347 is never
    taken. A legacy top-level-"rooms" entry that predates the active_map_id
    field must still flatten — re-keyed under the literal "unknown".
    """
    legacy_entry = {
        # No "active_map_id" key at all → .get(...) is None → "unknown".
        "rooms": [
            {"room_id": 1, "map_id": "6", "name": "Kitchen"},
        ],
    }
    hass_storage[_STORAGE_KEY] = {"version": 1, "data": {
        "discovery": {_VAC: copy.deepcopy(legacy_entry)},
    }}

    m = await _init_manager(hass, mock_config_entry)

    # 346-348: still flattened (top-level "rooms" present), keyed "unknown",
    # original payload preserved verbatim under that key.
    assert m.data["discovery"][_VAC] == {"unknown": legacy_entry}


async def test_init_flattens_legacy_discovery_falsy_active_map_id(
    hass, hass_storage, mock_config_entry
):
    """[CMI-3d] legacy discovery with a falsy active_map_id also → "unknown" (347).

    An empty-string active_map_id is falsy, so the `or "unknown"` branch fires
    even though the key exists — covers the present-but-empty leg of line 347
    that the missing-key case (CMI-3c) does not.
    """
    legacy_entry = {
        "active_map_id": "",  # present but falsy → str("") or "unknown" → "unknown"
        "rooms": [
            {"room_id": 1, "map_id": "6", "name": "Kitchen"},
        ],
    }
    hass_storage[_STORAGE_KEY] = {"version": 1, "data": {
        "discovery": {_VAC: copy.deepcopy(legacy_entry)},
    }}

    m = await _init_manager(hass, mock_config_entry)

    assert m.data["discovery"][_VAC] == {"unknown": legacy_entry}


# ---------------------------------------------------------------------------
# [CMI-4] _migrate_setup_progress — one-time setup_progress back-fill.
#
# Unlike the CMI-1..CMI-3 cluster (which seed legacy storage and let
# async_initialize run the migration), _migrate_setup_progress is the rare
# migration that is also a directly-callable sync method. We get a real,
# fully-initialized manager via the shared _init_manager helper (its store is
# empty, so the initialize-time call leaves setup_progress == {}), then seed
# manager.data fresh and call the method directly to assert its effects.
# ---------------------------------------------------------------------------

_VAC_ROOMS = "vacuum.has_rooms"      # real record + managed rooms → stamped
_VAC_PRESENT = "vacuum.already"      # already in setup_progress → untouched (394)
_VAC_NO_ROOMS = "vacuum.no_rooms"    # real record, zero managed rooms → skipped (402)
_VAC_BAD = "vacuum.bad_record"       # non-dict vacuum record → skipped (392)
_MAP6 = "6"


async def test_migrate_setup_progress_backfill(hass, hass_storage, mock_config_entry):
    """[CMI-4] back-fills a rooms-bearing vacuum; skips junk + already-done (392,394,402,418,421).

    Seeds four vacuum records that each drive one branch of the migration, then
    calls the synchronous _migrate_setup_progress() and asserts the observable
    result on manager.data:
      - 392: a non-dict vacuum record is skipped (no crash, not added).
      - 394: a vacuum already in setup_progress is left exactly as-is.
      - 402: a vacuum with no managed rooms is NOT added.
      - 418/421: a non-dict map bucket / non-dict room value are skipped while
        the genuine sibling room is stamped is_configured=True + configured_at.
    """
    hass_storage[_STORAGE_KEY] = {"version": 1, "data": {}}
    m = await _init_manager(hass, mock_config_entry)

    # A sentinel the migration must NOT touch: a pre-existing setup_progress
    # entry whose completed_steps differ from what the migration would write.
    preexisting = {
        "completed_steps": ["add_vacuum"],
        "last_advanced_at": "2020-01-01T00:00:00+00:00",
        "rejected_rooms": [],
        "room_drift_history": {},
    }
    m.data["setup_progress"] = {_VAC_PRESENT: preexisting}

    # Four vacuum records. The non-dict record (392) sits alongside real dicts.
    m.data["vacuums"] = {
        _VAC_ROOMS: {"vacuum_entity_id": _VAC_ROOMS, "is_managed": True},
        _VAC_PRESENT: {"vacuum_entity_id": _VAC_PRESENT, "is_managed": True},
        _VAC_NO_ROOMS: {"vacuum_entity_id": _VAC_NO_ROOMS, "is_managed": True},
        _VAC_BAD: "not-a-dict",  # 392: non-dict record is skipped
    }

    # Maps tree. The rooms-bearing vacuum has one real room (stamped) plus a
    # non-dict bucket (418) and a non-dict room (421) the migration must skip.
    real_room = {"room_id": 1, "name": "Kitchen"}  # no is_configured yet
    m.data["maps"] = {
        _VAC_ROOMS: {
            _MAP6: {
                "rooms": {
                    "1": real_room,
                    "bad_room": "not-a-dict",  # 421: non-dict room is skipped
                },
            },
            "7": "not-a-dict-bucket",  # 418: non-dict bucket is skipped
        },
        # _VAC_NO_ROOMS deliberately has NO maps entry → has_rooms False (402).
        _VAC_PRESENT: {_MAP6: {"rooms": {"1": {"room_id": 1}}}},
    }

    m._migrate_setup_progress()

    sp = m.data["setup_progress"]

    # The rooms-bearing vacuum is stamped with all three legacy Eufy steps.
    assert _VAC_ROOMS in sp
    assert sp[_VAC_ROOMS]["completed_steps"] == [
        "add_vacuum",
        "import_active_map",
        "save_rooms",
    ]
    # Migration metadata is populated (timestamps + empty derived state).
    assert sp[_VAC_ROOMS]["migrated_at"]
    assert sp[_VAC_ROOMS]["last_advanced_at"]
    assert sp[_VAC_ROOMS]["rejected_rooms"] == []
    assert sp[_VAC_ROOMS]["room_drift_history"] == {}

    # 402: the no-managed-rooms vacuum is NOT added.
    assert _VAC_NO_ROOMS not in sp

    # 392: the non-dict vacuum record is NOT added (and did not crash).
    assert _VAC_BAD not in sp

    # 394: the pre-existing entry is left exactly as-is (idempotent skip).
    assert sp[_VAC_PRESENT] is preexisting
    assert sp[_VAC_PRESENT]["completed_steps"] == ["add_vacuum"]

    # The real room got stamped is_configured True + a configured_at timestamp.
    assert real_room["is_configured"] is True
    assert real_room["configured_at"]

    # 418/421: the non-dict bucket/room were skipped without mutation.
    assert m.data["maps"][_VAC_ROOMS]["7"] == "not-a-dict-bucket"
    assert m.data["maps"][_VAC_ROOMS][_MAP6]["rooms"]["bad_room"] == "not-a-dict"


async def test_migrate_setup_progress_preserves_existing_is_configured(
    hass, hass_storage, mock_config_entry
):
    """[CMI-4b] an explicit is_configured value is preserved (422 guard).

    The migration only stamps rooms missing the field entirely ("is_configured"
    not in room); a prior explicit value (here False) must survive untouched and
    gain no configured_at, even though the vacuum still earns a setup_progress
    entry from having managed rooms.
    """
    hass_storage[_STORAGE_KEY] = {"version": 1, "data": {}}
    m = await _init_manager(hass, mock_config_entry)

    m.data["setup_progress"] = {}
    m.data["vacuums"] = {
        _VAC_ROOMS: {"vacuum_entity_id": _VAC_ROOMS, "is_managed": True},
    }
    already = {"room_id": 1, "name": "Kitchen", "is_configured": False}
    m.data["maps"] = {_VAC_ROOMS: {_MAP6: {"rooms": {"1": already}}}}

    m._migrate_setup_progress()

    # The vacuum still earns a setup_progress entry (it has managed rooms)...
    assert _VAC_ROOMS in m.data["setup_progress"]
    # ...but the explicitly-False room flag is preserved, no configured_at added.
    assert already["is_configured"] is False
    assert "configured_at" not in already
