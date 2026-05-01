/**
 * ============================================================
 * STATE: ROOMS
 * ============================================================
 *
 * PURPOSE
 * -------
 * All room-related state reads for the Rooms view.
 *
 * This file owns:
 * - active map resolution
 * - room entity discovery (attribute-based scanning)
 * - room list building and sorting
 * - enabled room counting
 * - start-cleaning readiness check
 * - queue chip interaction timing accessors
 *
 * HOW ROOM DATA REACHES THIS MODULE
 * ----------------------------------
 * The eufy_vacuum integration creates one switch entity per room
 * per map per vacuum. These entities expose the room's effective
 * settings in extra_state_attributes, with switch on/off state
 * representing the room's enabled flag.
 *
 * Relevant attributes include:
 *
 *   vacuum_entity_id, map_id, room_id, room_name, slug,
 *   order, profile_name, clean_mode, fan_speed, water_level,
 *   clean_intensity, clean_passes, edge_mopping, floor_type,
 *   carpet, grants_access_to, rules
 *
 * ORDER SOURCE OF TRUTH
 * ---------------------
 * Room order is persisted through the integration's number
 * entities. The card should prefer those number entity states
 * when available so visual ordering reflects saved order
 * immediately after reorder actions.
 *
 * INTERACTION TIMING SOURCE OF TRUTH
 * ---------------------------------
 * Queue chip long-press timing is resolved from persisted card
 * config/theme settings when available.
 *
 * Supported config locations:
 * - config.theme.queue_chip_long_press_ms
 * - config.queue_chip_long_press_ms
 *
 * Persisted variable name:
 * - queue_chip_long_press_ms
 *
 * ============================================================
 */

import { ENTITY, INVALID_STATES } from "../constants.js";

