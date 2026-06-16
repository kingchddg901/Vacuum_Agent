# Profiles

There are two independent profile systems in eufy_vacuum: **room profiles** and **run profiles**. They solve different problems and work at different levels of the card.

- A **room profile** is a named set of cleaning settings (mode, suction, water level, cleaning path, passes, edge mopping). You save it once and apply it to any room at any time. Think of it as a preset.
- A **run profile** is a snapshot of an entire room queue: which rooms are included, in what order, and with what per-room settings. Applying one restores that entire setup in a single tap.

---

## Room Profiles

!!! note "Roborock (S6): Cleaning Profile section hidden"

    Everything in this Room Profiles section assumes your vacuum supports room profiles. Some brands report that they do not — the Roborock S6, for example, exposes only a per-room fan speed, so a room profile would be degenerate. On those vacuums the **Cleaning Profile** row is hidden from the room editor entirely, and none of the apply / Save as New / Save Over / Rename / Delete controls described below appear. The **Run Profiles** section further down is brand-agnostic and remains available on those vacuums.

### What a room profile saves

A room profile stores these fields:

| Field | What it controls |
|---|---|
| Cleaning mode | Vacuum only, mop only, or vacuum and mop |
| Suction level | Fan speed during vacuuming |
| Water level | Water output during mopping |
| Cleaning path | The intensity pattern the vacuum follows (called "clean_intensity" internally) |
| Cleaning passes | 1 pass or 2 passes |
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

Applying a profile replaces your current queue. It does not start a cleaning run — it only configures the card. You still need to press **Start** to begin cleaning.

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

When you create or edit a run profile, you can tick **Expose as Home Assistant Button**. When this is enabled, the backend creates a `button` entity for that profile. Pressing the button from anywhere in Home Assistant — a dashboard, a script, or an automation — applies the saved room configuration and starts the vacuum.

This is the main way to use run profiles in automations. You do not need to interact with the card at all: your automation calls `button.press` on the profile's entity, and the vacuum starts the saved run.

The detail section of a selected profile shows a "Exposed as button" label when this option is on.
