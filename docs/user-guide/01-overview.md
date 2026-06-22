# 01 — Overview

## What is this?

eufy_vacuum is a Home Assistant custom integration paired with a Lovelace card called **eufy-vacuum-command-center**. Together they give you room-level control over your robot vacuum directly from your HA dashboard. It's a multi-brand integration — it supports **Eufy** and **Roborock** vacuums today through an adapter system, and is built to extend to other brands.

The integration has been tested on the **Eufy X10 Pro Omni** and the **Roborock S6**. Other models of either brand may work but aren't officially supported. Because capabilities differ by brand and model, some tabs and controls described in this guide appear, are hidden, or read differently depending on your vacuum — those differences are called out inline as you go.

## What does it add beyond the stock Eufy integration?

A stock vacuum integration in Home Assistant lets you start and stop your vacuum as a single unit. eufy_vacuum goes further:

- **Room-level control.** You choose exactly which rooms to clean before each run, and in what order.
- **Per-room cleaning settings.** Each room can have its own cleaning mode (vacuum, mop, or both), suction level, water level, cleaning path, number of passes, and edge mopping toggle.
- **Cleaning profiles.** You can save a named set of room settings as a reusable profile and apply it to any room in one tap. Built-in profiles are read-only; you can create as many custom profiles as you like.
- **Run profiles.** You can save an entire room selection — which rooms are included, in what order, with what settings — as a named run profile and start it again with a single button.
- **Queue management.** The card shows you which rooms are queued, their estimated cleaning times, and your planned run order. You can reorder rooms by dragging or by using a move button.
- **Learning system.** After each run the integration records how long the vacuum spent in each room. Over time it builds per-room timing estimates that get more accurate the more you use it. The card displays a confidence indicator (Reliable / Learning / Uncertain) for each room's estimate.
- **Incomplete run recovery.** If a run ends before all rooms are finished, the card shows a banner letting you queue only the missed rooms for a follow-up run.
- **Trouble room indicators.** The card tracks rooms the vacuum has repeatedly failed to clean and flags them so you can investigate.
- **Metrics and learning review.** Dedicated panels let you browse historical run data and review what the system has learned.
- **Theming.** The card's colors, typography, and layout tokens are fully customizable from within the card itself — including a built-in **Colorblind Safe** theme that keeps status colors distinguishable for color-vision deficiency (see [Accessibility](14-accessibility.md)).

## Requirements

- Home Assistant with your Eufy vacuum already set up as a `vacuum` entity.
- The eufy_vacuum custom component installed in `custom_components/eufy_vacuum`.
- The eufy-vacuum-command-center Lovelace card installed and added to a dashboard with your `vacuum_entity_id` set in the card config.

At minimum your card config needs:

```yaml
type: custom:eufy-vacuum-command-center
vacuum_entity_id: vacuum.your_vacuum
```

## The card at a glance

The card has a header strip at the top showing your vacuum's name, two status pills, and the current battery level:

- **Vacuum Status** — what the vacuum entity itself reports (Docked, Cleaning, Returning, Paused, etc.).
- **Dock Status** — what the dock entity reports (Idle, Washing, Drying, Emptying, Charging, etc.). Only shown when your model exposes a dock status.

Both labels are formatted server-side, so any vocabulary the integration knows about is rendered consistently. A colored dot next to each one mirrors the state at a glance — green for active work, amber for transitional states, red for errors, muted grey for idle/offline.

Below the header is a navigation bar with tabs that switch between panels:

| Tab | What it does |
|---|---|
| **Rooms** | Select rooms, adjust their settings, and start a cleaning run. This is the main day-to-day panel. |
| **Maintenance** | Track consumable lifespans (brushes, filter, etc.) and trigger upkeep actions. |
| **Base Station** | Control base station functions — wash mop, dry mop, empty dust bin — and configure pause timeout settings. |
| **Metrics** | Browse historical run data with filters by room, profile, and status. |
| **Learning Review** | Review what the learning system has recorded about each room's cleaning history. |
| **Room Rules** | Set up automation rules that apply to rooms (for example, automatically adjusting settings based on time of day or other conditions). |
| **Theme** | Customize the card's visual appearance — colors, token values, and saved theme presets. |
| **Map Bounds** | Review and adjust the boundary boxes the integration uses to track which room the vacuum is in. |
| **Setup** | Add vacuums and import maps into the integration. |

!!! info "Tabs adapt to your vacuum"
    The navigation only shows tabs your vacuum supports. **Base Station** and **Map Bounds** appear on models with the matching hardware/feature (both present on Eufy) and are hidden on models without them — for example the dockless, natively-tracked **Roborock S6** shows neither tab.

Uploading a map image and linking the vacuum's map segments to your rooms happen on a separate **Map Config** screen rather than a top-nav tab. You reach it from the **Configure** button in the Rooms map view. See [Making your own maps](16-making-your-own-maps.md) for the step-by-step walkthrough, or [Map configuration](../advanced/08-map-configuration.md) for the technical reference.

On a narrow screen (under 600px) the navigation collapses into a bottom tab bar with shortened labels — **Rooms**, **Upkeep** (Maintenance), **Dock** (Base Station), and **Stats** (Metrics) — plus a **More** overflow sheet holding Learning Review, Room Rules, Theme, Map Config, Map Bounds, and Setup.

The card opens on the **Rooms** tab the first time you load it. After that it remembers whichever tab you were on last per vacuum, so refreshing the browser doesn't lose your place.

## Small conveniences

A few interaction details that aren't tied to any one tab:

- **Toast feedback.** Save / reset / dock-action / delete operations surface a short status pill near the bottom of the card. Successful actions get a green stripe, failures a red one, informational events a blue one. Each one auto-dismisses after a few seconds; click the ✕ to drop it sooner.
- **ESC closes modals.** Any open modal (room editor, room access editor, run-estimate detail, maintenance item, order picker) closes on Escape.
- **Two-tap destructive actions.** Cancel Run, Clear Queue, and Delete on a map image variant all require two clicks. The first click flips the button to a pulsing "Confirm" state; the second click commits. The confirmation auto-clears after a few seconds, and switching tabs also drops it so a pending confirm never surprises you when you come back.
- **Incomplete run banner.** If a run ends with rooms unvisited, an alert banner appears at the top of the Rooms tab the moment the integration finalizes the job. A "Queue missed rooms" button kicks off a follow-up run with just the skipped rooms.
