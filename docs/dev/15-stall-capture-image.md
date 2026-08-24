# 15 — The Stall Capture Image

**Scope.** The renderer that turns room-id raster bytes into a PNG when a stall fires: one room
as a flat silhouette, the last stretch of travel, a dot where the robot stopped, and a
white-on-black name pill.

It is pure — no Home Assistant imports, no I/O, no adapter lookups. Bytes in, bytes out. The
single production caller supplies a geometry block the renderer must not re-derive.

**Every interesting behaviour here is an absence behaviour.** Pillow missing, no anchor, no
cells, unreadable cadence — each degrades to a smaller picture or to `None`, never to an
exception on a job-lifecycle path.

---

## 1. Generated, not screenshotted

The rejected design zoomed the live card to the stalled room and captured what the user would
see. It would make a browser a runtime dependency of a job-lifecycle path — kept alive, kept
authenticated, kept in step with a card that changes.

**The image is deliberately plain**: one fill, one trail colour, one dot, no palette resolution.
A port of the card's themeable room-fill cascade existed in a draft and was deleted rather than
shipped, because it would have been a *third* copy of a palette that has already drifted once.

**It cannot drift from a design it never copied.** That is the whole argument for it looking
nothing like the card.

The crop is computed from geometry, not from the saved per-room viewport. The two zoom
mechanisms in this subsystem are unrelated and from different eras; wiring the saved one in would
couple a notification image to card framing.

---

## 2. Three coordinate spaces, and two quiet failures

Cells go raster → offset → flip. The anchor and trail are **already in rendered space** and get
neither.

The first draft assumed the raster *is* the canvas and that a raster byte *is* a room id. Both
are false on Eufy, and **both fail quietly** — they render a perfectly plausible image of the
wrong region rather than raising.

**Membership is a shifted compare, with the shift declared by the render-data block and never
sniffed.** A raw byte compare works on Roborock. On Eufy a cell holds `room_id << 2`, so a raw
compare is empty for most ids — but for any id that is a multiple of 4 it matches **another
room's** cells: room 4 draws room 1, room 8 draws room 2, up to room 28 drawing room 7. That
failure is not an absence. It is a fully rendered, entirely plausible picture of the wrong room.

**Return `None`, never a blank image**, when Pillow is absent or the room has no cells. Absence
has to stay distinguishable from "an empty room was rendered"; the caller re-imports the module
on the failure path purely to tell the two causes apart.

---

## 3. The trail, and why its constants are one system

The dense branch needs four **distinct** points to draw a connected trail; the sparse branch
connects from two. Identical consecutive anchors are deduped *before* the draw style is chosen. A polyline asserts the robot travelled straight between
samples — without the dedup, twelve identical samples from a wedged robot render as a trail for
exactly the case where the robot did not move.

**The window is derived from the brand's declared pose cadence, floored at 30 seconds.** Two
alternatives were rejected, and one of them had already shipped: a per-brand window constant asks
every adapter to restate a number it already declares.

The floor is what makes the change a no-op for the brand that was already working — its fast
cadence never reaches the floor, so its picture is unchanged.

**Widening the window is made safe by the same number choosing breadcrumbs over a line**, and the
three constants make that arithmetic rather than hope: the cadence at which a widened window
matters is past the cadence at which the renderer has already switched to sparse marks.

**Sparse samples are connected**, reversing an earlier ruling. That ruling was right about a
whole-map trail and overcautious inside a single-room crop, where a segment cannot cross a wall
unseen. The scope was what changed, not the reasoning.

**Direction is lightness plus chevrons — never hue, never a legend.** A hue ramp is invisible to
about 8% of men, and this image ships to people whose floors we have never seen. A worded key
would be the first English baked into the PNG, in a product that ships 18 locales.

**Chevrons are placed by arc length with the rhythm carried across joints**, not one per
segment. A fast cadence puts ~30 points in the window and per-segment marks become a solid
sawtooth; a slow one puts a handful across a room and per-segment is a single mark.

---

## 4. Draw order is the design

Upscale first with nearest-neighbour, draw vector elements at final resolution, rotate, then draw
the label pill **last**.

Upscaling the trail and dot along with the mask looks broken and makes the label illegible.
Rotating after labelling rotates the text — the label is the one element that must stay readable
at any map rotation.

**The rotation angle is negated.** The card rotates clockwise via CSS; the imaging library
rotates counter-clockwise. Without the negation the capture is correct in every case where the
angle is symmetric and wrong in the rest.

**Dot radii are multiples of the upscale factor, not of the output size — and that is what makes
dot visibility inversely related to room size.** The factor is capped, so a large room renders at
a lower factor and its dots come out relatively smaller. Tying radii to the output dimension
would give a constant fraction of the frame and remove the inversion; the scheme is kept anyway,
because a radius validated on a small room is then safe everywhere and helps most where the
result is currently worst.

---

## 5. Common wrong assumptions

| assumption | actually |
|---|---|
| the comment saying Pillow is optional because requirements are empty | `manifest.json` requirements is **not** empty — it carries the font subsetter's deps. Pillow simply is not among them |
| `max_edge_px` bounds the output image size | it bounds the **upscale factor**, floors at 1, and the module never downsamples |
| `trail_gap_s` is the observed spacing between samples | it is the brand's **declared** cadence, passed straight through |
| the two cell-lookup paths are the same, one just faster | the fast path masks to a byte, so on a shift-0 brand it aliases room ids modulo 256 |
| `flip_y=False` is a configuration some brand uses | neither shipping brand does |
| `room_cells` mirrors the current-room lookup, so it applies the same filters | only the *parameters* mirror it; the catch-all handling differs |
| the capture reflects what the user sees, so their customisations carry over | exactly one display preference is honoured — rotation. Hidden regions are **not** applied, so the capture shows masked areas |

---

## Registries

[00b-invariants.md](00b-invariants.md) · [00c-replicas.md](00c-replicas.md)
