/**
 * ============================================================
 * ACCESS GRAPH MODEL — the one owner of every graph question
 * ============================================================
 *
 * The room access graph is a TREE: the single-inbound constraint means every
 * non-dock room has exactly one parent, so building a graph is N−1 parent
 * assignments and nothing more.
 *
 * Three surfaces ask questions about that tree — the per-room access modal, the
 * unconfigured-rooms panel, and (Wave C) the graph builder. They used to ask via
 * methods hung on the card prototype that read STORED rooms plus, for the modal,
 * a single-room draft. That works for one modal at a time and cannot work for a
 * builder holding a whole-map draft where nothing is stored yet.
 *
 * So the questions moved here and take an explicit GRAPH SNAPSHOT instead of
 * reading storage:
 *
 *     graph = { dockRoomIds: string[], grants: { [roomId]: string[] } }
 *
 * `dockRoomIds` is a LIST even though exactly one dock room is legal: two dock
 * rooms is a state the validator can genuinely observe (multiple_dock_rooms),
 * and collapsing it to a single id here would silently offer the second one as
 * an access target while the map is invalid.
 *
 * The modal passes "stored graph with this room's draft overlaid"; the builder
 * will pass its draft directly. Same functions, same answers — if the two
 * surfaces ever disagree it is a bug in one function rather than drift between
 * two copies.
 *
 * Pure: no DOM, no `this`, no storage, immutable graph operations. The proto
 * methods in state/rooms.js and state/room-access.js keep their names and
 * contracts and delegate here, so nothing above them moves.
 *
 * A room, as the card holds it: {id, name, isDockRoom, grantsAccessTo, mapId}.
 *
 * ============================================================
 */

/**
 * Normalize a room-reference list to trimmed non-empty strings.
 *
 * Room ids arrive as numbers from the backend, strings from the DOM, and
 * occasionally as a bare scalar rather than a list — comparing them without
 * this is how `1 !== "1"` bugs get in.
 *
 * @param {unknown} value
 * @returns {string[]}
 */
export function normalizeRefs(value) {
  if (value == null) return [];
  const list = Array.isArray(value) ? value : [value];
  return list
    .map((entry) => String(entry ?? "").trim())
    .filter((entry) => entry !== "");
}

/**
 * Snapshot the graph as the rooms currently store it.
 *
 * @param {Array<object>} rooms
 * @returns {{dockRoomIds: string[], grants: Record<string, string[]>}}
 */
export function graphFromRooms(rooms = []) {
  const grants = {};
  const dockRoomIds = [];
  for (const room of rooms) {
    const id = String(room.id);
    grants[id] = normalizeRefs(room.grantsAccessTo);
    // Every dock room, not just the first — see the header. Resolving a
    // double-dock map to one id here would hide half of an invalid state.
    if (room.isDockRoom) dockRoomIds.push(id);
  }
  return { dockRoomIds, grants };
}

/**
 * Return a new graph with one room's outbound edges replaced.
 *
 * This is how the modal overlays its draft onto stored state without mutating
 * either — and how the builder attaches a room to its parent.
 *
 * @param {object} graph
 * @param {string|number} roomId
 * @param {unknown} targets
 * @returns {object} a NEW graph
 */
export function withEdges(graph, roomId, targets) {
  return {
    ...graph,
    grants: { ...graph.grants, [String(roomId)]: normalizeRefs(targets) },
  };
}

/**
 * Return a new graph with the dock room set, or cleared with null.
 *
 * Always yields at most ONE dock room: this is the builder's entry point, and
 * the builder must not be able to construct the invalid state that
 * graphFromRooms has to be able to REPRESENT.
 *
 * @param {object} graph
 * @param {string|number|null} roomId
 * @returns {object} a NEW graph
 */
export function withDockRoom(graph, roomId) {
  return { ...graph, dockRoomIds: roomId == null ? [] : [String(roomId)] };
}

