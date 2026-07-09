# 05 — Live Monitoring

While your vacuum is running, the card switches into a live monitoring mode. This page explains every piece of information shown during and immediately after a job.

---

## The live banner

As soon as a job starts, a live banner appears at the top of the card. It updates automatically as the vacuum moves from room to room.

The card follows the vacuum's actual room-to-room transitions rather than guessing purely from the clock: when the robot makes a real trip from one room to the next (a short travel gap between rooms), the banner advances to the new room. This makes the "currently cleaning" room more accurate, especially in homes where some rooms take much longer or shorter than their estimate.

!!! note "Strict-order runs: how the banner advances"

    The "follows actual transitions" behavior applies to normal, path-optimized runs (where the vacuum chooses its own route through the queue). During a Strict-order run — where rooms are sequenced and cleaned one at a time — the banner instead advances as each room is dispatched and completed in turn, since the order is driven by the framework rather than inferred from the robot's movement.

### What the banner shows

The banner always displays one of three states:

- **Cleaning `<room name>`** — the room currently being cleaned, shown with a play symbol (▶). If an estimated completion time is available for that room, it appears below the room name (for example, "Done at 2:45 PM").
- **All rooms complete** — shown when every queued room has been finished, with the subtitle "Returning to dock".
- **Learning active / Waiting for next room update** — a brief transitional state shown when the vacuum is between rooms and the card is waiting for the next update from the integration.

Each room entry in the banner also carries a **confidence chip** — a small label (High, Medium, or Low) that reflects how reliable the time estimate for that room is, based on how many past runs the integration has learned from.

### Charge and wait stops

If the run profile includes a **charge stop** or a **wait stop** between room groups (see [Profiles](10-profiles.md)), the vacuum docks partway through the run and the banner shows a dedicated status while it holds there:

- **Charging to `<target>`%** — during a charge stop, shown with a lightning symbol (⚡). When the integration can estimate how long the charge will take, the subtitle reads "Charging to `<target>`% · ~N min left". A live "N% to go" counter shrinks toward the target as the battery fills.
- **Waiting · ~N left** — during a wait stop (a timed dock-and-hold, for example a mop-dry pause), shown with a timer symbol (⏱). The countdown updates on its own.

These docks are part of the plan, so the card does **not** treat them as the run finishing or being cancelled. When the target is reached (or the wait time elapses), the vacuum leaves the dock and the banner returns to showing the next room group automatically.

---

## Live progress list

Below the banner, a **Live Progress** list shows every room in the current job:

| Symbol | Meaning |
|--------|---------|
| ✓ | Room is complete. The actual time taken is shown next to the name. |
| ▶ | Room is currently being cleaned. Shows percentage done and estimated time remaining, or an ETA wall-clock time if a snapshot is available. The estimated total duration for the room is shown alongside a confidence chip. |
| ○ | Room is queued but not yet started. An ETA wall-clock time is shown if one is available. |

The list animates as rooms transition between states — you do not need to refresh the page.

A room that appears to have been **skipped** is not shown as a row in this list — it is marked on the queue chips instead (dashed outline + struck-through name). See [Skipped-room marker](#skipped-room-marker) below.

---

## Live map

On brands that expose a live map (Roborock, or Eufy with the eufy-clean fork's live camera-map entity configured), the Map view shows the vacuum's live map image as the backdrop, so you can watch progress against the actual floor plan rather than a list alone. Plain Eufy without the fork has no live-map entity, so the CV/custom map or the room list is used instead.

A **Rotate** control in the map toolbar turns the map in 90° steps. The rotation is saved in the backend, so it follows you across every device that opens the card. The whole layer rotates together — the map image, the room polygons, the labels, and the mascot — but the labels and the mascot stay upright so they remain readable at any angle.

You can also draw and save room segments directly over the live map; see [Making your own maps](16-making-your-own-maps.md) for the full workflow.

The mascot follows the robot's current room (dwell-debounced so it does not jump on brief passes), and it stays draggable even when the map is rotated. If you'd rather watch it **track the robot's exact position**, tap the **Mascot follows robot** toggle in the map toolbar — the mascot then rides the live robot pixel (replacing the position dot) and moves with it in real time. Tap the toggle again to return it to room/dock mode.

---

## Battery warning

If the integration determines that the vacuum may not have enough charge to finish all remaining rooms without stopping to recharge, a warning notice appears below the banner:

> **May need to recharge to finish remaining rooms**

This warning is based on the live or reanchored estimate. If the vacuum does recharge mid-job, cleaning continues automatically and the warning clears once the job progresses.

---

## Running-long warning

Before a room crosses the full stall threshold, the card flags it as **running long**. When the room currently being cleaned has been going noticeably longer than its learned estimate — and the integration sees no sign that the vacuum has moved on to the next room — the current queue chip gains a warning ring.

This is the gentle, earlier tier below the stall notice below. It simply means "this room is overrunning its estimate." No action is required: many rooms occasionally run long (extra dirt, a re-clean pass, furniture in the way), and the integration keeps refining its estimates as it learns. If the room keeps going, the warning escalates into the stall notice described next.

A brand-new room the integration has not yet learned a time for does **not** trigger this warning — with no real baseline to judge against, it would otherwise flag every room on a fresh setup. The warning only appears once the room has a learned estimate to overrun.

---

## Stall detection warning

If the vacuum has been cleaning a single room for significantly longer than expected, the card shows a stall notice:

> **Robot may be stuck in current room** *(X min elapsed, expected Y min)*

The elapsed time and expected time are shown in parentheses when available. "Stuck" here means the room is taking much longer than the learned average — it does not always mean the vacuum is physically stuck.

**What to do:**

1. Check the vacuum's physical location if you can. The robot may have found an obstacle, a closed door, or a tangle it cannot clear on its own.
2. If the vacuum is genuinely stuck, use the vacuum's physical controls or the Home Assistant vacuum entity controls to send it home or to pause it.
3. If the room simply took longer than usual (furniture moved, etc.), no action is needed — the integration will update its estimates over time.

---

## Skipped-room marker

If the live tracking sees the job advance past a queued room without ever cleaning it, that room is marked as **skipped** in the queue: its chip is drawn with a dashed outline and its name is struck through.

This is a conservative signal — it only appears when the integration can be sure a room was genuinely passed over, not merely cleaned out of order. On most Eufy vacuums, which clean their queue strictly in order, a mid-run skip cannot be detected reliably while the job is still running, so this marker rarely appears live. The authoritative "these rooms were missed" report is the **incomplete run banner** below, which is reconciled after the job ends. The live skipped marker is an early hint for that same situation.

If a room you expected to be cleaned shows up as skipped, check it for closed doors or obstacles the vacuum could not get past, and re-queue it once the run finishes.

---

## Incomplete run banner

When a job ends without cleaning all the rooms that were queued — because it was cancelled, interrupted, or failed — the card shows an **incomplete run banner** the next time you open the card (the banner is hidden while a job is actively running).

### What the banner shows

- A headline stating the outcome: "Last run cancelled", "Last run failed", or "Last run interrupted", along with the number of rooms that were missed.
- A chip for each missed room by name.

### Actions

| Button | What it does |
|--------|-------------|
| **Queue missed rooms** | Re-adds all the missed rooms to the queue so you can start a new run immediately. |
| **✕** | Dismisses the banner. The missed-room information is cleared from card memory. |

The banner does not reappear unless a new incomplete run is recorded.
