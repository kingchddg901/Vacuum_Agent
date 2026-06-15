# Roborock adapter (Wave 1)

Second-brand adapter for the multi-brand framework — proves the adapter boundary
with a brand whose **discovery and dispatch are completely different from Eufy's**
(HA `roborock` core integration: native segments via `get_maps`, dispatch via
`send_command app_segment_clean`). Mirrors `adapters/eufy/`.

## Locked decisions (see the project brief)

- **`adapter_id = "roborock"`** — brand-level, not per-model. Per-model differences
  are **capability-gated at registration** from the device-registry model string
  (`device.model`, e.g. `roborock.vacuum.s6`) + live entity presence + the
  `model_catalog`. The Eufy technique; the S6 is the first profile under `roborock`.
- **`DOMAIN` stays `eufy_vacuum`** — Roborock runs inside the same integration.
- Brand is **auto-detected** per vacuum (manufacturer `Roborock` / model prefix
  `roborock.`) in `__init__.py`; an explicit UI brand selector is a follow-up.

## Wave 1 scope (this package)

Loads + the **maintenance** and **lifecycle** tabs work live against the device.
Grounded in the captured `vacuum.ivy` states + a full run trace (2026-06-14):

- `entities` — `sensor.{id}_status` (task_status), `_current_room`
  (active_cleaning_target), `_cleaning_time`/`_area`, `_battery` (mandatory —
  BATTERY feature bit unset), `_vacuum_error` (error_message),
  `binary_sensor.{id}_charging`, `binary_sensor.{id}_cleaning` (job-active hook).
- `lifecycle/completion/error_tracking` — confirmed dual-channel error
  (status + vacuum.state both flip to `error` + code string), completion on
  `charging`/dock.
- `maintenance_components` — 4 consumables (main/side brush, filter, sensor) →
  remaining-hours sensors + reset buttons; rated lives confirmed from the diag.
- `mapping = noop_fallback` (no map image), `job_segmenter = noop_job_fallback`
  (native progress; empirically validated — Eufy counter-plateau would false-segment
  on obstacle stalls). `dispatch = roborock_segment_clean` (valid; exercised in Wave 2).

## Deferred (with reason)

- **`discovery`** (rooms from `get_maps`) — needs the live `get_maps` payload shape;
  the map hasn't fully saved yet. **Wave 2.**
- **`active_map`** entity wiring + multi-map alignment — needs the `get_maps`
  id-space + a collision test. **Wave 2.**
- **maintenance `remaining_is_state` core seam** — Roborock `*_time_left` are
  device-owned countdowns (no `usage_hours`/`total_life`); the flag tells core to
  read device state directly instead of computing a stale duplicate. Flagged on the
  component entries; core support is **Wave 1b**. Replacement-status works natively
  meanwhile.
- **recharge-resume completion gate** — a mid-job recharge also hits `charging`;
  the robust disambiguator is `binary_sensor.{id}_cleaning` staying ON through the
  recharge dock. Wiring the framework to watch + gate on that job-active signal needs
  the recharge→resume→finish continuation trace. **Wave 2.**
- **UI brand selector** (explicit override of auto-detect) — config/options flow. **Wave 1b.**
