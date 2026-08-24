# Saved Zones — Named, Human-Semantic Clean Regions

**Status:** **Waves 1 + 2 + 3 BUILT + adversarially reviewed** — W1 storage + CRUD + read; W2 filing
(`room_number` at ≥90%-of-floor via `zone_membership`) + `area_m2` + the `set_saved_zone_room`
override; **W3a `clean_saved_zone` dispatch** (resolve zone → bbox rect → the shared
`dispatch_zone_clean`, active-map-guarded, fire-and-forget). 2795 tests green, 2026-07-02.
**Wave 3b** (the card UX: draw→save, room-grouped multi-select list, pick-and-clean, delete) is
**BUILT/SHIPPED** across `src/{state,renderers,bindings,actions}/saved-zones.js`. This doc is the
contract; each wave is additive.

> **Scope:** persist **named, reusable zones** on a map ("the couch", "the stove", "under the
> table") that a user can draw once, name, bucket under a room, and re-clean on demand. It is a
> thin persistence + UX layer over infrastructure that **already exists** — deliberately not a new
> map/geometry/dispatch subsystem.

---

## 1. Why (the value)

Humans navigate by **landmark**, not coordinate or even room. "Clean under the couch" / "by the
stove after dinner" is how people actually reference a spot. A saved zone is a **named, human-
semantic handle on a sub-room location** — more precise than room-level ("clean the kitchen"),
reusable (draw once, keep forever), and organized the way a person thinks (by furniture, under the
room it lives in). That naming is the whole point; the geometry is just its anchor.

## 2. What already exists (this is a delta, not a build)

Per the scan-first rule, the load-bearing pieces are already standing — saved zones **reuses**
them and adds only persistence + UI:

| Need | Already provides it | Source |
|---|---|---|
| Stable, drift-immune frame | `map_state_source` normalized 0–1 (provider's own segmentation, **not** the drifting pose) | [map-state-source.md](../design/shipped/map-state-source.md), [12 — Where the Map Comes From](../12-map-source.md) |
| Zone **size** (m²) | per-room `area_m2` / `width_m` / `height_m` from map resolution — same math for a drawn box | `map_source.build_map_source_result` |
| Named, per-map, user-authored **collection** storage | `custom_layouts: dict[id, CustomLayout]` on the map bucket + `_migrate_custom_layouts` + summaries + `create/rename/delete_custom_layout` services | [data-model.md §Segment stores](../03-data-model.md), `mapping/mapping_services.py::_migrate_custom_layouts` / `::_create_layout` / `::_handle_create_custom_layout` |
| Room-membership of a point/region | the `room_pixels` room-id raster (decoded with `map_render` `rid_shift`/`catch_all_rid`) that backs `current_room`; per-point analog = the fork's `room_at_point` (#139) | `map_source.py`, fork `room_id_at_normalized` |
| Fire a zone clean | `normalized_rects_to_quads_cm` → zone-clean dispatch (Eufy `SelectZonesClean` via fork #138; Roborock `app_zoned_clean`, shipped v1.2.0) | [project_roborock_zone_clean], fork `commands.py` |

**Net new work = a `saved_zones` sibling collection + a bucketing computation + card UX.** No new
coordinate frame, no new size math, no new dispatch.

## 3. Data model

A new per-map collection on the map bucket (`data["maps"][v][m]`), mirroring `custom_layouts`
exactly — same id-gen, same lazy `_migrate_saved_zones(map_bucket)` guard, same
summary-in-snapshot pattern:

```python
data["maps"][v][m]["saved_zones"]: dict[zone_id_str, SavedZone]   # {} until first author
```

```python
SavedZone = {
    "id":            str,            # "sz_<YYYYMMDDTHHMMSS>_<seq>" (_generate_saved_zone_id;
                                     #   monotonic seq, ignores deletions)
    "name":          str,            # USER string ("the couch") — data, never i18n (see §7);
                                     #   stripped, "Zone" fallback if empty at mint
    "geometry":      [[x,y],...],    # normalized 0–1 point list (min 3 points) — THE zone;
                                     #   dispatch works off this ALONE. Each coord is schema-
                                     #   sanitized: non-numeric/bool/NaN/inf rejected, clamped
                                     #   to 0–1, rounded to 5 dp (_saved_zone_coord)
    "area_m2":       float | None,   # computed from map dims at author time (display + validation);
                                     #   None until computed — self-healed on read (§5, backfill)
    "room_number":   int | None,     # FILING ONLY (§4): auto-set at author by ≥90% dominance, else
                                     #   None ("Unassigned"); user-editable; NEVER affects dispatch
    "kind":          str,            # "clean" (default, and the only value the schema
                                     #   currently accepts -- neither clean handler reads
                                     #   kind, so a wider value would silently dispatch as
                                     #   a clean anyway; RP-032/A6-ZONE-C-7)
    "created_at":    str,            # ISO UTC at mint (utc_now_iso)
    "updated_at":    str,            # ISO UTC, touched by rename / set-room / backfill
}
```

There is **no stored map-version key** — the §10 invalidation described below is design intent,
not an implemented mechanism (grep confirms `map_version` appears nowhere in
`custom_components/` or `src/`).

There is deliberately **no** persisted `rooms[]` breakdown and **no** separate `room_override` — the
dominance % is a transient author-time compute, and under the §10 invalidation *intent* (a re-map
would invalidate the zone, were that wired up) there is no re-compute that a stored override would
need to survive. `SavedZone` is **lighter than a `CustomLayout`** — one box + name, not a whole
segmentation.
Brand-agnostic: it mirrors the custom-layout *storage pattern* but is **not** part of the Eufy
CV/segmentation system; it feeds the per-brand zone-clean dispatch and works on Roborock too.

## 4. Room grouping — a filing concern, never a dispatch one

**The key clarification (the leaves case forced it):** a saved zone is fundamentally just its
**geometry**. Dispatch cleans that quad directly (§6) and does **not** care what room(s) it crosses —
a cross-room footprint cleans identically to a single-room one. So `room_number` is **purely
organizational**: it decides where the zone appears in the card list, nothing more. It never gates,
splits, or shapes the clean. There is **no multi-room tagging and no partition math** — dispatch was
never in question, which is exactly *why* a zone clean (vs. a room clean) is valuable: it addresses
"this specific footprint" regardless of room boundaries.

> **Motivating case:** leaves blow into the entryway and a bit of the adjoining office. You want a
> single job over *that footprint* — the whole entryway + a corner of the office — not the whole
> office cleaned. The zone crosses a room boundary on purpose; dispatch just cleans the box.

**Two populations** (design rationale — split is an expected minority, not a rare afterthought and
not a heavy feature):

- **Landmark zones (majority)** — "in front of the couch", "outside the cat room". Single-room *by
  construction* (a landmark lives somewhere), so ≥90% dominance auto-assigns correctly and rarely
  needs touching.
- **Task-footprint zones (a known minority)** — deliberately cross a soft/user-drawn boundary
  because the *task* ignores rooms: the leaves case, "along this whole wall". These land in
  **Unassigned** and get filed by hand or just left there.

**Auto-assign (`room_number`, filing only):** sample the `room_pixels` room-id raster over the
zone's box; **denominator = segmented floor pixels only** (furniture footprints — the couch's body,
the Eufy bg rid — excluded, so a big-furniture zone isn't wrongly split). One room holds **≥ 90%**
of the floor → `room_number = that room`; otherwise `room_number = None` → **Unassigned**. Computed
**once at author time** — no persisted breakdown, no re-compute.

**Editable:** `room_number` is user-settable any time (a room picker; None = Unassigned) — the same
machine-guesses / human-files pattern as phantom-room curation and the external-run review wizard.
The majority never need it; the task-footprint minority get filed (or left) in one tap. Editing is a
filing action with **zero** effect on the clean.

## 5. Services (mirror the custom-layout trio)

In `mapping/mapping_services.py`, mirroring `_handle_{create,rename,delete}_custom_layout`:

- `create_saved_zone` — `(vacuum_entity_id, map_id, name, geometry[, kind])` → stores, then
  best-effort computes `area_m2` + `room_number` (≥90%-of-floor dominance, filing only; never
  fails the create), returns `{saved, zone_id, zone}`. **Create-time refuse gates:** blank name →
  `missing_name`; unknown map → `map_not_found` (+ `known_maps`); and the schema itself rejects a
  **degenerate geometry** — a bbox with either side `< 0.01` normalized
  (`_reject_degenerate_zone_geometry`, the same `_MIN_SIDE` as `dispatch_zone_clean`'s own guard,
  so a zone that saves can never fail degenerate at clean time; RP-032/A1-SERVIC-4). The
  membership compute is **active-map-guarded**: it runs when the active map matches the zone's
  `map_id` *or is indeterminate*; a definite mismatch leaves `area_m2`/`room_number` `None`.
  Un-sized zones are **self-healed on the `get_map_segments` read**
  (`_backfill_saved_zone_area`: same guard, sizes + files any `area_m2 is None` zone, persists).
- `rename_saved_zone` — `(…, zone_id, name)`.
- `delete_saved_zone` — `(…, zone_id)`.
- `set_saved_zone_room` — `(…, zone_id, room_number | null)` → sets/clears `room_number` (filing
  only; null = Unassigned; **no effect on dispatch**).
- `clean_saved_zone` — `(…, zone_id, clean_times?)` → takes the geometry's normalized **bbox
  rect** and fires the shared `dispatch_zone_clean` (which owns the per-brand coordinate
  conversion, §6) at call time. `clean_times` is the optional number of cleaning passes (min 1) —
  **but Eufy declares `supports_zone_repeat: false`, so any `clean_times > 1` there is normalized
  to 1 with a logged warning, not honored** (`dispatch/manager.py`, the non-`device_mm` branch).
  **Clean-time refuse gates:** `zone_not_found`; the **active-map guard** — a zone's geometry is
  only valid on ITS map, so a different active map refuses with `map_not_active` (+
  `active_map_id`), and an **unreadable/indeterminate active map also refuses**
  (`active_map_indeterminate` — indeterminate ≠ match, RP-029/ZONE-C-1); `bad_geometry` (< 3
  valid points). Fire-and-forget: no job/queue/learning.
- `clean_saved_zones` — `(vacuum_entity_id, map_id, zone_ids[], clean_times?)` → resolves every
  zone to its bbox rect and fires the whole set as ONE `dispatch_zone_clean` call (same
  active-map + indeterminate refusals + Eufy repeat-normalization above; per-brand caps enforced
  inside the dispatch: Eufy up to 10 zones / 0.5–10 m per side, Roborock up to 5 zones /
  1 ft²–3.05 m² each; JS wrapper `cleanSavedZones`). **Atomic:** any missing zone
  (`zone_not_found` + the id list) or bad-geometry zone (`bad_geometry` + the id list) refuses the
  whole batch.

Each runs `_migrate_saved_zones` first, degrades safely, and the snapshot carries a
full saved-zone dict per zone on the `get_map_segments` read (geometry included — NOT a summary, unlike the sibling `custom_layouts`, which is); no `SavedZoneSummary` shape exists anywhere in the code.

## 6. Dispatch + drift-safety (the one hard rule)

**Store normalized, convert at clean-time — never persist absolute cm.** The provider re-origins
its coordinate frame per session; the map-relative (normalized) frame is stable, but a cached
device-coordinate quad is not. So `clean_saved_zone`/`clean_saved_zones` hand the stored 0–1 bbox
rect(s) to the shared `dispatch_zone_clean` (`dispatch/manager.py::dispatch_zone_clean`) each time, which converts
**per brand, at call time, from the current session's live map**, exactly as live zone-drawing
already does — never persist absolute coordinates. The conversion itself is brand-branched on the
adapter's `zone_coords` capability, not a single shared helper:

- **`zone_coords: device_mm`** (Roborock) — converted to world millimetres via
  `zone_dispatch.normalized_rects_to_mm`, using `map_source_runtime.correspondences_from_mapdata`;
  a validation failure **refuses** the dispatch rather than risk cleaning the wrong area.
- **Everything else** (Eufy) — the 0–1 rects ship **verbatim**; the fork de-normalizes them on its
  own side (`SelectZonesClean`). Size-bound checks (when the adapter declares any) still convert
  to metres locally for validation only, using the live map's own `width`/`height`/`resolution`
  (the same math as `map_source.zone_membership`'s footprint calc) — that conversion never leaves
  the service, the dispatched payload stays normalized.

Saved zones must not shortcut this by caching a converted quad.

**Map-flip property (hypothesis to validate — Chris, 2026-07-02):** because a saved zone is stored
map-relative and converted at call time from the **current** map's geometry — which updates ~0.5s
after a `MAP_LOAD`, well before the pose re-localizes — a saved zone may dispatch **correctly right
after a map switch**, when live zone *drawing* cannot (drawing needs the live grounded frame the
switch un-grounds). If so, saved zones are the reliable post-switch clean path, and firing one
likely forces re-localization itself (like the room-based refresh probe). Test once the fork
`map_load` primitive lands (fork PR #150) — see the map-switcher notes in `reference_eufy_biz_map_switch`.

## 7. i18n

Zone names are **user data, not authored strings** — "the couch" is exactly like a user's room name
("Kids Bedroom"): we store and display it verbatim, never fabricate or translate it. So it satisfies
the no-string-without-i18n contract the same way room names do (display *is* identity). Only the
card **chrome** (buttons, section headers, the "Unassigned" section label, validation messages) routes
through i18n.

## 8. Card UX

- **Author:** draw a box on the map → name it → save (`create_saved_zone`). **No** live m² while
  drawing — `area_m2` is computed server-side at create (`_handle_create_saved_zone` →
  `zone_membership`) and renders only on an already-saved zone; the size/ count limits gate here (§9).
- **Browse:** the saved-zone list, **grouped by `room_number`** (room sections in map order, the
  **Unassigned** special-cases section last). Each entry shows name + m².
- **Reassign:** a room picker per zone (`set_saved_zone_room`) — a filing action only; None =
  Unassigned.
- **Clean:** tapping a zone row toggles its multi-select checkbox, and the singular `clean_saved_zone` has NO card caller (it is a registered service + the `cleanSavedZone` JS wrapper, reachable from an automation). The card's one clean control, "Clean N selected", always fires the `clean_saved_zones` batch
  (respecting the zone cap).

## 9. Validation (author-time + clean-time)

- **Author time:** the create schema rejects bad coords (`_saved_zone_coord`) and a degenerate
  bbox (either side `< 0.01` normalized — `_MIN_SIDE`, deliberately equal to the dispatch-side
  guard so nothing saves that can't clean); the card caps drawn boxes at the brand zone cap
  (snapshot `zone_max` via `zoneMax()`, fallback 10 — `src/state/map.js`).
- **Clean time:** `dispatch_zone_clean` re-checks degenerate rects and enforces the per-brand
  capability caps — zone **count** (`zone_max`) plus per-zone **size bounds**
  (`zone_min_area_m2` / `zone_max_area_m2` / `zone_min_side_m` / `zone_max_side_m`; absent =
  unconstrained for that brand). Eufy: 10 zones, 0.5–10 m per side. Roborock: 5 zones,
  1 ft²–3.05 m² area. There is **no auto-tiling** of an oversize zone — it refuses with an error.

## 10. Invalidation

**Design intent, NOT yet implemented:** the intent is that a genuine **re-map** (the
`room_pixels` raster changes meaning) invalidates the map's saved zones. Today **no code does
this** — the record stores no map-version key (§3) and no writer CLEARS `saved_zones` on a
re-map (`maps/map_manager.py:rebuild_map_bucket` rewrites rooms/summary/metadata only; the other
writers — `_create_saved_zone`, `_backfill_saved_zone_area`, `_handle_rename_saved_zone`,
`_handle_set_saved_zone_room`, `_handle_delete_saved_zone` — insert, mutate, or remove individual
zone entries, none of them invalidate the collection on a re-map), so zones survive a re-map with
silently re-interpreted geometry. The active-map guard (§5) only protects against cleaning while a
*different* map is loaded, not against the same map being re-mapped. Within an unchanged map,
zones + overrides are stable across sessions (the normalized frame doesn't drift).

## 11. Waves (each shippable, additive)

1. **Storage + services** — `saved_zones` collection, `_migrate_saved_zones`, create/rename/delete,
   snapshot summary. No bucketing yet (flat list).
2. **Bucketing** — the room-mask membership computation (90%-of-floor), `room_number` only (no
   `rooms[]` breakdown is persisted — §3), `set_saved_zone_room` override.
3. **Card UX (BUILT/SHIPPED)** — draw→name→save (via `_zoneDrawPurpose="save"`), room-grouped
   multi-select list, room-picker, clean (ONE "Clean N selected" batch control — selecting a single zone IS the single-zone clean; the card never calls the singular `clean_saved_zone`), delete,
   m² + validation. Implemented across `src/{state,renderers,bindings,actions}/saved-zones.js` and
   registered in each layer's `index.js`; the panel renders in the Rooms view (`renderers/rooms.js`
   calls `renderSavedZonesPanel`).

## 12. Non-goals / open

- **Not** map editing (no-go zones, virtual walls) — the app owns that.
- **Not** voice ("clean under the couch") — that's the back-burnered wizard; saved names would be a
  natural vocabulary *if* it's ever revived, but no dependency here.
- ~~**Confirm** the per-brand zone limits (count + m²) and whether Roborock exposes the same size
  bounds as Eufy.~~ **RESOLVED** — declared per adapter (capabilities: `zone_max` + the
  `zone_min/max_area_m2` / `zone_min/max_side_m` quartet) and enforced in `dispatch_zone_clean`
  (§9); Eufy caps per *side*, Roborock per *area*.
- ~~Decide the exact snapshot shape of `SavedZoneSummary` (heavy `geometry` in or out).~~
  **RESOLVED (W1):** the full zone (geometry included) rides in the `get_map_segments` read — a
  point list is negligible beside the base64 map image already in that payload (the "unbounded
  points" bloat concern was raised in review and refuted). No `min`/`max` point cap (the sibling
  segment/primitive stores are unbounded too).

**Wave 1 review outcome (2026-07-02):** 3-lens adversarial review → 2 confirmed findings, both the
same class — the `geometry` schema accepted **non-finite** (NaN/inf, which orjson silently nulls on
save) and **out-of-range** coords. Fixed by `_saved_zone_coord`: reject non-numeric/bool/non-finite
(fail loud), clamp finite to 0-1, round — mirroring `_handle_set_hidden_regions`. Locked by a test.

**Wave 2 (2026-07-02):** `zone_membership` (pure raster tally in `map_source.py`, reusing
`normalize_rendered`/`point_in_polygon`, but NOT `_area_m2` — the footprint is its own bbox-span math,
offset-independent so "size shown == size cleaned") + `async_get_map_data_dict` (coordinator accessor,
memory→`.storage`, Eufy-only, degrade-to-None) + best-effort compute in `create_saved_zone` +
`set_saved_zone_room` filing override. **Review → 1 finding (map-mismatch):** the compute read the
*current* map's raster with no check it matched the zone's `map_id` — could file wrong-map
membership on a multi-map device. **Fixed:** compute only when the active map
(`get_active_map_id`) matches `map_id` **or is indeterminate**; a definite mismatch leaves `None`
— mirroring the dispatch-path `map_mismatch` guard. (Note the asymmetry vs the CLEAN path, which
refuses on indeterminate rather than proceeding — RP-029: a wrong *filing* is recoverable by
re-editing `room_number`, a wrong *clean* is not.) Locked by a test. (LOW severity — unreachable
via the card's author-on-active-map flow + the fork can't read a non-active raster until PR #150,
but the guard makes it correct-by-construction.)

## Cross-links

- [map-state-source.md](../design/shipped/map-state-source.md) / [12 — Where the Map Comes From](../12-map-source.md) — the frame + size + room-mask this reuses.
- [data-model.md](../03-data-model.md) — the map bucket + the `custom_layouts` pattern this mirrors.
