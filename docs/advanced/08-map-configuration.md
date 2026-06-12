## Map Configuration

The **Map Configuration** view lets you upload map image variants and define the segment polygons that the integration uses to render the interactive floor plan. There are two ways to get those polygons: **Auto (CV)**, where the integration detects rooms from an uploaded map screenshot, and one or more named **custom layouts**, where you draw the rooms by hand from primitive shapes. A single map can hold **many** custom layouts — for example a "solar system" image and a "tree" image as two separate layouts on the same physical map — each with its own backdrop, hand-drawn rooms, room links, and mascot dock spot. A **Segmentation** picker selects between Auto (CV) and any of the named layouts; all of them persist independently, so switching never loses any of them.

> **This page is the technical reference** — image variants, the segment data model, the services, and the internals. For the hands-on, click-by-click guide to setting a map up, see **[Making your own maps](../user-guide/16-making-your-own-maps.md)** in the user guide.

You reach the view by enabling **map view** in the Rooms tab and clicking **Configure map**; it opens the `MAP_CONFIG` view (a "Rooms" back-arrow returns you), with all segment polygons visible in the map panel throughout.

---

### What the view shows

The Map Configuration view has three areas:

- **Map panel** (top) — the floor plan image with all segment polygons overlaid. In CV (config) mode the polygons are rendered at reduced opacity until selected; click any polygon to select it. In Custom mode this area becomes the composer canvas where your draft shapes are drawn.
- **Side panel** (right) — segment adjustment controls in CV mode (shown once a polygon is selected), or the **Compose rooms** toolbar in Custom mode.
- **Bottom panel** — a **Segmentation** picker (an **Auto (CV)** chip plus one chip per named custom layout, a **＋ New** button, and — when a layout is active — **Rename** / **Delete layout** controls) followed by either the **Image Variants** section (CV mode, with upload controls and an Analyse button) or the **Custom backdrop** section (custom mode).

#### The map-view toolbar

The Rooms-tab map view carries its own toolbar (companion-animal select, icon-size slider, mascot toggle, floor-texture toggle) — walkthrough in the user guide's [The mascot and floor textures](../user-guide/16-making-your-own-maps.md#the-mascot-and-floor-textures). For reference, the two toggles persist per vacuum in `localStorage`: **`evcc_animal_on_<vacuum>`** (mascot, default on) and **`evcc_floor_tex_<vacuum>`** (floor textures, default on). The **Segmentation** picker (Auto (CV) plus the custom-layout chips) is *not* on this toolbar — it lives in the bottom panel of the Map Configuration view itself.

---

### Image variants

The `upload_map_image` service accepts a `variant` field. The validator allows the four fixed values `default`, `dark`, `light`, and `custom`, plus any per-layout `custom_<layout_id>` key. The first three are segmenter inputs; the rest are manual-drawing backdrops. Each variant serves a distinct role:

| Variant | Role | Purpose |
|---|---|---|
| **Dark** | Primary | Clearest room colour separation — preferred input for segment detection |
| **Light** | Assist | Wall and boundary detection, used alongside the dark variant |
| **Default** | Fallback | Used when no dark variant is available |
| **Custom** / **custom_&lt;layout_id&gt;** | Backdrop | The tracing image for a custom layout. **Never** auto-segmented — the analyser only ever reads the dark/default/light variants. Each named layout owns its own backdrop, stored under its own `custom_<layout_id>` key; the legacy single `custom` variant is the backdrop of a migrated default layout. The active backdrop's recorded pixel dimensions become the canvas the custom-segment writer rasterises against. |

The Image Variants section (CV mode) shows the dark, light, and default variants' current upload status. Uploaded variants display their pixel dimensions (width × height); missing variants show "not uploaded". Each layout's backdrop is uploaded and managed separately, from the **Custom backdrop** section shown in custom mode — and it always targets the **active** layout.

---

### Image size, resolution & format

Every image you upload — a CV variant or a custom backdrop — is sent to Home Assistant inside a **single websocket message**, and HA caps that message at **4 MiB** (an aiohttp default; there is no configuration option to raise it). Images travel base64-encoded, which inflates them by ~33 %, so the practical ceilings are:

| | Value |
|---|---|
| Hard websocket frame limit | **4 MiB** (4,194,304 bytes) — exceeding it drops the connection |
| Safe **encoded** payload (what the card targets) | ≤ ~3.4 MB of base64 (**~19 % under** the frame limit) |
| Equivalent **raw image** size (the rec) | ≤ **~2.5 MB** |
| Where uploads begin to fail | ~3 MB of raw image and up |

