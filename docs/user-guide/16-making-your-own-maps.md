# Making your own maps

The card can show your floor plan as an interactive map: each room is a coloured shape you can tap to queue, and your vacuum's mascot wanders across it. This guide walks you through getting that map set up — from a first screenshot to hand-drawn themed layouts.

You have a few ways to put rooms on the map, and you can use more than one on the same vacuum:

- **Auto (CV)** — upload a screenshot of your Eufy app's map and let the integration **detect the rooms for you**. Best when your app map has clean, solid room colours.
- **Custom layouts** — **draw the rooms yourself** from rectangles and circles on top of any background picture. Best when auto-detection struggles, or when you want a themed map (a blueprint, a solar system, a tree) with rooms exactly where you put them.
- **Live map** *(Roborock and other live-map brands)* — **skip the upload entirely** and draw rooms straight over the map image your vacuum streams. See [Roborock and other live-map brands](#roborock-and-other-live-map-brands) below.

> **Not sure which?** Start with Auto (CV) — it's the least work. If the detected rooms come out wrong and won't nudge into shape, switch to a custom layout. Trying a custom layout never destroys your Auto (CV) result; they live side by side.

---

## Opening the map

1. Go to the **Rooms** tab.
2. Use the toggle in the top-left of the room grid to switch from the list to **map view** (see [The rooms panel](02-rooms-panel.md)).
3. To set the map up, click **Configure map** inside the map view. This opens **Map Configuration**, where you upload images and define rooms. A **Rooms** back-arrow in the top-left returns you.

The map view shows "No map image available" until a map is set up — that's expected on a fresh install. The rest of this guide fills it in.

---

## Picking a good image: size, resolution & format

Before you upload anything, it helps to know what makes a good image — the same rules apply whether it's an Auto (CV) screenshot or a custom backdrop.

| Aim for | Why |
|---|---|
| **Long side ≤ 2,048 px** | Big enough to look sharp, small enough to upload quickly. |
| **File ≤ ~2.5 MB** | Home Assistant sends images over a connection with a size limit; staying under this uploads at full quality. |
| **PNG** (or WebP) | Lossless and — for custom backdrops — keeps **transparency**. |

A few specifics:

- **Auto (CV) screenshots:** use **PNG**. The detector reads flat room colours, and PNG keeps them crisp (JPEG smudges the colour edges). Keep these small — an app screenshot is usually already well under the limit. If you ever see a "too large" message on a CV upload, crop tighter or export smaller; the card will **not** shrink a CV image for you, because resizing it would throw off room detection.
- **Custom backdrops:** bring **any** picture. If it's bigger than the limit, the card **automatically resizes and compresses it** for you (down to ≤ 2,048 px), so even a large photo uploads — it just looks a little softer the larger it started. For the sharpest result, pre-size it yourself to the targets above.
- **Transparency is kept.** A cut-out picture with a transparent background — a tree, a planet, a logo — keeps its see-through areas, so your dashboard background shows behind it. Don't save such an image as JPEG first; JPEG fills the transparent area with a solid colour.

For the full story on *why* these limits exist, see [Map configuration → Image size, resolution & format](../advanced/08-map-configuration.md#image-size-resolution--format).

---

## Option A: Auto (CV) — detect rooms from a screenshot

### Capturing a good map image

The quality of segment detection depends heavily on the map image you provide. Follow these steps to capture the cleanest possible input for each variant. Repeat the full sequence for both your dark and light captures, keeping orientation and crop consistent between them.

#### Preparation

1. Start and immediately cancel a vacuum only job to clear all trace lines on map.

2. **Clear all floor types** — In the Eufy app, open Map Editor and remove all floor type assignments. This strips out texture and pattern overlays, leaving each room as a flat, solid colour for the segmentor to work with.

3. **Switch to 2D mode** — Ensure the map display is set to 2D. 3D mode skews the geometry and perspective, which distorts the polygon shapes the segmentor produces.

4. **Hide all UI overlays** — In the map display settings, turn off room names, furniture, virtual furniture, and obstacles. The capture should show nothing but raw room colour regions.

#### Framing

5. **Set your orientation** — Choose whichever map rotation fits cleanly within the app's viewable area. There is no required direction, but pick one and keep it consistent across all variants. Mismatched orientations between dark and light images will cause polygon misalignment.

6. **Collapse all UI chrome** — Minimise panels, drawers, and toolbars as much as possible. The map should fill the visible area cleanly with no UI elements overlapping its edges or corners.

#### Capture

7. **Take the screenshot.**

8. **Crop tightly** — Crop the screenshot as close to the map boundary as possible, eliminating any remaining UI chrome. Do not clip any part of the map itself. Use the same crop boundary for both variants so their polygons align when overlaid.

#### Second variant

9. **Switch colour mode and repeat** — Toggle the app to the opposite mode (light if you captured in dark, dark if you captured in light) and repeat steps 4–7 without changing orientation or crop boundary. This gives you your matched dark and light pair.

#### Assigning the Default variant

The Default variant does not require a separate capture. Upload whichever of your two images you prefer to see rendered in the card UI day-to-day. It acts as a fallback when no dark variant is present, but can also simply be your preferred display image.

### Upload and analyse

In **Map Configuration**, with **Auto (CV)** selected, find the **Image Variants** section and:

1. Click **Upload** next to **Dark** and pick your dark screenshot. The card uploads it, then automatically **analyses** it to find rooms (this takes a few seconds).
2. Do the same for **Light** if you captured one.
3. Optionally upload a **Default** image — this is just the picture shown in the card day-to-day; either of your two captures works.

When analysis finishes, the detected rooms appear as coloured shapes on the map, and the segment count shows next to the **Analyse** button.

### Link each room

The shapes the detector found are just *regions* — they don't know which room is which yet. Tap a shape to select it, and in the side panel use the **Link to room** chips to pick the matching room. Each shape links to one room, and each room to one shape.

### Fine-tune (optional)

If a shape's edge spills into the next room or sits slightly off, select it and use the **Translation**, **Edges**, and **Vertices** controls in the side panel to nudge it into place. Adjustments save as you go. If detection just can't get it right, that's the cue to try a **custom layout** instead.

---

## Option B: Custom layouts — draw your rooms by hand

A custom layout lets you trace rooms onto **any** background image. You can keep **several** named layouts on one vacuum — say a realistic floor plan and a fun themed one — and switch between them whenever you like.

### 1. Create a layout and add its backdrop

1. In **Map Configuration**, open the **Segmentation** picker (bottom panel). Click **＋ New**, type a name (e.g. "Tree" or "Blueprint"), and click **Create**. This makes the layout active and switches the map into custom mode.
2. In the **Custom backdrop** section, click **Upload** and pick your background picture. Every layout has *its own* backdrop — uploading here always applies to the layout you're on.

> Each layout needs its **own** backdrop. With no live map to fall back on (Eufy, or any layout with no live image), the map shows "No map image" until you upload one, and you can't save rooms — so do this first. On a live-map brand you can skip this step and draw over the live map instead — see [Roborock and other live-map brands](#roborock-and-other-live-map-brands).

### 2. Draw your rooms

In the **Compose rooms** toolbar:

- **＋ Rectangle / ＋ Circle** adds a shape — each new shape is one room.
- **Tap a shape** to select it and reveal its controls.
- **Move** with the arrow pad, or **tap an empty spot** to drop the shape's centre there.
- **－ / ＋ Scale** resizes it about its centre; **W / H** buttons resize a rectangle's width or height; **↺ / ↻ Rotate** turns it.
- **Fine / Med / Coarse** sets how far each nudge moves.

Everything is tap- and button-driven, so it works on a phone — no precise dragging required.

### 3. Combine or carve shapes (optional)

A room can be more than one shape:

- **⛓ Merge** — tap Merge, then tap another shape to fold it into the same room (an L-shaped room from two rectangles, for example).
- **Make cutout** — mark a shape to *carve out* of its room instead of adding to it (e.g. notch a corner). Cutouts work along a room's edge; a hole fully inside a room can't be represented, so model interior obstacles separately.
- **Split out** — pull a shape back out into its own room.
- **Move: Room / Piece** — for a merged room, choose whether the move pad shifts the whole room or just the one piece.

### 4. Link each room and save

1. With a shape (or merged room) selected, use **Link to room** to pick which room it is — same 1:1 rule as Auto (CV).
2. Click **Save rooms**. Your shapes are saved as this layout's rooms and re-appear (editable) next time you open it.

If you click Save with no backdrop *and* no live map, the card tells you so and saves nothing — upload the backdrop, then save again. On a live-map brand, rooms save straight over the live map once it has loaded; the guard only fires while the live image is still loading, or when there's genuinely no backdrop and no live image. The on-screen message offers to **wait for the live map to appear, then save again (or upload a backdrop)**.

### 5. Keep several layouts

Each chip in the **Segmentation** picker is one layout; **Auto (CV)** is always there too. Click a chip to switch — the backdrop, rooms, and mascot spot all swap together. Use **Rename** / **Delete layout** for the active one. Switching never loses any layout.

---

## Roborock and other live-map brands

If your vacuum streams a live map (Roborock S6, for example), there's **nothing to upload** — the vacuum's live map image *is* your backdrop. You draw rooms straight over it.

1. In **Map Configuration**, open the **Segmentation** picker, click **＋ New**, name the layout, and **Create** it (as in Option B). This switches the map into custom mode.
2. **Skip the Custom backdrop upload.** Leave it empty — the live map shows through underneath instead of a "No map image" placeholder.
3. **Draw your rooms** over the live map with the **Compose rooms** tools (same rectangles, circles, merge, and cutout controls as Option B).
4. **Link each room** and click **Save rooms**. The save captures the live image's pixel size at that moment, so your shapes line up with the live map exactly as it looked when you saved.

> **Tip:** Let the live map finish loading before you save — the save reads its current pixel dimensions. If you save while it's still blank, the card waits and asks you to try again (see [Link each room and save](#4-link-each-room-and-save)).

### Rotating the live map

If the live map comes in sideways relative to how you picture your home, use the **Rotate** control on the map-view toolbar to turn it in 90° steps until it matches. The rotation is stored in the backend, so it **follows you across devices** — set it once and every dashboard and phone sees the same orientation. The whole layer turns together: the image, your room polygons, the labels, and the mascot all rotate as one, so your drawn rooms stay aligned no matter which way you face the map.

---

## The mascot and floor textures

The map view's small toolbar also controls the cosmetic layers:

- **Companion animal** — pick the sprite (cat, dog, raccoon, parrot, snake) and its size. It homes to the room your vacuum is in, and parks at a **dock spot** when docked — drag it once while docked to set where it parks (great for sitting it on the sun of a space map). The mascot and dock spot are remembered **per layout**.
- **Mascot toggle** (paw) — hide or show the sprite.
- **Map textures toggle** (hatched square) — hide or show the floor textures on the map polygons.
- **Room-card textures toggle** (hatched card) — hide or show the floor textures on the room cards, independently of the map. (This one stays in the toggle row even in list view, so you can flip the cards' textures while you're looking at them.)
- **Rotate** (live-map brands only) — *not* a cosmetic toggle: this turns the **live map** in 90° steps to match your home. The rotation is stored in the backend, so it follows you across devices, and the whole layer — image, room polygons, labels, and mascot — turns together. See [Rotating the live map](#rotating-the-live-map).

You can recolour the map's labels and overlays in the **Theme editor → Map** group.

---

## Troubleshooting

| You see… | Do this |
|---|---|
| **"No map image available"** in the room map | Set the map up: upload Auto (CV) images and analyse, **or** create a custom layout and upload its backdrop. On a custom layout it means that layout has no backdrop yet. |
| **"Image too large…"** on upload | A custom backdrop is auto-fitted, so this is usually a **CV** image — crop or export it smaller (≤ ~2.5 MB). |
| **Rooms detected wrong** (merged/split) and won't nudge right | Switch to a **custom layout** and draw them by hand — your Auto (CV) result is kept. |
| **A second custom layout won't show its rooms** | It needs its own backdrop uploaded, then its rooms drawn and saved — backdrops and rooms are per-layout. |

---

## Going deeper

This is the everyday workflow. For the technical reference — the exact services, the segment data model, how custom shapes rasterise, the CV vs custom storage model, and the image-size limits in detail — see [Map configuration](../advanced/08-map-configuration.md).
