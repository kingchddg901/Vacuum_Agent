# 04a — Zones

A **zone** is an area you draw on the map — a box over a spill, the patch in front of the couch, the strip by the stove. Cleaning a zone is more precise than cleaning a whole room: the vacuum works just that footprint, and a zone can cross a room boundary on purpose (the entryway plus a corner of the office, where the leaves blow in).

There are three ways to use a zone, from most casual to most deliberate:

1. **Clean an area right now** — draw a box, send it, done. Nothing is saved.
2. **Save a zone you'll come back to** — draw it once, name it ("the stove"), and re-clean it any time in one tap.
3. **Fold a zone into a room-clean run** — add a saved zone as a **step** so a single job cleans some rooms *and* a zone, in sequence.

The first is a quick tool. The second and third are what turn zone cleaning from a one-off into something the card remembers, sequences, and learns.

!!! note "Where zones work"
    Zone cleaning needs a device-accurate map backdrop — either the **live map** image or the rendered **▦** room map — on a brand that supports it: **Eufy** (eufy-clean v1.11.1+) and **Roborock** (the S6, and likely other models, through the stock integration). You can draw at any map rotation. Right after you **switch maps**, drawing is briefly paused until the robot moves and re-localizes on the new map (a banner explains and offers an override) — drawing before then would land the box in the old map's coordinates. Per-clean limits are brand-specific — see [Brand support and limits](#brand-support-and-limits) at the end.

---

## Clean an area right now (draw a box)

This is the one-off: an area you want cleaned once, not kept.

1. Open the **Map** view and tap the **▢ "Draw a zone to clean"** button in the map toolbar to enter zone mode.
2. **Drag a box** on the map over the area you want cleaned. Repeat to add more boxes — up to the brand cap (each is numbered).
3. The **Zone clean** panel (right column) lists your boxes. Remove one with its **✕**, or **Clear** to drop them all. Under **Settings**, choose the suction/mop options for the run — they apply to the whole clean.
4. Press **Clean zone** (or **Clean *N* zones**) to send it. **Cancel** leaves zone mode without cleaning.

These boxes are ephemeral — they aren't kept between cleans. If you find yourself drawing the same box over and over, save it instead (below).

---

## Save a zone you'll reuse

A **saved zone** is a named, reusable region. You draw it once, give it a human name, and it stays on the map for that map version — ready to re-clean, or to drop into a run as a step. Humans navigate by landmark, not coordinate: "clean under the couch" is how you actually think about a spot, so the name is the whole point.

### Save one

1. Open the **Rooms** view and find the **Saved Zones** panel. Click **+ Draw a zone** — available over the **live map**, since you draw the box directly on it.
2. **Drag a box** over the region and click **Save zone** — the draw UI here is just a hint plus **Save zone** / **Cancel**; there's no live size readout, and the per-clean size limit isn't checked at save. It's checked later, when you actually clean the zone (see [Brand support and limits](#brand-support-and-limits)), so a saved zone can be too big or small to clean until you delete it and draw a new one.
3. When prompted, **name it** — "the stove", "front of couch", "cat corner". The name is yours; the card stores and shows it verbatim, never translated.

On save, the card files the zone under a room automatically: if at least ~90% of the zone's floor sits in one room, it's filed there; otherwise it lands in **Unassigned** (this is common and fine for a zone that deliberately spans two rooms). The filing is organizational only — it decides where the zone appears in the list, and never changes what gets cleaned. The automatic filing and the m² size shown afterward both come from the Eufy map raster, so on **Roborock** they aren't computed — a new zone files under Unassigned with no size shown, and you can move it with the per-zone room picker.

### Browse, reassign, and clean

