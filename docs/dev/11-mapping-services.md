# 11 — Mapping Services

**Scope.** The 29 services that write a map's stored representation: its images, its
segmentation, how it is displayed, and the reusable regions drawn on it. All of them live in
`mapping/mapping_services.py` and all of them write under `maps[<vacuum>][<map_id>]`.

Everything here is state anchored to something that can be replaced underneath it. An image
gets re-uploaded; the active layout changes; rooms renumber. So the recurring question in this
subsystem is not *how do I store this* — it is **what happens to the dependents when the thing
they were anchored to goes away.** Each section below is largely an answer to that.

The file is not split, and the sections below address regions of it directly:

| section | anchor | handlers |
|---|---|---:|
| Images and the segment cache | `mapping/mapping_services.py#BN6NPMKA` | 5 |
| Custom segmentation | `mapping/mapping_services.py#BNC3PSH3` | 4 |
| Layout lifecycle | `mapping/mapping_services.py#BNS7MCWP` | 4 |
| How the map looks | `mapping/mapping_services.py#BN436BDT` | 10 |
| Saved zones | `mapping/mapping_services.py#BNWZH4DA` | 6 |

---

## 1. Two modes, resolved once

A map is segmented either by computer vision over an uploaded image (`cv`) or by hand-authored
primitives (`custom`). `segmentation_mode` selects, and `active_custom_layout_id` names which
custom layout is live.

**`_resolve_active_scope` collapses that pair once**, into a uniform
`{segments_store, links, anchors, backdrop_variant}`, and every reader and writer goes through
it. That is what keeps the two modes from being two code paths.

It returns **the same shape in every case**, plus a `resolved` boolean — rather than `None` for
custom-mode-with-no-layout. Returning `None` would force every read-only caller to branch
defensively for a state that is perfectly legitimate to read.

⚠ **Writers must test `resolved`; readers need not.** On the unresolved branch the stores are
fresh dict literals bound to nothing. A writer that takes `scope["links"]`, mutates it, calls
`async_save()` and returns `saved: True` has written into an object that is discarded on return
— a silent, reported-as-successful no-op.

**`segment_room_links` and `companion_anchors` are the same two key names at two levels**:
map-bucket for CV, per-layout for custom. The resolver is the only thing keeping them apart.

---

## 2. Images and the segment cache · `#BN6NPMKA`

This section owns the only bytes on disk in the mapping system — PNGs under
`<config>/eufy_vacuum/maps/<object_id>/`, their `image_variants` records, and the
`image_segments` cache derived from them.

### The cache outlives its image, deliberately

When a CV source image is replaced or deleted, the cached segmentation is **marked stale and
still served** — `image_segments["stale_since"]` gets an ISO stamp. It is not dropped.

Dropping it would orphan every saved zone, custom layout and furnished-art anchor keyed to
those segment ids for the whole re-analyze window. A user deleting a bad `dark` upload would
lose their zone filing until a successful CV pass — one that may not even be installable, since
numpy, Pillow and scipy are all optional.

**Staleness is a flag and a cache-gate clause, not a trigger.** Upload and delete never re-run
the segmenter; the CV pass is a 10–30 second blocking step. Nothing clears `stale_since` by
hand either — a successful analysis assigns a whole new result dict, so the flag disappears with
the dict it lived on.

*Scope:* only `dark` / `default` / `light` can mark anything. Roborock declares
`segmenter_engine: noop_fallback`, so its analysis never becomes available and this whole path
is inert there.

### One guarded call, not three

The `_CV_SOURCE_VARIANTS` membership test lives **inside** `_mark_segments_stale_for_variant`,
and the call sits **before** upload's art and backdrop branches. Those branches force
`custom_<layout_id>`-shaped variant keys, none of which are in the frozenset — so one guarded
call above them is provably equivalent to three guarded calls below. Move it into the branches
and the plain upload path silently loses invalidation.

### Dimensions have three sources and a refusal

