# 07 — Room Access Graph

The room access graph describes which rooms the vacuum must pass through on its way to other rooms. Think of it as a map of doorways: if the vacuum has to go through the hallway to reach the bedroom, the hallway "grants access to" the bedroom. The card uses this information when building a cleaning queue so it can order rooms in a sequence that the vacuum can actually reach without backtracking through locked paths.

### Why it matters

When you queue several rooms for cleaning, the card needs to know whether the robot can move directly between them or must travel through intermediate rooms first. The access graph encodes those dependencies. If the graph is incomplete or incorrect, the queue-building logic may produce an order the vacuum cannot follow, or the backend may reject the plan entirely.

Every map has exactly one **dock room** — the room that contains the charging station. The dock room is the origin of the access tree and has no inbound dependencies of its own.

### How to view the access graph

Open the room editor for any room. At the bottom of the room editor you will find an **Access** button. Clicking it closes the room editor and opens the room access modal for that room.

The modal has three sections:

- **Dock Room** — shows whether this room is marked as the dock room. Only one room on a map can hold this designation.
- **Rooms Accessed From Here** — shows every room this room unlocks. These are the outbound links you can edit.
- **Accessed From** — shows the room that grants access to this room. This section is read-only; to change it, open the access editor for the other room and adjust its outbound links there. This section is hidden when the current room is the dock room.

### How to edit access relationships

Each room offered in the "Rooms Accessed From Here" section is shown as a chip button. Click a chip to toggle whether this room grants access to that room. A highlighted chip means the link is active.

Two kinds of room are **not offered** as new targets, so you cannot construct an invalid link in the first place:

- A room that is already claimed as a target by a different room does not appear in the list at all — no room can be reached from two rooms.
- The dock room is never offered as a new target.

In both cases there is an escape hatch for links that *already exist*: a link this room has already saved stays visible and removable, even if it points at the dock room (its tooltip explains it can be removed but not re-added) or at a room that has since been deleted. A link to a deleted room shows as a **Missing Room \<id\>** chip — click it to remove the stale link.

When you have finished making changes, click **Save Access**. The Save button is disabled while there are unresolved graph issues.

#### Setting the dock room

In the **Dock Room** section, click **Set as Dock Room** to mark the current room as the dock room. The button label changes to **This is the Dock Room** while the toggle is on. Dock rooms have no inbound dependency requirements, so graph validation is skipped for them.

There is exactly one dock room, and the card enforces it before you can tap: once any room holds the dock, the button is disabled in every other room's access modal, with a note naming the holder ("*Kitchen* is the dock room. Release it there first."). Setting the dock somewhere else is not a move — you release it in the room that holds it first.

**Releasing the dock room clears the whole access graph for that map.** The access tree is rooted at the dock, so links without a root are meaningless. If any rooms currently hold links, the card asks you to confirm before proceeding (basic cleaning still works on a map with no graph, as long as no room has access rules — a blank graph only blocks runs once some room does).

The dock also gates the *first* link: on a map with no dock room yet, a save that changes links is refused with "Set a dock room before linking rooms. The dock room is the origin of the access tree." The ordinary first save is the dock plus its first children together.

### What the health check shows

Before you can save, the card validates this room's proposed outbound links against the rest of the graph. If there is a problem — a loop, a link to a room that no longer exists on the map, or (rarely, from a stale snapshot) a room already claimed by another room — the **Graph Issues** section appears in the modal listing one or more issue messages. Most of these are generic, plain-language sentences ("This access setup would create a loop in the room graph.", "All access links must point to rooms on the current map."); only the already-claimed-room message names the specific rooms involved (for example, "*Bedroom* already has an inbound link from *Hallway*. Each room can only be reached from one room."). The Save button stays disabled until all issues are resolved.

Completeness — whether every room has a path back to the dock — is deliberately **not** checked at save time: the graph has to be buildable one room at a time. Unreachable rooms are caught later, when a cleaning queue is built.

If the backend rejects the save after the local check passes, the error appears in red below the graph issues area, in the same plain-language style. This is a backstop for races the card's local check cannot see on its own — for example, two access modals open on different rooms fighting over the same target, or two dock-room changes landing one after the other. Correct the relationship described in the error and try saving again.
