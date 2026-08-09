# 11 — Setup

The Setup tab walks you through getting your vacuum registered with the
integration and configuring its rooms. After the initial pass it stays
useful: whenever the vacuum reports a new room (you added a room in the
Eufy app, or the firmware redrew the map) or a configured room
disappears (you removed a room, the vacuum lost track of it), the Setup
tab surfaces those changes for you to review.

## Accessing the Setup tab

Open the Lovelace card for your vacuum. The tab bar along the top
includes a **Setup** item. Click it to open the wizard. The card shows
a **Vacuum Setup** heading and a brief description.

If the card has never loaded setup status from the integration, click
the **Check Status** button at the bottom of the view. After the first
successful fetch, the button label changes to **Refresh** and stays
available so you can re-sync at any time.

---

## How the setup steps work

The integration declares which setup steps apply to your vacuum. For
Eufy this is three steps: **Add Vacuum**, **Import Active Map**, and
**Configure Rooms**. Each step has a numbered badge that fills with
**✓** once that step is complete. The currently-active step is the
first one without a checkmark — its body is fully visible with the
action button enabled; later steps are visible but dimmed until their
prerequisites are met.

When every step has a ✓ and there is no room drift to review, a green
banner appears below the steps:

> ✓ Setup complete — switch to the Rooms tab to start cleaning.

The **Import Another Map** button (in the import step) and the
**Reconfigure** button (per map in the configure step) remain
available after that — you don't need to redo setup to add more maps
or revisit room settings.

---

## Step 1 — Add Vacuum

Click **Add Vacuum**. The card shows "Working…" while the service
call runs.

The integration checks two things before registering:

- The vacuum entity must be present in Home Assistant. If it is not
  found, you see a blocked message asking you to make sure the vacuum
  integration is loaded and the device is online.
- If the vacuum is already managed, the result is "already done" and
  setup moves forward without registering twice.

On success the step 1 badge fills with **✓** and step 2 unlocks.

---

## Step 2 — Import Active Map *(Eufy only)*

This step exists because the Eufy cloud API only surfaces one map at a
time. If you have several floor plans, you have to make each one
active on the device in turn and import them one at a time. Other
vacuum brands that expose all maps upfront don't need this step — the
adapter for those brands skips it.

Click **Import Active Map**. The card shows "Working…" while the
backend discovers the map. Once at least one map has been imported,
the button label changes to **Import Another Map**.

If the import is blocked, the message explains why. Common causes:

- The vacuum is powered off or has never completed a mapping run.
- Room segmentation is not configured in your vacuum app.

The step badge fills with **✓** as soon as one map has been imported.
You can come back later and import additional maps; the step stays
checked.

!!! tip "Stuck on this step? Download diagnostics"

    If the import keeps failing — most commonly **"No active map detected"** —
    download a diagnostics report and attach it when you ask for help:
    **Settings → Devices & Services → Vacuum Agent → ⋮ → Download diagnostics**.
    It shows how each entity resolves — including whether the active-map sensor
    actually has a value — which usually pinpoints the cause at a glance.
    Credentials are redacted.

---

## Step 3 — Configure Rooms

This is where you decide which rooms the integration should manage,
exclude any phantom rooms the vacuum reports, and set each room's
floor type. Phantom rooms are real: Eufy occasionally reports rooms
that do not correspond to real spaces on your floor plan, and they
need to be rejected here so they don't become managed entities.

Each imported map gets its own row. Click **Configure Rooms** to open
the editor for that map. If a map has been configured before, the
button reads **Reconfigure** and a "✓ Configured" badge appears next
to the map name.

### The room editor

The editor shows a row per discovered room with two controls:

**Include / exclude toggle.** A button on the left shows ✓ if the
room is included and ✕ if it is excluded. Click to toggle. Excluded
rooms are greyed out and their floor-type chips are hidden. Use this
to deselect any phantom rooms — they will never be saved to the
integration if excluded.

**Floor type chips.** For each included room, a row of chips lets you
pick one of eight floor types:

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

All rooms start with Hardwood. Click a chip to change the selection
for that room — the active chip is highlighted. Floor type drives the
cleaning-profile system, so it's worth getting right.

When you're happy with the include/exclude choices and floor types,
click **Save Room Configuration**. On success the editor closes, the
"✓ Configured" badge appears, and global status refreshes.

You can't save a map with *every* room excluded — the save button
disables and the editor explains: "Select at least one room to save. To
remove this map entirely, use Delete Map instead."

---

## Rename this vacuum's sidebar entry

