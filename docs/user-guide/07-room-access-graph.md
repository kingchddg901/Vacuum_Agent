## Room Access Graph

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

Each room in the "Rooms Accessed From Here" section is shown as a chip button. Click a chip to toggle whether this room grants access to that room. A highlighted chip means the link is active.

A room that is already claimed as a target by a different room is not shown as an available option. You cannot give two rooms the same outbound target.

When you have finished making changes, click **Save Access**. The Save button is disabled while there are unresolved graph issues.

#### Setting the dock room

In the **Dock Room** section, click **Set as Dock Room** to mark the current room as the dock room. The button label changes to **This is the Dock Room** while the toggle is on. Dock rooms have no inbound dependency requirements, so graph validation is skipped for them.

### What the health check shows

Before you can save, the card validates the proposed access graph. If there is a problem — for example, a room has no path back to the dock, or the graph would create a loop — the **Graph Issues** section appears in the modal listing one or more issue messages. The Save button stays disabled until all issues are resolved.

If the backend rejects the save after the local check passes, the error message from the backend appears in red below the graph issues area. Correct the relationship described in the error and try saving again.
