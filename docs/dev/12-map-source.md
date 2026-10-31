# 12 — Where the Map Comes From

**Scope.** The provider's own segmentation and pose, normalized into one brand-neutral shape:
per-room bbox, name and area, plus the moving overlays — robot and dock anchors, current room,
path, hazards. Everything is a float 0..1 of the **rendered** image with a top-left origin.

What a map's stored state holds once it arrives is [11 — A Map's Stored State](11-map-stored-state.md).

Two brands feed this through **declarations**, not through branches in core:

| brand | `map_state_source.backend` | pose | notes |
|---|---|---|---|
| Eufy | `storage` | `inmem_pixel_pose` | the fork's `.storage` file, memory-primary off its in-memory map; pixel pose needs separately-loaded geometry to normalize against |
| Roborock | `memory` | `parsed_mapdata` | a parser `MapData` located by defensive search; pose already in the rendered frame, plus a re-decode of the raw blob's segment layer the parser discards |

---

## 1. No backend is a default

`map_state_source.live_pose.backend` is `inmem_pixel_pose` or `parsed_mapdata`. An undeclared or
unrecognised value is reported **as itself** — `unknown_pose_backend:<name|undeclared>` — and
never falls through to a reader.

The rejected version is the one that shipped: the accessor *was* the Eufy fork reader wearing a
generic name, so anything undeclared got the fork's treatment. That collapsed **"this brand
declares no pose shape"** into **"this brand has no position"**, and the two are
indistinguishable to every consumer downstream. Roborock's position sat live on the parsed map
the card was already rendering while the accessor answered `not_configured` — the stall capture
drew rooms with no robot dot, and the pose ring banked rows with no anchors.

**A third brand stays a declaration. It never becomes a branch here.**

### The gate is checked at the second door too

`_apply_inmem_pose_to_result` tests `live_cfg["backend"] == POSE_BACKEND_INMEM_PIXELS`, not
merely that a `live_pose` dict exists. Testing for the dict was sufficient while exactly one
brand declared the block, and stops being sufficient the moment a second does — a
`parsed_mapdata` brand would drive the fork's attribute search over an unrelated provider's
internals, on the event loop, inside the dashboard snapshot, finding nothing and then paying for
a full structure dump to say so, on every refresh.

**The test that pins this was green while the gate was removed.** The method wraps its body in
`except Exception` by design, so a probe that raises is swallowed. It was rewritten to **record the
call** and assert nothing was called — and only ablation caught the difference.

Re-verified 2026-08-23, including the two sibling tests that still use a raising stub. Those probe
`async_get_map_live_pose`, whose dispatch has no `try`/`except` around it, so a raise there does
propagate and they bite as written — confirmed by ablating each backend gate in turn. **Recorded
because the distinction is the useful part:** record-the-call and raise-in-a-stub are not
interchangeable styles, and which one is correct depends entirely on whether the seam under test
swallows. A raising stub in a never-raises seam proves nothing and looks identical to a passing
test.

---

## 2. Absence: hold the map, drop the movement

A transient absent read **holds the last-known-good map for up to six hours**, and the hold
**strips the moving fields**: `current_room` to None, `robot_anchor` to None, `path` to empty.

Two alternatives were rejected here, and the second is the interesting one:

- **Dropping the map on any absent read.** A Roborock cloud map entity going unavailable when
  the vacuum idles or docks makes the introspector report `no_parsed_map` — which would throw
  away a perfectly good map for the ordinary act of finishing a run.
- **Flagging staleness and leaving the moving fields intact**, which is what shipped first. A
  docked robot then kept *attributing* to wherever it was last seen, for the whole six-hour
  window, at whatever cadence the consumer polled. The stale flag existed and nothing downstream
  read it.

**A hold is display-only.** Geometry survives a dropout; claims about where the robot *is* do
not.

The terminal reasons that never hold — `live_map_absent`, `store_version_mismatch`,
`not_configured`, `no_device`, and any unknown backend — are the ones where holding would serve
a map that is not this vacuum's, or not this map. Everything else is transient.

### The cache key carries `map_id`, and that is load-bearing

The `.storage` mtime cache hits on `(mtime, presence gate, map_id)`. The fork's file is
**per-vacuum, not per-map**, so its mtime does not vary by which map is being asked about. Key
on mtime alone and two different maps queried close together legitimately share one — the second
silently inherits the first map's geometry. The hold path carries the same guard, for the same
reason.

