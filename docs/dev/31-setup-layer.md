# 31 — The Setup Layer

**Scope.** How a vacuum becomes configured and stays configured: the step machine the adapter
declares, the drift signal that reopens a finished step, and the gate in front of every destructive
operation. Room identity itself is [17 — Room Identity](17-room-identity.md); what a brand declares
is [22 — The Adapter Contract](22-adapter-contract.md).

Setup is not a wizard that runs once. It is a set of predicates that are continuously re-evaluated,
and any of them can go false again while the system is running.

---

## 1. The step machine is declared, not hardcoded

`setup/drift.py::SETUP_STEP_IDS` is a **closed** enum of the steps the framework understands, and
each brand declares which of them apply through its adapter's setup block. The framework iterates
whatever the adapter requires rather than assuming a map must be imported before rooms can be
saved.

The split of authority is worth noting because it is the opposite of the usual one:

- **The adapter chooses which steps apply.**
- **The framework owns what each step means**, including its display label —
  `setup/drift.py::SETUP_STEP_LABELS` is explicitly not adapter-overridable.

A brand that could rename a step could make two installs disagree about what "save rooms" means
while both reported the same state. Choosing from a closed set cannot.

`setup/status.py::get_setup_status` evaluates the whole machine for the panel. It carries legacy
fields alongside the data-driven ones for the card that has not yet moved — a compatibility surface
with an expiry, not a second source of truth.

---

## 2. Every operation reports; none of them raise

`setup/workflow.py::add_vacuum` and `setup/workflow.py::import_active_map` are the two atomic
operations, and both return an explicit result: a status of success, already-done, blocked or
error, a message, an operation payload, and **`next_actions`** — what to do next.

Three properties are stated as requirements rather than emerging from the code: it never raises, it
never silently no-ops, and it always tells the caller what to do next.

`already_done` is the one carrying the most weight. A setup step invoked twice is a normal event —
a user clicks again, a card reloads, a service is called from an automation — and collapsing that
into either success or error loses the distinction between *it worked* and *it was already true*.
The panel needs both to render honestly.

---

## 3. Drift is what reopens a finished step

The signal that `save_rooms` has gone stale is disagreement between the vacuum's reported rooms and
the configured ones. `setup/drift.py::compute_room_drift` returns that snapshot in four parts:
in-sync, new rooms, removed rooms, and **transiently missing** — a category that exists precisely
so the third can be distinguished from the second.

`setup/drift.py::update_drift_history` runs on every discovery pass, incrementing missing-pass
counters and refreshing last-seen stamps. The thresholds are read per brand through
`setup/drift.py::get_discovery_cadence`.

**The two directions are deliberately asymmetric:**

| | passes required | why |
|---|---|---|
| a **new** room | one — immediate | a room that appears is a fact; showing it early costs a glance |
| a **removed** room | three consecutive misses | a room that vanishes is usually an API glitch, and announcing a removal invites the user to act on it |

The asymmetry follows the cost of being wrong, not a preference for caution. A premature "new room"
prompt is noise; a premature "room removed" prompt asks someone to clean up something that is still
there. Both floors are clamped to at least one pass, so a brand cannot declare a zero-pass cadence
and get instant removals.

---

## 4. A rejection belongs to one map, because ids do

`setup/drift.py::reject_rooms` hides a phantom room id the vacuum reports but which does not exist.
It is scoped to a single map, and the reason is a defect that shipped.

Rejection was stored as one flat list per **vacuum**, while the thing being rejected is per **map**.
Eufy reissues room ids from one on every map, so id 3 downstairs and id 3 upstairs are different
physical rooms. Rejecting a ghost downstairs therefore made the **real room upstairs
unconfigurable — permanently, and silently**, because a rejected id never appears in `new_rooms`
for anyone to notice. Nothing in the record said which map a rejection was made on, so nothing
could tell the two apart.

`setup/drift.py::rejected_room_ids` is the single reader, and it resolves **two backings on
purpose**:

- the per-map store, which every new rejection is written to and which applies to its own map only
- the **legacy flat list**, which still applies to every map

Keeping the legacy list broad is the interesting half. A legacy id genuinely carries no map, and
inventing one would be a guess — and it also matches what the user meant, because those entries
were recorded when only one map existed, so "every map" and "the map I was looking at" were the
same set. It is read but never appended to, so the ambiguity is frozen rather than growing, and
`setup/drift.py::unreject_rooms` is the way out of a legacy entry that blocks a real room upstairs.

### The reporting superset is the wrong input for a decision

Calling the resolver without a map unions every map's rejections. That is a legitimate answer to
"what has been rejected anywhere on this vacuum" and the right thing for a whole-vacuum status
read.

⚠ **It is the wrong input for any decision about a specific room**, because over-reporting here
hides a real room — which is the original defect reproduced through the reporting path. Every
production caller passes a map. A new caller that omits it will look correct, compile, and
resurrect the bug.

---

## 5. Destructive operations are gated by the backend

`setup/protection.py::evaluate_map_protection` assigns one of three levels, and **the backend is
the single source of truth** — the panel only displays what it is told:

| level | gate |
|---|---|
| normal | one click |
| elevated | a confirmation click |
| high | a typed token that must match the map's display name exactly |

Putting the level in the backend means the same rule applies to a service call from an automation
as to a button in the card. A protection level the panel computed would protect only the panel.

`setup/delete.py::delete_map` evaluates protection before touching anything, and refuses with a
`requires_confirmation` result rather than an error when a token is needed and absent — the same
report-don't-raise contract as §2.

**Deletes are integration-only and never touch upstream cloud data.** The scope of the destructive
operation is the integration's own record of a map. That boundary is what makes the protection
levels a proportionate answer rather than an insufficient one.

---

## 6. Common wrong assumptions

| assumption | reality |
|---|---|
| setup completes once | every step is a predicate that is continuously re-evaluated and can go false again — §3 |
| an adapter can define its own steps | it selects from a closed set; the framework owns the semantics and the labels — §1 |
| a missing room means a removed room | it means transiently missing until it has been missed three consecutive passes — §3 |
| new and removed rooms are symmetric | they are not, and the asymmetry follows the cost of a wrong prompt — §3 |
| rejecting a phantom id is harmless | before it was map-scoped it silently disabled the same id on every other map — §4 |
| the unscoped rejection read is a convenient default | it is a reporting superset, and using it for a per-room decision reproduces the defect — §4 |
| the card enforces confirmation | the backend does; the card renders it — §5 |

---

## Registries

[00b-invariants.md](00b-invariants.md) · [00c-replicas.md](00c-replicas.md)