Saved zones live in the **Saved Zones** panel in the Rooms view, grouped by the room they're filed under (with **Unassigned** last). Each entry shows its name, plus its size on brands where it's computed (Eufy) — on Roborock no size is shown (see [above](#save-one)).

| Action | What it does |
|---|---|
| **Select → Clean *N* selected** | Tick one or more zones and press **Clean *N* selected** — one zone cleans just that footprint, several clean as one batch (up to the brand cap). **Clear** drops the selection. |
| **Rename** | Renames a saved zone. |
| **File under room** | A per-zone picker moves a zone to a different room section, or to **Unassigned**. Filing only — it never affects the clean. |
| **Delete** | Removes the saved zone (asks you to confirm first). |

!!! note "Saved zones survive a map switch; a re-map clears them"
    A saved zone is stored relative to the map (not to absolute coordinates), so it stays put across sessions and is converted to the vacuum's live coordinates fresh each time it's cleaned. But a genuine **re-map** (redrawing the floor plan) changes what the coordinates mean, so it invalidates that map's saved zones — you'd re-save them against the new map.

---

## Add a zone to a run (a zone step)

The most powerful use: make a saved zone a **step** inside a normal room-clean run, so one job does *rooms and a zone* in sequence — the same way a [charge or wait stop](10-profiles.md#steps-charging-and-waiting-mid-run) is a step. "Vacuum the kitchen and living room, then hit the stove zone, then mop the kitchen" becomes one button press.

A zone step is added **on the queue**:

1. Set up your room queue as usual (see [The Queue and Room Order](03-queue-and-order.md)) — a zone step needs at least **two rooms queued**.
2. Tap the **+ Zone** chip in the Rooms view. (It appears only once you have at least one saved zone on this map, with two or more rooms queued and no run active.)
3. In the **Add a zone step** picker, tick one or more saved zones — they'll clean together as a single phase — and press **Add to queue**.

The zone step drops into the queue as a **🎯 chip**, at an interior slot between your room groups (it never leads — the run always opens with a room). It behaves like the other stops:

- It shows in the flat **queue chip row** and in the **"This Job"** preview alongside your rooms, charge, and wait steps.
- You can **reorder or remove** it — from the queue, or in the run-profile editor's step list. Unlike a charge or wait stop, a zone step can also be **moved to trail after the last room** (charge/wait stops stay interior); use the move handle to place it there.
- When you **save your setup as a run profile**, the zone step is captured with it, so the profile replays the whole rooms-and-zone sequence on **Run** (or from its Home Assistant button). See [Profiles → Steps](10-profiles.md#steps-charging-and-waiting-mid-run).

!!! note "Adding vs. editing zone steps"
    Zone steps are **added** from the queue's **+ Zone** chip — the profile editor's own step controls add charge, wait, and room-group steps, not zones. Once a zone step is in a profile, the editor lists it (🎯) and lets you reorder or remove it like any other step.

While a zone step is cleaning, the live view shows a dedicated zone status and the zone chip goes **current** in the [live queue](05-live-monitoring.md#the-live-queue) — the vacuum docks and returns just as it does for a charge or wait stop, and the run isn't treated as finished until the whole sequence is done.

---

## Automate a zone clean

You can fire a saved zone from a Home Assistant automation — clean "under the table" every evening, or "the entryway" whenever a rain sensor trips. The `clean_saved_zone` / `clean_saved_zones` services are the automation form of the **Clean** button, and pre-run timing ("only once charged", "off-peak only") lives in the automation's conditions rather than inside the job. See the worked examples in [Automation examples → Clean a saved zone](../advanced/04-automation-examples.md#8-clean-a-saved-zone-on-a-trigger) and [Pre-run conditions](../advanced/04-automation-examples.md#9-pre-run-conditions).

---

## Learned zone times

Once you run a saved zone as a step, the card **learns how long it takes** — as a wall-clock total, so a mop zone's dock-to-wet-the-pad and post-wash time counts as the wait you actually experience. That learned time drives the zone chip's estimate on the next run. Before there's a sample, the card estimates from the zone's size instead, and shows a "learning" hint. Zone learning is separate from room learning and keyed per zone and mode (mop vs. vacuum) — see [The Learning System → Zone learning](../advanced/01-learning-system.md#zone-learning) for the details.

---

## Brand support and limits

| | Eufy | Roborock |
|---|---|---|
| Zone cleaning | eufy-clean v1.11.1+ | S6 (and likely others) via the stock integration |
| Zones per clean | up to **10** | up to **5** |
| Per-zone size | ~0.5–10 m per side | **1 ft² – 32.8 ft²** each |
| Draw over | live map or the ▦ rendered map | the ▦ rendered map (the **Draw a zone** button appears once it's on) |

The card enforces the count cap as you draw — it stops the draw once you hit the per-clean zone limit. The size limit isn't checked at draw or save time; it's checked when you actually clean the zone, and an out-of-size zone is refused then with a message. When in doubt, draw a modest box; you can always save several small zones and clean them as a batch.
