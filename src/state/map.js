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

  // ---- Live-map rotation (display only, BACKEND-stored per map) ----
  // The live map image (Roborock) can be oriented differently from how the user
  // pictures their home; let them rotate it in 90° steps to match. Display only —
  // never touches dispatch (cleaning is by room id). Stored on the map bucket +
  // surfaced in the dashboard snapshot (write via the set_live_map_rotation
  // action/service) so the orientation FOLLOWS THE USER across browsers/devices,
  // like the dot anchors. An optimistic overlay covers the click → service-ack →
  // snapshot-refresh window so the turn is instant. Applied only to the live-image
  // element (which fills a SQUARE container, so a 90° turn about its centre stays
  // perfectly in frame) — NOT to CV/custom maps, whose polygons would drift.
  proto._mapRotationOverlay = null; // pending optimistic value (deg) or null
  proto._normRotation = function (deg) {
    return (((Math.round(Number(deg) / 90) * 90) % 360) + 360) % 360;
  };
  proto.mapRotation = function () {
    const snap = this._normRotation(this.dashboardSnapshot()?.live_map_rotation ?? 0);
    if (this._mapRotationOverlay != null) {
      // Drop the overlay once the backend snapshot has caught up to it.
      if (this._mapRotationOverlay === snap) { this._mapRotationOverlay = null; return snap; }
      return this._mapRotationOverlay;
    }
    return snap;
  };
  proto.setMapRotationOptimistic = function (deg) {
    this._mapRotationOverlay = this._normRotation(deg);
  };

  // The rotation ACTUALLY applied to the content rotator. The whole content block (backdrop +
  // co-rotated overlays/labels/masks) turns as one unit, so rotation is safe for the two
  // object-fit:contain backdrops that stay inside the SQUARE container at 90/270 — the VA
  // self-render canvas AND a live device image. It is NOT applied to an uploaded CV/custom
  // backdrop (which can be stretched `--fill` and would leave the square frame when turned).
  // The renderer AND the drag handlers (mascot, area-label) all read this one source, so a drag
  // converts pointer->content in the SAME frame the rotator is rendered in. (Rubber-band DRAWS
  // — zone/hide-area — still require rotation 0; their letterbox math isn't rotation-aware.)
  proto.effectiveMapRotation = function () {
    if (this.isVaRenderActive?.()) return this.mapRotation?.() ?? 0;
    const hasLiveImage = Boolean(this.liveMapImageEntity?.());
    const wantVa = Boolean(this.useVaRender?.() && this.supportsVaRender?.());
    return (hasLiveImage && !wantVa) ? (this.mapRotation?.() ?? 0) : 0;
  };

  // Map a pointer position given as a 0-100 pct of the (unrotated) .evcc-map-layers box
  // into the CONTENT frame inside .evcc-map-content-rotator, which is rotated `rot`
  // degrees. The container is square, so a 90/180/270 turn maps pct corners exactly.
  // Used by the mascot drag so a dragged anchor lands — and is stored — at the right
  // spot on a rotated live map (a 90/270 drag was previously off by the rotation).
  // Identity at rot 0.
  proto.unrotatePct = function (fx, fy, rot) {
    switch (this._normRotation(rot)) {
      case 90:  return [fy, 100 - fx];
      case 180: return [100 - fx, 100 - fy];
      case 270: return [100 - fy, fx];
      default:  return [fx, fy];
    }
  };

  // ---- Dwell-debounced mascot room tracker (display only) ----
  // Moves the mascot to the room the robot is PHYSICALLY in — including transit /
  // passthrough rooms not on the job queue — but only after the SAME room is seen
  // for N consecutive renders, so a flickery live current-room signal never makes
  // it jitter (sustained dwell IS the debounce). Reads the RAW brand current-room
  // NAME (lifecycle.active_cleaning_target) and resolves it to a managed room by
  // slug/name. Fully separate from the backend job-completion rollover (which stays
  // target-filtered + authoritative for the queue/timeline); this fires no events
  // and advances nothing. Holds the last committed room while a new candidate
  // accrues dwell; returns null before the first commit (the renderer then falls
  // back to the backend-computed position_room_id / current_room_id).
  proto._mascotDwellState = null;     // { observed: id|null, count, committed: id|null }
  proto._mascotDwellThreshold = 3;    // consecutive renders before a hop commits
  proto.mascotDwelledRoomId = function () {
    const st = this._mascotDwellState
      || (this._mascotDwellState = { observed: null, count: 0, committed: null });
    const resolved = this._resolveRoomIdByName(
      this.dashboardLifecycle?.()?.active_cleaning_target,
    );
    if (resolved == null) {
      // No usable signal this tick: break any in-progress streak but HOLD the last
      // committed room (don't snap the mascot away on a momentary blank/transit).
      st.observed = null;
      st.count = 0;
      return st.committed;
    }
    if (resolved === st.observed) {
      st.count += 1;
    } else {
      st.observed = resolved;
      st.count = 1;
    }
    if (st.count >= this._mascotDwellThreshold) st.committed = resolved;
    return st.committed;
  };

  // Resolve a raw current-room NAME to a managed room id (ANY room, incl. transit).
  // Slug first, then case/space-insensitive name; null for blank/sentinels/no match.
  proto._resolveRoomIdByName = function (rawName) {
    const norm = (s) => String(s ?? "").trim().toLowerCase().replace(/[\s_]+/g, " ");
    const n = norm(rawName);
    if (!n || ["unknown", "unavailable", "none", "null"].includes(n)) return null;
    for (const r of (this.getRoomsForActiveMap?.() ?? [])) {
      if (r?.slug != null && norm(r.slug) === n) return r.id;
      if (r?.name != null && norm(r.name) === n) return r.id;
    }
    return null;
  };

  proto.mapSegmentsData = function () {
    return this._mapSegmentsData;
  };

  proto.setMapSegmentsData = function (data) {
    const oldMapId = this._mapSegmentsData?.map_id;
    const oldKey = `${oldMapId ?? ""}:${this._mapSegmentsData?.active_custom_layout_id ?? ""}`;
    const newKey = `${data?.map_id ?? ""}:${data?.active_custom_layout_id ?? ""}`;
    this._mapSegmentsData = data;
    // Fresh backend segments are authoritative for hidden_regions + area-label anchors — drop
    // the optimistic overlays.
    this._hiddenRegionsOverlay = null;
    this._areaLabelOverlay = null;
    if (oldKey !== newKey) {
      // Reset overlays + draft when the active map OR layout changes — what was
      // true for the old map/layout's segments has nothing to do with the new.
      this._segmentRoomOverlay = null;
      this._dotAnchorOverlay = null;
      this._mapAnchorMode = false;
      this._hideDrawMode = false;        // exit hide-area draw on any map/layout switch
      this._composeDraft = null;       // new map/layout → fresh draft, reload from its segments
      this._composeSelectedId = null;
      this._composeMergeFrom = null;
      this._composeLoadedFor = null;
      this._zoneDrawMode = false;      // exit ad-hoc zone-draw on any map/layout switch
      this._zoneDrafts = [];
      this._mascotDwellState = null;   // fresh dwell tracking for the new map/layout
      if (data?.map_id !== oldMapId) {
        this.resetMapTransform();
        // Rotation is stored per-map; drop a pending optimistic overlay so a freshly
        // switched map renders at ITS rotation, not the previous map's.
        this._mapRotationOverlay = null;
      }
    } else {
      // Same map, fresh data — the backend's authoritative state has
      // landed. Drop any optimistic overlay entries the user clicked
      // since the last fetch; they're either now reflected in the
      // backend payload or were rejected (rare; the action would log).
      this._segmentRoomOverlay = null;
      this._dotAnchorOverlay = null;
    }
    // Legacy localStorage migration is driven by the action layer
    // (`getMapSegments` in actions/map.js) — state has no card
    // back-reference for service calls.
  };

  proto.mapSegments = function () {
    return this._mapSegmentsData?.segments ?? [];
  };

  proto.segmentationMode = function () {
    return this._mapSegmentsData?.segmentation_mode ?? "cv";
  };

  // Named custom layouts: a map can hold many (each its own backdrop / segments /
  // links / mascot anchors). The list + active id ride on every get_map_segments.
  proto.customLayouts = function () {
    return this._mapSegmentsData?.custom_layouts ?? [];
  };

  proto.activeCustomLayoutId = function () {
    return this._mapSegmentsData?.active_custom_layout_id ?? null;
  };

  proto.activeCustomLayout = function () {
    const id = this.activeCustomLayoutId();
    if (id == null) return null;
    return (this.customLayouts() || []).find((l) => String(l.id) === String(id)) ?? null;
  };

  // ---- Custom-layout name editor (create / rename) ----
  proto._layoutEditor = null;
  proto._ensureLayoutEditor = function () {
    if (!this._layoutEditor) this._layoutEditor = { open: false, mode: "new", name: "" };
    return this._layoutEditor;
  };
  proto.isLayoutEditorOpen = function () { return this._ensureLayoutEditor().open === true; };
  proto.layoutEditorMode = function () { return this._ensureLayoutEditor().mode; };
  proto.layoutDraftName = function () { return this._ensureLayoutEditor().name; };
  proto.setLayoutDraftName = function (name) { this._ensureLayoutEditor().name = String(name ?? ""); };
  proto.openNewLayoutEditor = function () { this._layoutEditor = { open: true, mode: "new", name: "" }; };
  proto.openRenameLayoutEditor = function () {
    this._layoutEditor = { open: true, mode: "rename", name: this.activeCustomLayout()?.name ?? "" };
  };
  proto.closeLayoutEditor = function () { this._layoutEditor = { open: false, mode: "new", name: "" }; };

  proto.mapImageUrl = function () {
    const variants = this._mapSegmentsData?.image_variants ?? {};
    // In custom mode the authored polygons sit on the ACTIVE layout's OWN
    // backdrop (custom_<id>). Show only that: a per-layout backdrop that has
    // not been uploaded yet must read as "missing" (-> upload prompt), never
    // silently borrow a sibling layout's image. Only the shared/legacy "custom"
    // variant keeps the CV-image fallback, for trace-over on the pre-layout flow.
    if (this.segmentationMode() === "custom") {
      // A layout explicitly pinned to the live map ("Live map" source) always shows
      // the brand's live image as its backdrop — never an uploaded variant — so you
      // compose rooms straight over the live camera/image.
      if (this.activeCustomLayout()?.backdrop_source === "live") {
        return this._liveMapImageUrl();
      }
      const v = this.activeCustomLayout()?.backdrop_variant || "custom";
      const own = variants[v];
      if (own) return own.browser_url ?? null;
      // A per-layout backdrop that hasn't been uploaded falls back to the brand's
      // LIVE image (Roborock) so the user can compose room polygons straight over
      // the live map — no static upload needed (the save captures its pixel size).
      if (v !== "custom") return this._liveMapImageUrl();
      return (variants.dark ?? variants.default ?? variants.light)?.browser_url
        ?? this._liveMapImageUrl();
    }
    // No CV/custom backdrop (e.g. a Roborock with native segments and no uploaded
    // map): fall back to the brand's LIVE map image entity if one is declared.
    return (variants.dark ?? variants.default ?? variants.light)?.browser_url
      ?? this._liveMapImageUrl();
  };

  // Live-camera poll tick. Bumped by the card's poll timer (main._scheduleLiveMapRefresh)
  // so a camera.* backdrop refetches on the frame cadence — see _liveMapImageUrl below.
  proto._liveMapTick = 0;
  proto.bumpLiveMapTick = function () { this._liveMapTick = (this._liveMapTick || 0) + 1; };

  /**
   * The LIVE map backdrop URL: the live-map entity's entity_picture.
   * - An `image.` entity (Roborock current map) rotates its token on each frame, so
   *   the URL self-busts and <img src> refreshes live with no polling.
   * - A `camera.` entity (e.g. the eufy-clean fork's camera.<device>_map) has a STABLE
   *   token, and HA dedupes identical state writes, so its last_updated only advances on
   *   token rotation (~5 min) — NOT per pushed frame. last_updated alone would leave the
   *   <img> on a frozen frame until a manual refresh; the card polls the camera on the
   *   frame cadence (main._scheduleLiveMapRefresh) and bumps _liveMapTick, which we fold
   *   into the cache-bust so each poll refetches the latest frame.
   * Null when the adapter declares no live entity (plain Eufy) or there's no picture yet.
   */
  proto._liveMapImageUrl = function () {
    const eid = this.liveMapImageEntity?.();
    if (!eid) return null;
    const ent = this.entity?.(eid);
    const url = ent?.attributes?.entity_picture ?? null;
    if (!url) return null;
    let stamp = ent?.last_updated ? Date.parse(ent.last_updated) : 0;
    // camera.* doesn't self-bust (stable token + deduped writes) -> fold in the poll tick.
    if (eid.startsWith("camera.")) stamp += (this._liveMapTick || 0);
    if (!stamp) return url;
    return url + (url.includes("?") ? "&" : "?") + "_=" + stamp;
  };

  /**
   * True when the active custom layout is backed by the LIVE image (no uploaded
   * backdrop). The composer must then render the backdrop with object-fit:contain
   * (NOT the custom-mode --fill stretch) so a non-square live image letterboxes the
   * SAME way in the composer and the room view — keeping drawn polygons aligned to
   * the picture in both. Uploaded custom backdrops keep the fill behaviour.
   */
  proto.isLiveBackdropActive = function () {
    if (this.segmentationMode() !== "custom") return false;
    // A layout pinned to the live map is always live-backed (ignores any upload).
    if (this.activeCustomLayout()?.backdrop_source === "live") {
      return Boolean(this._liveMapImageUrl());
    }
    const variants = this._mapSegmentsData?.image_variants ?? {};
    const v = this.activeCustomLayout()?.backdrop_variant || "custom";
    if (variants[v]) return false; // an uploaded backdrop exists -> not live-backed
    return Boolean(this._liveMapImageUrl());
  };

  // ---- Custom-segment composer draft (in-progress shapes, not yet saved) ----
  // Each shape is one room/segment: { id, type:"rect"|"circle", ...geom (pct),
  // room_id? }. Saved (replace-all) via set_custom_segments in a later pass.
  proto._composeDraft = null; // lazily []
  proto._composeSelectedId = null;
  proto._composeNextId = 1;

  proto.composeDraft = function () {
    if (this._composeDraft === null) this._composeDraft = [];
    return this._composeDraft;
  };

  proto.composeSelectedId = function () {
    return this._composeSelectedId;
  };

  proto.selectComposeShape = function (id) {
    this._composeSelectedId = id ?? null;
  };

  proto.addComposeShape = function (type) {
    // Guarantee a fresh id even if loaded shapes reused earlier draft_N ids
    // (the counter resets on page load; reloaded shapes keep their saved ids).
    const used = new Set(this.composeDraft().map((s) => s.id));
    let id;
    do { id = `draft_${this._composeNextId++}`; } while (used.has(id));
    const off = (this.composeDraft().length % 6) * 5; // cascade so adds don't stack
    const shape = type === "circle"
      ? { id, type: "circle", cx: 28 + off, cy: 28 + off, r: 14 }
      : { id, type: "rect", x: 22 + off, y: 22 + off, w: 28, h: 22, angle: 0 };
    this.composeDraft().push(shape);
    this._composeSelectedId = id;
    return shape;
  };

  // ── Ad-hoc zone clean (draw boxes on the live map → clean them) ─────────
  // Transient card-only state (like the compose draft): a LIST of rectangles in
  // pct (0-100) of the square map container, drawn → dispatched → discarded.
  // Never persisted. _zoneDrawMode toggles the draw interaction; _zoneDrafts holds
  // the committed rectangles ({x,y,w,h} pct). The in-progress drag box is painted
  // straight to the DOM and pushed here on release. App cap = 10 zones per clean.
  proto._ZONE_MAX = 10;
  proto._zoneDrawMode = false;
  proto._zoneDrafts = null; // lazily []

  proto.zoneDrawMode = function () { return this._zoneDrawMode; };
  proto.zoneDrafts = function () {
    if (this._zoneDrafts === null) this._zoneDrafts = [];
    return this._zoneDrafts;
  };
  proto.zoneCount = function () { return this.zoneDrafts().length; };
  proto.zoneMax = function () { return this._ZONE_MAX; };
  proto.zoneAtCap = function () { return this.zoneCount() >= this._ZONE_MAX; };

  proto.setZoneDrawMode = function (on) {
    this._zoneDrawMode = Boolean(on);
    if (!this._zoneDrawMode) this._zoneDrafts = [];
  };

  // Commit one drawn rectangle. Returns false (ignored) once at the 10-zone cap.
  proto.addZoneDraft = function (rect) {
    if (!rect) return false;
    const list = this.zoneDrafts();
    if (list.length >= this._ZONE_MAX) return false;
    list.push({ x: rect.x, y: rect.y, w: rect.w, h: rect.h });
    return true;
  };
  proto.removeZoneDraft = function (i) {
    const list = this.zoneDrafts();
    if (i >= 0 && i < list.length) list.splice(i, 1);
  };
  proto.clearZoneDrafts = function () { this._zoneDrafts = []; };

  /**
   * Convert ONE pct rect (0-100 of the SQUARE map container) into a normalized
   * [x0,y0,x1,y1] in the live-map IMAGE frame (fractions 0-1, top-left origin) —
   * the shape the provider's zone_clean expects. Corrects for `object-fit:contain`
   * letterboxing: the longer image side fills the box; the shorter side is centered
   * with equal bars, so "50% of the box" is NOT 50% of the image on a non-square map.
   * Returns null for a degenerate rect (drawn entirely inside a letterbox bar).
   *
   * @param {{x:number,y:number,w:number,h:number}} d pct rect
   * @param {{width:number,height:number}} backdropDims natural px of the live image
   * @returns {number[]|null} [x0,y0,x1,y1] in 0-1, or null
   */
  proto._rectToNormalized = function (d, backdropDims) {
    if (!d || !backdropDims) return null;
    const W = backdropDims.width, H = backdropDims.height;
    if (!(W > 0) || !(H > 0)) return null;
    const imgPctW = W >= H ? 100 : (100 * W) / H;
    const imgPctH = H >= W ? 100 : (100 * H) / W;
    const offX = (100 - imgPctW) / 2;
    const offY = (100 - imgPctH) / 2;
    const clamp01 = (v) => Math.min(Math.max(v, 0), 1);
    const toNorm = (px, py) => [
      clamp01((px - offX) / imgPctW),
      clamp01((py - offY) / imgPctH),
    ];
    const [nx0, ny0] = toNorm(Math.min(d.x, d.x + d.w), Math.min(d.y, d.y + d.h));
    const [nx1, ny1] = toNorm(Math.max(d.x, d.x + d.w), Math.max(d.y, d.y + d.h));
    const x0 = Math.min(nx0, nx1), y0 = Math.min(ny0, ny1);
    const x1 = Math.max(nx0, nx1), y1 = Math.max(ny0, ny1);
    const MIN_SIDE = 0.01;
    if (x1 - x0 < MIN_SIDE || y1 - y0 < MIN_SIDE) return null;
    return [x0, y0, x1, y1];
  };

  // All committed zones as normalized [x0,y0,x1,y1] rects (degenerate ones dropped).
  proto.zoneDraftsToNormalizedRects = function (backdropDims) {
    return this.zoneDrafts()
      .map((d) => this._rectToNormalized(d, backdropDims))
      .filter(Boolean);
  };

  /**
   * Single source of truth for whether the ad-hoc zone-draw control may be
   * shown AND used right now: the provider supports zone clean, a live-map
   * backdrop is active (you draw on that image), and rotation is 0 (Wave 1 — a
   * rotated map letterboxes on the swapped axis, not yet handled). The renderer
   * gate and the drag/confirm guards both call this so they can never drift.
   */
  proto.canDrawZone = function () {
    return (this.supportsZoneClean?.() ?? false)
        && (this.isLiveBackdropActive?.() ?? false)
        && (this.mapRotation?.() ?? 0) === 0;
  };

  /* =========================================================
     HIDDEN REGIONS (user-drawn rects that MASK map noise, e.g. a
     porch off a room). Persisted per-map like companion_anchors
     (ride along on get_map_segments as `hidden_regions`); stored as
     normalized [x0,y0,x1,y1] in the rendered-image frame — the same
     space the device overlays use, so _overlayTransform places them.
     ========================================================= */
  proto._hideDrawMode = false;
  proto.hideDrawMode = function () { return this._hideDrawMode; };
  proto.setHideDrawMode = function (on) { this._hideDrawMode = Boolean(on); };

  // Optimistic overlay so a draw/delete shows instantly; the set_hidden_regions
  // response (authoritative) replaces it, and a fresh segments fetch clears it.
  proto._hiddenRegionsOverlay = null;
  proto.hiddenRegions = function () {
    if (Array.isArray(this._hiddenRegionsOverlay)) return this._hiddenRegionsOverlay;
    // Editor fetch when present, else the dashboard snapshot — same reason as areaLabelAnchor.
    // Empty-aware: a present-but-empty [] from the editor must not shadow a populated snapshot
    // (get_map_segments always emits hidden_regions:[]). An intentional in-editor clear is held
    // by the optimistic overlay above until the snapshot settles.
    const seg = this.mapSegmentsData?.()?.hidden_regions;
    const r = (Array.isArray(seg) && seg.length)
      ? seg
      : this.dashboardSnapshot?.()?.hidden_regions;
    return Array.isArray(r) ? r : [];
  };
  proto.setHiddenRegionsOptimistic = function (list) {
    this._hiddenRegionsOverlay = Array.isArray(list) ? list : [];
  };
  proto.clearHiddenRegionsOptimistic = function () { this._hiddenRegionsOverlay = null; };

  // Draw gate: a device-overlay-aligned backdrop is shown (live image OR VA render — the
  // masks need map_state_source.image_size for the letterbox transform) and rotation is 0
  // (a rotated map letterboxes on the swapped axis — not handled for drawing, same as zones).
  proto.canDrawHideArea = function () {
    return (this.overlaysAligned?.() ?? false)
        && !!this.mapImageSize?.()
        && (this.mapRotation?.() ?? 0) === 0;
  };

  /* =========================================================
     AREA-LABEL ANCHORS — per-room position for the m² chip, so it
     can be dragged off the room-name label. Map-level (the device
     rooms are mode-independent), keyed by room number, {pct_x,pct_y}
     in map-content-box % (same frame as the mascot anchor). Rides on
     get_map_segments as `area_label_anchors`. null => default (centre).
     ========================================================= */
  proto._areaLabelOverlay = null;
  proto.areaLabelAnchor = function (roomKey) {
    const k = String(roomKey);
    if (this._areaLabelOverlay && this._areaLabelOverlay[k]) return this._areaLabelOverlay[k];
    // Editor fetch (get_map_segments) when present, else the dashboard snapshot — the m² chips
    // render on the plain dashboard (overlaysAligned) where segments are NOT fetched, so the
    // saved positions must ride the snapshot too (mirrors map_overlay_visibility). Without the
    // snapshot fallback a dragged label reverts to centre on reload off the editor.
    // Empty-aware: get_map_segments ALWAYS emits area_label_anchors:{} and the editor cache
    // isn't cleared on leaving the editor, so a `??` chain would let a present-but-empty {}
    // shadow a populated snapshot. Only treat the editor set as authoritative when non-empty.
    const seg = this.mapSegmentsData?.()?.area_label_anchors;
    const anchors = (seg && Object.keys(seg).length)
      ? seg
      : this.dashboardSnapshot?.()?.area_label_anchors;
    return (anchors && anchors[k]) || null;
  };
  proto.setAreaLabelAnchorLocal = function (roomKey, pctX, pctY) {
    if (!this._areaLabelOverlay) this._areaLabelOverlay = {};
    this._areaLabelOverlay[String(roomKey)] = { pct_x: pctX, pct_y: pctY };
  };

  /* =========================================================
     MAP_STATE_SOURCE OVERLAYS (Wave 3c) — the VA's read of the
     device's own map (rooms+area, anchors, no-go/walls/zones/path/
     obstacles), normalized 0–1 of the LIVE rendered image, + the
     per-layer visibility the user toggles.
     ========================================================= */

  // Card-side defaults — a mirror of the backend OVERLAY_VISIBILITY_DEFAULTS, used
  // only if the snapshot omits a layer (it normally resolves all of them server-side).
  proto._OVERLAY_VIS_DEFAULTS = {
    room_labels: true, room_area: true, current_room: true, robot: true, dock: true,
    no_go: false, no_mop: false, walls: false, zones: false, path: false, obstacles: false,
    hidden_regions: true,
  };

  proto.mapStateSource = function () {
    return this.dashboardSnapshot?.()?.map_state_source ?? null;
  };

  /* -- Auto-derived click targets: pixel-exact room hit-test ---------------------
     Given a CONTENT-box % point (0-100 of the rotator, i.e. AFTER unrotatePct), resolve the
     DEVICE ROOM ID under it by reading the room raster from the card-render data (room_pixels
     + decode params from get_map_render_data — the same bundle the ▦ render decodes). Exact
     room boundaries (no bbox overlap). null when off-map / a catch-all cell / no render data.
     The device room id IS the managed room id, so the caller toggles it straight into the
     clean selection. */
  proto._roomRasterBin = function (rd) {
    // Decode the base64 raster once, cached by content version.
    if (this._roomRasterCache && this._roomRasterCache.version === rd.version) {
      return this._roomRasterCache.bin;
    }
    let bin = null;
    try { bin = atob(rd.room_pixels || ""); } catch (_) { bin = null; }
    this._roomRasterCache = { version: rd.version, bin };
    return bin;
  };

  proto.roomIdAtContentPct = function (contentX, contentY, rd) {
    if (!rd || !rd.present || !rd.room_pixels) return null;
    const W = rd.width | 0, H = rd.height | 0;
    if (!(W > 0 && H > 0)) return null;
    // content% -> image-normalized: undo the object-fit:contain letterbox (same math as
    // _overlayTransform/_rectToNormalized). Aspect comes from map_state_source.image_size when
    // present, else the render dims (rd.width/height) — the VA canvas IS letterboxed by those, and
    // for the camera-less VA-render config map_state_source is absent, so mapImageSize() is null.
    // Both derive from the same md.width/height, so this is byte-identical whenever both exist.
    const size = this.mapImageSize?.();
    const iw = (Array.isArray(size) && size[0] > 0 && size[1] > 0) ? size[0] : W;
    const ih = (Array.isArray(size) && size[0] > 0 && size[1] > 0) ? size[1] : H;
    const sx = iw >= ih ? 100 : (100 * iw) / ih;
    const sy = ih >= iw ? 100 : (100 * ih) / iw;
    const offX = (100 - sx) / 2;
    const offY = (100 - sy) / 2;
    const nx = (contentX - offX) / sx;
    const ny = (contentY - offY) / sy;
    if (nx < 0 || nx > 1 || ny < 0 || ny > 1) return null;   // outside the image (letterbox bar)
    // image-normalized -> MAIN-grid pixel (undo normalize_rendered's Y-flip).
    const flip = rd.flip_y !== false;
    const px = Math.min(W - 1, Math.max(0, Math.floor(nx * W)));
    const pyN = flip ? ((H - 1) - ny * H) : (ny * H);
    const py = Math.min(H - 1, Math.max(0, Math.floor(pyN)));
    // MAIN grid -> room_outline raster cell -> rid (byte >> rid_shift), catch-all filtered.
    const bin = this._roomRasterBin(rd);
    if (!bin) return null;
    const roW = rd.ro_width | 0, roH = rd.ro_height | 0;
    const rx = px - (rd.ro_dx | 0), ry = py - (rd.ro_dy | 0);
    if (rx < 0 || rx >= roW || ry < 0 || ry >= roH) return null;
    const idx = ry * roW + rx;
    if (idx < 0 || idx >= bin.length) return null;
    const rid = bin.charCodeAt(idx) >> (rd.rid_shift | 0);
    const catchAll = rd.catch_all_rid | 0;
    return (rid > 0 && rid < catchAll) ? rid : null;
  };

  /* -- Live pose (Phase B) ------------------------------------------------------
     The snapshot's map_state_source carries the MOVING overlays (robot/dock/current-
     room/path) too, but only as fresh as the slow snapshot cadence — so a cleaning
     robot visibly lags. The card polls get_map_live_pose (~2s, in-memory, loop-safe)
     and stashes the result here; mapOverlayData() folds it over the snapshot so the
     STATIC segmentation (rooms/area/hazards/image_size) stays from the snapshot while
     the moving fields track live. null => no live override (poll off / unsupported). */
  proto._livePose = null;
  proto.setLivePose = function (pose) {
    this._livePose = (pose && pose.present) ? pose : null;
  };
  proto.livePose = function () { return this._livePose; };

  // The overlay source the device-overlay renderers read: the snapshot map_state_source
  // with the live pose's moving fields layered on top (when present). Same normalized
  // frame, so the existing letterbox transform (image_size) still applies unchanged.
  proto.mapOverlayData = function () {
    const base = this.mapStateSource();
    const lp = this._livePose;
    if (!base || !base.present || !lp || !lp.present) return base;
    const merged = { ...base };
    // The live pose OWNS current_room + path when present: clear the stale snapshot values
    // first (mirrors the backend apply_live_pose_override) so a live anchor in a no-room
    // (catch-all) cell, or with no live trail, can't leave the old room highlighted / a
    // lagged trail drawn — the exact "stale in the kitchen" ghost this feature kills.
    delete merged.current_room;
    delete merged.path;
    if (Array.isArray(lp.robot_anchor)) merged.robot_anchor = lp.robot_anchor;
    if (Array.isArray(lp.dock_anchor)) merged.dock_anchor = lp.dock_anchor;
    if (lp.current_room != null) merged.current_room = lp.current_room;
    if (lp.robot_heading != null) merged.robot_heading = lp.robot_heading;
    if (Array.isArray(lp.path)) merged.path = lp.path;
    merged.robot_docked = Boolean(lp.robot_docked);
    return merged;
  };

  // Rendered-image dims [w, h] for the overlay letterbox correction (the overlays are
  // normalized to the IMAGE frame, but the live <img> is object-fit:contain inside a
  // SQUARE box). Only the aspect is used. null → card assumes square (no correction).
  proto.mapImageSize = function () {
    const s = this.mapStateSource()?.image_size;
    return (Array.isArray(s) && s.length === 2 && s[0] > 0 && s[1] > 0) ? s : null;
  };

  // Pending optimistic per-layer toggles (cleared once the snapshot catches up),
  // so a checkbox flip is instant across the click → service-ack → refresh window.
  proto._overlayVisOverlay = null;
  proto.mapOverlayVisibility = function () {
    const snap = this.dashboardSnapshot?.()?.map_overlay_visibility ?? {};
    const base = { ...this._OVERLAY_VIS_DEFAULTS, ...snap };
    if (this._overlayVisOverlay) {
      for (const [k, v] of Object.entries(this._overlayVisOverlay)) {
        if (snap[k] === v) delete this._overlayVisOverlay[k]; // backend caught up
        else base[k] = v;
      }
      if (Object.keys(this._overlayVisOverlay).length === 0) this._overlayVisOverlay = null;
    }
    return base;
  };
  proto.isOverlayVisible = function (layer) {
    return Boolean(this.mapOverlayVisibility()[layer]);
  };
  proto.setOverlayVisibilityOptimistic = function (layer, on) {
    if (!this._overlayVisOverlay) this._overlayVisOverlay = {};
    this._overlayVisOverlay[layer] = Boolean(on);
  };
  // Roll back one pending optimistic flip (e.g. the service call failed) so the
  // checkbox + overlay revert to the backend value instead of sticking unsaved.
  proto.clearOverlayVisibilityOptimistic = function (layer) {
    if (!this._overlayVisOverlay) return;
    delete this._overlayVisOverlay[layer];
    if (Object.keys(this._overlayVisOverlay).length === 0) this._overlayVisOverlay = null;
  };

  /**
   * True when the DISPLAYED backdrop is the LIVE device image — the only space the
   * map_state_source overlays are normalized to. Mirrors mapImageUrl()'s live
   * branches: Roborock/no-CV always live; Eufy shows the CV image unless a live
   * source is active, so overlays hide there (they'd misalign). NOT
   * isLiveBackdropActive() (that's the custom-layout-pinned-to-live predicate).
   */
  proto.isLiveImageDisplayed = function () {
    if (!this._liveMapImageUrl?.()) return false;
    const variants = this._mapSegmentsData?.image_variants ?? {};
    const hasCv = Boolean(variants.dark || variants.default || variants.light);
    if (this.segmentationMode?.() === "custom") {
      if (this.activeCustomLayout?.()?.backdrop_source === "live") return true;
      const v = this.activeCustomLayout?.()?.backdrop_variant || "custom";
      if (variants[v]) return false;     // an uploaded custom backdrop is showing
      if (v !== "custom") return true;   // per-layout, not uploaded → live
      return !hasCv;                     // shared "custom": CV fallback if present
    }
    return !hasCv;                       // non-custom: CV variant if present, else live
  };

  /* =========================================================
     VA-RENDERED MAP BACKDROP (Wave 1 — client-side canvas, no dependency)
     =========================================================
     The card draws its OWN full-grid backdrop from the device's room raster
     (get_map_render_data, adapter-driven). The VA owns the frame, so the overlays
     align perfectly (no fork-camera crop). A per-vacuum toggle picks it over the
     live camera; the raster is cached in-memory by version (static; re-fetched only
     when the map changes). Only offered when the adapter supplies a map_render block.
     ========================================================= */

  proto.supportsVaRender = function () {
    return Boolean(this.dashboardSnapshot?.()?.supports_va_render);
  };

  proto._useVaRender = null; // null = not yet read from localStorage
  proto._useVaRenderKey = function () {
    return `evcc_va_render_${vacuumObjectId(this.config?.vacuum ?? "")}`;
  };
  proto.useVaRender = function () {
    if (this._useVaRender === null) {
      try {
        this._useVaRender = localStorage.getItem(this._useVaRenderKey()) === "1";
      } catch (_) {
        this._useVaRender = false;
      }
    }
    return this._useVaRender;
  };
  proto.setUseVaRender = function (on) {
    this._useVaRender = !!on;
    // (Re)enabling drops any cached render data so the binding re-fetches fresh — this
    // is also the retry path after a failed fetch (which stored a present:false sentinel).
    if (on) this._mapRenderData = null;
    try {
      localStorage.setItem(this._useVaRenderKey(), on ? "1" : "0");
    } catch (_) {}
  };
  proto.toggleUseVaRender = function () {
    this.setUseVaRender(!this.useVaRender());
  };

  // In-memory cache of the get_map_render_data response (the raster + decode params).
  proto._mapRenderData = null;
  proto.mapRenderData = function () {
    return this._mapRenderData;
  };
  proto.setMapRenderData = function (rd) {
    this._mapRenderData = (rd && typeof rd === "object") ? rd : null;
  };
  proto.mapRenderVersion = function () {
    return this._mapRenderData?.version ?? null;
  };

  // The VA canvas is the active backdrop right now (toggle on + brand supports it +
  // we have render data to draw).
  proto.isVaRenderActive = function () {
    return this.useVaRender()
        && this.supportsVaRender()
        && Boolean(this.mapRenderData()?.present);
  };

  // Overlays + the layers panel align on ANY grid-frame backdrop: the live device
  // image OR the VA render. (Both are normalized to the same image_size grid.)
  proto.overlaysAligned = function () {
    return (this.isLiveImageDisplayed?.() ?? false) || this.isVaRenderActive();
  };

  proto.updateComposeShape = function (id, patch) {
    const s = this.composeDraft().find((x) => x.id === id);
    if (s) Object.assign(s, patch);
  };

  proto.deleteComposeShape = function (id) {
    this._composeDraft = this.composeDraft().filter((x) => x.id !== id);
    if (this._composeSelectedId === id) this._composeSelectedId = null;
    if (this._composeMergeFrom === id) this._composeMergeFrom = null;
  };

  proto.clearComposeDraft = function () {
    this._composeDraft = [];
    this._composeSelectedId = null;
    this._composeMergeFrom = null;
  };

  // Move / scale / resize a shape — all button-driven (mobile-friendly, no drag).
  // Geometry is pct (0-100); scale + resize keep the shape centred.
  proto.moveComposeShape = function (id, dx, dy) {
    const s = this.composeDraft().find((x) => x.id === id);
    if (!s) return;
    const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));
    if (s.type === "circle") {
      s.cx = clamp(s.cx + dx, 0, 100);
      s.cy = clamp(s.cy + dy, 0, 100);
    } else if (s.type === "polygon") {
      const xs = s.points.map((p) => p[0]), ys = s.points.map((p) => p[1]);
      const ddx = clamp(dx, -Math.min(...xs), 100 - Math.max(...xs));
      const ddy = clamp(dy, -Math.min(...ys), 100 - Math.max(...ys));
      s.points = s.points.map(([x, y]) => [x + ddx, y + ddy]);
    } else {
      s.x = clamp(s.x + dx, 0, 100 - s.w);
      s.y = clamp(s.y + dy, 0, 100 - s.h);
    }
  };

  proto.scaleComposeShape = function (id, factor) {
    const s = this.composeDraft().find((x) => x.id === id);
    if (!s) return;
    const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));
    if (s.type === "circle") {
      s.r = clamp(s.r * factor, 2, 50);
    } else if (s.type === "polygon") {
      const xs = s.points.map((p) => p[0]), ys = s.points.map((p) => p[1]);
      const cx = (Math.min(...xs) + Math.max(...xs)) / 2;
      const cy = (Math.min(...ys) + Math.max(...ys)) / 2;
      s.points = s.points.map(([x, y]) => [
        clamp(cx + (x - cx) * factor, 0, 100),
        clamp(cy + (y - cy) * factor, 0, 100),
      ]);
    } else {
      const cx = s.x + s.w / 2, cy = s.y + s.h / 2;
      s.w = clamp(s.w * factor, 3, 100);
      s.h = clamp(s.h * factor, 3, 100);
      s.x = clamp(cx - s.w / 2, 0, 100 - s.w);
      s.y = clamp(cy - s.h / 2, 0, 100 - s.h);
    }
  };

  proto.resizeComposeShape = function (id, dim, delta) {
    const s = this.composeDraft().find((x) => x.id === id);
    if (!s || s.type !== "rect") return;   // W/H only applies to rectangles
    const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));
    const cx = s.x + s.w / 2, cy = s.y + s.h / 2;
    if (dim === "w") {
      s.w = clamp(s.w + delta, 3, 100);
      s.x = clamp(cx - s.w / 2, 0, 100 - s.w);
    } else {
      s.h = clamp(s.h + delta, 3, 100);
      s.y = clamp(cy - s.h / 2, 0, 100 - s.h);
    }
  };

  // Nudge step size (pct). Fine=1 / Med=3 / Coarse=7; move + resize scale by it.
  proto._composeStep = 3;
  proto.composeStep = function () { return this._composeStep; };
  proto.setComposeStep = function (n) { this._composeStep = Number(n) || 3; };

  // Tap-to-place: jump the selected shape's centre to a pct point on the map.
  proto.placeComposeShape = function (id, pctX, pctY) {
    const s = this.composeDraft().find((x) => x.id === id);
    if (!s) return;
    const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));
    if (s.type === "circle") {
      s.cx = clamp(pctX, 0, 100);
      s.cy = clamp(pctY, 0, 100);
    } else if (s.type === "polygon") {
      const xs = s.points.map((p) => p[0]), ys = s.points.map((p) => p[1]);
      const cx = (Math.min(...xs) + Math.max(...xs)) / 2;
      const cy = (Math.min(...ys) + Math.max(...ys)) / 2;
      this.moveComposeShape(id, pctX - cx, pctY - cy);
    } else {
      s.x = clamp(pctX - s.w / 2, 0, 100 - s.w);
      s.y = clamp(pctY - s.h / 2, 0, 100 - s.h);
    }
  };

  // Map the draft to the set_custom_segments payload. Group-aware: shapes are
  // bucketed by `group` (default = each shape's own id, i.e. one room each), so
  // merge/cut (shared group + op:subtract) drops in later with no change here.
  proto.composeToSegments = function () {
    const rectCorners = (s) => {
      const cx = s.x + s.w / 2, cy = s.y + s.h / 2;
      const rad = ((s.angle || 0) * Math.PI) / 180, cos = Math.cos(rad), sin = Math.sin(rad);
      const rot = (px, py) => [
        Math.round((cx + (px - cx) * cos - (py - cy) * sin) * 100) / 100,
        Math.round((cy + (px - cx) * sin + (py - cy) * cos) * 100) / 100,
      ];
      return [rot(s.x, s.y), rot(s.x + s.w, s.y), rot(s.x + s.w, s.y + s.h), rot(s.x, s.y + s.h)];
    };
    const groups = {};
    for (const s of this.composeDraft()) {
      const g = s.group ?? s.id;
      (groups[g] = groups[g] || []).push(s);
    }
    return Object.keys(groups).map((gid) => {
      const members = groups[gid];
      // Subtract primitives must be drawn AFTER the fills they carve, whatever
      // order the shapes were added in (Array.sort is stable).
      const ordered = [...members].sort(
        (a, b) => (a.op === "subtract" ? 1 : 0) - (b.op === "subtract" ? 1 : 0),
      );
      // The merged room's link is whichever member carries a room_id (group-mates
      // are kept in sync by assignComposeRoom/mergeComposeShapes).
      const roomMember = members.find((s) => s.room_id != null);
      return {
        id: gid,
        room_id: roomMember ? roomMember.room_id : undefined,
        primitives: ordered.map((s) => {
          const p = s.type === "circle"
            ? { type: "circle", cx: s.cx, cy: s.cy, r: s.r }
            : s.type === "polygon"
              ? { type: "polygon", points: s.points }
              : s.angle
                ? { type: "polygon", points: rectCorners(s) }   // rotated rect -> polygon
                : { type: "rect", x: s.x, y: s.y, w: s.w, h: s.h };
          if (s.op === "subtract") p.op = "subtract";
          return p;
        }),
      };
    });
  };

  // Re-editability: rebuild the draft from saved custom segments as polygon
  // shapes (the backend stores polygons, not the original primitives). Runs
  // once per map (maybeLoadComposeDraft), so it won't clobber an in-progress
  // draft or reload right after a save.
  proto.loadComposeDraftFromSegments = function (data) {
    const draft = [];
    for (const seg of (data?.segments ?? [])) {
      const pts = seg?.polygon_pct;
      if (!Array.isArray(pts) || pts.length < 3) continue;
      draft.push({
        id: String(seg.segment_id ?? `loaded_${draft.length + 1}`),
        type: "polygon",
        points: pts.map((p) => [Number(p[0]), Number(p[1])]),
        room_id: seg.room_id != null ? String(seg.room_id) : undefined,
      });
    }
    this._composeDraft = draft;
    this._composeSelectedId = null;
    this._composeMergeFrom = null;
    this._composeLoadedFor = this._composeKey(data);
    // Advance the id counter past any reloaded draft_N ids so new shapes can't
    // collide with one that came back from a save.
    let maxN = 0;
    for (const s of draft) {
      const m = /(\d+)$/.exec(s.id);
      if (m) maxN = Math.max(maxN, Number(m[1]));
    }
    this._composeNextId = maxN + 1;
  };

  proto._composeKey = function (data) {
    return `${data?.map_id ?? ""}:${data?.active_custom_layout_id ?? ""}`;
  };

  proto.maybeLoadComposeDraft = function (data) {
    if (!data || (data.segmentation_mode ?? "cv") !== "custom") return;
    // Key on map AND active layout — switching layouts reloads that layout's shapes.
    if (this._composeLoadedFor === this._composeKey(data)) return;
    this.loadComposeDraftFromSegments(data);
  };

  // Link the shape to a room (set on the draft; persisted on Save by segment id).
  // Tapping the already-linked room clears it. 1:1 — the chip UI disables rooms
  // already taken by another shape.
  proto.assignComposeRoom = function (id, roomId) {
    const draft = this.composeDraft();
    const s = draft.find((x) => x.id === id);
    if (!s) return;
    const rid = roomId == null ? undefined : String(roomId);
    const next = (s.room_id != null && String(s.room_id) === rid) ? undefined : rid;
    // A room links to a whole merged group, so set it on every group-mate.
    const grp = s.group ?? s.id;
    for (const m of draft) if ((m.group ?? m.id) === grp) m.room_id = next;
  };

  /* =========================================================
     MERGE / CUT
     =========================================================
     Shapes sharing a `group` rasterise into ONE segment (room); a member with
     op:"subtract" carves a hole out of it. Group defaults to a shape's own id,
     so an un-merged shape is its own room. Merge is a two-tap flow (select a
     target, then tap another shape); _composeMergeFrom holds the target while
     the next tap is pending. */
  proto._composeMergeFrom = null;
  proto.composeMergeFrom = function () { return this._composeMergeFrom; };
  proto.startComposeMerge = function (id) { this._composeMergeFrom = id ?? null; };
  proto.cancelComposeMerge = function () { this._composeMergeFrom = null; };

  proto.mergeComposeShapes = function (targetId, memberId) {
    if (!targetId || !memberId || targetId === memberId) return;
    const draft = this.composeDraft();
    const target = draft.find((x) => x.id === targetId);
    const member = draft.find((x) => x.id === memberId);
    if (!target || !member) return;
    const tg = target.group ?? target.id;
    const mg = member.group ?? member.id;
    // Move the member's WHOLE current group into the target's group (so chained
    // merges stay coherent)...
    for (const s of draft) if ((s.group ?? s.id) === mg) s.group = tg;
    // ...then unify the room link across the result (target's wins, else member's).
    const room = target.room_id ?? member.room_id;
    for (const s of draft) if ((s.group ?? s.id) === tg) s.room_id = room;
  };

  proto.splitComposeShape = function (id) {
    const s = this.composeDraft().find((x) => x.id === id);
    if (!s) return;
    s.group = undefined;    // its own segment again
    s.op = undefined;       // a standalone cutout is meaningless
    s.room_id = undefined;  // don't duplicate the group's room link (1:1)
  };

  proto.toggleComposeOp = function (id) {
    const s = this.composeDraft().find((x) => x.id === id);
    if (!s) return;
    s.op = s.op === "subtract" ? undefined : "subtract";
  };

  /* =========================================================
     MOVE SCOPE (room vs piece)
     =========================================================
     When a merged shape is selected, moving can shift the whole room together
     ("room", the default) or just the one piece ("piece"). Shaping (scale /
     resize / rotate) is always per-piece. Standalone shapes ignore the scope. */
  proto._composeMoveScope = "room";
  proto.composeMoveScope = function () { return this._composeMoveScope; };
  proto.setComposeMoveScope = function (scope) {
    this._composeMoveScope = scope === "piece" ? "piece" : "room";
  };

  proto._composeGroupMembers = function (id) {
    const draft = this.composeDraft();
    const s = draft.find((x) => x.id === id);
    if (!s) return [];
    const grp = s.group ?? s.id;
    return draft.filter((x) => (x.group ?? x.id) === grp);
  };

  proto._composeIsMerged = function (id) {
    return this._composeGroupMembers(id).length >= 2;
  };

  // Translate one shape's geometry in place (no clamp — the caller clamps the group).
  proto._translateShape = function (s, ddx, ddy) {
    if (s.type === "circle") { s.cx += ddx; s.cy += ddy; }
    else if (s.type === "polygon") { s.points = s.points.map(([x, y]) => [x + ddx, y + ddy]); }
    else { s.x += ddx; s.y += ddy; }
  };

  // Axis-aligned bbox (pct) over a set of shapes. Rect rotation is ignored here —
  // this only bounds the group-move clamp, which is coarse by design.
  proto._composeShapesBBox = function (shapes) {
    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
    const grow = (x, y) => {
      minX = Math.min(minX, x); maxX = Math.max(maxX, x);
      minY = Math.min(minY, y); maxY = Math.max(maxY, y);
    };
    for (const s of shapes) {
      if (s.type === "circle") { grow(s.cx - s.r, s.cy - s.r); grow(s.cx + s.r, s.cy + s.r); }
      else if (s.type === "polygon") { for (const [x, y] of s.points) grow(x, y); }
      else { grow(s.x, s.y); grow(s.x + s.w, s.y + s.h); }
    }
    return { minX, minY, maxX, maxY };
  };

  proto.moveComposeGroup = function (id, dx, dy) {
    const members = this._composeGroupMembers(id);
    if (!members.length) return;
    const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));
    const bb = this._composeShapesBBox(members);
    // Clamp the delta so no member leaves the canvas.
    const ddx = clamp(dx, -bb.minX, 100 - bb.maxX);
    const ddy = clamp(dy, -bb.minY, 100 - bb.maxY);
    for (const s of members) this._translateShape(s, ddx, ddy);
  };

  proto.placeComposeGroup = function (id, pctX, pctY) {
    const members = this._composeGroupMembers(id);
    if (!members.length) return;
    const bb = this._composeShapesBBox(members);
    this.moveComposeGroup(id, pctX - (bb.minX + bb.maxX) / 2, pctY - (bb.minY + bb.maxY) / 2);
  };

  // Scope-aware dispatchers used by the move pad and tap-to-place.
  proto.moveComposeScoped = function (id, dx, dy) {
    if (this._composeMoveScope === "room" && this._composeIsMerged(id)) this.moveComposeGroup(id, dx, dy);
    else this.moveComposeShape(id, dx, dy);
  };
  proto.placeComposeScoped = function (id, pctX, pctY) {
    if (this._composeMoveScope === "room" && this._composeIsMerged(id)) this.placeComposeGroup(id, pctX, pctY);
    else this.placeComposeShape(id, pctX, pctY);
  };

  // Rotate (deg). Rects carry an angle (applied at render + baked to a polygon on
  // save); polygons rotate their points about the bbox centre; circles no-op.
  proto.rotateComposeShape = function (id, deg) {
    const s = this.composeDraft().find((x) => x.id === id);
    if (!s || s.type === "circle") return;
    if (s.type === "rect") {
      s.angle = ((((s.angle || 0) + deg) % 360) + 360) % 360;
      return;
    }
    const xs = s.points.map((p) => p[0]), ys = s.points.map((p) => p[1]);
    const cx = (Math.min(...xs) + Math.max(...xs)) / 2;
    const cy = (Math.min(...ys) + Math.max(...ys)) / 2;
    const rad = (deg * Math.PI) / 180, cos = Math.cos(rad), sin = Math.sin(rad);
    s.points = s.points.map(([x, y]) => [
      Math.round((cx + (x - cx) * cos - (y - cy) * sin) * 100) / 100,
      Math.round((cy + (x - cx) * sin + (y - cy) * cos) * 100) / 100,
    ]);
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
   * Read legacy localStorage segment-room links if any exist. Returns
   * a plain `{segment_id: room_id}` dict, or null if nothing's stored.
   *
   * The actual migration (push to backend + clear localStorage) lives
   * in the action layer (`getMapSegments` in actions/map.js) — state
   * has no card back-reference for service calls. This helper just
   * surfaces the data; the action drives the round-trip.
   */
  proto.getLegacySegmentRoomLinks = function () {
    try {
      const raw = localStorage.getItem(this._segRoomLegacyKey());
      if (!raw) return null;
      const parsed = JSON.parse(raw);
      if (!parsed || typeof parsed !== "object") return null;
      return parsed;
    } catch (_) {
      return null;
    }
  };

  proto.clearLegacySegmentRoomLinks = function () {
    try { localStorage.removeItem(this._segRoomLegacyKey()); } catch (_) {}
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
   * Optimistic local update. The binding fires the backend service
   * call right after this returns — state has no card back-reference,
   * so the persistence side is orchestrated from the binding layer
   * (where both `card._state` and `card.setSegmentRoomLink` are
   * available).
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
  };

  proto.unassignSegmentRoom = function (segmentId) {
    this._ensureSegmentRoomOverlay().delete(String(segmentId));
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

  /* =========================================================
     PER-VARIANT DELETE CONFIRMATION
     =========================================================
     Backed by the confirmation registry. Keys take the shape
     "map-config.delete-variant.<variant>", so multiple variants
     could in theory be armed, but the shim enforces single-arm
     semantics by clearing siblings before arming a new one.
     The registry handles the 5 s auto-clear (no more
     card._mapVariantDeleteArmTimer bookkeeping on the binding).
     ========================================================= */
  const VARIANT_DELETE_PREFIX = "map-config.delete-variant.";

  proto.armMapVariantDelete = function (variant) {
    const v = variant ? String(variant) : null;
    if (!v) return;
    // Only one variant armed at a time — drop any sibling first.
    this.disarmConfirmationsWithPrefix?.(VARIANT_DELETE_PREFIX);
    // No grace window — original code didn't have one for variant
    // delete; the risk of accidental fire is lower than mid-job
    // cancel because the file is recoverable via re-upload.
    this.armConfirmation?.(`${VARIANT_DELETE_PREFIX}${v}`, { ttl: 5000, grace: 0 });
  };

  proto.clearMapVariantDeleteArm = function () {
    this.disarmConfirmationsWithPrefix?.(VARIANT_DELETE_PREFIX);
  };

  proto.mapVariantDeleteArmed = function () {
    const key = this.firstArmedConfirmationKey?.(VARIANT_DELETE_PREFIX);
    return key ? key.slice(VARIANT_DELETE_PREFIX.length) : null;
  };

  proto.isMapVariantDeleteArmed = function (variant) {
    if (!variant) return false;
    return this.isConfirmationArmed?.(`${VARIANT_DELETE_PREFIX}${String(variant)}`) === true;
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
   * Surface legacy localStorage anchors so the action layer can push
   * them to the backend. Returns `{room_id: {pct_x, pct_y}}` or null.
   * State has no card back-reference, so the migration round-trip is
   * orchestrated by `getMapSegments` in actions/map.js.
   */
  proto.getLegacyDotAnchors = function () {
    try {
      const raw = localStorage.getItem(this._dotAnchorLegacyKey());
      if (!raw) return null;
      const parsed = JSON.parse(raw);
      if (!parsed || typeof parsed !== "object") return null;
      return parsed;
    } catch (_) {
      return null;
    }
  };

  proto.clearLegacyDotAnchors = function () {
    try { localStorage.removeItem(this._dotAnchorLegacyKey()); } catch (_) {}
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

  /**
   * Optimistic local update. Binding fires the backend save right
   * after this returns.
   */
  proto.setRoomDotAnchor = function (roomId, pct_x, pct_y) {
    const idStr = String(roomId);
    this._ensureDotAnchorOverlay().set(idStr, { pct_x, pct_y });
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

  /* =========================================================
     MASCOT ON / OFF  (per vacuum, localStorage)
     =========================================================
     Separate from the animal SELECTION so toggling off then on keeps the chosen
     animal. Default on. */
  proto._mapAnimalEnabled = null; // null = not yet read
  proto._animalEnabledKey = function () {
    return `evcc_animal_on_${vacuumObjectId(this.config?.vacuum ?? "")}`;
  };
  proto.mapAnimalEnabled = function () {
    if (this._mapAnimalEnabled === null) {
      try {
        this._mapAnimalEnabled = localStorage.getItem(this._animalEnabledKey()) !== "0";
      } catch (_) {
        this._mapAnimalEnabled = true;
      }
    }
    return this._mapAnimalEnabled;
  };
  proto.setMapAnimalEnabled = function (on) {
    this._mapAnimalEnabled = !!on;
    try {
      localStorage.setItem(this._animalEnabledKey(), on ? "1" : "0");
    } catch (_) {}
  };
  proto.toggleMapAnimalEnabled = function () {
    this.setMapAnimalEnabled(!this.mapAnimalEnabled());
  };

  /* Mascot FOLLOWS the live robot pixel (rides robot_anchor, replacing the position
     dot) vs. homing to rooms / the dock spot. Default OFF — the existing room/dock
     behavior (and the draggable dock spot) is unchanged unless turned on. When docked
     the mascot still homes to the dock spot in BOTH modes, so dragging survives. */
  proto._mapAnimalFollowsRobot = null; // null = not yet read
  proto._animalFollowsRobotKey = function () {
    return `evcc_animal_follow_${vacuumObjectId(this.config?.vacuum ?? "")}`;
  };
  proto.mapAnimalFollowsRobot = function () {
    if (this._mapAnimalFollowsRobot === null) {
      try {
        this._mapAnimalFollowsRobot = localStorage.getItem(this._animalFollowsRobotKey()) === "1";
      } catch (_) {
        this._mapAnimalFollowsRobot = false;
      }
    }
    return this._mapAnimalFollowsRobot;
  };
  proto.setMapAnimalFollowsRobot = function (on) {
    this._mapAnimalFollowsRobot = !!on;
    try {
      localStorage.setItem(this._animalFollowsRobotKey(), on ? "1" : "0");
    } catch (_) {}
  };
  proto.toggleMapAnimalFollowsRobot = function () {
    this.setMapAnimalFollowsRobot(!this.mapAnimalFollowsRobot());
  };

  /* =========================================================
     ROOM LABELS ON / OFF  (per vacuum, localStorage)
     =========================================================
     VA draws its own room-name labels over the map. A live backdrop (e.g. the
     eufy-clean fork's camera map) already bakes in its OWN room labels, so VA's
     would stack on top into noise — this toggle hides VA's labels. Default on. */
  proto._mapRoomLabelsEnabled = null; // null = not yet read
  proto._roomLabelsEnabledKey = function () {
    return `evcc_map_labels_${vacuumObjectId(this.config?.vacuum ?? "")}`;
  };
  proto.mapRoomLabelsEnabled = function () {
    if (this._mapRoomLabelsEnabled === null) {
      try {
        this._mapRoomLabelsEnabled = localStorage.getItem(this._roomLabelsEnabledKey()) !== "0";
      } catch (_) {
        this._mapRoomLabelsEnabled = true;
      }
    }
    return this._mapRoomLabelsEnabled;
  };
  proto.setMapRoomLabelsEnabled = function (on) {
    this._mapRoomLabelsEnabled = !!on;
    try {
      localStorage.setItem(this._roomLabelsEnabledKey(), on ? "1" : "0");
    } catch (_) {}
  };
  proto.toggleMapRoomLabelsEnabled = function () {
    this.setMapRoomLabelsEnabled(!this.mapRoomLabelsEnabled());
  };

  /* =========================================================
     FLOOR TEXTURES ON / OFF  (per vacuum, localStorage)
     =========================================================
     Two INDEPENDENT toggles — the map polygons and the room-card layers are
     controlled separately. Each first read seeds from the legacy unified key
     (evcc_floor_tex_<vac>) so an existing on/off preference carries over to
     both. Default on. */
  proto._mapFloorTextureEnabled  = null; // null = not yet read
  proto._roomFloorTextureEnabled = null;
  proto._floorTexKey = function (which) {
    return `evcc_floor_tex_${which}_${vacuumObjectId(this.config?.vacuum ?? "")}`;
  };
  proto._readFloorTex = function (which) {
    try {
      const v = localStorage.getItem(this._floorTexKey(which));
      if (v !== null) return v !== "0";
      // Migrate from the legacy unified key (absent => default on).
      const legacy = localStorage.getItem(`evcc_floor_tex_${vacuumObjectId(this.config?.vacuum ?? "")}`);
      return legacy !== "0";
    } catch (_) {
      return true;
    }
  };
  proto._writeFloorTex = function (which, on) {
    try { localStorage.setItem(this._floorTexKey(which), on ? "1" : "0"); } catch (_) {}
  };

  proto.mapFloorTextureEnabled = function () {
    if (this._mapFloorTextureEnabled === null) this._mapFloorTextureEnabled = this._readFloorTex("map");
    return this._mapFloorTextureEnabled;
  };
  proto.setMapFloorTextureEnabled = function (on) {
    this._mapFloorTextureEnabled = !!on;
    this._writeFloorTex("map", !!on);
  };
  proto.toggleMapFloorTextureEnabled = function () {
    this.setMapFloorTextureEnabled(!this.mapFloorTextureEnabled());
  };

  proto.roomFloorTextureEnabled = function () {
    if (this._roomFloorTextureEnabled === null) this._roomFloorTextureEnabled = this._readFloorTex("rooms");
    return this._roomFloorTextureEnabled;
  };
  proto.setRoomFloorTextureEnabled = function (on) {
    this._roomFloorTextureEnabled = !!on;
    this._writeFloorTex("rooms", !!on);
  };
  proto.toggleRoomFloorTextureEnabled = function () {
    this.setRoomFloorTextureEnabled(!this.roomFloorTextureEnabled());
  };
}