---

## 3. Normalization, and where clamping lies

`normalize_rendered` defaults to **clamping** out-of-grid points. Only the pose and anchor
callers opt into rejection.

For those callers a clamped point is indistinguishable from a legitimate point *at the edge*, so
clamping silently reports "off the map" as "at the wall". It stops there: the companion
current-room lookup is handed the RAW pixel, and `current_room_for_pixel` bounds-checks the
derived raster index, so an off-grid anchor yields `None` rather than the room owning that wall.
The observed failure is the pair disagreeing — a confident edge position beside no room at all.
For room geometry the opposite holds: a room whose
bbox slightly exceeds the grid is still that room, and rejecting it loses a real room.

The same rule is implemented twice, once per brand path, deliberately.

### The Eufy outline offset is a measurement

The `room_outline` → main-grid offset **sign** is not derived; it was measured, and it is the
single source shared by per-room extraction, the current-room lookup and saved-zone filing.

On a stored map whose outline origin sits 105 cells from the map origin, the shipped sign
overlays the segmentation floor onto the rendered floor at ~93%. The other plausible reading of
`origin + index*res` gives **under 1%** — rooms land nowhere near their pixels. One source, not
per-call-site copies, because two copies of a measured sign is two chances to invert it.

*Eufy only. Roborock has no separate outline frame, and its zero offset is itself a measurement
rather than an absence.*

---

## 4. Two decoders would be one too many

**The in-memory Eufy map is base64-encoded so the existing `.storage` decoders consume it
unchanged.** The alternative was a second, object-shaped decoder — and two decoders of one map
is the failure this codebase keeps re-learning.

It returns `None`, not a partial dict, when `room_pixels` is not bytes or when any of the four
`_MAPDATA_REQUIRED_GEOMETRY_FIELDS` — `width`, `height`, `room_outline_width`,
`room_outline_height` — is missing. A partial dict *looks* usable because it carries the raster,
and then the geometry step hard-requires the four fields it lacks. `resolution` is **not** in that
set: a MapData without one converts fine and the geometry step falls back to 5.

**The in-memory content version hashes the raster bytes plus the origin and resolution**, unlike
the sibling render path which hashes the raster alone. The raster does not say where its pixels
*sit*: a re-map to the same room shapes at a new origin is a real content change that a
raster-only hash reads as a cache hit.

**Roborock's raw re-decode is emitted under Eufy's format name**, with the image block's
`top`/`left` carried as `raw_top`/`raw_left` and deliberately **not applied** — the parser's own
projection already carries that correction, and applying it again double-corrects. The values
are emitted rather than dropped because they were measured, on hardware, at 281/245: about 12
metres of offset if anyone ever applies them by mistake.

The shared format name is not sloppiness — it is what lets Roborock ride the same frontend
decoder instead of shipping a second one.

---

## 5. Finding the data at all

Both brands locate their map by searching a provider's internals, and both searches are
narrower than they look.

**Roborock duck-types for `.rooms` *and* `.image`**, not for a generic bbox-like collection. The
generic predicate also matches no-go areas, walls and zones — all bbox-shaped — so the search
would happily return a hazard layer as "the rooms", and the room list would be silently wrong
rather than empty.

**The Eufy pose holder is matched on its attributes *existing*, not on the robot pixel currently
being a coordinate pair.** The fork nulls that pixel while the robot is docked, so value-matching
misses a docked robot entirely — which is exactly the case the live read exists to serve. A
non-pair robot pixel with a valid dock resolves the robot to the dock.

---

## 6. Which vacuum is this? (the in-memory reads)

The `.storage` read has been per-vacuum since the feature landed: `eufy_store_path` resolves
the device-registry serial and opens `robovac_mqtt.<serial>`. The in-memory reads added the
same day — a faster path in front of it — did not inherit that, and for four months every one
of them answered from whichever coordinator the walk reached first.

**The provider holds every vacuum in one place.** `hass.data["robovac_mqtt"][entry_id]` is
`{"coordinators": [...]}` — a LIST per entry, and the bucket spans entries. So the unscoped
roots contain the whole house, and the introspectors downstream stop at the first object
carrying the attrs they want. With two Eufy vacuums the second showed the first's pose, rooms,
raster and render data. **It never required a shared account**; the issue title says one, but
the bucket is keyed by entry and the collector returned all of it.

