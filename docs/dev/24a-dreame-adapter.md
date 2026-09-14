# 24a — The Dreame Adapter

**Scope.** How the third brand answers [the contract](22-adapter-contract.md), and what it cost to
be third. Read [24 — The Roborock Adapter](24-roborock-adapter.md) first: Roborock paid the bill
for Eufy's residual defaults, and Dreame is the first brand to arrive after that bill was settled.

Roborock's lesson was that most of its verbosity was *a name Eufy already occupied*. Dreame's
lesson is the quieter one: **being third cost core very little.** The contract absorbed it. What
looks in the commit history like a large core change is mostly a *method* change that ran
alongside this port rather than one the brand demanded — §5 separates the two, because the
difference is the whole answer to "what does a new brand cost us now".

Shipped in v2.2.0 (2026-09-13). The registrar row that reaches this package was deliberately
withheld for all 131 commits of its development — see §8.

---

## 1. What the adapter computes

`adapters/dreame/adapter.py::register_dreame_adapter_for_vacuum` resolves the model profile,
capability flags, and the entity-id map at runtime, then emits a literal config dict into
`adapters/registry.py::register_adapter_config`. Same shape as Roborock — it wraps an upstream HA
integration rather than talking to hardware — and like Roborock, nothing in the file executes
during a clean.

Capability flags are **the model profile OR-ed with live entity presence**
(`adapters/config_schema.py::detect_capabilities`), so the registered config reflects this
installation's actual HA surface rather than the catalog's opinion of the model. That matters more
here than it did for Roborock, because the catalog is thin (§6).

---

## 2. Identity, and a station that is not a dock

`adapters/dreame/const.py::UPSTREAM_PLATFORMS` is `("dreame_vacuum",)`, matched against the entity
registry's `platform` — the mechanism Roborock introduced, used here without change. This brand is
the reason that mechanism exists at all: the deleted per-brand detector had a default arm, and the
failure it produced was *a Dreame being silently registered as a Eufy*, binding 2 of ~10 Eufy roles
by coincidence of naming and looking configured rather than wrong.

**The station is integral, and that removes a whole resolution step.** Roborock's dock is a
separate device in the device registry and needs live resolution (24 §3). Dreame's station is part
of the one device, so there is no `dock.py` equivalent here: station capabilities come from the
model profile and are OR-ed with live entity presence — `self_wash_base_status`,
`auto_empty_status` and the `drying_*` sensors are the live gate.

---

## 3. The map is decoded, not given

The largest genuine difference from either earlier brand. Eufy's rooms are inferred from map
screenshots ([25 — The Eufy Segmentor](25-eufy-segmentor.md)); Roborock's arrive as vendor rooms.
Dreame's arrive as **a camera attribute carrying encoded map data**, which we decode ourselves into
rooms, true per-room area, furniture and pose.

Two consequences the rest of the system feels:

- **Geometry is ours, so the projection is ours to get wrong.** `mapping/map_source_runtime.py`
  carries `dreame_correspondences_from_mapdata`, and it is a declared replica (`RN0Y49XS`) of the
  render's own projection: the go-to / zone affine is fitted from those correspondences, so if the
  two projections ever disagree the robot drives to the wrong place. That is why it is anchored
  rather than merely commented.
- **Heading comes from the camera's live angle**, `h = (a - 90) mod 360` — the render frame and the
  device frame differ by a quarter turn — with a tunable frame offset for aligning our raster onto
  the device's.

This is the one area where the brand really did push on core: the map source runtime and
coordinator carry Dreame-shaped work that neither earlier brand needed.

---

## 4. Zone is a service, not a verb

