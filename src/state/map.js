// Card-local state for the map view: zoom/pan transform, segment selection, segment↔room associations,
// dot anchor positions, robot-position room detection, and animal companion settings.

import { vacuumObjectId } from "../constants.js";

export function applyMapState(proto) {
  proto._mapViewActive = null; // null = not yet read from localStorage
  proto._mapSegmentsData = null;
  proto._selectedSegmentIds = null; // lazily created Set

  proto._mapViewStorageKey = function () {
    return `evcc_map_view_active_${vacuumObjectId(this.config?.vacuum ?? "")}`;
  };

  proto.isMapViewActive = function () {
    if (this._mapViewActive === null) {
      const stored = localStorage.getItem(this._mapViewStorageKey());
      this._mapViewActive = stored === "true";
    }
    return this._mapViewActive;
  };

  proto.setMapViewActive = function (active) {
    this._mapViewActive = Boolean(active);
    try {
      localStorage.setItem(this._mapViewStorageKey(), String(this._mapViewActive));
    } catch (_) {}
  };

  proto.toggleMapView = function () {
    this.setMapViewActive(!this.isMapViewActive());
  };

  proto.mapSegmentsData = function () {
    return this._mapSegmentsData;
  };

  proto.setMapSegmentsData = function (data) {
    const oldMapId = this._mapSegmentsData?.map_id;
    this._mapSegmentsData = data;
    if (data?.map_id !== oldMapId) {
      // Reset overlays when the active map changes — what was true for
      // the old map's segments has nothing to do with the new map's.
      this._segmentRoomOverlay = null;
      this._dotAnchorOverlay = null;
      this._mapAnchorMode = false;
      this.resetMapTransform();
    } else {
      // Same map, fresh data — the backend's authoritative state has
      // landed. Drop any optimistic overlay entries the user clicked
      // since the last fetch; they're either now reflected in the
      // backend payload or were rejected (rare; the action would log).
      this._segmentRoomOverlay = null;
      this._dotAnchorOverlay = null;
    }
    // One-time migration of legacy localStorage on the FIRST payload
    // with a real map_id. Idempotent across reloads — both helpers
    // bail if localStorage is empty.
    if (data?.map_id) {
      this._migrateLegacySegmentRoomLinks();
      this._migrateLegacyDotAnchors();
    }
  };

  proto.mapSegments = function () {
    return this._mapSegmentsData?.segments ?? [];
  };

  proto.mapImageUrl = function () {
    const variants = this._mapSegmentsData?.image_variants ?? {};
    return (variants.dark ?? variants.default ?? variants.light)?.browser_url ?? null;
  };

  proto._getSegmentIds = function () {
    if (!this._selectedSegmentIds) this._selectedSegmentIds = new Set();
    return this._selectedSegmentIds;
  };

  proto.selectedSegmentIds = function () {
    return this._getSegmentIds();
  };

  proto.isSegmentSelected = function (segmentId) {
    return this._getSegmentIds().has(String(segmentId));
  };

  proto.toggleSegmentSelected = function (segmentId) {
    const ids = this._getSegmentIds();
    const id = String(segmentId);
    if (ids.has(id)) {
      ids.delete(id);
    } else {
      ids.add(id);
    }
  };

  proto.clearSegmentSelection = function () {
    this._getSegmentIds().clear();
  };

  proto.enableSegmentForRoom = function (roomId) {
    const segId = this.segmentIdForRoom(roomId);
    if (segId) this._getSegmentIds().add(String(segId));
  };

  proto.disableSegmentForRoom = function (roomId) {
    const segId = this.segmentIdForRoom(roomId);
    if (segId) this._getSegmentIds().delete(String(segId));
  };

  proto.selectedSegments = function () {
    const segs = this.mapSegments();
    const result = [];
    for (const id of this._getSegmentIds()) {
      const seg = segs.find((s) => String(s.segment_id) === id);
      if (seg) result.push(seg);
    }
    return result;
  };

  /* =========================================================
     CONFIG VIEW STATE
     ========================================================= */

  proto._configSelectedSegmentId = null;

  proto.configSelectedSegmentId = function () {
    return this._configSelectedSegmentId;
  };

  proto.setConfigSelectedSegmentId = function (id) {
    this._configSelectedSegmentId = id != null ? String(id) : null;
  };

  /* =========================================================
     SEGMENT ↔ ROOM ASSOCIATIONS
     =========================================================
     One-to-one: each segment maps to at most one room and vice versa.
     Stored in localStorage per vacuum+map combination.
     ========================================================= */

  // Local optimistic-update overlay on top of the backend's canonical
  // segment_room_links map. Each segment payload from the backend
  // already carries its `room_id` field when linked; this Map only
  // exists so a freshly-clicked link is visible before the service
  // round-trip resolves. Cleared whenever fresh segments arrive.
  proto._segmentRoomOverlay = null;

  proto._segRoomLegacyKey = function () {
    const mapId = this._mapSegmentsData?.map_id ?? "unknown";
    const vacId = vacuumObjectId(this.config?.vacuum ?? "");
    return `evcc_seg_rooms_${vacId}_${mapId}`;
  };

  proto._ensureSegmentRoomOverlay = function () {
    if (!this._segmentRoomOverlay) this._segmentRoomOverlay = new Map();
    return this._segmentRoomOverlay;
  };

  /**
   * One-time migration: if browser localStorage has segment-room links
   * from an older card version AND the backend hasn't been told about
   * them yet, push each entry through the service and clear the
   * legacy key. Idempotent across reloads (the second call sees an
   * empty localStorage and bails).
   *
   * Called from setMapSegmentsData when fresh segments arrive — that's
   * also when we have an authoritative view of which links the backend
   * already knows about, so the comparison is accurate.
   */
  proto._migrateLegacySegmentRoomLinks = function () {
    let raw;
    try {
      raw = localStorage.getItem(this._segRoomLegacyKey());
    } catch (_) {
      return;
    }
    if (!raw) return;

    let legacy;
    try {
      legacy = JSON.parse(raw);
    } catch (_) {
      return;
    }
    if (!legacy || typeof legacy !== "object") return;

    // Build the set of links the backend already knows about, from the
    // freshly-loaded segments payload.
    const backendLinks = new Set();
    for (const seg of (this._mapSegmentsData?.segments) || []) {
      if (seg && seg.room_id != null) backendLinks.add(String(seg.segment_id));
    }

    const mapId = this._mapSegmentsData?.map_id;
    if (!mapId) return;

    // Push each legacy link the backend doesn't have. Fire-and-forget
    // is fine — the entire migration is best-effort, and any failure
    // means the user's link is preserved in localStorage for the next
    // attempt.
    let pushed = 0;
    for (const [segId, roomId] of Object.entries(legacy)) {
      if (backendLinks.has(String(segId))) continue;
      try {
        this.card?.setSegmentRoomLink?.(mapId, segId, roomId);
        pushed += 1;
      } catch (_) {}
    }

    // Clear localStorage regardless of pushed count — if everything
    // was already in the backend, we're done; otherwise the next
    // setMapSegmentsData will see backend-confirmed links.
    try {
      localStorage.removeItem(this._segRoomLegacyKey());
    } catch (_) {}

    if (pushed > 0 && console?.info) {
      console.info(
        `[evcc] Migrated ${pushed} segment-room link(s) from localStorage to backend.`
      );
    }
  };

  proto.roomIdForSegment = function (segmentId) {
    const segIdStr = String(segmentId);
    // Backend payload is canonical when present.
    const seg = this.mapSegments().find(
      (s) => String(s.segment_id) === segIdStr
    );
    if (seg?.room_id != null) return String(seg.room_id);
    // Optimistic overlay covers the gap between user click and backend ack.
    return this._segmentRoomOverlay?.get(segIdStr) ?? null;
  };

  proto.segmentIdForRoom = function (roomId) {
    const roomStr = String(roomId);
    const fromBackend = this.mapSegments().find(
      (s) => s.room_id != null && String(s.room_id) === roomStr
    );
    if (fromBackend) return String(fromBackend.segment_id);
    if (this._segmentRoomOverlay) {
      for (const [segId, rId] of this._segmentRoomOverlay) {
        if (rId === roomStr) return segId;
      }
    }
    return null;
  };

  /**
   * Assign a segment to a room. Optimistic local update + backend
   * service call. The local overlay covers the round-trip; once the
   * service responds and the next setMapSegmentsData arrives with
   * the link baked into the segment payload, the overlay is cleared.
   */
  proto.assignSegmentRoom = function (segmentId, roomId) {
    const segId = String(segmentId);
    const rId   = String(roomId);
    const overlay = this._ensureSegmentRoomOverlay();
    // Enforce 1:1 in the overlay too (matches backend's enforcement).
    for (const [s, r] of overlay) {
      if (r === rId && s !== segId) overlay.delete(s);
    }
    overlay.set(segId, rId);
    const mapId = this._mapSegmentsData?.map_id;
    if (mapId) {
      try { this.card?.setSegmentRoomLink?.(mapId, segId, rId); } catch (_) {}
    }
  };

  proto.unassignSegmentRoom = function (segmentId) {
    const segId = String(segmentId);
    this._ensureSegmentRoomOverlay().delete(segId);
    const mapId = this._mapSegmentsData?.map_id;
    if (mapId) {
      try { this.card?.setSegmentRoomLink?.(mapId, segId, null); } catch (_) {}
    }
  };

  proto.configSelectedSegment = function () {
    const id = this._configSelectedSegmentId;
    if (!id) return null;
    return this.mapSegments().find((s) => String(s.segment_id) === id) ?? null;
  };

  /* =========================================================
     ACTION STATUS
     ========================================================= */

  proto._mapActionStatus = null;

  proto.mapActionStatus = function () {
    return this._mapActionStatus;
  };

  proto.setMapActionStatus = function (status) {
    this._mapActionStatus = status;
  };

  proto.clearMapActionStatus = function () {
    this._mapActionStatus = null;
  };

  proto.mapNudgeStep = function () {
    const variants = this._mapSegmentsData?.image_variants ?? {};
    const variant = variants.dark ?? variants.default ?? variants.light;
    const w = variant?.width ?? 1000;
    const h = variant?.height ?? 1000;
    return {
      x: Math.max(1, Math.round(w * 0.005)),
      y: Math.max(1, Math.round(h * 0.005)),
    };
  };

  /* =========================================================
     ZOOM / PAN STATE
     =========================================================
     Transform is: translate(tx, ty) scale(zoom)
     with transform-origin: 0 0 on the .evcc-map-layers element.

     A point at layers-local coord (lx, ly) appears at
     container coord: (tx + lx * zoom, ty + ly * zoom).
     ========================================================= */

  proto._mapZoom = 1;
  proto._mapTranslateX = 0;
  proto._mapTranslateY = 0;

  proto.mapZoom = function () { return this._mapZoom; };
  proto.mapTranslateX = function () { return this._mapTranslateX; };
  proto.mapTranslateY = function () { return this._mapTranslateY; };

  proto.resetMapTransform = function () {
    this._mapZoom = 1;
    this._mapTranslateX = 0;
    this._mapTranslateY = 0;
  };

  proto.applyMapZoom = function (newZoom, originX, originY) {
    const clamped = Math.max(0.5, Math.min(8, newZoom));
    const ratio = clamped / this._mapZoom;
    this._mapTranslateX = originX - (originX - this._mapTranslateX) * ratio;
    this._mapTranslateY = originY - (originY - this._mapTranslateY) * ratio;
    this._mapZoom = clamped;
  };

  proto.applyMapPan = function (dx, dy) {
    this._mapTranslateX += dx;
    this._mapTranslateY += dy;
  };

  /* =========================================================
     DOT ANCHOR — per room, backend-persisted
     =========================================================
     Anchor is a pct position (0-100 space) for where the
     presence dot renders when the robot is in that room.
     Defaults to polygon centroid (computed in renderer).

     Storage moved from browser localStorage to the backend
     so anchors follow the user across browsers and devices.
     The card reads the canonical map from
     `_mapSegmentsData.companion_anchors` (which the backend
     enriches into the segments response). An optimistic
     overlay covers the user-click → service-ack window.
     ========================================================= */

  proto._dotAnchorOverlay = null;
  proto._mapAnchorMode    = false;

  proto._dotAnchorLegacyKey = function () {
    const mapId = this._mapSegmentsData?.map_id ?? "unknown";
    const vacId = vacuumObjectId(this.config?.vacuum ?? "");
    return `evcc_dot_anchors_${vacId}_${mapId}`;
  };

  proto._ensureDotAnchorOverlay = function () {
    if (!this._dotAnchorOverlay) this._dotAnchorOverlay = new Map();
    return this._dotAnchorOverlay;
  };

  /**
   * One-time migration: push any legacy localStorage anchors to the
   * backend on the first segments payload load, then clear the local
   * key. Idempotent across reloads.
   */
  proto._migrateLegacyDotAnchors = function () {
    let raw;
    try {
      raw = localStorage.getItem(this._dotAnchorLegacyKey());
    } catch (_) {
      return;
    }
    if (!raw) return;

    let legacy;
    try {
      legacy = JSON.parse(raw);
    } catch (_) {
      return;
    }
    if (!legacy || typeof legacy !== "object") return;

    const backendAnchors = this._mapSegmentsData?.companion_anchors || {};
    const mapId = this._mapSegmentsData?.map_id;
    if (!mapId) return;

    let pushed = 0;
    for (const [roomId, val] of Object.entries(legacy)) {
      if (backendAnchors[roomId]) continue;
      const pct_x = val?.pct_x;
      const pct_y = val?.pct_y;
      if (pct_x == null || pct_y == null) continue;
      try {
        this.card?.setCompanionAnchor?.(mapId, roomId, pct_x, pct_y);
        pushed += 1;
      } catch (_) {}
    }

    try {
      localStorage.removeItem(this._dotAnchorLegacyKey());
    } catch (_) {}

    if (pushed > 0 && console?.info) {
      console.info(
        `[evcc] Migrated ${pushed} companion anchor(s) from localStorage to backend.`
      );
    }
  };

  proto.roomDotAnchor = function (roomId) {
    const idStr = String(roomId);
    // Optimistic overlay covers click → ack window.
    if (this._dotAnchorOverlay?.has(idStr)) {
      return this._dotAnchorOverlay.get(idStr);
    }
    // Backend-canonical: rides along on the segments payload.
    const fromBackend = this._mapSegmentsData?.companion_anchors?.[idStr];
    return fromBackend ?? null;
  };

  proto.setRoomDotAnchor = function (roomId, pct_x, pct_y) {
    const idStr = String(roomId);
    this._ensureDotAnchorOverlay().set(idStr, { pct_x, pct_y });
    const mapId = this._mapSegmentsData?.map_id;
    if (mapId) {
      try {
        this.card?.setCompanionAnchor?.(mapId, idStr, pct_x, pct_y);
      } catch (_) {}
    }
  };

  proto.isMapAnchorMode = function () { return this._mapAnchorMode; };
  proto.setMapAnchorMode = function (v) { this._mapAnchorMode = Boolean(v); };

  /* =========================================================
     CURRENT MAP ROOM
     =========================================================
     Determines which room the robot is in by checking raw
     vacuum coordinates against each room's learned bounds.
     Uses the same margin as the backend BOUNDS_MARGIN = 50.
     ========================================================= */

  proto.currentMapRoom = function () {
    const pos = this.rawRobotPosition?.();
    if (!pos || pos.x == null || pos.y == null) return null;

    const rooms  = this.getRoomsForActiveMap?.() ?? [];
    const MARGIN = 50;

    for (const room of rooms) {
      if (room.is_transition || room.isTransition) continue;
      const b = room.bounds;
      if (!b) continue;
      if (
        pos.x >= b.min_x - MARGIN && pos.x <= b.max_x + MARGIN &&
        pos.y >= b.min_y - MARGIN && pos.y <= b.max_y + MARGIN
      ) {
        return room;
      }
    }
    return null;
  };

  proto._configSelectedVertexIndex = null;

  proto.configSelectedVertexIndex = function () {
    return this._configSelectedVertexIndex;
  };

  proto.setConfigSelectedVertexIndex = function (idx) {
    this._configSelectedVertexIndex = idx != null ? Number(idx) : null;
  };

  /* =========================================================
     ANIMAL SELECTION — which animal-svg companion to show
     =========================================================
     Persisted per vacuum in localStorage. Defaults to "cat".
     Available values come from the animal-svg registry:
     cat | dog | raccoon | parrot | snake
     ========================================================= */

  proto._mapAnimalSelection = null; // null = not yet read

  proto._animalSelectionKey = function () {
    return `evcc_animal_${vacuumObjectId(this.config?.vacuum ?? "")}`;
  };

  proto.mapAnimalSelection = function () {
    if (this._mapAnimalSelection === null) {
      try {
        this._mapAnimalSelection =
          localStorage.getItem(this._animalSelectionKey()) ?? "cat";
      } catch (_) {
        this._mapAnimalSelection = "cat";
      }
    }
    return this._mapAnimalSelection;
  };

  proto.setMapAnimalSelection = function (animal) {
    this._mapAnimalSelection = animal;
    try {
      localStorage.setItem(this._animalSelectionKey(), animal);
    } catch (_) {}
  };

  /* =========================================================
     ANIMAL SCALE
     =========================================================
     Multiplier applied to the base icon dimensions (64 × 44 px).
     Range: 0.5 – 3.0, step 0.25, default 1.0.
     Persisted per vacuum in localStorage.
     ========================================================= */

  proto._mapAnimalScale = null; // null = not yet read

  proto._animalScaleKey = function () {
    return `evcc_animal_scale_${vacuumObjectId(this.config?.vacuum ?? "")}`;
  };

  proto.mapAnimalScale = function () {
    if (this._mapAnimalScale === null) {
      try {
        const raw = parseFloat(localStorage.getItem(this._animalScaleKey()));
        this._mapAnimalScale = isFinite(raw) ? raw : 1.0;
      } catch (_) {
        this._mapAnimalScale = 1.0;
      }
    }
    return this._mapAnimalScale;
  };

  proto.setMapAnimalScale = function (scale) {
    const clamped = Math.max(0.5, Math.min(3.0, Number(scale)));
    this._mapAnimalScale = clamped;
    try {
      localStorage.setItem(this._animalScaleKey(), String(clamped));
    } catch (_) {}
  };
}
