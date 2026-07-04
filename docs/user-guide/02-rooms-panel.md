# 02 — Rooms Panel

The Rooms panel is the main day-to-day screen. From here you choose which rooms to clean, set how you want each room cleaned, reorder the cleaning sequence, and start a run.

## Layout

The panel is divided into two main areas, with a side column alongside them:

- **Action bar** — at the top, showing the queue summary, primary action buttons, and the ordered list of queued rooms.
- **Room grid** — below the action bar, showing a card for every room on your active map.
- **Side column** — to the right of the room grid (or below it on narrow screens), holding the [Run Profiles panel](#run-profiles-panel) and, below it, the [Saved Zones panel](#saved-zones-panel).

A toggle in the top-left of the room grid lets you switch between a list view (cards) and a map view (room positions overlaid on the floor plan). To set up that floor plan — upload a map image or draw your own rooms — see [Making your own maps](16-making-your-own-maps.md).

## Including and excluding rooms

Each room card acts as a toggle. Click (or tap) a room card to include it in the next run. Click it again to remove it. When a room is included its card is highlighted; when excluded it appears dimmed.

You can also:
- **Select All** — includes every room at once.
- **Clear Queue** — removes all rooms from the queue. Two-tap to fire: first click pulses "Confirm Clear", second click within five seconds actually clears. The pulse auto-clears if you walk away; navigating to another view also drops the pending confirmation.
- **Locate** — sends a chirp to the vacuum so you can find it. A toast confirms the command was sent.

Both Select All and Clear Queue are in the action bar at the top.

On path-optimizing brands (Roborock) the action bar also shows a **Strict order / Force this exact order** toggle for the run — see [Queue and order](03-queue-and-order.md) for what it does.

The action bar shows how many rooms are currently included (for example, "3 rooms included") and, once the system has learned timing data, an estimated total run time for the current selection.

## The queue strip

Below the count and action buttons, the action bar shows a row of chips — one per queued room, in cleaning order. Each chip shows:

- The room's position number in the queue.
- The room's name.
- An estimated time for that room (once the learning system has enough data).

During a live run the chips update in real time: the current room shows a percentage progress, completed rooms are marked as done, and remaining rooms stay in their waiting state.

**Queue chip interactions:**
- **Single click** — opens the room settings editor for that room.
- **Double-click** — opens the time estimate detail for that room.
- **Hold (long press)** — toggles the room in or out of the queue. The default hold duration is 450 ms; it can be changed in card config under `queue_chip_long_press_ms` (minimum 250 ms, maximum 1000 ms).

## Starting, pausing, and cancelling a run

The primary button in the action bar changes label depending on what state the vacuum is in:

| Situation | Button label |
|---|---|
| Queue has rooms and vacuum is docked | **Start Cleaning** |
| A run is active | **Cancel Run** (first click asks for confirmation; second click cancels) |
| Cancel confirmation is pending | **Confirm Cancel** |
| A reduced run has been detected (some rooms blocked) | **Confirm Start** |

When a run is active and the vacuum supports it, a **Pause** button appears alongside the primary button. If the vacuum is already paused, the button changes to **Resume**.

A **Locate** button is also present to make the vacuum emit a sound so you can find it.

If the start button is disabled, a reason is shown just below the button row — for example "No rooms included" or "Already cleaning."

### Reduced run detection

When you start a run, the integration checks whether any of your queued rooms are inaccessible given the current queue (for example, a room the vacuum can only reach by passing through another room that you have excluded). If blocked rooms are found, the button changes to **Confirm Start** and a panel appears listing:

- **Blocked rooms** — rooms that cannot be reached and will be skipped, with the reason for each.
- **Modified rooms** — rooms whose settings were automatically adjusted to make the run viable.
- **Warnings** — other non-blocking issues to be aware of.

You can either confirm the reduced run or cancel and adjust your room selection.

## Room cards

Each room card shows:

- The room's **name**.
- Its **queue position number** and a **Move** button for reordering.
- A drag handle (the `⋮⋮` icon) for drag-to-reorder.
- A **settings button** (⚙) to open the room editor.
- **Setting chips** showing any non-default settings at a glance — for example "Vacuum + Mop", "Boost", "Deep", "Edge Mop On", or "2× passes". Default settings (vacuum-only mode, standard suction, standard path, 1 pass) do not show a chip to keep the card clean.
- A **time estimate chip** if the learning system has data for the room. Learned estimates show the time directly; fallback (default) estimates are prefixed with "~" to indicate they are approximate.
- A **confidence chip** indicating how reliable the estimate is: "Reliable", "Learning", or "Uncertain" (or "Unlearned" if no data has been collected yet).
- A **projected water use chip** when the room is set to a mop mode and the integration can calculate expected water consumption.
- A **"Last cleaned ~Nd ago" pill** showing when the room was last actually cleaned, sourced from the integration's per-room history. Hover for the full timestamp and the cleaning mode used. The pill is suppressed for whichever room is *currently* being cleaned (the progress chip takes over there) and for rooms with no recorded history yet.
- **Warning notes** at the bottom of the card when issues are detected (see below).

### Sticky current room during a run

While a job is running, whichever room is *currently being cleaned* is pinned to the top of the room grid (or to the first slot in the visible list on mobile). The original order is preserved for every other room — only the active one moves. As the vacuum advances to the next room the pin shifts with it, so you don't need to scroll to see what's underway.

## Room settings editor

Click the ⚙ button on a room card — or click a queue chip once — to open the room settings editor. Changes you make here are not saved until you click **Save**.

The editor shows:

!!! note "Roborock (S6): what the room editor exposes"
    What's settable per room depends on your vacuum. On the Roborock S6: **cleaning mode / water is observe-only** — instead of a Vacuum / Mop / Vacuum + Mop selector the editor shows whether the water tank is attached ("Mopping — water tank attached" or "Vacuum only — no water tank"), because the S6's mop can't be switched from Home Assistant; **passes are global** — set once in the Roborock app, and the strongest per-room value wins for the run; **fan speed is per-room and applied live**; and the **Cleaning Profile** section is hidden, because with a single editable field a profile would be redundant. Controls your vacuum doesn't support simply don't appear.

### Cleaning Profile

A row of chip buttons lets you pick a named profile that applies a preset combination of settings to the room. The available profiles are read from your vacuum entity. You can also:

- **Save as New** — saves the room's current settings as a new named profile.
- **Save Over** — overwrites an existing custom profile with the current settings.
- **Rename** — renames the currently selected custom profile.
- **Delete** — deletes the currently selected custom profile (built-in profiles cannot be deleted).

When the room's settings do not match any saved profile, the **Custom** chip is shown as active. The profile selector disappears if no profiles are available, and is also hidden on brands that expose only a single editable field per room (for example the Roborock S6), where a profile would have nothing meaningful to bundle.

### Cleaning Mode

Selects what the vacuum does in this room. The options available are the modes your vacuum supports. Common options:

- **Vacuum** — suction only; no mopping.
- **Mop** — mopping only; no suction.
- **Vacuum + Mop** (shown in the UI as `vacuum_mop`) — suction and mop simultaneously.

Carpet rooms are locked to vacuum-only modes and show a notice in the editor. Mop-related fields (Water Level and Edge Mopping) are hidden for carpet rooms.

### Suction Level

Selects how hard the vacuum's motor works in this room. The exact options (such as Standard, Boost, Max, or similar) reflect what your vacuum supports. A higher suction level uses more battery and takes longer but picks up more debris.

### Water Level

Only shown when the selected cleaning mode includes mopping and the room is not carpet.

Sets how much water the mop pad receives. The exact options (typically something like Low, Medium, High, or Off) reflect what your vacuum supports. Setting this to Off effectively disables mopping even if a mop mode is selected.

### Cleaning Path

Controls how thoroughly the vacuum covers the room. The exact options reflect what your vacuum supports. Common values include Standard (single efficient pass) and deeper options that make the vacuum cover the room more completely — at the cost of time. Vacuums that don't expose this concept simply omit the row.

If you later change the Cleaning Path and the room already has a learned time estimate from a different path setting, a warning note on the room card will say "intensity mismatch" to let you know the estimate may be inaccurate until new data is collected.

### Cleaning Passes

- **1 Pass** — the vacuum cleans the room once.
- **2 Passes** — the vacuum cleans the room twice consecutively.

Two passes are useful for heavily soiled rooms but roughly double the time spent in the room.

The number of pass chips offered follows your vacuum (Eufy exposes 2, Roborock up to 3). On some vacuums passes are not per-room at all but a single whole-run value you set in the robot's own app — in that case the per-room control is omitted and the app's setting applies to the entire run.

### Edge Mopping

Only shown when the selected cleaning mode includes mopping and the room is not carpet.

- **On** — the mop pad is pressed against skirting boards and furniture edges.
- **Off** — the vacuum mops the open floor area only, staying clear of edges.

The room card shows an "Edge Mop On" chip when this is active.

### Transition Space

Marks the room as a hallway or connecting corridor. This tells the integration that the robot is passing through the space rather than cleaning it as a destination room. The integration's shape analysis may suggest this automatically if the room's geometry matches common corridor shapes; when it does, a callout appears in the editor.

### Room Color

Overrides this room's fill color on the map. The field shows:

- A **color swatch** — a native OS color picker (an `<input type="color">`) for choosing a custom fill color for the room.
- A **value readout** — showing the custom hex code when an override is set, or "Default (palette)" when it is not. With no override the swatch previews the room's default color from the shared themeable palette, so the picker opens at that color.
- A **Reset** button — shown only when an override is set. It clears the override back to the shared themeable palette.

Like the other editor fields, the color override is buffered while you edit and saved with the room's other settings when you click **Save**.

## Reordering rooms

Every room card has a position number chip, a **Move** button, and a drag handle.

- **Move button** — opens an order selector that lets you type or pick a new position number.
- **Drag handle** — click and drag a room card to a new position in the grid. Dragging onto another card inserts the room at that position.

Order changes take effect immediately and are saved to the integration's number entities so the order persists after page reload.

## Warnings and indicators on room cards

### Trouble room indicator

If your vacuum has repeatedly failed to finish a room across several runs, a warning note appears at the bottom of that room's card:

> ⚠ Missed N× of M runs (X%)

Hover over the note to see a suggestion to check for obstacles or map accuracy issues. Trouble room data is loaded once when the card starts up.

### Intensity mismatch warning

If the room's current Cleaning Path setting is different from the setting that was used when the learning system collected its timing data, the room card shows:

> ⚠ intensity mismatch

This means the displayed time estimate was learned at a different intensity and may not accurately reflect how long the room will take at the current setting.

## Access not set panel

If your setup includes a room access graph (which rooms the vacuum must pass through to reach other rooms) and any rooms have not yet been placed in that graph, a small panel appears above the room grid listing those rooms by name under the label "Access not set." This is a reminder to configure access links for those rooms using the Room Access editor (reachable from within the room settings editor via the **Access** button).

## Incomplete run banner

If your previous run ended before all queued rooms were cleaned (for example, because you cancelled it or the vacuum ran low on battery), a banner appears at the top of the Rooms panel listing the rooms that were missed. Two actions are available:

- **Queue Missed Rooms** — automatically sets only the missed rooms as included so you can finish the job.
- **Dismiss** — clears the banner without making any changes.

## Run profiles panel

To the right of the room grid (or below it on narrow screens) is the Run Profiles panel. A run profile saves your entire current setup — which rooms are included, their order, and all their settings — under a name so you can restore it with one tap.

See the Run Profiles section of this guide for full details.

## Saved Zones panel

Below the Run Profiles panel (in the same side column) is the Saved Zones panel — a collapsible list of named reusable clean regions (for example "the couch" or "the stove"), grouped by the room they're filed under. It is always visible, showing an empty-state message when you have no saved zones yet.

- Each zone row is a **multi-select checkbox**, so you can pick several zones at once.
- A shared set of **device clean settings** (Suction, Mode, Intensity, Water) sits at the top of the panel and applies to the zones you clean from here.
- A **Clean N selected** action cleans your selected zones using those shared settings.
- Per-zone controls let you **rename** a zone, **delete** it, or **re-file** it under a different room (or leave it Unassigned).
- A **Draw zone to save** button lets you draw a box on the map to capture a new saved zone.