The Setup tab has a **Panel name** field that renames this vacuum's
sidebar entry — type a new name and click **Rename**. The backend
re-registers the panel right away; refresh the page to see the new name
in the sidebar (no restart required). Leave the field blank to reset to
the default name, **Vacuum Agent**.

This matters most when you run more than one vacuum: each gets its own
sidebar entry, and giving them distinct names (for example "Upstairs"
and "Downstairs") makes it obvious which panel you're opening.

---

## Live map camera

The Setup tab has a **Live map camera** dropdown that lets you pick a
camera (or image) entity to use as this vacuum's live map backdrop —
for example the `camera.<device>_map` entity exposed by
[eufy-clean](https://github.com/jeppesens/eufy-clean) v1.11.1 or later,
which renders the robot's live map and refreshes it every couple of seconds. The
field only appears when at least one camera or image entity exists in
Home Assistant, and your choice saves immediately on change — no button
to press.

Leave it on **Auto (adapter default)** to let the integration resolve a
sensibly-named live-map entity on its own; pick an entity explicitly
only when your vacuum entity was renamed and the automatic match no
longer lines up.

Selecting a live map here is the first step; for how to draw and link
tap-selectable rooms on top of it, see
[Making your own maps](16-making-your-own-maps.md), which covers the
"Live map" source and the room-label toggle.

---

## Room drift — the Setup tab after initial setup

The Setup tab does not become useless once every step has its ✓.
The integration runs room discovery automatically in the background
(every time the vacuum returns to its dock, every time the active map
changes, after a config reload, and once every six hours as a safety
net). If discovery
detects a difference between what the vacuum currently reports and
what you've configured, a **room drift** panel appears inside the
Configure Rooms step.

The phantom-room and multi-pass confirmation behavior described below
is specific to Eufy's CV-based mapping. Brands that report only the
rooms you deliberately named in their app (Roborock) surface a newly
named room immediately and have no phantom-room problem, so the
confirmation window is an Eufy-only consideration.

The panel can show up to three categories of difference:

### New rooms discovered

Rooms the vacuum reports that you haven't configured yet. Each row
shows the room name, its map, and two affordances:

- **Configure** (use the matching map's Configure / Reconfigure
  button above to include it with the right floor type), or
- **Reject as phantom**, which suppresses the room *on that map*. Once
  rejected, it never appears in this list again for that map, even if
  the vacuum keeps reporting it. Use this for ghost rooms the firmware
  occasionally invents.

Rejections are stored **per map** — Eufy reissues room IDs from scratch
on every map, so ID 3 on one floor is a different physical room from
ID 3 on another. Rejecting a ghost on one floor never hides a real room
on a different floor.

If you reject the wrong room, there's an escape hatch: call the
**`eufy_vacuum.setup_unreject_rooms`** service (Developer Tools →
Actions) with the vacuum and room IDs. The room doesn't reappear
immediately — it resurfaces on the next discovery pass that sees it,
through the normal confirmation cadence. It clears the rejection on
the given map, and also clears any older rejection recorded before
rejections were per-map (those applied to every map, so a stale entry
could still be blocking a real room on another floor). The service
takes an optional **Map ID**: leave it blank to use the current active
map; if the active map can't be determined and the vacuum has more
than one map, the call is refused rather than guessing, since a bare
room ID doesn't identify a room across maps.

### Rooms no longer reported

Configured rooms that the vacuum has stopped reporting for several
consecutive discovery passes (the default is three; this matches a
typical day or two of normal use). These rooms have been **confirmed
removed** — the framework waited through several transient-glitch
windows before flagging them. To drop them from the integration,
reconfigure the matching map and deselect them.

### Temporarily missing

Configured rooms that are missing from the most recent discovery
passes but haven't yet hit the "confirmed removed" threshold. These
might be a transient API glitch and might come back on their own — the
framework doesn't surface them as a hard removal yet. Two paths:

- **Wait.** This is the default. If the room reappears, the
  transient-missing entry vanishes silently. If it stays missing, it
  promotes to **Rooms no longer reported** after a few more passes.
- **Force remove now.** If you know the room is permanently gone
  (you renovated, you reset the vacuum), this button bypasses the
  confirmation window and immediately moves the entry into "Rooms no
  longer reported." The room stays in the integration's stored data
  with its history intact; only the drift signal flips.

---

## Renumbered and renamed rooms

Re-mapping can shuffle the vacuum's room numbering or names. When the
integration detects that the current map's rooms no longer line up with
what you saved, a review panel appears inside the Configure Rooms step
with up to two groups:

- **Rooms renumbered** — the vacuum reassigned these room numbers after
  re-mapping. Informational only: your saved settings follow the rooms
  automatically, no action needed. Each row shows the old → new number.
- **Renamed rooms** — same room number, different name. Either you
  renamed the room in the app, or re-mapping reused that number for a
  different space. The integration can't tell those apart
  automatically, so review the list before updating.

The decision is per map, not per room. **Update saved rooms** migrates
your saved settings onto the new room identities; **Dismiss** leaves
everything as it is. Dismissing is not permanent — the same review can
resurface after a later discovery pass. After a successful update the
panel reports how many rooms were updated, and names any room that was
removed from the map and had its settings discarded.

If the map changes while you're reviewing, the panel refreshes itself
and says so. If that automatic refresh fails, a **Re-discover rooms**
button appears so you can retry manually.

---

## Room settings are repaired automatically

A per-room setting is only useful if the word it is stored under is one your vacuum actually accepts. A value the robot doesn't recognise isn't rejected loudly — it is discarded, and the setting quietly does nothing.

So the integration checks its own work. Shortly after Home Assistant starts, it compares every stored room against the vocabulary your vacuum's adapter declares, and repairs anything that doesn't line up. There is nothing to click and no prompt: it runs on its own, once, and records that it is done.

Two things can happen to a room:

- **A setting your brand doesn't have is dropped.** Nothing is lost — the field was never going to reach the robot. (For example, Roborock rooms that had picked up a Eufy-shaped Cleaning Path value.)
- **A value outside your brand's option list is replaced.** Where the brand declares what a retired name used to mean, the room keeps that meaning: a Eufy room stored with the old **Standard** cleaning path becomes **Narrow**, the middle density — not the fastest setting. Where there is no such declaration, the room falls back to your brand's default for that field. If neither is available, the room is left exactly as it was and a warning goes to the Home Assistant log rather than a guess going to the robot.

Everything else about the room — its name, floor type, queue position, history, and learning data — is untouched.

!!! note "If your vacuum wasn't ready yet"

    The repair can only judge a room against a vacuum whose own integration has finished loading. On a cold start that isn't always true yet. When it can't evaluate every managed vacuum, it deliberately does **not** mark itself finished — it leaves the rooms alone and tries again on the next start, so nothing is silently skipped forever.

---

## Adding another vacuum

Below the setup steps, an **Add another vacuum** section lists any
`vacuum.*` entities in Home Assistant that aren't managed yet, each
with an **Add** button. Adding one registers it with the integration
and wires up its own sidebar panel — each panel's setup steps only ever
manage that panel's own vacuum. When every vacuum is already managed,
the section says so.

---

## Deleting a map

Each map row has a **Delete** button. Clicking it opens a confirmation
panel inline below the map name.

The panel shows:

- **Protection badges** — if the map has associated history or
  learning data, the badges explain what will be lost.
- A warning message: "Delete [map name]? This removes all rooms,
  history, and learning data for this map from the integration. The
  upstream cloud map is not affected."

For maps with significant history (higher protection level), the
panel also shows a text input — you must type the map's display name
exactly before the **Delete Map** button enables. This is intentional
friction; map deletes lose a lot of accumulated data.

Click **Delete Map** to proceed (button reads "Deleting…" during the
operation) or **Cancel** to dismiss. After a successful delete, the
map disappears from the list and the global status refreshes. You can
then re-import the map from scratch.

> Note: deleting a map here only affects the integration's stored
> data. It does not delete anything from the vacuum's cloud servers
> or the Eufy app.

---

## When to come back to the Setup tab

Day-to-day cleaning happens on the **Rooms tab**. You'll come back to
Setup in three situations:

1. **You imported a new map** and want to configure its rooms.
2. **You added a room in the Eufy app** (or the firmware redrew the
   map and surfaced a new segment). The drift panel surfaces this as
   a "new room discovered" entry within a day or so of normal use.
3. **You removed a room** and want to clean it up from the
   integration. The drift panel surfaces this as "rooms no longer
   reported" after the confirmation window. Or use **Force remove
   now** if you don't want to wait.

The drift detection is the reason the Setup tab matters beyond the
initial wizard pass — it keeps the integration in sync with what your
vacuum actually sees over time, without requiring you to remember to
re-run setup after every change.

---

## Removing the integration

Go to **Settings → Devices & Services**, find **Vacuum Agent**,
and delete it. No extra steps are required — all integration data is
stored inside Home Assistant and is removed with the entry.

Note: this integration sits on top of whichever upstream integration
provides the underlying `vacuum.*` entity — for Eufy that's
[eufy-clean](https://github.com/jeppesens/eufy-clean); for Roborock
it's Home Assistant's built-in Roborock integration. Removing Vacuum
Agent does not remove that underlying integration; remove it separately
if you no longer need it.