/**
 * target room id -> the room that claims it, ignoring one room's own claims.
 *
 * Enforces the single-inbound constraint in both directions: validation refuses
 * a second claim, and chip rendering greys the target out before the user can
 * make one.
 *
 * @param {object} graph
 * @param {string|number} excludeRoomId - the room being edited.
 * @returns {Map<string, string>}
 */
export function claimedTargets(graph, excludeRoomId = "") {
  const claimed = new Map();
  const exclude = String(excludeRoomId);
  for (const [roomId, targets] of Object.entries(graph.grants ?? {})) {
    if (roomId === exclude) continue;
    for (const targetId of targets) {
      // First claimant wins — duplicates are caught by validation.
      if (!claimed.has(targetId)) claimed.set(targetId, roomId);
    }
  }
  return claimed;
}

/**
 * Whether the graph contains a cycle.
 *
 * Edges pointing at rooms outside the graph are skipped rather than treated as
 * nodes: a stale reference is a `missing_room_references` issue, and letting it
 * masquerade as a cycle would report the wrong fault.
 *
 * @param {object} graph
 * @returns {boolean}
 */
export function hasCycle(graph) {
  const adjacency = graph.grants ?? {};
  const visited = new Set();
  const active = new Set();

  const visit = (roomId) => {
    if (active.has(roomId)) return true;
    if (visited.has(roomId)) return false;

    visited.add(roomId);
    active.add(roomId);

    for (const nextRoomId of adjacency[roomId] ?? []) {
      if (!(nextRoomId in adjacency)) continue;
      if (visit(nextRoomId)) return true;
    }

    active.delete(roomId);
    return false;
  };

  return Object.keys(adjacency).some((roomId) => visit(roomId));
}

/**
 * The rooms `forRoomId` may be offered as access targets, as renderable chips.
 *
 * Excludes self, and rooms claimed by ANOTHER room — but never a room this one
 * has ALREADY selected, in either case. That escape hatch is what keeps a stored
 * edge visible and removable rather than turning it into a ghost (A6-AGX-6).
 *
 * Selected-but-unknown ids are appended as missing entries carrying a code and
 * params rather than an English name: this module has no `t`.
 *
 * @param {Array<object>} rooms - every room on the map.
 * @param {object} graph - the graph to read, draft already overlaid.
 * @param {string|number} forRoomId
 * @returns {Array<object>} chips
 */
export function offerableTargets(rooms, graph, forRoomId) {
  const selfId = String(forRoomId);
  const selectedIds = new Set(normalizeRefs(graph.grants?.[selfId]));
  const claimedByOther = claimedTargets(graph, selfId);
  const dockRoomIds = new Set((graph.dockRoomIds ?? []).map(String));

  const known = rooms
    .filter((entry) => {
      const id = String(entry.id);
      if (id === selfId) return false;
      // A dock room is not OFFERED as a new target, but an edge into one that
      // already exists stays visible and removable — the same escape hatch the
      // claimed-by-another rule below has always had (A6-AGX-6).
      if (dockRoomIds.has(id) && !selectedIds.has(id)) return false;
      return selectedIds.has(id) || !claimedByOther.get(id);
    })
    .map((entry) => ({
      id: String(entry.id),
      name: entry.name,
      missing: false,
      available: true,
      claimedBy: null,
      isDockRoom: dockRoomIds.has(String(entry.id)),
    }));

  const knownRoomIds = new Set(known.map((entry) => entry.id));
  const missing = Array.from(selectedIds)
    .filter((id) => !knownRoomIds.has(id))
    .map((id) => ({
      id,
      name: null,
      nameCode: "room_access.missing_room",
      nameParams: { id },
      missing: true,
      available: true,
      claimedBy: null,
      isDockRoom: false,
    }));

  return [...known, ...missing];
}

/**
 * Rooms not yet placed in the tree: not the dock room, and nothing grants them
 * access.
 *
 * Returns [] while no dock room exists — the whole graph is unset then, and
 * listing every room as "unconfigured" is noise rather than a to-do list.
 *
 * `requiresAccessFrom` is derived, never stored, so it is computed here from
 * `grants` rather than read off an entity.
 *
 * @param {Array<object>} rooms
 * @param {object} graph
 * @returns {Array<object>} the room objects, in input order
 */
