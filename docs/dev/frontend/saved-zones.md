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
| Stable, drift-immune frame | `map_state_source` normalized 0–1 (provider's own segmentation, **not** the drifting pose) | [map-state-source.md](../map-state-source.md), [map-source-coordinator.md](../31-map-source-coordinator.md) |
| Zone **size** (m²) | per-room `area_m2` / `width_m` / `height_m` from map resolution — same math for a drawn box | `map_source.build_map_source_result` |
| Named, per-map, user-authored **collection** storage | `custom_layouts: dict[id, CustomLayout]` on the map bucket + `_migrate_custom_layouts` + summaries + `create/rename/delete_custom_layout` services | [data-model.md §Segment stores](../03-data-model.md), `mapping/mapping_services.py:2299+` |
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
    "id":            str,            # generated, like layout_id
    "name":          str,            # USER string ("the couch") — data, never i18n (see §7)
    "geometry":      [[x,y],...],    # normalized 0–1 quad — THE zone; dispatch works off this ALONE
    "area_m2":       float,          # computed from map dims at author time (display + validation)
    "room_number":   int | None,     # FILING ONLY (§4): auto-set at author by ≥90% dominance, else
                                     #   None ("Unassigned"); user-editable; NEVER affects dispatch
    "kind":          str,            # "clean" (default); reserved for future kinds
    "map_version":   ...,            # invalidation key (§6)
}
```

There is deliberately **no** persisted `rooms[]` breakdown and **no** separate `room_override` — the
dominance % is a transient author-time compute, and since a re-map invalidates the zone (§10) there
is no re-compute that a stored override would need to survive. `SavedZone` is **lighter than a
`CustomLayout`** — one box + name, not a whole segmentation.
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

- `create_saved_zone` — `(vacuum_entity_id, map_id, name, geometry)` → computes `area_m2` +
  `room_number` (≥90%-of-floor dominance, filing only), stores, returns the `SavedZone`.
- `rename_saved_zone` — `(…, zone_id, name)`.
- `delete_saved_zone` — `(…, zone_id)`.
- `set_saved_zone_room` — `(…, zone_id, room_number | null)` → sets/clears `room_number` (filing
  only; null = Unassigned; **no effect on dispatch**).
- `clean_saved_zone` — `(…, zone_id, clean_times?)` → converts `geometry` → device coords **at call
  time** (§6) and fires the existing zone-clean dispatch. `clean_times` is the optional number of
  cleaning passes (min 1).
- `clean_saved_zones` — `(vacuum_entity_id, map_id, zone_ids[], clean_times?)` → fires the whole
  selected set as one ad-hoc zone clean (fire-and-forget; per-brand caps: Eufy up to 10 zones/side
  0.5–10 m, Roborock up to 5 zones/1 ft²–3.05 m² each; JS wrapper `cleanSavedZones`).

Each runs `_migrate_saved_zones` first, degrades safely, and the snapshot carries a
`SavedZoneSummary` catalog (like `custom_layouts`) for the card.

## 6. Dispatch + drift-safety (the one hard rule)

**Store normalized, convert at clean-time — never persist absolute cm.** The provider re-origins
its coordinate frame per session; the map-relative (normalized) frame is stable, but a cached cm
quad is not. So `clean_saved_zone` converts `geometry` → device coords from the **current**
session's map geometry (`normalized_rects_to_quads_cm`) each time, exactly as live zone-drawing
already does, then routes to the per-brand zone-clean path. Saved zones must not shortcut this by
caching a quad.

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
card **chrome** (buttons, section headers, the "Spans rooms" label, validation messages) routes
through i18n.

## 8. Card UX

- **Author:** draw a box on the map → name it → save (`create_saved_zone`). Live m² shown while
  drawing; the size/ count limits gate here (§9).
- **Browse:** the saved-zone list, **grouped by `room_number`** (room sections in map order, the
  **Unassigned** special-cases section last). Each entry shows name + m².
- **Reassign:** a room picker per zone (`set_saved_zone_room`) — a filing action only; None =
  Unassigned.
- **Clean:** tap a saved zone → `clean_saved_zone`. Multi-select → `clean_saved_zones` batch
  (respecting the zone cap).

## 9. Validation (free, from the size calc)

The m² calc doubles as the device-limit gate: reject/auto-tile a too-big zone, block a too-small
one, cap total zones per clean (~≤10, ~0.5–10 m² per zone — confirm per brand). Enforced at author
+ at clean-time.

## 10. Invalidation

Saved zones are keyed to the **map version**. A genuine **re-map** changes the `room_pixels`
raster → the stored geometry no longer means the same thing → the map's saved zones invalidate
(same as phantom rooms / the other per-map dicts handle a re-map). Within a map version, zones +
overrides are stable across sessions (the normalized frame doesn't drift).

## 11. Waves (each shippable, additive)

1. **Storage + services** — `saved_zones` collection, `_migrate_saved_zones`, create/rename/delete,
   snapshot summary. No bucketing yet (flat list).
2. **Bucketing** — the room-mask membership computation (90%-of-floor), `rooms[]`/`room_number`,
   `set_saved_zone_room` override.
3. **Card UX (BUILT/SHIPPED)** — draw→name→save (via `_zoneDrawPurpose="save"`), room-grouped
   multi-select list + Spans-rooms, room-picker, clean (single + "Clean N selected" batch), delete,
   m² + validation. Implemented across `src/{state,renderers,bindings,actions}/saved-zones.js` and
   registered in each layer's `index.js`; the panel renders in the Rooms view (`renderers/rooms.js`
   calls `renderSavedZonesPanel`).

## 12. Non-goals / open

- **Not** map editing (no-go zones, virtual walls) — the app owns that.
- **Not** voice ("clean under the couch") — that's the back-burnered wizard; saved names would be a
  natural vocabulary *if* it's ever revived, but no dependency here.
- **Confirm** the per-brand zone limits (count + m²) and whether Roborock exposes the same size
  bounds as Eufy. *(still open — Wave 3 validation gate)*
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
`_area_m2`/`normalize_rendered`/`point_in_polygon`) + `async_get_map_data_dict` (coordinator accessor,
memory→`.storage`, Eufy-only, degrade-to-None) + best-effort compute in `create_saved_zone` +
`set_saved_zone_room` filing override. **Review → 1 finding (map-mismatch):** the compute read the
*current* map's raster with no check it matched the zone's `map_id` — could file wrong-map
membership on a multi-map device. **Fixed:** only compute when `map_id` == the active map
(`get_active_map_id`), else leave `None` — mirroring the dispatch-path `map_mismatch` guard. Locked
by a test. (LOW severity — unreachable via the card's author-on-active-map flow + the fork can't read
a non-active raster until PR #150, but the guard makes it correct-by-construction.)

## Cross-links

- [map-state-source.md](../map-state-source.md) / [map-source-coordinator.md](../31-map-source-coordinator.md) — the frame + size + room-mask this reuses.
- [data-model.md](../03-data-model.md) — the map bucket + the `custom_layouts` pattern this mirrors.
