# 03 — The Data Model

**Scope.** Everything this integration persists, in one place: the two stores and why they are not
alike, the store's real key set as opposed to its declared one, the identifiers that address it,
and which of it is the only copy. Per-subsystem detail lives with each subsystem; this is the map.

Read [01 — Architecture Overview](01-architecture-overview.md) first for the layers.

---

## 1. Two stores, and the split is about write shape

| | **the store** | **the tree** |
|---|---|---|
| where | one Home Assistant store document | `config/eufy_vacuum/` |
| holds | configuration and current state | history and derived statistics |
| written | **whole, every time** | per record |
| grows | with your rooms and maps | with every run, forever |
| deleted with the integration | yes | **no** — [39 §5](39-the-entry-point.md) |

A single document rewritten on every change is exactly wrong for a growing history, and exactly
right for configuration you want atomic. That is the whole reason there are two, and it is why a
new subsystem should ask which shape its data has before choosing where to put it.

Mechanics: [32 — The Store](32-the-store.md) and
[26 — The Learning Record Store](26-learning-record-store.md).

---

## 2. The store's declared schema is a minority of its real one

`core/storage.py::async_load` returns **eight** top-level keys for a fresh install:

`vacuums` · `maps` · `theme` · `analytics` · `maintenance` · `dock_events` · `onboarding` ·
`error_tracker`

**A live install carries twenty-four.** Measured by reading the store on the reference install
rather than by grepping for writers — the sixteen the loader does not declare are:

`active_jobs` · `battery` · `capabilities` · `discovery` · `entity_overrides` ·
`learning_pending_runs` · `learning_processing_enabled` · `migrations` · `payloads` · `profiles` ·
`queue` · `room_history` · `room_rule_status` · `run_profiles` · `setup_progress` ·
`_pending_run_steps`

⚠ **Neither the loader nor a grep for writers is the schema.** Reading `async_load` tells you what
a *fresh* install looks like. Grepping for `data.setdefault(…)` — the obvious second source — finds
twenty of the twenty-four and silently misses `entity_overrides`, `migrations`, `profiles` and
`run_profiles`, because not every key is created that way.

**The only authority is a live store.** That is worth knowing before trusting any list of keys,
including this one: it is a measurement of one install on one date, and a subsystem that has never
run there has never created its key.

Only one key gets a defensive backfill on load rather than lazy creation: the error tracker's,
added for installs that predate it. That is the pattern the other sixteen do not follow.

---

## 3. The store nests the same way almost everywhere

Most sections key **per vacuum, then per map**:

```
maps
 └─ vacuum.alfred
     └─ "2"                     ← map_id, always stringified
         ├─ metadata
         ├─ rooms
         │   └─ "5"             ← room_id, stringified at the boundary
         │       ├─ room_id     (int)   ─┐
         │       ├─ map_id      (str)    ├─ identity
         │       ├─ name / slug          ┘
         │       ├─ enabled / order
         │       └─ clean_mode · fan_speed · water_level · clean_intensity …
         └─ summary
```

Two conventions to know before reading any of it:

- **Ids are ints in code and strings in storage.** JSON has no integer keys, so every map and room
  id is stringified on the way in and coerced back on the way out. A comparison that skips the
  coercion silently never matches.
- **A room's settings are a mix of framework metadata and brand vocabulary**, and only the
  framework half may be defaulted without asking the adapter. Crossing that line stamped a brand
  axis onto every room of every brand ([33 §4](33-the-orchestrator.md)).

Room identity in full: [17 — Room Identity](17-room-identity.md).

---

## 4. The tree: one root per vacuum, six directories

```
config/eufy_vacuum/
├─ learning/<vacuum-slug>/
│   ├─ jobs/            completed-job records — and phase CHILDREN
│   ├─ phases/          break records: a wait or a charge is not a job
│   ├─ phased_jobs/     parents: the run a user actually started
│   ├─ learned/         room_stats · job_stats · jobs_index · accuracy_stats
│   ├─ exports/         jobs_flat.csv · rooms_flat.csv
│   └─ live/            last_job_snapshot · incomplete_run · trouble_rooms
├─ maps/                uploaded map images, per variant
└─ fonts/               drop-in user fonts — [45 §5](45-the-shared-layer.md)
```

Three record kinds live here, each carrying an explicit `record_type` rather than being identified
by its directory — which is what lets one check refuse a non-job wherever the file came from.

