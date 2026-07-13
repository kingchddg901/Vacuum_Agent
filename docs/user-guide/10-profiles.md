# 10 — Profiles

There are two independent profile systems in eufy_vacuum: **room profiles** and **run profiles**. They solve different problems and work at different levels of the card.

- A **room profile** is a named set of cleaning settings (mode, suction, water level, cleaning path, passes, edge mopping). You save it once and apply it to any room at any time. Think of it as a preset.
- A **run profile** is a snapshot of an entire room queue: which rooms are included, in what order, and with what per-room settings. Applying one restores that entire setup in a single tap.

---

## Room Profiles

!!! note "Roborock: Run Profiles work everywhere; room-level presets depend on the model"

    This does **not** mean Roborock lacks profiles — **Run Profiles** (the [next section](#run-profiles)) are fully supported on every Roborock, including the charge / wait step sequences and the exposed profile buttons, and are the main way to save and recall a setup.

    The room-level **Cleaning Profile** presets in *this* section depend on how much your model exposes per room. On the **S6** (fan speed is the only settable per-room field) a preset bundle would be a degenerate named fan speed, so the Cleaning Profile row is hidden — you set fan directly. On a **settable-mop model (S7/S8 and newer)**, where cleaning mode and water level are per-room too, the Cleaning Profile presets appear and work exactly as on Eufy.

### What a room profile saves

A room profile stores these fields:

| Field | What it controls |
|---|---|
| Cleaning mode | Vacuum only, mop only, or vacuum and mop |
| Suction level | Fan speed during vacuuming |
| Water level | Water output during mopping |
| Cleaning path | The intensity pattern the vacuum follows (called "clean_intensity" internally) |
| Cleaning passes | The number of cleaning passes, from 1 up to the adapter maximum (2 on Eufy, 3 on Roborock) |
| Edge mopping | Whether to mop along walls and edges |

A room profile does not store which rooms it applies to, or whether a room is included in the queue. It is purely a settings preset.

Some profiles are **built-in** (labelled as "built in and read-only" in the editor). You can apply them but cannot edit, rename, or delete them. Profiles you create yourself are **custom** and fully editable.

### How to open the room editor

Room profiles are managed inside the room editor modal. To open it, go to the **Rooms** tab and click the settings button on any room chip. The modal opens with the room's current settings and shows all available profiles across the top under the heading **Cleaning Profile**.

### How to apply a room profile

In the room editor, the **Cleaning Profile** row shows chips for each available profile. Click any chip to instantly load that profile's settings into all the fields below. The chip becomes highlighted to show it is active.

If you then change any field manually, the card switches to **Custom** mode — a "Custom" chip becomes highlighted instead, and the profile link is cleared. Your manual edits remain; the profile has just been unlinked.

Click **Save** at the bottom of the modal to write the current field values back to the room.

### How to create a room profile

1. Open the room editor for any room.
2. Set the fields to the combination you want to save.
3. Click **Save as New** in the Cleaning Profile row.
4. A prompt asks for a display label (the name shown in the card). Enter a label and confirm.

The profile is saved to the integration's backend and immediately appears as a chip in the profile row. The editor automatically links the current room to the new profile.

### How to overwrite a room profile

If you want to update an existing custom profile with a room's current settings:

1. Open the room editor for the room whose settings you want to promote.
2. Adjust the fields if needed.
3. Click **Save Over** in the Cleaning Profile row.
4. If the editor is already linked to a custom profile, that profile is the target. If the editor is in Custom mode or linked to a built-in profile, a prompt lists your custom profiles and asks you to choose one by name.
5. Confirm the overwrite when asked.

Built-in profiles cannot be overwritten. The **Save Over** button is disabled when no custom profiles exist.

### How to rename a room profile

1. Open the room editor for any room.
2. Click **Rename** in the Cleaning Profile row.
3. If the editor is linked to a custom profile, that profile is the target. Otherwise a prompt asks you to choose from your custom profiles.
4. A prompt asks for a new display label.
5. A second prompt lets you change the internal backend key if you want. You can accept the suggested key or leave it unchanged.

The **Rename** button is disabled when no custom profile is active in the editor.

### How to delete a room profile

1. Open the room editor for any room.
2. Click **Delete** (shown in red) in the Cleaning Profile row.
3. If the editor is linked to a custom profile, that profile is the target. Otherwise a prompt asks you to choose.
4. Confirm the deletion when asked.

Deletion cannot be undone. Built-in profiles cannot be deleted. The **Delete** button is disabled when only built-in profiles are available.

---

## Run Profiles

### What a run profile saves

A run profile is a full snapshot of the room queue as it was when you saved it. It records:

- Which vacuum entity and which map the profile belongs to
- Which rooms were included
- The room order
- The per-room settings in effect at save time (all fields saved into each room)
- **Optionally, an ordered list of _steps_** — room groups broken up by **charge** stops ("dock and charge to X% before continuing") and **wait** stops ("dock and hold for X minutes"). A profile without steps is just a plain queue; a profile with steps runs as a sequence. See [Steps: charging and waiting mid-run](#steps-charging-and-waiting-mid-run) below.
- The profile's display name
- Whether the profile is exposed as a Home Assistant button entity (see below)

A run profile is tied to a specific map. You will only see run profiles for the map you are currently viewing.

### How run profiles differ from room profiles

| | Room profile | Run profile |
|---|---|---|
| What it saves | A set of cleaning settings | A full room queue and all room settings |
| Scope | Any room on any map | One specific map |
| Applies to | One room at a time | The entire queue at once |
| Stored per-room settings | Yes | Yes (as a snapshot at save time) |
| Includes room selection | No | Yes |
| Includes room order | No | Yes |

### The Run Profiles panel

The Run Profiles panel appears alongside the Rooms view as a side panel on the right. It shows:

- A **Save This Setup** button at the top.
- A list of saved profiles as chips. The active profile (if one has been applied) is highlighted.
- A detail section below the list showing the selected profile's name, room count, and whether it is exposed as a button.

### How to create a run profile

1. Go to the **Rooms** tab and configure your room queue: include the rooms you want, set their order, and adjust any per-room settings.
2. In the Run Profiles panel, click **Save This Setup**.
3. An editor form opens. Enter a name for the profile (for example, "Morning Clean").
4. Optionally tick **Expose as Home Assistant Button** if you want the integration to create a button entity for this profile (see below).
5. Click **Create Profile**.

The profile appears immediately in the list.

### How to apply a run profile

Click any profile chip in the Run Profiles panel. The card restores the saved room selection, order, and per-room settings for that map. The chip becomes highlighted to show the profile is active, and the detail section below the list shows the profile's room count.

Applying a profile replaces your current queue. It does not start a cleaning run — it only configures the card. You still need to press **Start** to begin cleaning — or use **Run** (below) to apply and start in one tap.

### Running a profile now — the Run button

When you select a saved profile, its detail section shows a **Run** button alongside **Edit** and **Delete**. **Run** applies the profile *and* starts it immediately — the one-tap "do this now" action, so you do not have to apply and then press **Start** separately.

If the profile has steps (below), **Run** dispatches the whole sequence, not just the first group.

---

## Steps: charging and waiting mid-run

A plain run profile cleans its rooms in one pass. A **stepped** profile breaks the run into groups separated by stops, so the vacuum can dock, do something, and keep going — all as one job:

- A **charge step** ("Charge to X%") docks the vacuum and waits until the battery reaches your target before starting the next group. This is what turns *"vacuum the whole floor, top up to 80%, then mop it"* into a single button press instead of two profiles wired together with an automation.
- A **wait step** ("Wait X min") docks and holds for a set number of minutes — for example a **mop-dry pause** between a vacuum pass and a mop pass.
- A **zone step** ("🎯 clean a saved zone") cleans a [saved zone](04a-zones.md)'s footprint as one phase of the run — for example vacuum the rooms, then hit the stove zone before mopping. Zone steps are added on the queue with the **+ Zone** chip (not in the editor below), and are captured into the profile when you save your setup. See [Zones → Add a zone to a run](04a-zones.md#add-a-zone-to-a-run-a-zone-step).

Two things worth knowing:

- **The same room can appear in more than one group, with different settings each time.** Vacuum the kitchen in the first group, then mop the same kitchen in a later group — each group's own settings apply for that phase. This is the intended way to build a vacuum-then-mop run.
- **A run can charge more than once.** Clean → charge → clean → charge → clean is allowed; each charge is its own stop.

!!! note "No fake charge estimate"

    The card does **not** show a predicted duration for a charge step before the run. How long a charge takes depends entirely on how low the battery is when the vacuum docks, which varies every run — so rather than show a number it hasn't earned, the card just notes that "Charge time varies with the battery level when it docks," and shows a live countdown once the charge is actually under way.

### Building a stepped profile

Steps live in the run-profile **editor**, so open a profile for editing first (select it, then **Edit**). The **Run steps** section has three controls:

| Button | What it does |
|---|---|
| **Add a charge step** | Inserts a "Charge to X%" stop. Set the target percent in the field on the step row. |
| **Add a wait** | Inserts a "Wait X min" stop. Set the minutes in the field on the step row. |
| **Add current rooms as a group** | Snapshots the rooms currently set up in the **Rooms** view as the next room group in the sequence. |

The typical flow is: set up the first batch of rooms in the Rooms view → **Add current rooms as a group** → **Add a charge step** (or a wait) → change the Rooms view to the next batch → **Add current rooms as a group** again, and so on. Each step row has up/down arrows to reorder it and a control to remove it.

A charge or wait stop at the very start or end of the sequence is dropped automatically (there is nothing to bracket), and two of the same kind in a row collapse to the later one.

!!! note "Zone steps are added from the queue, not the editor"
    The editor's three controls add charge, wait, and room-group steps. A **zone step** is added a different way — on the queue, with the **+ Zone** chip (see [Zones](04a-zones.md#add-a-zone-to-a-run-a-zone-step)) — and is captured into the profile when you save your setup. In the editor a zone step then appears in the step list (🎯) and can be reordered or removed like the others; it just isn't created here.

### The "This run" preview

When a stepped profile is applied, the Rooms view shows a **"This run"** block — a collapsible preview that lays out the exact sequence the vacuum will follow: each room group, each ⚡ charge stop with its target, and each ⏱ wait stop with its duration. It is the read-only mirror of the steps you built, so you can confirm the order before pressing **Run**. The saved-profile detail card shows the same sequence under a **"Runs as"** heading — as does the standalone **Profile card** you can drop on any dashboard (see [Dashboard & Room cards](20-dashboard-and-room-cards.md#the-profile-card)), which surfaces one saved profile's **Runs As** list plus a **Run** button without opening the panel.

### Editing a charge or wait inline

Once a stepped profile is applied, the queue chips include the charge and wait stops as chips of their own. You can adjust a stop **directly in its chip** — type a new percent into a charge chip, or new minutes into a wait chip — without reopening the editor. The change is saved back to the profile.

### Watching a stepped run

While a stepped run is going, the live panel surfaces the current stop:

- During a charge: **"Charging to X%"** with a live **"N% to go"** figure that shrinks as the battery climbs (plus a "~M left" estimate once the charge-rate baseline has learned enough to earn one).
- During a wait: **"Waiting · ~M left"** — a countdown of the remaining hold time.

Between groups the vacuum returns to its dock. That is normal: the run has not ended, it is just parked for the stop. The card knows the dock is intentional and will not report the run as finished or cancelled until the whole sequence is done.

### How stepped runs behave on Roborock

Stepped profiles work the same on Roborock as on Eufy, with two brand details:

- **Order is enforced.** A stepped profile is a deliberate sequence, so it always runs in **strict order** — each group's rooms are cleaned in exactly the order shown. (Roborock normally path-optimises and may reorder rooms within a single dispatch; inside a stepped run it does not.) The trade-off is that a multi-room group docks between its rooms.
- **Vacuum-then-mop needs a settable mop.** Cleaning one group as a vacuum pass and a later group as a mop pass requires a model whose mop is programmatically settable (Roborock S7/S8 and newer). On the S6, whose mop is tank-only, the mop controls are hidden and a group's mop setting has no effect. Charge and wait stops themselves work on every model.

### How to overwrite (update) a run profile

If you want to update a saved profile with your current room setup:

1. Click the profile chip you want to update — its detail section appears below the list.
2. Click **Edit** in the detail section.
3. The editor form opens with the profile's current name pre-filled. Change the name if you want, or leave it.
4. Click **Save Over Profile**.

This replaces the saved room snapshot with whatever is currently configured in the card.

### How to rename a run profile

Follow the same steps as overwriting (click the chip, then **Edit**), change the name field, and click **Save Over Profile**. The room snapshot is also updated in the process.

If you only want to change the name without changing the saved rooms, apply the profile first (so the card loads its rooms), then open Edit and save.

### How to delete a run profile

1. Click the profile chip to select it.
2. Click **Delete** in the detail section.
3. Confirm the deletion when asked.

Deletion cannot be undone.

### Exposing a run profile as a Home Assistant button

When you create or edit a run profile, you can tick **Expose as Home Assistant Button**. When this is enabled, the backend creates a `button` entity for that profile. Pressing the button from anywhere in Home Assistant — a dashboard, a script, or an automation — applies the saved room configuration and starts the vacuum. If the profile has steps, the button runs the whole sequence (charge and wait stops included), exactly like the card's **Run** button.

This is the main way to use run profiles in automations. You do not need to interact with the card at all: your automation calls `button.press` on the profile's entity, and the vacuum starts the saved run. A profile button is also a tidy dashboard tile — it triggers from a tap without opening the card.

The detail section of a selected profile shows a "Exposed as button" label when this option is on.
