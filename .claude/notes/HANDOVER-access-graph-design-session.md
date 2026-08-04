# HANDOVER — Access graph design session (2026-08-04)

A design review that started as one audit finding, proposed a redesign, **rejected
its own redesign**, and shipped four small changes instead. This records the
reasoning so nobody re-opens the settled parts.

**Read this before touching `rooms/access_graph.py`, `state/room-access.js`, or
the room-access modal.**

---

## 1. What the access graph IS

A sketch of the house, drawn once. The dock is the **root**.

The invariant is **not** "no loops" — it is **every room must be able to reach the
dock**. The robot leaves the dock, works outward, and must come home; that round
trip is what the tree guarantees.

An edge is a **doorway**, and a doorway works both ways. The graph stores it
directed (parent → child) only to say which side you enter from. So "reachable
from the dock" and "can reach the dock" are the same statement, which is why
`_validate_room_access_graph` only walks outward.

Shape, in Chris's terms — `A → B → C`, then `C → C1, C2`, then `C1 → C1-1`:

- **one way IN** — exactly one parent. This is the constraint.
- **many ways ON** — a room may lead to any number of rooms. Fan-out is ordinary;
  that is why "Rooms Accessed From Here" is a list.
- **depth is free.**
- **the way back is the parent chain, reversed.** Nothing else is stored.

### Why single-parent is not negotiable

`jobs/active_job.py:1818` (`_transit_rooms_between`) BFS's the graph to answer
*"which rooms does the robot pass through going from A to B?"*. With one canonical
path that has a definite answer. With two doors it has none, and every consumer
would have to pick arbitrarily. Blocker propagation depends on it, and so does
the learned transit-time model: a bimodal transit time is not a slow estimate,
it is a wrong one that reads as variance and quietly degrades confidence.

**So single-parent is what makes the feature computable, not a UI convenience.**

Residual, accepted: a house with a true circulation loop gets **over**-blocking —
the tree claims the robot transits room X when it could have gone the other way,
so a blocker on X refuses a destination it needn't. Conservative failure, the safe
direction. And the approximation is worst where it is cheapest (open plan:
contiguous segments, the "wrong" path is physically almost identical) and best
where it is expensive (real doors, real hallways).

---

## 2. SETTLED — do not re-open

| Question | Decision | Why |
| --- | --- | --- |
| Should a partial graph block the whole map? | **YES. Intentional.** | All-or-nothing: blank or complete, no half-configured state. A partially-honoured graph would run the vacuum through doors the user believed were governed. `A5-AG-2`'s semantics half is adjudicated REFUSED — the MEDIUM→HIGH regrade rested on "the exclusion is strictly safer than the block", which is the assumption being rejected. |
| Auto-suggest the graph from map geometry? | **NO.** | "No map suggestions." "We're not going to make it automatic." |
| Drag-and-drop tree builder? | **NO.** | Doesn't work on mobile, and buys nothing over tapping the rooms that lead out of here. |
| One modal that lists every room and builds the tree? | **NO — designed, then rejected.** | See §3. |
| Re-root the tree when the dock moves? | **NO.** | "If you made a mistake there, you made a mistake." Releasing the dock CLEARS the graph instead. |
| Grey out claimed rooms instead of hiding them? | **NO.** | Hiding is deliberate and better: the pool is only ever things you can actually do. |

---

## 3. The builder that was designed and rejected

A click-driven wizard: pick the dock, then *"what leads out of Hallway?"*,
breadth-first, placed rooms leave the pool, "N of M placed". Fully specced. Then
killed, by Chris's argument and three measurements.

**Why it lost:**

1. **It asks the identical question.** *"What leads out of Hallway?"* is what the
   per-room modal already asks. The wizard was never more intuitive — it only
   fixed the *order*.
2. **The problem is already decomposed.** Single-parent means each assignment is
   independent: nothing you pick in the Hallway changes what is *correct* in the
   Entryway. The builder re-composed a problem the data model had taken apart.