export function unplacedRooms(rooms, graph) {
  const dockRoomIds = new Set((graph.dockRoomIds ?? []).map(String));
  if (!dockRoomIds.size) return [];

  const placed = new Set();
  for (const targets of Object.values(graph.grants ?? {})) {
    for (const targetId of targets) placed.add(targetId);
  }

  return rooms.filter((room) => {
    const id = String(room.id);
    if (dockRoomIds.has(id)) return false;
    return !placed.has(id);
  });
}

/**
 * Who currently holds the dock, from the point of view of one room.
 *
 * The dock is the ROOT and there is exactly one. Once a room holds it, the
 * button must not be live in any other room (Chris, 2026-08-04) — setting it
 * elsewhere is not a move, it is a second dock, which the backend refuses as
 * `multiple_dock_rooms` AFTER the user has committed to the action. Answering
 * this before the tap is what turns that into an unconstructible state.
 *
 * Returns null when this room may take the dock: nobody holds it, or this room
 * already does.
 *
 * @param {Array<object>} rooms
 * @param {object} graph
 * @param {string|number} forRoomId
 * @returns {{roomId: string, name: string}|null} the blocking holder, or null.
 */
export function dockHeldByOther(rooms, graph, forRoomId) {
  const selfId = String(forRoomId);
  const holder = (graph.dockRoomIds ?? [])
    .map(String)
    .find((id) => id !== selfId);
  if (!holder) return null;

  const room = rooms.find((entry) => String(entry.id) === holder);
  return { roomId: holder, name: room?.name ?? null };
}

/**
 * Whether a save may proceed given the dock state.
 *
 * THE GATE. The access graph is a tree rooted at the dock, so links without a
 * root are meaningless — every room trips missing_dependency and the map is
 * `partial`, which refuses every run. Nothing stopped that being saved: the
 * card returned valid, and `missing_dock_room` is absent from the backend's
 * structural set (it has been since v0.9.0, while its mirror image
 * `multiple_dock_rooms` IS structural — too many docks refused, zero docks
 * allowed).
 *
 * TWO ESCAPE HATCHES, both load-bearing:
 *
 *  1. A save that SETS the dock passes even though no dock existed before —
 *     otherwise the very first save of a fresh map is refused and the graph can
 *     never be started. This is the ordinary path: dock plus first children in
 *     one save.
 *  2. A save that changes NO links passes. Removing the dock must stay possible,
 *     and it is the operation that clears the graph.
 *
 * @param {object} graph - the graph as stored, before this save.
 * @param {{isDockRoom?: boolean, changesLinks?: boolean}} save
 * @returns {{allowed: boolean, code: string|null}}
 */
export function dockGate(graph, save = {}) {
  const hasDock = (graph.dockRoomIds ?? []).length > 0;
  if (hasDock) return { allowed: true, code: null };
  if (save.isDockRoom) return { allowed: true, code: null };
  if (!save.changesLinks) return { allowed: true, code: null };
  return { allowed: false, code: "no_dock_room" };
}

/**
 * Validate ONE room's proposed outbound edges against the rest of the graph.
 *
 * Card-side pre-flight for the modal's Save button. Issues carry `scope: "card"`
 * because several of these codes mean something different when the BACKEND
 * raises them — see state/access-issue-label.js. `message` stays as the fallback
 * for a card release whose locale pack lacks the key.
 *
 * Completeness (no dock room, unreachable rooms) is deliberately NOT checked
 * here: it is enforced at queue-build time, and refusing a save for it would
 * make the graph unbuildable one room at a time.
 *
 * @param {Array<object>} rooms
 * @param {object} graph - WITHOUT the proposal applied.
 * @param {string|number} roomId
 * @param {unknown} proposedTargets
 * @returns {{valid: boolean, issues: Array<object>, normalizedGrantsAccessTo: string[]}}
 */