PNG IHDR bytes first, then Pillow, then caller-declared `image_width`/`image_height`. If all
three fail the upload **refuses** with `unreadable_image_dimensions` and unlinks the PNG it just
wrote.

IHDR needs no dependency — the spec fixes it as the first chunk. Pillow is genuinely optional.
And **the declared fallback is dead**: those two fields are optional in the schema and appear
nowhere in `src/`, so the card never sends them. Reorder the chain to try Pillow first and the
common case regains a dependency on an undeclared package.

> ⚠ **A known asymmetry, not a rule.** A post-write layout-relink failure returns
> `saved: False, reason: layout_not_found` — but unlike the dimension refusal three lines above
> it, it does **not** remove the file it wrote, and it returns *after* the `image_variants` row
> has been written into the live bucket. The PNG stays on disk and the next `async_save()` from
> anywhere persists a variant no layout points at.

---

## 3. Custom segmentation · `#BNC3PSH3`

A map can hold many named layouts, each a no-CV segmentation authored from primitive shapes over
its own backdrop, owning its own segments, links and anchors.

**`layout_id` is required on `set_custom_segments`, and the handler re-checks it.** The previous
active-layout fallback meant a destructive replace-all landed on whatever happened to be active:
authoring in one layout while another was active destroyed the second's geometry, with no way
for the caller to name its target.

**Migration copies, it does not move.** `_migrate_custom_layouts` folds only those
`segment_room_links` and `companion_anchors` entries that resolve against the legacy custom
segments into the new default layout, and leaves the map-level dicts fully intact. Those dicts
were *shared* between CV and the single legacy custom store — a move would silently strip CV
mode of every link that also happened to be a custom one. The copy is why toggling between
modes is lossless.

**An authored segment is built in the exact shape the CV segmentor produces** —
`source: "custom"`, `confidence: 1.0`, and every CV field including the ones authoring never
uses. Trim it to a leaner custom-only schema and every downstream consumer needs a
`source == "custom"` branch.

**`_apply_segment_adjustments` always returns copies**, even for segments with no adjustment.
It feeds a service *response* which the caller then enriches in place — pass-through by
reference meant a read endpoint was writing derived fields back into the store.

> **The migrated default layout keeps the bare `custom` variant key** rather than being renamed
> to `custom_<layout_id>` for uniformity. Pre-layouts installs uploaded their tracing image
> under `image_variants["custom"]`; renaming on migration would orphan that file and leave the
> layout with no backdrop.

---

## 4. Layout lifecycle · `#BNS7MCWP`

Create, rename, delete, set-active — four handlers, 144 lines.

⚠ **This section is not independently reviewable, and its size is misleading.** Every one of
the four handlers opens with `ensure_map_bucket` + `_migrate_custom_layouts`, and
`_create_layout`, `_generate_custom_layout_id`, `_active_custom_layout` and
`_resolve_active_scope` all live under `#BNC3PSH3`. A change to layout identity or resolution is
a change to §3, wherever the handler happens to sit.

**Deleting the last layout forces `segmentation_mode` back to `cv`**, and delete also pops the
layout's backdrop and every art variant row from `image_variants` — reaching into §2's storage
to do it. Adding a fourth art-bearing field to a layout without extending that sweep leaves
orphaned rows behind.

---

## 5. How the map looks · `#BN436BDT`

Ten services that persist how the map is **displayed**, never what gets cleaned. Two storage
tiers with different rules, and the split is the substance:

| tier | services | why |
|---|---|---|
| **active layout** | furnished art placement, render mode, room viewport | art must not leak across layouts |
| **map bucket** | hidden regions, live map rotation, overlay visibility | they describe physical or display facts that outlive any segmentation mode |

**`hidden_regions` is map-level and not resolved through `_resolve_active_scope`**, unlike every
other user-drawn overlay here. A mask covers a physical region of the home and is drawable only
over the device-frame backdrop, so it follows the map across mode and layout switches. Put it
under a layout and a user's masks vanish when they switch.

