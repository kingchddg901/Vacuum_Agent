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
filter card off a model it recognises. `mop`, `cleaning_tray` and `mop_pad_holders_dock` are the
regime-varying rows.

---

## 1c. The guide holds no words — the backend ships KEYS

⭐ **No live doc stated this before 2026-10-21.** It was documented at
`docs/retired/dev/13-maintenance-manager.md` and retired without the successor picking it
up — the same omission §1b records, in the same subsystem. `guide_regime` and
`__GUIDE_VER__` appeared in no live doc at all; `supported_guide_components` and
`guide_available` appeared only in the retired one.

**The backend carries no guide text whatsoever.** It resolves which guide applies and emits
KEY LISTS; the card turns keys into sentences. That is not an optimisation — it is the only
arrangement that can work, because the guide must render in the READER's language and the
reader's language is the card's globe, which is per-user and which the backend cannot see.
The backend knows the HA instance language and nothing else, so two people reading one card
in different languages would get the same words. See
[frontend/i18n-system.md § Guide on the card](frontend/i18n-system.md) for that half; this
section is the resolution chain only.

### The chain, in order

| step | input → output | where |
|---|---|---|
| 1 | vacuum → `model_code` | `_get_registry_model_code` — the **upstream device registry**, not our config |
| 2 | `model_code` → `guide_regime` | `upkeep_catalog["model_key_regimes"]` |
| 3 | `guide_regime` → `{component: {steps, notes}}` | `upkeep_catalog["key_guides"]`, from `adapters/<brand>/upkeep_keys.py` |
| 4 | that map → key lists per component | `maintenance/manager.py::_get_upkeep_item_guide` |

`_get_upkeep_model_meta` publishes the regime itself alongside two derived facts:
`guide_available` (`bool(key_map)`) and `supported_guide_components` (`sorted(key_map)`).
A model whose code resolves to no regime, or a regime with no entry for the component, gets
`None` — **there is no prose fallback and no generic guide.** An adapter that declares no
`key_guides` for a model has no guide, deliberately.

### Three contracts that look like details and are not

- **`frequency` is always `None` on a key guide.** By design: the only cadence the card can
  state honestly is the device's own countdown, which the sensor-backed rows already show in
  hours. The card renders a frequency line only when it has one.
- **`steps` and `notes` stay present and EMPTY beside `steps_keys`/`notes_keys`.** The key
  fields were added *additively*. A card that has not been rebuilt renders an empty guide
  instead of raising, and nothing reading the old fields has to tell a key from a sentence.
  Removing the empty lists is a breaking change to an un-upgraded card.
- **One body, three times.** `maintenance`, `replacement` and `display` each carry a copy of
  the same body, because a key guide draws no line between cleaning a part and replacing it —
  the steps are what a person does with their hands either way.

### Where the words are, and what makes an edit reach a browser

English lives in `src/i18n/guide-keys.js` — 42 authored sentences, **GENERATED**, bundled so
the resolver always has a synchronous fallback. The other 17 languages are served as
`custom_components/eufy_vacuum/frontend/guides/keys/<lang>.json` (42 keys each, with
`index.json` listing the available packs) and lazy-loaded by `src/i18n/guide-loader.js` from
`/eufy_vacuum/frontend/guides/keys`.

⚠ **`__GUIDE_VER__` is load-bearing and easy to mistake for dead weight.**
`scripts/build-card.mjs` hashes the whole guides directory (`hashDir(GUIDES_DIR)`) and
injects it as an esbuild `define`; `guide-loader.js` appends it to every pack URL. Without
it a translated guide edit does not reach a browser that has already cached the pack. The
static path is registered `cache_headers=False`, which covers the integration's own serving
but not what the browser already holds — the two are not substitutes.

⚠ **Do not hand-edit the key packs or `guide-keys.js`.** Edit the authoring source in
`authoring/guide-keys/keys_<lang>.json` and run `python scripts/sync-dreame-guide-keys.py`.
That source is IN the repository as of 2026-10-22 — until then it lived two directories
above the repo in `durable/`, beside the manual corpus, which made the 18 shipped packs
unreproducible from any other machine. `authoring/guide-keys/README.md` states the
provenance line: the sentences are authored, the notes cite manuals and never quote them.

### What a successor breaks

- Deleting `__GUIDE_VER__` — guide edits silently stop reaching cached browsers.
- Hand-editing a key pack — overwritten by the next generator run, with no warning.
- Adding a component to `maintenance_components.py` but not to the regime's `emit` — it is
  not emitted at all. `components_for_model` returns `frozenset(key_guides[regime])`, so the
  emitted set IS the guide map's keys: no row, no entities, no guide, and nothing says so.
  This is also why "emitted but guideless" cannot happen — the two cannot disagree. Measured
  2026-10-21: 0 empty-key rows across eufy 36 / roborock 38 / dreame 88 (regime, component)
  pairs.
- Adding a `model_code` without a `model_key_regimes` entry — the regime is UNRESOLVED, so
  the model keeps only components the device is reporting on and **loses every guide-only
  card** (`[MGT-3]`), not just its `guide_available` flag.
