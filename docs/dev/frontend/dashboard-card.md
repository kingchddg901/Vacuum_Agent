# Dashboard control card (DESIGN + shipped W1–W3)

> **Status: W1–W3 SHIPPED** (branch `feat/dashboard-card`). The compact multi-room
> control card, the embedded map, and the polish pass are all live. This file keeps
> the original design rationale below (issue #34); the banner tracks what actually
> shipped. For the *architecture* of the cards + bundles + map host, see
> [Card Topology & Bundles](card-topology-and-bundles.md).
>
> **W1 — control card (list-based):**
> - `src/cards/dashboard-dispatch.js` — pure, unit-tested run-launcher logic
>   (`nextArmed` mutual-exclusivity reducer, `planStart` dispatcher, `armedIsValid`
>   re-validation). `dashboard-dispatch.test.mjs`.
> - `src/cards/_shared.js` — helpers shared with the room-card (`esc`, `vocab`,
>   `roomSwitchesFor`, `adapterOptions`, `committedRoomFields`, `isMopMode`,
>   `chipRow`, `callResponse`, `registerCard`, `defineCard`, the language control).
> - `src/cards/dashboard-card.js` — the `vacuum-agent-dashboard` element + editor.
> - Backend: `scene_select` declared in the Eufy adapter `entities` block, surfaced
>   (existence-checked) on `get_dashboard_snapshot`. Roborock degrades to `None`.
> - Global cards bundle: `src/cards-standalone.js` → `frontend/eufy-vacuum-cards.js`
>   (cards only, no panel), registered as a global ES module via
>   `frontend.add_extra_js_url` in `async_setup` — defined on every page, even a cold
>   dashboard. `defineCard` makes the panel bundle's duplicate define a no-op.
>
> **W2 — the embedded map.** The map subsystem was extracted into a reusable
> `<eufy-vacuum-map>` custom element (`src/cards/vacuum-map-host.js`) that mounts the
> existing `VacuumCard{State,Renderers,Bindings,Actions}` mixins onto a card-shim host.
> It ships as its own lazily-loaded bundle (`frontend/eufy-vacuum-map.js`), imported on
> demand by the dashboard card. Full VA-render backdrop, zone-draw, rotate, layers
> panel, mascot controls — the same map as the panel. See
> [Card Topology & Bundles](card-topology-and-bundles.md).
>
> **W3 — polish.** Collapsible map + Rooms groups; the per-user **language globe** in
> both cards; **strict-order** toggle (Roborock); Eufy scene **"None"** filter; pinned
> **pan/zoom** across reloads (per-device, per-context); **drag-to-move room-name
> labels** (per-device). Locale files de-bundled + cache-busted; `vacuum_card.*` keys
> translated into all 7 shipped locales.
>
> **Verified:** frontend `node --test` + backend pytest green; i18n + styles gates
> clean; multi-agent adversarial review at each wave (notably: a first-load
> `resetMapTransform` that wiped the restored pan/zoom, and a double-escape class —
> `esc()` over already-escaped `t()` output — both caught + fixed). **Pending:** merge
> → release (version bump + CHANGELOG + HACS).

## 1. Goal

Give users a **compact control card they drop into their own dashboard** (next to
their lights), instead of opening the full sidebar panel — pick rooms + clean mode,
run a saved setup, start, dock. This is the **adoption lever**: most HA users live in
their dashboards, not sidebar panels. Requested by Pistakkio ([#34]) with a Dreame
card as the visual reference (status header → map with room blobs → mode/passes →
Room/All/Zone → Clean/Dock).

**The headline:** the *engine* is already built and tested. Every backend service the
card needs exists; the existing single-room `EufyRoomCard` already proves the
card+editor+i18n form factor. This is mostly **assembly**, with one honest exception
(the map — see §7).

[#34]: https://github.com/kingchddg901/Vacuum_Agent/issues/34

## 2. What it does

A new **multi-room control card** (`vacuum-agent-dashboard`, display "Vacuum Agent — Dashboard Mode"),
config-driven, sections capability-gated:

- **Header** — vacuum name, status, battery, area (from `get_dashboard_snapshot`).
- **Run source** (pick ONE):
  - **Rooms** — a list of **collapsing per-room rows**: toggle a room to include it,
    expand the row to set that room's own mode / suction / water / passes (the
    room-card's setting body, repeated per row — an accordion).
  - **Your profiles** — a dropdown of saved run profiles (`get_saved_run_profiles`).
  - **App scenes** — *Eufy only* — a dropdown of the vendor-app scenes
    (`select.<object_id>_scene`); hidden on Roborock (no such entity).
- **Actions** — **Start** (commits the armed run), **Dock**, and optional dock
  actions (Wash/Dry/Empty) gated by `get_dock_action_status`.
- *(Later)* **Map** — the interactive room map in a compact box (§7).

## 3. The core contract — arm, then Start

**Selecting is inert; only Start fires.** The user builds a selection — rooms, mode,
a profile, a scene — entirely in **card-local draft state** (the same pattern
`EufyRoomCard` already uses with `_fields`). Nothing reaches the vacuum until **Start**.
This is a hard requirement: *"we don't want a run to fire just because they were
setting it up."* It is also load-bearing for the Eufy scene (see §6 — `select_option`
*is* the fire).

**Start is a small dispatcher**, by what's armed:

| Armed source | Start does |
|---|---|
| **App scene** (Eufy) | `select.select_option(select.<obj>_scene, <name>)` — this *is* the run; no VA dispatch |
| **Run profile** | `eufy_vacuum.start_run_profile({vacuum_entity_id, profile_id, …})` |
| **Manual rooms** | enable the chosen room switches (`switch.turn_on` / `update_room_fields`), then `eufy_vacuum.start_selected_rooms({vacuum_entity_id, map_id, …})` |

**Mutual exclusivity:** a scene or a profile is a *complete* pre-baked run, so arming
one greys/disables the manual room+mode pickers (and vice-versa). Exactly one source
is ever live. Enforced client-side (no backend gate needed). **Dock** is its own
button, independent of the armed source.

## 4. What it reuses (this is why it's cheap)

| Card piece | Reuses (verify-vs-code) |
|---|---|
| Card + editor + registration | `EufyRoomCard` / `EufyRoomCardEditor` patterns (`src/room-card.js`) — `setConfig`, `set hass`, `customElements.define`, `window.customCards.push`, `getConfigElement`, `getStubConfig` |
| Room list + per-room settings chips | the room-switch finders + `_adapterOptions()` + the `chipRow()` builder (`src/room-card.js`) — the `switch.*` entities already carry `room_id` + `*_options` attrs |
| Draft/dirty state | `_fields` / `_committedFields` / `_isDirty` pattern |
| Mode/suction/water/path/passes vocab | `get_dashboard_snapshot().adapter_vocabulary` (`clean_mode_options` / `fan_speed_options` / …) + `tVocab` |
| Status header | `eufy_vacuum.get_dashboard_snapshot` (lifecycle, job_progress, battery, area) |
| Run profiles | `eufy_vacuum.get_saved_run_profiles` (list) + `eufy_vacuum.start_run_profile` |
| Room clean | `switch.turn_on/off` + `eufy_vacuum.update_room_fields` + `eufy_vacuum.start_selected_rooms` |
| Dock + dock actions | `vacuum.return_to_base` + `eufy_vacuum.{wash_mop,dry_mop,empty_dust}`, gated by `eufy_vacuum.get_dock_action_status` |
| Capability gating | `get_dashboard_snapshot().capabilities` (`max_clean_passes`, `supports_base_station`, `supports_room_profiles`, `honors_clean_order`, …) |
| i18n | the same i18n module (`translate` / `resolveLang` / `tVocab`); new `vacuum_card.*` keys, reuse `vocab.*` |

**Everything in that table already exists and is tested.** No new backend services.

## 5. Architecture — a NEW sibling card, not an extension

`EufyRoomCard` is deliberately **single-room** (config = `vacuum_entity_id` + `room_id`).
The control card is **multi-room + profiles + scenes + dock** — a different shape.
**Recommendation: a new sibling card** (`vacuum-agent-dashboard`) that reuses the room-card's
*patterns/helpers* (extract the shared bits — `chipRow`, the entity/option readers, the
i18n helpers, the draft-state pattern — into a small `src/cards/_shared.js` both import),
rather than overloading the room-card with a mode flag. Both register in
`window.customCards`; both ship in the existing bundle (`npm run build:deploy`, never
hand-edit the minified bundle —).

## 6. App scenes — Eufy-only, fires-on-select, adapter-gated

Confirmed on-device (): selecting an option in eufy-clean's
`select.<object_id>_scene` **immediately runs** the scene. So:

- Build the dropdown from the entity's **`options` attribute** (read-only — safe).
- **Never call `select_option` until Start** (arm = local highlight only).
- **Gating:** the scene group shows **only when the scene entity resolves**. Cleanest
  is to **declare it in the adapter** — add a `scene_select` key to the adapter
  `entities` block (Eufy: `"select.{object_id}_scene"`; Roborock: absent) and surface
  the resolved id on `get_dashboard_snapshot` (like `setting_entities` / `live_map_image_entity`
  already are). The card reads it from the snapshot; Roborock simply has none → group
  hidden. (Fallback if we don't touch the adapter: the card probes
  `select.<object_id>_scene` in `hass.states` — works, but the declared path is
  adapter-pattern-consistent and brand-future-proof. **Recommend the adapter route.**)

This is the adapter pattern paying off: a brand-specific capability is one declared
entity; the card stays brand-agnostic; Roborock degrades gracefully instead of showing
a dead control.

## 7. The map — honest scope (the one real lift)

Chris's "scale the map, simple math" is **half right**: the *coordinate* math is already
solved — the renderer works in normalized 0–1 coords, `object-fit: contain` in a square
box, so it reprojects to any container size for free. **But the map is a renderer
*mixin*, not a standalone component** (`src/renderers/map.js` + `src/state/map.js` +
`src/bindings/map.js`). It's coupled to the monolithic `EufyVacuumCommandCenter`:
`this.card._state`, `this.card._actions`, `this.card._scheduleRender()`, and
`this.card.shadowRoot`. Dropping it into a separate card means **extracting a component**:
clone the state mixin + render + bindings onto a new element, provide an actions/scheduler
shim, scope DOM to the new `shadowRoot`, feed it `hass` + the snapshot, and share the
`.evcc-map-*` CSS. That's real work, not "a smaller div."

**So the map is staged out:**
- **W1 ships without the map** — a clean **room *list*** (multi-select chips), which is
  the room-card's proven path and delivers the full functional ask (select rooms + mode
  + profiles + scenes + start/dock).
- **W2 adds the map** — extract the map renderer into a reusable
  `<eufy-vacuum-map>` element (also lets the panel reuse it), or, cheaper, render a
  **static, tap-selectable** room map (the VA-render raster / segment polygons with
  click-to-toggle, no zoom/pan/overlays). Decide at W2.

Calling this out so the estimate is honest: **the list card is days; the embedded map
is its own chunk.**

## 8. Config schema + editor

```yaml
type: custom:vacuum-agent-dashboard
vacuum_entity_id: vacuum.alfred   # required
title: Vacuum                     # optional
show_profiles: true               # default true (hidden if supports_room_profiles=false)
show_scenes: auto                 # auto = show iff the scene entity resolves (Eufy)
show_dock: true                   # default true (hidden if supports_base_station=false)
show_map: true                    # default true; the embedded map shipped (shown unless set to false)
```

Editor: extend the `EufyRoomCardEditor` pattern — a `vacuum_entity_id` picker + the
`show_*` toggles. `getStubConfig` returns the first discovered vacuum.

## 9. i18n

New `vacuum_card.*` keys for the new labels (Rooms / Your profiles / App scenes /
Clean / Clean all / Dock / "scene runs immediately" hint / etc.) — keyed at creation per, +7 locales drafted as usual. Slot *values*
(modes/suction/etc.) reuse the existing `vocab.*`. The card runtime-loads non-English
locales the same way the room-card does (a card on a view with no main panel is the only
thing that triggers the loader).

## 10. Edge cases / gotchas

- **Scene fires on select** — never call `select_option` until Start (§6); a careless
  hover/preview must not dispatch.
- **Roborock has no scenes** — group hidden, not a dead control.
- **`honors_clean_order=false` (Roborock)** — if we expose room *order*, show it as
  advisory (path-optimizing), mirroring the panel.
- **`max_clean_passes`** caps the passes chips (Eufy 2, Roborock 3); `passes_is_global`
  changes per-room vs whole-run semantics.
- **Two cards on one dashboard** — ✅ pan/zoom (and moved room-name labels) are keyed
  per *context* (panel vs card) + per device, so the panel and a dashboard card keep
  independent map views (`_mapCtx` on the state; see [Card Topology & Bundles](card-topology-and-bundles.md)).
- **Multi-map vacuum** — the room list is filtered to the **active map only**
  (`_roomsForActiveMap()`, mirroring the panel's `getRoomsForActiveMap`), so a device with
  several maps (e.g. Alfred: map 6 + map 7) doesn't list every map's rooms at once. Every
  operate-on-rooms site (render, room toggle, `_startContext`, `_turnOffAllRooms`, room-by-id
  lookup) uses the filtered set, which also prevents a Start from targeting an off-map room
  when two maps share `room_id` values. Unfiltered `_rooms()` survives only where it must (the
  `_activeMapId()` fallback and the `shouldUpdate` diff).
- **No live entity** — degrade every section independently; a missing snapshot field
  hides its control, never throws (wrap reads).
- **Mid-run** — show progress in the header; Start becomes "already cleaning" / the
  pause/resume controls (reuse `job_control` from the snapshot).

## 11. Phasing (waves)

- **W0** — this design + approval pause.
- **W1 (MVP, list-based).** New `vacuum-agent-dashboard` + editor; header (snapshot);
  multi-room chip select + mode/passes; **run-launcher** (profiles + Eufy scenes,
  adapter-declared `scene_select`); arm-only/Start dispatcher; Clean / Dock. Eufy +
  Roborock (scenes Eufy-only). `vacuum_card.*` i18n. **No map.**
- **W2 — the map.** ✅ Extracted the reusable `<eufy-vacuum-map>` host
  (`src/cards/vacuum-map-host.js`), lazily loaded; full VA-render map, zone-draw,
  rotate, layers, mascot.
- **W3 — polish.** ✅ Collapsible map + Rooms; language globe in both cards;
  strict-order toggle (Roborock); scene "None" filter; pinned pan/zoom across reloads;
  drag-to-move room-name labels.

## 12. Testing

The card is frontend JS: unit-test the **Start dispatcher** (armed scene → `select_option`;
profile → `start_run_profile`; rooms → `start_selected_rooms`; nothing fires before
Start) and the mutual-exclusivity logic with `node --test`, and add it to the
**render harness** (Playwright visual-reg, incl. a Cyrillic locale + a Roborock config
that hides the scenes group). The backend services are already covered. Gate:
`node --test` + the harness.

## 13. Decisions (resolved 2026-06-28, Chris)

1. **Scene gating** — ✅ **declare `scene_select` in the adapter** `entities` block
   (Eufy `select.{object_id}_scene`, Roborock absent), surfaced on `get_dashboard_snapshot`.
   Not probing.
2. **Map** — ✅ **in scope.** Extract a reusable `<eufy-vacuum-map>` component (the panel
   reuses it too); ships in **W2**.
3. **Card** — ✅ **a NEW sibling card.** The existing single-room `EufyRoomCard` STAYS —
   Chris likes it one-per-room — and the new card is the multi-room control card. Shared
   helpers extracted to `src/cards/_shared.js`.
4. **Per-room settings** — ✅ **per-room, as collapsing rows.** Each room is a row you
   toggle to include; expand it to set that room's own mode/suction/water/passes — i.e.
   the room-card's setting body, repeated per row (an accordion). Not one-mode-per-run.
5. **Name** — **"Vacuum Agent — Dashboard Mode"** (display), `type: custom:vacuum-agent-dashboard`.

## 14. References

- Issue [#34]; the Dreame reference card.
- Reuse map (this design): `src/room-card.js`, `src/renderers/map.js` + `src/state/map.js`
  + `src/bindings/map.js`, `custom_components/eufy_vacuum/services.yaml`,
  `adapters/{config_schema,eufy/adapter,roborock/adapter}.py`, `profiles/manager.py`,
  `core/manager.py::get_dashboard_snapshot`.
- Memory: (scene fires-on-select),
  (edit src/, build:deploy),, the voice wizard's
  sibling "meet users where they are" play in.
