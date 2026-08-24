# 01 — Architecture Overview

**Scope.** The shape of the system: what the layers are, which direction they depend, where a run
travels, and which boundaries are load-bearing. Every claim here is a pointer — the detail lives in
the document named beside it.

Read this first if you are new. Read [03 — The Data Model](03-data-model.md) second; between them
they are the map, and everything from 05 onward is territory.

---

## 1. What this integration is

It manages **rooms, runs and learned timing** for a robot vacuum that some *other* integration
already talks to. It has no protocol client of its own and never has had one.

That single fact explains more of the architecture than anything else:

- The vacuum, its sensors and its buttons are entities owned by another component. Everything this
  system knows arrives through Home Assistant's state machine, and everything it does is a service
  call on somebody else's entity.
- Those entities **may not exist yet** when setup runs, which is why setup runs twice
  ([39 §2](39-the-entry-point.md)).
- Entity naming is a brand's convention rather than a contract, which is why there is a resolution
  and rescue layer ([23 §4](23-eufy-adapter.md), [34](34-capability-detection.md)).

---

## 2. Five layers, and which way they point

```
        Home Assistant
              │
   ┌──────────┴──────────┐
   │  entry point (39)   │   four contract functions; constructs everything
   └──────────┬──────────┘
              │
   ┌──────────┴──────────┐   services (36) ── entities (37) ── panels (44)
   │   public surface    │   the API a person or an automation actually touches
   └──────────┬──────────┘
              │
   ┌──────────┴──────────┐
   │  manager + store    │   one facade (33), one persistent document (32)
   └──────────┬──────────┘
              │
   ┌──────────┴──────────┐   runs · rooms · learning · mapping · maintenance · themes …
   │     subsystems      │   fifteen, constructed in order, each owning its own store section
   └──────────┬──────────┘
              │
   ┌──────────┴──────────┐
   │      adapters       │   the only layer that knows a brand's words (22 · 23 · 24)
   └─────────────────────┘
```

**Dependencies point down, and the bottom layer is data.** A subsystem asks the adapter registry
what this brand calls something; the adapter never calls back up. That is what makes a second brand
a declaration rather than a fork.

The one deliberate exception is documented at its site: the CV segmenter lives in the Eufy package
and is imported by the brand-agnostic engine registry, because its optional imaging stack makes a
lazy registration awkward ([25](25-eufy-segmentor.md)).

---

## 3. Where a run actually goes

A run is the spine of the product, and it crosses almost every layer:

| stage | what happens | doc |
|---|---|---|
| **select** | rooms are chosen and ordered; a queue is built | [05](05-run-live.md) |
| **gate** | can this start at all — map, rooms, lifecycle, blocked rooms | [05](05-run-live.md) · [36 §3](36-the-service-layer.md) |
| **resolve** | stored slugs become the ids this device uses *right now* | [42 §1](42-the-send-side.md) |
| **pre-call** | device-global settings pushed, after everything that can refuse has | [42 §2](42-the-send-side.md) |
| **dispatch** | the adapter's wire envelope goes out | [42](42-the-send-side.md) |
| **observe** | counters, current room, faults, pose — no geometry | [43](43-observing-a-run.md) · [35](35-the-fault-tracker.md) |
| **end** | one status machine, many authorities, exactly-once finalization | [06](06-run-end.md) |
| **record** | the durable job record is written | [26](26-learning-record-store.md) |
| **judge** | is this evidence worth learning from | [27](27-learning-eligibility.md) |
| **derive** | records become per-room statistics | [28](28-learning-statistics.md) |
| **predict** | the next run's estimate, and how confident it is | [29](29-learning-prediction.md) |

A run the user *did not* start enters at **observe** and leaves at **record** through a human review
step instead of a gate — [30](30-external-runs.md).

---

## 4. The four boundaries that carry the design

Most defects in this system have been a boundary crossed rather than a function written wrong. Four
are worth knowing by name.

### Whose word is this

Core owns keys; an adapter owns values. A framework default that happens to be one brand's word is
the failure mode this project keeps rediscovering — in core's fallbacks
([23 §2](23-eufy-adapter.md)), in a migration loop that stamped a brand axis onto every room of
every brand ([33 §4](33-the-orchestrator.md)), and in what is deliberately *not* configurable
([35 §5](35-the-fault-tracker.md)).

### Own it, or address it

State the system owns may be created on demand. State the **caller addresses** must be able to come
back *not found* — otherwise a typo becomes a durable record. The same rule was arrived at
independently four times ([45 §3](45-the-shared-layer.md)).

### Read, or write

A read is how a card discovers state, so it answers honestly with an empty shape and a reason. A
write refuses with a reason or succeeds carrying what it applied. The split is decidable by
inspecting the handler ([36 §3](36-the-service-layer.md)).

### Observe, or perturb

A diagnostic must not change what it reports ([40 §1](40-diagnostics-and-evidence.md)); a dock
action offered by a wrong gate corrupted the measurement of the run it interrupted
([41 §3](41-maintenance-and-the-dock.md)).

---

## 5. Two persistence layers, and they are not alike

| | the store | the tree |
|---|---|---|
| what | rooms, maps, profiles, themes, capabilities, adapter config | job records, learned statistics, captures, the pose ring |
| where | one Home Assistant store document | files under the config directory |
| written | whole, every time | per record, append-mostly |
| on removal | **deleted** | **kept, deliberately** |

The second row is why they are separate: a single document rewritten on every change is the wrong
shape for a growing history. The last row is a ruling — the tree is the user's own record of their
own home, and removing an integration is not obviously a request to destroy it
([39 §5](39-the-entry-point.md)).

Details: [32](32-the-store.md) and [26](26-learning-record-store.md).

---

## 6. What the front end is, from here

The card is a separate corpus ([frontend/](frontend/backend-contract-and-data-shapes.md)) and this
document does not describe it. Two facts about the boundary matter from the backend side:

- **The backend decides; the card renders.** Protection levels, start blockers and capability flags
  are computed here and displayed there, so the same rule applies to an automation as to a button
  ([31 §5](31-setup-layer.md)).
- **Except where the vocabulary belongs to the display layer** — system tag words and facet
  derivation live in the card on purpose, so the backend validates format and lets meaning resolve
  where the vocabulary lives ([38 §4](38-the-theme-library.md)).

---

## 7. How to find things

- **By subsystem** — the table in [README](README.md).
- **By rule** — [00b-invariants.md](00b-invariants.md), which names the constraints that bind
  across files, and the anchor each one is cited by.
- **By duplicate** — [00c-replicas.md](00c-replicas.md), for values that exist in more than one
  place on purpose.
- **By shape** — [03 — The Data Model](03-data-model.md).

> Retired documents under `docs/retired/dev/` are as-of-their-date records. Several are the only
> written account of their subsystem's history. Read them for orientation; do not treat them as
> current.

---

## Registries

[00b-invariants.md](00b-invariants.md) · [00c-replicas.md](00c-replicas.md)
