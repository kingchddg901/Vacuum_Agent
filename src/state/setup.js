/**
 * ============================================================
 * STATE: SETUP
 * ============================================================
 *
 * PURPOSE
 * -------
 * Stores the result of setup_get_status and all transient UI
 * state for the Setup tab:
 *   - global status (loading, error, last action result)
 *   - room editor (which map is open, room enabled/floor settings)
 *
 * ============================================================
 */

export function applySetupState(proto) {

  /* =========================================================
     GLOBAL SETUP STATE
     ========================================================= */

  proto._ensureSetupState = function () {
    if (!this._setupState) {
      this._setupState = {
        status:     null,
        loading:    false,
        error:      null,
        lastResult: null,
      };
    }
    return this._setupState;
  };

  proto.setupStatus = function () {
    return this._ensureSetupState().status ?? null;
  };
  proto.setSetupStatus = function (status) {
    this._ensureSetupState().status = status ?? null;
  };

  proto.setupLoading = function () {
    return this._ensureSetupState().loading;
  };
  proto.setSetupLoading = function (loading) {
    this._ensureSetupState().loading = Boolean(loading);
  };

  proto.setupError = function () {
    return this._ensureSetupState().error ?? null;
  };
  proto.setSetupError = function (error) {
    this._ensureSetupState().error = error ?? null;
  };

  proto.setupLastResult = function () {
    return this._ensureSetupState().lastResult ?? null;
  };
  proto.setSetupLastResult = function (result) {
    this._ensureSetupState().lastResult = result ?? null;
  };

  /* =========================================================
     ROOM EDITOR STATE
     =========================================================
     Tracks which map's rooms are currently being configured
     and the per-room enabled/floor-type selections.
     ========================================================= */

  proto._ensureSetupRoomEditor = function () {
    if (!this._setupRoomEditor) {
      this._setupRoomEditor = {
        openMapId:        null,   // map_id whose rooms are shown
        rooms:            null,   // array from setup_get_map_rooms
        loadingMapId:     null,   // map_id currently fetching rooms
        enabled:          {},     // String(room_id) → bool
        floorTypes:       {},     // String(room_id) → string
        saving:           false,
        configuredMapIds: {},     // String(map_id) → true
      };
    }
    return this._setupRoomEditor;
  };

  proto.setupRoomEditorOpenMapId = function () {
    return this._ensureSetupRoomEditor().openMapId ?? null;
  };
  proto.setupRoomEditorRooms = function () {
    return this._ensureSetupRoomEditor().rooms ?? null;
  };
  proto.setupRoomEditorLoadingMapId = function () {
    return this._ensureSetupRoomEditor().loadingMapId ?? null;
  };
  proto.setupRoomEditorSaving = function () {
    return this._ensureSetupRoomEditor().saving;
  };
  proto.isSetupMapConfigured = function (mapId) {
    return Boolean(this._ensureSetupRoomEditor().configuredMapIds[String(mapId)]);
  };

  proto.setSetupRoomEditorLoadingMapId = function (mapId) {
    this._ensureSetupRoomEditor().loadingMapId = mapId ?? null;
  };

  proto.openSetupRoomEditor = function (mapId, rooms) {
    const ed = this._ensureSetupRoomEditor();
    ed.openMapId    = mapId;
    ed.rooms        = rooms;
    ed.loadingMapId = null;
    // Pre-populate from existing room settings (floor type from backend, all enabled).
    const enabled    = {};
    const floorTypes = {};
    for (const room of rooms) {
      const key         = String(room.room_id);
      enabled[key]    = true;
      floorTypes[key] = room.floor_type || "hardwood";
    }
    ed.enabled    = enabled;
    ed.floorTypes = floorTypes;
  };

  proto.closeSetupRoomEditor = function () {
    const ed      = this._ensureSetupRoomEditor();
    ed.openMapId  = null;
    ed.rooms      = null;
  };

  proto.toggleSetupRoom = function (roomId) {
    const ed  = this._ensureSetupRoomEditor();
    const key = String(roomId);
    ed.enabled[key] = ed.enabled[key] === false ? true : false;
  };

  proto.setSetupRoomFloorType = function (roomId, floorType) {
    this._ensureSetupRoomEditor().floorTypes[String(roomId)] = floorType;
  };

  proto.setSetupRoomEditorSaving = function (saving) {
    this._ensureSetupRoomEditor().saving = Boolean(saving);
  };

  proto.markSetupMapConfigured = function (mapId) {
    this._ensureSetupRoomEditor().configuredMapIds[String(mapId)] = true;
  };

  /* =========================================================
     MAP DELETE STATE
     =========================================================
     Tracks per-map delete confirmation flow.
     States: null → "confirm" → "typing" (high protection only)
     ========================================================= */

  proto._ensureSetupDeleteState = function () {
    if (!this._setupDeleteState) {
      this._setupDeleteState = {
        pendingMapId:  null,   // map_id currently in confirm flow
        stage:         null,   // "confirm" | "typing"
        typedToken:    "",     // text the user has typed so far
        deleting:      false,  // service call in flight
      };
    }
    return this._setupDeleteState;
  };

  proto.setupDeletePendingMapId = function () {
    return this._ensureSetupDeleteState().pendingMapId ?? null;
  };
  proto.setupDeleteStage = function () {
    return this._ensureSetupDeleteState().stage ?? null;
  };
  proto.setupDeleteTypedToken = function () {
    return this._ensureSetupDeleteState().typedToken ?? "";
  };
  proto.setupDeleteDeleting = function () {
    return this._ensureSetupDeleteState().deleting;
  };

  proto.openSetupDeleteConfirm = function (mapId, requiresTyped) {
    const s = this._ensureSetupDeleteState();
    s.pendingMapId = mapId;
    s.stage        = requiresTyped ? "typing" : "confirm";
    s.typedToken   = "";
    s.deleting     = false;
  };
  proto.setSetupDeleteTypedToken = function (token) {
    this._ensureSetupDeleteState().typedToken = token ?? "";
  };
  proto.setSetupDeleteDeleting = function (deleting) {
    this._ensureSetupDeleteState().deleting = Boolean(deleting);
  };
  proto.closeSetupDeleteConfirm = function () {
    const s = this._ensureSetupDeleteState();
    s.pendingMapId = null;
    s.stage        = null;
    s.typedToken   = "";
    s.deleting     = false;
  };

  /* =========================================================
     RECONCILIATION REVIEW STATE (CARD-7/RP-019)
     =========================================================
     Transient UI state for the reconciliation banner rendered inside
     the save_rooms step. The REVIEW DATA itself (reviews, has_changes,
     plan_token, map_id) comes straight from setupStatus()'s per-vacuum
     "reconciliation" field (Gap 2) — this only tracks what the user has
     done with it locally:
       - resolvedToken: the plan_token of the last review this card
         successfully applied (migrate) or dismissed (ignore). Comparing
         it against the CURRENT reconciliation.plan_token lets the
         renderer stop showing a group banner for a plan the user already
         acted on, even though the backend's cached reconciliation block
         only refreshes on the next real discover_rooms pass (same
         "reflects the last pass" contract room_drift already has) — see
         renderers/setup.js's renderReconciliationPanel.
       - result: the raw reconcile_room response for the resolvedToken
         above, rendered as State C (report id_remap/dropped) when its
         action is "migrate". Cleared implicitly whenever a fresh
         plan_token supersedes it — no explicit reset needed.
       - staleNote: one-line "the map changed" note shown after a
         successful silent recovery from a plan_changed refusal.
       - refreshFailed: the silent recovery itself failed to complete —
         render the design's literal fallback ("re-discover" button)
         instead of guessing at stale data.
     ========================================================= */

  proto._ensureSetupReconcileState = function () {
    if (!this._setupReconcileState) {
      this._setupReconcileState = {
        loading:        false,
        resolvedToken:  null,
        result:         null,
        staleNote:      false,
        refreshFailed:  false,
      };
    }
    return this._setupReconcileState;
  };

  proto.setupReconcileLoading = function () {
    return this._ensureSetupReconcileState().loading;
  };
  proto.setSetupReconcileLoading = function (loading) {
    this._ensureSetupReconcileState().loading = Boolean(loading);
  };

  proto.setupReconcileResolvedToken = function () {
    return this._ensureSetupReconcileState().resolvedToken ?? null;
  };
  proto.setupReconcileResult = function () {
    return this._ensureSetupReconcileState().result ?? null;
  };
  /** Record a locally-resolved (migrated or dismissed) plan_token + its response. */
  proto.setSetupReconcileResolved = function (planToken, result) {
    const s = this._ensureSetupReconcileState();
    s.resolvedToken = planToken ?? null;
    s.result        = result ?? null;
  };

  proto.setupReconcileStaleNote = function () {
    return this._ensureSetupReconcileState().staleNote;
  };
  proto.setSetupReconcileStaleNote = function (shown) {
    this._ensureSetupReconcileState().staleNote = Boolean(shown);
  };

  proto.setupReconcileRefreshFailed = function () {
    return this._ensureSetupReconcileState().refreshFailed;
  };
  proto.setSetupReconcileRefreshFailed = function (failed) {
    this._ensureSetupReconcileState().refreshFailed = Boolean(failed);
  };

  /* Collect enabled room IDs as integers for the service call. */
  proto.setupRoomEditorEnabledIds = function () {
    const ed    = this._ensureSetupRoomEditor();
    const rooms = ed.rooms ?? [];
    return rooms
      .filter((r) => ed.enabled[String(r.room_id)] !== false)
      .map((r) => r.room_id);
  };

  /* Collect floor types dict: String(room_id) → floor_type_string. */
  proto.setupRoomEditorFloorTypesMap = function () {
    return { ...this._ensureSetupRoomEditor().floorTypes };
  };
}
