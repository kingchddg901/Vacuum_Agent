# Setup

The Setup tab is a two-step wizard that gets your vacuum registered with the integration and prepares its maps and rooms for use. You work through it once per vacuum — or once per map if you have several floor plans. After setup is complete, you use the Rooms tab for day-to-day cleaning.

## Accessing the Setup tab

Open the Lovelace card for your vacuum. The tab bar along the top includes a **Setup** item. Click it to open the wizard. The card shows a **Vacuum Setup** heading and a brief description reminding you what the two steps accomplish: registering the vacuum, importing its maps, and configuring rooms per map.

If the card has never loaded setup status from the integration, it shows a **Check Status** button at the bottom of the view. Click it once to fetch the current state. After the first successful fetch, the button label changes to **Refresh** and stays available throughout setup so you can re-sync at any time.

---

## The three workflow states

Before you do anything, the integration backend classifies the current situation into one of three states. These states determine which controls are active and what guidance text appears.

### `no_vacuums` — nothing configured yet

Step 1 shows its badge as **1** (unfilled) and the body text reads: "Register this vacuum with the integration so it can be managed." The vacuum entity ID configured on the card is displayed below that text, and an **Add Vacuum** button is shown.

Step 2 is locked. Its body reads "Complete step 1 first." and no import button is available until step 1 is done.

### `no_map` — vacuum registered but no map imported

Step 1's badge changes to a filled **✓** and the body is replaced by a green "Vacuum registered." message — that step is done.

Step 2 becomes active. Its body reads: "Import the vacuum's currently active map. Make sure it has completed a mapping run first." An **Import Active Map** button appears.

### `ready` — at least one map has been imported and configured

Both steps show ✓ badges. A green banner appears below the steps:

> ✓ Setup complete — switch to the Rooms tab to start cleaning.

If maps have been imported but not yet fully configured, a blue info banner appears instead:

> Configure rooms for each imported map to complete setup.

---

## Step 1 — Adding a vacuum

Click **Add Vacuum**. The card shows "Working…" while the service call runs.

The integration checks two things before registering:

- The vacuum entity must be present in the Home Assistant state machine. If it is not found, you see a blocked message asking you to ensure the Eufy integration is loaded and the device is online.
- If the vacuum is already managed, the result is "already done" and setup moves forward without doing anything twice.

On success, the step 1 badge fills with ✓ and a green "Vacuum registered." message appears. Step 2 unlocks immediately.

---

## Step 2 — Importing a map and configuring rooms

Import and room configuration are deliberately combined into one step. The reason: Eufy sometimes reports phantom rooms (rooms that do not correspond to real spaces on your floor plan). If rooms were saved to the integration automatically on import, those ghost rooms would be persisted. Instead, the wizard opens a room editor immediately after import so you can review and exclude any ghost rooms before anything is saved.

### Importing the active map

Click **Import Active Map**. The card shows "Working…" while the backend discovers the map.

The integration can only import the map that is currently active on the device — this is a hard limitation of the Eufy cloud API. If you have multiple maps (for example, one per floor), you need to make each map active on the device in turn and import them one at a time. Once at least one map has been imported, the button label changes to **Import Another Map**.

If the import is blocked, a message explains the reason. Common causes:

- The vacuum is powered off or has never completed a mapping run.
- Room segmentation is not configured in the Eufy app.

### Configuring rooms

After a successful import, the room editor opens automatically for the newly imported map. You can also open it manually for any map in the list by clicking **Configure Rooms** (or **Reconfigure** if the map has been configured before).

The editor shows a row for each room the integration discovered. Each row has two parts:

**Include/exclude toggle.** A button on the left shows ✓ if the room is included and ✕ if it is excluded. Click it to toggle. Excluded rooms are greyed out and their floor-type chips are hidden. Use this to deselect any ghost rooms — rooms that appear in the room list but do not correspond to real spaces.

**Floor type chips.** For each included room, a row of chips lets you pick one of eight floor types:

| Value | Label |
|---|---|
| `hardwood` | Hardwood |
| `laminate` | Laminate |
| `tile` | Tile |
| `marble` | Marble |
| `granite` | Granite |
| `concrete` | Concrete |
| `carpet_low_pile` | Low-Pile Carpet |
| `carpet_high_pile` | High-Pile Carpet |

All rooms start with Hardwood selected. Click a chip to change the selection for that room. The active chip is highlighted.

The floor type you set here drives the cleaning profile system — the integration uses it to determine appropriate suction and water settings for each room.

### Saving room configuration

When you are satisfied with the include/exclude choices and floor types, click **Save Room Configuration**. The button label changes to "Saving…" while the call runs. On success:

- The room editor closes.
- A ✓ Configured badge appears next to the map name in the list.
- The global status refreshes automatically.

If all imported maps are now configured, the ready banner appears and setup is complete.

---

## What the ready state looks like

When every imported map has been configured, the Setup tab shows:

- Step 1 badge: ✓
- Step 2 badge: ✓
- A green banner: "✓ Setup complete — switch to the Rooms tab to start cleaning."

The **Import Another Map** button remains available so you can add more maps later without going through the whole wizard again.

---

## Deleting a map and starting over

Each map row in step 2 has a **Delete** button. Clicking it opens a confirmation panel inline below the map name.

The confirmation panel shows:

- **Protection badges** — if the map has associated history or learning data, badge labels explain what will be lost.
- A warning message: "Delete [map name]? This removes all rooms, history, and learning data for this map from the integration. Eufy's upstream map is not affected."

For maps that require extra confirmation (those with a higher protection level), the panel also shows a text input. You must type the map's display name exactly before the **Delete Map** button becomes enabled.

Click **Delete Map** to proceed — the button shows "Deleting…" during the operation. Click **Cancel** to dismiss the panel without deleting anything.

After a successful delete, the map disappears from the list and the global status refreshes. You can then re-import the map from scratch by clicking **Import Another Map**.

> Note: deleting a map here only affects the integration's stored data. It does not delete anything from Eufy's servers or the Eufy app.
