# 37 — The Entity Surface

**Scope.** What the integration publishes to Home Assistant across six platforms: how a room's
entities are named, why that name cannot be parsed back apart, how entities are removed when a room
stops existing, and the one predicate that decides an entity is saying nothing. The services API is
[36](36-the-service-layer.md).

This is the half of the product that works without the card. An automation that reads a room's
cleaning-history sensor never calls a service, so these entities are a public contract in the same
way service names are.

---

## 1. Six platforms, one device per vacuum

The integration forwards to binary sensor, button, switch, select, number and sensor. Every entity
it creates is attached to a device built by
`entity_helpers.py::build_vacuum_device_info`, so a vacuum's rooms, buttons and counters group
under one device rather than scattering across the registry.

Entities are push-driven, not polled — they subscribe to the manager's notification channels from
[33 §5](33-the-orchestrator.md) and re-render when told.

---

## 2. A room entity's id is deliberately one-way

`entity_helpers.py::make_room_unique_id` joins the vacuum key, the map id, the room id and a suffix
with underscores. **That join is non-injective on purpose, and the file says so.**

The underscore appears *inside* vacuum keys, map ids and suffixes, so the result cannot be taken
apart again: `vacuum_alfred_2_…` is simultaneously vacuum `alfred` on map `2`, and vacuum
`alfred_2` on any map. There is no parser, and the comment states plainly that none may be written.

Two sanctioned ways to answer an ownership question exist instead, and neither dissects a string:

- `entity_helpers.py::entity_belongs_to` — ask the entity's live attributes
- `entity_helpers.py::unique_ids_for_map` — **rebuild** the ids this configuration should produce
  and compare forward

Accepting an ambiguous identifier and banning the inverse operation is the unusual half of this
decision. The alternative — a delimiter no component may contain — constrains vacuum names, map ids
and suffixes forever, to buy a parse that nothing legitimately needs.

---

## 3. The suffix set is closed, and a test counts the classes

`entity_helpers.py::ROOM_ENTITY_SUFFIXES` lists every suffix a room entity is built with, one per
room entity class, each annotated with the class it belongs to.

It has to be complete, because the deletion sweep reconstructs ids **from this tuple**: a suffix
missing here is a room entity that is created and never cleaned up. So the guard is not a comment
asking for diligence — a parity test **counts the room entity classes** and fails if the tuple has
fallen behind. Adding a class without its suffix goes red.

---

## 4. Removing entities is the complement of building them

Rooms disappear — a re-segment, a deleted map, a vacuum removed. The entities have to go with them,
and doing that by prefix was proven dangerous.

⚠ **The naive version registry-deleted a sibling vacuum's entities.** A prefix scan for
`vacuum.alfred` swept everything belonging to `vacuum.alfred_2`, because the second name *is* the
first name plus a suffix. That was demonstrated, not theorised.

`entity_helpers.py::orphaned_active_job_unique_ids` is built so it cannot recur:

1. **The deletion set is the complement of a forward-built set.** The live pairs actually
   constructed this run are the input, and only ids absent from that set are candidates. A live
   entity can be selected only if this run failed to build it at all — so the failure mode is
   leaving an orphan behind, never deleting something real.
2. **The remainder after the prefix is re-checked**, so one managed vacuum's prefix cannot swallow
   another's id.

The second guard carries a detail worth reading twice. The prefix has already consumed the
underscore, so what remains looks like `active_job_5` — with no leading underscore. A guard written
to test for `_active_job_` there matches nothing and **silently never fires**. It was caught by a
test, not by review, which is the only way an inert guard ever is.

The general shape: **prefer a complement of what you built to a scan for what you want to remove.**
The first is wrong only by omission; the second is wrong by deletion.

---

## 5. One blank-state predicate, strictly stronger than the six it replaced

`entity_helpers.py::BLANK_STATE_VALUES` decides whether an entity's state carries any information,
and `entity_helpers.py::is_blank_state` is the single reader.

Hand-copied variants existed at **six sites in three different shapes**, and the differences were
not sloppiness — each tracked how *absent* reached the state machine through a different transport:

| leak form | comes from |
|---|---|
| `"None"` | a backend that stringifies Python's `None` |
| `"null"` | a JSON or JavaScript null from the map and websocket side |

**Each site caught the leak its own producer emitted and missed the others.** So unifying them was
not deduplication with a tidiness payoff — covering both forms made *every* caller strictly more
robust than it had been, and the union is safe because no legitimate entity state is the literal
string `None` or `null`.

That is the test worth carrying for any centralisation: if merging the copies only removes lines,
it is housekeeping and can wait. If merging them makes each call site handle a case it previously
missed, the duplication was hiding a defect at every copy.

---

## 6. Common wrong assumptions

| assumption | reality |
|---|---|
| a room entity's unique id can be parsed for its parts | the join is non-injective by decision and no parser may be written — §2 |
| ownership is decided by string matching | it is decided by live attributes or forward reconstruction — §2 |
| the suffix list is documentation | the deletion sweep reads it, and a parity test counts the classes against it — §3 |
| cleanup finds what to delete | it computes what it failed to build; deleting is the complement — §4 |
| a guard that reads correctly fires correctly | the prefix already ate the underscore; the guard matched nothing — §4 |
| the blank-state sets were duplicates | they were three different partial answers, and the union is stronger than any of them — §5 |

---

## Registries

[00b-invariants.md](00b-invariants.md) · [00c-replicas.md](00c-replicas.md)