3. **The cost is not N.** Only rooms that *have children* need visiting; leaves
   are placed by their parent. Measured on both live maps: **10 rooms → 4 modals**,
   depth 3, and Hallway alone places 4 rooms (40% of the house) in one visit.
   Worst case is a house shaped like a train carriage. That house doesn't exist.
4. **The one thing it bought already exists.** "Which room next?" is answered by
   `_renderOrphanedRoomsPanel` ("Access not set" + a chip per unplaced room), and
   by unplaced rooms appearing as the *selectable* chips in any room's modal.
5. **Repair beats cold start.** Cold start happens once per map; repair recurs
   (a rebuild adds a room). The per-room modal is better at repair, and a wizard
   for a one-room fix is absurd.

**Measured pool reduction, replayed against Chris's live setup walkthrough** —
the model in `state/access-graph-model.js` predicts every screenshot chip-for-chip:

```
Dining (cleared)              9 offered
Dining (dock + 2 picked)      9 offered, 2 selected
Living Room                   7 offered
Entryway                      5 offered
Hallway                       4 offered
                              -> unplaced: []
```

---

## 4. What DID ship

### Wave A — `376f644` — `src/state/access-graph-model.js`

Pure model over an explicit snapshot `{dockRoomIds, grants}`. Seven prototype
methods deduped into it (`_normalizeRoomReferenceList`,
`_buildRoomAccessAdjacency`, `_roomAccessGraphHasCycle`, `_buildClaimedTargetMap`,
`validateRoomAccessUpdate`, `orphanedRooms`, `accessEditableRooms`), all names and
contracts unchanged. **Net −186 lines.** Zero user-visible change.

Built for the rejected builder — kept because it is worth having anyway: it is
why every claim in this document could be checked against Chris's real rooms in
seconds instead of guessed.

- `dockRoomIds` is a **list**, not a scalar. Two dock rooms is a state the
  validator genuinely raises; collapsing it would offer the second dock room as
  an ordinary target on an already-invalid map. `[AGM-8]`.
- `[AGM-12]` pins that modal-shaped and builder-shaped calls agree on the same
  graph.

### Wave B — `7a9c493` — `eufy_vacuum.set_room_access_graph`

One atomic replace-all: dock + every edge. **Build, rebuild and clear are the same
call** — clearing is it with no dock and no edges — so there is no separate clear
service to drift against.

Why replace-all: `[SAG-1]` pins it. **Blank and complete are BOTH unblocked** — an
empty graph is the permissive state — and the blocked state is *partial*, in
between. Built room by room the map walks through the blocked state on its way to
the unblocked one, and a browser closed midway leaves it there.

Response carries `block_code_before`/`after` because **clearing does not always
unlock**: on a map with blocker rules it swaps `incomplete_access_graph` for
`access_graph_required_for_rules` `[SAG-4]`. **Callers check `blocked_after`, not
`ok`.** That is A6-AGX-1's remediation trap on the write side.

### `A5-AG-2` — `423fad8` — the refusal names its rooms

`access_graph_block_rooms` + `reason_params` (rooms as an unjoined LIST). Two card
defects found while verifying reachability: `startBlockedReason` preferred the
English `message` over the machine `reason` (so **every** backend refusal was
untranslatable by construction), and the reduced-run panel rendered raw warning
codes — users read the literal string `rooms_blocked` under a "Warnings" heading.

### `A5-DOCK-1` — `14f496a` — the two guards

