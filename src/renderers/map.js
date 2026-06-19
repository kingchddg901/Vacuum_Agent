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

function _polygonCentroid(points) {
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

const _SEGMENT_COLORS = [
  "#00e5ff", "#ff6b35", "#a3e635", "#e879f9",
  "#fbbf24", "#a78bfa", "#fb7185", "#34d399",
  "#60a5fa", "#f472b6", "#4ade80", "#f97316",
];

const _VARIANTS = [
  { key: "dark",    label: "Dark",    hint: "primary — clearest room colours" },
  { key: "light",   label: "Light",   hint: "assist — wall detection" },
  { key: "default", label: "Default", hint: "fallback" },
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
      const title = wantVa ? "Rendering the map…" : "No map image available.";
      const hint = wantVa
        ? "Drawing the map from the device's room data — one moment."
        : hasLiveImage
          ? "The live map appears once the robot has one — start a clean, or open the robot's app to build its map."
          : isCustom
            ? "Open Map Configuration to upload this layout's backdrop, then draw + save its rooms."
            : "Upload and analyze a map image to enable map view.";
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
    // Live-map rotation is display only and applies ONLY to the live image (no
    // segment overlay to keep aligned); CV/custom maps stay at 0.
    const rot          = (hasLiveImage && !wantVa) ? (state.mapRotation?.() ?? 0) : 0;
    // Ad-hoc zone clean: only over a live-map backdrop (you draw on that image),
    // only when the provider supports it, and only at rotation 0 for now — a
    // rotated map letterboxes on the swapped axis (Wave 2 handles rotation).
    const canZone   = state.canDrawZone?.() ?? false;
    // zoneMode is gated by canZone so the overlay, action bar, and container
    // class can never be live while the gate is false (e.g. after a rotate).
    const zoneMode   = canZone && (state.zoneDrawMode?.() ?? false);
    const zoneDrafts = zoneMode ? (state.zoneDrafts?.() ?? []) : [];
    const zoneCount  = zoneDrafts.length;
    const zoneMax    = state.zoneMax?.() ?? 10;
    // map_state_source overlay layers (no-go/walls/path/robot/etc.) render over any
    // GRID-frame backdrop their normalized coords align to: the live device image OR
    // the VA-rendered canvas (Wave 3c overlays; Wave 1 self-render).
    const deviceOverlays = state.overlaysAligned?.() ?? false;
    return `
      <div class="evcc-map-view">
        <div class="evcc-map-container${zoneMode ? " evcc-map-container--zone" : ""}">

          <div class="evcc-map-layers" style="transform:translate(${tx}px,${ty}px) scale(${zoom});transform-origin:0 0">
            <!-- Rotation turns this whole content layer (image + polygons + labels
                 + mascot) together so overlays stay aligned at any 90° step; zoom/pan
                 stays on .evcc-map-layers above. --evcc-map-rotation lets labels +
                 mascot counter-rotate upright (see styles/map.js). -->
            <div class="evcc-map-content-rotator" style="transform:rotate(${rot}deg);--evcc-map-rotation:${rot}deg">
            ${vaActive
              ? `<canvas class="evcc-map-image evcc-map-render-canvas" data-render-version="${this.escapeHtml(String(state.mapRenderVersion?.() ?? ""))}"></canvas>`
              : (imageUrl
                  ? `<img class="evcc-map-image" src="${this.escapeHtml(imageUrl)}" alt="Floor plan" draggable="false">`
                  : "")}
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
                const label  = room?.name ?? seg.name ?? seg.label ?? `Segment ${seg.segment_id}`;
                const hint   = room ? "Tap to queue · Double-tap to configure" : "Tap to queue";
                return this._renderMapSegmentPolygon(seg, selectedIds, i, label, hint);
              }).join("")}
              ${typeof this._renderFloorTexturePolygon === "function"
                ? segments.map((seg, i) =>
                    this._renderFloorTexturePolygon(seg, segFloorTypes[i])
                  ).join("")
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
              return `<div class="evcc-map-label${isSel ? " evcc-map-label--selected" : ""}" style="left:${lx}%;top:${ly}%">
                ${isSel ? `<span class="evcc-map-label-order">${selOrder + 1}</span>` : ""}
                <span class="evcc-map-label-name">${this.escapeHtml(label)}</span>
              </div>`;
            }).join("") : ""}
            ${deviceOverlays ? this._renderDeviceOverlayHtml(state) : ""}
            </div>
            ${zoneMode ? `
              ${zoneDrafts.map((d, i) => `<div class="evcc-zone-rect" style="left:${Math.min(d.x, d.x + d.w)}%;top:${Math.min(d.y, d.y + d.h)}%;width:${Math.abs(d.w)}%;height:${Math.abs(d.h)}%"><span class="evcc-zone-rect-num">${i + 1}</span></div>`).join("")}
              <div class="evcc-zone-draft" style="display:none"></div>` : ""}

          </div>

          <div class="evcc-map-tooltip" aria-hidden="true"></div>

          <!-- Zoom controls. Absolute-positioned over the map. CSS-styled
               as a small floating toolbar; see styles/map.js -->
          <div class="evcc-map-zoom-toolbar" aria-label="Map zoom controls">
            <button class="evcc-map-zoom-btn" data-action="map-zoom-out"
                    title="Zoom out" aria-label="Zoom out">−</button>
            <button class="evcc-map-zoom-btn" data-action="map-zoom-fit"
                    title="Fit map to screen" aria-label="Fit to screen">⤢</button>
            <button class="evcc-map-zoom-btn" data-action="map-zoom-in"
                    title="Zoom in" aria-label="Zoom in">+</button>
            ${hasLiveImage ? `
            <button class="evcc-map-zoom-btn" data-action="map-rotate"
                    title="Rotate map 90°" aria-label="Rotate map 90 degrees">↻</button>` : ""}
            ${(state.supportsVaRender?.() ?? false) ? `
            <button class="evcc-map-zoom-btn${(state.useVaRender?.() ?? false) ? " evcc-map-zoom-btn--on" : ""}"
                    data-action="toggle-va-render"
                    title="Toggle VA-rendered map" aria-label="Toggle VA-rendered map">▦</button>` : ""}
            ${canZone ? `
            <button class="evcc-map-zoom-btn${zoneMode ? " evcc-map-zoom-btn--on" : ""}"
                    data-action="toggle-zone-draw"
                    title="Draw a zone to clean" aria-label="Draw a zone to clean">▢</button>` : ""}
            <span class="evcc-map-zoom-readout"
                  aria-label="Current zoom level">${Math.round(zoom * 100)}%</span>
          </div>

        </div>

      </div>
    `;
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
    return out;
  };

  proto._renderDeviceOverlayHtml = function (state) {
    const mss = state.mapOverlayData?.() ?? state.mapStateSource?.();
    if (!mss || !mss.present) return "";
    const vis = (layer) => state.isOverlayVisible?.(layer) ?? false;
    const { tx, ty } = this._overlayTransform(state);
    const f = (v) => v.toFixed(2);
    let out = "";

    if (vis("robot") && Array.isArray(mss.robot_anchor) && mss.robot_anchor.length === 2) {
      const [x, y] = mss.robot_anchor;
      const h = Number(mss.robot_heading ?? 0);
      out += `<div class="evcc-map-ov-robot" style="left:${f(tx(x))}%;top:${f(ty(y))}%">`
           + `<span class="evcc-map-ov-robot-arrow" style="transform:rotate(${h}deg)"></span></div>`;
    }
    if (vis("dock") && Array.isArray(mss.dock_anchor) && mss.dock_anchor.length === 2) {
      const [x, y] = mss.dock_anchor;
      out += `<div class="evcc-map-ov-dock" style="left:${f(tx(x))}%;top:${f(ty(y))}%" title="Dock"></div>`;
    }
    if (vis("obstacles")) {
      for (const o of (mss.obstacles || [])) {
        if (!o || !Array.isArray(o.pos) || o.pos.length !== 2) continue;
        const cls = o.has_photo ? " evcc-map-ov-obstacle--photo" : "";
        out += `<div class="evcc-map-ov-obstacle${cls}" style="left:${f(tx(o.pos[0]))}%;top:${f(ty(o.pos[1]))}%" `
             + `title="${this.escapeHtml(String(o.type ?? "obstacle"))}"></div>`;
      }
    }
    if (vis("room_area")) {
      for (const r of (mss.rooms || [])) {
        if (r.area_m2 == null || !Array.isArray(r.bbox) || r.bbox.length !== 4) continue;
        const [x0, y0, x1, y1] = r.bbox;
        out += `<div class="evcc-map-ov-area" style="left:${f(tx((x0 + x1) / 2))}%;top:${f(ty((y0 + y1) / 2))}%">`
             + `${this.escapeHtml(String(r.area_m2))} m²</div>`;
      }
    }
    return out;
  };

  /* =========================================================
     MAP LAYERS PANEL (right column; Wave 3c visibility toggles)
     ========================================================= */

  proto._renderMapLayersPanel = function (state) {
    const vis = state.mapOverlayVisibility?.() ?? {};
    const live = state.isLiveImageDisplayed?.() ?? false;
    const LAYERS = [
      { key: "current_room", label: "Current room" },
      { key: "robot",        label: "Robot + heading" },
      { key: "dock",         label: "Dock" },
      { key: "room_area",    label: "Room area (m²)" },
      { key: "no_go",        label: "No-go zones" },
      { key: "no_mop",       label: "No-mop zones" },
      { key: "walls",        label: "Virtual walls" },
      { key: "zones",        label: "Saved zones" },
      { key: "path",         label: "Cleaning path" },
      { key: "obstacles",    label: "Obstacles" },
    ];
    return `
      <div class="evcc-map-layers-panel">
        <div class="evcc-map-layers-title">Map Layers</div>
        ${live ? "" : `<div class="evcc-map-layers-hint">Overlays appear on the live-map backdrop.</div>`}
        <div class="evcc-map-layers-list">
          ${LAYERS.map((l) => `
            <label class="evcc-map-layers-row">
              <input type="checkbox" data-action="toggle-map-overlay" data-layer="${l.key}"${vis[l.key] ? " checked" : ""}>
              <span>${this.escapeHtml(l.label)}</span>
            </label>`).join("")}
        </div>
      </div>`;
  };

  /* =========================================================
     ZONE-CLEAN PANEL (rendered in the right column, under Run Profiles)
     ========================================================= */

  proto._renderZonePanel = function (state, zoneDrafts, zoneCount, zoneMax) {
    const esc = (s) => this.escapeHtml(String(s));
    const settingEntities = state.settingEntities?.() ?? {};

    // The vacuum's setting selects, in display order. Each is rendered live from
    // the real provider entity (current value + options); changing it calls
    // select.select_option — a zone clean runs off these current settings.
    const SETTINGS = [
      { key: "fan_speed",       label: "Suction" },
      { key: "clean_mode",      label: "Mode" },
      { key: "clean_intensity", label: "Intensity" },
      { key: "water_level",     label: "Water" },
    ];
    const settingRows = SETTINGS.map(({ key, label }) => {
      const eid = settingEntities[key];
      if (!eid) return "";
      const ent = state.entity?.(eid);
      const opts = ent?.attributes?.options ?? [];
      if (!ent || !opts.length) return "";
      const cur = ent.state;
      return `
        <label class="evcc-zone-setting">
          <span class="evcc-zone-setting-label">${esc(label)}</span>
          <select class="evcc-zone-setting-select" data-action="zone-setting"
                  data-entity-id="${esc(eid)}">
            ${opts.map((o) => `<option value="${esc(o)}"${o === cur ? " selected" : ""}>${esc(o)}</option>`).join("")}
          </select>
        </label>`;
    }).join("");

    const zoneList = zoneDrafts.map((_, i) => `
      <li class="evcc-zone-list-item">
        <span class="evcc-zone-list-num">${i + 1}</span>
        <button class="evcc-zone-list-del" data-action="zone-remove" data-zone-index="${i}"
                title="Remove zone ${i + 1}" aria-label="Remove zone ${i + 1}">✕</button>
      </li>`).join("");

    return `
      <div class="evcc-zone-panel" role="group" aria-label="Zone clean">
        <div class="evcc-zone-panel-title">Zone clean</div>
        ${settingRows ? `
        <div class="evcc-zone-panel-section">
          <div class="evcc-zone-panel-section-title">Settings
            <span class="evcc-zone-panel-note">apply to the whole clean</span></div>
          ${settingRows}
        </div>` : ""}
        <div class="evcc-zone-panel-section">
          <div class="evcc-zone-panel-section-title">Zones
            <span class="evcc-zone-panel-note">${zoneCount}/${zoneMax}</span></div>
          ${zoneCount
            ? `<ul class="evcc-zone-list">${zoneList}</ul>`
            : `<div class="evcc-zone-panel-empty">Drag a box on the map to add a zone.</div>`}
        </div>
        <div class="evcc-zone-panel-actions">
          <button class="evcc-zone-bar-btn evcc-zone-bar-btn--primary"
                  data-action="zone-clean-confirm"${zoneCount ? "" : " disabled"}>${
            zoneCount > 1 ? `Clean ${zoneCount} zones` : "Clean zone"
          }</button>
          ${zoneCount ? `<button class="evcc-zone-bar-btn" data-action="zone-clear">Clear</button>` : ""}
          <button class="evcc-zone-bar-btn" data-action="zone-clean-cancel">Cancel</button>
        </div>
      </div>`;
  };

  /* =========================================================
     SEGMENT POLYGON
     ========================================================= */

  proto._renderMapSegmentPolygon = function (seg, selectedIds, segIndex, label, hint) {
    const polygon = seg.polygon_pct;
    if (!Array.isArray(polygon) || polygon.length < 3) return "";

    const isSelected = selectedIds.has(String(seg.segment_id));
    const color = _SEGMENT_COLORS[segIndex % _SEGMENT_COLORS.length];
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

    const isAtDock = (vacuumStatus === "docked" || vacuumStatus === "idle");
    if (isAtDock) {
      const dockRoom = rooms.find((r) => r.isDockRoom);
      targetSeg = _segForRoom(dockRoom?.id);
    }

    if (!targetSeg) {
      const progress = state.dashboardJobProgress?.();
      // Prefer the dwell-debounced live room (the room the robot is physically in,
      // incl. transit rooms, committed only after sustained dwell — display only,
      // separate from the job rollover). Fall back to the backend-computed
      // position_room_id, then current_room_id (next queued room).
      const currentRoomId = state.mascotDwelledRoomId?.()
        ?? progress?.position_room_id ?? progress?.current_room_id;
      targetSeg = _segForRoom(currentRoomId);
    }

    if (!targetSeg) {
      targetSeg = allSegments[0] ?? null;
    }

    if (!targetSeg) return "";

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

    const pose     = _vacuumStateToPose(vacuumStatus ?? "");
    const isDocked = pose === "curled";
    const animal   = state.mapAnimalSelection?.() ?? "cat";
    const scale    = state.mapAnimalScale?.()     ?? 1.0;
    // Battery state is an auxiliary visual signal orthogonal to pose. The
    // five-band resolution (charging/good/mid/warn/low) lives in
    // state.batteryState(); the animal renders the corresponding eye color
    // via :host([battery-state="X"]) rules, plus a charging pulse.
    const batteryState = state.batteryState?.() ?? "good";

    // Anchor key matches the lookup key — so dragging the DOCKED mascot writes
    // the shared "dock" spot, while dragging it mid-clean writes the per-room
    // anchor as before.
    const anchorKey = lookupKey;

    const W = Math.round(64 * scale);
    const H = Math.round(44 * scale);

    return `<div
      class="evcc-map-animal${isDocked ? " evcc-map-animal--pulse" : ""}"
      style="left:${pct_x}%;top:${pct_y}%;width:${W}px;height:${H}px"
      data-action="map-dot-click"
      data-anchor-key="${this.escapeHtml(anchorKey)}"
      title="${isAtDock ? "Drag to set the mascot's docked home spot" : "Drag to reposition"}"
    ><animal-svg animal="${this.escapeHtml(animal)}" pose="${this.escapeHtml(pose)}" width="${W}px" height="${H}px" battery-state="${this.escapeHtml(batteryState)}"></animal-svg></div>`;
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
        ?? `Segment ${seg.segment_id}`;
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

    // Config mode shares the same zoom state as the rooms view — same
    // bindings drive it, same toolbar reflects it. The .evcc-map-layers
    // wrapper here mirrors the rooms-view structure so the CSS
    // transform on it scales both the image and the polygon SVG
    // together.
    const zoom = state.mapZoom?.() ?? 1;
    const tx   = state.mapTranslateX?.() ?? 0;
    const ty   = state.mapTranslateY?.() ?? 0;

    return `
      <div class="evcc-map-config-view">

        <div class="evcc-map-config-header">
          <button class="evcc-map-config-back" data-action="map-config-back" aria-label="Back to rooms">
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <polyline points="10,3 4,8 10,13"/>
            </svg>
            Rooms
          </button>
          <span class="evcc-map-config-title">Map Configuration</span>
        </div>

        <div class="evcc-map-config-body">

          <div class="evcc-map-container evcc-map-container--config">
            ${imageUrl
              ? `<div class="evcc-map-layers" style="transform:translate(${tx}px,${ty}px) scale(${zoom});transform-origin:0 0">
                   <img class="evcc-map-image${isCustom && !state.isLiveBackdropActive?.() ? " evcc-map-image--fill" : ""}" src="${this.escapeHtml(imageUrl)}" alt="Floor plan" draggable="false">
                   <svg class="evcc-map-svg" viewBox="0 0 100 100" preserveAspectRatio="none">
                     ${isCustom
                       ? this._renderComposerShapes(state)
                       : segments.map((seg, i) => {
                           const isThis = String(seg.segment_id) === String(selectedId ?? "");
                           return this._renderConfigPolygon(seg, selectedId, i, isThis ? (state.configSelectedVertexIndex?.() ?? null) : null, zoom);
                         }).join("")}
                   </svg>
                 </div>
                 <div class="evcc-map-zoom-toolbar" aria-label="Map zoom controls">
                   <button class="evcc-map-zoom-btn" data-action="map-zoom-out"
                           title="Zoom out" aria-label="Zoom out">−</button>
                   <button class="evcc-map-zoom-btn" data-action="map-zoom-fit"
                           title="Fit map to screen" aria-label="Fit to screen">⤢</button>
                   <button class="evcc-map-zoom-btn" data-action="map-zoom-in"
                           title="Zoom in" aria-label="Zoom in">+</button>
                   <span class="evcc-map-zoom-readout"
                         aria-label="Current zoom level">${Math.round(zoom * 100)}%</span>
                 </div>`
              : `<div class="evcc-map-unavailable">
                   <p>No map image uploaded yet.</p>
                 </div>`}
          </div>

          <div class="evcc-map-config-side-panel">
            ${isCustom
              ? this._renderComposerToolbar(state)
              : (selectedSeg
                ? this._renderSegmentAdjustSection(selectedSeg, state)
                : `<div class="evcc-map-config-section evcc-map-config-section--hint">
                     <p>Click a segment on the map to adjust it.</p>
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

  proto._renderConfigPolygon = function (seg, selectedId, segIndex, selectedVertexIdx, zoom = 1) {
    const polygon = seg.polygon_pct;
    if (!Array.isArray(polygon) || polygon.length < 3) return "";

    const isSelected = String(seg.segment_id) === String(selectedId ?? "");
    const color = _SEGMENT_COLORS[segIndex % _SEGMENT_COLORS.length];
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

  function _formatAnalyzedAt(isoStr) {
    if (!isoStr) return null;
    const d = new Date(isoStr);
    if (isNaN(d)) return null;
    const diffMs  = Date.now() - d.getTime();
    const diffMin = Math.floor(diffMs / 60000);
    if (diffMin < 1)  return "just now";
    if (diffMin < 60) return `${diffMin}m ago`;
    const diffH = Math.floor(diffMin / 60);
    if (diffH < 24)   return `${diffH}h ago`;
    const diffD = Math.floor(diffH / 24);
    if (diffD < 14)   return `${diffD}d ago`;
    return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
  }

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
        title="Detect rooms automatically from the map image">Auto (CV)</button>` : "";
    // The live-pinned layout is represented by the dedicated "Live map" chip below,
    // not as a regular named layout chip — filter it out here to avoid a duplicate.
    const layoutChips = layouts
      .filter((l) => l.backdrop_source !== "live")
      .map((l) => `
      <button class="evcc-map-mode-btn${mode === "custom" && String(l.id) === String(activeId) ? " evcc-map-mode-btn--active" : ""}"
        data-action="set-active-custom-layout" data-layout-id="${esc(l.id)}"
        title="Custom layout: ${esc(l.name)}">${esc(l.name)}</button>`).join("");
    // "Live map" chip — only when a live-map entity is available. Selects (or creates)
    // the layout pinned to the live backdrop, so the composer draws rooms straight over
    // the live camera/image. Active when that layout is current.
    const hasLive = Boolean(state.liveMapImageEntity?.());
    const liveActive = mode === "custom" && state.activeCustomLayout?.()?.backdrop_source === "live";
    const liveChip = hasLive ? `
      <button class="evcc-map-mode-btn${liveActive ? " evcc-map-mode-btn--active" : ""}"
        data-action="select-or-create-live-layout"
        title="Draw rooms over your vacuum's live map">Live map</button>` : "";
    const newChip = `
      <button class="evcc-map-mode-btn" data-action="open-new-layout"
        title="Add a custom layout (its own backdrop + rooms)">＋ New</button>`;

    return `
      <div class="evcc-map-config-section">
        <div class="evcc-map-config-section-title">Segmentation</div>
        <div class="evcc-map-mode-toggle">
          ${liveChip}${cvChip}${layoutChips}${newChip}
        </div>
        ${!cvOk ? `
        <div class="evcc-map-cv-unavailable">
          <strong>Auto (CV)</strong> map segmentation needs optional packages
          (${esc(cvMissingText)}) that aren't installed in this Home Assistant.
          Use <strong>Live map</strong>, a <strong>custom layout</strong>, or manual
          bounds instead — see the
          <a href="https://kingchddg901.github.io/Vacuum_Agent/docs/user-guide/16-making-your-own-maps/" target="_blank" rel="noopener">map setup guide</a>.
        </div>` : ""}
        ${editing ? `
        <div class="evcc-compose-tools">
          <input type="text" class="evcc-map-config-input" data-layout-field="name"
            value="${esc(draftName)}" placeholder="Layout name" />
          <button class="evcc-map-config-btn evcc-map-config-btn--primary"
            data-action="${editMode === "rename" ? "rename-layout-save" : "create-layout-save"}"
          >${editMode === "rename" ? "Save" : "Create"}</button>
          <button class="evcc-map-config-btn" data-action="cancel-layout-editor">Cancel</button>
        </div>` : ""}
        ${mode === "custom" && activeId ? `
        <div class="evcc-compose-tools">
          <button class="evcc-map-config-btn" data-action="open-rename-layout">Rename</button>
          <button class="evcc-map-config-btn evcc-map-config-btn--danger" data-action="delete-layout">Delete layout</button>
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
    const statusText = custom ? `${custom.width} × ${custom.height}` : "no backdrop yet";
    const statusCls  = custom
      ? "evcc-map-variant-status--ok"
      : "evcc-map-variant-status--missing";

    return `
      <div class="evcc-map-config-section">
        <div class="evcc-map-config-section-title">Custom backdrop</div>
        <div class="evcc-map-variant-row">
          <div class="evcc-map-variant-info">
            <span class="evcc-map-variant-label">Backdrop image</span>
            <span class="evcc-map-variant-hint">any map picture — drawn on, never auto-segmented</span>
          </div>
          <span class="evcc-map-variant-status ${statusCls}">${statusText}</span>
          ${isError
            ? `<span class="evcc-map-action-status evcc-map-action-status--error">${this.escapeHtml(actionStatus.message ?? "Upload failed")}</span>`
            : ""}
          <button
            class="evcc-map-config-btn${isBusy ? " evcc-map-config-btn--busy" : ""}"
            data-action="upload-map-variant"
            data-variant="${this.escapeHtml(variantKey)}"
            ${isBusy ? "disabled" : ""}
          >${isBusy ? "Uploading…" : custom ? "Replace" : "Upload"}</button>
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
        <div class="evcc-map-config-section-title">Compose rooms</div>
        <div class="evcc-compose-tools">
          <button class="evcc-map-config-btn" data-action="compose-add" data-shape-type="rect">＋ Rectangle</button>
          <button class="evcc-map-config-btn" data-action="compose-add" data-shape-type="circle">＋ Circle</button>
        </div>
        <div class="evcc-map-config-adj-meta">${count} shape${count === 1 ? "" : "s"}${hasSel ? "" : (count ? " · tap one to edit" : " · add a shape to start")}</div>
      </div>
      ${this._renderComposerSelectedControls(state)}
      ${this._renderComposerRoomAssign(state)}
      <div class="evcc-map-config-section">
        <div class="evcc-compose-tools">
          <button class="evcc-map-config-btn evcc-map-config-btn--danger" data-action="compose-delete" ${hasSel ? "" : "disabled"}>Delete</button>
          <button class="evcc-map-config-btn" data-action="compose-clear" ${count ? "" : "disabled"}>Clear all</button>
        </div>
        <button
          class="evcc-map-config-btn evcc-map-config-btn--primary${saveBusy ? " evcc-map-config-btn--busy" : ""}"
          data-action="compose-save"
          ${(count && !saveBusy) ? "" : "disabled"}
        >${saveBusy ? "Saving…" : "Save rooms"}</button>
        ${saveErr
          ? `<span class="evcc-map-action-status evcc-map-action-status--error">${this.escapeHtml(status.message ?? "Save failed")}</span>`
          : ""}
      </div>
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
        <div class="evcc-map-config-section-title">Selected: <em>${s.type}</em></div>
        <div class="evcc-compose-tools">
          ${stepBtn(1, "Fine")}${stepBtn(3, "Med")}${stepBtn(7, "Coarse")}
        </div>
        ${groupSize >= 2 ? `
        <div class="evcc-map-config-adj-meta">Move: the whole room, or just this piece</div>
        <div class="evcc-compose-tools">
          <button class="evcc-map-config-btn${moveScope === "room" ? " evcc-map-config-btn--primary" : ""}"
            data-action="compose-move-scope" data-scope="room" title="Move the whole room together">Room</button>
          <button class="evcc-map-config-btn${moveScope === "piece" ? " evcc-map-config-btn--primary" : ""}"
            data-action="compose-move-scope" data-scope="piece" title="Move just this shape">Piece</button>
        </div>` : ""}
        <div class="evcc-map-nudge-pad">
          <div class="evcc-map-nudge-row">${mv(0, -1, "↑", "Up")}</div>
          <div class="evcc-map-nudge-row">${mv(-1, 0, "←", "Left")}${mv(1, 0, "→", "Right")}</div>
          <div class="evcc-map-nudge-row">${mv(0, 1, "↓", "Down")}</div>
        </div>
        <div class="evcc-map-config-adj-meta">…or tap the map to drop the shape there.</div>
        <div class="evcc-compose-tools">
          <button class="evcc-map-config-btn" data-action="compose-scale" data-factor="0.85" title="Shrink">－ Scale</button>
          <button class="evcc-map-config-btn" data-action="compose-scale" data-factor="1.18" title="Grow">＋ Scale</button>
        </div>
        ${s.type === "rect" ? `
        <div class="evcc-compose-tools">
          <button class="evcc-map-config-btn" data-action="compose-resize" data-dim="w" data-delta="-1">－ W</button>
          <button class="evcc-map-config-btn" data-action="compose-resize" data-dim="w" data-delta="1">＋ W</button>
          <button class="evcc-map-config-btn" data-action="compose-resize" data-dim="h" data-delta="-1">－ H</button>
          <button class="evcc-map-config-btn" data-action="compose-resize" data-dim="h" data-delta="1">＋ H</button>
        </div>` : ""}
        ${s.type !== "circle" ? `
        <div class="evcc-compose-tools">
          <button class="evcc-map-config-btn" data-action="compose-rotate" data-deg="-15" title="Rotate left">↺ Rotate</button>
          <button class="evcc-map-config-btn" data-action="compose-rotate" data-deg="15" title="Rotate right">↻ Rotate</button>
        </div>` : ""}
        <div class="evcc-compose-tools">
          ${merging
            ? `<button class="evcc-map-config-btn evcc-map-config-btn--primary" data-action="compose-merge-cancel" title="Stop merging">Cancel — tap a shape to merge</button>`
            : `<button class="evcc-map-config-btn" data-action="compose-merge-start" ${totalShapes < 2 ? "disabled" : ""} title="Combine another shape into this room">⛓ Merge</button>`}
          ${groupSize >= 2 ? `<button class="evcc-map-config-btn" data-action="compose-split" title="Make this shape its own room again">Split out</button>` : ""}
        </div>
        ${groupSize >= 2 ? `
        <div class="evcc-compose-tools">
          <button class="evcc-map-config-btn${s.op === "subtract" ? " evcc-map-config-btn--primary" : ""}"
            data-action="compose-toggle-op"
            title="${s.op === "subtract" ? "Carving a hole — tap to fill instead" : "Carve this shape out of the room (cutout)"}"
          >${s.op === "subtract" ? "⛏ Cutout (carving)" : "Make cutout"}</button>
        </div>` : ""}
        <div class="evcc-compose-tools">
          <button class="evcc-map-config-btn" data-action="compose-deselect" title="Stop editing this shape">Done</button>
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
          <p>No rooms discovered for this map yet — link a shape to a room here once they appear.</p>
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
          title="${takenByOther ? "Already linked to another shape"
            : linkedHere ? "Unlink" : "Link to " + this.escapeHtml(room.name)}"
        >${this.escapeHtml(room.name)}${linkedHere ? " ✓" : ""}</button>`;
    }).join("");
    return `
      <div class="evcc-map-config-section">
        <div class="evcc-map-config-section-title">Link to room</div>
        <div class="evcc-map-room-assign-chips">${chips}</div>
      </div>`;
  };

  proto._renderVariantsSection = function (variants, summary, actionStatus, state) {
    const armedDelete = state?.mapVariantDeleteArmed?.() ?? null;
    const rows = _VARIANTS.map(({ key, label, hint }) => {
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
        : "not uploaded";
      const statusCls  = uploaded
        ? "evcc-map-variant-status--ok"
        : "evcc-map-variant-status--missing";

      // Label flips between upload (network transfer) and analyze
      // (segmenter pipeline) so the user has some sense of what's happening.
      const buttonLabel = isUploadBusy ? "Uploading…"
                        : isAnalyzeBusy ? "Analyzing… (10-30s)"
                        : "Upload";

      return `
        <div class="evcc-map-variant-row">
          <div class="evcc-map-variant-info">
            <span class="evcc-map-variant-label">${this.escapeHtml(label)}</span>
            <span class="evcc-map-variant-hint">${this.escapeHtml(hint)}</span>
          </div>
          <span class="evcc-map-variant-status ${statusCls}">${statusText}</span>
          ${isError
            ? `<span class="evcc-map-action-status evcc-map-action-status--error">
                 ${this.escapeHtml(actionStatus.message ?? "Upload failed")}
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
            const btnLabel = isDeleteBusy ? "Deleting…"
                           : isArmed ? "Confirm Delete"
                           : "Delete";
            const btnClass = "evcc-map-config-btn evcc-map-config-btn--danger"
                           + (isArmed ? " evcc-map-config-btn--confirm" : "")
                           + (isDeleteBusy ? " evcc-map-config-btn--busy" : "");
            return `
              <button
                class="${btnClass}"
                data-action="delete-map-variant"
                data-variant="${key}"
                title="${isArmed
                  ? 'Click again to confirm — or click anywhere else to cancel'
                  : 'Delete this image (does not affect the map itself)'}"
                ${isDeleteBusy ? "disabled" : ""}
              >${btnLabel}</button>
              ${isArmed ? `
                <button
                  class="evcc-map-config-btn"
                  data-action="cancel-delete-map-variant"
                  title="Cancel the pending delete"
                >Cancel</button>
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
    const analyzedAt   = _formatAnalyzedAt(summary.analyzed_at);

    return `
      <div class="evcc-map-config-section">
        <div class="evcc-map-config-section-title">Image Variants</div>
        ${rows}
        <div class="evcc-map-config-analyze-row">
          <span class="evcc-map-config-seg-count">
            ${analyzeError
              ? `<span class="evcc-map-action-status evcc-map-action-status--error">
                   ${this.escapeHtml(actionStatus.message ?? "Analysis failed")}
                 </span>`
              : segCount > 0
                ? `${segCount} segments${adjCount > 0 ? `, ${adjCount} adjusted` : ""}${analyzedAt ? ` · ${analyzedAt}` : ""}`
                : "No segments analysed"}
          </span>
          <button
            class="evcc-map-config-btn evcc-map-config-btn--primary${analyzeBusy ? " evcc-map-config-btn--busy" : ""}"
            data-action="analyze-map"
            ${analyzeBusy ? "disabled" : ""}
          >${analyzeBusy ? "Analysing…" : segCount > 0 ? "Re-analyse" : "Analyse map"}</button>
        </div>
      </div>
    `;
  };

  /* =========================================================
     SEGMENT ADJUSTMENT SECTION
     ========================================================= */

  proto._renderSegmentAdjustSection = function (seg, state) {
    const label = seg.name ?? seg.label ?? `Segment ${seg.segment_id}`;
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
          Adjusting: <em>${this.escapeHtml(label)}</em>
        </div>
        <div class="evcc-map-config-adj-meta">Offset: ${ox} px, ${oy} px</div>
        <div class="evcc-map-nudge-pad">
          <div class="evcc-map-nudge-row">
            <button class="evcc-map-nudge-btn" data-action="nudge-segment"
              data-segment-id="${segIdStr}" data-dx="0" data-dy="-${step.y}" title="Nudge up">↑</button>
          </div>
          <div class="evcc-map-nudge-row">
            <button class="evcc-map-nudge-btn" data-action="nudge-segment"
              data-segment-id="${segIdStr}" data-dx="-${step.x}" data-dy="0" title="Nudge left">←</button>
            <button class="evcc-map-nudge-btn evcc-map-nudge-btn--reset"
              data-action="reset-segment-adjustment"
              data-segment-id="${segIdStr}" title="Reset translation">○</button>
            <button class="evcc-map-nudge-btn" data-action="nudge-segment"
              data-segment-id="${segIdStr}" data-dx="${step.x}" data-dy="0" title="Nudge right">→</button>
          </div>
          <div class="evcc-map-nudge-row">
            <button class="evcc-map-nudge-btn" data-action="nudge-segment"
              data-segment-id="${segIdStr}" data-dx="0" data-dy="${step.y}" title="Nudge down">↓</button>
          </div>
        </div>
      </div>
    `;
  };

  proto._renderEdgeSection = function (seg, state, segIdStr) {
    const step = state.mapNudgeStep();
    const ea   = seg.edge_adjustment ?? {};
    const edges = [
      { key: "top",    label: "Top",    stepKey: "y" },
      { key: "bottom", label: "Bottom", stepKey: "y" },
      { key: "left",   label: "Left",   stepKey: "x" },
      { key: "right",  label: "Right",  stepKey: "x" },
    ];

    const rows = edges.map(({ key, label, stepKey }) => {
      const cur = ea[key] ?? 0;
      const s   = step[stepKey];
      return `
        <div class="evcc-map-edge-row">
          <span class="evcc-map-edge-label">${label}</span>
          <button class="evcc-map-nudge-btn evcc-map-nudge-btn--edge"
            data-action="adjust-edge" data-segment-id="${segIdStr}"
            data-edge="${key}" data-delta="-${s}" title="Contract ${label}">−</button>
          <span class="evcc-map-edge-val">${cur > 0 ? "+" : ""}${cur}</span>
          <button class="evcc-map-nudge-btn evcc-map-nudge-btn--edge"
            data-action="adjust-edge" data-segment-id="${segIdStr}"
            data-edge="${key}" data-delta="${s}" title="Expand ${label}">+</button>
        </div>
      `;
    }).join("");

    return `
      <div class="evcc-map-config-section">
        <div class="evcc-map-config-section-title">Edges</div>
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
              data-dx="0" data-dy="-${step.y}" title="Nudge vertex up">↑</button>
          </div>
          <div class="evcc-map-nudge-row">
            <button class="evcc-map-nudge-btn" data-action="nudge-vertex"
              data-segment-id="${segIdStr}" data-vertex-index="${selectedIdx}"
              data-dx="-${step.x}" data-dy="0" title="Nudge vertex left">←</button>
            <button class="evcc-map-nudge-btn evcc-map-nudge-btn--reset"
              data-action="reset-vertex"
              data-segment-id="${segIdStr}" data-vertex-index="${selectedIdx}"
              title="Reset this vertex">○</button>
            <button class="evcc-map-nudge-btn" data-action="nudge-vertex"
              data-segment-id="${segIdStr}" data-vertex-index="${selectedIdx}"
              data-dx="${step.x}" data-dy="0" title="Nudge vertex right">→</button>
          </div>
          <div class="evcc-map-nudge-row">
            <button class="evcc-map-nudge-btn" data-action="nudge-vertex"
              data-segment-id="${segIdStr}" data-vertex-index="${selectedIdx}"
              data-dx="0" data-dy="${step.y}" title="Nudge vertex down">↓</button>
          </div>
        </div>
      `;
    }

    return `
      <div class="evcc-map-config-section">
        <div class="evcc-map-config-section-title">Vertices</div>
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
            ? "Already linked to another segment"
            : isLinkedHere
              ? `Unlink ${this.escapeHtml(room.name)}`
              : `Link to ${this.escapeHtml(room.name)}`}"
        >${this.escapeHtml(room.name)}${isLinkedHere ? " ✓" : ""}</button>
      `;
    }).join("");

    return `
      <div class="evcc-map-config-section">
        <div class="evcc-map-config-section-title">Link to room</div>
        <div class="evcc-map-room-assign-chips">${chips}</div>
      </div>
    `;
  };
}
