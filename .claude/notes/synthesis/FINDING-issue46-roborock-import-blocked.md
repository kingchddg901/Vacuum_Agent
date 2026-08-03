# FINDING — issue #46: Roborock import blocked when the map-selector entity is capability-gated away

**Source:** GitHub issue #46 (loryanstrant, Roborock Q5 / `roborock.vacuum.a72`, HA 2026.7.2,
VA 1.11.0). First HACS-default-store user report. Diagnosed 2026-08-02 from the attached
diagnostics; RELEASE-QUEUED per Chris.

## Chain

1. HA 2026.7 moved Roborock entity creation to device-capability gating
   (home-assistant/core#173282, merged 2026-06-08) → `select.{id}_selected_map` is never
   created for the Q5 (absent from state machine AND entity registry). This is the exact
   risk banked in the Roborock-2026.7 watch memory, landed in the wild.
2. `setup/workflow.py:152` — `import_active_map` calls `get_active_map_id()` BEFORE the
   service-response cache refresh at :186 and returns `blocked` on None. `roborock.get_maps`
   is never called. User is stuck at Setup step 2 forever.
3. `rooms/room_discovery.py:176` already has the correct handling for this topology
   (single cached map + unresolvable active map → adopt the one cache key, RP-019/ID-2 guard
   intact). **Import is a shorter copy of the same resolution predicate** — the
   predicate-vs-copies / enter-through-seam-exit-outside class from the audit-2 charter §4,
   found in the wild before the audit ran.

Evidence the device is fine: raw-map raster decoded 12 rooms (ids 16–27, parser/raster
aligned, IoU ≥0.95); `sensor.vlad_current_room` = "Living room" (upstream has names).

## Fix spec (primary)

In `import_active_map`, for service-response brands: run `async_refresh_room_source`
BEFORE resolving; if resolution is still None and the refreshed cache holds exactly ONE
map, adopt that map's cache key (map NAME) as the map id — mirroring
`discover_rooms_for_vacuum`'s fallback and its RP-019 guard EXACTLY (an explicit resolved
id that misses the cache must still refuse). Bucket then keys by name, consistent with
every discovery lookup.

## Same-pass items

- **Strand gate:** `binary_sensor.{id}_cleaning` is ALSO capability-gated away on this
  install; `completion_health` correctly warns EVERY run will strand. Needs a fallback
  completion signal (or adapter-declared alternative) or #46 gets a follow-up issue the
  day import works.
- **Eufy-ism leaks this user actually read:** `diagnostics.py:278` ("finish a mapping run
  … in the Eufy app") and `workflow.py:160` ("Eufy's reduced transport") — brand-neutral
  rewrites; new strings route through i18n at creation.
- **`upkeep_snapshot_error`:** `TypeError: NoneType + str` in the upkeep snapshot when
  maintenance sources are null — separate small bug, visible in the same diagnostics.

## Secondary (note, not queued)

Map identity split: user's store holds an empty bucket keyed `"1"` (numeric flag path via
some `ensure_map_bucket` caller) while the get_maps cache keys by NAME — two identity
schemes for one map. Worth a look when touching map identity; do not fold into the import
fix.
