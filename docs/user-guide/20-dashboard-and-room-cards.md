# 20 — Dashboard & Room cards

Most of this guide describes the **sidebar panel** — the full eufy-vacuum-command-center
that the integration adds to your Home Assistant sidebar. But you don't have to leave your
dashboard to control the vacuum. The integration also ships **three compact cards you drop
straight onto your own Lovelace dashboards**, next to your lights and thermostats:

- **Vacuum Agent — Dashboard Mode** (`vacuum-agent-dashboard`) — a compact, multi-room
  control card: pick rooms and their settings, run a saved profile or an app scene, see the
  map, and Start / Dock.
- **Eufy Room Card** (`eufy-room-card`) — one card per room: that room's settings and a
  quick Start button.
- **Vacuum Agent — Profile Card** (`vacuum-agent-profile-card`) — one card per saved run
  profile: shows exactly what that routine will do (its step sequence) and a **Run** button.

Both are served by the integration itself — there's **nothing to register**. No HACS
frontend repository, no Lovelace *Resources* entry. Once the integration is installed the
cards are available everywhere, even on a dashboard that never opens the sidebar panel.

## Adding a card

In any dashboard, click **Edit dashboard → + Add card**, then search for **"Vacuum Agent"**
(the dashboard card), **"Eufy Room"** (the room card), or **"Vacuum Agent Profile"** (the
profile card). Each card has a visual editor — no YAML required.

Prefer YAML? The minimal configs are:

```yaml
# Multi-room dashboard card
type: custom:vacuum-agent-dashboard
vacuum_entity_id: vacuum.alfred   # required — which vacuum this card controls
```

```yaml
# Single-room card
type: custom:eufy-room-card
vacuum_entity_id: vacuum.alfred   # required
room_id: 5                        # required — which room (pick it in the editor)
```

```yaml
# Single-profile "inspect & run" card
type: custom:vacuum-agent-profile-card
vacuum_entity_id: vacuum.alfred   # required
map_id: "6"                       # required — which map the profile belongs to
profile_id: rp_20260709T065541    # required — pick it in the editor
```

## The Dashboard Mode card

A compact stack you can keep on a wall tablet or your phone dashboard. Top to bottom:

- **Header** — the vacuum's name, status, and battery, plus a **language globe**
  (see [Language](19-language.md)).
- **Map** — the same live/render map as the panel, in a collapsible section (see
  [The map](#the-map) below). Tap a room on the map to include it in the next run.
- **Rooms** — a collapsing list. Tap a room's row to expand it and set **that room's** own
  cleaning mode, suction, water, cleaning path, and passes. The checkbox (or the room name)
  includes the room in the next run.
- **Your profiles** — a dropdown of your saved run profiles, if you have any. A profile
  can be a plain room queue **or** a stepped run that docks to recharge (or waits) partway
  through and then keeps cleaning — either way you just pick it and press **Start**, and the
  card runs the whole sequence. If the vacuum returns to the dock mid-run, that's the charge
  or wait stop doing its job; it will carry on once it's ready. (You build stepped profiles
  in the sidebar panel — see [Profiles](10-profiles.md).)
- **App scenes** — *Eufy only* — a dropdown of the scenes from the Eufy app. (Roborock has
  no equivalent, so this section simply doesn't appear.)
- **Footer** — **Start** and **Dock**.

You can hide any section you don't want from the card editor (or in YAML):

```yaml
type: custom:vacuum-agent-dashboard
vacuum_entity_id: vacuum.alfred
title: Downstairs vacuum     # optional — defaults to the vacuum's name
show_map: true               # default true
show_profiles: true          # default true (hidden if your vacuum has no room profiles)
show_scenes: true            # default true (Eufy only; auto-hidden otherwise)
show_dock: true              # default true
```

!!! info "Build it, then Start it"
    Choosing rooms, settings, a profile, or a scene is **inert** — nothing reaches the
    vacuum until you press **Start**. So you can set up a run without it taking off
    mid-tap. A profile or an app scene is a *complete* pre-built run, so picking one
    greys out the manual room pickers (and vice-versa) — exactly one run source is ever
    active. **Dock** is always independent.

!!! note "App scenes start immediately on the vacuum"
    An Eufy app scene runs the moment you Start it — the card never triggers it just from
    selecting it in the dropdown.

## The Room card

Place one per room (a nice grid on a "Cleaning" view). Pick the vacuum and the room in the
editor; the card then shows that room's settings chips and a **Start** button. The room
name at the top is a button:

> **Click the room name to select it for cleaning — this clears all other rooms in the
> queue.** (The same note appears on the card.)

So a Room card always starts a **single-room** clean of its own room. Edit a setting and the
**Save** button appears; **Start** also saves any pending edits before it runs.

## The Profile card

A run profile can grow into a whole routine — room groups, per-room settings, a charge-to-%
stop partway through, wait steps, strict ordering. Once it does, the profile's *name* alone
may not tell you what pressing it will do. The **Profile card** puts one saved profile on your
dashboard: its name, how many rooms, whether it's exposed as a button, and a read-only **Runs
As** list of every step in order — ⏱ waits, cleans (with each group's mode), ⚡ charge stops —
then a single **Run** button.

Pick the vacuum, map, and profile in the editor (three dropdowns, no YAML). It's
**inspect-and-run only** — there's no save, edit, or delete here; you build and manage profiles
in the sidebar panel (see [Profiles](10-profiles.md)). Pressing **Run** applies the profile and
starts the whole sequence, charge stops and all, exactly like starting it from the panel.

Unlike the Dashboard and Room cards, this one isn't offered automatically when you add a vacuum
entity — it needs you to choose *which* profile — so add it yourself from **+ Add card** and
search **"Vacuum Agent Profile"**.

## The map

Both cards (and the sidebar panel) share the same map. A few things you can do with it:

- **Collapse it** — click the **Map** header (the chevron) to fold the map away and keep the
  card compact. Click again to bring it back.
- **Pan & zoom** — drag to pan, use the **+ / −** buttons (or the mouse wheel) to zoom, and
  the **⤢** button to fit the whole map. **Your pan and zoom are remembered between
  reloads**, per device — so the map stays where you left it. (Hit **⤢** to reset.)
- **Rotate** — the **↻** button rotates the map to match how your home is actually oriented.
- **Layers & mascot** — open the layers panel to toggle overlays (rooms, robot, dock, paths,
  no-go zones, …) and to pick / scale / hide the map [companion](18-furnished-render.md).
- **Move room names** — drag a room's **name label** to reposition it anywhere on the map
  (handy when a name sits awkwardly over a doorway or another room). The position is saved
  on your device. To put a name back, **drag it back onto its room's centre** and it returns
  to automatic placement.

!!! tip "Each card keeps its own map view"
    Pan/zoom and moved room names are remembered separately for the sidebar panel and for a
    dashboard card, and per device — so a tight zoom on your phone's card doesn't disturb the
    panel on your desktop.

## Panel or cards — which?

They're complementary, and you can use both:

- The **sidebar panel** is the full workspace — the learning system, review wizards, the
  theme editor, maintenance, metrics, setup.
- The **cards** are for *driving* the vacuum from where you already are — a quick room
  pick + Start without leaving your dashboard.

Everything the cards show comes from the same backend, so a run you start from a card shows
up in the panel's history and learning exactly like a panel-started run.
