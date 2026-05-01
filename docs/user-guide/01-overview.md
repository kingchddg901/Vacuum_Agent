# eufy_vacuum — User Guide Overview

## What is this?

eufy_vacuum is a Home Assistant custom integration paired with a Lovelace card called **eufy-vacuum-command-center**. Together they give you room-level control over your Eufy robot vacuum directly from your HA dashboard.

The integration has been tested on the **Eufy X10 Pro Omni**. It may work on other Eufy models, but only the X10 Pro Omni is officially supported.

## What does it add beyond the stock Eufy integration?

The standard Eufy integration in Home Assistant lets you start and stop your vacuum as a single unit. eufy_vacuum goes further:

- **Room-level control.** You choose exactly which rooms to clean before each run, and in what order.
- **Per-room cleaning settings.** Each room can have its own cleaning mode (vacuum, mop, or both), suction level, water level, cleaning path, number of passes, and edge mopping toggle.
- **Cleaning profiles.** You can save a named set of room settings as a reusable profile and apply it to any room in one tap. Built-in profiles are read-only; you can create as many custom profiles as you like.
- **Run profiles.** You can save an entire room selection — which rooms are included, in what order, with what settings — as a named run profile and start it again with a single button.
- **Queue management.** The card shows you which rooms are queued, their estimated cleaning times, and your planned run order. You can reorder rooms by dragging or by using a move button.
- **Learning system.** After each run the integration records how long the vacuum spent in each room. Over time it builds per-room timing estimates that get more accurate the more you use it. The card displays a confidence indicator (Reliable / Learning / Uncertain) for each room's estimate.
- **Incomplete run recovery.** If a run ends before all rooms are finished, the card shows a banner letting you queue only the missed rooms for a follow-up run.
- **Trouble room indicators.** The card tracks rooms the vacuum has repeatedly failed to clean and flags them so you can investigate.
- **Metrics and learning review.** Dedicated panels let you browse historical run data and review what the system has learned.
- **Theming.** The card's colors, typography, and layout tokens are fully customizable from within the card itself.

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

The card has a header strip at the top showing your vacuum's name, current status (cleaning, docked, paused, etc.), and battery level. Below that is a navigation bar with tabs that switch between panels:

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

The card opens on the **Rooms** tab by default.
