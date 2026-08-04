# Recorder-replay corpus (audit-2 charter §4 delta 12)

Raw HA recorder exports + run inventory, banked as audit-2 test fodder. Provenance: Chris
exported full recorder history from live HA via the history UI, 2026-08-04.

## Files

- `raw/alfred_history_2026-07-25_to_2026-08-04.csv` — Eufy Alfred, 5,620 rows, 150 entities
  (incl. task_status, dock_status, active_cleaning_target, robot_position_x/y_raw pose stream,
  cleaning counters, battery/charging, all the VA-created per-room entities).
- `raw/ivy_history_2026-07-31_to_2026-08-04.csv` — Roborock Ivy, 1,060 rows, 93 entities
  (incl. status, current_room, cleaning/charging binaries, cleaning counters, image entity
  change ticks, active_job).
- `RUN-INVENTORY.json` — derived episode list (57 Alfred + 11 Ivy runs) with start/end/rooms.
  **Chris fills `label` with one ground-truth sentence per run worth keeping** — that label is
  what turns a state stream into an oracle. Unlabeled micro-runs are skipped by consumers.
  Two runs of `pj_2026-08-02T23-04-45` are pre-labeled (the RP-047 group-phase stimulus).

## Format limits — know before consuming

- History-UI CSV: `entity_id, state, last_changed` ONLY. **No attributes**, and attribute-only
  updates are invisible (no last_updated column). Anything attribute-borne (vacuum entity
  attrs, overlay payloads) is NOT here — the future exporter (recorder DB / history API,
  compact keys `s`/`a`/`lu`/`lc`) supersedes this when attribute fidelity is needed.
- Timestamps are real; replay uses virtual time. Deterministic — sequences and gaps, never
  await-interleavings. NOT race evidence (charter delta 6/7 limits).
- Observed oddity worth Chris's confirmation, not consumer guessing: entity ids like
  `sensor.other_alfred_active_job_3`, `switch.other_alfred_kitchen_selected_for_cleaning`,
  `sensor.dining_room_alfred_total_cleaning_time` — registry-history artifacts (rename /
  re-add / area-prefix)? If these are stale duplicates, that is itself corpus metadata.

## Consumers (charter delta 12)

1. Mock replacement — replay through the public state-change seam, production code unmodified.
2. Premise evidence — grep recorded truth for device-answerable questions; bank answers into
   `_premises.json`.
3. Probe scenarios — including ugly topologies (mid-run recharge, stale pushes).
4. trace_route three-path fix review — identical recorded stimulus at BEFORE/AFTER SHAs.
