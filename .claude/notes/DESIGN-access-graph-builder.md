# DESIGN — Access graph builder (one modal, click-driven)

**Status:** SUPERSEDED — the builder in §2 was REJECTED. Waves A and B shipped
and stand on their own; Waves C and D are dropped. See
[HANDOVER-access-graph-design-session.md](HANDOVER-access-graph-design-session.md)
for the reasoning, the measurements that killed it, and what shipped instead.
This file is kept as the record of the design that was considered.
**Origin:** `live:AGX-CLEAR-1`, and Chris's design call on `A5-AG-2` (2026-08-04) —
the graph is **all-or-nothing** by design; the fix is not to relax the block but to
make both of its exits reachable. Auto-suggestion from map geometry is **rejected**
(Chris: "no map suggestions", "we're not going to make it automatic").

---

## 0. What the graph MEANS (Chris, 2026-08-04)

It is a sketch of the house, drawn once. The dock is the **root**, and the
invariant is not "no loops" — it is **every room must be able to reach the dock**.
The robot leaves the dock, works outward, and must be able to come home; that
round trip is what the tree guarantees.

An edge is a **doorway**, and a doorway works both ways. The graph stores it
directed (parent → child) only to express which side you enter from. So
"reachable from the dock" and "can reach the dock" are the same statement here,
which is why the validator checks only the outward direction.

Shape, in Chris's terms — `A → B → C`, then `C → C1, C2`, then `C1 → C1-1`:

- **one way IN.** Each room has exactly one parent. That is the constraint.
- **many ways ON.** A room may lead to any number of rooms. `C` having both `C1`
  and `C2` is ordinary — fan-out is not a violation, which is why "Rooms Accessed
  From Here" is a list.
- **depth is free.** `C1-1` hanging off `C1` is just a longer chain home.
- **the way back is the parent chain, reversed.** Follow your one parent upward
  and you arrive at the dock. Nothing else needs storing.

Loop prevention is a CONSEQUENCE of this, not the goal. Note that single-parent
alone does not forbid a ring — `A → B, B → A` gives both rooms exactly one parent
— so `cycle_detected` remains a real check for callers who post arbitrary graphs.
What forbids it is single-parent PLUS everything hanging off the dock: a ring's
rooms take their one parent from inside the ring, so no edge from the tree can
reach them and the ring is a detached island.

## 1. The problem, precisely

Because the graph is a tree rooted at the dock, building it is N−1 parent
assignments — and nothing more.

Today that work is spread across N per-room modals, reached via
room editor → Access. The user must:

- know which room to open next (nothing lists what is still unplaced — the data
  exists as `unlinked_room_ids` on `get_access_graph_health`, but no surface shows it);
- open a room to discover it has nothing to offer;
- hold the tree in their head, because each modal shows one room's slice of it.

And the two exits the (now translated) start refusal names are asymmetric: *complete
it* is reachable room by room, *clear it* has **no service and no button** —
`services.yaml` registers no clear/reset access service, and the modal exposes
exactly four actions: `close-room-access`, `save-room-access`, `toggle-is-dock-room`,
`toggle-room-access-target`.

## 2. The flow

One modal, one column, taps only. Drag-and-drop is **rejected** — it does not work
on mobile and buys nothing over tapping the rooms that lead out of here.

1. **Pick the dock room.** All rooms listed; tap one. That is the root.
2. **"What leads out of *Hallway*?"** The remaining **unplaced** rooms appear as
   chips. Tap every room reached directly from there.
3. Each room just attached becomes the next question, breadth-first.
4. Placed rooms **leave the pool**. It shrinks visibly: *"4 of 11 placed."*

### Why this shape

Every invalid state becomes **unconstructible**, rather than constructible-then-explained:

| Issue the validator can raise | Why the builder cannot produce it |
| --- | --- |
| `self_reference` | a room is never in its own pool |
| `multiple_inbound` | a placed room has left the pool |
| `unreachable_from_dock` | you can only attach to a room already connected to the dock, so every room has a path home the moment it is placed |
| `cycle_detected` | only *unplaced* rooms are ever attached, so every edge points away from the tree and never back into it |
| `missing_dependency` | the pool empties only when every room has a parent |
| `missing_dock_room` | step 1 is the dock room |
| `duplicate_edge` | a target is tapped into exactly one parent's list |

So the Graph Issues panel stops being the teaching surface and becomes what it should
be: a fallback for legacy graphs, hand-edits, and YAML callers.

## 3. The dedupe (the point of this design)

The builder is **not** a second implementation. It is the same state machine with a
different presentation — but the current code cannot be reused as-is, because the
modal's accessors read *stored rooms* plus a **single-room draft**
(`_roomAccessRoomId` / `_roomAccessFields`). The builder holds a **whole-map draft**
where nothing is stored yet.

The seam is therefore a pure graph snapshot, and both surfaces become drivers over it.

**NEW `src/state/access-graph-model.js`** — pure, no DOM, no `this`, no storage,
unit-testable directly (the shape `coded-label.js` / `access-issue-label.js` /
`room-access.js` already follow):

