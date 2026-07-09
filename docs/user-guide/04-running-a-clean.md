# 04 — Running a Clean

## Starting a Clean

To start a clean, enable at least one room and then press the **Start Cleaning** button in the action bar. The button is greyed out and disabled when a start is blocked (see [What Blocks a Start](#what-blocks-a-start) below).

When the card detects that some rooms in your queue are blocked but others can still be cleaned, the button label changes to **Confirm Start** and the button pulses. This is called the preflight confirmation step. Before the job sends, a panel expands below the button listing:

- The number of **blocked rooms** and the estimated time they would have added.
- The number of **included rooms** that will still be cleaned.
- A **Blocked Rooms** section with each blocked room's name and reason.
- A **Modified Rooms** section if any rooms will run with adjusted settings.
- A **Warnings** section for any other preflight notes.

A **Cancel** button appears alongside the flashing confirm button so you can back out. Pressing **Confirm Start** proceeds with the reduced run. Pressing **Cancel** dismisses the preflight panel and returns the button to its normal state.

---

## What Blocks a Start

The card shows a brief reason below the action bar when the Start button is disabled. The possible blocked reasons are:

| Reason | What it means |
|---|---|
| `job_paused` | A tracked job is currently paused. Resume or cancel it before starting a new one. |
| `onboarding_required` | One or more enabled rooms have not had their floor type confirmed yet. Set the floor type in each room's settings before starting. |
| `all_selected_rooms_blocked` | Every room in the queue is individually blocked (for example, by access constraints). No rooms remain to clean. |
| `no_target_map` | No map has been selected as the target. |
| `map_mismatch` | The map you have selected does not match the map the vacuum is currently on. |
| `no_rooms_selected` | No rooms are enabled in the queue. |
| `invalid_payload` | The room-clean command could not be built — the payload is missing or invalid. |
| `mid_job_service` | The dock is servicing the active job (for example, washing pads) and cannot start a new one. |
| `active_job_running` | A room-clean job is already running. |
| `vacuum_busy` | The vacuum is busy with another task and cannot accept a new room job. |

Some conditions are **warnings** rather than hard blocks. When the dock is currently drying pads (`dock_drying`), the start button remains enabled but is styled with a warning colour, and a tooltip explains the situation. Similarly, if the planned job is estimated to use most or all of the clean water in the tank, a water warning appears but does not prevent the start.

---

## While a Job Is Running

Once a job starts, the action bar updates to reflect the live state:

- The primary button label changes to **Cancel Run** (with a cancel style).
- A **Pause** button appears next to it.
- The queue chips change colour to show which rooms are completed, which room is current, and which rooms are still remaining.
- The current room's chip shows a live completion percentage (for example, `42%`) instead of a time estimate.
- The room card for the current room shows a progress bar fill and a progress chip with percentage complete and estimated time remaining (for example, "42% complete" and "~3 min left").
- An **Active Job** strip appears above the room grid. It shows a "Running" label with a pulse indicator, followed by chips for each room in the job. Each chip in the active job strip shows the job-order position number and the room name.

!!! note "Stepped runs dock mid-job on purpose"
    If you started a [stepped run](10-profiles.md#steps-charging-and-waiting-mid-run) — a run profile with **charge** or **wait** stops — the vacuum returns to its dock between room groups to charge or hold. That is expected: the run has not ended, and the card knows the dock is intentional, so it will not report the job as finished or cancelled until the whole sequence is done. During a stop the live panel shows the charge or wait progress instead of a room percentage. See [Steps: charging and waiting mid-run](10-profiles.md#steps-charging-and-waiting-mid-run) for the full walkthrough.

---

## Zone cleaning (draw a box)

Instead of cleaning whole rooms, you can clean **just an area you draw on the map** — handy for a spill, a high-traffic patch, or the spot under the table.

Zone cleaning works on any device-accurate map backdrop — either the **live map** image or the **rendered room map** (the **▦** map-render view) — on brands that support it: **Eufy** (on eufy-clean v1.11.1+) and **Roborock** (the S6, and likely other models, through the stock integration). On Roborock the **Draw a zone** button appears once the rendered room map is on. You can draw at **any map rotation**. The per-clean limits are brand-specific: **Eufy** allows up to **10** zones; **Roborock** up to **5**, each between **1 ft² and 32.8 ft²** — the card stops the draw at the cap, and an out-of-size zone is refused with a message.

1. Open the **Map** view and tap the **▢ "Draw a zone to clean"** button in the map toolbar to enter zone mode.
2. **Drag a box** on the map over the area you want cleaned. Repeat to add more boxes — up to the brand cap noted above (each is numbered).
3. The **Zone clean** panel (right column) lists your zones. Remove one with its **✕**, or **Clear** to drop them all. Under **Settings**, choose the suction/mop options for the run — they apply to the whole clean.
4. Press **Clean zone** (or **Clean *N* zones**) to send it. **Cancel** leaves zone mode without cleaning.

Zones are one-off — they aren't saved between cleans. To clean by room instead, leave zone mode and use the normal [room queue](#starting-a-clean).

---

## Strict Order (path-optimizing vacuums)

By default the robot decides its own cleaning path and may visit the rooms in whatever order is most efficient for it, regardless of the order shown in your queue. When you turn on **Strict order** for a run, the integration instead cleans the rooms one at a time, in the order you set, returning to the dock between rooms before dispatching the next one. This is slower, but it guarantees the exact order. Each room dispatch is verified and retried if the vacuum doesn't pick it up, and the live progress banner advances as each room is dispatched and then completed.

Strict order is a per-run opt-in, and the toggle only appears on brands that don't already honour your queue order — the path-optimizing Roborock S6, for example. On Eufy the queue order is always followed, so the toggle has no effect and isn't shown. See [The Queue and Room Order](03-queue-and-order.md) for where to find the toggle.

A [stepped run](10-profiles.md#steps-charging-and-waiting-mid-run) — one with charge or wait stops — always runs in strict order automatically, whether or not the toggle is on, because the stops make it a deliberate sequence. On Eufy this changes nothing (the order is already honoured); on a path-optimizing Roborock it means each group's rooms are cleaned in exactly the order shown, with a dock between them.

---

## Pausing a Job

Press the **Pause** button while a job is running. The button is only visible when a job is active and pausing is allowed — its visibility keys off the vacuum entity state being `cleaning`, not the tracked job status. After you press **Pause**:

- The vacuum pauses.
- The tracked job status changes to `paused`.
- The **Pause** button is replaced by a **Resume** button.
- The start button becomes disabled with the reason `job_paused` — you cannot start a new job while one is paused.

---

## Resuming a Job

Press the **Resume** button to send a start command to the vacuum and resume the tracked job. The **Resume** button only appears when the vacuum entity state is `paused` (its visibility keys off the vacuum state, not the tracked job status). After resuming, the job status returns to `started`, the **Pause** button reappears, and the card continues tracking progress where it left off. Paused time is accumulated separately so elapsed-time estimates remain accurate.

---

## Cancelling a Job

Press the **Cancel Run** button to cancel the active or paused job.

When you press **Cancel Run** the first time, the button label changes to **Confirm Cancel** and begins flashing. A **Cancel** button appears below it so you can change your mind. This two-step confirmation protects you from an accidental cancel.

Press **Confirm Cancel** to proceed. The card sends a `return_to_base` command to the vacuum. It then waits up to 30 seconds for the vacuum to reach a docked or idle state before writing the final outcome. If the vacuum does not confirm within that window, the job is finalized as cancelled anyway so the tracked state is never left open. Once cancelled, the active job strip disappears and the action bar returns to its idle state.
