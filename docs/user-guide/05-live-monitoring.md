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

### Charge, wait, and zone stops

If the run includes a **charge stop**, a **wait stop**, or a **zone step** between room groups (see [Profiles](10-profiles.md) and [Zones](04a-zones.md)), the banner shows a dedicated status for that phase:

- **Charging to `<target>`%** — during a charge stop, shown with a lightning symbol (⚡). When the integration can estimate how long the charge will take, the subtitle reads "Charging to `<target>`% · ~N min left". A live "N% to go" counter shrinks toward the target as the battery fills.
- **Waiting · ~N left** — during a wait stop (a timed dock-and-hold, for example a mop-dry pause), shown with a timer symbol (⏱). The countdown updates on its own.
- **Cleaning zone `<name>`** — during a 🎯 zone step, shown while the vacuum works the saved-zone footprint. Once a time estimate is available (learned from past runs, or derived from the zone's size before the first one), the banner reads "Cleaning zone: `<name>` · ~N left" — the "~" appears either way, so the banner text itself doesn't tell you which kind of estimate you're looking at. (The learned-vs-size distinction is only shown pre-run, on the zone's queue chip in the room composer — see [Zones → Learned zone times](04a-zones.md#learned-zone-times).) The zone chip goes *current* in the live queue below, where its ETA is likewise always "~"-prefixed.

Charge and wait stops are docks — the vacuum parks there and the card does **not** treat that as the run finishing or being cancelled. A zone step is active cleaning of its own footprint. In every case the run continues automatically to the next phase, and the whole job is only reported finished once the last phase completes.

---

## Live progress list

Below the banner, a **Live Progress** list shows every room in the current job:

| Symbol | Meaning |
|--------|---------|
| ✓ | Room is complete. The actual time taken is shown next to the name. |
| ▶ | Room is currently being cleaned. Shows percentage done and estimated time remaining, or an ETA wall-clock time if a snapshot is available. The estimated total duration for the room is shown alongside a confidence chip. |
| ○ | Room is queued but not yet started. An ETA wall-clock time is shown if one is available. |
| ⤫ | Room was **skipped** — the run advanced past it without cleaning it. The row reads "Skipped" and shows no ETA (an ETA for a room that won't be cleaned would be a false promise). |

The list animates as rooms transition between states — you do not need to refresh the page.

A skipped room is also marked on the queue chips (dashed outline + struck-through name). See [Skipped-room marker](#skipped-room-marker) below.

---

## The live queue

While the Live Progress list above details the **rooms**, the **live queue** shows the *whole job* — the running twin of the queue you built. It flattens the entire sequence into one ordered chip row and appears above the room grid as soon as the job starts.

Every phase becomes a chip, in order:

- **Room** chips — one per room, showing a live percentage on the current room.
- **⚡ Charge** chips — a charge stop and its target.
- **⏱ Wait** chips — a timed dock-and-hold.
- **🎯 Zone** chips — a [zone step](04a-zones.md#add-a-zone-to-a-run-a-zone-step) and the saved zones it cleans.

Each chip carries one of three states as the run moves through the sequence:

| State | Meaning |
|---|---|
| **Done** | This phase has completed. |
| **Current** | The vacuum is on this phase now (a room shows its percentage; a charge/zone shows its ETA). |
| **Upcoming** | This phase is still ahead. |

So a stepped run reads at a glance — for example *Kitchen ✓ · ⚡ Charge to 80% (current) · 🎯 Stove zone · Kitchen* — with charge, wait, and zone stops shown in place between the room groups, not hidden.

**Collapse it.** The live queue can be folded to a single summary line when you'd rather watch the map or the banner — tap to collapse or expand it. It's a separate, always-available view: collapsing it doesn't remove it, and it never disturbs the running job.

!!! note "The live queue reads a frozen snapshot"
    The live queue is drawn from the job's plan as it was **when the run started** — a snapshot frozen at launch. The editable queue below is a separate thing entirely: it stays [locked while the job runs](03-queue-and-order.md#the-queue-is-locked-during-a-run) — including through a mid-run charge or wait stop — and unlocks once the job is finalized and the vacuum entity is no longer reporting `cleaning`/`paused`. Once it unlocks, the queue you build for your *next* clean can never disturb the chips of the job you just watched.

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

Both this warning and the stall notice below depend on strict room-order tracking, so they only appear on order-honoring brands (Eufy). On path-optimizing brands (the Roborock S6), where the robot's actual room sequence isn't tracked the same way, neither one appears — a Strict-order run doesn't change this.

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

## Stall capture

The stall notice tells you *which* room. **Stall capture** shows you *where in the room*. When it is armed and a stall is detected, the integration draws the room the vacuum stopped in — the room's outline, the last stretch of travel as a thin line, and a dot for where it came to rest — and raises a Home Assistant notification naming the room and the map.

Capture is **off by default and armed per vacuum**. A feature that writes a picture of your floor plan is one you switch on deliberately; an update never switches it on for you.

### Arming it

The Rooms toolbar — the button row above the room grid, alongside the list/map view toggles — has a **camera** button. Tap it to arm capture for the vacuum you are looking at, tap it again to disarm. The button is highlighted while capture is armed, and its tooltip reads **Turn on stall capture** or **Turn off stall capture**. It sits outside the map-only controls, so it is there in both the list view and the map view.

You can also arm it from an automation or from **Developer Tools → Actions** with the `eufy_vacuum.set_stall_capture` action, which takes the vacuum entity and `enabled: true` or `false`.

### What a capture produces

**A notification.** A persistent Home Assistant notification titled **Vacuum Agent**, reading for example:

> Alfred likely stalled in Kitchen on map 2

"Likely" is doing real work there: a stall is measured as elapsed time against the room's learned estimate, not as proof the robot is physically wedged. The map is shown by name on brands that report one and by its id otherwise. There is one notification per vacuum — a later stall replaces the earlier one rather than stacking up.

**An image**, written to:

```
config/eufy_vacuum/learning/<vacuum>/stall/<map id>.png
```

`<vacuum>` is the entity id without its `vacuum.` prefix. There is one file per vacuum per map, replaced on every capture, so an automation can point at a fixed path and never have to clean up after itself. The drawing is deliberately plain — one flat room silhouette, the trail, the dot, and the room's name — because it is meant to be read one-handed, at a glance, from another room.

**An event**, `eufy_vacuum_stall_captured`, fired once the image is on disk. This is the half that reaches your phone: trigger an automation on it and attach the file it names.

| Event field | What it holds |
|---|---|
| `vacuum_entity_id` | The vacuum that stalled. |
| `map_id` | The map it was cleaning. |
| `room_id` / `room_name` | The room it stopped in. |
| `image_path` | Full path to the PNG just written. |
| `message` | The same sentence the notification shows. |

!!! note "Why the notification has no picture in it"

    The image is written beside the vacuum's own data rather than into `config/www/`, because anything under `www/` is served **without authentication** — a cropped floor plan of your home should not be fetchable by URL. A persistent notification can only embed an image it can reach by URL, so the notification carries the text and the event carries the path. Someone already looking at Home Assistant has the map in front of them anyway; the picture is for the phone.

### When no capture appears

- Capture rides on the same stall detection as the notice above, so it only happens on order-honoring brands (Eufy), and only once per room per job. Turning capture off does **not** disable stall detection — the notice, the queue-chip warning, and the run's anomaly record all carry on regardless.
- Drawing the image needs an optional Python imaging package that isn't present on every Home Assistant install — one of the same set [Auto (CV) segmentation](16-making-your-own-maps.md#option-a-auto-cv--detect-rooms-from-a-screenshot) relies on. Without it there is no picture; nothing else is affected.
- If the map has no room outline to draw, no image is written.
- The trail is only drawn when the vacuum reported enough distinct positions around the stall to describe a real route. With fewer, the dot is shown on its own rather than a straight line the robot never drove.

---

## Skipped-room marker

If the live tracking sees the job advance past a queued room without ever cleaning it, that room is marked as **skipped** in the queue: its chip is drawn with a dashed outline and its name is struck through, and its row in the Live Progress list switches to the ⤫ "Skipped" style (no ETA — an ETA for a room that won't be cleaned would be a false promise).

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