export function applyRoomsState(proto) {

  /* =========================================================
     ACCESS GRAPH HELPERS
     ========================================================= */

  proto._normalizeRoomReferenceList = function (value) {
    if (value == null) return [];

    const list = Array.isArray(value) ? value : [value];

    return list
      .map((entry) => String(entry ?? "").trim())
      .filter((entry) => entry !== "");
  };

  proto._buildRoomAccessAdjacency = function (rooms = []) {
    const adjacency = {};

    rooms.forEach((room) => {
      adjacency[String(room.id)] = this._normalizeRoomReferenceList(room.grantsAccessTo);
    });

    return adjacency;
  };

  proto._roomAccessGraphHasCycle = function (adjacency = {}) {
    const visited = new Set();
    const active = new Set();

    const visit = (roomId) => {
      if (active.has(roomId)) return true;
      if (visited.has(roomId)) return false;

      visited.add(roomId);
      active.add(roomId);

      const neighbors = adjacency[roomId] ?? [];
      for (const nextRoomId of neighbors) {
        if (!(nextRoomId in adjacency)) continue;
        if (visit(nextRoomId)) return true;
      }

      active.delete(roomId);
      return false;
    };

    return Object.keys(adjacency).some((roomId) => visit(roomId));
  };

  proto.roomAccessGraph = function (mapId = null) {
    const rooms = mapId == null
      ? this.getRoomsForActiveMap()
      : this.getRoomsForMap(mapId);

    const adjacency = this._buildRoomAccessAdjacency(rooms);

    return rooms.map((room) => {
      const roomId = String(room.id);
      const grantsAccessTo = adjacency[roomId] ?? [];
      const requiresAccessFrom = rooms
        .filter((candidate) => {
          const candidateEdges = adjacency[String(candidate.id)] ?? [];
          return candidateEdges.includes(roomId);
        })
        .map((candidate) => String(candidate.id));

      return {
        roomId,
        grantsAccessTo,
        requiresAccessFrom,
      };
    });
  };

  proto.validateRoomAccessUpdate = function (mapId, roomId, proposedGrantsAccessTo = []) {
    const rooms = this.getRoomsForMap(mapId);
    const targetRoomId = String(roomId ?? "").trim();
    const knownRoomIds = new Set(rooms.map((room) => String(room.id)));
    const rawRefs = this._normalizeRoomReferenceList(proposedGrantsAccessTo);
    const duplicateRefs = rawRefs.filter((ref, index) => rawRefs.indexOf(ref) !== index);
    const uniqueRefs = Array.from(new Set(rawRefs));
    const missingRefs = uniqueRefs.filter((ref) => !knownRoomIds.has(ref));
    const selfReference = uniqueRefs.includes(targetRoomId);

    const issues = [];

    if (!knownRoomIds.has(targetRoomId)) {
      issues.push({
        code: "missing_room",
        message: "This room no longer exists on the active map.",
      });
    }

    if (selfReference) {
      issues.push({
        code: "self_reference",
        message: "A room cannot grant access to itself.",
      });
    }

    if (duplicateRefs.length) {
      issues.push({
        code: "duplicate_edges",
        message: "Each access link can only appear once.",
        roomIds: Array.from(new Set(duplicateRefs)),
      });
    }

    if (missingRefs.length) {
      issues.push({
        code: "missing_room_references",
        message: "All access links must point to rooms on the current map.",
        roomIds: missingRefs,
      });
    }

    // Single-inbound constraint: a room that is already claimed as a target
    // by another room cannot be added as a target by this room too.
    const adjacency = this._buildRoomAccessAdjacency(rooms);
    const claimedByOther = this._buildClaimedTargetMap(rooms, targetRoomId);

    const multipleInboundRefs = uniqueRefs.filter(
      (ref) => claimedByOther.has(ref) && knownRoomIds.has(ref)
    );

    if (multipleInboundRefs.length) {
      const roomNamesById = Object.fromEntries(
        rooms.map((room) => [String(room.id), room.name])
      );
      multipleInboundRefs.forEach((ref) => {
        const claimedBy = claimedByOther.get(ref);
        const claimantName = roomNamesById[claimedBy] ?? `Room ${claimedBy}`;
        const targetName = roomNamesById[ref] ?? `Room ${ref}`;
        issues.push({
          code: "multiple_inbound",
          message: `${targetName} already has an inbound link from ${claimantName}. Each room can only be reached from one room.`,
          roomIds: [ref, claimedBy].filter(Boolean),
        });
      });
    }

    adjacency[targetRoomId] = uniqueRefs.filter((ref) => knownRoomIds.has(ref));

    if (!issues.length && this._roomAccessGraphHasCycle(adjacency)) {
      issues.push({
        code: "cycle",
        message: "This access setup would create a loop in the room graph.",
      });
    }

    return {
      valid: issues.length === 0,
      issues,
      normalizedGrantsAccessTo: adjacency[targetRoomId] ?? [],
    };
  };

  /**
   * Returns rooms that have not been set up in the access tree yet:
   * - not the dock room
   * - requiresAccessFrom is empty (no one grants them access)
   */
  proto.orphanedRooms = function (mapId = null) {
    const rooms = mapId != null
      ? this.getRoomsForMap(mapId)
      : this.getRoomsForActiveMap();

    // Only show the panel once a dock room has been declared.
    // If no dock room exists yet the whole graph is unset — not useful to list.
    const hasDockRoom = rooms.some((room) => room.isDockRoom);
    if (!hasDockRoom) return [];

    // Build the set of rooms that appear as a target in any other room's
    // grantsAccessTo. These rooms have been placed in the access tree.
    // requiresAccessFrom is a derived field never stored on entities — we
    // must derive it here from grantsAccessTo which IS in entity attributes.
    const placed = new Set();
    rooms.forEach((room) => {
      this._normalizeRoomReferenceList(room.grantsAccessTo).forEach((targetId) => {
        placed.add(targetId);
      });
    });

    // A room is unconfigured if it is not the dock room and no other room
    // grants access to it — i.e. it has not been placed in the tree yet.
    return rooms.filter((room) => {
      if (room.isDockRoom) return false;
      return !placed.has(String(room.id));
    });
  };

  /**
   * Build a map of target room ID -> claimant room ID for all rooms
   * except the room being edited (excludeRoomId). Used to enforce the
   * single-inbound constraint during validation and chip rendering.
   */
  proto._buildClaimedTargetMap = function (rooms = [], excludeRoomId = "") {
    const claimed = new Map();

    rooms.forEach((room) => {
      if (String(room.id) === String(excludeRoomId)) return;

      this._normalizeRoomReferenceList(room.grantsAccessTo).forEach((targetId) => {
        // First claimant wins — duplicates are caught elsewhere.
        if (!claimed.has(targetId)) {
          claimed.set(targetId, String(room.id));
        }
      });
    });

    return claimed;
  };

  /* =========================================================
     RUN ACTION STATE
     ========================================================= */

  proto.setStartStatus = function (status) {
    this._startStatus = status ?? null;
  };

  proto.startPreflight = function () {
    const preflight =
      this.dashboardJobControl?.()?.preflight ??
      this.dashboardStartStatus?.()?.preflight ??
      this._startStatus?.preflight ??
      null;

    if (preflight) return preflight;

    const status = this._startStatus ?? this.dashboardStartStatus?.() ?? null;

    if (status?.selected_room_ids || status?.blocked_rooms || status?.modified_rooms) {
      return status;
    }

    return null;
  };

  proto.setStartConfirmation = function (preflight = null, confirmToken = null) {
    this._startConfirmation = {
      preflight: preflight ?? this.startPreflight(),
      confirmToken: confirmToken ?? preflight?.confirm_token ?? null,
    };
  };

  proto.clearStartConfirmation = function () {
    this._startConfirmation = null;
  };

  proto.startConfirmation = function () {
    return this._startConfirmation ?? null;
  };

  proto.startRequiresConfirmation = function () {
    return Boolean(
      this._startConfirmation?.confirmToken ||
      this._startConfirmation?.preflight?.requires_confirmation
    );
  };

  proto.startConfirmationToken = function () {
    return (
      this._startConfirmation?.confirmToken ??
      this._startConfirmation?.preflight?.confirm_token ??
      null
    );
  };

  proto.requestCancelRunConfirmation = function () {
    this._cancelRunConfirmation = true;
  };

  proto.clearCancelRunConfirmation = function () {
    this._cancelRunConfirmation = false;
  };

  proto.cancelRunRequiresConfirmation = function () {
    return this._cancelRunConfirmation === true;
  };

  proto.hasActiveRun = function () {
    const status = String(this.vacuumState() ?? "").toLowerCase();
    if (status === "cleaning" || status === "paused") return true;
    return this._dashboardJobIsActive?.() ?? false;
  };

  /**
   * =========================================================
   * LIVE QUEUE VISIBILITY
   * =========================================================
   *
   * PURPOSE
   * -------
   * Single source of truth for whether the Rooms view should
   * render the live in-progress queue rather than the planned
   * pre-start queue.
   *
   * DESIGN RULE
   * -----------
   * Learning job state can be initialized before the vacuum has
   * actually transitioned into a running state. To avoid early
   * queue switching, live queue mode requires BOTH:
   * - a job progress timeline exists
   * - the vacuum is actively running or paused
   * =========================================================
   */
  proto.shouldShowLiveQueue = function () {
    const timeline = this.dashboardJobProgressTimeline?.() ?? [];
    return timeline.length > 0 && this.hasActiveRun();
  };

  proto.canPauseRun = function () {
    return String(this.vacuumState() ?? "").toLowerCase() === "cleaning";
  };

  proto.canResumeRun = function () {
    return String(this.vacuumState() ?? "").toLowerCase() === "paused";
  };

  /* =========================================================
     MAP RESOLUTION
     ========================================================= */

  proto.activeMapId = function () {
    const entityId = ENTITY.activeMap(this.vacuumEntityId());
    const raw = this.stateOf(entityId);

    if (raw && !INVALID_STATES.has(String(raw))) {
      return String(raw);
    }

    const switches = this._findRoomSwitchEntities();
    if (switches.length > 0) {
      return String(switches[0].attributes.map_id ?? "1");
    }

    return "1";
  };

  /* =========================================================
     INTERACTION SETTINGS
     =========================================================
     Theme/editor-ready accessors for queue chip interactions.
     ========================================================= */

  proto.queueChipLongPressMs = function () {
    const themeValue = Number(this.config?.theme?.queue_chip_long_press_ms);
    const directValue = Number(this.config?.queue_chip_long_press_ms);

    const raw = Number.isFinite(themeValue)
      ? themeValue
      : Number.isFinite(directValue)
        ? directValue
        : 450;

    return Math.min(1000, Math.max(250, raw));
  };

  /* =========================================================
     ENTITY DISCOVERY
     ========================================================= */

  proto._findRoomSwitchEntities = function () {
    const hass = this.hass;
    const vacuumId = this.vacuumEntityId();
    if (!hass?.states || !vacuumId) return [];

    const results = [];

    for (const [entityId, entityState] of Object.entries(hass.states)) {
      if (!entityId.startsWith("switch.")) continue;

      const attrs = entityState?.attributes;
      if (!attrs) continue;

      if (
        attrs.vacuum_entity_id === vacuumId &&
        attrs.room_id != null &&
        attrs.map_id != null &&
        "enabled" in attrs
      ) {
        results.push({
          entityId,
          state: entityState.state,
          attributes: attrs,
        });
      }
    }

    return results;
  };

  /**
   * =========================================================
   * FIND ROOM ORDER NUMBER ENTITIES
   * =========================================================
   *
   * PURPOSE
   * -------
   * Discover the number entities that persist room order.
   *
   * PLAIN ENGLISH
   * -------------
   * These are the real saved order entities. We prefer their
   * numeric state over attrs.order on the profile entity so
   * the UI reflects freshly saved reorder changes immediately.
   * =========================================================
   */
  proto._findRoomOrderNumberEntities = function () {
    const hass = this.hass;
    const vacuumId = this.vacuumEntityId();
    if (!hass?.states || !vacuumId) return [];

    const results = [];

    for (const [entityId, entityState] of Object.entries(hass.states)) {
      if (!entityId.startsWith("number.")) continue;

      const attrs = entityState?.attributes;
      if (!attrs) continue;

      if (
        attrs.vacuum_entity_id === vacuumId &&
        attrs.room_id != null &&
        attrs.map_id != null
      ) {
        results.push({
          entityId,
          state: entityState.state,
          attributes: attrs,
        });
      }
    }

    return results;
  };

  /**
   * =========================================================
   * FIND ROOM ORDER NUMBER ENTITY ID
   * =========================================================
   */
  proto.findRoomOrderNumberEntityId = function (mapId, roomId) {
    const allStates = Object.values(this.hass?.states ?? {});
    const wantedMapId = String(mapId);
    const wantedRoomId = String(roomId);

    const matches = allStates.filter((stateObj) => {
      if (!stateObj?.entity_id?.startsWith("number.")) return false;

      const attrs = stateObj.attributes ?? {};
      return (
        String(attrs.map_id) === wantedMapId &&
        String(attrs.room_id) === wantedRoomId
      );
    });

    const preferred = matches.find((stateObj) =>
      String(stateObj.entity_id).toLowerCase().endsWith("_order")
    );

    return preferred?.entity_id ?? matches[0]?.entity_id ?? null;
  };

  proto.findRoomSwitchEntityId = function (mapId, roomId) {
    const switches = this._findRoomSwitchEntities();
    const target = String(roomId);
    const map = String(mapId);

    const match = switches.find(
      (s) =>
        String(s.attributes.map_id) === map &&
        String(s.attributes.room_id) === target
    );

    return match?.entityId ?? null;
  };

  /* =========================================================
     ROOM LIST
     ========================================================= */

  proto.getRoomsForActiveMap = function () {
    const mapId = this.activeMapId();
    return this.getRoomsForMap(mapId);
  };

  proto.getRoomsForMap = function (mapId) {
    const switches = this._findRoomSwitchEntities();
    const orderNumbers = this._findRoomOrderNumberEntities();

    const orderByRoomId = {};
    for (const num of orderNumbers) {
      if (String(num.attributes.map_id) !== String(mapId)) continue;

      const roomId = String(num.attributes.room_id);
      const numericState = Number(num.state);
      const looksLikeOrder = String(num.entityId).toLowerCase().endsWith("_order");

      if (!Number.isFinite(numericState)) continue;

      if (!(roomId in orderByRoomId) || looksLikeOrder) {
        orderByRoomId[roomId] = numericState;
      }
    }

    const rooms = switches
      .filter((sw) => String(sw.attributes.map_id) === String(mapId))
      .map((sw) => {
        const roomId = String(sw.attributes.room_id);
        const enabled = sw.state === "on";

        const effectiveOrder = roomId in orderByRoomId
          ? orderByRoomId[roomId]
          : sw.attributes.order;

        return this._normalizeRoom(sw.attributes, enabled, effectiveOrder);
      });

    rooms.sort((a, b) => {
      const orderDiff = (a.order ?? 999) - (b.order ?? 999);
      if (orderDiff !== 0) return orderDiff;
      return String(a.name).localeCompare(String(b.name));
    });

    return rooms;
  };

  /* =========================================================
     NORMALIZE ROOM
     ========================================================= */

  proto._normalizeRoom = function (attrs, enabled, resolvedOrder = null) {
    const roomId = Number(attrs.room_id);
    const mapId = String(attrs.map_id ?? "");
    const name = String(attrs.room_name ?? `Room ${attrs.room_id}`);
    const slug = attrs.slug ?? null;
    const isEnabled = enabled !== undefined ? Boolean(enabled) : Boolean(attrs.enabled);
    const order = Number(resolvedOrder ?? attrs.order ?? 999);

    const profileName = String(attrs.profile_name ?? "vacuum_quick");
    const profileLabel   = attrs.profile_label   ?? null;
    const profileSubtitle = attrs.profile_subtitle ?? null;

    const floorType = String(attrs.floor_type ?? "");
    const floorTypeLabel = attrs.floor_type_label ?? null;
    const carpetType = String(attrs.carpet_type ?? "");
    const carpetTypeLabel = attrs.carpet_type_label ?? null;
    const carpet = Boolean(
      attrs.carpet ??
      String(floorType).toLowerCase() === "carpet"
    );

    const cleanMode      = attrs.clean_mode      ?? "vacuum";
    const fanSpeed       = attrs.fan_speed       ?? null;
    const waterLevel     = attrs.water_level     ?? null;
    const cleanIntensity = attrs.clean_intensity ?? null;
    const cleanPasses    = Number(attrs.clean_passes ?? 1);
    const edgeMopping    = Boolean(attrs.edge_mopping ?? false);
    const cleanModeLabel  = attrs.clean_mode_label  ?? null;
    const fanSpeedLabel   = attrs.fan_speed_label   ?? null;
    const waterLevelLabel = attrs.water_level_label ?? null;
    const cleanIntensityLabel = attrs.clean_intensity_label ?? attrs.path_type_label ?? null;
    const cleanPassesLabel    = attrs.clean_passes_label    ?? null;
    const edgeMoppingLabel    = attrs.edge_mopping_label    ?? null;

    const normalizedMode = String(cleanMode ?? "").toLowerCase();
    const isVacuumOnly = normalizedMode === "vacuum";
    const isMopCapable =
      normalizedMode === "mop" ||
      normalizedMode === "vacuum_mop" ||
      normalizedMode.includes("mop") ||
      normalizedMode.includes("wash");
    const isDockRoom      = Boolean(attrs.is_dock_room         ?? attrs.isDockRoom         ?? false);
    const isTransition    = Boolean(attrs.is_transition        ?? attrs.isTransition        ?? false);
    const transitionCandidate = Boolean(attrs.transition_candidate ?? attrs.transitionCandidate ?? false);
    const transitionScore = Number(attrs.transition_score      ?? attrs.transitionScore      ?? 0);
    const grantsAccessTo = this._normalizeRoomReferenceList(
      attrs.grants_access_to ?? attrs.grantsAccessTo
    );
    const requiresAccessFrom = this._normalizeRoomReferenceList(
      attrs.requires_access_from ?? attrs.requiresAccessFrom
    );
    const rawRules = attrs.rules ?? attrs.automation_rules;
    const rules = Array.isArray(rawRules) ? rawRules : [];

    return {
      id: roomId,
      mapId,
      name,
      slug,
      enabled: isEnabled,
      order,
      profileName,
      profileLabel,
      profileSubtitle,
      floorType,
      floorTypeLabel,
      carpetType,
      carpetTypeLabel,
      carpet,
      cleanMode,
      cleanModeLabel,
      fanSpeed,
      fanSpeedLabel,
      waterLevel,
      waterLevelLabel,
      cleanIntensity,
      cleanIntensityLabel,
      cleanPasses,
      cleanPassesLabel,
      edgeMopping,
      edgeMoppingLabel,

      isCustomProfile: profileName.toLowerCase() === "custom",
      isVacuumOnly,
      isMopCapable,
      isDockRoom,
      isTransition,
      transitionCandidate,
      transitionScore,
      rules,

      profile: profileName,
      passes: cleanPasses,
      grantsAccessTo,
      requiresAccessFrom,

      profile_name: profileName,
      floor_type: floorType,
      floor_type_label: floorTypeLabel,
      carpet_type: carpetType,
      carpet_type_label: carpetTypeLabel,
      clean_mode: cleanMode,
      clean_mode_label: cleanModeLabel,
      fan_speed: fanSpeed,
      fan_speed_label: fanSpeedLabel,
      water_level: waterLevel,
      water_level_label: waterLevelLabel,
      clean_intensity: cleanIntensity,
      clean_intensity_label: cleanIntensityLabel,
      clean_passes: cleanPasses,
      clean_passes_label: cleanPassesLabel,
      edge_mopping: edgeMopping,
      edge_mopping_label: edgeMoppingLabel,
      map_id: mapId,
      room_id: roomId,
      room_name: name,
      grants_access_to: grantsAccessTo,
      requires_access_from: requiresAccessFrom,
      is_transition: isTransition,
      transition_candidate: transitionCandidate,
      transition_score: transitionScore,
    };
  };

  proto._roomModeIncludesMop = function (cleanMode) {
    const mode = String(cleanMode ?? "").toLowerCase();

    return (
      mode === "mop" ||
      mode === "vacuum_mop" ||
      mode.includes("mop") ||
      mode.includes("wash")
    );
  };

  /* =========================================================
     ROOM COUNTS / READINESS
     ========================================================= */

  proto.enabledRoomCount = function () {
    return this.getRoomsForActiveMap().filter((r) => r.enabled).length;
  };

  /**
   * =========================================================
   * START STATUS HELPERS
   * =========================================================
   *
   * PURPOSE
   * -------
   * Normalize integration start-status values so button enable/
   * disable logic is resilient to string/boolean payloads and
   * never bypasses local hard blockers.
   *
   * DESIGN RULE
   * -----------
   * Local blockers always win:
   * - no enabled rooms
   * - vacuum already cleaning
   * - vacuum returning
   * - vacuum in error
   *
   * Integration start status then adds:
   * - blocked state
   * - warning state
   * - user-facing message/reason
   * =========================================================
   */

  proto._startStatusFlag = function (key) {
    const raw = (
      this.dashboardJobControl?.()?.[key] ??
      this.dashboardStartStatus?.()?.[key] ??
      this._startStatus?.[key]
    );

    if (typeof raw === "boolean") return raw;
    if (raw == null) return false;

    const normalized = String(raw).trim().toLowerCase();
    return normalized === "true" || normalized === "1" || normalized === "yes";
  };

  proto._localStartBlockReason = function () {
    if (this.enabledRoomCount() < 1) return "No rooms included.";

    const status = String(this.vacuumState() ?? "").toLowerCase();

    if (status === "cleaning")  return "Already cleaning.";
    if (status === "returning") return "Returning to dock.";
    if (status === "error")     return "Vacuum has an error.";

    return null;
  };

  proto.canStartCleaning = function () {
    const localBlock = this._localStartBlockReason();
    if (localBlock && !this.startRequiresConfirmation()) return false;

    const jobControl = this.dashboardJobControl?.();
    if (jobControl && jobControl.can_start != null) {
      return Boolean(jobControl.can_start);
    }

    if (this._startStatus) {
      return !this._startStatusFlag("blocked");
    }

    return true;
  };

  proto.startBlockedReason = function () {
    if (this.startRequiresConfirmation()) return null;

    const localBlock = this._localStartBlockReason();
    if (localBlock) return localBlock;

    const jobControl = this.dashboardJobControl?.();
    if (jobControl) {
      if (this._startStatusFlag("blocked")) {
        return jobControl.message ?? jobControl.reason_detail ?? jobControl.reason ?? "Start is blocked.";
      }

      if (this._startStatusFlag("warning")) {
        return jobControl.message ?? jobControl.reason_detail ?? null;
      }
    }

    if (this._startStatus || this.dashboardStartStatus?.()) {
      if (this._startStatusFlag("blocked")) {
        return (
          this.dashboardStartStatus?.()?.message ??
          this._startStatus?.message ??
          "Start is blocked."
        );
      }

      if (this._startStatusFlag("warning")) {
        return (
          this.dashboardStartStatus?.()?.message ??
          this._startStatus?.message ??
          null
        );
      }

      return null;
    }

    return null;
  };

  proto.hasStartWarning = function () {
    if (this._localStartBlockReason()) return false;
    return this._startStatusFlag("warning");
  };

  proto.startStatusReason = function () {
    return (
      this.dashboardJobControl?.()?.reason ??
      this.dashboardStartStatus?.()?.reason ??
      this._startStatus?.reason ??
      null
    );
  };

  proto.activeJobRooms = function () {
    const timeline = this.dashboardJobProgressTimeline?.() ?? [];
    if (this.shouldShowLiveQueue()) {
      return timeline.map((entry, index) => ({
        jobOrder: entry.position ?? index + 1,
        name: entry.room_name ?? `Room ${entry.room_id ?? index + 1}`,
      }));
    }

    const status = String(this.vacuumState() ?? "").toLowerCase();
    const jobDone = new Set(["docked", "idle", "error"]);

    if (jobDone.has(status) && this._activeJobRooms?.length) {
      this._activeJobRooms = null;
    }

    return this._activeJobRooms ?? null;
  };
}