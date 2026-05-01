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
      this._segmentRoomMap = null;
      this._mapRoomDotAnchors = null;
      this._mapAnchorMode = false;
      this.resetMapTransform();
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

  proto._segmentRoomMap = null;

  proto._segRoomStorageKey = function () {
    const mapId = this._mapSegmentsData?.map_id ?? "unknown";
    const vacId = vacuumObjectId(this.config?.vacuum ?? "");
    return `evcc_seg_rooms_${vacId}_${mapId}`;
  };

  proto._loadSegmentRooms = function () {
    if (this._segmentRoomMap) return;
    this._segmentRoomMap = new Map();
    try {
      const stored = localStorage.getItem(this._segRoomStorageKey());
      if (stored) {
        Object.entries(JSON.parse(stored)).forEach(([k, v]) =>
          this._segmentRoomMap.set(k, v)
        );
      }
    } catch (_) {}
  };

  proto._saveSegmentRooms = function () {
    try {
      localStorage.setItem(
        this._segRoomStorageKey(),
        JSON.stringify(Object.fromEntries(this._segmentRoomMap ?? []))
      );
    } catch (_) {}
  };

  proto.roomIdForSegment = function (segmentId) {
    this._loadSegmentRooms();
    const seg = this.mapSegments().find(
      (s) => String(s.segment_id) === String(segmentId)
    );
    if (seg?.room_id != null) return String(seg.room_id);
    return this._segmentRoomMap.get(String(segmentId)) ?? null;
  };

  proto.segmentIdForRoom = function (roomId) {
    this._loadSegmentRooms();
    const fromBackend = this.mapSegments().find(
      (s) => s.room_id != null && String(s.room_id) === String(roomId)
    );
    if (fromBackend) return String(fromBackend.segment_id);
    for (const [segId, rId] of this._segmentRoomMap) {
      if (rId === String(roomId)) return segId;
    }
    return null;
  };

  proto.assignSegmentRoom = function (segmentId, roomId) {
    this._loadSegmentRooms();
    const segId = String(segmentId);
    const rId   = String(roomId);
    for (const [s, r] of this._segmentRoomMap) {
      if (r === rId && s !== segId) {
        this._segmentRoomMap.delete(s);
        break;
      }
    }
    this._segmentRoomMap.set(segId, rId);
    this._saveSegmentRooms();
  };

  proto.unassignSegmentRoom = function (segmentId) {
    this._loadSegmentRooms();
    this._segmentRoomMap.delete(String(segmentId));
    this._saveSegmentRooms();
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
     DOT ANCHOR — per room, persisted per vacuum + map
     =========================================================
     Anchor is a pct position (0-100 space) for where the
     presence dot renders when the robot is in that room.
     Defaults to polygon centroid (computed in renderer).
     ========================================================= */

  proto._mapRoomDotAnchors = null;
  proto._mapAnchorMode     = false;

  proto._dotAnchorKey = function () {
    const mapId = this._mapSegmentsData?.map_id ?? "unknown";
    const vacId = vacuumObjectId(this.config?.vacuum ?? "");
    return `evcc_dot_anchors_${vacId}_${mapId}`;
  };

  proto._loadDotAnchors = function () {
    if (this._mapRoomDotAnchors) return;
    this._mapRoomDotAnchors = new Map();
    try {
      const raw = localStorage.getItem(this._dotAnchorKey());
      if (raw) {
        Object.entries(JSON.parse(raw)).forEach(([k, v]) =>
          this._mapRoomDotAnchors.set(k, v)
        );
      }
    } catch (_) {}
  };

  proto.roomDotAnchor = function (roomId) {
    this._loadDotAnchors();
    return this._mapRoomDotAnchors.get(String(roomId)) ?? null;
  };

  proto.setRoomDotAnchor = function (roomId, pct_x, pct_y) {
    this._loadDotAnchors();
    this._mapRoomDotAnchors.set(String(roomId), { pct_x, pct_y });
    try {
      localStorage.setItem(
        this._dotAnchorKey(),
        JSON.stringify(Object.fromEntries(this._mapRoomDotAnchors)),
      );
    } catch (_) {}
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