```
graphFromRooms(rooms)                  -> {dockRoomId, grantsByRoom}
offerableTargets(rooms, graph, forId)  -> chips   // the ONE "who can X grant to?" answer
unplacedRooms(rooms, graph)            -> rooms with no parent yet
validateGraph(rooms, graph)            -> {valid, issues[]}      // whole-graph, coded
applyEdge / removeEdge / setDockRoom   -> a new graph (immutable)
graphToUpdates(graph)                  -> per-room {is_dock_room, grants_access_to}
```

Then:

- `accessEditableRooms()` keeps its name and contract — the modal, its bindings and
  `[RAC-1..15]` are untouched — and delegates to `offerableTargets` with
  `graph = stored graph + this room's draft`.
- `validateRoomAccessUpdate()` delegates to `validateGraph` with the same overlay.
  Its card-scoped issue codes (`scope: "card"`, A6-AGX-4) are unchanged, so
  `accessIssueLabel` and all 18 locale packs keep working untouched.
- The builder calls the same functions with `graph = the in-progress draft`.

One question, one owner. If the two surfaces ever disagree it is a bug in one
function rather than a drift between two copies.

## 4. Backend — one replace-all service

**NEW `eufy_vacuum.set_room_access_graph(vacuum_entity_id, map_id, dock_room_id, edges)`**
— response-capable, replace-all semantics for that map.

This is deliberately the **same service** that closes `live:AGX-CLEAR-1`: clearing is
this call with `dock_room_id: null` and `edges: []`. Build, rebuild, and clear are one
operation, which is why there is no separate `clear_room_access_graph`.

Why replace-all rather than N × `update_room_fields`:

- **atomic** — the map is never half-built on disk. All-or-nothing is then enforced at
  the storage layer instead of being defended by the UI.
- **one write, one notify** — N per-room saves means N validations, N summaries, N
  refreshes, and N chances to leave a partial graph if the browser closes midway.
- it touches **only** `is_dock_room` and `grants_access_to`. Rules, `enabled`, order,
  colours, profiles, `is_transition` are not this service's business.

**Response must answer "did this actually unlock me?"** — carrying `block_code_before`
and `block_code_after` from `access_graph_block_code`. This is the A6-AGX-1 lesson
applied: on a map with blocker rules, clearing the graph moves the user from
`incomplete_access_graph` to `access_graph_required_for_rules` — **still blocked**, with
a different message. A "clear to unlock" action that silently does not unlock is the
same remediation trap AGX-1 was about, and the response is where it gets caught.

## 5. Assumptions (Chris has not ruled — strike any of these)

1. **Free pool, not strict order.** "What leads out of Hallway" offers *all* unplaced
   rooms. The breadth-first walk is guidance, not a cage; someone who knows their home
   will jump around.
2. **No partial commit.** Save stays disabled with a live "4 of 11 placed" counter.
   The escape hatch is a **Clear** button in the same modal — the refusal's two exits,
   both finally one tap. Consistent with all-or-nothing.
3. **`is_transition` is orthogonal** and stays in the room editor. The tracker uses it
   to skip corridors for attribution (`mapping/tracker.py:495`); it is not read by
   `_validate_room_access_graph` and so is not a graph field.

## 6. Scope boundary

- **NOT** auto-suggestion, geometry inference, or any automatic completion — rejected.
- **NOT** drag-and-drop — rejected (mobile).
- **NOT** a change to the all-or-nothing semantics — that block is intentional and
  A5-AG-2's semantics half is adjudicated as refused.
- The per-room modal **stays**. It is the right tool for changing one relationship
  later; the builder is for building, rebuilding, and clearing.
- Every user-facing string goes through i18n at creation, all 18 packs. No new packs.

## 7. Waves

- **A — the seam.** `access-graph-model.js` + unit tests; repoint
  `accessEditableRooms` / `validateRoomAccessUpdate` onto it. Zero user-visible change;
  `[RAC-1..15]`, `[AIL-1..6]`, `[CL-1..10]` stay green. Proves the layer is real
  before anything is built on it.
- **B — the service.** `set_room_access_graph` + schema + `services.yaml` + docs +
  tests, including the `block_code_before/after` trap case. Closes
  `live:AGX-CLEAR-1` on the YAML side.
- **C — the builder.** Renderer + bindings over Wave A, committing through Wave B.
  Card-side i18n, styles in `src/styles/` only. **Opens SEEDED from the surviving
  graph, never blank** — the graph is drawn once, and the only thing that erodes
  it is a map rebuild: a newly discovered room arrives with no parent (the
  A5-AG-2 scenario), and `rooms/reconciliation.py:307` drops remapped targets
  that no longer resolve, orphaning whatever they led to. Neither is announced.
  Seeded, a post-rebuild repair is "place the one new room" rather than
  re-sketching the house, which is what makes "never touch it again" honest.
- **D — entry points.** Where the builder opens from (rooms view when blocked, Setup),
  and the Clear button.
