# Eufy Vacuum Manager

A custom Home Assistant integration that adds room-level control, queue management, a learning/ETA system, automation events, and a built-in Lovelace panel card to your Eufy vacuum. These capabilities are not available in the standard Eufy integration.

## What it does

The stock Eufy integration exposes basic start/stop/pause and a few entity states. This integration goes further:

- **Room-level control** — select individual rooms by name and send targeted clean jobs, rather than cleaning the whole floor.
- **Queue management** — build, inspect, and reorder a cleaning queue before the job starts.
- **Run profiles and room profiles** — save vacuum settings (suction, mop, passes) per-room or as named run profiles you can trigger from automations or the UI.
- **Room rules** — attach per-room rules (e.g. mop-only, skip when occupied) that are applied automatically when a job is built.
- **Learning system and ETA** — the integration records how long each room takes and uses that data to estimate job completion times. Estimates improve with each run.
- **Stall detection** — fires a Home Assistant event when the vacuum has been in a room significantly longer than its learned average.
- **Automation events** — exposes `eufy_vacuum_job_finished`, `eufy_vacuum_room_started`, `eufy_vacuum_room_finished`, `eufy_vacuum_path_blocked`, `eufy_vacuum_stall_detected`, and `eufy_vacuum_run_incomplete` events for use in automations.
- **Theme system** — a built-in theme editor for the panel card, with save/load/import/export support.
- **Built-in Lovelace panel card** — the integration registers its own dashboard panel. No separate card repository or manual resource registration is needed.

## Tested hardware

| Model | Status |
|---|---|
| Eufy X10 Pro Omni | Tested |
| Other Eufy models | Untested — may work, not supported |

## Prerequisites

- Home Assistant 2024.1.0 or later
- Your Eufy vacuum must already be set up and working in Home Assistant via the standard Eufy integration (the one that provides the `vacuum.*` entity). This integration does not replace it — it builds on top of it.

## Installation via HACS

1. In Home Assistant, open **HACS** and go to **Integrations**.
2. Click the three-dot menu (top right) and choose **Custom repositories**.
3. Add `[GitHub repo URL]` as an **Integration** type repository.
4. Search for **Eufy Vacuum Manager** in HACS and install it.
5. Restart Home Assistant.
6. Go to **Settings → Devices & Services → Add Integration** and search for **Eufy Vacuum Manager** to complete setup.
7. A **Eufy Vacuum** item will appear in your sidebar. The panel card is registered automatically — no manual dashboard editing required.

## What's included

- The `eufy_vacuum` custom integration (services, events, data layer).
- A Lovelace panel card served directly from the integration. No separate HACS frontend repository and no manual resource registration needed.

## Feature summary

- Room selection and targeted clean jobs
- Cleaning queue — build, reorder, inspect before starting
- Room profiles — per-room suction, mop, and pass settings
- Run profiles — named full-run configurations, triggerable from automations
- Room rules — conditional per-room behavior
- Learning system — records per-room timing, improves ETA estimates over time
- ETA display — estimated completion time shown in the panel
- Stall detection — event fired when a room takes significantly longer than learned average
- Automation events — job, room, stall, path-blocked, and incomplete-run events
- Dock actions — wash mop, dry mop, empty dust bin (model-dependent)
- Maintenance tracking — reset maintenance counters from the UI
- Theme system — full theme editor with save/load/import/export

## Documentation

Full documentation: [GitHub repo URL]

## Issues

Please report bugs and feature requests at: [GitHub repo URL]/issues
