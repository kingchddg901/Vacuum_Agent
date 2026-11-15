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
        // APPEARANCE ONLY, and separate from floorTypes on purpose: floor_type
        // carries the carpet-water-off guarantee and stays a closed vocabulary.
        // "" is a real value here — it means "clear the material".
        floorMaterials:   {},     // String(room_id) → material id or ""
        // Degrees. 0 is a REAL value (“as authored”), not an absence -- an
        // untouched room is absent from this map entirely, which is what tells
        // the backend to leave its angle alone.
        floorRotations:   {},     // String(room_id) → degrees
        // WHERE A FITTED MATERIAL SITS: {tx, ty, scale}. Only a drop-in that makes no
        // `tileable` claim is fitted; a tiled one shares a map-space grid and has
        // nothing to place. An EMPTY object is a real value here -- back to centred,
        // exact cover -- and an untouched room is absent from this map entirely, which
        // is what tells the backend to leave its placement alone.
        floorFits:        {},     // String(room_id) → {tx, ty, scale}
        // Nudge step, shared by every placement control in this editor. Deliberately
        // NOT the composer's `composeStep`, which is named for its own surface: sharing
        // it would make changing the precision here silently change it there.
        floorFitStep:     3,      // 1 fine | 3 med | 7 coarse, as the composer's does
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

  proto.setSetupRoomFloorMaterial = function (roomId, material) {
    this._ensureSetupRoomEditor().floorMaterials[String(roomId)] = material ?? "";
  };

  proto.setSetupRoomFloorRotation = function (roomId, degrees) {
    const n = Number(degrees);
    this._ensureSetupRoomEditor().floorRotations[String(roomId)] =
      Number.isFinite(n) ? n : 0;
  };

  /* A PLACEMENT IS MERGED, NOT REPLACED. Each control moves one axis and the others
     must survive it, so a pan after a zoom does not silently reset the zoom. Values are
     clamped to the renderable range HERE as well as in the backend, so a draft can
     never hold a value the save would refuse to keep.

     THIS DRAFT IS NOT RENDERED, and an earlier version of this comment claimed it was.
     It cannot be: the setup room editor is a LIST, with no map beside it. The live
     control is on the map and reads the separate draft in state/map.js. These controls
     earn their place by batching several rooms before one save, and they show their
     values so they are not silent -- but nothing here moves a floor until it is saved.

     tx/ty are fractions of the slack that exists, so +/-1 is the room's own edge and
     anything past it is the same picture; scale multiplies the cover, 1 being exact. */
  proto.setSetupRoomFloorFit = function (roomId, patch) {
    const key = String(roomId);
    const editor = this._ensureSetupRoomEditor();
    const cur = editor.floorFits[key] || {};
    const next = { ...cur };
    const clamp = (v, lo, hi) => Math.min(Math.max(v, lo), hi);
    for (const [k, lo, hi] of [["tx", -1, 1], ["ty", -1, 1], ["scale", 0.25, 4]]) {
      if (!(patch && k in patch)) continue;
      const n = Number(patch[k]);
      if (Number.isFinite(n)) next[k] = clamp(n, lo, hi);
    }
    editor.floorFits[key] = next;
  };

  /* Back to centred, exact cover. An EMPTY object, not a delete: absent would mean
     "leave whatever is stored alone", which is the opposite of what a reset asks for. */
  proto.resetSetupRoomFloorFit = function (roomId) {
    this._ensureSetupRoomEditor().floorFits[String(roomId)] = {};
  };

  proto.setupRoomFloorFit = function (roomId) {
    return this._ensureSetupRoomEditor().floorFits[String(roomId)] || null;
  };

  proto.setupRoomEditorFloorFitStep = function () {
    return this._ensureSetupRoomEditor().floorFitStep;
  };

  proto.setSetupRoomEditorFloorFitStep = function (n) {
    const v = Number(n);
    this._ensureSetupRoomEditor().floorFitStep = Number.isFinite(v) && v > 0 ? v : 3;
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

  /* Collect floor MATERIALS dict: String(room_id) → material id ("" clears).
     Only rooms the user actually touched appear, because the backend reads an
     ABSENT room as “leave it alone” — sending every room would let this view
     overwrite materials the room editor set. */
  proto.setupRoomEditorFloorMaterialsMap = function () {
    return { ...this._ensureSetupRoomEditor().floorMaterials };
  };

  proto.setupRoomEditorFloorRotationsMap = function () {
    return { ...this._ensureSetupRoomEditor().floorRotations };
  };

  proto.setupRoomEditorFloorFitsMap = function () {
    const out = {};
    for (const [k, v] of Object.entries(this._ensureSetupRoomEditor().floorFits)) {
      out[k] = { ...v };
    }
    return out;
  };
}
