# 41 — Maintenance and the Dock

**Scope.** Consumable tracking and station actions: why the framework keeps a bookmark rather than
a counter, what the two clamps in the remaining-hours arithmetic each defend against, and the gate
that asked the wrong question about whether a run was happening.

The two halves share one property — **the device owns the state and we own a reference to it.**
Every design below is a consequence of not being the authority.

---

## 1. The framework does not own the counter

The device publishes a monotonic lifetime usage figure per component.
`maintenance/manager.py::reset_maintenance` does not zero anything: it **snapshots that figure**
as a new baseline, and `maintenance/manager.py::get_maintenance_remaining` subtracts.

Three consequences follow directly, and they explain most of the module:

- **A reset can fail for four distinguishable reasons** — no source entity declared, the entity is
  unavailable, its usage value will not parse, or it worked. A reset that cannot read the counter
  must not write a baseline, because a wrong baseline is worse than no reset.
- **`source_available` is reported beside the numbers**, so a component reading zero because
  nothing could be read is distinguishable from one reading zero because it is new.
- **The interval is ours and the usage is theirs.** The interval comes from the adapter's component
  catalog; only the usage crosses the boundary.

⚠ The other shipped brand inverts this. Roborock's consumables are **device-owned countdowns** with
no usage accumulator, so the device resets itself when its own button is pressed and the declared
intervals are advisory rather than consulted — see [24 §5](24-roborock-adapter.md). Two brands, two
ownership models, and the framework holds both without a brand check.

---

## 1b. DECLARATION is not EMISSION — which components a vacuum actually has

⭐ **No live doc stated this before 2026-09-14**, and the gap was load-bearing rather than
cosmetic: `maintenance_sources` appears nowhere in `docs/dev/`, doc 41 §1 said only that "the
interval comes from the adapter's component **catalog**", and
`docs/dev/37-the-entity-surface.md` — which owns the entity contract — carried no maintenance
content at all. It *was* documented once, at `docs/retired/dev/13-maintenance-manager.md`, and
retired without the successor picking it up. In the gap, the card moved to per-model routing and
the three entity platforms did not, so 876 (model, component) pairs minted entities for hardware
the model does not have.

Three different things, and they are not interchangeable:

| | what it is | where it lives |
|---|---|---|
| **DECLARATION** | every component a BRAND can ever have | `adapters/<brand>/maintenance_components.py` |
| **EMISSION** | the components THIS MODEL has, from its measured regime | `adapters/<brand>/upkeep_keys.py` → `<BRAND>_UPKEEP_KEY_GUIDES[regime]` |
| **STORAGE KEY** | the component id a user's interval is filed under | `data["maintenance"][vacuum][component]` |

**Every consumer reads the EMISSION.** The card's rows, the reset buttons, the interval numbers
and the remaining sensors all ask one shared predicate,
`adapters/upkeep_keys.model_has_component`, so "the card shows X" and "X has entities" are the
same statement rather than two that can drift.

**Why the regime and not the sensor.** A sensor's existence is not evidence of hardware, and
that is measured: `robovac_mqtt` gates its consumables on `supported_api_types` — a *protocol*
family — so any novel-protocol Eufy publishes a "Cleaning Tray Remaining" counter whether or not
it owns a tray, and its `water_level` entity is created on every such device and merely reads
`unavailable` without a station. Dreame gates on real capability flags; Roborock offers neither.
Two of three brands cannot answer the hardware question at all, so the only consistent source of
truth is the per-model regime — three measured facts, and ours.

**Why not the resolved source either.** `capabilities._rescue_maintenance_source` exists because
a declaration cannot predict what a device publishes (Dreame builds entities at runtime). That
cuts both ways: if a declaration cannot say what *will* resolve, what *did* resolve cannot say
what the hardware is. Keying the gate on `sources.get(component)` was proposed and parked for
exactly the hazard that implies — a sensor briefly missing would hide a panel. Regime membership
is static and cannot blink.

**Three states, not two.** `components_for_model` returns a frozenset, `REGIME_UNRESOLVED`
(`None`), or `NOT_REGIME_ROUTED`. An adapter with no regime table has said nothing about
hardware, so everything it declares stands. A regime-routed adapter that cannot place *this*
model has tried and failed — the hardware is unknown, so nothing guide-only is invented while
anything the device is actively reporting survives. Collapsing those two is a real defect, not a
tidy-up: it went red across six `test_maintenance_manager` cases on this gate's first run.

