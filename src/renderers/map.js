/**
 * ============================================================
 * RENDERERS: MAP
 * ============================================================
 *
 * Renders the map view — SVG room polygon segments, pan/zoom
 * overlay, animal companion, selection bar, and map config panel.
 *
 * ============================================================
 */

import { roomFillCss, normalizeHex } from "../cards/map-room-color.js";

/* =========================================================
   VACUUM STATE → ANIMAL POSE
   =========================================================
   Maps HA vacuum-platform standard state strings to animal-svg
   poses. The mapping is brand-agnostic — every HA vacuum
   integration reports the same canonical state set
   (cleaning / returning / paused / error / docked / idle).
   ========================================================= */

function _vacuumStateToPose(vacuumStatus) {
  switch (vacuumStatus) {
    case "cleaning":  return "alert";
    case "returning": return "walking";
    case "paused":    return "standing";
    case "error":     return "warning";
    case "docked":
    case "idle":      return "curled";
    default:          return "curled";
  }
}

export function _polygonCentroid(points) {
  let area = 0, cx = 0, cy = 0;
  const n = points.length;
  for (let i = 0, j = n - 1; i < n; j = i++) {
    const cross = points[j][0] * points[i][1] - points[i][0] * points[j][1];
    area += cross;
    cx   += (points[j][0] + points[i][0]) * cross;
    cy   += (points[j][1] + points[i][1]) * cross;
  }
  area *= 0.5;
  if (Math.abs(area) < 1e-10) {
    // degenerate — fall back to vertex average
    const sx = points.reduce((s, p) => s + p[0], 0);
    const sy = points.reduce((s, p) => s + p[1], 0);
    return [sx / n, sy / n];
  }
  return [cx / (6 * area), cy / (6 * area)];
}

// The axis-aligned bbox [x0,y0,x1,y1] of a saved zone's normalized geometry, or null when
// the geometry is missing / degenerate. The clean dispatches this bbox, so it's what the map
// draws + highlights (matches what actually gets cleaned).
export function _savedZoneBbox(zone) {
  const g = zone?.geometry;
  if (!Array.isArray(g) || g.length < 3) return null;
  const xs = [], ys = [];
  for (const p of g) {
    if (!Array.isArray(p) || p.length !== 2) continue;
    const x = Number(p[0]), y = Number(p[1]);
    if (!Number.isFinite(x) || !Number.isFinite(y)) continue;
    xs.push(x); ys.push(y);
  }
  if (xs.length < 3) return null;
  return [Math.min(...xs), Math.min(...ys), Math.max(...xs), Math.max(...ys)];
}

// Room-fill colors now resolve through the shared themeable palette (roomFillCss) — the
// hardcoded _SEGMENT_COLORS array moved to cards/map-room-color.js as ROOM_FILL_PALETTE.

// Stable variant keys only — the human label + ranking hint are localized at
// the render site (`map.variant_<key>_label` / `_hint`), so no English lives here.
const _VARIANTS = [
  { key: "dark" },
  { key: "light" },
  { key: "default" },
];

/**
 * Mix map renderer methods onto the given prototype.
 *
 * @param {object} proto - VacuumCardRenderers prototype to extend.
 */