**A phase child stays an ordinary job record in `jobs/`.** The two new directories hold new record
*kinds*, not a new kind of job, so every existing reader of `jobs/` kept working when phased runs
arrived ([26 §3](26-learning-record-store.md)).

---

## 5. Three of the identifiers are names, and names change

This is the hazard the data model has and does not announce.

| identifier | shape | stable? |
|---|---|---|
| `map_id` | **brand-dependent** | **not on every brand — see below** |
| `room_id` | device-assigned int | **renumbers on re-segment** — [17](17-room-identity.md) |
| `vacuum_entity_id` | an HA entity id | **user-renameable** |
| `slug` | derived from the room's name | **changes when the room is renamed** |

⚠ **`map_id` is a number on one shipped brand and a display NAME on the other.** Measured on the
reference install: the Eufy vacuums key on `'7'`, `'11'`, `'12'`; the Roborock keys on
`'Main floor'`. On that brand the map id is a user-renameable name, and it is the **first**
component of the learning key — so renaming a map in the vendor app orphans the learned statistics
of **every room on it at once**, which is strictly worse than renaming one room.

The last three are used as **storage addresses**:

- the tree's per-vacuum directory is derived from the vacuum's entity id — and so are **seventeen
  sections of the store**, `maps` and `run_profiles` among them. Renaming the vacuum entity strands
  the configuration and the history together, and the record builder then creates a fresh empty one,
  so the vacuum returns as brand new ([26 §7](26-learning-record-store.md));
- the learning key is `map_id::slug::…`, so renaming a **room** files its future runs under a new
  key while its past stays under the old one ([28 §2](28-learning-statistics.md));
- and on a brand whose map id is a name, renaming the **map** does the same to every room on it at
  once.

A room rename is not silent about the *event* — reconciliation detects it and shows it to the user
— but **nothing rekeys the stores**, so the history stays addressable only by a name nothing will
ask for again. A vacuum rename and a map rename are not even detected.

Room ids renumbering is the hazard that *is* handled: identity is carried by slug, and the device's
current id is re-resolved at dispatch ([42 §1](42-the-send-side.md)). The design that fixed the
unstable id introduced the unstable name.

---

## 6. What is the only copy, and what can be rebuilt

Worth knowing before deleting anything, and before assuming a value is authoritative.

**Authoritative — the only copy:**
`maps` (rooms and their settings) · `vacuums` · `theme` · `setup_progress` · `onboarding` ·
`maintenance` reset baselines · every record under `jobs/`, `phases/` and `phased_jobs/`

**Derived — reproducible from the above:**
`learned/` in full ([28](28-learning-statistics.md)) · `exports/` · `queue` · `payloads` ·
`capabilities` · `discovery` · `room_history`

The derived half is why a corrupt statistics file is recoverable for a **reader** and fatal for a
**writer**: the reader can rebuild it, so it may proceed; the writer must never overwrite the
evidence that a rebuild would have used ([32 §4](32-the-store.md),
[26 §4](26-learning-record-store.md)).

⚠ **`live/` is neither.** Its three files are single-overwrite scratch — the newest snapshot, the
most recent incomplete run, the running trouble-room counters. Losing them costs a prompt, not
history; but they are also not rebuildable, because nothing keeps what they summarised.

---

## 7. Common wrong assumptions

| assumption | reality |
|---|---|
| the schema is in `async_load` | a live install carries 24; grepping for writers finds only 20 — §2 |
| `map_id` is a stable device id | it is a display NAME on one of the two shipped brands — §5 |
| ids are integers in storage | JSON has no integer keys; every id is stringified at the boundary — §3 |
| the store and the tree are two halves of one thing | different write shapes, different lifetimes, and only one is deleted with the integration — §1 |
| a phase is a new kind of job | children are ordinary job records; the parents and breaks are new record *kinds* — §4 |
| room ids are the risky identifier | they renumber and that is handled; the unhandled ones are the two that are **names** — §5 |
| renaming is caught, so it is handled | the event is detected and shown; nothing rekeys the stores — §5 |
| the learned statistics are authoritative | they are derived and rebuildable, which is exactly why a reader may proceed past a corrupt one — §6 |

---

## Registries

[00b-invariants.md](00b-invariants.md) · [00c-replicas.md](00c-replicas.md)