- "Simplifying" the empty `steps`/`notes` away — breaks un-rebuilt cards.
- Reintroducing a backend language choice — that is the exact design error the key system
  exists to undo, and it is not fixable by adding translations.

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
`dock/manager.py::_async_run_dock_action` fired the action **on a robot that was about to
resume.** (It said "pressed the button" until §4b; the control is whatever the adapter declares.)

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

**But the question those strings answer is "what does the dock_status STRING say", and a brand
may have no such entity.** Roborock has none — and declares no `dock_events.triggers` either, so
`_dry_states`, `_wash_states` and `_empty_states` are all empty on every one of them and every
gate reading them is inert. That is not a gap in the declaration; it is the declaration being
honest about a dock whose state is not one string. What such a brand declares instead is an
**action-scoped `extra_watches`** entry — the same `{event_type: [states]}` shape scoped to one
source, e.g. `{"action": "dry_mop", "triggers": {"last_dry_start": ["on"]}}`.

The cost of missing that: `stop_dry_mop` tested `dock_status not in _dry_states`, which on a
brand with no dock_status is **true forever**, so Stop Dry reported `not_drying` and was
unavailable for the whole life of the feature on every Roborock dock that can dry. An outside
contributor found it ([#76](https://github.com/kingchddg901/Vacuum_Agent/pull/76)). The first fix
compared the control's state to a hardcoded `"on"` in core, which worked and made this section
false; the gate now reads the adapter's own action-scoped declaration, the same one
`listeners/dock_events.py` already watches to count the event. **Two readers, one declaration** —
they cannot disagree about what drying looks like, and a brand that declares nothing still gets
no detection.

The **event-type keys** are the opposite case and are owned by core, which is also correct — they
are framework vocabulary, not a brand's words. The recorded defect there is not the ownership but
the **copying**: the three keys are hand-written at three sites in one file, and the anchor on that
block says plainly that a module constant is the real fix and that deriving them from the adapter
would be the *wrong* one.

That distinction is the whole test from [33 §4](33-the-orchestrator.md) in miniature: whose word is
it. State strings are the brand's, so they are declared. Event-type keys are ours, so they are
owned — and being owned does not excuse being duplicated.

---

---

## 4b. The dock declares how it is DRIVEN, not just what it is called

§4 is about the brand's *words*. This is about the brand's *wiring*, and it was the same mistake
one level down: the contract let an adapter name a dock control but not say how to operate it,
because the framework had already decided. `dock_events.action_buttons` was the key, the resolver
hardcoded `domain="button"`, and the dispatch hardcoded `("button", "press")`.

That is fine for exactly as long as every dock is buttons. Roborock's is not: wash, dry and empty
are **switches** (`mop_washing`, `mop_drying`, `dust_emptying`) and the device publishes no dock
button at all. The declaration surface could not express that, so no amount of declaring would
have helped — the domain was fixed in the resolver *and* in the send, which is two places to
forget and one of the ways `supports_zone_clean` ended up open at one end and unconnected at the
other ([24 §8](24-roborock-adapter.md)).

The key is now **`action_controls`**, and each entry is a *service-call description*:

```python
{"entity_suffixes": [...], "token_sets": [...],
 "domain": "button",   # default — every brand that shipped before this is unchanged
 "service": "press",   # default for button; REQUIRED for any other domain
 "data": {}}
```

Both the resolver and the dispatch read it through one helper, so they cannot disagree about what
a control is. The old name is the lesson: it was named for its first consumer and became a lie the
moment a second kind of consumer appeared.

**The pair that proves the shape.** On Roborock, `dry_mop` and `stop_dry_mop` are the *same entity*
with inverse services — `turn_on` / `turn_off`, upstream `APP_SET_DRYER_STATUS` 1 and 0. Under the
old schema that was unrepresentable. Here it is the same `entity_suffixes` twice with a different
`service`, and no carve-out. A future select-driven control is `{"domain": "select", "service":
"select_option", "data": {...}}` with no further schema change.

**`service` is required once a non-button domain is declared, and is never guessed.** "switch"
alone does not say `turn_on` or `turn_off`, and the pair above uses both on one entity — so a
default would be a coin flip on physical hardware, and on the dry pair a 50% chance of starting a
dryer someone asked to stop. The dispatch refuses and names the missing declaration.

**`token_sets` stay button-only.** The registry fallback they drive scans `button.{object_id}_`, so
running it for a switch could only return a wrong entity or nothing. A non-button control declares
`entity_suffixes`, which resolve through the shared act-path ladder (derived id → sibling suffix →
upstream `translation_key`) and so survive the localized install where this is needed most.

There is deliberately **no momentary-vs-stateful field**. One was drafted and dropped because
nothing would read it: the presence of `stop_dry_mop` in the declaration *is* the statefulness, and
a field no consumer reads is a preference, not a contract.

Covered by `[DC-1]`..`[DC-5]`. `[DC-3]` is the no-regression guard — an entry naming neither domain
nor service must still resolve a button, or the rename broke the two brands that already had dock
support.

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
| the backend picks the guide's language | it holds no guide words at all; it ships keys and the card resolves them in the reader's globe language — §1c |
| a model with no guide falls back to a generic one | it gets `None`; there is no prose fallback — §1c |
| `__GUIDE_VER__` is build noise | it is the cache-bust that makes a translated guide edit reach a browser — §1c |

---

## Registries

[00b-invariants.md](00b-invariants.md) · [00c-replicas.md](00c-replicas.md)
