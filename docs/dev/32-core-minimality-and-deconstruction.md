# Core Minimality & Deconstruction

*What is the irreducible core, and how much can be removed while the system still cleans a room?*

This is the measured answer to that question — the second axis of the doc-as-spec / deconstruction work (see [`10-learning-system.md` §9.3](10-learning-system.md) for the same exercise scoped to one subsystem). It is a **map, not a changelog**: nothing here has been refactored. It records where the real waterline sits so that a "make the core stand alone" refactor (called **B** below) can be scoped honestly — or deliberately declined.

Method: an AST subsystem-dependency map plus a runtime trace of a single `room_clean` from its service entry to the adapter wire call. Line anchors are as of this audit (2026-07-11) — cite the **method names**, which are stable; the line numbers drift.

---

## 1. Two claims, only one of which matters

The bundled-subsystem pattern (`self.X = XManager(manager=self)`) invites a weak claim and a strong one, and they are easy to confuse:

- **"Subsystems detach"** — *outside-in.* Remove a leaf, does the system survive? This proves the **feature ring is removable**. It is real but weak: maintenance falling off cleanly says maintenance is a module; it says nothing about what's left.
- **"The core stands alone"** — *inside-out.* Start from the claimed atom, everything else absent, and fire one clean. This proves the **core is a core**. It is the claim worth testing, and the only way to test it is to build up from the middle, never to peel down from the edge.

The stated atom is **adapter + dispatch + some input for dispatch**. This document measures how close that is to true.

## 2. The genesis (why the atom is shaped the way it is)

At its base this integration is **`eufy-clean` plus a clean way to call the rooms as a segment.** The original heart was a ~118-line HA script (*ALFRED*): assemble the room input from dashboard helpers → dual-gate it → `vacuum.send_command room_clean` → reset. A brand integration and a room-segment caller. Nothing more.

The base has evolved **exactly once**: when the eufy core was split from the primitives, `eufy-clean` stopped being *the* base and became **an adapter** — adapter #1, with Roborock as #2. The foundation didn't get more capable; it got *generic*. Everything else in the system accreted as strata **above** that unchanged base.

## 3. The atom, measured

Trace of the simplest room clean — `core/manager.py::start_selected_rooms` with `strict_order=False`, the atomic single-phase path a rooms-only brand would hit:

```
start_selected_rooms                       core/manager.py     ── entry
  get_start_status                           (gates: onboarding, paused-job)
  _build_effective_start_plan  ──▶ run_plan  (BUILDS the payload)
  _run_global_pre_calls        ──▶ dispatch  (no-op for a dumb brand)
  _resolve_live_dispatch_payload──▶ dispatch  (passthrough for a dumb brand)
  _dispatch_clean_payload      ──▶ dispatch  ★ WIRE SEND ★
        hass.services.async_call(domain, name, data)   dispatch/manager.py:84
  build_active_job_state       ──▶ queue     (post-wire bookkeeping)
```

**The caller never grew.** The wire send is one line — `dispatch/manager.py:84`, `command` defaulting to the literal `"room_clean"` at `:67` — structurally the same call ALFRED ended on. The `DispatchManager` reads only adapter config + `hass`; it touches **no** feature ring.

The set that **must** exist to fire that one send:

| Atom member | Where | Role |
|---|---|---|
| **adapter** | `adapters/registry.py` `get_adapter_config` + the adapter object | the brand connection |
| **dispatch** | `dispatch/manager.py` + `queue/dispatch_engines.py` `get_dispatch_engine` | shape payload → wire envelope → send |
| **rooms** | `rooms/` | segment identity (the IDs) |
| **spine** | `self.hass`, `self.storage`, `self.data` | HA handle + the internalized state ALFRED kept in helpers |
| **active_job** | `jobs/` `ActiveJobTracker` | tracks the run you dispatched (paused-job gate + post-wire) |
| *(+ the input pipeline)* | see §5 | *mis-homed — the interesting part* |

## 4. The rings (genuinely optional)

Confirmed by the trace, on the room-clean path:

- **Never touched:** `themes`, `maintenance`, `dock`, `room_map`, `map_source`, `live_room_refresh`.
- **Guarded-optional — the model to copy:** `learning` / `external_run`. Every reach-in is already `if learning is None: return …` (`learning/utils.py`, `core/manager.py` preflight + `try/except` snapshot). This is *exactly why* learning is the one heavy subsystem a bare core can run without — and the pattern the welds below lack.
- **Conditionally needed:** `phase_runner` — only for `strict_order` / charge-step runs (atomic jobs build with `phases=None`, so the branch is never entered).

## 5. The welds — atom-logic living in the wrong house

Five rings *are* load-bearing on the current path. Decoded, they are not five dependencies — they are **one legit atom member, three mis-homed room-definition primitives, and one self-satisfiable VA gate that isn't really a weld at all**:

