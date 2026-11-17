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

All three are served by the integration itself — there's **nothing to register**. No HACS
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
  cleaning mode, suction, cleaning path, and passes (plus water level and edge mopping, on
  rooms whose cleaning mode is a mop mode and that aren't marked carpet). The checkbox (or
  the room name) includes the room in the next run. With the Rooms list expanded, on brands
  that path-optimize and ignore your order (Roborock) a **Force this exact order** chip
  appears once two or more rooms are selected — once enabled it relabels to
  **Strict order: ON**.
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
show_companion: true         # default true — the companion animal on the map, and its
                             # row of controls. Set false to remove both completely.
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
dashboard: its name, how many rooms, whether it's exposed as a button, and a read-only
**Runs in this order** list of every step — ⏱ waits, cleans (with each group's mode),
⚡ charge stops — then a single **Run** button.

Pick the vacuum, map, and profile in the editor (three dropdowns, no YAML). It's
**inspect-and-run only** — there's no save, edit, or delete here; you build and manage profiles
in the sidebar panel (see [Profiles](10-profiles.md)). Pressing **Run** applies the profile and
starts the whole sequence, charge stops and all, exactly like starting it from the panel.

Unlike the Dashboard and Room cards, this one isn't offered automatically when you add a vacuum
entity — it needs you to choose *which* profile — so add it yourself from **+ Add card** and
search **"Vacuum Agent Profile"**.

## The map

The Dashboard card and the sidebar panel share the same map (the Room and Profile cards
don't carry one). A few things you can do with it:

- **Collapse it** — click the **Map** header (the chevron) to fold the map away and keep the
  card compact. Click again to bring it back.
- **Pan & zoom** — drag to pan, use the **+ / −** buttons (or the mouse wheel) to zoom, and
  the **⤢** button to fit the whole map. **Your pan and zoom are remembered between
  reloads**, per device — so the map stays where you left it. (Hit **⤢** to reset.)
- **Rotate** — the **↻** button rotates the map to match how your home is actually oriented.
- **Zone clean** — if your vacuum brand supports it, you can draw zone boxes right on the
  card's map and clean just those areas — see [Zones](04a-zones.md). (The zone panel stacks
  under the map here, rather than sitting in a side column like it does in the panel.)
- **Layers & mascot** — open the layers panel to toggle overlays (rooms, robot, dock, paths,
  no-go zones, …) and to pick / scale / hide the map
  [companion](16-making-your-own-maps.md#the-mascot-and-floor-textures).
- **Move room names** — drag a room's **name label** to reposition it anywhere on the map
  (handy when a name sits awkwardly over a doorway or another room). The position is saved
  on your device. To put a name back, **drag it back onto its room's centre** and it returns
  to automatic placement.

!!! tip "The panel and cards keep separate map views"
    Pan/zoom is remembered separately for the sidebar panel and for a dashboard card, and
    per device — so a tight zoom on your phone's card doesn't disturb the panel on your
    desktop. (Two dashboard cards for the same vacuum on the same device share one saved
    view — the split is panel-vs-card, not per card.) Moved room names are per device too,
    but shared between the panel and the card (they're stored per vacuum and map, not per
    view).

## Finding the theme editor from a card

Each card's editor has an **Open the theme editor** button. It takes you to that vacuum's
Vacuum Agent panel, straight to the **Theme** tab, where the colours, spacing and shadows
the card reads are set.

The panel is per vacuum, so the button only appears once you have chosen one — and only
when that vacuum actually has a panel. Opening it leaves the card-edit dialog, so save any
card changes first.

## Styling the cards from a Home Assistant theme

The cards already follow your Home Assistant theme. They don't carry a fixed palette — they
read **twelve** of Home Assistant's own theme variables and compute everything else from
them, so a card picks up a theme you already have without being told about it.

Set any of these in your HA theme and the cards follow:

| Set this in your theme | and it moves |
|---|---|
| `card-background-color` | the card surface, and every panel, chip, well and raised block derived from it |
| `primary-text-color` | body text, headings, **and every tinted overlay** — borders, chips, hovers, controls |
| `secondary-text-color` | captions, hints, secondary labels |
| `accent-color` | the accent: active chips, focus rings, primary buttons |
| `success-color` | "good" states (charged, complete) |
| `warning-color` | "attention" states |
| `error-color` | "problem" states (faults, unavailable) |
| `ha-card-border-radius` | the card's corner radius |
| `ha-card-background` | the card's own fill |
| `ha-card-border-color` | the card's edge, and every other border derived from it |
| `ha-card-border-width` | the thickness of the card's edge |
| `ha-card-box-shadow` | the card's shadow |

The four `ha-card-…` entries below the radius are the ones Home Assistant's own cards use,
so a theme written for built-in cards styles these without knowing they exist.

`primary-text-color` is the one worth knowing about. It is not just the text — the cards
derive every translucent overlay from it, so it inverts the whole card with your theme:
near-white ink on a dark theme, near-black on a light one. That is why a light HA theme
produces a readable card rather than white-on-white.

### Overriding the card surface on its own

`card-background-color` also moves the panels and wells derived from it. If you want to
change **only** the card's own background, there is one dedicated variable:

```yaml
my-theme:
  evcc-surface-card-override: "rgba(50, 50, 50, 0.65)"
```

It accepts any colour value, translucency included. Leave it unset and the card surface
derives from `card-background-color` exactly as before.

!!! note "Why most other `evcc-` names don't work"

    Most of the cards' internal tokens are named `--evcc-…`, and setting one of those in a
    theme has no effect — `evcc-surface-card`, for instance, is ignored. That is not an
    oversight, it is the cost of the cards following your theme at all: those names are
    *computed* from the variables above, and in CSS a value an element computes for itself
    always beats one it inherits. So they are outputs of the theming system, not inputs
    to it.

    **The card frame tokens in the next section are the exception**, and they are
    deliberately the exception: they are computed from nothing, so there is no computed
    value to beat an inherited one, and a theme can set them.

### Styling the card frame from YAML

The theme editor is the easy path and needs no YAML. But everything it sets for the card
frame can be set from `themes.yaml` too, which is the normal Home Assistant way and is
there for people who build their dashboards that way.

These are **inputs**, not computed values — set one and the card follows:

```yaml
my-theme:
  # applies to all three cards
  evcc-card-frame-background: "#1b1f24"
  evcc-card-frame-border-color: "rgba(255,255,255,0.14)"
  evcc-card-frame-border-width: "2px"
  evcc-card-frame-shadow: "0 2px 8px rgba(0,0,0,0.4)"

  # and any one card on its own — these win over the shared names above
  evcc-card-room-frame-background: "#232830"
  evcc-card-dashboard-frame-border-width: "0px"
  evcc-card-profile-frame-shadow: "none"
```

Swap `room`, `dashboard` or `profile` into `evcc-card-<card>-<property>` for the per-card
form — so `evcc-card-frame-shadow` becomes `evcc-card-profile-frame-shadow`.

#### Every control, and which cards read it

The name in the first column is the shared one. Prefix the property with a card id for the
per-card form. A card only reads the controls it has a use for, and setting one it does not
read simply does nothing.

| Set this | The control is called | Value | Room | Dashboard Mode | Profile |
|---|---|---|---|---|---|
| `evcc-card-frame-background` | Frame Background | any colour | ✅ | ✅ | ✅ |
| `evcc-card-frame-border-color` | Frame Border Colour | any colour | ✅ | ✅ | ✅ |
| `evcc-card-frame-border-width` | Frame Border Width | a length, 0–8px | ✅ | ✅ | ✅ |
| `evcc-card-frame-shadow` | Frame Shadow | a CSS `box-shadow`, or `none` | ✅ | ✅ | ✅ |
| `evcc-card-action-glow` | Action Glow | a CSS `box-shadow`, or `none` | ✅ | ✅ | ✅ |
| `evcc-card-font-scale` | Text Scale | a number, 0.5–2 | ✅ | ✅ | ✅ |
| `evcc-card-header-padding` | Header Padding | 1–4 CSS lengths | ✅ | ✅ | — |
| `evcc-card-field-gap` | Field Gap | a length, 0–16px | ✅ | ✅ | — |
| `evcc-card-row-padding` | Row Padding | 1–4 CSS lengths | — | ✅ | — |
| `evcc-card-section-padding` | Section Padding | 1–4 CSS lengths | — | ✅ | — |

The Profile card has no padding or gap controls because it has no rows, sections or header
to pad; Row and Section Padding are Dashboard Mode only, as the only card with room rows
and sections.

A few notes on values:

- **Lengths** take the usual CSS forms — `12px`, `0.75rem`, or several separated by spaces
  the way CSS padding works (`14px 16px 12px`). In the editor a bare number gains `px`
  when you leave the field; in YAML write the unit yourself.
- **Text Scale** multiplies every font size in the card at once rather than setting one, so
  the proportions between a heading, a room name and a chip hold at any size.
- **Shadows** take a full CSS `box-shadow`, including a comma-separated stack of layers.
  `none` is a value; leaving the name out entirely is different — that inherits.
- **Four `ha-card-*` variables** reach the frame as well, listed in the table further up.
  They sit below these names, so an `evcc-card-…` value wins over them.

```yaml
my-theme:
  # all three cards
  evcc-card-frame-background: "#1b1f24"
  evcc-card-frame-border-width: "2px"
  evcc-card-font-scale: "1.1"

  # the Dashboard Mode card alone
  evcc-card-dashboard-row-padding: "10px 14px"
  evcc-card-dashboard-frame-shadow: "0 2px 8px rgba(0,0,0,0.4), inset 0 0 0 1px rgba(255,255,255,0.06)"

  # the Profile card alone
  evcc-card-profile-frame-border-width: "0px"
```

**Which wins, if more than one is set:**

1. **`theme_vars` on the card itself** — see the next section. Set directly on one card, so
   it beats everything else, including the Vacuum Agent theme.
2. **The Vacuum Agent theme**, on a card with *Use the Vacuum Agent theme* ticked.
3. **The per-card name**, `evcc-card-room-…` — beats the shared name.
4. **The shared name**, `evcc-card-frame-…` — beats the Home Assistant variable.
5. **The Home Assistant variable**, `ha-card-background` and friends from the table above.
6. The shipped default.

So a YAML-only setup gets rungs 3–6 and behaves exactly as you would expect; ticking the
Vacuum Agent theme on a card hands that card to the theme editor — unless that card also
carries `theme_vars`, which stays on top either way.

### Styling one card on its own — `theme_vars`

The names above are theme-wide: set `evcc-card-room-frame-background` and *every* room card
moves. To style **one card** — two room cards side by side in different colours — put the
values on that card's own config:

```yaml
type: custom:eufy-room-card
vacuum_entity_id: vacuum.alfred
room_id: 3
theme_vars:
  evcc-card-frame-background: "#232830"
  evcc-card-frame-border-color: "#3d4450"
  evcc-accent: "#e0a060"
```

**Any token the theme editor exposes works here** — not just the card frame. The names are
the same ones the editor shows, with or without the leading `--`, so
`evcc-accent` and `--evcc-accent` both work.

A few things worth knowing:

- It beats the Vacuum Agent theme on that card. The theme still supplies everything
  `theme_vars` does not name, so this overrides a theme rather than replacing it.
- Delete a key and the card goes back to whatever it would otherwise have shown — no
  reload needed.
- Only `--evcc-…` names are accepted. Anything else is ignored, so this cannot be used to
  set arbitrary CSS on the card.
- On the Dashboard Mode card it reaches the embedded map too, so the map follows.

!!! tip "You don't have to choose"

    The theme editor and `theme_vars` work together: build the palette in the editor, tick
    *Use the Vacuum Agent theme* on the cards, and use `theme_vars` only where one card
    needs to differ.

### Or carry the Vacuum Agent theme across

Each card's editor has a **Use the Vacuum Agent theme** checkbox, off by default. Ticked,
that card wears the palette, opacities and font from the theme set for its vacuum instead
of your Home Assistant theme. It is per card, so you can mix — a themed room card beside a
Dashboard Mode card that still matches your dashboard. Unticking it hands the card straight
back to the HA theme.

**A card follows the vacuum's saved theme, not a per-device pin.** In the panel you can pin
a theme to *this browser only* — that pin is stored locally and does not travel. Cards do
not read it. A ticked card always wears whichever theme is **saved** for its vacuum, so the
same dashboard looks the same on your phone and your laptop, while the panel beside it may
not. That is deliberate: a card lives on a dashboard other people see, and a per-browser
preference is not something it should inherit.

The practical consequence is worth knowing if you are mid-edit. Pinning a different theme
in the panel to try it out changes the panel and leaves every ticked card on the saved one,
so the two will disagree until you save. Within the theme editor the cards do follow your
unsaved edits live — it is only the per-device *pin* they ignore.

## Panel or cards — which?

They're complementary, and you can use both:

- The **sidebar panel** is the full workspace — the learning system, review wizards, the
  theme editor, maintenance, metrics, setup.
- The **cards** are for *driving* the vacuum from where you already are — a quick room
  pick + Start without leaving your dashboard.

Everything the cards show comes from the same backend, so a run you start from a card shows
up in the panel's history and learning exactly like a panel-started run.