export function applyMapRenderers(proto) {

  /* =========================================================
     MAP ROOM VIEW
     ========================================================= */

  proto.renderMapRoomView = function (ctx) {
    const { state, vacuumStatus } = ctx;

    const segmentsData = state.mapSegmentsData();
    const imageUrl = state.mapImageUrl();
    const hasLiveImage = Boolean(state.liveMapImageEntity?.());
    // VA-rendered backdrop (Wave 1): the card draws its OWN full-grid canvas from the
    // device raster (the binding fetches via get_map_render_data + draws). When on, we
    // proceed even without a camera URL — the canvas is the backdrop.
    const wantVa = Boolean(state.useVaRender?.() && state.supportsVaRender?.());
    const vaActive = state.isVaRenderActive?.() ?? false;

    // Empty state ONLY when there's genuinely no usable backdrop: not the VA render
    // (gate on vaActive, not the mere intent wantVa), no live/CV image, no custom
    // segments. A live-image brand (Roborock) renders the picture alone once its URL is
    // ready; the segment/label SVG below is a safe no-op on an empty segment list.
    if (!vaActive && (!imageUrl || (!segmentsData?.available && !hasLiveImage))) {
      const isCustom = (state.segmentationMode?.() ?? "cv") === "custom";
      // VA render selected but its raster hasn't loaded yet -> "rendering", not "no map".
      const title = wantVa ? this.t("map.empty_rendering_title") : this.t("map.empty_no_image_title");
      const hint = wantVa
        ? this.t("map.empty_rendering_hint")
        : hasLiveImage
          ? this.t("map.empty_live_hint")
          : isCustom
            ? this.t("map.empty_custom_hint")
            : this.t("map.empty_upload_hint");
      return `
        <div class="evcc-map-view">
          <div class="evcc-map-unavailable">
            <p>${title}</p>
            <p class="evcc-map-unavailable-hint">${hint}</p>
          </div>
        </div>
      `;
    }

    const segments = state.mapSegments();
    const selectedIds = state.selectedSegmentIds();
    const selectedSegments = state.selectedSegments();

    const rooms = state.getRoomsForActiveMap?.() ?? [];

    const segFloorTypes = segments.map((seg) => {
      const roomId = state.roomIdForSegment(seg.segment_id);
      const room   = roomId != null ? rooms.find((r) => String(r.id) === String(roomId)) : null;
      return typeof this._resolveSegmentFloorType === "function"
        ? this._resolveSegmentFloorType(room)
        : "default";
    });

    const zoom         = state.mapZoom?.() ?? 1;
    const tx           = state.mapTranslateX?.() ?? 0;
    const ty           = state.mapTranslateY?.() ?? 0;
    // Display-only rotation of the whole content block (backdrop + co-rotated overlays). Applied
    // to the contain backdrops (VA self-render canvas + live image), not uploaded CV/custom
    // (--fill). Single source so the mascot/area-label drags convert in the same frame.
    const rot          = state.effectiveMapRotation?.() ?? 0;
    // Ad-hoc zone clean: only over a live-map backdrop (you draw on that image),
    // only when the provider supports it. Rotation IS handled — the drawn rect is
    // un-rotated to the content frame at dispatch (state.zoneDraftsToNormalizedRects).
    const canZone   = state.canDrawZone?.() ?? false;
    // zoneMode is gated by canZone so the overlay, action bar, and container
    // class can never be live while the gate is false (e.g. after a rotate).
    const zoneMode   = canZone && (state.zoneDrawMode?.() ?? false);
    const zoneDrafts = zoneMode ? (state.zoneDrafts?.() ?? []) : [];
    const zoneCount  = zoneDrafts.length;
    const zoneMax    = state.zoneMax?.() ?? 10;
    // Hide-area draw: same gate spirit as zones (overlay-aligned backdrop + rotation 0).
    const hideMode   = (state.canDrawHideArea?.() ?? false) && (state.hideDrawMode?.() ?? false);
    // map_state_source overlay layers (no-go/walls/path/robot/etc.) render over any
    // GRID-frame backdrop their normalized coords align to: the live device image OR
    // the VA-rendered canvas (Wave 3c overlays; Wave 1 self-render).
    const deviceOverlays = state.overlaysAligned?.() ?? false;
    // Furnished render (Wave 1): the whole-home art layer + the base-fade mode. The art
    // is only live on the "Live map" custom layout; the base live <img> stays MOUNTED
    // always (opacity-faded, never unmounted — it anchors the overlay frame + keeps the
    // camera poll alive). render_mode: live → base full / art hidden; art → base ~0 / art
    // full; blend → base ~0.45 / art full (alignment view). See styles/map.js.
    const furnishedOn = state.isFurnishedLayoutActive?.() ?? false;
    const furnishedMode = furnishedOn ? (state.furnishedRenderMode?.() ?? "live") : "live";
    const baseFadeCls = furnishedOn && furnishedMode !== "live"
      ? ` evcc-map-image--furnished-${furnishedMode}` : "";
    return `
      <div class="evcc-map-view">
        <div class="evcc-map-container${zoneMode ? " evcc-map-container--zone" : ""}${hideMode ? " evcc-map-container--hide" : ""}">

          <div class="evcc-map-layers" style="transform:translate(${tx}px,${ty}px) scale(${zoom});transform-origin:0 0">
            <!-- Rotation turns this whole content layer (image + polygons + labels
                 + mascot) together so overlays stay aligned at any 90° step; zoom/pan
                 stays on .evcc-map-layers above. --evcc-map-rotation lets labels +
                 mascot counter-rotate upright (see styles/map.js). -->
            <div class="evcc-map-content-rotator" style="transform:rotate(${rot}deg);--evcc-map-rotation:${rot}deg">
            ${vaActive
              ? `<canvas class="evcc-map-image evcc-map-render-canvas" data-render-version="${this.escapeHtml(String(state.mapRenderVersion?.() ?? ""))}"></canvas>`
              : (imageUrl
                  ? `<img class="evcc-map-image${baseFadeCls}" src="${this.escapeHtml(imageUrl)}" alt="${this.t("map.floor_plan_alt")}" draggable="false">`
                  : "")}
            ${(furnishedOn && furnishedMode !== "live") ? this._renderFurnishedArt(state, false) : ""}
            ${this._renderSelectionScrim(state)}
            <svg
              class="evcc-map-svg"
              viewBox="0 0 100 100"
              preserveAspectRatio="none"
            >
              ${typeof this._buildFloorTextureDefs === "function"
                ? this._buildFloorTextureDefs(segFloorTypes)
                : ""}
              ${segments.map((seg, i) => {
                const roomId = state.roomIdForSegment(seg.segment_id);
                const room   = roomId != null ? rooms.find((r) => String(r.id) === String(roomId)) : null;
                const label  = room?.name ?? seg.name ?? seg.label ?? this.t("map.segment_fallback", { id: seg.segment_id });
                const hint   = room ? this.t("map.segment_hint_configurable") : this.t("map.segment_hint_queue");
                return this._renderMapSegmentPolygon(seg, selectedIds, i, label, hint, room?.color);
              }).join("")}
              ${typeof this._renderFloorTexturePolygon === "function"
                ? segments.map((seg, i) => {
                    // A per-room color OVERRIDE is the room's chosen fill, so it wins over the floor
                    // texture — skip the texture polygon, which otherwise covers the recolored raster
                    // and lets the override peek only at the edge. Net-zero for un-overridden rooms.
                    const rid = state.roomIdForSegment(seg.segment_id);
                    const room = rid != null ? rooms.find((r) => String(r.id) === String(rid)) : null;
                    if (room && normalizeHex(room.color)) return "";
                    return this._renderFloorTexturePolygon(seg, segFloorTypes[i]);
                  }).join("")
                : ""}
              ${deviceOverlays ? this._renderDeviceOverlaySvg(state) : ""}
            </svg>
            ${this._renderMapAnimal(state, vacuumStatus)}
            ${(state.mapRoomLabelsEnabled?.() ?? true) ? segments.map((seg) => {
              const polygon = seg.polygon_pct;
              if (!Array.isArray(polygon) || polygon.length < 3) return "";
              const [cx, cy] = _polygonCentroid(polygon);
              const lx = Math.min(Math.max(cx, 5), 95);
              const ly = Math.min(Math.max(cy, 6), 94);
              const roomId = state.roomIdForSegment(seg.segment_id);
              const room   = roomId != null ? rooms.find((r) => String(r.id) === String(roomId)) : null;
              const label  = room?.name ?? seg.name ?? seg.label ?? null;
              if (!label) return "";
              const selOrder = selectedSegments.findIndex((s) => String(s.segment_id) === String(seg.segment_id));
              const isSel    = selOrder >= 0;
              // Draggable name: a saved per-device anchor (localStorage, % of the content box)
              // overrides the centroid; data-room is the anchor key, data-segment lets a TAP
              // (no drag) still select the room (see bindings _bindRoomNameDrag).
              const anchorKey = roomId != null ? String(roomId) : `seg:${seg.segment_id}`;
              const na = state.roomNameAnchor?.(anchorKey);
              const px = na ? Math.min(Math.max(na.x, 0), 100) : lx;
              const py = na ? Math.min(Math.max(na.y, 0), 100) : ly;
              return `<div class="evcc-map-label evcc-map-label--draggable${isSel ? " evcc-map-label--selected" : ""}" data-action="room-name-drag" data-room="${this.escapeHtml(anchorKey)}" data-segment="${this.escapeHtml(String(seg.segment_id))}" data-cx="${lx}" data-cy="${ly}" style="left:${px}%;top:${py}%">
                ${isSel ? `<span class="evcc-map-label-order">${selOrder + 1}</span>` : ""}
                <span class="evcc-map-label-name">${this.escapeHtml(label)}</span>
              </div>`;
            }).join("") : ""}
            ${(segments.length === 0 && (state.mapRoomLabelsEnabled?.() ?? true)) ? this._renderDeviceRoomLabels(state) : ""}
            ${deviceOverlays ? this._renderDeviceOverlayHtml(state) : ""}
            ${this._renderRoomSelection(state)}
            ${this._renderHiddenRegions(state, hideMode)}
            </div>
            ${zoneMode ? `
              ${zoneDrafts.map((d, i) => `<div class="evcc-zone-rect" style="left:${Math.min(d.x, d.x + d.w)}%;top:${Math.min(d.y, d.y + d.h)}%;width:${Math.abs(d.w)}%;height:${Math.abs(d.h)}%"><span class="evcc-zone-rect-num">${i + 1}</span></div>`).join("")}
              <div class="evcc-zone-draft" style="display:none"></div>` : ""}
            ${hideMode ? `<div class="evcc-hide-draft" style="display:none"></div>` : ""}

          </div>

          <div class="evcc-map-tooltip" aria-hidden="true"></div>

          <!-- Zoom controls. Absolute-positioned over the map. CSS-styled
               as a small floating toolbar; see styles/map.js -->
          <div class="evcc-map-zoom-toolbar" aria-label="${this.t("map.zoom_controls_aria")}">
            <button class="evcc-map-zoom-btn" data-action="map-zoom-out"
                    title="${this.t("map.zoom_out")}" aria-label="${this.t("map.zoom_out")}">−</button>
            <button class="evcc-map-zoom-btn" data-action="map-zoom-fit"
                    title="${this.t("map.zoom_fit")}" aria-label="${this.t("map.zoom_fit_aria")}">⤢</button>
            <button class="evcc-map-zoom-btn" data-action="map-zoom-in"
                    title="${this.t("map.zoom_in")}" aria-label="${this.t("map.zoom_in")}">+</button>
            ${(hasLiveImage || vaActive) ? `
            <button class="evcc-map-zoom-btn" data-action="map-rotate"
                    title="${this.t("map.rotate")}" aria-label="${this.t("map.rotate_aria")}">↻</button>` : ""}
            ${((state.supportsVaRender?.() ?? false) && !(state.embeddedInCard?.() ?? false)) ? `
            <button class="evcc-map-zoom-btn${(state.useVaRender?.() ?? false) ? " evcc-map-zoom-btn--on" : ""}"
                    data-action="toggle-va-render"
                    title="${this.t("map.toggle_va_render")}" aria-label="${this.t("map.toggle_va_render")}">▦</button>` : ""}
            ${(vaActive && !(state.embeddedInCard?.() ?? false)) ? `
            <button class="evcc-map-zoom-btn${(state.useFloorTexture?.() ?? false) ? " evcc-map-zoom-btn--on" : ""}"
                    data-action="toggle-floor-texture"
                    title="${this.t("map.toggle_floor_texture")}" aria-label="${this.t("map.toggle_floor_texture")}">▨</button>` : ""}
            ${canZone ? `
            <button class="evcc-map-zoom-btn${zoneMode ? " evcc-map-zoom-btn--on" : ""}"
                    data-action="toggle-zone-draw"
                    title="${this.t("map.draw_zone")}" aria-label="${this.t("map.draw_zone")}">▢</button>` : ""}
            ${this._renderMapSwitch(state)}
            <span class="evcc-map-zoom-readout"
                  aria-label="${this.t("map.zoom_level_aria")}">${Math.round(zoom * 100)}%</span>
          </div>

        </div>

      </div>
    `;
  };

  /**
   * Map switcher — the fork's per-vacuum "Switch Map" select, backend-fed via
   * snapshot.map_switcher. A native <select> in the map toolbar; shown ONLY when that
   * select entity exists, is available, and offers >1 map (older eufy-clean builds omit
   * it → nothing renders). Picking fires select.select_option (see bindings/map.js).
   */
  proto._renderMapSwitch = function (state) {
    const ms = state.mapSwitcher?.();
    const options = Array.isArray(ms?.options) ? ms.options : [];
    if (!ms || !ms.available || options.length < 2) return "";
    return `
      <select class="evcc-map-switch-select" data-action="map-switch-select"
              title="${this.t("map.switch_map")}" aria-label="${this.t("map.switch_map")}">
        ${options
          .map(
            (o) =>
              `<option value="${this.escapeHtml(o)}"${o === ms.current ? " selected" : ""}>${this.escapeHtml(o)}</option>`,
          )
          .join("")}
      </select>`;
  };

  /* =========================================================
     MAP_STATE_SOURCE DEVICE OVERLAYS (Wave 3c)
     =========================================================
     The VA's read of the device's own map, normalized 0–1 of the LIVE rendered
     image -> ×100 into the same 0–100 SVG / pct space the room polygons use, inside
     the rotator so they turn with the map. SVG layers (polygons/lines/rects) here;
     HTML markers + area labels in _renderDeviceOverlayHtml. Each layer is gated by
     its own visibility toggle (state.isOverlayVisible). Every array is guarded.
     ========================================================= */

  /**
   * Letterbox transform: the backend normalizes overlay coords to the 0–1 IMAGE
   * frame, but the live <img> is object-fit:contain inside a SQUARE box, so a
   * non-square image gets centered bars. This maps image-normalized (0–1) to
   * container space (0–100, the SVG viewBox + HTML %) the SAME way the zone-clean
   * path does (state._rectToNormalized, inverted). Identity when the size is unknown
   * (assumes square). Returns {tx, ty, sx, sy} in container-% units.
   */
  proto._overlayTransform = function (state) {
    const size = state.mapImageSize?.();
    let sx = 100, sy = 100, offX = 0, offY = 0;
    if (Array.isArray(size) && size.length === 2 && size[0] > 0 && size[1] > 0) {
      const W = Number(size[0]), H = Number(size[1]);
      sx = W >= H ? 100 : (100 * W) / H;
      sy = H >= W ? 100 : (100 * H) / W;
      offX = (100 - sx) / 2;
      offY = (100 - sy) / 2;
    }
    return {
      sx, sy,
      tx: (v) => offX + Number(v) * sx,
      ty: (v) => offY + Number(v) * sy,
    };
  };

  /* =========================================================
     FURNISHED ART LAYER (Wave 1 — whole-home art over the live map)
     =========================================================
     The user's to-scale home render, placed as ONE rotated rect over the faded live
     base, UNDER the overlay SVG/markers (so the robot/dock/path ride on top). Rendered
     as an <img class="evcc-map-art"> — a DISTINCT class from .evcc-map-image (D3), so the
     zone-confirm naturalWidth selector + selection scrim + hit-test never grab it.

     The element is absolute/inset:0/object-fit:contain (the SAME letterbox the overlays
     assume), so an UNTRANSFORMED art exactly fills the overlay frame. The placement
     transform {tx,ty,scale,rotation} is applied to the art element ONLY (the overlays
     keep riding the live frame via _overlayTransform, untouched). tx/ty are a pct offset
     in the content frame; scale multiplies the contain size; rotation is degrees. Stored
     in the natural (pre-live_map_rotation) frame — the rotator applies live_map_rotation
     last, so the art co-rotates with the overlays (D2).

     `editable` (config view only) adds the drag-handle data-action; the room view layer is
     display-only + click-through. */
  proto._renderFurnishedArt = function (state, editable) {
    const url = state.furnishedHomeArtUrl?.();
    if (!url) return "";
    // In the editor use the live draft (seeded from the saved transform); in the room view
    // use the saved transform straight.
    const t = editable
      ? (state.furnishedArtTransform?.() ?? { tx: 0, ty: 0, scale: 1, rotation: 0 })
      : (state.furnishedHomeArtTransform?.() ?? null);
    const tx  = Number(t?.tx ?? 0);
    const ty  = Number(t?.ty ?? 0);
    const sc  = Number(t?.scale ?? 1) || 1;
    const rot = Number(t?.rotation ?? 0);
    // translate is in the element's own % (matches the pct-offset contract); rotate then
    // scale about the centre. transform-origin 50% 50% (set in CSS) keeps it centred.
    const xform = `translate(${tx.toFixed(3)}%, ${ty.toFixed(3)}%) rotate(${rot}deg) scale(${sc})`;
    // When a compose shape is selected for placement, the full-frame art must be
    // click-through so the empty-space tap reaches the compose layer underneath — otherwise
    // the art swallows every tap and segment placement is silently dead. The user deselects
    // the shape to drag the art again. (Room-view art is already pointer-events:none.)
    const composeActive = editable && (state.composeSelectedId?.() != null);
    const cls = "evcc-map-art"
      + (editable ? " evcc-map-art--editable" : "")
      + (composeActive ? " evcc-map-art--passthrough" : "");
    const drag = (editable && !composeActive) ? ` data-action="furnished-art-drag"` : "";
    return `<img class="${cls}" src="${this.escapeHtml(url)}" alt="${this.t("map.furnished_art_alt")}" `
         + `draggable="false" style="transform:${xform}"${drag}>`;
  };

  proto._renderDeviceOverlaySvg = function (state) {
    const mss = state.mapOverlayData?.() ?? state.mapStateSource?.();
    if (!mss || !mss.present) return "";
    const vis = (layer) => state.isOverlayVisible?.(layer) ?? false;
    const { tx, ty, sx, sy } = this._overlayTransform(state);
    const f = (v) => v.toFixed(2);
    const pts = (poly) => poly.map((p) => `${f(tx(p[0]))},${f(ty(p[1]))}`).join(" ");
    const rect = (cls, x0, y0, x1, y1) => {
      const ax = tx(Math.min(x0, x1)), ay = ty(Math.min(y0, y1));
      return `<rect class="${cls}" x="${f(ax)}" y="${f(ay)}" `
           + `width="${f(Math.abs(x1 - x0) * sx)}" height="${f(Math.abs(y1 - y0) * sy)}" />`;
    };
    let out = "";

    if (vis("current_room") && mss.current_room != null) {
      const r = (mss.rooms || []).find((rm) => rm.number === mss.current_room);
      if (r && Array.isArray(r.bbox) && r.bbox.length === 4) {
        out += rect("evcc-map-ov-current", r.bbox[0], r.bbox[1], r.bbox[2], r.bbox[3]);
      }
    }
    if (vis("no_go")) {
      for (const poly of (mss.no_go || [])) {
        if (Array.isArray(poly) && poly.length >= 3) out += `<polygon class="evcc-map-ov-nogo" points="${pts(poly)}" />`;
      }
    }
    if (vis("no_mop")) {
      for (const poly of (mss.no_mop || [])) {
        if (Array.isArray(poly) && poly.length >= 3) out += `<polygon class="evcc-map-ov-nomop" points="${pts(poly)}" />`;
      }
    }
    if (vis("zones")) {
      for (const z of (mss.zones || [])) {
        if (Array.isArray(z) && z.length === 4) out += rect("evcc-map-ov-zone", z[0], z[1], z[2], z[3]);
      }
    }
    if (vis("walls")) {
      for (const w of (mss.walls || [])) {
        if (Array.isArray(w) && w.length === 2 && Array.isArray(w[0]) && Array.isArray(w[1])) {
          out += `<line class="evcc-map-ov-wall" x1="${f(tx(w[0][0]))}" y1="${f(ty(w[0][1]))}" `
               + `x2="${f(tx(w[1][0]))}" y2="${f(ty(w[1][1]))}" />`;
        }
      }
    }
    if (vis("path") && Array.isArray(mss.path) && mss.path.length >= 2) {
      out += `<polyline class="evcc-map-ov-path" points="${pts(mss.path)}" />`;
    }
    // Saved zones: draw ONLY the SELECTED set — the map is "here's what I'm about to clean".
    // Driven purely by the panel selection (NOT a Map Layers toggle), each as its bbox rect
    // (what a clean actually dispatches). Read straight from card state.
    for (const z of (state.savedZones?.() ?? [])) {
      if (!(state.isSavedZoneSelected?.(z.id) ?? false)) continue;
      const box = _savedZoneBbox(z);
      if (!box) continue;
      out += rect("evcc-map-ov-savedzone evcc-map-ov-savedzone--selected", box[0], box[1], box[2], box[3]);
    }
    return out;
  };

  proto._renderDeviceOverlayHtml = function (state) {
    const mss = state.mapOverlayData?.() ?? state.mapStateSource?.();
    if (!mss || !mss.present) return "";
    const vis = (layer) => state.isOverlayVisible?.(layer) ?? false;
    const { tx, ty } = this._overlayTransform(state);
    const f = (v) => v.toFixed(2);
    let out = "";

    // The mascot REPLACES the dot when "follow robot" is on (and the companion is shown).
    const _followActive = (state.mapAnimalFollowsRobot?.() ?? false) && (state.mapAnimalEnabled?.() ?? true);
    if (vis("robot") && !_followActive && Array.isArray(mss.robot_anchor) && mss.robot_anchor.length === 2) {
      const [x, y] = mss.robot_anchor;
      const h = Number(mss.robot_heading ?? 0);
      out += `<div class="evcc-map-ov-robot" style="left:${f(tx(x))}%;top:${f(ty(y))}%">`
           + `<span class="evcc-map-ov-robot-arrow" style="transform:rotate(${h}deg)"></span></div>`;
    }
    if (vis("dock") && Array.isArray(mss.dock_anchor) && mss.dock_anchor.length === 2) {
      const [x, y] = mss.dock_anchor;
      out += `<div class="evcc-map-ov-dock" style="left:${f(tx(x))}%;top:${f(ty(y))}%" title="${this.t("map.dock")}"></div>`;
    }
    if (vis("obstacles")) {
      for (const o of (mss.obstacles || [])) {
        if (!o || !Array.isArray(o.pos) || o.pos.length !== 2) continue;
        const cls = o.has_photo ? " evcc-map-ov-obstacle--photo" : "";
        out += `<div class="evcc-map-ov-obstacle${cls}" style="left:${f(tx(o.pos[0]))}%;top:${f(ty(o.pos[1]))}%" `
             + `title="${o.type != null ? this.escapeHtml(String(o.type)) : this.t("map.obstacle")}"></div>`;
      }
    }
    if (vis("room_area")) {
      for (const r of (mss.rooms || [])) {
        if (r.area_m2 == null || !Array.isArray(r.bbox) || r.bbox.length !== 4) continue;
        const [x0, y0, x1, y1] = r.bbox;
        // Draggable: a saved anchor (map-content-box %) wins over the default room centre, so
        // the user can pull the m² chip off the room-name label. Same % frame as tx/ty output.
        const anchor = state.areaLabelAnchor?.(r.number);
        const lx = anchor ? Number(anchor.pct_x) : tx((x0 + x1) / 2);
        const ly = anchor ? Number(anchor.pct_y) : ty((y0 + y1) / 2);
        out += `<div class="evcc-map-ov-area" data-action="area-label-drag" `
             + `data-room="${this.escapeHtml(String(r.number))}" `
             + `style="left:${f(lx)}%;top:${f(ly)}%">`
             + `${this.escapeHtml(String(r.area_m2))} m²</div>`;
      }
    }
    // Saved-zone name (+ m²) labels — only for the SELECTED set (mirrors the boxes above),
    // at each zone's bbox centre via the same overlay transform, so they ride the rotator upright.
    for (const z of (state.savedZones?.() ?? [])) {
      if (!(state.isSavedZoneSelected?.(z.id) ?? false)) continue;
      const box = _savedZoneBbox(z);
      if (!box) continue;
      const cx = (box[0] + box[2]) / 2;
      const cy = (box[1] + box[3]) / 2;
      const area = z.area_m2 != null
        ? ` · ${this.t("saved_zones.area_m2", { area: this.escapeHtml((Number(z.area_m2) || 0).toFixed(1)) })}`
        : "";
      out += `<div class="evcc-map-ov-savedzone-label evcc-map-ov-savedzone-label--selected" `
           + `style="left:${f(tx(cx))}%;top:${f(ty(cy))}%">${this.escapeHtml(z.name)}${area}</div>`;
    }
    return out;
  };

  /* Room-NAME labels for the live map's OWN rooms (map_state_source) — the fallback when the
     layout has no drawn segments (a bare Roborock/Eufy live map). Names come from the device's
     rooms (e.g. "Room 18", or a reconciled name); positioned at each room's bbox centre via the
     same overlay transform the m² chips use, so they sit with those chips and ride the rotator
     upright (reusing .evcc-map-label). Gated by the room-labels toggle + only when there are no
     segments (else the segment labels own the names). */
  proto._renderDeviceRoomLabels = function (state) {
    const mss = state.mapOverlayData?.() ?? state.mapStateSource?.();
    if (!mss || !mss.present || !Array.isArray(mss.rooms)) return "";
    const { tx, ty } = this._overlayTransform(state);
    const managed = state.getRoomsForActiveMap?.() ?? [];
    const order = this._selectedRoomOrder(state);   // Map(device number -> 1-based clean order)
    return mss.rooms.map((r) => {
      if (!Array.isArray(r.bbox) || r.bbox.length !== 4) return "";
      // Prefer the user's CONFIGURED room name (the managed room keyed by the device
      // number == managed room id — the mapping tap-to-select uses), falling back to the
      // device's own name ("Room N") for a device room the user hasn't named yet.
      const mr = managed.find((m) => String(m.id) === String(r.number));
      const name = mr?.name ?? r?.name;
      if (!name) return "";
      // Selected rooms light up via --selected (the raster scrim that dims rooms can't run
      // without a raster). The clean order is shown by the separate number markers, so no
      // order chip on the label to avoid doubling it.
      const isSel = order.has(Number(r.number));
      const lx = Math.min(Math.max(+tx((r.bbox[0] + r.bbox[2]) / 2), 5), 95);
      const ly = Math.min(Math.max(+ty((r.bbox[1] + r.bbox[3]) / 2), 6), 94);
      // Draggable name — same as the polygon path: a saved per-device anchor (localStorage,
      // % of the content box — the SAME space as lx/ly) overrides the bbox centroid.
      // data-room is the anchor key (the device room NUMBER == managed room id); data-cx/cy
      // are the auto-placement the drag resets toward. No data-segment (raster rooms have no
      // polygon) — _bindRoomNameDrag routes a TAP to select-by-number instead.
      const na = state.roomNameAnchor?.(String(r.number));
      const px = na ? Math.min(Math.max(na.x, 0), 100) : lx;
      const py = na ? Math.min(Math.max(na.y, 0), 100) : ly;
      return `<div class="evcc-map-label evcc-map-label--draggable${isSel ? " evcc-map-label--selected" : ""}" data-action="room-name-drag" data-room="${this.escapeHtml(String(r.number))}" data-cx="${lx}" data-cy="${ly}" style="left:${px}%;top:${py}%">`
           + `<span class="evcc-map-label-name">${this.escapeHtml(String(name))}</span></div>`;
    }).join("");
  };

  /**
   * User-drawn HIDDEN REGIONS — background-colored rects that mask map noise (a porch off a
   * room). Rendered INSIDE the rotator (so they rotate with the map), emitted LAST in the DOM
   * but at z-index 5 — so they cover every static z5 layer (room labels AND the area chips,
   * which also live in the device-overlay HTML) while the z6 robot/dock markers stay on top.
   * Each region is normalized [x0,y0,x1,y1]; positioned with the same letterbox transform the
   * device overlays use. Hidden by the "Hidden areas" toggle (unless editing, so you can still
   * see + delete them). In edit mode each gets a × delete + reads semi-transparent.
   */
  proto._renderHiddenRegions = function (state, editMode) {
    const regions = state.hiddenRegions?.() ?? [];
    if (!regions.length) return "";
    const visible = state.isOverlayVisible?.("hidden_regions") ?? true;
    if (!visible && !editMode) return "";   // toggled off + not editing -> reveal what's under
    const { tx, ty } = this._overlayTransform(state);
    const f = (v) => v.toFixed(2);
    const cls = "evcc-hidden-region" + (editMode ? " evcc-hidden-region--edit" : "");
    let out = "";
    for (let i = 0; i < regions.length; i++) {
      const r = regions[i];
      if (!Array.isArray(r) || r.length !== 4) continue;
      const left = tx(r[0]), top = ty(r[1]);
      const w = tx(r[2]) - left, h = ty(r[3]) - top;
      out += `<div class="${cls}" style="left:${f(left)}%;top:${f(top)}%;width:${f(w)}%;height:${f(h)}%">`
           + (editMode
               ? `<button class="evcc-hidden-region-del" data-action="delete-hidden-region" `
                 + `data-index="${i}" title="${this.t("map.remove_hidden_area_title")}" aria-label="${this.t("map.remove_hidden_area_aria")}">×</button>`
               : "")
           + `</div>`;
    }
    return out;
  };

  // The enabled (tapped) device rooms + their clean-order (sorted by the order field).
  // Map(deviceNumber -> orderPosition). Empty when nothing's selected.
  proto._selectedRoomOrder = function (state) {
    const enabled = (state.getRoomsForActiveMap?.() ?? []).filter((r) => r.enabled);
    const order = new Map();
    [...enabled].sort((a, b) => (a.order ?? 999) - (b.order ?? 999))
      .forEach((r, i) => order.set(Number(r.id), i + 1));
    return order;
  };

  /**
   * SUBTRACTIVE selection canvas: dims the UN-selected device rooms (per-pixel, exact room
   * shapes from the raster) so selected rooms stay bright with no bbox overlap. Rendered right
   * over the backdrop, inside the rotator (co-rotates). Drawn by the binding; only present when a
   * raster + a partial selection exist (all-selected => nothing to dim => no canvas).
   */
  proto._renderSelectionScrim = function (state) {
    if (!(state.overlaysAligned?.() ?? false)) return "";   // only over a co-registered backdrop
    const rd = state.mapRenderData?.();
    if (!rd || !rd.present) return "";
    const order = this._selectedRoomOrder(state);
    const total = (state.getRoomsForActiveMap?.() ?? []).length;
    if (order.size === 0 || order.size >= total) return "";   // none or all selected => no dim
    return `<canvas class="evcc-map-image evcc-map-selection-canvas" `
         + `data-sel-key="${this.escapeHtml(String(rd.version) + ":" + [...order.keys()].sort((a, b) => a - b).join(","))}"></canvas>`;
  };

  /**
   * Clean-ORDER badges for the selected rooms (HTML, at each room's bbox top-left). The exact
   * highlight is the subtractive scrim above; this just shows the sequence. Co-rotates; the badge
   * counter-rotates upright. Keyed by device room number (== managed room id).
   */
  proto._renderRoomSelection = function (state) {
    const mss = state.mapOverlayData?.() ?? state.mapStateSource?.();
    if (!mss || !mss.present || !Array.isArray(mss.rooms)) return "";
    const order = this._selectedRoomOrder(state);
    if (order.size === 0) return "";
    const { tx, ty } = this._overlayTransform(state);
    const f = (v) => v.toFixed(2);
    let out = "";
    for (const room of mss.rooms) {
      const pos = order.get(Number(room.number));
      if (pos == null || !Array.isArray(room.bbox) || room.bbox.length !== 4) continue;
      const [x0, y0, x1, y1] = room.bbox;
      out += `<div class="evcc-map-ov-selnum" style="left:${f(tx(Math.min(x0, x1)))}%;top:${f(ty(Math.min(y0, y1)))}%">${pos}</div>`;
    }
    return out;
  };

  /* =========================================================
     MAP LAYERS PANEL (right column; Wave 3c visibility toggles)
     ========================================================= */

  // The mascot controls (companion animal select + size + show/hide + follow-robot),
  // extracted from the rooms-view toggle bar so BOTH the panel and the embedded
  // dashboard map host render the identical, _bindMap-wired controls. The render-source
  // (live↔VA) toggle stays in the map toolbar; the texture/labels toggles stay in the
  // panel toggle bar. `this` is the renderers instance (has t/escapeHtml).
  proto._renderMapAnimalControls = function (state) {
    return `
        <select
          class="evcc-rooms-animal-select"
          data-action="map-animal-select"
          title="${this.t("rooms.companion_animal")}"
          aria-label="${this.t("rooms.companion_animal")}"
        >
          ${(() => {
            const list    = window.AnimalSVG?.list?.() ?? ["cat","dog","raccoon","parrot","snake"];
            const current = state.mapAnimalSelection?.() ?? "cat";
            const opt = (a) => {
              const def   = window.AnimalSVG?.get?.(a);
              const label = def?.label ?? (a.charAt(0).toUpperCase() + a.slice(1).replace(/_/g, " "));
              return `<option value="${a}"${current === a ? " selected" : ""}>${label}</option>`;
            };
            const memorial = list.filter((a) => window.AnimalSVG?.get?.(a)?.memorial);
            const regular  = list.filter((a) => !window.AnimalSVG?.get?.(a)?.memorial);
            return regular.map(opt).join("")
              + (memorial.length
                  ? `<optgroup label="🌈 ${this.t("rooms.rainbow_bridge")}">${memorial.map(opt).join("")}</optgroup>`
                  : "");
          })()}
        </select>
        <input
          type="range"
          class="evcc-rooms-animal-scale"
          data-action="map-animal-scale"
          min="0.5" max="3" step="0.25"
          value="${state.mapAnimalScale?.() ?? 1.0}"
          title="${this.t("rooms.icon_size")}"
          aria-label="${this.t("rooms.icon_size")}"
        >
        <button
          class="evcc-rooms-view-toggle-btn${(state.mapAnimalEnabled?.() ?? true) ? " active" : ""}"
          data-action="map-animal-toggle"
          title="${(state.mapAnimalEnabled?.() ?? true) ? this.t("rooms.hide_companion") : this.t("rooms.show_companion")}"
          aria-label="${(state.mapAnimalEnabled?.() ?? true) ? this.t("rooms.hide_companion") : this.t("rooms.show_companion")}"
          aria-pressed="${(state.mapAnimalEnabled?.() ?? true) ? "true" : "false"}"
        >
          <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor" stroke="none">
            <ellipse cx="8" cy="10.5" rx="3" ry="2.3"/>
            <circle cx="3.8" cy="7" r="1.3"/>
            <circle cx="6.5" cy="4.8" r="1.3"/>
            <circle cx="9.5" cy="4.8" r="1.3"/>
            <circle cx="12.2" cy="7" r="1.3"/>
          </svg>
        </button>
        <button
          class="evcc-rooms-view-toggle-btn${(state.mapAnimalFollowsRobot?.() ?? false) ? " active" : ""}"
          data-action="map-animal-follow-toggle"
          title="${(state.mapAnimalFollowsRobot?.() ?? false) ? this.t("rooms.mascot_follow_on") : this.t("rooms.mascot_follow_off")}"
          aria-label="${this.t("rooms.mascot_follows_robot")}"
          aria-pressed="${(state.mapAnimalFollowsRobot?.() ?? false) ? "true" : "false"}"
        >
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4">
            <circle cx="8" cy="8" r="3"/>
            <line x1="8" y1="0.5" x2="8" y2="3"/><line x1="8" y1="13" x2="8" y2="15.5"/>
            <line x1="0.5" y1="8" x2="3" y2="8"/><line x1="13" y1="8" x2="15.5" y2="8"/>
          </svg>
        </button>
        <button
          class="evcc-rooms-view-toggle-btn${(state.mapAnimalMoonwalk?.() ?? false) ? " active" : ""}"
          data-action="map-animal-moonwalk-toggle"
          title="${(state.mapAnimalMoonwalk?.() ?? false) ? this.t("rooms.moonwalk_on") : this.t("rooms.moonwalk_off")}"
          aria-label="${this.t("rooms.mascot_physics")}"
          aria-pressed="${(state.mapAnimalMoonwalk?.() ?? false) ? "true" : "false"}"
        >
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round">
            <path d="M2.5 11 H11"/><path d="M6 8 L3 11 L6 14"/><circle cx="12.4" cy="4.2" r="1.5" fill="currentColor" stroke="none"/>
          </svg>
        </button>`;
  };

  proto._renderMapLayersPanel = function (state) {
    const vis = state.mapOverlayVisibility?.() ?? {};
    const live = state.isLiveImageDisplayed?.() ?? false;
    const LAYERS = [
      { key: "current_room", label: this.t("map.layer_current_room") },
      { key: "robot",        label: this.t("map.layer_robot") },
      { key: "dock",         label: this.t("map.layer_dock") },
      { key: "room_area",    label: this.t("map.layer_room_area") },
      { key: "no_go",        label: this.t("map.layer_no_go") },
      { key: "no_mop",       label: this.t("map.layer_no_mop") },
      { key: "walls",        label: this.t("map.layer_walls") },
      { key: "zones",        label: this.t("map.layer_zones") },
      { key: "path",         label: this.t("map.layer_path") },
      { key: "obstacles",    label: this.t("map.layer_obstacles") },
      { key: "hidden_regions", label: this.t("map.layer_hidden_areas") },
    ];
    // Hide-area draw control. Available wherever a device-overlay-aligned backdrop is shown at
    // rotation 0 (same gate as the masks). In draw mode: drag to add a mask, × to delete one.
    const canHide  = state.canDrawHideArea?.() ?? false;
    const hideMode = canHide && (state.hideDrawMode?.() ?? false);
    const regionCount = (state.hiddenRegions?.() ?? []).length;
    return `
      <div class="evcc-map-layers-panel">
        <div class="evcc-map-layers-title">${this.t("map.layers_title")}</div>
        ${live ? "" : `<div class="evcc-map-layers-hint">${this.t("map.layers_hint")}</div>`}
        <div class="evcc-map-layers-list">
          ${LAYERS.map((l) => `
            <label class="evcc-map-layers-row">
              <input type="checkbox" data-action="toggle-map-overlay" data-layer="${l.key}"${vis[l.key] ? " checked" : ""}>
              <span>${l.label}</span>
            </label>`).join("")}
        </div>
        ${canHide ? `
        <div class="evcc-map-hide-tools">
          <button class="evcc-map-hide-btn${hideMode ? " evcc-map-hide-btn--on" : ""}"
                  data-action="toggle-hide-draw">
            ${hideMode ? this.t("map.hide_done") : this.t("map.hide_area")}
          </button>
          ${regionCount > 0 ? `
          <button class="evcc-map-hide-btn evcc-map-hide-btn--clear" data-action="clear-hidden-regions">
            ${this.t("map.hide_clear", { count: regionCount })}
          </button>` : ""}
        </div>
        ${hideMode ? `<div class="evcc-map-layers-hint">${this.t("map.hide_draw_hint")}</div>` : ""}
        ` : ""}
      </div>`;
  };

  /* =========================================================
     ZONE-CLEAN PANEL (rendered in the right column, under Run Profiles)
     ========================================================= */

  /**
   * The vacuum's clean-setting selects (Suction / Mode / Intensity / Water), rendered
   * live from the real provider entities. Shared by the ad-hoc zone panel AND the Saved
   * Zones panel — a zone clean (drawn or saved) runs off these current DEVICE settings,
   * so there is ONE source of truth. ``action`` scopes the change binding to the caller
   * (map panel = "zone-setting", saved-zones panel = "sz-setting") so the two don't
   * double-fire. Returns "" when the vacuum exposes no setting selects.
   *
   * @param {object} state
   * @param {string} [action="zone-setting"] data-action for the change binding.
   * @returns {string} HTML rows.
   */
  proto._renderZoneSettingRows = function (state, action = "zone-setting") {
    const esc = (s) => this.escapeHtml(String(s));
    const settingEntities = state.settingEntities?.() ?? {};
    const SETTINGS = [
      { key: "fan_speed",       label: this.t("map.zone_setting_suction") },
      { key: "clean_mode",      label: this.t("map.zone_setting_mode") },
      { key: "clean_intensity", label: this.t("map.zone_setting_intensity") },
      { key: "water_level",     label: this.t("map.zone_setting_water") },
    ];
    const rows = SETTINGS.map(({ key, label }) => {
      const eid = settingEntities[key];
      if (!eid) return "";
      const ent = state.entity?.(eid);
      const opts = ent?.attributes?.options ?? [];
      if (!ent || !opts.length) return "";
      const cur = ent.state;
      return `
        <label class="evcc-zone-setting">
          <span class="evcc-zone-setting-label">${label}</span>
          <select class="evcc-zone-setting-select" data-action="${esc(action)}"
                  data-entity-id="${esc(eid)}">
            ${opts.map((o) => `<option value="${esc(o)}"${o === cur ? " selected" : ""}>${this.tVocab(key, o, o)}</option>`).join("")}
          </select>
        </label>`;
    }).join("");
    // Fallback suction row for brands whose fan speed is the STANDARD vacuum entity
    // (fan_speed / fan_speed_list + vacuum.set_fan_speed) rather than a provider `select`
    // entity — e.g. Roborock, which declares fan_speed_options but no settings_select, so
    // the loop above renders nothing for it. A zone clean runs at the device's CURRENT fan
    // power, so editing it here (via set_fan_speed) is the same "runs off current device
    // settings" model as the select rows. Only when there's no fan_speed select (no doubling).
    const fanFallback = settingEntities.fan_speed ? "" : this._renderVacuumFanSpeedRow(state);
    return fanFallback + rows;
  };

  /**
   * A suction row backed by the HA-standard vacuum entity (fan_speed_list + fan_speed),
   * for brands with no provider fan-speed `select`. Change -> vacuum.set_fan_speed (card-wide
   * `zone-fanspeed` binding). Returns "" when the vacuum exposes no fan_speed_list.
   */
  proto._renderVacuumFanSpeedRow = function (state) {
    const esc = (s) => this.escapeHtml(String(s));
    const vid = state.vacuumEntityId?.();
    const ent = vid ? state.entity?.(vid) : null;
    const opts = ent?.attributes?.fan_speed_list;
    if (!ent || !Array.isArray(opts) || !opts.length) return "";
    const cur = ent.attributes?.fan_speed;
    return `
        <label class="evcc-zone-setting">
          <span class="evcc-zone-setting-label">${this.t("map.zone_setting_suction")}</span>
          <select class="evcc-zone-setting-select" data-action="zone-fanspeed">
            ${opts.map((o) => `<option value="${esc(o)}"${o === cur ? " selected" : ""}>${this.tVocab("fan_speed", o, o)}</option>`).join("")}
          </select>
        </label>`;
  };

  proto._renderZonePanel = function (state, zoneDrafts, zoneCount, zoneMax) {
    const settingRows = this._renderZoneSettingRows(state, "zone-setting");

    const zoneList = zoneDrafts.map((_, i) => `
      <li class="evcc-zone-list-item">
        <span class="evcc-zone-list-num">${i + 1}</span>
        <button class="evcc-zone-list-del" data-action="zone-remove" data-zone-index="${i}"
                title="${this.t("map.zone_remove", { num: i + 1 })}" aria-label="${this.t("map.zone_remove", { num: i + 1 })}">✕</button>
      </li>`).join("");

    return `
      <div class="evcc-zone-panel" role="group" aria-label="${this.t("map.zone_clean")}">
        <div class="evcc-zone-panel-title">${this.t("map.zone_clean")}</div>
        ${settingRows ? `
        <div class="evcc-zone-panel-section">
          <div class="evcc-zone-panel-section-title">${this.t("map.zone_settings")}
            <span class="evcc-zone-panel-note">${this.t("map.zone_settings_note")}</span></div>
          ${settingRows}
        </div>` : ""}
        <div class="evcc-zone-panel-section">
          <div class="evcc-zone-panel-section-title">${this.t("map.zone_zones")}
            <span class="evcc-zone-panel-note">${zoneCount}/${zoneMax}</span></div>
          ${zoneCount
            ? `<ul class="evcc-zone-list">${zoneList}</ul>`
            : `<div class="evcc-zone-panel-empty">${this.t("map.zone_empty")}</div>`}
        </div>
        <div class="evcc-zone-panel-actions">
          <button class="evcc-zone-bar-btn evcc-zone-bar-btn--primary"
                  data-action="zone-clean-confirm"${zoneCount ? "" : " disabled"}>${
            zoneCount > 1 ? this.t("map.zone_clean_n", { count: zoneCount }) : this.t("map.zone_clean_one")
          }</button>
          ${zoneCount ? `<button class="evcc-zone-bar-btn" data-action="zone-clear">${this.t("map.zone_clear")}</button>` : ""}
          <button class="evcc-zone-bar-btn" data-action="zone-clean-cancel">${this.t("common.cancel")}</button>
        </div>
      </div>`;
  };

  /* =========================================================
     SEGMENT POLYGON
     ========================================================= */

  proto._renderMapSegmentPolygon = function (seg, selectedIds, segIndex, label, hint, overrideColor) {
    const polygon = seg.polygon_pct;
    if (!Array.isArray(polygon) || polygon.length < 3) return "";

    const isSelected = selectedIds.has(String(seg.segment_id));
    const color = roomFillCss(segIndex, overrideColor);   // per-room override > theme palette > default
    const points = polygon.map(([x, y]) => `${x},${y}`).join(" ");

    return `<polygon
      class="evcc-map-polygon${isSelected ? " evcc-map-polygon--selected" : ""}"
      points="${points}"
      style="--seg-color:${color}"
      data-action="toggle-segment"
      data-segment-id="${this.escapeHtml(String(seg.segment_id))}"
      data-label="${this.escapeHtml(label ?? "")}"
      data-hint="${this.escapeHtml(hint ?? "")}"
    />`;
  };

  /* =========================================================
     ANIMAL SVG COMPANION
     =========================================================
     Renders an <animal-svg> at the polygon centroid of the
     first selected segment (or first segment overall as a
     fallback so the companion is always visible on the map).

     Position uses the same per-room anchor system as the old
     presence dot: user can click to place it, default is the
     polygon centroid from the image segmentation data.

     Pose is derived from the current vacuum entity state.
     The docked/idle pose ("curled") gets a gentle luminance
     pulse via the --pulse CSS modifier.
     ========================================================= */

  proto._renderMapAnimal = function (state, vacuumStatus) {
    if (!(state.mapAnimalEnabled?.() ?? true)) return "";   // mascot toggled off

    const isAtDock = (vacuumStatus === "docked" || vacuumStatus === "idle");
    // Follow-robot mode: ride the live robot pixel (replacing the position dot). When
    // docked we fall through to the dock-spot homing below, so the calm parked placement
    // and dragging both survive. Reads the live anchor + transform exactly as the dot does.
    if ((state.mapAnimalFollowsRobot?.() ?? false) && !isAtDock) {
      const mss = state.mapOverlayData?.() ?? state.mapStateSource?.();
      if (mss && Array.isArray(mss.robot_anchor) && mss.robot_anchor.length === 2) {
        const { tx, ty } = this._overlayTransform(state);
        const [rx, ry] = mss.robot_anchor;
        // Direction-aware mirror (follow mode only): face travel (Normal universe) or its
        // opposite (Moonwalk mode). facing = committed travel sign (+1 = moving screen-right).
        // The animal sprites are authored facing LEFT, so mirror when the EFFECTIVE facing is
        // screen-RIGHT (eff > 0) — confirmed against the live render 2026-07-05.
        const facing = state.mascotFacing?.() ?? 1;
        const eff = (state.mapAnimalMoonwalk?.() ?? false) ? -facing : facing;
        return this._animalDivHtml(state, vacuumStatus, (+tx(rx)).toFixed(2), (+ty(ry)).toFixed(2), null, eff > 0);
      }
    }

    const allSegments = state.mapSegments();
    const rooms       = state.getRoomsForActiveMap?.() ?? [];

    // --- Determine which segment anchors the companion ---
    //
    // Priority:
    //  1. Docked / idle  → dock room (isDockRoom from integration access graph)
    //  2. Active job     → current_room_id from dashboardJobProgress (backend computed)
    //  3. Fallback       → first segment so the companion is always visible
    //
    // The card does no computation — all room inference is done by the backend.

    let targetSeg = null;

    const _segForRoom = (roomId) => {
      if (roomId == null) return null;
      const segId = state.segmentIdForRoom?.(roomId);
      if (segId == null) return null;
      return allSegments.find((s) => String(s.segment_id) === String(segId)) ?? null;
    };

    if (isAtDock) {
      const dockRoom = rooms.find((r) => r.isDockRoom);
      targetSeg = _segForRoom(dockRoom?.id);
    }

    if (!targetSeg) {
      const progress = state.dashboardJobProgress?.();
      const mss = state.mapOverlayData?.() ?? state.mapStateSource?.();
      // Prefer the dwell-debounced live room (the room the robot is physically in,
      // incl. transit rooms, committed only after sustained dwell — display only,
      // separate from the job rollover). Fall back to the live map source's own
      // current_room (device segmentation, render-frame) before the dwell commits,
      // then current_room_id (next queued room). Both ride the real map — no bounds.
      const currentRoomId = state.mascotDwelledRoomId?.()
        ?? mss?.current_room ?? progress?.current_room_id;
      targetSeg = _segForRoom(currentRoomId);
    }

    if (!targetSeg) {
      targetSeg = allSegments[0] ?? null;
    }

    // No drawn/CV segment to anchor to (a bare live map) — fall back to the device's own
    // rooms / dock / robot from map_state_source so the mascot still shows.
    if (!targetSeg) return this._mapAnimalDeviceFallback(state, vacuumStatus, isAtDock);

    // Resolve position: stored user anchor OR polygon centroid.
    // Anchor is keyed by room ID when available, else by segment ID
    // so unlinked segments can still hold a user-placed position.
    const roomId    = state.roomIdForSegment(targetSeg.segment_id);
    // When docked, the mascot homes to a single map-level "dock" spot (not a
    // room) — drag it once to park it anywhere, e.g. on the sun of a space map.
    // Falls back to the resolved segment's centroid until that spot is set.
    const lookupKey = isAtDock
      ? "dock"
      : (roomId != null ? String(roomId) : `seg_${targetSeg.segment_id}`);
    let pct_x, pct_y;
    const stored = state.roomDotAnchor?.(lookupKey);

    if (stored) {
      pct_x = stored.pct_x;
      pct_y = stored.pct_y;
    } else {
      const poly = targetSeg.polygon_pct;
      if (!Array.isArray(poly) || poly.length < 3) return "";
      [pct_x, pct_y] = _polygonCentroid(poly);
    }

    // Anchor key matches the lookup key — so dragging the DOCKED mascot writes
    // the shared "dock" spot, while dragging it mid-clean writes the per-room
    // anchor as before.
    return this._animalDivHtml(state, vacuumStatus, pct_x, pct_y, lookupKey);
  };

  /* Mascot fallback for a bare live map (no drawn segments to anchor to): home to the
     user's dragged "dock" spot or the device dock anchor when docked, else ride the current
     device room's centre (or the robot). Positions via the overlay transform (normalized ->
     content %), the same frame the device markers use. "" when no live pose is available. */
  proto._mapAnimalDeviceFallback = function (state, vacuumStatus, isAtDock) {
    const mss = state.mapOverlayData?.() ?? state.mapStateSource?.();
    if (!mss || !mss.present) return "";
    const { tx, ty } = this._overlayTransform(state);
    if (isAtDock) {
      const stored = state.roomDotAnchor?.("dock");
      if (stored) return this._animalDivHtml(state, vacuumStatus, stored.pct_x, stored.pct_y, "dock");
      if (Array.isArray(mss.dock_anchor) && mss.dock_anchor.length === 2) {
        return this._animalDivHtml(
          state, vacuumStatus, (+tx(mss.dock_anchor[0])).toFixed(2),
          (+ty(mss.dock_anchor[1])).toFixed(2), "dock");
      }
    }
    const cur = mss.current_room;
    const room = (cur != null && Array.isArray(mss.rooms))
      ? mss.rooms.find((r) => String(r.number) === String(cur)) : null;
    if (room && Array.isArray(room.bbox) && room.bbox.length === 4) {
      const cx = (room.bbox[0] + room.bbox[2]) / 2;
      const cy = (room.bbox[1] + room.bbox[3]) / 2;
      return this._animalDivHtml(state, vacuumStatus, (+tx(cx)).toFixed(2), (+ty(cy)).toFixed(2), null);
    }
    if (Array.isArray(mss.robot_anchor) && mss.robot_anchor.length === 2) {
      return this._animalDivHtml(
        state, vacuumStatus, (+tx(mss.robot_anchor[0])).toFixed(2),
        (+ty(mss.robot_anchor[1])).toFixed(2), null);
    }
    return "";
  };

  /* Render the <animal-svg> companion div at a map-content-box % position.
     anchorKey != null → draggable (writes that per-room / "dock" anchor on drag);
     anchorKey == null → follow-robot mode: NO drag (it's tracking the live pixel).
     Battery state is an auxiliary visual signal orthogonal to pose (five-band
     charging/good/mid/warn/low → eye color via :host([battery-state]) + charge pulse). */
  proto._animalDivHtml = function (state, vacuumStatus, pct_x, pct_y, anchorKey, flip) {
    const pose         = _vacuumStateToPose(vacuumStatus ?? "");
    const isDocked     = pose === "curled";
    const animal       = state.mapAnimalSelection?.() ?? "cat";
    const scale        = state.mapAnimalScale?.()     ?? 1.0;
    const batteryState = state.batteryState?.()       ?? "good";
    const W = Math.round(64 * scale);
    const H = Math.round(44 * scale);
    const drag = anchorKey != null
      ? ` data-action="map-dot-click" data-anchor-key="${this.escapeHtml(String(anchorKey))}"`
        + ` title="${isDocked ? this.t("map.mascot_dock_home") : this.t("map.mascot_reposition")}"`
      : ` title="${this.t("map.mascot_following")}"`;
    return `<div class="evcc-map-animal${isDocked ? " evcc-map-animal--pulse" : ""}`
         + `${anchorKey == null ? " evcc-map-animal--following" : ""}${flip ? " evcc-map-animal--flip" : ""}"`
         + ` style="left:${pct_x}%;top:${pct_y}%;width:${W}px;height:${H}px"${drag}`
         + `><animal-svg animal="${this.escapeHtml(animal)}" pose="${this.escapeHtml(pose)}"`
         + ` width="${W}px" height="${H}px" battery-state="${this.escapeHtml(batteryState)}"></animal-svg></div>`;
  };

  /* =========================================================
     SELECTION BAR
     ========================================================= */

  proto._renderMapSelectionBar = function (segments, state) {
    const rooms = state.getRoomsForActiveMap?.() ?? [];

    const chips = segments.map((seg, idx) => {
      const roomId = state.roomIdForSegment(seg.segment_id);
      const room   = roomId != null
        ? rooms.find((r) => String(r.id) === String(roomId))
        : null;

      const label   = room?.name ?? seg.name ?? seg.label
        ?? this.t("map.segment_fallback", { id: seg.segment_id });
      const summary = room ? this._mapRoomSettingsSummary(room) : "";

      return `
        <div
          class="evcc-map-chip"
          data-action="map-chip-activate"
          data-segment-id="${this.escapeHtml(String(seg.segment_id))}"
          data-room-id="${roomId != null ? this.escapeHtml(String(roomId)) : ""}"
        >
          <span class="evcc-map-chip-order">${idx + 1}</span>
          <div class="evcc-map-chip-body">
            <span class="evcc-map-chip-label">${this.escapeHtml(label)}</span>
            ${summary
              ? `<span class="evcc-map-chip-settings">${this.escapeHtml(summary)}</span>`
              : ""}
          </div>
        </div>
      `;
    }).join("");

    return `<div class="evcc-map-selection-bar">${chips}</div>`;
  };

  proto._mapRoomSettingsSummary = function (room) {
    const parts = [];
    if (room.fanSpeed) parts.push(room.fanSpeed);
    if (room.waterLevel) parts.push(room.waterLevel);
    return parts.join(" · ");
  };

  /* =========================================================
     MAP CONFIG VIEW
     ========================================================= */

  proto.renderMapConfigView = function (ctx) {
    const { state } = ctx;

    const segmentsData   = state.mapSegmentsData();
    const imageUrl       = state.mapImageUrl();
    const segments       = state.mapSegments();
    const selectedId     = state.configSelectedSegmentId();
    const selectedSeg    = state.configSelectedSegment();
    const variants       = segmentsData?.image_variants ?? {};
    const summary        = { ...(segmentsData?.summary ?? {}), analyzed_at: segmentsData?.analyzed_at };
    const actionStatus   = state.mapActionStatus?.() ?? null;
    const isCustom       = (state.segmentationMode?.() ?? "cv") === "custom";
    // Per-room fill overrides, so the config editor shows the same room colors as the live map.
    const rooms          = state.getRoomsForActiveMap?.() ?? [];

    // Config mode shares the same zoom state as the rooms view — same
    // bindings drive it, same toolbar reflects it. The .evcc-map-layers
    // wrapper here mirrors the rooms-view structure so the CSS
    // transform on it scales both the image and the polygon SVG
    // together.
    const zoom = state.mapZoom?.() ?? 1;
    const tx   = state.mapTranslateX?.() ?? 0;
    const ty   = state.mapTranslateY?.() ?? 0;

    // D5 — fix the composer-rotation gap: wrap the config content in
    // .evcc-map-content-rotator (like the room view) so art authored here is WYSIWYG vs
    // the rotated room view. Rotate ONLY over a live-CONTAIN backdrop (isLiveBackdropActive
    // — the "Live map" layout or a per-layout backdrop not yet uploaded); an uploaded
    // --fill backdrop must NOT rotate (its polygons would drift, same rule as
    // effectiveMapRotation). The drag handler routes pointer→content through unrotatePct
    // with this same value so authoring stays correct across rotation.
    const liveBackdrop = state.isLiveBackdropActive?.() ?? false;
    const configRot = liveBackdrop ? (state.effectiveMapRotation?.() ?? 0) : 0;
    // Furnished art authoring is live only on the "Live map" custom layout.
    const furnishedOn = state.isFurnishedLayoutActive?.() ?? false;
    const furnishedMode = furnishedOn ? (state.furnishedRenderMode?.() ?? "live") : "live";
    const baseFadeCls = furnishedOn && furnishedMode !== "live"
      ? ` evcc-map-image--furnished-${furnishedMode}` : "";

    return `
      <div class="evcc-map-config-view">

        <div class="evcc-map-config-header">
          <button class="evcc-map-config-back" data-action="map-config-back" aria-label="${this.t("map.config_back_aria")}">
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <polyline points="10,3 4,8 10,13"/>
            </svg>
            ${this.t("map.config_back")}
          </button>
          <span class="evcc-map-config-title">${this.t("map.config_title")}</span>
        </div>

        <div class="evcc-map-config-body">

          <div class="evcc-map-container evcc-map-container--config">
            ${imageUrl
              ? `<div class="evcc-map-layers" style="transform:translate(${tx}px,${ty}px) scale(${zoom});transform-origin:0 0">
                 <div class="evcc-map-content-rotator" style="transform:rotate(${configRot}deg);--evcc-map-rotation:${configRot}deg">
                   <img class="evcc-map-image${isCustom && !liveBackdrop ? " evcc-map-image--fill" : ""}${baseFadeCls}" src="${this.escapeHtml(imageUrl)}" alt="${this.t("map.floor_plan_alt")}" draggable="false">
                   ${(furnishedOn && furnishedMode !== "live") ? this._renderFurnishedArt(state, true) : ""}
                   <svg class="evcc-map-svg" viewBox="0 0 100 100" preserveAspectRatio="none">
                     ${isCustom
                       ? this._renderComposerShapes(state)
                       : segments.map((seg, i) => {
                           const isThis = String(seg.segment_id) === String(selectedId ?? "");
                           const rid = state.roomIdForSegment(seg.segment_id);
                           const room = rid != null ? rooms.find((r) => String(r.id) === String(rid)) : null;
                           return this._renderConfigPolygon(seg, selectedId, i, isThis ? (state.configSelectedVertexIndex?.() ?? null) : null, zoom, room?.color);
                         }).join("")}
                   </svg>
                 </div>
                 </div>
                 <div class="evcc-map-zoom-toolbar" aria-label="${this.t("map.zoom_controls_aria")}">
                   <button class="evcc-map-zoom-btn" data-action="map-zoom-out"
                           title="${this.t("map.zoom_out")}" aria-label="${this.t("map.zoom_out")}">−</button>
                   <button class="evcc-map-zoom-btn" data-action="map-zoom-fit"
                           title="${this.t("map.zoom_fit")}" aria-label="${this.t("map.zoom_fit_aria")}">⤢</button>
                   <button class="evcc-map-zoom-btn" data-action="map-zoom-in"
                           title="${this.t("map.zoom_in")}" aria-label="${this.t("map.zoom_in")}">+</button>
                   <span class="evcc-map-zoom-readout"
                         aria-label="${this.t("map.zoom_level_aria")}">${Math.round(zoom * 100)}%</span>
                 </div>`
              : `<div class="evcc-map-unavailable">
                   <p>${this.t("map.config_no_image")}</p>
                 </div>`}
          </div>

          <div class="evcc-map-config-side-panel">
            ${furnishedOn ? this._renderFurnishedToolbar(state, actionStatus) : ""}
            ${isCustom
              ? this._renderComposerToolbar(state)
              : (selectedSeg
                ? this._renderSegmentAdjustSection(selectedSeg, state)
                : `<div class="evcc-map-config-section evcc-map-config-section--hint">
                     <p>${this.t("map.config_click_segment")}</p>
                   </div>`)}
          </div>

        </div>

        <div class="evcc-map-config-panel">
          ${this._renderSegmentationToggle(state)}
          ${(state.segmentationMode?.() ?? "cv") === "custom"
            ? this._renderCustomBackdropSection(variants, actionStatus, state)
            : this._renderVariantsSection(variants, summary, actionStatus, state)}
        </div>

      </div>
    `;
  };

  /* =========================================================
     CONFIG POLYGON
     ========================================================= */

  proto._renderConfigPolygon = function (seg, selectedId, segIndex, selectedVertexIdx, zoom = 1, overrideColor) {
    const polygon = seg.polygon_pct;
    if (!Array.isArray(polygon) || polygon.length < 3) return "";

    const isSelected = String(seg.segment_id) === String(selectedId ?? "");
    const color = roomFillCss(segIndex, overrideColor);   // per-room override > theme palette > default
    const points = polygon.map(([x, y]) => `${x},${y}`).join(" ");
    const segIdStr = this.escapeHtml(String(seg.segment_id));

    const polygonEl = `<polygon
      class="evcc-map-polygon evcc-map-polygon--config"
      points="${points}"
      style="fill:${color};fill-opacity:${isSelected ? "0.20" : "0.06"};stroke:${isSelected ? "#ffffff" : color};stroke-width:${isSelected ? "1.8" : "1.1"};stroke-opacity:${isSelected ? "1" : "0.7"};vector-effect:non-scaling-stroke"
      data-action="config-select-segment"
      data-segment-id="${segIdStr}"
    />`;

    let vertexEls = "";
    if (isSelected) {
      vertexEls = polygon.map(([x, y], i) => {
        const isSelV = selectedVertexIdx === i;
        return `<circle
          class="evcc-map-vertex-dot${isSelV ? " evcc-map-vertex-dot--selected" : ""}"
          cx="${x}" cy="${y}" r="${((isSelV ? 1.1 : 0.65) / zoom).toFixed(3)}"
          style="fill:${isSelV ? "#ffdd00" : color};stroke:${isSelV ? "#000" : "rgba(0,0,0,0.55)"};stroke-width:0.9;pointer-events:all;cursor:pointer;vector-effect:non-scaling-stroke"
          data-action="select-vertex"
          data-segment-id="${segIdStr}"
          data-vertex-index="${i}"
        />`;
      }).join("");
    }

    return `<g>${polygonEl}${vertexEls}</g>`;
  };

  /* =========================================================
     VARIANTS SECTION
     ========================================================= */

  // A proto method (not a closure) so it can reach this.t — the relative-time
  // strings come from the shared i18n `relative.*` catalog. Buckets/thresholds
  // are unchanged; only >14d falls through to a locale-formatted date.
  proto._formatAnalyzedAt = function (isoStr) {
    if (!isoStr) return null;
    const d = new Date(isoStr);
    if (isNaN(d)) return null;
    const diffMs  = Date.now() - d.getTime();
    const diffMin = Math.floor(diffMs / 60000);
    if (diffMin < 1)  return this.t("relative.just_now");
    if (diffMin < 60) return this.t("relative.minutes_ago", { count: diffMin });
    const diffH = Math.floor(diffMin / 60);
    if (diffH < 24)   return this.t("relative.hours_ago", { count: diffH });
    const diffD = Math.floor(diffH / 24);
    if (diffD < 14)   return this.t("relative.days_ago", { count: diffD });
    return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
  };

  /* =========================================================
     SEGMENTATION MODE TOGGLE (CV vs Custom)
     ========================================================= */

  proto._renderSegmentationToggle = function (state) {
    const mode      = state.segmentationMode?.() ?? "cv";
    const layouts   = state.customLayouts?.() ?? [];
    const activeId  = state.activeCustomLayoutId?.();
    const editing   = state.isLayoutEditorOpen?.();
    const editMode  = state.layoutEditorMode?.() ?? "new";
    const draftName = state.layoutDraftName?.() ?? "";
    const esc = (s) => this.escapeHtml(String(s));

    // CV is the special always-present option; each custom layout is its own chip;
    // "＋ New" opens the inline name editor. Switching a chip swaps the whole
    // layout (backdrop + authored rooms + links + mascot home).
    // Auto (CV) needs the optional science stack (numpy/Pillow/scipy). When it's
    // missing, hide the chip and explain below — it would otherwise silently produce
    // nothing. Live/custom/manual paths don't need it.
    const cvOk = state.cvAvailable?.() ?? true;
    const _cvPkgLabel = { numpy: "numpy", pillow: "Pillow", scipy: "scipy", scipy_ndimage: "scipy" };
    const cvMissingText =
      [...new Set((state.cvMissing?.() ?? []).map((p) => _cvPkgLabel[p] ?? p))].join(", ")
      || "numpy, Pillow, scipy";
    const cvChip = cvOk ? `
      <button class="evcc-map-mode-btn${mode === "cv" ? " evcc-map-mode-btn--active" : ""}"
        data-action="set-segmentation-mode" data-mode="cv"
        title="${this.t("map.seg_cv_title")}">${this.t("map.seg_cv")}</button>` : "";
    // The live-pinned layout is represented by the dedicated "Live map" chip below,
    // not as a regular named layout chip — filter it out here to avoid a duplicate.
    const layoutChips = layouts
      .filter((l) => l.backdrop_source !== "live")
      .map((l) => `
      <button class="evcc-map-mode-btn${mode === "custom" && String(l.id) === String(activeId) ? " evcc-map-mode-btn--active" : ""}"
        data-action="set-active-custom-layout" data-layout-id="${esc(l.id)}"
        title="${this.t("map.seg_custom_layout_title", { name: esc(l.name) })}">${esc(l.name)}</button>`).join("");
    // "Live map" chip — only when a live-map entity is available. Selects (or creates)
    // the layout pinned to the live backdrop, so the composer draws rooms straight over
    // the live camera/image. Active when that layout is current.
    const hasLive = Boolean(state.liveMapImageEntity?.());
    const liveActive = mode === "custom" && state.activeCustomLayout?.()?.backdrop_source === "live";
    const liveChip = hasLive ? `
      <button class="evcc-map-mode-btn${liveActive ? " evcc-map-mode-btn--active" : ""}"
        data-action="select-or-create-live-layout"
        title="${this.t("map.seg_live_title")}">${this.t("map.seg_live")}</button>` : "";
    const newChip = `
      <button class="evcc-map-mode-btn" data-action="open-new-layout"
        title="${this.t("map.seg_new_title")}">${this.t("map.seg_new")}</button>`;

    return `
      <div class="evcc-map-config-section">
        <div class="evcc-map-config-section-title">${this.t("map.seg_title")}</div>
        <div class="evcc-map-mode-toggle">
          ${liveChip}${cvChip}${layoutChips}${newChip}
        </div>
        ${!cvOk ? `
        <div class="evcc-map-cv-unavailable">
          ${this.tRaw("map.seg_cv_unavailable", { packages: esc(cvMissingText) })}
        </div>` : ""}
        ${editing ? `
        <div class="evcc-compose-tools">
          <input type="text" class="evcc-map-config-input" data-layout-field="name"
            value="${esc(draftName)}" placeholder="${this.t("map.layout_name_placeholder")}" />
          <button class="evcc-map-config-btn evcc-map-config-btn--primary"
            data-action="${editMode === "rename" ? "rename-layout-save" : "create-layout-save"}"
          >${editMode === "rename" ? this.t("common.save") : this.t("map.layout_create")}</button>
          <button class="evcc-map-config-btn" data-action="cancel-layout-editor">${this.t("common.cancel")}</button>
        </div>` : ""}
        ${mode === "custom" && activeId ? `
        <div class="evcc-compose-tools">
          <button class="evcc-map-config-btn" data-action="open-rename-layout">${this.t("common.rename")}</button>
          <button class="evcc-map-config-btn evcc-map-config-btn--danger" data-action="delete-layout">${this.t("map.layout_delete")}</button>
        </div>` : ""}
      </div>
    `;
  };

  /* =========================================================
     CUSTOM BACKDROP (custom mode only)
     =========================================================
     The backdrop is uploaded as the `custom` image variant via the
     shared upload-map-variant binding, which skips analyze for this
     variant (it is a tracing image, never segmented). mapImageUrl()
     surfaces it in the config map area once it lands. */

  proto._renderCustomBackdropSection = function (variants, actionStatus, state) {
    // Each custom layout owns its backdrop under a per-layout variant key
    // (custom_<id>); the legacy single-custom flow uses the shared "custom".
    // Read + upload against the ACTIVE layout's key so the status + Upload button
    // reflect THIS layout, not whichever shared image happens to exist.
    const variantKey = state?.activeCustomLayout?.()?.backdrop_variant || "custom";
    const custom  = variants?.[variantKey];
    const isBusy  = actionStatus?.type === "upload" && actionStatus?.variant === variantKey
                    && actionStatus?.status === "busy";
    const isError = actionStatus?.type === "upload" && actionStatus?.variant === variantKey
                    && actionStatus?.status === "error";
    const statusText = custom ? `${custom.width} × ${custom.height}` : this.t("map.backdrop_none");
    const statusCls  = custom
      ? "evcc-map-variant-status--ok"
      : "evcc-map-variant-status--missing";

    return `
      <div class="evcc-map-config-section">
        <div class="evcc-map-config-section-title">${this.t("map.backdrop_title")}</div>
        <div class="evcc-map-variant-row">
          <div class="evcc-map-variant-info">
            <span class="evcc-map-variant-label">${this.t("map.backdrop_image_label")}</span>
            <span class="evcc-map-variant-hint">${this.t("map.backdrop_image_hint")}</span>
          </div>
          <span class="evcc-map-variant-status ${statusCls}">${statusText}</span>
          ${isError
            ? `<span class="evcc-map-action-status evcc-map-action-status--error">${actionStatus.message ? this.escapeHtml(actionStatus.message) : this.t("map.upload_failed")}</span>`
            : ""}
          <button
            class="evcc-map-config-btn${isBusy ? " evcc-map-config-btn--busy" : ""}"
            data-action="upload-map-variant"
            data-variant="${this.escapeHtml(variantKey)}"
            ${isBusy ? "disabled" : ""}
          >${isBusy ? this.t("map.uploading") : custom ? this.t("map.replace") : this.t("map.upload")}</button>
        </div>
      </div>
    `;
  };

  /* =========================================================
     CUSTOM-SEGMENT COMPOSER (custom mode authoring canvas)
     =========================================================
     Draws the in-progress draft shapes onto the backdrop SVG, and a
     toolbar in the side panel. Shapes are pct-space; the SVG viewBox is
     0 0 100 100 (preserveAspectRatio none) so a "circle" renders as an
     ellipse, matching how the backdrop fills the frame. Drag + Save
     (-> set_custom_segments) land in later passes. */

  proto._renderComposerShapes = function (state) {
    const draft = state.composeDraft?.() ?? [];
    const selId = state.composeSelectedId?.();
    // Colour only MERGED groups (2+ shapes) so the common one-shape-per-room case
    // keeps the default accent, while merged rooms share a distinguishing stroke.
    const groupOf = (s) => s.group ?? s.id;
    const sizes = {};
    for (const s of draft) sizes[groupOf(s)] = (sizes[groupOf(s)] || 0) + 1;
    const palette = ["#5ac8fa", "#ffd60a", "#ff9f0a", "#bf5af2", "#30d158", "#ff6482"];
    const colorByGroup = {};
    let ci = 0;
    for (const s of draft) {
      const g = groupOf(s);
      if (sizes[g] >= 2 && !(g in colorByGroup)) colorByGroup[g] = palette[ci++ % palette.length];
    }
    return draft
      .map((s) => this._renderComposerShape(s, s.id === selId, colorByGroup[groupOf(s)] ?? null))
      .join("");
  };

  proto._renderComposerShape = function (s, isSel, color) {
    let cls = "evcc-compose-shape";
    if (isSel) cls += " evcc-compose-shape--selected";
    if (s.op === "subtract") cls += " evcc-compose-shape--cut";
    const style = color ? ` style="--evcc-grp:${color}"` : "";

    // Per-type geometry + (rect-only) rotation, shared by the shape and its halo.
    let tag, geom, rot = "";
    if (s.type === "circle") {
      tag = "ellipse";
      geom = `cx="${s.cx}" cy="${s.cy}" rx="${s.r}" ry="${s.r}"`;
    } else if (s.type === "polygon") {
      tag = "polygon";
      geom = `points="${(s.points || []).map(([x, y]) => `${x},${y}`).join(" ")}"`;
    } else {
      tag = "rect";
      geom = `x="${s.x}" y="${s.y}" width="${s.w}" height="${s.h}"`;
      if (s.angle) rot = ` transform="rotate(${s.angle} ${s.x + s.w / 2} ${s.y + s.h / 2})"`;
    }

    // A selected shape gets a non-interactive black halo drawn UNDER its bright 3px
    // outline, so the selection stays legible on any backdrop: 1px of black shows on
    // each side of the stroke (the black reads on light photos, the bright core on
    // dark CV maps).
    const halo = isSel
      ? `<${tag} class="evcc-compose-shape-halo"${rot} ${geom}/>`
      : "";
    const shape =
      `<${tag} class="${cls}"${style}${rot} data-action="compose-select" ` +
      `data-shape-id="${this.escapeHtml(String(s.id))}" ${geom}/>`;
    return halo + shape;
  };

  proto._renderComposerToolbar = function (state) {
    const count    = state.composeDraft?.().length ?? 0;
    const hasSel   = state.composeSelectedId?.() != null;
    const status   = state.mapActionStatus?.() ?? null;
    const saveBusy = status?.type === "compose-save" && status?.status === "busy";
    const saveErr  = status?.type === "compose-save" && status?.status === "error";
    return `
      <div class="evcc-map-config-section">
        <div class="evcc-map-config-section-title">${this.t("map.compose_rooms")}</div>
        <div class="evcc-compose-tools">
          <button class="evcc-map-config-btn" data-action="compose-add" data-shape-type="rect">${this.t("map.compose_add_rect")}</button>
          <button class="evcc-map-config-btn" data-action="compose-add" data-shape-type="circle">${this.t("map.compose_add_circle")}</button>
        </div>
        <div class="evcc-map-config-adj-meta">${this.t("map.compose_shape_count", { count })}${hasSel ? "" : (count ? this.t("map.compose_tap_to_edit") : this.t("map.compose_add_to_start"))}</div>
      </div>
      ${this._renderComposerSelectedControls(state)}
      ${this._renderComposerRoomAssign(state)}
      <div class="evcc-map-config-section">
        <div class="evcc-compose-tools">
          <button class="evcc-map-config-btn evcc-map-config-btn--danger" data-action="compose-delete" ${hasSel ? "" : "disabled"}>${this.t("common.delete")}</button>
          <button class="evcc-map-config-btn" data-action="compose-clear" ${count ? "" : "disabled"}>${this.t("map.compose_clear_all")}</button>
        </div>
        <button
          class="evcc-map-config-btn evcc-map-config-btn--primary${saveBusy ? " evcc-map-config-btn--busy" : ""}"
          data-action="compose-save"
          ${(count && !saveBusy) ? "" : "disabled"}
        >${saveBusy ? this.t("common.saving") : this.t("map.compose_save")}</button>
        ${saveErr
          ? `<span class="evcc-map-action-status evcc-map-action-status--error">${status.message ? this.escapeHtml(status.message) : this.t("map.save_failed")}</span>`
          : ""}
      </div>
    `;
  };

  /* =========================================================
     FURNISHED ART TOOLBAR (config view; "Live map" layout only)
     =========================================================
     Upload a to-scale home render, pick a render mode (live/art/blend), and align the
     art over the live map (nudge/scale/rotate; pointer-drag on the art itself). Matches
     the composer toolbar UX. Only shown when the furnished layout is active. */
  proto._renderFurnishedToolbar = function (state, actionStatus) {
    const hasArt = Boolean(state.furnishedHomeArtUrl?.());
    const mode   = state.furnishedRenderMode?.() ?? "live";
    const t      = state.furnishedArtTransform?.() ?? { scale: 1, rotation: 0 };
    const isBusy = actionStatus?.type === "upload" && actionStatus?.variant === "furnished-art"
                   && actionStatus?.status === "busy";
    const isErr  = actionStatus?.type === "upload" && actionStatus?.variant === "furnished-art"
                   && actionStatus?.status === "error";
    const isExportErr = actionStatus?.type === "export" && actionStatus?.variant === "furnished-map"
                   && actionStatus?.status === "error";
    const noSize = !(state.mapImageSize?.());

    const modeBtn = (key, label, hint) => `
      <button class="evcc-map-config-btn${mode === key ? " evcc-map-config-btn--primary" : ""}"
        data-action="furnished-render-mode" data-mode="${key}" title="${hint}"
        ${hasArt || key === "live" ? "" : "disabled"}>${label}</button>`;

    return `
      <div class="evcc-map-config-section">
        <div class="evcc-map-config-section-title">${this.t("map.furnished_title")}</div>
        <div class="evcc-map-config-adj-meta">
          ${this.t("map.furnished_intro")}
        </div>
        <div class="evcc-map-config-adj-meta">
          ${this.t("map.furnished_tip")}
        </div>
        <div class="evcc-compose-tools">
          <button class="evcc-map-config-btn" data-action="furnished-export-map"
            title="${this.t("map.furnished_export_title")}">${this.t("map.furnished_export")}</button>
        </div>
        ${isExportErr ? `<span class="evcc-map-action-status evcc-map-action-status--error">${actionStatus.message ? this.escapeHtml(actionStatus.message) : this.t("map.furnished_export_failed")}</span>` : ""}
        ${noSize ? `<div class="evcc-map-action-status evcc-map-action-status--error">
          ${this.t("map.furnished_no_size")}</div>` : ""}
        <div class="evcc-compose-tools">
          <button class="evcc-map-config-btn${isBusy ? " evcc-map-config-btn--busy" : ""}"
            data-action="upload-furnished-art" ${isBusy ? "disabled" : ""}>
            ${isBusy ? this.t("map.uploading") : hasArt ? this.t("map.furnished_replace_art") : this.t("map.furnished_upload_art")}</button>
          ${hasArt ? `<button class="evcc-map-config-btn evcc-map-config-btn--danger"
            data-action="furnished-art-clear" title="${this.t("map.furnished_reset_title")}">${this.t("map.furnished_reset")}</button>` : ""}
        </div>
        ${isErr ? `<span class="evcc-map-action-status evcc-map-action-status--error">${actionStatus.message ? this.escapeHtml(actionStatus.message) : this.t("map.upload_failed")}</span>` : ""}
      </div>
      ${hasArt ? `
      <div class="evcc-map-config-section">
        <div class="evcc-map-config-section-title">${this.t("map.furnished_render_mode")}</div>
        <div class="evcc-compose-tools">
          ${modeBtn("live", this.t("map.furnished_mode_live"), this.t("map.furnished_mode_live_title"))}
          ${modeBtn("blend", this.t("map.furnished_mode_blend"), this.t("map.furnished_mode_blend_title"))}
          ${modeBtn("art", this.t("map.furnished_mode_art"), this.t("map.furnished_mode_art_title"))}
        </div>
      </div>
      <div class="evcc-map-config-section">
        <div class="evcc-map-config-section-title">${this.t("map.furnished_align")}</div>
        <div class="evcc-map-config-adj-meta">${this.t("map.furnished_align_hint")}</div>
        <div class="evcc-map-nudge-pad">
          <div class="evcc-map-nudge-row">
            <button class="evcc-map-nudge-btn" data-action="furnished-art-nudge" data-dx="0" data-dy="-1" title="${this.t("map.nudge_up")}">↑</button>
          </div>
          <div class="evcc-map-nudge-row">
            <button class="evcc-map-nudge-btn" data-action="furnished-art-nudge" data-dx="-1" data-dy="0" title="${this.t("map.nudge_left")}">←</button>
            <button class="evcc-map-nudge-btn" data-action="furnished-art-nudge" data-dx="1" data-dy="0" title="${this.t("map.nudge_right")}">→</button>
          </div>
          <div class="evcc-map-nudge-row">
            <button class="evcc-map-nudge-btn" data-action="furnished-art-nudge" data-dx="0" data-dy="1" title="${this.t("map.nudge_down")}">↓</button>
          </div>
        </div>
        <div class="evcc-compose-tools">
          <button class="evcc-map-config-btn" data-action="furnished-art-scale" data-factor="0.9" title="${this.t("map.scale_shrink")}">${this.t("map.scale_minus")}</button>
          <button class="evcc-map-config-btn" data-action="furnished-art-scale" data-factor="1.111" title="${this.t("map.scale_grow")}">${this.t("map.scale_plus")}</button>
          <span class="evcc-map-config-adj-meta">${Math.round((Number(t.scale) || 1) * 100)}%</span>
        </div>
        <div class="evcc-map-furnished-rotate">
          <button class="evcc-map-config-btn" data-action="furnished-art-rotate" data-deg="-90" title="${this.t("map.rotate_left_90")}">↺ 90°</button>
          <button class="evcc-map-config-btn" data-action="furnished-art-rotate" data-deg="-1" title="${this.t("map.rotate_left_1")}">−1°</button>
          <button class="evcc-map-config-btn" data-action="furnished-art-rotate" data-deg="-0.1" title="${this.t("map.rotate_left_01")}">−0.1°</button>
          <span class="evcc-map-config-adj-meta evcc-map-furnished-rotate-readout">${(Number(t.rotation) || 0).toFixed(1)}°</span>
          <button class="evcc-map-config-btn" data-action="furnished-art-rotate" data-deg="0.1" title="${this.t("map.rotate_right_01")}">+0.1°</button>
          <button class="evcc-map-config-btn" data-action="furnished-art-rotate" data-deg="1" title="${this.t("map.rotate_right_1")}">+1°</button>
          <button class="evcc-map-config-btn" data-action="furnished-art-rotate" data-deg="90" title="${this.t("map.rotate_right_90")}">↻ 90°</button>
        </div>
        <div class="evcc-map-furnished-trim">
          <span class="evcc-map-config-adj-meta">${this.t("map.furnished_fine_trim")}</span>
          <input type="range" class="evcc-map-furnished-rotate-slider"
                 data-action="furnished-art-rotate-slider"
                 min="-15" max="15" step="0.1" value="0"
                 aria-label="${this.t("map.furnished_fine_trim_aria")}">
        </div>
        <div class="evcc-compose-tools">
          <button class="evcc-map-config-btn evcc-map-config-btn--primary" data-action="furnished-art-save" title="${this.t("map.furnished_save_align_title")}">${this.t("map.furnished_save_align")}</button>
        </div>
      </div>` : ""}
    `;
  };

  proto._renderComposerSelectedControls = function (state) {
    const id = state.composeSelectedId?.();
    if (id == null) return "";
    const draft = state.composeDraft?.() ?? [];
    const s = draft.find((x) => x.id === id);
    if (!s) return "";
    const grp = s.group ?? s.id;
    const groupSize = draft.filter((x) => (x.group ?? x.id) === grp).length;
    const merging = state.composeMergeFrom?.() === s.id;
    const totalShapes = draft.length;
    const moveScope = state.composeMoveScope?.() ?? "room";
    const step = state.composeStep?.() ?? 3;
    const mv = (dx, dy, glyph, label) => `
      <button class="evcc-map-nudge-btn" data-action="compose-move"
        data-dx="${dx}" data-dy="${dy}" title="${label}">${glyph}</button>`;
    const stepBtn = (n, label) => `
      <button class="evcc-map-config-btn${step === n ? " evcc-map-config-btn--primary" : ""}"
        data-action="compose-step" data-step="${n}">${label}</button>`;
    return `
      <div class="evcc-map-config-section">
        <div class="evcc-map-config-section-title">${this.t("map.compose_selected")} <em>${s.type}</em></div>
        <div class="evcc-compose-tools">
          ${stepBtn(1, this.t("map.compose_step_fine"))}${stepBtn(3, this.t("map.compose_step_med"))}${stepBtn(7, this.t("map.compose_step_coarse"))}
        </div>
        ${groupSize >= 2 ? `
        <div class="evcc-map-config-adj-meta">${this.t("map.compose_move_prompt")}</div>
        <div class="evcc-compose-tools">
          <button class="evcc-map-config-btn${moveScope === "room" ? " evcc-map-config-btn--primary" : ""}"
            data-action="compose-move-scope" data-scope="room" title="${this.t("map.compose_scope_room_title")}">${this.t("map.compose_scope_room")}</button>
          <button class="evcc-map-config-btn${moveScope === "piece" ? " evcc-map-config-btn--primary" : ""}"
            data-action="compose-move-scope" data-scope="piece" title="${this.t("map.compose_scope_piece_title")}">${this.t("map.compose_scope_piece")}</button>
        </div>` : ""}
        <div class="evcc-map-nudge-pad">
          <div class="evcc-map-nudge-row">${mv(0, -1, "↑", this.t("map.nudge_up"))}</div>
          <div class="evcc-map-nudge-row">${mv(-1, 0, "←", this.t("map.nudge_left"))}${mv(1, 0, "→", this.t("map.nudge_right"))}</div>
          <div class="evcc-map-nudge-row">${mv(0, 1, "↓", this.t("map.nudge_down"))}</div>
        </div>
        <div class="evcc-map-config-adj-meta">${this.t("map.compose_tap_to_drop")}</div>
        <div class="evcc-compose-tools">
          <button class="evcc-map-config-btn" data-action="compose-scale" data-factor="0.85" title="${this.t("map.scale_shrink")}">${this.t("map.scale_minus")}</button>
          <button class="evcc-map-config-btn" data-action="compose-scale" data-factor="1.18" title="${this.t("map.scale_grow")}">${this.t("map.scale_plus")}</button>
        </div>
        ${s.type === "rect" ? `
        <div class="evcc-compose-tools">
          <button class="evcc-map-config-btn" data-action="compose-resize" data-dim="w" data-delta="-1">${this.t("map.resize_w_minus")}</button>
          <button class="evcc-map-config-btn" data-action="compose-resize" data-dim="w" data-delta="1">${this.t("map.resize_w_plus")}</button>
          <button class="evcc-map-config-btn" data-action="compose-resize" data-dim="h" data-delta="-1">${this.t("map.resize_h_minus")}</button>
          <button class="evcc-map-config-btn" data-action="compose-resize" data-dim="h" data-delta="1">${this.t("map.resize_h_plus")}</button>
        </div>` : ""}
        ${s.type !== "circle" ? `
        <div class="evcc-compose-tools">
          <button class="evcc-map-config-btn" data-action="compose-rotate" data-deg="-15" title="${this.t("map.rotate_left")}">${this.t("map.rotate_ccw")}</button>
          <button class="evcc-map-config-btn" data-action="compose-rotate" data-deg="15" title="${this.t("map.rotate_right")}">${this.t("map.rotate_cw")}</button>
        </div>` : ""}
        <div class="evcc-compose-tools">
          ${merging
            ? `<button class="evcc-map-config-btn evcc-map-config-btn--primary" data-action="compose-merge-cancel" title="${this.t("map.compose_merge_stop_title")}">${this.t("map.compose_merge_cancel")}</button>`
            : `<button class="evcc-map-config-btn" data-action="compose-merge-start" ${totalShapes < 2 ? "disabled" : ""} title="${this.t("map.compose_merge_start_title")}">${this.t("map.compose_merge")}</button>`}
          ${groupSize >= 2 ? `<button class="evcc-map-config-btn" data-action="compose-split" title="${this.t("map.compose_split_title")}">${this.t("map.compose_split")}</button>` : ""}
        </div>
        ${groupSize >= 2 ? `
        <div class="evcc-compose-tools">
          <button class="evcc-map-config-btn${s.op === "subtract" ? " evcc-map-config-btn--primary" : ""}"
            data-action="compose-toggle-op"
            title="${s.op === "subtract" ? this.t("map.compose_cutout_on_title") : this.t("map.compose_cutout_off_title")}"
          >${s.op === "subtract" ? this.t("map.compose_cutout_on") : this.t("map.compose_cutout_off")}</button>
        </div>` : ""}
        <div class="evcc-compose-tools">
          <button class="evcc-map-config-btn" data-action="compose-deselect" title="${this.t("map.compose_done_title")}">${this.t("map.compose_done")}</button>
        </div>
      </div>
    `;
  };

  proto._renderComposerRoomAssign = function (state) {
    const id = state.composeSelectedId?.();
    if (id == null) return "";
    const draft = state.composeDraft?.() ?? [];
    const shape = draft.find((x) => x.id === id);
    if (!shape) return "";
    const rooms = state.getRoomsForActiveMap?.() ?? [];
    if (!rooms.length) {
      return `
        <div class="evcc-map-config-section evcc-map-config-section--hint">
          <p>${this.t("map.compose_no_rooms")}</p>
        </div>`;
    }
    const groupOf = (x) => x.group ?? x.id;
    const myGroup = groupOf(shape);
    const chips = rooms.map((room) => {
      const linkedHere   = shape.room_id != null && String(room.id) === String(shape.room_id);
      const takenByOther = !linkedHere && draft.some(
        (s) => groupOf(s) !== myGroup && s.room_id != null && String(s.room_id) === String(room.id),
      );
      let cls = "evcc-map-room-assign-chip";
      if (linkedHere)   cls += " evcc-map-room-assign-chip--linked";
      if (takenByOther) cls += " evcc-map-room-assign-chip--taken";
      return `
        <button class="${cls}" data-action="compose-assign-room"
          data-shape-id="${this.escapeHtml(String(shape.id))}"
          data-room-id="${this.escapeHtml(String(room.id))}"
          ${takenByOther ? "disabled" : ""}
          title="${takenByOther ? this.t("map.assign_taken_shape")
            : linkedHere ? this.t("map.assign_unlink") : this.t("map.assign_link_to", { name: this.escapeHtml(room.name) })}"
        >${this.escapeHtml(room.name)}${linkedHere ? " ✓" : ""}</button>`;
    }).join("");
    return `
      <div class="evcc-map-config-section">
        <div class="evcc-map-config-section-title">${this.t("map.link_to_room")}</div>
        <div class="evcc-map-room-assign-chips">${chips}</div>
      </div>`;
  };

  proto._renderVariantsSection = function (variants, summary, actionStatus, state) {
    const armedDelete = state?.mapVariantDeleteArmed?.() ?? null;
    const rows = _VARIANTS.map(({ key }) => {
      const uploaded   = variants[key];
      // Treat both the upload phase and the (much longer) analyze phase
      // as "busy" for this variant, so the button stays in a clear working
      // state through the whole 10-30s round-trip. Dropping the indicator
      // partway through the flow makes the slow analyze step read as a
      // silent no-op to the user.
      const isUploadBusy = actionStatus?.type === "upload" &&
                           actionStatus?.variant === key &&
                           actionStatus?.status === "busy";
      const isAnalyzeBusy = actionStatus?.type === "analyze" &&
                            actionStatus?.variant === key &&
                            actionStatus?.status === "busy";
      const isBusy = isUploadBusy || isAnalyzeBusy;
      const isError    = actionStatus?.type === "upload" &&
                         actionStatus?.variant === key &&
                         actionStatus?.status === "error";

      const statusText = uploaded
        ? `${uploaded.width} × ${uploaded.height}`
        : this.t("map.variant_not_uploaded");
      const statusCls  = uploaded
        ? "evcc-map-variant-status--ok"
        : "evcc-map-variant-status--missing";

      // Label flips between upload (network transfer) and analyze
      // (segmenter pipeline) so the user has some sense of what's happening.
      const buttonLabel = isUploadBusy ? this.t("map.uploading")
                        : isAnalyzeBusy ? this.t("map.analyzing_progress")
                        : this.t("map.upload");

      return `
        <div class="evcc-map-variant-row">
          <div class="evcc-map-variant-info">
            <span class="evcc-map-variant-label">${this.t(`map.variant_${key}_label`)}</span>
            <span class="evcc-map-variant-hint">${this.t(`map.variant_${key}_hint`)}</span>
          </div>
          <span class="evcc-map-variant-status ${statusCls}">${statusText}</span>
          ${isError
            ? `<span class="evcc-map-action-status evcc-map-action-status--error">
                 ${actionStatus.message ? this.escapeHtml(actionStatus.message) : this.t("map.upload_failed")}
               </span>`
            : ""}
          <button
            class="evcc-map-config-btn${isBusy ? " evcc-map-config-btn--busy" : ""}"
            data-action="upload-map-variant"
            data-variant="${key}"
            ${isBusy ? "disabled" : ""}
          >${buttonLabel}</button>
          ${uploaded ? (() => {
            const isArmed = armedDelete === key;
            const isDeleteBusy = actionStatus?.type === "delete" &&
                                 actionStatus?.variant === key &&
                                 actionStatus?.status === "busy";
            const btnLabel = isDeleteBusy ? this.t("map.deleting")
                           : isArmed ? this.t("map.confirm_delete")
                           : this.t("common.delete");
            const btnClass = "evcc-map-config-btn evcc-map-config-btn--danger"
                           + (isArmed ? " evcc-map-config-btn--confirm" : "")
                           + (isDeleteBusy ? " evcc-map-config-btn--busy" : "");
            return `
              <button
                class="${btnClass}"
                data-action="delete-map-variant"
                data-variant="${key}"
                title="${isArmed
                  ? this.t("map.delete_variant_confirm_title")
                  : this.t("map.delete_variant_title")}"
                ${isDeleteBusy ? "disabled" : ""}
              >${btnLabel}</button>
              ${isArmed ? `
                <button
                  class="evcc-map-config-btn"
                  data-action="cancel-delete-map-variant"
                  title="${this.t("map.cancel_delete_title")}"
                >${this.t("common.cancel")}</button>
              ` : ""}
            `;
          })() : ""}
          <!-- File input is created in-memory by the click binding (bindings/map.js).
               Keeping it out of the DOM avoids re-render orphan issues when HA pushes
               state updates between picker open and file selection. -->
        </div>
      `;
    }).join("");

    const segCount     = summary.segment_count ?? summary.count ?? 0;
    const adjCount     = summary.adjusted_count ?? 0;
    const analyzeBusy  = actionStatus?.type === "analyze" &&
                         actionStatus?.status === "busy";
    const analyzeError = actionStatus?.type === "analyze" &&
                         actionStatus?.status === "error";
    const analyzedAt   = this._formatAnalyzedAt(summary.analyzed_at);

    return `
      <div class="evcc-map-config-section">
        <div class="evcc-map-config-section-title">${this.t("map.image_variants")}</div>
        ${rows}
        <div class="evcc-map-config-analyze-row">
          <span class="evcc-map-config-seg-count">
            ${analyzeError
              ? `<span class="evcc-map-action-status evcc-map-action-status--error">
                   ${actionStatus.message ? this.escapeHtml(actionStatus.message) : this.t("map.analysis_failed")}
                 </span>`
              : segCount > 0
                ? `${this.t("map.seg_count", { count: segCount })}${adjCount > 0 ? this.t("map.seg_adjusted", { count: adjCount }) : ""}${analyzedAt ? ` · ${analyzedAt}` : ""}`
                : this.t("map.no_segments")}
          </span>
          <button
            class="evcc-map-config-btn evcc-map-config-btn--primary${analyzeBusy ? " evcc-map-config-btn--busy" : ""}"
            data-action="analyze-map"
            ${analyzeBusy ? "disabled" : ""}
          >${analyzeBusy ? this.t("map.analyzing") : segCount > 0 ? this.t("map.reanalyse") : this.t("map.analyse_map")}</button>
        </div>
      </div>
    `;
  };

  /* =========================================================
     SEGMENT ADJUSTMENT SECTION
     ========================================================= */

  proto._renderSegmentAdjustSection = function (seg, state) {
    const label = seg.name ?? seg.label ?? this.t("map.segment_fallback", { id: seg.segment_id });
    const segIdStr = this.escapeHtml(String(seg.segment_id));

    return `
      ${this._renderTranslationSection(seg, state, segIdStr, label)}
      ${this._renderEdgeSection(seg, state, segIdStr)}
      ${this._renderVertexSection(seg, state, segIdStr)}
      ${this._renderRoomAssignSection(seg, state)}
    `;
  };

  proto._renderTranslationSection = function (seg, state, segIdStr, label) {
    const step = state.mapNudgeStep();
    const raw  = seg.translation_offset;
    const ox   = Array.isArray(raw) ? (raw[0] ?? 0) : (raw?.x ?? 0);
    const oy   = Array.isArray(raw) ? (raw[1] ?? 0) : (raw?.y ?? 0);

    return `
      <div class="evcc-map-config-section">
        <div class="evcc-map-config-section-title">
          ${this.t("map.adjusting")} <em>${this.escapeHtml(label)}</em>
        </div>
        <div class="evcc-map-config-adj-meta">${this.t("map.offset_label", { x: ox, y: oy })}</div>
        <div class="evcc-map-nudge-pad">
          <div class="evcc-map-nudge-row">
            <button class="evcc-map-nudge-btn" data-action="nudge-segment"
              data-segment-id="${segIdStr}" data-dx="0" data-dy="-${step.y}" title="${this.t("map.nudge_up")}">↑</button>
          </div>
          <div class="evcc-map-nudge-row">
            <button class="evcc-map-nudge-btn" data-action="nudge-segment"
              data-segment-id="${segIdStr}" data-dx="-${step.x}" data-dy="0" title="${this.t("map.nudge_left")}">←</button>
            <button class="evcc-map-nudge-btn evcc-map-nudge-btn--reset"
              data-action="reset-segment-adjustment"
              data-segment-id="${segIdStr}" title="${this.t("map.reset_translation")}">○</button>
            <button class="evcc-map-nudge-btn" data-action="nudge-segment"
              data-segment-id="${segIdStr}" data-dx="${step.x}" data-dy="0" title="${this.t("map.nudge_right")}">→</button>
          </div>
          <div class="evcc-map-nudge-row">
            <button class="evcc-map-nudge-btn" data-action="nudge-segment"
              data-segment-id="${segIdStr}" data-dx="0" data-dy="${step.y}" title="${this.t("map.nudge_down")}">↓</button>
          </div>
        </div>
      </div>
    `;
  };

  proto._renderEdgeSection = function (seg, state, segIdStr) {
    const step = state.mapNudgeStep();
    const ea   = seg.edge_adjustment ?? {};
    const edges = [
      { key: "top",    label: this.t("map.edge_top"),    stepKey: "y" },
      { key: "bottom", label: this.t("map.edge_bottom"), stepKey: "y" },
      { key: "left",   label: this.t("map.edge_left"),   stepKey: "x" },
      { key: "right",  label: this.t("map.edge_right"),  stepKey: "x" },
    ];

    const rows = edges.map(({ key, label, stepKey }) => {
      const cur = ea[key] ?? 0;
      const s   = step[stepKey];
      return `
        <div class="evcc-map-edge-row">
          <span class="evcc-map-edge-label">${label}</span>
          <button class="evcc-map-nudge-btn evcc-map-nudge-btn--edge"
            data-action="adjust-edge" data-segment-id="${segIdStr}"
            data-edge="${key}" data-delta="-${s}" title="${this.t("map.edge_contract", { edge: label })}">−</button>
          <span class="evcc-map-edge-val">${cur > 0 ? "+" : ""}${cur}</span>
          <button class="evcc-map-nudge-btn evcc-map-nudge-btn--edge"
            data-action="adjust-edge" data-segment-id="${segIdStr}"
            data-edge="${key}" data-delta="${s}" title="${this.t("map.edge_expand", { edge: label })}">+</button>
        </div>
      `;
    }).join("");

    return `
      <div class="evcc-map-config-section">
        <div class="evcc-map-config-section-title">${this.t("map.edges")}</div>
        <div class="evcc-map-edge-grid">${rows}</div>
      </div>
    `;
  };

  proto._renderVertexSection = function (seg, state, segIdStr) {
    const vertices    = seg.polygon_pct ?? seg.polygon_pixel ?? [];
    const vertexAdj   = seg.vertex_adjustment ?? [];
    const selectedIdx = state.configSelectedVertexIndex?.();
    const step        = state.mapNudgeStep();

    if (vertices.length === 0) return "";

    const adjByIndex = {};
    vertexAdj.forEach((v) => { adjByIndex[v.index] = v; });

    const chips = vertices.map((_, i) => {
      const isSelected = selectedIdx === i;
      const hasAdj     = adjByIndex[i] != null;
      let cls = "evcc-map-vertex-chip";
      if (isSelected) cls += " evcc-map-vertex-chip--selected";
      if (hasAdj)     cls += " evcc-map-vertex-chip--adjusted";
      return `<button class="${cls}" data-action="select-vertex"
        data-segment-id="${segIdStr}" data-vertex-index="${i}">${i}</button>`;
    }).join("");

    let nudgePad = "";
    if (selectedIdx != null && selectedIdx < vertices.length) {
      const cur = adjByIndex[selectedIdx];
      const vdx = cur?.delta_x ?? 0;
      const vdy = cur?.delta_y ?? 0;
      nudgePad = `
        <div class="evcc-map-config-adj-meta">V${selectedIdx}: ${vdx >= 0 ? "+" : ""}${vdx}, ${vdy >= 0 ? "+" : ""}${vdy} px</div>
        <div class="evcc-map-nudge-pad">
          <div class="evcc-map-nudge-row">
            <button class="evcc-map-nudge-btn" data-action="nudge-vertex"
              data-segment-id="${segIdStr}" data-vertex-index="${selectedIdx}"
              data-dx="0" data-dy="-${step.y}" title="${this.t("map.nudge_vertex_up")}">↑</button>
          </div>
          <div class="evcc-map-nudge-row">
            <button class="evcc-map-nudge-btn" data-action="nudge-vertex"
              data-segment-id="${segIdStr}" data-vertex-index="${selectedIdx}"
              data-dx="-${step.x}" data-dy="0" title="${this.t("map.nudge_vertex_left")}">←</button>
            <button class="evcc-map-nudge-btn evcc-map-nudge-btn--reset"
              data-action="reset-vertex"
              data-segment-id="${segIdStr}" data-vertex-index="${selectedIdx}"
              title="${this.t("map.reset_vertex")}">○</button>
            <button class="evcc-map-nudge-btn" data-action="nudge-vertex"
              data-segment-id="${segIdStr}" data-vertex-index="${selectedIdx}"
              data-dx="${step.x}" data-dy="0" title="${this.t("map.nudge_vertex_right")}">→</button>
          </div>
          <div class="evcc-map-nudge-row">
            <button class="evcc-map-nudge-btn" data-action="nudge-vertex"
              data-segment-id="${segIdStr}" data-vertex-index="${selectedIdx}"
              data-dx="0" data-dy="${step.y}" title="${this.t("map.nudge_vertex_down")}">↓</button>
          </div>
        </div>
      `;
    }

    return `
      <div class="evcc-map-config-section">
        <div class="evcc-map-config-section-title">${this.t("map.vertices")}</div>
        <div class="evcc-map-vertex-chips">${chips}</div>
        ${nudgePad}
      </div>
    `;
  };

  /* =========================================================
     ROOM ASSIGNMENT SECTION
     ========================================================= */

  proto._renderRoomAssignSection = function (seg, state) {
    const rooms        = state.getRoomsForActiveMap?.() ?? [];
    const linkedRoomId = state.roomIdForSegment(seg.segment_id);
    const segIdStr     = this.escapeHtml(String(seg.segment_id));

    if (rooms.length === 0) return "";

    const chips = rooms.map((room) => {
      const isLinkedHere = linkedRoomId != null &&
                           String(room.id) === String(linkedRoomId);
      const takenByOther = !isLinkedHere &&
                           state.segmentIdForRoom(room.id) != null;

      let cls = "evcc-map-room-assign-chip";
      if (isLinkedHere) cls += " evcc-map-room-assign-chip--linked";
      if (takenByOther) cls += " evcc-map-room-assign-chip--taken";

      return `
        <button
          class="${cls}"
          data-action="assign-segment-room"
          data-segment-id="${segIdStr}"
          data-room-id="${this.escapeHtml(String(room.id))}"
          ${takenByOther ? "disabled" : ""}
          title="${takenByOther
            ? this.t("map.assign_taken_segment")
            : isLinkedHere
              ? this.t("map.assign_unlink_name", { name: this.escapeHtml(room.name) })
              : this.t("map.assign_link_to", { name: this.escapeHtml(room.name) })}"
        >${this.escapeHtml(room.name)}${isLinkedHere ? " ✓" : ""}</button>
      `;
    }).join("");

    return `
      <div class="evcc-map-config-section">
        <div class="evcc-map-config-section-title">${this.t("map.link_to_room")}</div>
        <div class="evcc-map-room-assign-chips">${chips}</div>
      </div>
    `;
  };
}