export function validateEdit(rooms, graph, roomId, proposedTargets = [], save = {}) {
  const targetRoomId = String(roomId ?? "").trim();
  const knownRoomIds = new Set(rooms.map((room) => String(room.id)));
  const rawRefs = normalizeRefs(proposedTargets);
  const duplicateRefs = rawRefs.filter((ref, index) => rawRefs.indexOf(ref) !== index);
  const uniqueRefs = Array.from(new Set(rawRefs));
  const selfReference = uniqueRefs.includes(targetRoomId);
  const missingRefs = uniqueRefs.filter((ref) => !knownRoomIds.has(ref));

  const issues = [];

  if (!knownRoomIds.has(targetRoomId)) {
    // A6-AGX-4: `scope` marks this as CARD-raised. The backend uses the same
    // code for a different fault ("references a room that is gone"), so the
    // resolver looks up room_access.issue.card.missing_room first.
    issues.push({
      code: "missing_room",
      scope: "card",
      params: {},
      message: "This room no longer exists on the active map.",
    });
  }

  if (selfReference) {
    issues.push({
      code: "self_reference",
      scope: "card",
      params: {},
      message: "A room cannot grant access to itself.",
    });
  }

  if (duplicateRefs.length) {
    issues.push({
      code: "duplicate_edges",
      scope: "card",
      params: {},
      message: "Each access link can only appear once.",
      roomIds: Array.from(new Set(duplicateRefs)),
    });
  }

  if (missingRefs.length) {
    issues.push({
      code: "missing_room_references",
      scope: "card",
      params: {},
      message: "All access links must point to rooms on the current map.",
      roomIds: missingRefs,
    });
  }

  // Single-inbound: a room already claimed as a target by another room cannot
  // be claimed by this one too.
  const claimedByOther = claimedTargets(graph, targetRoomId);
  const multipleInboundRefs = uniqueRefs.filter(
    (ref) => claimedByOther.has(ref) && knownRoomIds.has(ref)
  );

  if (multipleInboundRefs.length) {
    const roomNamesById = Object.fromEntries(
      rooms.map((room) => [String(room.id), room.name])
    );
    for (const ref of multipleInboundRefs) {
      const claimedBy = claimedByOther.get(ref);
      const claimantName = roomNamesById[claimedBy] ?? `Room ${claimedBy}`;
      const targetName = roomNamesById[ref] ?? `Room ${ref}`;
      issues.push({
        code: "multiple_inbound",
        scope: "card",
        params: { target: targetName, claimant: claimantName },
        // Kept as the fallback AND because it is the only rung that works
        // before a locale pack ships the key.
        message: `${targetName} already has an inbound link from ${claimantName}. Each room can only be reached from one room.`,
        roomIds: [ref, claimedBy].filter(Boolean),
      });
    }
  }

  const normalized = uniqueRefs.filter((ref) => knownRoomIds.has(ref));
  const proposedGraph = withEdges(graph, targetRoomId, normalized);

  // The dock gate. Checked against the graph as STORED, and only when this save
  // actually changes links — see dockGate for why both escape hatches exist.
  const changesLinks =
    JSON.stringify(normalizeRefs(graph.grants?.[targetRoomId])) !==
    JSON.stringify(normalized);
  const gate = dockGate(graph, {
    isDockRoom: Boolean(save.isDockRoom),
    changesLinks,
  });
  if (!gate.allowed) {
    issues.push({
      code: gate.code,
      scope: "card",
      params: {},
      message: "Set a dock room before linking rooms. The dock room is the origin of the access tree.",
    });
  }

  // Only worth asking once the edges are otherwise sound — a self-reference or a
  // stale target would surface here as a "loop", blaming the wrong thing.
  if (!issues.length && hasCycle(proposedGraph)) {
    issues.push({
      code: "cycle",
      scope: "card",
      params: {},
      message: "This access setup would create a loop in the room graph.",
    });
  }

  return {
    valid: issues.length === 0,
    issues,
    normalizedGrantsAccessTo: normalized,
  };
}