| Ring | Reach-in (as of audit) | What it really is |
|---|---|---|
| **run_plan** | `_build_effective_start_plan` → `run_plan._build_effective_start_plan` | **IS "the input for dispatch."** The dispatch engine is invoked *through* it. Atom-adjacent. |
| **access_graph** | `core/manager.py:1626` `_normalized_managed_rooms_with_automation` → `self.access_graph.*` | the **room-config normalizer** that feeds the payload. A dumb vac has no access rules — but the normalizing *primitive* was housed in the graph ring. |
| **profiles** | `core/manager.py:1250-1254` `_protected_room_config` / `_match_profile_from_fields` → `self.profiles.*` | the **effective-room shaper**. A dumb vac has no profiles — but the shaping *primitive* was housed in the profiles ring. |
| **onboarding** | `core/manager.py:2490` `if not onboarding["floor_types_complete"]:` → blocks start `onboarding_required` | a **self-satisfiable VA gate**, *not a weld*. Floor type is pure VA state — `floor_types_confirmed` is a VA-owned dict in `data["onboarding"]` (`onboarding/manager.py:99`), `confirm_floor_type` just flips a boolean; **the adapter is never consulted.** VA owns the room list *and* the flags, so it can always complete this itself. It blocks today only because it waits for a human confirm — a step that earns its keep for **mopping** (don't mop an unclassified carpet), and is cosmetic for a non-mopping vac. |
| **active_job** | `jobs/` paused-gate + post-wire live settings | run tracking. **Legit atom member — keep.** |

**The verb stayed tiny; the noun got rich.** The *calling* is unchanged (one `async_call`). What inflated is *"which rooms, shaped how"* — ALFRED's helper-string became `run_plan → access_graph → profiles`. Every mis-homed weld is room-**definition**; the onboarding gate is about **when** a room may be called — and since floor type is VA-owned, VA can answer that itself. None of them is about the call.

**The seam is already there.** The core holds thin *delegators* — `_normalized_managed_rooms_with_automation` (`:1626`), `_protected_room_config` (`:1250`) — whose signatures live in core but whose **bodies just forward into the ring**. Giving those bodies a ring-free default is most of B.

## 6. "How much can you pull off?" — a two-layer answer

- **Functionally, today: it still cleans.** `async_initialize` constructs all subsystems unconditionally, so nothing is ever `None`; a rooms-only brand's send *fires* — **once it clears the onboarding floor-type gate** (`:2490`). That gate is brand-independent and self-satisfiable (VA owns the flags); it surprises only because it currently waits for a human confirm.
- **Structurally: not yet.** Remove the rings and the path raises `AttributeError` *before* the wire send, at: `run_plan` (`_build_effective_start_plan`), `access_graph` (`:1626`), `profiles` (`:1250`/`:1254`), `active_job` (paused-gate), `onboarding` (`:2490`/`:3740`).

The distance between those two layers **is** the deconstruction work. Answered plainly: *pull off everything and you are back at ALFRED — and it still calls a room.*

## 7. B — the core-stands refactor (blueprint, not done)

Not "cut five welds." Really **two relocations + one default** (plus one keep):

1. **Room-normalizer → core.** Move `_normalized_managed_rooms_with_automation`'s implementation out of `access_graph` into core/`run_plan` as a ring-free default; `access_graph` *augments* (rules, grants) only when present.
2. **Effective-room shaper → core.** Same for `_protected_room_config` / `_match_profile_from_fields`: a plain default in core; `profiles` *tags* only when present.
3. **Default the onboarding gate away (pure VA logic — not a relocation).** Floor type is VA-owned, so auto-confirm a sensible default on room discovery and gate the *requirement* on **mop capability**: a non-mopping vac passes trivially (floor type is cosmetic for it), a mopping vac still confirms (don't mop a carpet). No brand or ring involvement.
4. **`active_job` stays** — mechanism, not fit.

Result: the atom boots alone — **adapter + dispatch + queue + rooms + spine + active_job**, a plain payload path needing no feature ring. That is a dumb-vac core, and it is *the genesis re-exposed* rather than anything new.

> **B is speculative-value.** It buys portability — "true adapters/modules that attach elsewhere" — not correctness. Sequence it behind an actual need to reuse the core. The smallest safe first cut is the **onboarding default** (item 3): pure VA logic, no ring and no adapter touched. Gating the *requirement* on mop capability makes it a true no-op for the vacs where floor type is cosmetic; the behavior-flip only exists for mopping vacs — which is exactly why the mop-capability condition, not a blind default, is the right shape.

## 8. Acceptance test

**A dumb vac with rooms only** — a brand whose adapter exposes segment IDs and a `room_clean` verb and *nothing else* (no learning, no maps, no maintenance, no planning). If the core cleans a room for it with every feature ring absent, the core stands.

- **Today:** functionally yes, past the onboarding gate; structurally no (rings-absent → `AttributeError` at the §6 anchors).
- **After B:** yes, structurally.

The experience would be miserable — no ETA, no live map, no upkeep, no learned order. That is the point: those are **rings**, and a ring is a thing you add for *fit*, above a caller that has been the same size since ALFRED.

---

## 9. Subsystem pull-checklist

The map above walked the room-clean path. This is the standing worklist for walking **every** manager-constructed subsystem the same way — a living checklist, not a finished audit.

### How to walk one

For each subsystem, ask in order — the first "yes" sets the verdict:

1. **Dead coupling?** Vestigial import/alias core never uses → **CLIP** (see the maintenance clip, 3dc2a06).
2. **Mis-homed atom-logic?** Does core reach in for a *primitive* it should own (a payload/identity builder, not a feature)? → **RELOCATE** the primitive to core; the ring *augments* when present.
3. **Self-satisfiable gate?** Does it block on VA-owned state the adapter never provides? → **DEFAULT** it (see onboarding).
4. **Portable engine?** Is it read-a-lot / write-a-little logic reused elsewhere (learning, battery, water)? → **EXTRACT** behind a host contract (see §9.3 of [`10-learning-system.md`](10-learning-system.md)).
5. **Already clean?** Lazy import, low reach-in count, no core-owned logic inside → **LEAVE** (it's a proper ring today).
6. **Mechanism, not fit?** The core needs it to fire/track a clean → **KEEP** (atom member).

Signals to score it on: **import** (hard = spine candidate / lazy = ring candidate) · **ctor** (`manager=self` back-ref = can reach into core, tighter / `data`+`hass` = already loose) · **core reach-ins** (count of `self.X.` in `core/`, the weave; all currently originate in `manager.py`).

### The checklist (reach-ins as of 2026-07-11 audit)

| Subsystem | Imp | Ctor | Reach-ins | Verdict / status |
|---|---|---|---|---|
| `active_job` | lazy | mgr | 36 | **KEEP** — run tracking (paused-gate + live settings). Atom member. ✅ walked |
| `profiles` | lazy | mgr | 20 | **SPLIT** — relocate the effective-room shaper (`_protected_room_config`/`_match_profile_from_fields`) to core; leave profile CRUD as a ring. ◑ partial |
| `themes` | lazy | data | 13 | *unwalked* — presentation-only, owns `data["theme"]`, loose ctor. Hypothesis: clean detach. ⬜ **WALK** |
| `access_graph` | lazy | data+hass | 12 | **RELOCATE** — `_normalized_managed_rooms_with_automation` (room-normalizer) belongs in core; graph augments with rules/grants. ✅ walked |
| `run_plan` | lazy | mgr | 12 | **KEEP/absorb** — *is* the input pipeline for dispatch. Atom-adjacent. ✅ walked |
| `external_run` (learning) | lazy | mgr | 12 | **EXTRACT** — mapped in §9.3; already `if … is None`-guarded; the portable one. ✅ walked |
| `dock` | lazy | mgr | 9 | *unwalked* — device-action dispatch/gating; latent home for maintenance-level actions (self-clean/empty/descale). ⬜ **WALK** |
| `maintenance` | lazy | mgr | 7 | **LEAVE** — dead import clipped (3dc2a06); now lazy-only, detachable. 7 live reach-ins are legit upkeep delegators. ✅ walked |
| `room_map` | lazy | mgr | 7 | *unwalked* — room↔map association; may be atom-adjacent (map_id resolution) rather than a pure ring. ⬜ **WALK** |
| `onboarding` | lazy | data+hass | 6 | **DEFAULT** — self-satisfiable VA gate (floor type is VA-owned); not a structural weld. ✅ walked |
| `map_source` | lazy | mgr | 5 | *unwalked* — provider segmentation + live-pose (live-map backdrop); off the room-clean path. Hypothesis: clean detach. ⬜ **WALK** |
| `dispatch` | lazy | mgr | 4 | **KEEP** — the caller; reads only adapter cfg + `hass`. Ring-free. ✅ walked |
| `phase_runner` | lazy | mgr | 3 | **KEEP (conditional)** — needed only for strict-order / charge-step runs; atomic path never enters it. ✅ walked |
| `live_room_refresh` | lazy | mgr | 1 | *unwalked* — Lever B live current-room refresh; one reach-in, nearly detached already. ⬜ **WALK (quick)** |

### Out of the ring set

- **Singletons** (constructed in `__init__.async_setup_entry`, not the manager): `LearningManager`, `BatteryHealthManager`, `ErrorTracker`, `MappingManager`/`Tracker`. Battery/water are the **cheap siblings** — same estimation engine as learning; walk them *after* the learning extraction lands the shared host contract.
- **Atom / spine** (hard-imported, the thing that stands): `adapters`, `queue` (engine + dispatch_engines), `maps`, `models`, `rooms` (identity), `jobs`, and `core` (`storage`/`capabilities`/`charging`). Not pulled — this *is* the core.
- **HA glue** (platform wiring, not detachment candidates): `listeners`, `services`, `sensor`, `setup`, `frontend`, `translations`, `textures`.

### Walk queue

Unwalked rings, cheapest first: **`live_room_refresh`** (1) → **`map_source`** (5) → **`room_map`** (7) → **`dock`** (9) → **`themes`** (13). Then the **`profiles` split**, then the **battery/water singletons** once learning's contract is extracted.

---

**See also:** [`01-architecture-overview.md`](01-architecture-overview.md) · [`05-core-manager.md`](05-core-manager.md) · [`10-learning-system.md`](10-learning-system.md) (§9.3, the same host-contract exercise scoped to learning) · [`21-adapter-system.md`](21-adapter-system.md).
