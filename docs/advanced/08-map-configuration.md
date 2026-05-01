## Map Configuration

The **Map Configuration** view lets you upload map image variants and manually adjust the segment polygons that the integration uses to render the interactive floor plan. You access it from the Rooms view, not from the navigation bar — it has no tab of its own.

---

### Accessing map config mode

Map configuration is available when the map view is active in the Rooms tab. To open it:

1. Go to the **Rooms** view.
2. Enable map view if it is not already active.
3. Click **Configure map** (the configure button inside the map view).

The card switches to the `MAP_CONFIG` view. A back arrow labeled "Rooms" in the top-left returns you to the Rooms view. All segment polygons remain visible in the map panel throughout.

---

### What the view shows

The Map Configuration view has three areas:

- **Map panel** (top) — the floor plan image with all segment polygons overlaid. In config mode the polygons are rendered at reduced opacity until selected. Click any polygon to select it.
- **Side panel** (right) — segment adjustment controls, shown once a polygon is selected.
- **Image Variants section** (bottom) — upload controls and an Analyse button.

---

### Image variants

The integration uses up to three map image variants. Each variant serves a distinct role in segment detection:

| Variant | Role | Purpose |
|---|---|---|
| **Dark** | Primary | Clearest room colour separation — preferred input for segment detection |
| **Light** | Assist | Wall and boundary detection, used alongside the dark variant |
| **Default** | Fallback | Used when no dark variant is available |

The Image Variants section shows each variant's current upload status. Uploaded variants display their pixel dimensions (width × height). Missing variants show "not uploaded".

#### Uploading a variant

1. Click the **Upload** button next to the variant you want to replace.
2. A file picker opens. Select a PNG, JPEG, WebP, or BMP image file.
3. The card uploads the file (showing "Uploading…"), then immediately triggers a re-analysis (showing "Analysing…"), then fetches the updated segments.

The backend converts non-PNG uploads to PNG before saving. It stores the file at `eufy_vacuum/maps/<vacuum_id>/map_<map_id>_<suffix>.png` (the dark variant uses the suffix `_dark`, light uses `_light`, default has no suffix). The browser URL for the stored file is recorded and used to render the map image in the card.

After a successful upload and analysis cycle, the variant row updates to show the measured pixel dimensions of the saved file.

#### Re-analysing without uploading

If you want to re-run segment detection against the current images without uploading new files, click **Re-analyse** (or **Analyse map** if no segments exist yet). This calls `analyze_map_image` with `force_reanalyze: true` and fetches the updated segments.

The segment count and adjusted-segment count are shown to the right of the Analyse button.

---

### Segments

A segment is a detected region in the map image — a polygon derived from color clustering and morphological analysis of the uploaded image. Each segment has:

- A `segment_id` string
- A pixel-space polygon (`polygon_pixel`) and a percentage-space polygon (`polygon_pct`, 0–100 on both axes) used for SVG rendering
- A bounding box
- A center point
- Quality metadata (confidence, structural role, issues)

Segments are extracted by the `detect_room_segments` function in `image_segments.py`, which uses OpenCV or a Pillow/SciPy fallback depending on what is installed. The dark image variant is the primary input; the light variant assists with boundary detection when available.

Segments are not rooms. A segment is a region the image analysis found in the floor plan. You link segments to rooms manually in the side panel.

---

### Selecting and adjusting a segment

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

Room assignments made here are stored in the browser's localStorage, keyed by vacuum and map ID. The backend may also supply room_id values on segments directly when segments were previously associated during analysis; those take precedence over locally stored assignments.

---

### When to use map configuration

You need this view when:

- The map image you are using does not match the current room layout and you have a better screenshot to replace it with.
- Segment detection produced polygons that do not align with the actual room boundaries — you need to nudge, expand, or contract them to match.
- A segment's edge extends into an adjacent room, causing presence detection or job attribution errors.
- You want to link or re-link specific segments to rooms after a re-analysis produced different segment IDs.

All polygon adjustments are cumulative and additive — each nudge adds to the stored offset rather than replacing it. Adjustments are saved to the integration's data storage immediately after each button press and persist across restarts.
