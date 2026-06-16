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

  // ---- Live-map rotation (display only) ----
  // The live map image (Roborock) can be oriented differently from how the user
  // pictures their home; let them rotate it in 90° steps to match. Display only —
  // it never touches dispatch (cleaning is by room id). Persisted per vacuum in
  // localStorage (per browser; matches the other map view prefs). Applied only to
  // the live-image element (which fills a SQUARE container, so a 90° turn around
  // its centre stays perfectly in frame) — NOT to CV/custom maps, whose polygon
  // overlay would otherwise drift from the picture.
  proto._mapRotation = null; // null = not yet read from localStorage
  proto._mapRotationStorageKey = function () {
    return `evcc_map_rotation_${vacuumObjectId(this.config?.vacuum ?? "")}`;
  };
  proto.mapRotation = function () {
    if (this._mapRotation === null) {
      const stored = parseInt(localStorage.getItem(this._mapRotationStorageKey()) ?? "0", 10);
      this._mapRotation = [0, 90, 180, 270].includes(stored) ? stored : 0;
    }
    return this._mapRotation;
  };
  proto.setMapRotation = function (deg) {
    const norm = (((Math.round(Number(deg) / 90) * 90) % 360) + 360) % 360;
    this._mapRotation = norm;
    try {
      localStorage.setItem(this._mapRotationStorageKey(), String(norm));
    } catch (_) {}
  };
  proto.rotateMapCW = function () {
    this.setMapRotation(this.mapRotation() + 90);
  };

  proto.mapSegmentsData = function () {
    return this._mapSegmentsData;
  };

  proto.setMapSegmentsData = function (data) {
    const oldMapId = this._mapSegmentsData?.map_id;
    const oldKey = `${oldMapId ?? ""}:${this._mapSegmentsData?.active_custom_layout_id ?? ""}`;
    const newKey = `${data?.map_id ?? ""}:${data?.active_custom_layout_id ?? ""}`;
    this._mapSegmentsData = data;
    if (oldKey !== newKey) {
      // Reset overlays + draft when the active map OR layout changes — what was
      // true for the old map/layout's segments has nothing to do with the new.
      this._segmentRoomOverlay = null;
      this._dotAnchorOverlay = null;
      this._mapAnchorMode = false;
      this._composeDraft = null;       // new map/layout → fresh draft, reload from its segments
      this._composeSelectedId = null;
      this._composeMergeFrom = null;
      this._composeLoadedFor = null;
      if (data?.map_id !== oldMapId) this.resetMapTransform();
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
      const v = this.activeCustomLayout()?.backdrop_variant || "custom";
      const own = variants[v];
      if (own) return own.browser_url ?? null;
      if (v !== "custom") return null;
      return (variants.dark ?? variants.default ?? variants.light)?.browser_url ?? null;
    }
    // No CV/custom backdrop (e.g. a Roborock with native segments and no uploaded
    // map): fall back to the brand's LIVE map image entity if one is declared.
    return (variants.dark ?? variants.default ?? variants.light)?.browser_url
      ?? this._liveMapImageUrl();
  };

  /**
   * The LIVE map backdrop URL: the brand's HA `image` entity's entity_picture
   * (Roborock current map). That URL carries a token that rotates on each image
   * update, so binding it to <img src> refreshes the picture live with no polling.
   * Null when the adapter declares no live image entity (Eufy) or the entity has
   * no picture yet.
   */
  proto._liveMapImageUrl = function () {
    const eid = this.liveMapImageEntity?.();
    if (!eid) return null;
    return this.attrsOf(eid)?.entity_picture ?? null;
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
