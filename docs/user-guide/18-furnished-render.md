# 18 — Furnished Render

Furnished render lets you put a **to-scale picture of your actual home** — with its real furniture — under the live map, so when the robot cleans you watch it drive across your living room, not an abstract blob map. The live robot, dock, cleaning path, and room overlays always ride on top.

It works on any **live-map layout** (Roborock, and Eufy via the community camera fork) — the same live map you'd draw rooms over in [Making your own maps](16-making-your-own-maps.md). There's no complicated calibration: you line the art up over the live map once, by eye, and that alignment is all it needs.

> **Where it lives:** open the map, go to **map configuration**, and select a **Live map** custom layout. The **Furnished render** panel appears in the side panel. It only shows on a live-map layout — if you don't see it, switch the layout's backdrop to the live map first.

---

## The easy way: trace over the real map

The trick that makes alignment almost free:

1. In the Furnished render panel, click **⬇ Save map image**. This downloads the exact map frame the card is showing.
2. Open that image in any drawing app (even slides or a photo editor). On a **new layer on top**, draw your rooms and furniture to scale — over the map you just saved.
3. Hide or delete the map layer and export **just your furniture art** as a PNG, on the same canvas size.
4. Back in the panel, click **Upload art** and pick that PNG.

Because you traced over the real map, your art already lines up — it drops in almost perfectly, needing a nudge at most.

> On some brands the saved frame has the robot/dock drawn into it (that's the brand's own map render) — ignore those while you trace; the card draws the *live* robot on top anyway.

---

## Uploading art

Click **Upload art** and choose an image. Two scopes:

- **Whole-home** (the default) — one image covering your entire floor.
- **Per-room** — a separate image for a single room (handy if you only want to dress up one room, or want more detail per room).

The image is stored with the layout, not as the map backdrop — your drawn rooms and the live map are left untouched.

---

## Aligning it

After uploading, the panel switches to **Blend** mode so you can see your art semi-transparent over the live map. Now line it up:

- **Drag** the art on the map to position it.
- **Nudge** and **Scale** with the buttons for fine positioning and sizing.
- **Rotate** if your art is off-angle: **±90°** to flip orientation, **±1°** and **±0.1°** for fine steps, and the **±15° fine-trim slider** to dial it in smoothly. (Most renders and top-down photos aren't exactly square to the map, so the sub-degree controls matter.)

When it lines up with the live map underneath, click **Save alignment**.

---

## View modes

Three modes, toggled in the panel:

- **Live** — just the live map (art hidden). The normal map view.
- **Blend** — your art over a faded live map. Best for aligning.
- **Art** — your furnished render full-strength, the live map dropped to a ghost. This is the "watch the robot clean my actual home" view.

In every mode the **live robot, dock, cleaning path, and room overlays ride on top**, so the map stays fully functional — tap a room to queue it, watch the robot move, and so on.

---

## Good to know

- **No calibration, ever.** The alignment you do by eye *is* the reconciliation — the art is pinned to the live map's pixels, so the overlays land correctly for free.
- **Between sessions (Eufy):** the vacuum rebuilds its map each session and may shift the frame slightly, so your art can drift a touch — just re-drag and **Save alignment** again. Within a session it's stable. Roborock is steadier.
- **It's per layout.** Each custom layout has its own art, so you can keep a plain "rooms only" layout and a "furnished" one and switch between them.
- **Zone clean over your furniture (Eufy):** because zone-draw sits a layer above the art, you can draw a zone-clean straight onto your furnished room and it cleans the right spot (the map must be at rotation 0).

For the services behind the panel, see [Services → Furnished Render](../advanced/03-services.md#furnished-render); for the technical design, see the [developer deep-dive](../dev/32-furnished-render.md).
