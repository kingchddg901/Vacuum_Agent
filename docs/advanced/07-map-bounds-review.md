## Map Bounds Review

The **Map Bounds** tab gives you a live view of what the integration has learned about each room's spatial extent. You can audit individual job runs, remove outliers, and rebuild bounds from archived data — all without touching any configuration files.

---

### What bounds are

Every time the vacuum completes a cleaning job, the integration records the robot's position samples for that run. For each room that participated in the job, it computes a bounding box — the min/max X and Y extents in vacuum coordinate space — and stores that as a single job entry in the room's history.

The room's **accumulated bounds** are the union of all non-excluded job entries in that history. In vacuum coordinate terms, a room's bounds are the rectangular region (min_x, min_y) → (max_x, max_y) that encompasses every cleaning pass the robot has made in that room. The integration adds a 50-unit margin on all sides when using bounds for room-presence detection, so small gaps between runs do not break attribution.

Bounds accumulate over time: the more solo or targeted runs a room has, the tighter and more representative the box becomes. A room with no history has no bounds, and the integration treats it as unknown.

Each job entry in the history stores:

- The bounding box for that specific run (min_x, max_x, min_y, max_y)
- The center point (cx, cy)
- The sample count for that run
- A timestamp (recorded_at)
- A job identifier
- An excluded flag

The accumulated bounds shown on each card are computed fresh from whichever job entries are currently active (not excluded).

---

### Why you'd review bounds

Bounds drive two things: room-presence detection (which room the robot is currently in) and sample attribution in multi-room jobs (deciding which room owns a given position sample). If a run produced bad data — a robot that wandered into the wrong area, a recovery pass that collected samples far outside the room's normal footprint, or an unusually large bounding box that bleeds into a neighboring room — you can exclude that run's contribution without deleting the underlying data.

You would also check this view to confirm that a room has enough history to be used reliably. The card marks a room's bounds as "Likely" until it reaches 4 active runs; at 4 or more it shows a run count and sample count with a green badge.

---

### Navigating to the view

Click the **Map Bounds** tab in the navigation bar. The card loads a snapshot of all room bounds for the active vacuum and map on first open and refreshes it after every action.

---

### Filter options

Three filter chips let you narrow which rooms are shown:

| Filter | What it shows |
|---|---|
| **All Rooms** | Every room the integration has any record for |
| **Has Bounds** | Rooms where at least one job entry is active |
| **No Bounds** | Rooms with no active history (all entries excluded, or never cleaned) |

Clicking a chip updates the view immediately. Rooms with bounds sort before rooms without bounds; within each group they sort by room ID numerically.

---

### Reading a room card

Each room card shows:

- **Room name and ID** — the display name from your room configuration and the raw room ID.
- **Status badge** — green with run count and sample count when confidence is high (4+ active runs), amber "Likely" when fewer than 4 active runs exist, or "No bounds" when there is nothing active.
- **Excluded badge** — appears when any job entries are currently excluded for that room.
- **Bounds table** — the current accumulated X and Y ranges and their width/height in vacuum units, plus the timestamp of the most recent update.
- **Run history** — a list of individual job entries, newest first.

The oldest entry in the list is always marked **Baseline** and is protected — it cannot be excluded. This prevents the accumulated bounds from becoming empty by accident.

---

### Outlier detection

The card performs a leave-one-out outlier check on each active job entry. It computes the union of all other active entries and flags the current entry if any of its edges extend more than 10% beyond that reference box. Flagged entries show an **Outlier** badge identifying which edge is affected (for example, "Outlier: max X, max Y"). This is a visual hint — it does not exclude the entry automatically.

---

### Excluding a job's bounds contribution

To remove a specific run from the accumulated bounds:

1. Expand the run history section on a room card.
2. Find the entry you want to exclude. Entries flagged as outliers are highlighted.
3. Click **Exclude** on that entry.

The card disables the button and shows a spinner while the call is in flight, then refreshes the snapshot. The entry remains visible in the history marked with an "Excluded" badge. The accumulated bounds for the room are immediately recomputed from the remaining active entries. If all non-baseline entries are excluded, only the baseline contributes to bounds.

You cannot exclude the baseline entry (the oldest entry in the list). You also cannot exclude an entry when only one active entry remains — there must always be at least one active non-baseline entry before the baseline for exclusion to be available. (The Exclude button is hidden automatically when these conditions are not met.)

---

### Restoring excluded bounds

To bring a previously excluded entry back into the accumulated bounds:

1. Find the entry with the "Excluded" badge in the run history.
2. Click **Restore** on that entry.

The snapshot refreshes and the entry contributes to bounds again.

---

### Clearing all bounds for a room

The **Clear All** button at the bottom of a room card deletes the room's entire bounds record and job history. This is destructive — all history for that room is removed from the mapping data file and the room starts fresh the next time it is cleaned.

The button is disabled when the room has no bounds. While the clear is in flight the button shows "Clearing…" and is disabled.

---

### Rebuilding bounds from the archive

When a room's bounds have been cleared or are otherwise absent, but the room has a raw-samples archive on disk (captured from prior cleaning runs), you can regenerate bounds from that archive without running the vacuum again.

A **Rebuild from Archive** button appears on the room card when the following conditions are both true:

- The room currently has no active bounds.
- The integration has a raw-samples archive file for that room.

Click **Rebuild from Archive**. The card shows "Rebuilding…" while the backend re-processes the archive and writes new job history entries. After it completes, the snapshot refreshes and the bounds table appears.

If neither the Clear All button nor the Rebuild button appears on a room card, that room has no archive and no current bounds: the only way to establish bounds is to run the vacuum in that room.