**The furnished-art writes address the active layout implicitly** — none of the three schemas
carries a `layout_id`, unlike the authoring service next door which was hardened to require one.
So the art *image* names its layout and the art *transform* takes whatever is active: switching
layouts between opening the aligner and dropping the art lands the transform elsewhere.

**Values are clamped at the write, not only in the card** — `scale` and `zoom` to `[0.05, 20]`,
viewport `cx`/`cy` to `[0, 100]`. The renderer coerces with `Number(scale) || 1`, so a stored
`0` would render as `1×` and leave state and screen disagreeing with nothing to indicate it.
`tx`/`ty` are deliberately unclamped.

**A blank `room_id` means "layout-level default" for render mode, and is rejected as
`missing_room_id` by placement and viewport.** A transform or viewport with no room is
meaningless; a render mode legitimately has a layout-level default. Making it uniform in either
direction breaks one of the two.

**Overlay visibility persists deltas only**, merged over the defaults at read time, with
`reset: true` popping the key. Store the resolved map instead and every shipped default is
frozen permanently at the value it had when the user first touched the panel.

> **`FURNIS-6`:** a whole-home art *clear* does not `setdefault("home_art", {})` — it reads the
> existing dict or gives up, while room scope keeps its unconditional `setdefault`. The resolver
> decides "has whole-home art" by `home_art is None` but decides per-room data *per field*, so a
> present-but-empty `home_art: {}` reads as furnished data and flips the whole projection.

---

## 6. Saved zones · `#BNWZH4DA`

A named, reusable clean region on one map: a normalized 0–1 polygon, a display name, an advisory
`area_m2`, an advisory `room_number`, and a `kind`.

**Stored as a polygon, acted on as a bounding box.** Both clean handlers reduce geometry to
`[min(xs), min(ys), max(xs), max(ys)]`, and `area_m2` is computed from that same bbox rather
than from the true polygon. *Size shown equals size cleaned*, by construction. The bbox formula
also depends only on width, height and resolution — not on the room-outline offset — so it
cannot ride an offset bug the way a rasterised cell count could.

**The same signal drives opposite policies, and each site says so.** When `get_active_map_id`
returns `None`:

- the two **dispatch** paths refuse — a zone is never fired without positive evidence the right
  map is loaded;
- the two **filing/sizing** paths proceed — an advisory value computed against an
  indeterminate map is worth more than no value.

**Zone ids come from a process-lifetime monotonic counter**, with the collection-membership
check demoted to a fallback. The id is a durable foreign key held *outside* this domain — a
`queue_breaks` zone step, a run-profile step — and under the old scheme a create/delete/recreate
inside one wall-clock second regenerated the identical id, colliding with references still
pointing at the deleted zone. **Custom layout ids still use the old scheme**; whether that is a
defect is unsettled.

**A degenerate bbox is rejected at create time**, mirroring dispatch's own minimum-side check.
There is no set-geometry service here — create, rename, delete, set-room, clean — so a
degenerate zone that persisted could never be repaired: it saved cleanly and then failed every
clean attempt.

**`clean_saved_zones` is atomic.** One missing or bad zone refuses the whole batch. The other
consumer of the same store does the opposite and cleans what resolves.

---

## 7. Common wrong assumptions

| assumption | actually |
|---|---|
| the card can save custom segments | it cannot — check the write surface before assuming a UI path exists |
| `adjust_map_segment` follows the active scope like the rest of §3 | it does not |
| a saved zone is cleaned as the polygon you drew | it is reduced to its bounding box, and `area_m2` reports that same box |
| deleting a map image clears the segments derived from it | they are marked stale and still served |
| `layout-crud` is a small self-contained area | its helpers are all in §3, and every handler calls them |
| `hidden_regions` follows the active layout, like other overlays | it is map-level on purpose |
| an unresolved scope is safe to write through | the stores are unbound literals; the write is a successful-looking no-op |

---

## Registries

[00b-invariants.md](00b-invariants.md) — `IN` rules and their consequences.
[00c-replicas.md](00c-replicas.md) — `RN` sets, where one rule has more than one copy.