- **Dock gate.** Links without a root are meaningless, and were savable.
  `missing_dock_room` has been absent from the structural set since v0.9.0 while
  its mirror `multiple_dock_rooms` was always in it. NOT delta-scoped ("no dock
  yet" is a baseline condition); two escape hatches, both pinned: a save that
  SETS the dock passes `[AG-17b]`, and a save that changes no links passes.
  Only access edits are gated `[AG-17c]`.
- **Second-dock guard.** `Set as Dock Room` was live in four of six screenshots
  while Dining held it — `roomAccessValidation` short-circuits to valid for any
  dock room, so the card green-lit a save the backend then refused.
- **Releasing the dock clears the graph**, through Wave B's service.

---

## 5. The loop question, answered properly

Chris's rules, checked against the code:

1. *Can't select a room twice* — **real**, prevents two parents.
2. *Can't select parents* — **real in effect**, because a parent is always claimed
   by *its* parent. Except a chain root, which has none.
3. *Can't build before picking a dock* — **was not implemented.** Now is.

The gap was where 2 and 3 both miss. In `A→B→C→A` **every room is selected exactly
once**, so rule 1 is satisfied; A was never selected *at all*, so nothing hid it.
A ring has no room with zero ways in — nothing anchors it. Proven live:

```
A→B→C, no dock set
claimed        -> [["2","1"], ["3","2"]]   A is claimed by nobody
C(3) may select -> ["1"]
if tapped       -> ["cycle"]
```

**On a COMPLETE graph a loop is not constructible** — verified against both live
maps, every pool contains only its own children. The window was only ever open
mid-build. Chris closed it by habit (dock first); the gate closes it by rule.

`cycle_detected` stays for YAML callers `[SAG-5]`.

---

## 6. Still open

1. **Empty-state wording.** `room_access.no_other_rooms` = *"No other rooms are
   available on this map."* renders on a complete graph — i.e. on success, on a
   map with nine other rooms. Two conditions share one string: genuinely-only-room
   vs everything-already-placed. **Post-setup only** — every modal during the
   build had rooms to offer, so it is an inspection-time bug, not in the setup path.
2. **The help text and user doc describe behaviour that does not happen.**
   `room_access.accessed_from_here_help` and
   `docs/user-guide/07-room-access-graph.md:25` both say claimed rooms are *shown
   greyed out and disabled*. The code **hides** them. Hiding is the decision; the
   words should match it.
3. **Dead render path.** `claimedBy` has been hardcoded `null` since v0.9.0, so
   the renderer's `disabled` branch, `evcc-room-access-chip--claimed`, and
   `room_access.claimed_by` — **translated into 17 packs plus English** — have
   never once run. Nobody has ever seen that string in any language. Delete it,
   or it reads as live code to whoever comes next.
4. **The fixture.** Chris's real 10-room walkthrough (9→7→5→4→0) as a regression
   test. Better than anything invented, and it would catch any change to what the
   pool offers.
5. **Map rebuild erodes the set-once sketch.** A newly discovered room arrives
   with no parent (→ partial → blocked), and `rooms/reconciliation.py:307` drops
   remapped targets that no longer resolve, orphaning whatever they led to.
   Neither is announced. The remap itself is sound (fresh list per room, no
   mutate-while-iterating — it does not have `DR-ONB-1`'s bug).
6. **Not deployed.** `set_room_access_graph` is committed but not on the live box,
   and a new service only registers on an HA restart. The card bundle is also
   unbuilt.

---

## 7. Reusable lessons

- **A guard that EXISTS reads as complete.** `multiple_dock_rooms` was structural,
  `missing_dock_room` was not. The guard for "too many" got written and the one
  for "none" didn't, and the author remembered building both. **Diff a predicate
  against its mirror image, not just against its copies.**
- **Check the belief against the code, with a receipt.** Three separate times a
  remembered behaviour ("I block selecting parents", "claimed rooms grey out",
  "you can't build without a dock") diverged from the implementation. Each was
  settled in one command against live data, not by argument.
- **Design docs should record what was REJECTED and why.** Half this document is
  refusals. Without them the builder gets re-proposed next quarter.
- **A test that "passes" by comparing English to English proves nothing.** `[CL-8]`
  had to load the shipped locale packs, because `translate()` only knows English
  outside the browser.
