## Base Station

The Base Station tab shows you the current state of the dock and lets you trigger dock-side actions such as washing the mop, drying the mop, and emptying the dust bin. It also lets you set the default pause timeout used when a cleaning run is paused.

!!! note "Roborock (S6): no Base Station tab"

    On a dockless vacuum (for example, the Roborock S6) the entire Base Station tab is hidden — there is no dock for it to describe. Everything below applies only to models that ship with a base station.

The panels and action buttons on this tab are **capability-gated** — on a docked model, only the panels and buttons that apply to your vacuum's hardware are shown. A fully-equipped dock (mop wash + mop dry + auto-empty) shows everything below. A model with auto-empty but no mop dock shows Station Status, Pause Timeout, the Recent Dock Activity panel with just the Dust Empty card, and an Empty Dust button. If a section described below is missing from your card, your vacuum doesn't have that hardware.

### Station Status

The **Station Status** panel shows four values pulled from the latest dock status snapshot:

- **Dock Status** — the dock's reported state (for example, idle or cleaning)
- **Lifecycle** — the dock's lifecycle state (for example, standby or active)
- **Task** — the robot's current task as seen by the dock
- **Docked** — "Yes" if the robot is currently on the dock, otherwise "No"

The time the snapshot was last updated appears below the stat row when available.

### Water

The **Water** panel shows the water situation for the current or upcoming cleaning job:

- **Station Water** — the current level in the base station's water reservoir, shown as a percentage if the value is numeric or as a text label otherwise
- **Tank Now** — the available clean water volume right now, in millilitres
- **After Job** — the projected clean tank level after the planned job completes, shown as millilitres and a percentage when both are available
- **Job Use** — the estimated amount of clean water the planned job will consume, in millilitres

### Recent Dock Activity

The **Recent Dock Activity** panel shows the last known timestamps and recorded event counts for three dock operations:

- **Mop Wash** — when the dock last washed the mop, and how many mop washes have been recorded
- **Dust Empty** — when the dock last emptied the dust bin, and how many empties have been recorded
- **Dry Start** — when the dock last started a drying cycle, how many dry starts have been recorded, and the duration of the last dry cycle in minutes (if available)

If an event has never been recorded, the time field shows "No activity yet".

### Pause Timeout

The **Pause Timeout** section lets you set the default number of minutes the card will wait before automatically resuming or handling a paused run. Four options are available: **15 min**, **30 min**, **45 min**, and **60 min**. The currently active value is highlighted. Clicking a different value saves the change to the backend immediately.

### Dock Actions

The **Dock Actions** section shows four controls for triggering dock-side operations. Each action is shown as a button card:

| Action | What it does |
|---|---|
| **Wash Mop** | Tells the dock to wash the mop pad |
| **Dry Mop** | Tells the dock to start a mop-drying cycle |
| **Stop Drying** | Cancels an in-progress drying cycle |
| **Empty Dust** | Tells the dock to empty the robot's dust bin |

Each card shows whether the action is **Ready** or **Unavailable**, along with a reason message from the backend. An action is only clickable when the backend has confirmed it is allowed and no other dock action is already in progress.

When you click an allowed action, the card changes to **Running...** and the button is disabled until the action completes and the dock status refreshes. If the robot is not docked or the backend has gated the action for another reason, the card shows "Unavailable" and the button cannot be clicked.
