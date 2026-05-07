# Eufy Vacuum Manager

A custom Home Assistant integration that adds room-level control, queue management, a learning/ETA system, automation events, and a built-in Lovelace panel card to your Eufy vacuum. These capabilities are not available in the standard Eufy integration.

## What it does

[eufy-clean by jeppesens](https://github.com/jeppesens/eufy-clean) exposes basic start/stop/pause and a few entity states. This integration goes further:

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
- Your Eufy vacuum must already be set up and working in Home Assistant via [eufy-clean by jeppesens](https://github.com/jeppesens/eufy-clean) (the integration that provides the `vacuum.*` entity). This integration does not replace it — it builds on top of it.

## Installation via HACS

1. In Home Assistant, open **HACS** and go to **Integrations**.
2. Click the three-dot menu (top right) and choose **Custom repositories**.
3. Add `https://github.com/kingchddg901/eufy-vacuum-manager` as an **Integration** type repository.
4. Search for **Eufy Vacuum Manager** in HACS and install it.
5. Restart Home Assistant.
6. Go to **Settings → Devices & Services → Add Integration** and search for **Eufy Vacuum Manager** to complete setup.
7. A **Eufy Vacuum** item will appear in your sidebar. The panel card is registered automatically — no manual dashboard editing required.

## What's included

- The `eufy_vacuum` custom integration (services, events, data layer).
- A Lovelace panel card served directly from the integration. No separate HACS frontend repository and no manual resource registration needed.

Rooms Tab
<img width="810" height="435" alt="image" src="https://github.com/user-attachments/assets/6588451c-8656-461d-a725-2768c3ed42ff" />
Room Settings
<img width="243" height="352" alt="image" src="https://github.com/user-attachments/assets/324c8edd-7188-4dbc-815b-6e936eaf7377" />
Maintenance Tab 
<img width="848" height="431" alt="image" src="https://github.com/user-attachments/assets/3801b206-381e-45f1-93b1-1d3323b28ee4" />
Base Station Tab
<img width="843" height="365" alt="image" src="https://github.com/user-attachments/assets/744f6408-50cf-47eb-bb8f-582bd3385593" />
Metrics Tab
<img width="846" height="434" alt="image" src="https://github.com/user-attachments/assets/83014786-ad61-409b-adb7-5971dcb11b30" />
Learning Review Tab
<img width="848" height="438" alt="image" src="https://github.com/user-attachments/assets/4c3754e1-4038-49d1-baf2-c5ea62d427a3" />
Room Rules Tab
<img width="842" height="368" alt="image" src="https://github.com/user-attachments/assets/78bfb254-eb0f-4f3b-833b-93d6a56de8f6" />
Themes Tab
<img width="844" height="425" alt="image" src="https://github.com/user-attachments/assets/4fad5545-3bb4-47d9-b3f3-ad384b43e85d" />
Map Bounds Review Tab
<img width="844" height="408" alt="image" src="https://github.com/user-attachments/assets/7189e808-d8a9-4685-af49-65559d3cc660" />
Setup Tab
<img width="831" height="440" alt="image" src="https://github.com/user-attachments/assets/dd205110-8137-436f-8c0a-70aaa1e16052" />

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

## Acknowledgements

This integration would not exist without [eufy-clean](https://github.com/jeppesens/eufy-clean) by jeppesens and its contributors. Their work reverse-engineering the Eufy protocol and maintaining the HA integration that bridges the vacuum to Home Assistant is the foundation everything here is built on. If you find this useful, go give their repo a star too.

## Documentation

Full documentation: https://github.com/kingchddg901/eufy-vacuum-manager

## Licence

MIT — you are free to fork and adapt this work without attribution to this repository.

One condition: this project is a top-level addition built on [eufy-clean](https://github.com/jeppesens/eufy-clean). Any fork or derivative work must maintain acknowledgement of that dependency. See [LICENSE](LICENSE) for full terms.

## Issues

Please report bugs and feature requests at: https://github.com/kingchddg901/eufy-vacuum-manager/issues