The recommended ~2.5 MB raw target deliberately sits **10–20 % under** the point where uploads start to fail, so there is margin for the JSON envelope and format variation. Stay under it and an image uploads at full quality with no recompression.

If a payload overruns the limit, HA closes the socket: the browser console shows `ERR_CONNECTION_LOST` (logged as a bare `3`), often followed by unrelated "Subscription not found" noise while the frontend reconnects. The upload status shows **"Image too large even after resizing — pick a smaller image."**

The card sizes every upload to stay under that ceiling automatically, but it does so **differently for the two image roles** — which is why their recommendations differ.

#### CV variants (dark / light / default) — keep these small yourself

These feed the segmenter, so the card must **not** silently shrink them: rescaling would knock the dark/light pair out of alignment (the segmenter only tolerates a ~6 % scale difference between them) and push small rooms below the segmentor's fixed pixel-area thresholds, quietly degrading room detection. So the card **passes a CV image through untouched when it fits**, and **rejects it with a clear message when it doesn't** — it never downscales it for you.

In practice this is rarely a problem — an Eufy app screenshot is usually 1,000–1,600 px on the long side and well under 300 KB. Guidelines:

- **Format:** **PNG** (lossless — it preserves the crisp, flat room colours the segmentor keys on). JPEG technically works but its compression blurs colour boundaries; avoid it for CV captures.
- **Resolution:** whatever the app renders, no upscaling needed. A long side of roughly **1,200–2,500 px** is the sweet spot; there is no benefit to multi-thousand-pixel CV images and they risk the size ceiling.
- **Match the pair:** keep your dark and light captures at the **same resolution and crop** so their polygons align (see [Capturing a good map image](#capturing-a-good-map-image)).
- If you ever see the "too large" message on a CV upload, re-crop tighter or export at a lower resolution.

#### Custom backdrops — bring any picture; the card fits it

A custom-layout backdrop is a **display / tracing image only** — it is never segmented — so the card is free to resize it for you:

- It caps the long side at **2,048 px** and re-encodes to **WebP** (small, high quality) when your browser's encoder is confirmed to preserve transparency, falling back to **PNG** otherwise. It then keeps shrinking until the payload fits, so even a 10 MB photo uploads — just progressively softer the larger it started.
- For the **sharpest** result, pre-size the backdrop to **≤ 2,048 px on the long side** and **≤ ~2.5 MB** so it uploads at full quality with **no** recompression. (If it already fits, the card sends your original file byte-for-byte.)
- **Transparency is preserved.** A PNG or WebP with a transparent background — a cut-out tree, a planet, a logo — keeps its alpha channel, so the themeable Map surface shows through behind it. **Never flatten such an image to JPEG** before uploading; JPEG has no alpha and replaces the transparent area with a solid colour.
- **Aspect ratio:** the backdrop is stretched to fill the square drawing grid (`object-fit: fill`), so the composer's 0–100 % coordinates line up cell-for-cell with the picture. A roughly **square** image looks most natural, but any ratio works — your drawn rooms map onto it proportionally. The stored pixel dimensions become the canvas your shapes rasterise against, so resolution never distorts geometry (only the aspect ratio is visible). See [How the custom backdrop renders](#how-the-custom-backdrop-renders).

> **Rule of thumb.** Aim for a long side of **1,500–2,048 px** and a file **under ~2.5 MB** for any image (that target is ~10–20 % under the failure point). CV screenshots are normally already smaller; oversized custom backdrops are auto-fitted, but look best when you pre-size them.

---

### Capturing a good map image

The step-by-step Eufy-app capture procedure — clearing floor types, 2D mode, hiding overlays, the matched dark/light pair, cropping — lives in the user guide: **[Making your own maps → Capturing a good map image](../user-guide/16-making-your-own-maps.md#capturing-a-good-map-image)**. In short, you produce a matched **dark** + **light** screenshot pair (identical orientation and crop) plus an optional **default** display image. The points that matter for *detection* are below under [Segments](#segments).

---

### Uploading a variant

CV variants are uploaded from the **Image Variants** section (Auto (CV) mode), then analysed — walkthrough in the [user guide](../user-guide/16-making-your-own-maps.md#upload-and-analyse). CV variants are sent **as-is** (an oversized one is rejected, never silently shrunk), so prefer a **PNG** at a modest resolution; see [Image size, resolution & format](#image-size-resolution--format). For reference:

The backend converts non-PNG uploads to PNG before saving. It stores the file at `eufy_vacuum/maps/<vacuum_id>/map_<map_id>_<suffix>.png` (the dark variant uses the suffix `_dark`, light uses `_light`, default has no suffix). The browser URL for the stored file is recorded and used to render the map image in the card.

After a successful upload and analysis cycle, the variant row updates to show the measured pixel dimensions of the saved file.

The custom backdrop variants are the exception to the analyse step. Because they are never segmented, uploading one skips the re-analysis cycle entirely — the file is saved, its pixel dimensions recorded, and that is all. You upload it from the **Custom backdrop** section (see [Custom segmentation mode](#custom-segmentation-mode)) rather than the Image Variants list, and the upload always targets the **active layout**: the card passes the active `layout_id`, and the server forces the variant key to `custom_<layout_id>` and repoints that layout's `backdrop_variant`.

#### How the custom backdrop renders

The CV variants render with `object-fit: contain`, which letterboxes the image to preserve its aspect ratio. The custom backdrop instead renders with `object-fit: fill`, so it stretches to fill the square map frame exactly. This is deliberate: the composer draws on a `0–100` percentage grid (the SVG viewBox is `0 0 100 100` with `preserveAspectRatio="none"`), and `fill` makes that grid line up cell-for-cell with the backdrop picture. A shape you draw at 50 %, 50 % sits at the visual centre of the backdrop regardless of the image's native aspect ratio.

The active layout's backdrop **recorded pixel dimensions are the rasterise canvas**. When you save custom segments, the server rasterises your percentage-space shapes against those exact width × height pixels, so the resulting polygons match the backdrop you traced. Switching to a different layout swaps the backdrop image (and therefore the canvas) along with everything else.

Room-name labels render on a small semi-opaque **pill** so they stay legible over any backdrop — including a bright or busy photo where plain text would wash out. The pill's background and text colour are theme tokens (Theme editor → **Map** group), so you can dial the opacity to suit a particular image.

#### Re-analysing without uploading

If you want to re-run segment detection against the current images without uploading new files, click **Re-analyse** (or **Analyse map** if no segments exist yet). This calls `analyze_map_image` with `force_reanalyze: true` and fetches the updated segments.

The segment count and adjusted-segment count are shown to the right of the Analyse button.

---

### Segments

A segment is a polygon that the card overlays on the map and links to a room. Every map keeps a CV store at the map-bucket level plus a **named collection** of custom layouts, and the `segmentation_mode` flag (`cv` or `custom`) — together with the active layout id — decides what `get_map_segments` serves:

- **`image_segments`** — the CV store, special at the map-bucket level. Segments are detected regions in the map image, derived from colour clustering and morphological analysis of the uploaded dark/light variants. This is what Auto (CV) mode reads.
- **`custom_layouts`** — a `{layout_id: layout}` dict of named custom layouts, with `active_custom_layout_id` naming the live one. Each layout owns its own `custom_segments` store (the polygons your hand-drawn shapes rasterise into), and custom mode reads whichever layout is active.

`set_segmentation_mode` only flips the flag — it never runs the segmenter and never touches any store. The backend resolves the live store through a single `_resolve_active_scope` seam: in CV mode it points at the map-bucket keys, in custom mode at the active layout's keys. Toggling cv → custom → cv (or hopping between layout chips) is therefore lossless: every store survives the round-trip exactly as it was, and you can keep a CV segmentation alongside any number of hand-authored layouts for the same map and switch between them at will.

> **Migration.** Maps authored before named layouts existed kept a single `custom_segments` key. That legacy store is folded **lazily and non-destructively** into a default layout named "Custom" the first time the map is touched — the legacy key is copied, never deleted, and the migration is idempotent.

Whichever store is active, each segment has:

- A `segment_id` string
- A pixel-space polygon (`polygon_pixel`) and a percentage-space polygon (`polygon_pct`, 0–100 on both axes) used for SVG rendering
- A bounding box
- A center point
- Quality metadata (confidence, structural role, issues)

Segments are extracted by the `detect_room_segments` function in `adapters/eufy/segmentor.py` (re-exported through `mapping/segmenter_engines.py`), which uses a Pillow + NumPy + SciPy pipeline. The dark image variant is the primary input; the light variant assists with boundary detection when available.

Segments are not rooms. A segment is a region the image analysis found in the floor plan. You link segments to rooms manually in the side panel.

---

### Selecting and adjusting a segment (CV mode)

> This section applies to **Auto (CV)** mode. In Custom mode the side panel shows the composer toolbar instead — see [Custom segmentation mode](#custom-segmentation-mode).

Click any polygon in the map panel to select it. The polygon highlights (increased opacity, white stroke). The side panel shows four sub-sections for the selected segment.

#### Translation

Moves the entire polygon by a pixel offset. The nudge pad has arrow buttons (up, down, left, right) and a reset button (○). Each press moves the polygon by approximately 0.5% of the image dimension in that axis — for example, on a 1000 × 1000 image each step is 5 pixels. The current offset is shown as "Offset: X px, Y px". The reset button returns the translation to zero.

#### Edges

Expands or contracts individual edges of the polygon independently. Each edge (Top, Bottom, Left, Right) has a − and + button, and a current value display. The edge adjustment moves only vertices that fall within the outermost 10% band of the polygon on that axis, so vertices near the center are unaffected.

#### Vertices

Shows all polygon vertices as numbered chips. Click a chip to select that vertex; it highlights on the map as a larger yellow dot. With a vertex selected, a nudge pad lets you move that vertex independently in X or Y. The current delta for the selected vertex is shown (for example, "V3: +5, −2 px"). A reset button on the nudge pad zeroes the delta for that vertex only.

Vertices that have been moved show with a distinct style in the chip list. Clicking the same chip again deselects the vertex.

#### Link to room

A row of chips lists all rooms for the active map. Click a chip to link the selected segment to that room. Clicking again unlinks it. Each segment can be linked to at most one room, and each room can be linked to at most one segment. A chip that is already linked to a different segment is shown as disabled.

Room assignments made here apply to **CV segments**. Linking or unlinking a segment calls the `set_segment_room_link` service, which routes through `_resolve_active_scope` and writes the change to the active store's link map — in CV mode that is the map-bucket `segment_room_links` dict. Because the links live in the backend rather than the browser, they survive across browsers, devices, and HA restarts. (Earlier versions stored these assignments in the browser's localStorage; that local store was migrated to the backend bucket.) The backend may also supply room_id values on segments directly when segments were associated during analysis; those take precedence over the stored links.

In **Custom** mode the equivalent control is the composer's per-room link chips. There the link is attached to a whole merged **group** (one room) rather than an individual CV segment, and `set_segment_room_link` writes to the **active layout's own** `segment_room_links` — they are reconciled at **save time** rather than on each click. Because links are per-layout, two different layouts can each have a segment id (say `living`) linked to a *different* room without conflict. See [Custom segment composer](#custom-segment-composer) below.

---

### Custom segmentation mode

Custom mode replaces the CV segmenter with a hand-drawing workflow: you compose rooms from primitive shapes on top of any backdrop image, and the integration rasterises those shapes into the same kind of segment polygons that CV would have produced. It exists for maps where automatic detection struggles — stylised or low-contrast floor plans, themed backdrops (a space map, a blueprint), or layouts where you simply want exact control over where each room's polygon sits.

A map is not limited to one custom layout. You can keep **several named layouts** on the same physical map — a "solar system" image and a "tree" image, say — and each is fully independent: its own backdrop, its own hand-drawn rooms, its own room links, and its own mascot dock spot. Switching layouts swaps all of that at once. Custom layouts sit **alongside** the CV store, not as a "layout 0"; Auto (CV) remains a special, always-present option.

Switch into custom mode by clicking any layout chip in the **Segmentation** picker (bottom panel of the Map Configuration view), or with the `set_segmentation_mode` service with `mode: custom`. Creating your first layout (or pressing **＋ New**) auto-activates it and flips the map into custom mode for you.

#### The Segmentation picker

The **Segmentation** picker is a chip row, not a binary toggle:

- An **Auto (CV)** chip — always present; selecting it sets `segmentation_mode: cv`. Switching to Auto (CV) is lossless; it leaves every custom layout untouched.
- One chip **per named layout**, labelled with the layout name. Clicking it calls `set_active_custom_layout` (which activates that layout and flips the map to custom mode).
- A **＋ New** button — opens an inline name field; **Create** calls `create_custom_layout(name)`, which mints + activates the layout and flips to custom mode.
- When a layout is active, **Rename** and **Delete layout** controls appear. **Rename** opens the same inline name field (pre-filled) and calls `rename_custom_layout(layout_id, name)`; **Delete layout** calls `delete_custom_layout(layout_id)`.

The card state behind the picker lives in `src/state/map.js` — `customLayouts()`, `activeCustomLayoutId()`, `activeCustomLayout()`, and the inline name-editor slice (`openNewLayoutEditor` / `openRenameLayoutEditor` / `closeLayoutEditor` / `layoutDraftName` …). The CRUD calls are the new actions `createCustomLayout` / `renameCustomLayout` / `deleteCustomLayout` / `setActiveCustomLayout` in `src/actions/map.js`.

The layout services are all `supports_response`. Their behaviour:

| Service | Effect |
|---|---|
| `create_custom_layout(name)` → `layout_id` | Mints an empty layout (its own `custom_<layout_id>` backdrop variant), activates it, and sets `segmentation_mode: custom`. |
| `set_active_custom_layout(layout_id)` | Activates that layout and flips to custom mode. A `null`/unknown `layout_id` auto-creates and activates a default layout, so custom mode always resolves a live store. |
| `rename_custom_layout(layout_id, name)` | Renames the layout in place. |
| `delete_custom_layout(layout_id)` | Deletes the layout and best-effort removes its backdrop file. If it was the active layout, the next remaining layout (by name) is activated; if it was the **last**, the map flips back to `cv`. |

`get_map_segments` now reports the collection alongside the segments: its response carries `custom_layouts` (a list of `{id, name, backdrop_variant, segment_count, created_at, updated_at}`), `active_custom_layout_id`, and the active store's `segment_room_links`.

#### When to use custom layouts

| | Auto (CV) | Custom layouts |
|---|---|---|
| **Room detection** | Automatic, from the map image | Manual, you draw every room |
| **Backdrop image** | Dark/light/default screenshots, must show clean room colour regions | Any picture — never analysed; one per layout |
| **Effort** | Upload + analyse, then nudge stragglers | Draw, merge, link, save each room yourself |
| **Count** | One CV segmentation per map | Many named layouts per map |
| **Best when** | The Eufy map screenshots segment cleanly | CV mis-detects, or you want exact polygons / themed backdrops / several alternative layouts |

The modes are not exclusive: because CV and every custom layout persist independently, you can author one or more custom layouts and still flip back to CV at any time without losing any of them. (Re-running CV is the one operation that mutates a store — see the note under [Custom segment composer](#custom-segment-composer).)

#### Uploading a custom backdrop image

Each layout owns its own backdrop, uploaded from the **Custom backdrop** section in custom mode (walkthrough: [user guide](../user-guide/16-making-your-own-maps.md#1-create-a-layout-and-add-its-backdrop)). The card passes the active `layout_id` to `upload_map_image`; the server forces the variant key to `custom_<layout_id>`, saves the image, records its pixel dimensions, and repoints the layout's `backdrop_variant`. Unlike the CV variants, uploading a backdrop does **not** trigger analysis — it is a tracing image only.

Because a backdrop is display-only, the card **automatically fits it** to Home Assistant's websocket limit: it caps the long side at 2,048 px and re-encodes (alpha-preserving WebP, or PNG when the browser can't keep transparency in WebP), so even a large photo uploads. An image that already fits is sent unchanged. For the crispest backdrop, pre-size it to ≤ 2,048 px and ≤ ~2.5 MB, and keep transparency in a PNG/WebP — see [Image size, resolution & format](#image-size-resolution--format).

The backdrop renders with `object-fit: fill` so it stretches to fill the square draw grid (see [How the custom backdrop renders](#how-the-custom-backdrop-renders)), and its recorded width × height is the pixel canvas the active layout's shapes rasterise against. You cannot save custom segments until the active layout has a backdrop — without one the server has no pixel dimensions to rasterise into and the save is rejected (`reason: no_custom_backdrop`).

#### Custom segment composer

With a backdrop in place and Custom mode active, the map panel becomes a drawing canvas and the side panel shows the **Compose rooms** toolbar — add rectangles/circles, move/scale/resize/rotate, merge, carve cutouts, split, set move-scope, link, and save. The tool-by-tool walkthrough is in the user guide ([Draw your rooms](../user-guide/16-making-your-own-maps.md#2-draw-your-rooms)); the model, linking, and save contract are below.

**Shape model.** Each draft shape is `{ id, type, ...geometry, group?, op?, room_id?, angle? }`. Geometry is in `0–100` map percentages. A shape's `group` defaults to its own `id` — that is what makes an un-merged shape its own room. Merging moves shapes into a shared `group`; an `op: "subtract"` member carves a hole out of that group. Rectangles also carry an `angle`.

**Linking rooms.** When a shape (or merged group) is selected, the **Link to room** chips list every room on the active map. Tapping a chip links the room to that group; tapping the linked room again unlinks it. The relationship is 1:1 — a room already taken by another group shows as disabled. The link is set on the draft and only persisted when you save.

**Saving.** Click **Save rooms**. The composer groups the draft by `group`, orders any `subtract` primitives last within each group, and calls `set_custom_segments` (a **replace-all** write of the **active layout's** custom store; the handler auto-creates a default layout if somehow none is active). **If that write succeeds**, it then reconciles the room links **per segment** — one `set_segment_room_link` call per group, using the group id as the segment id, writing to the active layout's own link map — and re-fetches the segments. If the active layout has **no backdrop**, the write is rejected (`no_custom_backdrop`) and the save **stops and surfaces that error in the toolbar without writing any room links** — so you never end up with links pointing at segments that were never saved. An empty draft simply no-ops (the Save button makes no service call).

#### How custom segments rasterise

When you save, each group's shapes are sent to the server as a list of **primitives** and rasterised by `set_custom_segments` against the active layout's backdrop:

- A primitive is `{ type: "rect" | "circle" | "polygon", ...coords, op? }`, with all coordinates in `0–100` map percentages. A rotated rectangle is converted to a `polygon` before it leaves the card.
- The server draws each primitive in order onto a boolean mask at a fixed internal working resolution (a 512-px square) — `add` (fill) by default, or `subtract` (clear) when the primitive carries `op: "subtract"`.
- The mask's outer boundary is then traced into a polygon with the **same** `mask_to_polygon` routine the CV segmenter uses, and scaled to the backdrop's pixel space. Each group becomes exactly **one** segment (one room).
- Degenerate results are dropped: a group whose primitives draw nothing (or collapse to nothing) produces no segment and is reported in the save response's `skipped` count.

A couple of consequences worth knowing:

- **One segment = one room.** Multiple primitives in a group merge into a single room polygon.
- **`op: subtract` carves the outline.** A subtract that cuts into the edge of a room turns it into a concave simple polygon — that works. A subtract that sits fully *inside* the room would need a true hole, and a single boundary polygon cannot represent an interior hole, so model interior obstacles as separate geometry rather than expecting a doughnut.

#### Re-editing custom segments

Saved custom segments reload as editable shapes. When custom mode loads a layout, the composer rebuilds its draft from that layout's saved segment polygons (as `polygon` shapes, since the backend stores polygons rather than the original primitives), **once per active layout** — so it won't clobber an in-progress draft or reload immediately after you save. The reload is keyed on `` `${map_id}:${active_custom_layout_id}` `` (`_composeLoadedFor`), and `setMapSegmentsData` resets the draft whenever **either** the map or the active layout changes, so each layout reloads its own shapes when you click its chip. Each reloaded shape keeps its segment id and its room link, so re-saving preserves that layout's `segment_room_links`. The mascot dock spot reloads per active layout too — the reserved `dock` companion anchor lives in the active layout's `companion_anchors`.

Because `_resolve_active_scope` simply points at whichever store the mode + active layout select, switching between Auto (CV) and any custom layout is lossless: your CV analysis and every hand-authored layout coexist for the same map, and you lose none by switching. The one exception is CV itself: **re-running CV re-segments and forces a relink** of the CV store (the accepted cost of a fresh analysis). Custom layouts are never re-segmented — they only change when you explicitly save them.

---

### When to use map configuration

You need this view when:

- The map image you are using does not match the current room layout and you have a better screenshot to replace it with.
- Segment detection produced polygons that do not align with the actual room boundaries — you need to nudge, expand, or contract them to match.
- A segment's edge extends into an adjacent room, causing presence detection or job attribution errors.
- You want to link or re-link specific segments to rooms after a re-analysis produced different segment IDs.
- Automatic detection can't get a usable result (stylised, low-contrast, or themed map) and you want to **author rooms by hand** — draw shapes, merge them into rooms, carve cutouts, link each to a room, and save. See [Custom segmentation mode](#custom-segmentation-mode); creating a custom layout preserves your CV segmentation losslessly, so it's a safe thing to try.
- You want to maintain **several alternative layouts** on one physical map (different themed backdrops, or different room groupings) and switch between them on demand — each is a named custom layout.

In CV mode, all polygon adjustments are cumulative and additive — each nudge adds to the stored offset rather than replacing it, and adjustments save to the integration's data storage immediately after each button press and persist across restarts. In custom mode the draft lives in the card until you click **Save rooms**, which writes the active layout's whole custom segment set at once.
