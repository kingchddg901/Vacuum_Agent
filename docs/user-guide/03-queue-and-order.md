# 03 — The Queue and Room Order

## What the Queue Is

The queue is the ordered list of rooms the vacuum will clean when you press **Start Cleaning**. A room is in the queue when it is enabled (toggled on). The queue only contains enabled rooms — disabled rooms are excluded automatically and do not affect ordering.

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

## Queue Summary

At the top of the action bar, above the queue chips, there is a brief summary line that shows:

- **How many rooms are included** — for example, "3 rooms included" or "1 room included".
- **An estimated total time** for the full queue, shown as "~12 min" when a time estimate is available. This figure is drawn from learned or default per-room estimates and updates as you add or remove rooms from the queue.