On Roborock and Eufy an ad-hoc zone clean rides the same `send_command` verb as a room clean, so
the adapter expresses it as a verb override. Dreame's zone is **its own upstream service**
(`dreame_vacuum.vacuum_clean_zone`, distinct from room-clean's `vacuum_clean_segment`), which is
why the config carries a dedicated `zone` block alongside `goto` rather than a
`dispatch.zone_command`. Coordinates are 4-tuples in device mm, not Roborock's 5-tuples.

**And a zone clean is a GLOBAL clean on this brand**, which forced the more interesting piece. The
device applies its *global* cleaning settings to a zone, and those globals are gated by a
`customized_cleaning` switch — turn per-room custom cleaning on and the globals go `unavailable`.
So the config declares a `global_precall` sequence: flip the gate off, write suction / water / mode
/ route to the global selects with readback verification, run the bare zone, then restore every
snapshotted value *and* the gate at zone completion. A zone clean must not persist its own
settings, and on this brand that is work rather than a property.

Note what this *did not* require: no core change. The declaration shape already allowed a brand to
describe a command as its own service with a pre-call sequence.

---

## 5. What the third brand actually taught core

The honest accounting, because the commit history overstates it.

**Separate the method change from the brand.** A Dreame-scoped commit range touches
`adapters/eufy/adapter.py` and `adapters/roborock/adapter.py`, which looks like the third brand
reaching into the first two. It is not. Maintenance guidance moved from prose routed by guide
family to **regime → i18n keys**, and that method change was developed here because this is where
the work happened to be — the older family-prose channel was then deleted and both other brands
were ported onto the new one. A fourth brand meets the new method already in place and pays none of
it. Read that churn as *the method changed*, not as *Dreame forced it*.

**What the method change left behind is one genuinely neutral module.**
`adapters/upkeep_keys.py` says so in its own docstring: *"It was written inside the Dreame adapter
because Dreame was the only caller. It is now the second and third brand's algorithm too."* It sits
in `adapters/` rather than `core/` because that layer is already neutral **and checkable** —
`config_loader`, `config_schema`, `entity_resolve` and `registry` import zero brand packages, with
`brands.py` the deliberate exception for being the registrar table.

**The rule that came with it** is the one worth carrying forward: *core owns the key, the brand
keeps the word*. There is no mop-type alias map in the neutral module — `mop_type` arrives already
in `{cloth, pad, roller, track}` because the regime generator maps the vendor's term when it writes
the table. A brand that wants its own display word declares `label_key` in its component catalog
and the card resolves it. A brand's vocabulary never reaches the shared algorithm.

**So what did Dreame itself cost core?** Two things, both in §3: the camera-attribute map backend,
and the projection replica that the go-to / zone affine depends on. Everything else it needed, it
declared. That is the contract working as intended, and it is a materially cheaper third brand than
Roborock was a second.

---

## 6. Capabilities fail closed, and one of them is a known false

`adapters/dreame/model_catalog.py::DEFAULT_PROFILE` is what an unrecognised Dreame gets, and it is
deliberately asymmetric. Mop and station flags default **True**, because they degrade safely — a
device that cannot honour a mop control simply has no matching live entity, and entity-presence
detection is the real gate. `has_path_control` and `supports_zone_clean` default **False**, because
offering a control the device lacks — or worse, inverting a drawn box into the wrong coordinate
frame — is the worse failure.

The practical effect at release: **one model carries a hardware-verified override**
(`dreame.vacuum.r2469a`, the L10s Ultra Gen2 the adapter was built against). Every other Dreame
gets rooms, map, maintenance and history, and does not show go-to or zone clean. This opens up per
model as hardware is confirmed. `MODEL_PROFILES ⊆ DREAME_MODEL_REGIMES` is asserted at import, so
the capability source and the guide/name source cannot drift — the two-table lesson from 24 §7,
applied before it could bite.

> **`supports_edge_mopping` is hardcoded `False` with a comment saying some Dreame models have
> it.** That is a *false CAN'T*, and this brand's own working rule is that a false CAN'T hides a
> capability silently and permanently for every user of the brand, where a false CAN merely
> surfaces a control that errors. It is the one place in the package where the deferral is
> invisible from the outside. Resolving it needs per-model hardware confirmation.

Five more deferrals are marked `PHASE 3` / `PHASE 4` in `adapter.py` and carry conservative values.

---

## 7. The guides: 700 models, 13 regimes, no prose in the backend

Maintenance guidance is routed by **regime**, not by model and not by brand:
`adapters/dreame/upkeep_keys.py` over `upkeep_regimes.py` maps 700 model ids onto 13 regimes, each
of which is a list of **i18n keys**. The backend holds no guide words at all — the card supplies
them in the reader's own language, in all eighteen.

A regime is `(mop_type, dock_tier, tanks)` — three measured facts — and the same three facts now
type every brand's models, which is the method described in §5 rather than anything Dreame-specific.
What *is* Dreame-specific is the sourcing: the regime table was authored from Dreame's own manual
corpus rather than inferred, which is what makes 700 rows worth having instead of a default.

---

## 8. The release switch, withheld for 131 commits

There is exactly one thing that reaches this package: the `dreame` row in
`adapters/brands.py::BRAND_REGISTRARS`. While it was absent the entire adapter was dead code no
import touched, and every Dreame vacuum resolved to `unsupported`. It was never committed during
development — `git log -S dreame` on `brands.py` is empty across all 131 commits — and a test
existed solely to go red if it were added by accident.

That test, `test_dreame_has_a_brand_registrar_row` [DUK-1], is now **inverted rather than deleted**.
The asymmetry was never real: a row that can be added by accident can be dropped by accident, and
dropping it is the silent direction — no import breaks, no other test fails, every Dreame device
just quietly becomes unsupported again, precisely because nothing else references it.

**On the gate it waited behind.** The condition was recorded as "a RELEASED upstream build carrying
Tasshack #1707". That premise was retired by measurement on 2026-08-30: only an *unmapped* first
setup is bitten, a mapped device never is, so the remedy is a setup note — map first, then reload —
which shipped with the user guide. Do not re-derive the gate from tracker #1742; it is closed as a
duplicate and reads green, which it is not.

---

## Registries

| What | Where |
|---|---|
| The switch | `adapters/brands.py::BRAND_REGISTRARS`, the `dreame` row |
| Config assembly | `adapters/dreame/adapter.py::register_dreame_adapter_for_vacuum` |
| Identity | `adapters/dreame/const.py::UPSTREAM_PLATFORMS` |
| Capability profiles | `adapters/dreame/model_catalog.py` (`MODEL_PROFILES`, `DEFAULT_PROFILE`) |
| Live-captured enums | `adapters/dreame/vocabulary.py` — from a device, never a manual |
| Regime to keys | `adapters/dreame/upkeep_keys.py`, `upkeep_regimes.py`, `upkeep_catalog.py` |
| The shared algorithm | `adapters/upkeep_keys.py` (neutral; §5) |
| Map decode + projection | `mapping/map_source_runtime.py` (`dreame_*`, replica `RN0Y49XS`) |
| Contract tests | `tests/adapters/` — the brand is a case in the shared contract suite |
