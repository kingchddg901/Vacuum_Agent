# 18 — The Access Graph and Room Rules

**Scope.** Two questions asked of the stored room map: *can the robot reach this room* (the
access graph) and *should it clean this room right now* (rules against live entity state). Plus
the validation that decides whether an edit is allowed, and the two diagnostics the card reads.

**Nothing here writes a room.** `rooms/access_graph.py::AccessGraphManager` derives everything
from `data["maps"][vac][map_id]["rooms"]` on demand and never writes back into it — the one
assignment into a room dict builds a throwaway `candidate_rooms` copy to ask *what would this
edge break*. Its only persisted output is `room_rule_status`, written from core. Room identity,
CRUD and reconciliation are [17 — A Room's Identity](17-room-identity.md).

---

## 1. The gate judges the DELTA, not the graph

`rooms/access_graph.py::structural_issue_key` gives one violation a stable identity, the caller
snapshots the keys before an edit, and the refusal fires only on issues the edit **introduced**.

Absolute validation was the shipped behaviour and it does not work, because a structural
violation can genuinely pre-exist: `plan_migration` rewrites grants through an id remap and
de-dupes only *within* one room's list, never re-running the cross-room single-inbound check.
Under absolute validation one stored violation freezes the whole map — every subsequent edit is
refused for a problem the user did not just cause and, on that screen, cannot see.

> **Inside the issue key, `source_room_ids` is sorted and `rooms` is not**, and the asymmetry is
> deliberate. For `cycle_detected`, `rooms` carries the cycle **chain**, where order is meaning.
> Sorting it collapses two different cycles over the same room set into one key — so a newly
> created cycle matches the pre-existing one's key and is admitted as "already there".

---

## 2. The dock requirement is the exception

`A5-DOCK-1` is the one refusal in the function that is **not** delta-scoped, and it carries two
escape hatches.

Delta-scoping it would defeat it: "no dock room yet" is a *baseline* condition by definition, so
every edit would pass on exactly the maps the gate exists for. The hatches are what keep it
usable — without the first, a fresh map can never get its first edge, because the ordinary path
sets the dock and its first children in one save.

**`missing_dock_room` is deliberately absent from the structural set** while its mirror
`multiple_dock_rooms` is present. Adding it — the symmetric-looking fix — makes a blank graph
unsavable and destroys staged building. Completeness is enforced at **queue-build** time instead,
which is why refusing it at write time is the wrong place.

---

## 3. One owner for "do runs block on this?"

`AccessGraphManager::access_graph_block_code` answers it; `planning/run_plan.py` keeps its own
reason-to-message lookup. The split is the point — the *code* is centralised, the *English* is
not.

Leaving the inline `if/elif` in `run_plan` as the sole answer costs the distinction between a
**blank** graph, where all runs are allowed, and a **partial** one, where every run is refused.
Both produce exactly `[{"type": "missing_dock_room"}]` with an empty dock list, so a single
validator cannot tell them apart.

**`get_access_graph_health` also reports `unlinked_room_ids`** — the rooms that will *become*
`missing_dependency` the moment a dock room is set. A blank graph's only present issue is "no
dock room"; acting on that advice flips blank → partial and blocks every run. Reporting only what
is currently wrong makes the diagnostic's own remediation a trap.

**A user-facing issue is a CODE plus PARAMS**, with the English `message` kept unchanged beside
them and list-valued params never pre-joined. `message` is the documented response-service
surface that automations read, so it cannot move; pre-joining bakes an English list convention
into all 18 locales, which is why the card's resolver carries its own separator keys.

`access_graph_block_rooms` reads the **raw** validation issues, not the formatted ones, because
it runs inside the start path — which never formats. Routing it through the formatter would drag
an English-prose builder into the hot path. It returns an empty list for issues that name no
room, rather than a placeholder, so a refusal sentence can never name a room that does not exist.

---

## 4. Rules are tri-state

`AccessGraphManager::_room_rule_matches_known` returns `(matched, known)`. When the rule's entity
is absent or reads `unavailable`/`unknown`, **no operator runs at all** — the result is
indeterminate rather than false.

Two alternatives are named and rejected in the source. Treating a dropout as an ordinary string
value was the shipped behaviour, and the recorded failure is a live run cancelled because a door
sensor's battery died: a `not_equals` rule matched the dead sensor. Fail-closed-on-dropout by
string-matching the sentinels was rejected as the same mistake wearing a different sign.

**A rule is a statement about the world and cannot bind to ignorance.**

Two entry points sit on top of that. `_room_rule_matches` is the boolean plan-time wrapper where
indeterminate never matches; the raw `(matched, known)` pair drives the runtime report. Collapsing
them to one boolean means a cancel can fire on a rule that no longer matches with a *known* state,
because the runtime report is computed from a snapshot and the sensor may have recovered since —
the pre-action re-check is the only thing that catches it.

---

## 5. Writing the graph is replace-all

`set_room_access_graph` replaces the whole graph, **is** the clear operation when called with
neither dock nor edges, and commits by mutating the stored `rooms` dict in place rather than
rebinding it.

N per-room `update_room_fields` calls are rejected in the docstring: the map is observably
half-built between them, and a browser closed midway leaves it that way. The graph is
all-or-nothing by design. Rebinding is rejected because it strands every reference already held
to the original dict. A separate clear service is rejected because build, rebuild and clear being
one call is what keeps them consistent.

> ⚠ **The card does not use the service this argument is about.** `src/bindings/room-access.js`
> routes a normal Save through `update_room_fields`, one room at a time — the path the docstring
> rejects. The replace-all reasoning is sound and describes a service the primary consumer takes
> a different route around.

`set_room_access_graph` used to return two different shapes under one key. The refusal path
returned FORMATTED issues (`{code, message, params, room_ids}`); the success path handed back the
RAW validation issues (`{type, room_id, …}`). A consumer written against one broke on the other,
and the field name gave no warning.

Both exits now format. Formatted is the convention every other public reader in this subsystem
already follows — `_room_access_context`, `get_room_access_editor` and `get_access_graph_health`
all emit it — and the raw shape belongs to `_validate_room_access_graph`, which is internal. This
write path was the one place it leaked out.

Worth noting *why* the success path carries issues at all: an incomplete graph is **reported, not
refused**, so a successful write routinely returns a non-empty list. This was never an edge case
reachable only by contrivance — it is the ordinary result of building a graph in stages.

---

## 6. What actually reaches a user

Three gaps between what this subsystem produces and what anyone reads.

**`get_room_access_editor` has no consumer.** It is registered as a response service and
delegated from the manager, so an automation could call it — but nothing under `src/` does. Its
`reason_code` field is annotated as "the localizable half — the card resolver keys on it"; that
resolver does not exist.

**`update_room_fields`'s `no_dock_room` refusal renders untranslated in all 18 locales.** It
returns no `issues` array — only `reason_detail`, which is English prose. The card's error handler
falls through `issues → reason_detail → …`, so it stops at the prose and never reaches a
translatable code. Every other refusal on this path carries a code.

**`_names_edge`'s fallback is not the last resort its docstring claims**, and it is wrong in both
directions: `multiple_dock_rooms` *is* structural and is *not* handled by the reason ladder, so it
falls to the contentless `graph_illegal`; `missing_room` *is* in the ladder but is not structural.

---

## 7. Common wrong assumptions

| assumption | actually |
|---|---|
| validation refuses any graph carrying a structural issue | it refuses issues the *edit introduced*; a pre-existing one is admitted deliberately |
| the dock gate works like the others | it is the one refusal that is not delta-scoped, and it has two hatches |
| `missing_dock_room` is a structural issue | it is deliberately excluded, or a blank graph could never be saved |
| a rule against a dead sensor evaluates false | no operator runs at all — indeterminate is a third state |
| `set_room_access_graph`'s `issues` has one shape | refusal returns formatted issues, success returns raw ones |
| the card builds the access graph through `set_room_access_graph` | it saves through `update_room_fields`, one room at a time |
| `get_room_access_editor` feeds the room-access UI | nothing in `src/` calls it |
| `_issue_applies`'s `is not None` filter guards a live `None` in the contract | that branch was fixed; the comment ten lines above describes the fix in the past tense |
| every access-graph refusal reaches the user as a translatable code | `no_dock_room` reaches it as English prose |

---

## Registries

[00b-invariants.md](00b-invariants.md) · [00c-replicas.md](00c-replicas.md)