**The floor is five.** `filter`, `main_brush`, `side_brush`, `sensor` and
`omnidirectional_wheel` are emitted by all 754 models, so the gate can never take a brush or a
filter card off a model it recognises. `mop`, `cleaning_tray` and `mop_pad_holders` are the
regime-varying rows.

---

## 2. The two clamps guard opposite ends, and different causes

The arithmetic is two lines and both are clamped:

```
used_since_reset = max(current_usage - reset_snapshot, 0.0)
remaining        = max(interval_hours - used_since_reset, 0.0)
```

They are not the same defensive habit applied twice.

**The first clamp fires when the device's counter reads lower than our snapshot** — the counter
went *backwards*. That is reachable: the part was replaced through the device's own button, the
device reset its own counter, or the unit was swapped or re-paired. Unclamped, `used_since_reset`
goes negative and `remaining` exceeds the interval, so a brush would report as **better than new**.

**The second clamp fires when a component is simply overdue**, which is the ordinary case. Unclamped
it goes negative, and every percentage and status label derived from it inverts.

So one defends against a counter that moved the wrong way, and the other against time that kept
moving the right way. Removing either produces a different wrong answer, which is why both survived
from the pre-integration generator unchanged — and why the reason for there being two is worth
writing down, since the code shows only that they exist.

`maintenance/manager.py::maintenance_status` and
`maintenance/manager.py::replacement_status` are pure functions over those numbers, kept separate
from the arithmetic so labelling can change without touching the measurement.

---

## 3. The dock gate asked the dispatched question

`dock/manager.py::get_dock_action_status` decides whether wash, dry, stop-dry and empty-dust are
offered. It used to gate on the **dispatched** job states.

That is the wrong question for this gate, and nothing about the check looks wrong:

- An **app-started run** holds the slot at external status for its whole capture
  ([30 §1](30-external-runs.md)), so it was invisible to a dispatched-only check.
- Checking whether the vacuum is docked does not rescue it either — a **mid-run dock** for a
  recharge or a mop prewash is the documented normal case that the external-run capture
  deliberately holds the slot open through.

So every dock action reported itself available, the card offered them, and
`dock/manager.py::_async_run_dock_action` pressed the button **on a robot that was about to
resume.**

⚠ **And it corrupted the measurement on the way past.** The resulting dock event increments the
mop-wash counter, which the water amendment consumes as the count at finalization — so an action
offered by a wrong gate did not merely happen at a bad time, it poisoned the captured run's water
actuals.

The fix is a differently-named question rather than a wider condition:
`jobs/active_job.py::run_is_in_flight` is the owned answer to *is any run going*, and its docstring
names the distinction against the dispatched-only predicate explicitly. **A gate about the floor
has to ask a floor-level question**; widening a dispatched check case by case would have left the
next unanticipated slot state invisible in the same way.

---

## 4. Dock vocabulary is adapter-driven with no fallback

The state strings that recognise a wash, a dry or a dust-empty come from the adapter's declared
dock triggers, and an adapter that omits a trigger set gets **an empty set — no detection** rather
than inheriting the reference brand's vocabulary.

That is [23 §2](23-eufy-adapter.md)'s residual-default problem handled correctly at a site where
the tempting default was right there. Silence produces nothing rather than something borrowed.

The **event-type keys** are the opposite case and are owned by core, which is also correct — they
are framework vocabulary, not a brand's words. The recorded defect there is not the ownership but
the **copying**: the three keys are hand-written at three sites in one file, and the anchor on that
block says plainly that a module constant is the real fix and that deriving them from the adapter
would be the *wrong* one.

That distinction is the whole test from [33 §4](33-the-orchestrator.md) in miniature: whose word is
it. State strings are the brand's, so they are declared. Event-type keys are ours, so they are
owned — and being owned does not excuse being duplicated.

---

## 5. Common wrong assumptions

| assumption | reality |
|---|---|
| a maintenance reset zeroes a counter | it snapshots the device's lifetime counter as a baseline — §1 |
| the two clamps are the same precaution twice | one catches a counter running backwards, the other an overdue part — §2 |
| a component reading zero hours is new | it may be unreadable; `source_available` is the difference — §1 |
| every brand accumulates usage | Roborock publishes countdowns and resets itself; the declared intervals are advisory there — §1 |
| "is a job running" is one question | the dispatched question and the floor question differ, and a dock gate needs the second — §3 |
| a wrongly-offered dock action just runs at a bad time | it also increments a counter the water amendment reads at finalization — §3 |
| an adapter that omits dock triggers falls back | it gets an empty set and detects nothing, deliberately — §4 |

---

## Registries

[00b-invariants.md](00b-invariants.md) · [00c-replicas.md](00c-replicas.md)
