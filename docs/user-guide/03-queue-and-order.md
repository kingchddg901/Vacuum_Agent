# 03 — The Queue and Room Order

## What the Queue Is

The queue is the ordered list of rooms the vacuum will clean when you press **Start Cleaning**. A room is in the queue when it is enabled (toggled on). The queue only contains enabled rooms — disabled rooms are excluded automatically and do not affect ordering.

!!! note "Roborock (S6): clean order is advisory"
    Path-optimizing vacuums like the Roborock S6 pick their own cleaning path and treat your queue order as a *suggestion* — they may not visit rooms in the order you set. To force the exact order, turn on **Strict order** (the "Force this exact order" toggle in the action bar) before you start. The integration then cleans one room at a time, in your order, returning to the dock between rooms — slower, but exact. (You can also set a **Sequence** in the Roborock app.) On order-honoring brands like Eufy the toggle doesn't appear and the queue order is always followed. Note that a **stepped run profile** (below) always runs in strict order on Roborock even if the toggle is off, because its sequence is deliberate.

!!! note "Stops and zones can join the queue"
    The queue isn't always rooms-only. There are two ways stops get in: a run profile with mid-run **charge** or **wait** stops (see [Profiles → Steps](10-profiles.md#steps-charging-and-waiting-mid-run)) puts those stops in the chip row between the room groups — or you can add breaks **directly to the queue**, no profile needed, with the **+ Charge break** and **+ Wait break** chips in the action bar (shown once two or more rooms are queued and no run is active; **Clear breaks** removes them all once any exist). You can likewise insert a **🎯 zone step** with the **+ Zone** chip (see [Zones](04a-zones.md#add-a-zone-to-a-run-a-zone-step)). A plain **Start Cleaning** on a queue with breaks runs it as a stepped, multi-phase job. All of these extra chips are described under [What Queue Chips Show](#what-queue-chips-show).

The queue is shown in two places at once:

- **Queue chips** — a row of small buttons displayed in the action bar above the room grid. Each chip represents one enabled room in the order it will be cleaned.
- **Room cards** — each card in the grid shows the room's current position number (for example, `#3`) in its top-left corner.

If no rooms are enabled, the action bar shows the message: "No rooms queued — toggle rooms to include them."

---

## What Queue Chips Show

Each queue chip displays:

- A **position number** (1, 2, 3, …) on the left side of the chip, reflecting the room's place in the cleaning order.
- The **room name**.
- A **time label** on the right side of the chip, when available. While a job is idle this shows the estimated cleaning time for that room (for example, `8 min`). While a job is running and that room is the current room, the label switches to a live **percentage** (for example, `42%`).

When a job is running, chips are colour-coded to show progress:

| Chip state | Meaning |
|---|---|
| Queued | Job has not started yet, or room is waiting its turn |
| Current | The vacuum is cleaning this room right now |
| Remaining | This room is still to be cleaned later in the job |
| Completed | The vacuum has finished this room |

Chips for rooms that have a learned time estimate also carry a confidence colour (green / amber / red) that reflects how reliable the estimate is.

You can click a queue chip to open that room's settings. Double-clicking opens the estimate detail. Holding the chip removes the room from the queue (disables it).

### Charge, wait, and zone chips

When your queue includes mid-run stops — from a **stepped run profile** (charge or wait stops — see [Profiles → Steps](10-profiles.md#steps-charging-and-waiting-mid-run)) or from **breaks and zone steps you added straight to the queue** — the chip row shows them in place, in sequence between the room groups:

- A **charge chip** — a ⚡ icon with a **"Charge to"** label and a percentage field (for example, "Charge to `80` %"). It marks the point where the vacuum docks and tops up before the next group.
- A **wait chip** — a ⏱ icon with a **"Wait"** label and a minutes field (for example, "Wait `10` min"). It marks a timed dock-and-hold pause, such as a mop-dry gap.
- A **zone chip** — a 🎯 icon with the name(s) of the saved zone(s) it cleans, plus a time estimate once one is available ("~" marks a size-based estimate; no prefix once it's learned). It marks a [zone step](04a-zones.md#add-a-zone-to-a-run-a-zone-step): the vacuum cleans that footprint as one phase of the run.

Unlike room chips, these chips are not clickable to open a room. Charge and wait chips are **editable inline** — type a new percentage or new minutes and the change is saved back (to the profile when one is applied, otherwise to the queue's own steps). A zone chip carries no editable value. To **add** steps use the **+ Charge break / + Wait break / + Zone** chips. Steps that live on the queue carry their own controls: a **⋮⋮ move handle** that opens the move-to-position picker, and a **✕** that removes the step. Steps belonging to an applied profile are reordered or removed in the run-profile editor (see [Profiles → Steps](10-profiles.md#steps-charging-and-waiting-mid-run)).

---

## Reordering Rooms

You have two ways to change the order rooms are cleaned.

### Drag and drop (desktop)

Each room card has a drag handle in its top-left corner (shown as `⋮⋮`). Click and hold the handle, then drag the card to a new position and release it. The other cards animate into their updated positions while you drag, and a brief highlight on the moved card confirms the change.

### Position selector (mobile or when drag is awkward)

Each room card also has a **Move** button next to the drag handle. Clicking **Move** opens a modal dialog titled "Move [room name]". Inside the modal you see a row of numbered buttons — one for each position in the queue. Tap the position you want the room to move to, then tap **Save**. Tap **Cancel** or tap outside the modal to close it without making a change.

Both methods produce the same result: the full list is re-indexed from 1 upward after every move, so position numbers are always consecutive.

---

## How Enable/Disable Affects the Queue

Toggling a room off (disabling it) removes it from the queue immediately. Its chip disappears from the action bar and its position number is removed from the card. The remaining enabled rooms are re-numbered in sequence.

Re-enabling a room adds it back to the queue. Its order value determines where it is inserted relative to other enabled rooms.

Rooms that have not been placed in the access tree yet (shown in the "Access not set" panel above the room grid) can still be enabled and queued, but you may want to resolve their access configuration before running a job.

---

## The queue is locked during a run

While a job is running, the queue you're looking at is **locked** so you can't accidentally disturb the run in progress. Room enable/disable toggles, drag-reorder, the **Move** control, **Select All**, and **Clear Queue** are all disabled, and room cards are shown in a locked (non-interactive) state.

This is intentional: a running job follows the snapshot it started with (see [Live monitoring → The live queue](05-live-monitoring.md#the-live-queue)), so editing the queue mid-run would have no effect on the current clean anyway — and silently changing chips under a running job would be confusing. The lock covers the whole tracked job, including any mid-run charge or wait stop while the robot sits on its dock.

The lock lifts once the job is finalized **and** the vacuum entity is no longer reporting `cleaning` or `paused` — the two checks are independent, so a brief poll-skew window where the entity still reads `cleaning` right after a terminal job can hold the lock a moment longer. Once it lifts, you're free to build the next queue — the queue you edit is kept separate from the frozen snapshot the live queue displays.

---

## Queue Summary

At the top of the action bar, above the queue chips, there is a brief summary line that shows:

- **How many rooms are included** — for example, "3 rooms included" or "1 room included" (or "2 rooms · 1 zone included" once a zone step is queued — see [Rooms Panel → Including and excluding rooms](02-rooms-panel.md#including-and-excluding-rooms)).
- **An estimated total time** for the full queue, shown as "~12 min" when a time estimate is available. This figure is drawn from learned or default per-room estimates and updates as you add or remove rooms from the queue.