`map_state_source.device_id_attrs` names the coordinator's own id attr. Core matches it against
the same registry serial `store_key` already fills from, so the memory and storage paths cannot
disagree about which vacuum they are reading.

Two independent checks, deliberately:

| layer | what it does |
|---|---|
| `eufy_inmem_candidates(..., device_id=)` | returns the matching coordinator **alone** |
| `eufy_mapdata_obj_from_candidates(..., device_id=)` | re-checks that the raster holder carries the same id |

**The scoped root REPLACES the shared roots rather than preceding them.** The introspectors fall
through on a miss, so leaving the bucket behind the scoped root would mean a vacuum whose own
map is briefly absent silently inherits its neighbour's. Absent is the correct answer there, and
the per-vacuum storage path behind it answers correctly anyway.

**The fallback is load-bearing in the other direction.** No serial, or no coordinator carrying a
matching one, degrades to the old unscoped roots — so a single-vacuum install, and any provider
whose shape stops exposing the attr, behave exactly as before. The second-layer `device_id` is
therefore passed **only when the scoping actually matched**; handing it down after a fallback
would turn "this provider exposes no id" into `device_not_found`, i.e. absent, for installs that
work today.

> **Why it reached users.** This needs two vacuums of one brand. The development box has
> three — one Eufy, one Roborock, one Dreame — so it cannot reproduce it at all, and no
> amount of testing there would have surfaced it.

**Roborock had the same defect, and a release note claiming otherwise is how it was found.**
The 2.5.2 pre-release audit refuted a sentence asserting both sibling collectors had been
per-vacuum from the start. `dreame_coordinator` is: it resolves through the device registry.
`roborock_candidates` takes an `image_entity_id`, but **two of its four callers passed
none** — `_read_mapdata_pose` and `async_get_map_render_data` — so the live pose and the room
raster walked a duid-keyed container of every Roborock on the account and took the first hit.
The two that did pass one still had the shared roots behind it to fall through to.

Both brands now go through `_scope_roots_to_device`, the policy written once: `device_id_attrs`
is declared per brand (`device_id` for Eufy, `duid` for Roborock) and matched against that
brand's own registry identifier. Roborock's image-entity root is already resolved from the
asking vacuum, so it is kept alongside the match rather than replaced by it; the shared roots
are dropped either way.

No Roborock user has reported this, and it is unconfirmed on hardware for the same reason the
Eufy half is — one vacuum per brand here.

---

## 7. Common wrong assumptions

| assumption | actually |
|---|---|
| the catch-all room sentinel is one constant with one meaning | there are **two**, with different values *and* different bit widths, and neither is derivable from the other |
| functions marked pure and "never raises" are safe on the event loop | purity is not loop-safety. This unit contains an `O(width × height)` pure function |
| the `present_requires_live_map_image` gate means the live map is working | it tests presence in the **state machine**. An `unavailable` entity still has a State object and passes |
| an mtime cache hit re-applies the current pose, so a moving robot is never frozen | true of the **return value**, false of the **cache** — the hit branch mutates a shallow copy |
| ~~the multi-vacuum cross-contamination guard is closed~~ | **CLOSED 2026-10-27** (issue #77). It was true for four months: the `device_id` filter on `eufy_mapdata_obj_from_candidates` was correct and tested ([MSR-2o]) and **no call site passed it**, so the row sat here describing a live field defect as a curiosity. See §6 |
| the render format `room_pixels_v1` is Eufy-specific, or the legacy `eufy_room_pixels_v1` key is dead | it is the card's **brand-agnostic** decoder name (all three brands emit it — Eufy and Dreame declare it in `map_render`, Roborock builds it in `mapping/roborock_raw_map.py::roborock_render_data`), renamed to drop the brand word; the coordinator still **dual-accepts** the legacy `eufy_room_pixels_v1` for one release so a stored config isn't stranded |
| the render-data candidate walk tries every root until one yields a usable render | it short-circuits on a partial success — an absent-marker dict is not `None` |

---

## Registries

[00b-invariants.md](00b-invariants.md) — `IN` rules and their consequences.
[00c-replicas.md](00c-replicas.md) — `RN` sets, where one rule has more than one copy.
