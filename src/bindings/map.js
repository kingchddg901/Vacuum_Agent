/**
 * ============================================================
 * BINDINGS: MAP
 * ============================================================
 *
 * Wires DOM interactions in the map view — polygon selection,
 * pan/zoom gestures, tooltip hover, map config, and animal
 * companion drag/scale/species controls.
 *
 * ============================================================
 */

import { VIEWS } from "../render-cycle.js";
import { roomFillRgb, roomOverrideRgb, ROOM_FILL_N } from "../cards/map-room-color.js";
import { FLOOR_TEXTURE_REGISTRY, getPrimaryTextureUrl } from "../textures/floor-texture-registry.js";
import { resolveFloorType } from "../textures/floor-texture-resolver.js";
import { compositeFloorTexture } from "../textures/floor-texture-compositor.js";

// Apparent size of the floor material on the map: the 2048² masks are drawn to fill a
// ROOM-sized card, so at 1:1 (native) their veins/planks look "zoomed in" over the whole map.
// Scale the mask pattern DOWN so features are smaller + tile denser (more per room). 1.0 =
// native (too big); lower = finer/denser.
//
// PER-MATERIAL: materials read best at different feature sizes — marble's broad veins look
// great tiny (0.11), but granite's fine speckle vanishes to a flat dark field when shrunk that
// far. So each type gets its own default here; unlisted types fall back to the global. A theme
// can override any with `--evcc-floor-<type>-map-scale` (the "slider"). Tune by eye.
const FLOOR_TEXTURE_MASK_SCALE = 0.05; // global fallback (all materials at 0.05 for now)
const FLOOR_TEXTURE_MASK_SCALE_BY_TYPE = {
  // Keys MUST match resolveFloorType()'s output — e.g. granite resolves to "granite_light",
  // carpet to "carpet_low"/"carpet_high". A wrong key silently falls back to the global scale.
  marble:        0.05,
  tile:          0.05,
  wood:          0.05,
  concrete:      0.7,   // two-layer (broad + micro) -> splotches read; 0.7 tightens them a bit
  granite_light: 0.05,  // single fine speckle, no bold layer -> junk at any scale; PARKED, needs a mask
  carpet_low:    0.65,  // ditto — needs a bolder/special mask, not a scale tweak
  carpet_high:   0.65,
};

// The VA raster room-fill colors now resolve through the shared themeable palette
// (roomFillRgb, reading --evcc-room-fill-N off the canvas); the hardcoded array moved to
// cards/map-room-color.js as ROOM_FILL_PALETTE.

/**
 * Mix map binding methods onto the given prototype.
 *
 * @param {object} proto - VacuumCardBindings prototype to extend.
 */
export function applyMapBindings(proto) {

  /**
   * The live-map backdrop's natural pixel dims {width,height}, for letterbox-correcting a
   * drawn zone. The backdrop is an <img> (has naturalWidth) OR a <canvas> (VA-render /
   * selection scrim — has .width, NO naturalWidth), both sharing the .evcc-map-image class,
   * so accept EITHER and take the first element that actually reports dims. null when nothing
   * usable is mounted. Shared by the ad-hoc zone-clean confirm AND the saved-zone draw-to-save.
   *
   * @param {ParentNode} root  node to query within (map container or shadow root)
   */
  proto._liveMapDims = function (root) {
    if (!root || typeof root.querySelectorAll !== "function") return null;
    for (const el of root.querySelectorAll(".evcc-map-image")) {
      const w = el.naturalWidth || el.width || 0;
      const h = el.naturalHeight || el.height || 0;
      if (w > 0 && h > 0) return { width: w, height: h };
    }
    return null;
  };

  /* =========================================================
     BIND MAP
     =========================================================
     Re-attached after every render while rooms view is active.
     ========================================================= */

  proto._bindMap = function () {
    const root = this.card.shadowRoot;
    if (!root) return;

    this._bindMapViewToggle(root);
    this._bindMapPolygons(root);
    this._bindMapTooltip(root);
    this._bindMapChips(root);
    this._bindMapConfigEntry(root);
    this._bindMapConfig(root);
    this._bindMapZoomPan(root);
    this._bindMapAnimal(root);
    this._bindAreaLabelDrag(root);
    this._bindRoomNameDrag(root);
    this._bindFurnishedArt(root);
    this._bindMapAnimalSelect(root);
    this._bindMapLayersPanel(root);
    this._bindMapRenderToggle(root);
    this._bindMapRenderCanvas(root);
    this._bindSelectionScrim(root);

    const view = this.card._view;
    if (view === VIEWS.MAP_CONFIG || this.card._state.isMapViewActive?.()) {
      this._ensureMapSegments();
    }
  };

  /* =========================================================
     MAP LAYERS PANEL (Wave 3c overlay visibility toggles)
     ========================================================= */

  proto._bindMapLayersPanel = function (root) {
    root.querySelectorAll("[data-action='toggle-map-overlay']").forEach((el) => {
      this.card._on(el, "change", () => {
        const layer = el.dataset.layer;
        if (!layer) return;
        this.card._actions
          .setMapOverlayVisibility(layer, el.checked)
          .then(() => this.card._scheduleRender())
          .catch((err) => {
            // Service failed — roll back the optimistic flip so the checkbox +
            // overlay revert to the backend value instead of sticking unsaved.
            console.error("[eufy-vacuum-command-center] Overlay toggle failed:", err);
            this.card._state.clearOverlayVisibilityOptimistic?.(layer);
            this.card._scheduleRender();
          });
        // Optimistic flip already applied in state; re-render now for instant feedback.
        this.card._scheduleRender();
      });
    });

    // Hide-area draw: enter/exit the draw+edit mode (the rubber-band drag lives in the
    // map-container pointerdown handler).
    root.querySelectorAll("[data-action='toggle-hide-draw']").forEach((btn) => {
      this.card._on(btn, "click", () => {
        this.card._state.setHideDrawMode?.(!(this.card._state.hideDrawMode?.() ?? false));
        this.card._scheduleRender();
      });
    });
    // Delete ONE hidden region (the × on a mask while editing).
    root.querySelectorAll("[data-action='delete-hidden-region']").forEach((btn) => {
      this.card._on(btn, "click", (e) => {
        e.stopPropagation();
        const idx = Number(btn.dataset.index);
        const cur = this.card._state.hiddenRegions?.() ?? [];
        if (!Number.isInteger(idx) || idx < 0 || idx >= cur.length) return;
        const next = cur.filter((_, i) => i !== idx);
        this.card._actions?.setHiddenRegions?.(next);
        this.card._scheduleRender();
      });
    });
    // Clear ALL hidden regions.
    root.querySelectorAll("[data-action='clear-hidden-regions']").forEach((btn) => {
      this.card._on(btn, "click", () => {
        this.card._actions?.setHiddenRegions?.([]);
        this.card._scheduleRender();
      });
    });
  };

  /* =========================================================
     VA-RENDERED MAP BACKDROP (Wave 1 — client-side canvas)
     ========================================================= */

  proto._bindMapRenderToggle = function (root) {
    root.querySelectorAll("[data-action='toggle-va-render']").forEach((btn) => {
      this.card._on(btn, "click", () => {
        this.card._state.toggleUseVaRender?.();
        this.card._scheduleRender();
      });
    });
    root.querySelectorAll("[data-action='toggle-floor-texture']").forEach((btn) => {
      this.card._on(btn, "click", () => {
        this.card._state.toggleUseFloorTexture?.();
        this.card._scheduleRender();
      });
    });
  };

  /**
   * When the VA-rendered backdrop is selected: fetch the raster ONCE (cached by
   * version), then draw it to the <canvas> backdrop — redrawing only when the map
   * version changes. The raster is static, so this is cheap.
   */
  proto._bindMapRenderCanvas = function (root) {
    const state = this.card._state;
    // Fetch the render raster whenever overlays are shown over a render-capable map — the canvas
    // draws it for the VA backdrop AND the room hit-test (auto-derived click targets) needs it on
    // the live backdrop too. Drawing below is a no-op when the canvas element isn't rendered
    // (i.e. the VA backdrop isn't active). Fetch-once, cached by version.
    if (!(state.supportsVaRender?.() && state.overlaysAligned?.())) return;

    // Invalidate a raster fetched for a DIFFERENT map — we only auto-fetch when rd is null
    // (below), so without this a map/layout switch would keep hit-testing + dimming against the
    // previous map's frame. The version-keyed derived caches (raster/vaImage/scrim) self-clear
    // once the new map's render data (new version) lands.
    const mapId = state.activeMapId?.() ?? null;
    if (state.mapRenderData?.() && this._renderDataMapId != null && this._renderDataMapId !== mapId) {
      state.setMapRenderData?.(null);
    }
    const rd = state.mapRenderData?.();
    if (!rd && !this._vaRenderFetching) {
      this._vaRenderFetching = true;
      this._renderDataMapId = mapId;   // tag the map this fetch belongs to (stale-on-switch guard)
      this.card._actions
        .getMapRenderData()
        .then((data) => {
          // Store a TRUTHY sentinel on a null/failed resolve so the binding doesn't
          // re-fetch on every render (a transient WS drop returns null). Re-flipping the
          // toggle clears the cache to retry.
          state.setMapRenderData?.(
            (data && typeof data === "object")
              ? data
              : { present: false, reason: "fetch_failed" });
          this.card._scheduleRender();
        })
        .catch((err) => {
          console.error("[eufy-vacuum-command-center] map render fetch failed:", err);
          state.setMapRenderData?.({ present: false, reason: "fetch_failed" });
        })
        .finally(() => { this._vaRenderFetching = false; });
      return;
    }

    const canvas = root.querySelector("canvas.evcc-map-render-canvas");
    if (!canvas || !rd || !rd.present) return;
    // Floor-texture mode paints the same raster with per-room material textures; the
    // draw-key includes the mode so a flat<->floor toggle repaints (and the async
    // texture decode's re-render lands on a fresh canvas anyway).
    const floor = state.isFloorRenderActive?.() ?? false;
    const drawKey = `${rd.version}|${floor ? "floor" : "flat"}`;
    if (canvas._evccDrawnKey === drawKey) return; // already drawn this (version, mode)
    try {
      if (floor) this._drawVaFloorRender(canvas, rd);
      else this._drawVaRender(canvas, rd);
      canvas._evccDrawnKey = drawKey;
    } catch (err) {
      console.error("[eufy-vacuum-command-center] map render draw failed:", err);
    }
  };

  /**
   * SUBTRACTIVE room selection: draw a per-pixel dark scrim over the UN-selected device rooms
   * (exact room shapes from the raster) so selected rooms stay bright with no bbox overlap. The
   * scrim ImageData is cached on the binding by (version + selection) and re-stamped onto each
   * freshly-rendered canvas (cheap), mirroring _drawVaRender.
   */
  proto._bindSelectionScrim = function (root) {
    const state = this.card._state;
    const canvas = root.querySelector("canvas.evcc-map-selection-canvas");
    if (!canvas) return;
    const rd = state.mapRenderData?.();
    if (!rd || !rd.present) return;
    const W = rd.width | 0, H = rd.height | 0;
    if (W <= 0 || H <= 0) return;
    const selKey = canvas.dataset.selKey || "";
    let cache = this._scrimCache;
    if (!cache || cache.key !== selKey || cache.w !== W || cache.h !== H) {
      const bin = state._roomRasterBin?.(rd);
      if (!bin) return;
      const selected = new Set(
        (state.getRoomsForActiveMap?.() ?? []).filter((r) => r.enabled).map((r) => Number(r.id)),
      );
      const ctx0 = canvas.getContext("2d");
      if (!ctx0) return;
      const img = ctx0.createImageData(W, H);
      const data = img.data;
      const roW = rd.ro_width | 0, roH = rd.ro_height | 0;
      const dx = rd.ro_dx | 0, dy = rd.ro_dy | 0;
      const shift = rd.rid_shift | 0, catchAll = rd.catch_all_rid | 0;
      const flip = rd.flip_y !== false;
      for (let py = 0; py < H; py++) {
        for (let px = 0; px < W; px++) {
          const rx = px - dx, ry = py - dy;
          if (rx < 0 || rx >= roW || ry < 0 || ry >= roH) continue;
          const idx = ry * roW + rx;
          if (idx >= bin.length) continue;
          const rid = bin.charCodeAt(idx) >> shift;
          if (!(rid > 0 && rid < catchAll)) continue;   // not a room -> never dim
          if (selected.has(rid)) continue;              // selected -> stays bright
          const iy = flip ? (H - 1 - py) : py;
          const o = (iy * W + px) * 4;
          data[o] = 8; data[o + 1] = 10; data[o + 2] = 14; data[o + 3] = 168;  // ~0.66 dark scrim
        }
      }
      cache = { key: selKey, w: W, h: H, img };
      this._scrimCache = cache;
    }
    canvas.width = W;
    canvas.height = H;
    const ctx = canvas.getContext("2d");
    if (ctx) ctx.putImageData(cache.img, 0, 0);
  };

  /**
   * Decode the room-id raster into the canvas: per pixel, room id = byte>>rid_shift;
   * map the room_outline raster coord to the main grid (+ro_dx/dy), apply the Y-flip,
   * and paint the room's palette colour. All decode params come from the service
   * response (no brand assumptions). Wave 1 = rooms only (walls/floor are Wave 2).
   */
  proto._drawVaRender = function (canvas, rd) {
    const W = rd.width | 0, H = rd.height | 0;
    if (W <= 0 || H <= 0) return;
    canvas.width = W;
    canvas.height = H;
    const cctx = canvas.getContext("2d");
    if (!cctx) return;
    // Resolve the themeable room-fill palette ONCE (the canvas inherits the --evcc-room-fill-N
    // tokens); a palette signature busts the cache so a theme recolor repaints. The canvas takes
    // no CSS vars, so the raster reads the RESOLVED RGBs — unlike the SVG path, which uses var()
    // live. Themeless => the default palette => byte-identical to the old render.
    const palette = [];
    for (let i = 0; i < ROOM_FILL_N; i++) palette[i] = roomFillRgb(i, canvas);
    const paletteSig = palette.map((c) => c.join(",")).join("|");
    // Per-room fill OVERRIDES: recolor each room's OWN pixels with its custom color, so the cascade
    // (override > token > default) holds on the raster too — an exact per-pixel recolor, not an
    // overlay. Bridge the raster's per-pixel rid to a room via the DEVICE-AUTHORITATIVE rid->name
    // map the render payload already ships (rd.room_names = {rid: name}); our rooms carry that same
    // name (it's what the labels show). Keying by room.id directly is WRONG — the raster rid and our
    // stored room.id are DIFFERENT id spaces on real devices (empirically verified), so a room.id
    // key lands on no pixels (or, worse, another room's). Name-mismatch just falls through to the
    // palette — it never miscolors. Sparse array keyed by numeric rid so the hot pixel loop is a
    // plain index read; an overrideSig busts the cache so a recolor repaints, like paletteSig.
    const state = this.card._state;
    const rooms = state?.getRoomsForActiveMap?.() ?? [];
    const norm = (s) => String(s == null ? "" : s).trim().toLowerCase();
    const rgbByName = new Map();
    for (const room of rooms) {
      const rgb = roomOverrideRgb(room.color);
      if (rgb && room.name != null) rgbByName.set(norm(room.name), rgb);
    }
    const overrideByRid = [];
    const ridNames = (rd && rd.room_names) || {};
    for (const ridStr of Object.keys(ridNames)) {
      const rgb = rgbByName.get(norm(ridNames[ridStr]));
      const ridNum = Number(ridStr);
      if (rgb && Number.isFinite(ridNum)) overrideByRid[ridNum] = rgb;
    }
    const overrideSig = overrideByRid
      .map((c, i) => (c ? `${i}:${c.join(",")}` : null))
      .filter(Boolean)
      .join("|");
    // The canvas element is recreated on every view re-render (zoom/select/etc.), but the raster
    // is static per (map version, palette, overrides) — decode ONCE into an ImageData cached on the
    // binding, then just putImageData onto each fresh canvas (cheap).
    let cache = this._vaImageCache;
    if (!cache || cache.version !== rd.version || cache.w !== W || cache.h !== H
        || cache.paletteSig !== paletteSig || cache.overrideSig !== overrideSig) {
      const img = cctx.createImageData(W, H);
      const data = img.data;
      const bin = atob(rd.room_pixels || "");
      const roW = rd.ro_width | 0, roH = rd.ro_height | 0;
      const dx = rd.ro_dx | 0, dy = rd.ro_dy | 0;
      const shift = rd.rid_shift | 0;
      const catchAll = rd.catch_all_rid | 0;
      const flip = rd.flip_y !== false;
      for (let ry = 0; ry < roH; ry++) {
        const rowOff = ry * roW;
        for (let rx = 0; rx < roW; rx++) {
          const idx = rowOff + rx;
          if (idx >= bin.length) break;
          const rid = bin.charCodeAt(idx) >> shift;
          if (!(rid > 0 && rid < catchAll)) continue;
          const px = rx + dx, py = ry + dy;
          if (px < 0 || px >= W || py < 0 || py >= H) continue;
          const iy = flip ? (H - 1 - py) : py;
          const o = (iy * W + px) * 4;
          const c = overrideByRid[rid]
            || palette[(((rid - 1) % ROOM_FILL_N) + ROOM_FILL_N) % ROOM_FILL_N];
          data[o] = c[0]; data[o + 1] = c[1]; data[o + 2] = c[2]; data[o + 3] = 255;
        }
      }
      cache = { version: rd.version, w: W, h: H, paletteSig, overrideSig, img };
      this._vaImageCache = cache;
    }
    cctx.putImageData(cache.img, 0, 0);
  };

  /* =========================================================
     FLOOR-TEXTURE RENDER (mechanism A — raster clip, SUPERSAMPLED)
     =========================================================
     Paint each room's pixels from its floor-TYPE's composited material instead of a
     flat color. Continuous by construction: the material is composited in map-space
     (final-image coords), so adjacent same-type rooms sample the same texel — one
     continuous floor, no per-room offset/hash.

     WHY SUPERSAMPLED: the room_pixels raster is only ~360px. Downscaling the fine
     plank/grout masks to THAT averages the detail into a flat muddy tint (then the
     360px canvas upscales to the display, blurring more) — which is exactly the mush
     the first cut produced. So we render the canvas + composite the masks at S× the
     raster (~1200px): the material keeps its detail. The per-room CLIP is nearest-
     upscaled from the raster (room edges were already raster-limited — only the FILL
     needs to be crisp). Untextured / "default" rooms fall back to the flat palette.
     Async decode re-renders on completion. Both brands (Eufy CV + Roborock decode). */
  proto._drawVaFloorRender = function (canvas, rd) {
    const W = rd.width | 0, H = rd.height | 0;
    if (W <= 0 || H <= 0) return;

    const state = this.card._state;
    const rooms = state?.getRoomsForActiveMap?.() ?? [];
    const norm = (s) => String(s == null ? "" : s).trim().toLowerCase();

    // rid -> floorType, via the SAME device-authoritative rid->name bridge _drawVaRender
    // uses for colors (rd.room_names = {rid: name}; our rooms carry that name + floor_type).
    const floorByName = new Map();
    for (const room of rooms) {
      const ft = resolveFloorType({
        floor_type:  room?.floor_type  ?? room?.floorType  ?? "",
        carpet_type: room?.carpet_type ?? room?.carpetType ?? "",
      });
      if (ft && room.name != null) floorByName.set(norm(room.name), ft);
    }
    const floorTypeByRid = [];
    const ridNames = (rd && rd.room_names) || {};
    for (const ridStr of Object.keys(ridNames)) {
      const ft = floorByName.get(norm(ridNames[ridStr]));
      const ridNum = Number(ridStr);
      if (ft && Number.isFinite(ridNum)) floorTypeByRid[ridNum] = ft;
    }
    // "default" = no floor type set -> stays flat (palette); only real, textured types paint.
    const presentTypes = [...new Set(floorTypeByRid.filter(Boolean))]
      .filter((ft) => ft !== "default" && getPrimaryTextureUrl(ft));

    // Supersample the ~360px raster to ~1200px so the mask detail survives.
    const S = Math.max(1, Math.min(4, Math.round(1200 / Math.max(W, H)) || 1));
    const CW = W * S, CH = H * S;
    canvas.width = CW;
    canvas.height = CH;
    const cctx = canvas.getContext("2d");
    if (!cctx) return;

    // Flat palette — fallback for untextured rooms AND placeholder before textures load.
    const palette = [];
    for (let i = 0; i < ROOM_FILL_N; i++) palette[i] = roomFillRgb(i, canvas);
    const paletteSig = palette.map((c) => c.join(",")).join("|");
    const flatColor = (rid) => palette[(((rid - 1) % ROOM_FILL_N) + ROOM_FILL_N) % ROOM_FILL_N];

    // Decode room_pixels -> the rid at each FINAL (px, iy) raster cell (the per-room clip).
    const ridAtFinal = new Int16Array(W * H); // 0 = no room
    {
      const bin = atob(rd.room_pixels || "");
      const roW = rd.ro_width | 0, roH = rd.ro_height | 0;
      const dx = rd.ro_dx | 0, dy = rd.ro_dy | 0;
      const shift = rd.rid_shift | 0;
      const catchAll = rd.catch_all_rid | 0;
      const flip = rd.flip_y !== false;
      for (let ry = 0; ry < roH; ry++) {
        const rowOff = ry * roW;
        for (let rx = 0; rx < roW; rx++) {
          const idx = rowOff + rx;
          if (idx >= bin.length) break;
          const rid = bin.charCodeAt(idx) >> shift;
          if (!(rid > 0 && rid < catchAll)) continue;
          const px = rx + dx, py = ry + dy;
          if (px < 0 || px >= W || py < 0 || py >= H) continue;
          const iy = flip ? (H - 1 - py) : py;
          ridAtFinal[iy * W + px] = rid;
        }
      }
    }

    // Composite each present material at the canvas res, with the masks drawn at NATIVE
    // resolution (see _decodeMaskLum) so the fine grain/plank-seam detail survives — the
    // detail is what makes it read as a floor. Map-space + native-tiled -> continuous across
    // same-type rooms. (Downscaling the masks to map size averaged the detail to flat.)
    const { ready } = this._ensureFloorTextures(presentTypes, CW, CH, canvas);

    // Cache the composited floor ImageData (like _drawVaRender's) so zoom/select re-renders
    // just re-stamp it. Busts on version, size/scale, palette (theme), the rid->type map, or
    // a texture becoming ready (its key joins once decoded).
    const floorKey = `${rd.version}|${CW}x${CH}|${paletteSig}|${floorTypeByRid.join(",")}`
      + `|${[...ready.keys()].sort().join(",")}`;
    let cache = this._vaFloorImageCache;
    if (!cache || cache.key !== floorKey) {
      const img = cctx.createImageData(CW, CH);
      const data = img.data;
      for (let oy = 0; oy < CH; oy++) {
        const fy = (oy / S) | 0;         // nearest raster row
        const rowBase = fy * W;
        const oRow = oy * CW;
        for (let ox = 0; ox < CW; ox++) {
          const rid = ridAtFinal[rowBase + ((ox / S) | 0)];
          if (rid <= 0) continue;        // outside every room -> transparent
          const o = (oRow + ox) * 4;
          const ft = floorTypeByRid[rid];
          const tex = ft ? ready.get(ft) : null;
          if (tex) {
            // 1:1 map-space sample (tex is CW×CH from a native-res mask) -> crisp + continuous.
            data[o] = tex.data[o]; data[o + 1] = tex.data[o + 1];
            data[o + 2] = tex.data[o + 2]; data[o + 3] = 255;
          } else {
            const c = flatColor(rid);
            data[o] = c[0]; data[o + 1] = c[1]; data[o + 2] = c[2]; data[o + 3] = 255;
          }
        }
      }
      cache = { key: floorKey, img };
      this._vaFloorImageCache = cache;
    }
    cctx.putImageData(cache.img, 0, 0);
  };

  /* Ensure each present floorType's material is decoded + composited at W×H. Returns
     `{ ready: Map<floorType, {data}> }` of the types ready THIS frame; missing ones kick
     an async mask decode that re-renders on completion. Two caches on the binding: raw
     mask luminance (theme-independent, keyed by URL+size) and the composited texture
     (theme-dependent, keyed by resolved colors/opacities). */
  proto._ensureFloorTextures = function (presentTypes, W, H, host) {
    this._floorMaskCache = this._floorMaskCache || new Map();    // maskKey -> Uint8ClampedArray lum
    this._floorMaskPending = this._floorMaskPending || new Set();
    this._floorTexCache = this._floorTexCache || new Map();      // texKey -> composited {data}

    const ready = new Map();

    for (const ft of presentTypes) {
      const entry = FLOOR_TEXTURE_REGISTRY[ft];
      if (!entry || !Array.isArray(entry.layers) || !entry.layers.length) continue;

      // Per-material feature scale (token override / registry default / global).
      const scale = this._resolveFloorScale(ft, host);

      // Resolve each layer's color + opacity now (cheap getComputedStyle reads) -> colorSig.
      const resolved = entry.layers.map((layer) => ({
        url: String(layer.url),
        color: this._resolveFloorColor(layer.colorToken, layer.colorDefault, host),
        opacity: this._resolveFloorOpacity(layer.opacityToken, layer.opacityDefault, host),
      }));
      const colorSig = resolved.map((r) => `${r.color.join(",")}:${r.opacity}`).join("|");
      const texKey = `${ft}|${W}x${H}|${scale}|${colorSig}`;

      const cachedTex = this._floorTexCache.get(texKey);
      if (cachedTex) { ready.set(ft, cachedTex); continue; }

      // Need every layer's mask decoded to a luminance array.
      const lumArrays = [];
      let allLoaded = true;
      for (const r of resolved) {
        const maskKey = `${r.url}|${W}x${H}|${scale}`;
        const lum = this._floorMaskCache.get(maskKey);
        if (lum) { lumArrays.push(lum); continue; }
        allLoaded = false;
        if (!this._floorMaskPending.has(maskKey)) {
          this._floorMaskPending.add(maskKey);
          // ALWAYS cache a result (real luminance, or a zero-fill sentinel on failure) so a
          // missing/broken PNG degrades to "layer reveals nothing" (base shows through) instead
          // of never caching -> re-kicking every render -> an infinite render loop.
          this._decodeMaskLum(r.url, W, H, scale)
            .then((arr) => { this._floorMaskCache.set(maskKey, arr || new Uint8ClampedArray(W * H)); })
            .catch(() => { this._floorMaskCache.set(maskKey, new Uint8ClampedArray(W * H)); })
            .finally(() => {
              this._floorMaskPending.delete(maskKey);
              this.card._scheduleRender?.();
            });
        }
      }
      if (!allLoaded) continue;

      // Base = the "base"-role layer's color (else layer 0) — what shows in any gaps the
      // masks leave. Composite all layers over it (pure; unit-tested).
      const baseIdx = entry.layers.findIndex((l) => l.role === "base");
      const base = resolved[baseIdx >= 0 ? baseIdx : 0].color;
      const tex = compositeFloorTexture(
        W, H, base,
        // Fold the color's own alpha (8-hex / oklch can carry one) into the layer opacity —
        // that's what the CSS card does implicitly, so the material tones match.
        resolved.map((r, i) => ({
          lum: lumArrays[i],
          color: r.color,
          opacity: r.opacity * (Number.isFinite(r.color?.[3]) ? r.color[3] : 1),
        })),
      );
      this._floorTexCache.set(texKey, tex);
      ready.set(ft, tex);
    }

    return { ready };
  };

  /* Load a grayscale mask PNG and downscale it to W×H, returning a per-texel luminance
     array (0..255; white reveals). Same-origin (served by HA), so the canvas read is not
     tainted. Async — the caller re-renders when it resolves. */
  proto._decodeMaskLum = async function (url, W, H, scale = FLOOR_TEXTURE_MASK_SCALE) {
    if (typeof Image !== "function" || typeof document === "undefined") return null;
    const img = new Image();
    img.decoding = "async";
    img.src = url;
    await img.decode();
    const c = document.createElement("canvas");
    c.width = W; c.height = H;
    const cx = c.getContext("2d", { willReadFrequently: true });
    if (!cx) return null;
    // Fill at NATIVE resolution (repeat-pattern), NOT downscaled to W×H. Downscaling the fine
    // grain/seam detail (1-3px in the 2048 mask) to map size averages it to nothing -> flat.
    // Native res keeps it crisp — the same way the card shows the mask at native size — and the
    // pattern wraps for canvases larger than the mask.
    const pat = cx.createPattern(img, "repeat");
    if (!pat) return null;
    // Scale the pattern DOWN so the material features are smaller + tile denser (many veins/
    // planks per room) instead of one zoomed-in swatch. Anchored at (0,0) so every layer/room
    // shares the same map-space grid -> continuous across rooms.
    if (typeof pat.setTransform === "function" && typeof DOMMatrix === "function") {
      try {
        pat.setTransform(new DOMMatrix([scale, 0, 0, scale, 0, 0]));
      } catch (_e) { /* older engine — fall back to native scale */ }
    }
    cx.fillStyle = pat;
    cx.fillRect(0, 0, W, H);
    const d = cx.getImageData(0, 0, W, H).data;
    const n = W * H;
    const lum = new Uint8ClampedArray(n);
    for (let i = 0; i < n; i++) {
      const o = i * 4;
      lum[i] = d[o] * 0.299 + d[o + 1] * 0.587 + d[o + 2] * 0.114;
    }
    return lum;
  };

  /* Parse ANY CSS color string (hex 3/6/8, rgb()/hsl(), oklch(), named) to [r,g,b,a] via the
     browser's OWN parser (a cached 1×1 scratch canvas). The registry uses 8-digit hex (e.g.
     wood base #7A4010cf) and oklch() — the old hexToRgb only groks 3/6-digit hex and fell back
     to GREY [128,128,128] for the rest, which is why the canvas floor rendered flat grey while
     the CARDS (CSS, full color support) rendered fine. Returns null on an unparseable value. */
  proto._parseCssColor = function (str) {
    if (str == null || str === "") return null;
    let ctx = this._colorScratchCtx;
    if (!ctx) {
      if (typeof document === "undefined") return null;
      try {
        const c = document.createElement("canvas");
        c.width = 1; c.height = 1;
        ctx = c.getContext("2d", { willReadFrequently: true });
      } catch (_e) { return null; }
      this._colorScratchCtx = ctx;
    }
    if (!ctx) return null;
    try {
      ctx.fillStyle = "#000";
      ctx.fillStyle = String(str);   // an invalid value is IGNORED (fillStyle keeps its prior)
      ctx.fillRect(0, 0, 1, 1);
      const d = ctx.getImageData(0, 0, 1, 1).data;
      return [d[0], d[1], d[2], d[3] / 255];
    } catch (_e) { return null; }
  };

  /* Resolve a floor layer's color to [r,g,b,a]. Resolve it ON THE HOST element (the canvas,
     which inherits the theme vars) by applying it as a real `color` property and reading the
     COMPUTED value — exactly how the card's CSS resolves it. This is what lets `var()` and
     `oklch(from var(...) ...)` (the marble vein-minor default) resolve to real rgb; the bare
     scratch-canvas parser can't resolve a var() with no element context and was painting
     those veins BLACK. Falls back to parsing the default, then grey. The caller folds the
     alpha into the layer opacity. */
  /* A hidden, dedicated probe element appended BESIDE the map canvas (so it inherits the same
     theme vars) used ONLY to resolve floor colors — so color resolution never mutates the render
     canvas, and never touches anything the room-card / swatch renderers use. Fully map-local. */
  proto._floorColorProbe = function (host) {
    const parent = host && host.parentNode;
    if (!parent || typeof document === "undefined") return null;
    let el = this._floorColorProbeEl;
    if (!el || el.parentNode !== parent) {
      if (el && el.parentNode) { try { el.parentNode.removeChild(el); } catch (_e) {} }
      el = document.createElement("span");
      el.setAttribute("aria-hidden", "true");
      el.style.cssText =
        "position:absolute;width:0;height:0;overflow:hidden;visibility:hidden;pointer-events:none";
      try { parent.appendChild(el); } catch (_e) { return null; }
      this._floorColorProbeEl = el;
    }
    return el;
  };

  proto._resolveFloorColor = function (token, dflt, host) {
    try {
      const el = this._floorColorProbe(host);
      if (el && typeof getComputedStyle === "function") {
        const tokenVal = getComputedStyle(el).getPropertyValue(token).trim();
        const want = tokenVal || dflt;
        el.style.color = "";
        el.style.color = want;                          // invalid CSS is ignored -> stays ""
        const resolved = el.style.color ? getComputedStyle(el).color : "";  // computed rgb/oklab
        if (resolved) {
          const rgba = this._parseCssColor(resolved);
          if (rgba) return rgba;
        }
      }
    } catch (_e) { /* fall through to the default */ }
    return this._parseCssColor(dflt) || [128, 128, 128, 1];
  };

  /* Resolve a floor layer's opacity token (0..1), falling back to the registry default. */
  proto._resolveFloorOpacity = function (token, dflt, host) {
    let raw = dflt;
    try {
      if (host && typeof getComputedStyle === "function") {
        const v = getComputedStyle(host).getPropertyValue(token).trim();
        if (v) raw = v;
      }
    } catch (_e) { /* keep default */ }
    const n = parseFloat(raw);
    return Number.isFinite(n) ? Math.max(0, Math.min(1, n)) : 1;
  };

  /* Per-material mask feature scale (see FLOOR_TEXTURE_MASK_SCALE_BY_TYPE): a theme token
     `--evcc-floor-<type>-map-scale` overrides the per-type default, which overrides the global.
     Clamped to a sane range so a bad value can't explode the tiling. */
  proto._resolveFloorScale = function (floorType, host) {
    let s = FLOOR_TEXTURE_MASK_SCALE_BY_TYPE[floorType];
    if (!(typeof s === "number" && s > 0)) s = FLOOR_TEXTURE_MASK_SCALE;
    try {
      if (host && typeof getComputedStyle === "function") {
        const v = getComputedStyle(host).getPropertyValue(`--evcc-floor-${floorType}-map-scale`).trim();
        if (v) { const n = parseFloat(v); if (Number.isFinite(n) && n > 0) s = n; }
      }
    } catch (_e) { /* keep default */ }
    return Math.max(0.02, Math.min(2, s));
  };

  /* =========================================================
     VIEW TOGGLE
     ========================================================= */

  proto._bindMapViewToggle = function (root) {
    root.querySelectorAll("[data-action='set-map-view']").forEach((btn) => {
      this.card._on(btn, "click", () => {
        const active = btn.dataset.mapView === "true";
        this.card._state.setMapViewActive(active);

        if (active) {
          this._syncSegmentsFromRooms();
          this._ensureMapSegments();
        }

        this.card._scheduleRender();
      });
    });
  };

  /* =========================================================
     SYNC SEGMENT SELECTION ↔ ROOM ENABLED STATE
     ========================================================= */

  proto._syncSegmentsFromRooms = function () {
    if (!this.card._state.mapSegments().length) return;
    const rooms = this.card._state.getRoomsForActiveMap?.() ?? [];
    this.card._state.clearSegmentSelection();
    [...rooms]
      .filter((r) => r.enabled)
      .sort((a, b) => (a.order ?? 0) - (b.order ?? 0))
      .forEach((r) => this.card._state.enableSegmentForRoom(r.id));
  };

  /* =========================================================
     POLYGON CLICKS
     ========================================================= */

  proto._bindMapPolygons = function (root) {
    root.querySelectorAll("[data-action='toggle-segment']").forEach((el) => {
      let _clickTimer = null;

      this.card._on(el, "click", (e) => {
        // In zone-draw mode the rubber-band owns the map — a tap must not toggle a
        // room (belt-and-suspenders to the CSS pointer-events suppression).
        if (this.card._state.zoneDrawMode?.()) return;
        e.stopPropagation();
        if (this.card._mapDragOccurred) {
          this.card._mapDragOccurred = false;
          return;
        }
        const segmentId = el.dataset.segmentId;
        if (!segmentId) return;

        if (_clickTimer) {
          // Second click within window → treat as double-click → open editor.
          // Runs before the DOM is re-rendered so the element is still live.
          clearTimeout(_clickTimer);
          _clickTimer = null;

          const rooms  = this.card._state.getRoomsForActiveMap?.() ?? [];
          const roomId = this.card._state.roomIdForSegment(segmentId);
          const room   = roomId != null
            ? rooms.find((r) => String(r.id) === String(roomId))
            : null;
          if (room) {
            this.card._state.openRoomEditor(room.mapId, room.id);
            this.card._scheduleRender();
          }
          return;
        }

        // First click — wait to see if a second arrives before acting.
        const wasSelected = this.card._state.isSegmentSelected(segmentId);
        _clickTimer = setTimeout(() => {
          _clickTimer = null;

          this.card._state.toggleSegmentSelected(segmentId);

          const rooms  = this.card._state.getRoomsForActiveMap?.() ?? [];
          const roomId = this.card._state.roomIdForSegment(segmentId);
          const room   = roomId != null
            ? rooms.find((r) => String(r.id) === String(roomId))
            : null;
          if (room) {
            this.card._actions
              .toggleRoomEnabled(room.mapId, room.id, wasSelected)
              .then(() => this.card._scheduleRender())
              .catch((err) => console.error("[eufy-vacuum-command-center] Room sync failed:", err));
          }
          this.card._scheduleRender();
        }, 220);
      });
    });
  };

  /* =========================================================
     MAP TOOLTIP (hover over segment polygons)
     ========================================================= */

  proto._bindMapTooltip = function (root) {
    const tooltip   = root.querySelector(".evcc-map-tooltip");
    const container = root.querySelector(".evcc-map-container");
    if (!tooltip || !container) return;

    const show = (el, e) => {
      const label = el.dataset.label ?? "";
      const hint  = el.dataset.hint  ?? "";
      // Build via textContent, NOT innerHTML. The renderer escapes these into the
      // data-label/data-hint attributes, but reading them back through `.dataset`
      // DECODES the entities — so a room named `<img src=x onerror=...>` would come
      // back raw and execute if re-injected as innerHTML. textContent is inert.
      tooltip.replaceChildren();
      const labelEl = document.createElement("span");
      labelEl.className = "evcc-map-tooltip-label";
      labelEl.textContent = label;
      tooltip.appendChild(labelEl);
      if (hint) {
        const hintEl = document.createElement("span");
        hintEl.className = "evcc-map-tooltip-hint";
        hintEl.textContent = hint;
        tooltip.appendChild(hintEl);
      }
      tooltip.classList.add("evcc-map-tooltip--visible");
      move(e);
    };

    const move = (e) => {
      const rect = container.getBoundingClientRect();
      const x = e.clientX - rect.left + 14;
      const y = e.clientY - rect.top  - tooltip.offsetHeight - 8;
      tooltip.style.left = `${Math.min(x, rect.width  - tooltip.offsetWidth  - 8)}px`;
      tooltip.style.top  = `${Math.max(8, y)}px`;
    };

    const hide = () => tooltip.classList.remove("evcc-map-tooltip--visible");

    root.querySelectorAll("[data-action='toggle-segment']").forEach((el) => {
      this.card._on(el, "pointerenter", (e) => show(el, e));
      this.card._on(el, "pointermove",  (e) => move(e));
      this.card._on(el, "pointerleave", hide);
      this.card._on(el, "click",        hide);
    });
  };

  /* =========================================================
     SELECTION BAR CHIPS
     =========================================================
     Long-press (400ms) or double-click opens the room editor
     for the linked room, if one exists.
     ========================================================= */

  proto._bindMapChips = function (root) {
    root.querySelectorAll("[data-action='map-chip-activate']").forEach((chip) => {
      let _clickTimer = null;

      this.card._on(chip, "click", (e) => {
        e.stopPropagation();
        const roomId = chip.dataset.roomId;
        if (!roomId) return;

        if (_clickTimer) {
          clearTimeout(_clickTimer);
          _clickTimer = null;

          const rooms = this.card._state.getRoomsForActiveMap?.() ?? [];
          const room  = rooms.find((r) => String(r.id) === String(roomId));
          if (room) {
            this.card._state.openRoomEditor(room.mapId, room.id);
            this.card._scheduleRender();
          }
          return;
        }

        _clickTimer = setTimeout(() => { _clickTimer = null; }, 220);
      });
    });
  };

  /* =========================================================
     CONFIGURE MAP ENTRY BUTTON (inline map view → config view)
     ========================================================= */

  proto._bindMapConfigEntry = function (root) {
    root.querySelectorAll("[data-action='open-map-config']").forEach((btn) => {
      this.card._on(btn, "click", () => {
        this._ensureMapSegments();
        this.card.setView(VIEWS.MAP_CONFIG);
      });
    });
  };

  /* =========================================================
     MAP CONFIG VIEW BINDINGS
     ========================================================= */

  proto._bindMapConfig = function (root) {
    // Back button
    root.querySelectorAll("[data-action='map-config-back']").forEach((btn) => {
      this.card._on(btn, "click", () => {
        this.card.setView(VIEWS.ROOMS);
      });
    });

    // Segment selection (config mode)
    root.querySelectorAll("[data-action='config-select-segment']").forEach((el) => {
      this.card._on(el, "click", (e) => {
        e.stopPropagation();
        const segId = el.dataset.segmentId;
        if (!segId) return;

        const current = this.card._state.configSelectedSegmentId();
        this.card._state.setConfigSelectedSegmentId(
          current === segId ? null : segId
        );
        this.card._scheduleRender();
      });
    });

    // Upload buttons — open a fresh in-memory file input on each click.
    //
    // WHY a transient input (not the rendered <input> in the variant row):
    // between input.click() returning and the user actually picking a file,
    // HA pushes state updates (vacuum sync, etc.) that trigger card renders.
    // A render replaces the variant row's innerHTML, orphaning the rendered
    // <input> — when the picker finally fires `change`, browsers may not
    // deliver the event to listeners on the detached element. The picker
    // closes and the upload silently no-ops.
    //
    // Creating the input in-memory (detached from DOM) means no render can
    // touch it. The closure here holds the only reference; it lives long
    // enough for the picker + change event, then GCs once the handler
    // resolves.
    //
    // Idempotency for this button is critical: rebinding stacks click
    // handlers, causing the file picker to open N times per click.
    // card._on() guards against that via a per-event dataset marker.
    root.querySelectorAll("[data-action='upload-map-variant']").forEach((btn) => {
      this.card._on(btn, "click", () => {
        const variant = btn.dataset.variant;

        const input = document.createElement("input");
        input.type = "file";
        input.accept = "image/png,image/jpeg,image/webp,image/bmp";

        const handleChange = async () => {
          input.removeEventListener("change", handleChange);

          const file = input.files?.[0];
          if (!file) return;

          const rooms = this.card._state.getRoomsForActiveMap?.() ?? [];
          const mapId = rooms[0]?.mapId
            ?? this.card._state.mapSegmentsData()?.map_id ?? null;
          if (!mapId) {
            this.card._state.setMapActionStatus({
              type: "upload", variant, status: "error",
              message: this.t("bind_map.no_active_map"),
            });
            this.card._scheduleRender();
            return;
          }

          this.card._state.setMapActionStatus({ type: "upload", variant, status: "busy" });
          this.card._scheduleRender();

          try {
            // Fit the image under HA's websocket frame limit before sending.
            // CV variants (dark/light/default) feed the segmenter, so they are
            // passed through untouched if they fit and hard-fail otherwise (a
            // silent rescale would desync the dark/light alignment and drop small
            // rooms); custom backdrops are display-only, so they downscale +
            // recompress (alpha-safe) to fit.
            const isCustom = variant.startsWith("custom");
            const fitted = await _imageFileToFittedBase64(
              file,
              isCustom ? { maxDim: 2048, allowDownscale: true } : { allowDownscale: false },
            );
            if (!fitted) throw new Error(this.t("bind_map.could_not_prepare_image"));
            const base64 = fitted.base64;
            // A custom backdrop targets the ACTIVE layout (custom_<id> variant);
            // the server forces the variant key from layout_id.
            const opts = { variant };
            if (isCustom) {
              const lid = this.card._state.activeCustomLayoutId?.();
              if (lid) opts.layout_id = lid;
            }
            await this.card._actions.uploadMapImage(mapId, base64, opts);
            // CV variants (dark/light/default) drive segmentation, so an upload
            // kicks off analyze — the long Pillow/SciPy step (10-30s typical);
            // keeping the variant in the status stops the button reverting to
            // "Upload" while work continues. The "custom" backdrop is a no-CV
            // tracing image and is NEVER segmented, so skip analyze for it.
            if (!variant.startsWith("custom")) {
              this.card._state.setMapActionStatus({ type: "analyze", variant, status: "busy" });
              this.card._scheduleRender();
              await this.card._actions.analyzeMapImage(mapId, { force_reanalyze: true });
            }
            await this.card._actions.getMapSegments(mapId);
            this.card._state.clearMapActionStatus();
            this.card._scheduleRender();
          } catch (err) {
            console.error("[eufy-vacuum-command-center] Map upload failed:", err);
            this.card._state.setMapActionStatus({
              type: "upload", variant, status: "error",
              message: _uploadErrorMessage(err, this.tRaw.bind(this)),
            });
            this.card._scheduleRender();
          }
        };

        input.addEventListener("change", handleChange);
        input.click();
      });
    });

    // Delete a single uploaded variant — two-tap guard. First click
    // arms the variant; second click within the auto-clear window
    // actually fires the service. Refetches segments so the IMAGE
    // VARIANTS section reflects the removal immediately. Does NOT
    // re-run analysis; the existing segmentation cache is left alone.
    root.querySelectorAll("[data-action='delete-map-variant']").forEach((btn) => {
      this.card._on(btn, "click", async () => {
        const variant = btn.dataset.variant;
        const rooms = this.card._state.getRoomsForActiveMap?.() ?? [];
        const mapId = rooms[0]?.mapId ?? null;
        if (!variant || !mapId) return;

        // First click on this variant — arm it and bail. The
        // confirmation registry handles the 5s auto-clear and the
        // re-render that follows (renderTrigger wired in main.js).
        // The shim enforces single-arm semantics; any sibling
        // variant arm is dropped automatically.
        if (!this.card._state.isMapVariantDeleteArmed?.(variant)) {
          this.card._state.armMapVariantDelete?.(variant);
          this.card._scheduleRender();
          return;
        }

        // Second click — actually delete. Drop the arm (registry
        // cancels its auto-clear timer internally).
        this.card._state.clearMapVariantDeleteArm?.();

        this.card._state.setMapActionStatus?.({
          type: "delete", variant, status: "busy",
        });
        this.card._scheduleRender();

        try {
          const result = await this.card._actions.deleteMapImage(mapId, variant);
          await this.card._actions.getMapSegments(mapId);
          this.card._state.clearMapActionStatus?.();

          const ok = result && result.deleted !== false;
          this.card.showToast?.(
            ok ? this.t("bind_map.variant_image_deleted", { variant: `${variant.charAt(0).toUpperCase()}${variant.slice(1)}` })
               : this.t("bind_map.could_not_delete_variant_image", { variant }),
            { kind: ok ? "success" : "error" }
          );
        } catch (err) {
          console.error("[eufy-vacuum-command-center] deleteMapImage failed:", err);
          this.card._state.setMapActionStatus?.({
            type: "delete", variant, status: "error",
            message: err?.message ?? this.t("bind_map.delete_failed"),
          });
          this.card.showToast?.(this.t("bind_map.could_not_delete_variant_image", { variant }), { kind: "error" });
        }

        this.card._scheduleRender();
      });
    });

    // Cancel an armed delete (inline Cancel button next to the
    // pulsing "Confirm Delete" chip).
    root.querySelectorAll("[data-action='cancel-delete-map-variant']").forEach((btn) => {
      this.card._on(btn, "click", () => {
        if (this.card._mapVariantDeleteArmTimer) {
          clearTimeout(this.card._mapVariantDeleteArmTimer);
          this.card._mapVariantDeleteArmTimer = null;
        }
        this.card._state.clearMapVariantDeleteArm?.();
        this.card._scheduleRender();
      });
    });

    // Analyse button
    root.querySelectorAll("[data-action='analyze-map']").forEach((btn) => {
      this.card._on(btn, "click", async () => {
        const rooms = this.card._state.getRoomsForActiveMap?.() ?? [];
        const mapId = rooms[0]?.mapId ?? null;
        if (!mapId) return;

        this.card._state.setMapActionStatus({ type: "analyze", status: "busy" });
        this.card._scheduleRender();

        try {
          await this.card._actions.analyzeMapImage(mapId, { force_reanalyze: true });
          await this.card._actions.getMapSegments(mapId);
          this.card._state.clearMapActionStatus();
          this.card._scheduleRender();
        } catch (err) {
          console.error("[eufy-vacuum-command-center] Map analysis failed:", err);
          this.card._state.setMapActionStatus({
            type: "analyze", status: "error",
            message: err?.message ?? this.t("bind_map.analysis_failed"),
          });
          this.card._scheduleRender();
        }
      });
    });

    // CV/Custom segmentation toggle
    root.querySelectorAll("[data-action='set-segmentation-mode']").forEach((btn) => {
      this.card._on(btn, "click", async () => {
        const mode  = btn.dataset.mode;
        const mapId = this.card._state.mapSegmentsData()?.map_id
          ?? this.card._state.activeMapId?.() ?? null;
        if (!mode || !mapId) return;
        if (this.card._state.segmentationMode?.() === mode) return; // already there
        try {
          await this.card._actions.setSegmentationMode(mapId, mode);
          await this.card._actions.getMapSegments(mapId);
          if (this.card._state.mapSegmentsData()) this.card._scheduleRender();
        } catch (err) {
          console.error("[eufy-vacuum-command-center] segmentation mode toggle failed:", err);
        }
      });
    });

    // Custom-layout picker: activate a layout (swaps backdrop + rooms + mascot home)
    const _mapId = () => this.card._state.mapSegmentsData()?.map_id ?? this.card._state.activeMapId?.() ?? null;
    root.querySelectorAll("[data-action='set-active-custom-layout']").forEach((btn) => {
      this.card._on(btn, "click", async () => {
        const mapId = _mapId();
        const layoutId = btn.dataset.layoutId;
        if (!mapId || !layoutId) return;
        try {
          await this.card._actions.setActiveCustomLayout(mapId, layoutId);
          await this.card._actions.getMapSegments(mapId);
          this.card._scheduleRender();
        } catch (err) {
          console.error("[eufy-vacuum-command-center] set active layout failed:", err);
        }
      });
    });

    // "Live map" source — select the live-pinned layout, or create one. Lets the
    // composer draw rooms straight over the live camera/image backdrop.
    root.querySelectorAll("[data-action='select-or-create-live-layout']").forEach((btn) => {
      this.card._on(btn, "click", async () => {
        const mapId = _mapId();
        if (!mapId) return;
        try {
          const existing = (this.card._state.customLayouts?.() ?? [])
            .find((l) => l.backdrop_source === "live");
          if (existing) {
            await this.card._actions.setActiveCustomLayout(mapId, existing.id);
          } else {
            await this.card._actions.createCustomLayout(mapId, "Live map", { backdropSource: "live" });
          }
          await this.card._actions.getMapSegments(mapId);
          this.card._scheduleRender();
        } catch (err) {
          console.error("[eufy-vacuum-command-center] live-map layout failed:", err);
        }
      });
    });

    // Custom-layout editor: open (new / rename), cancel, name input
    root.querySelectorAll("[data-action='open-new-layout']").forEach((btn) => {
      this.card._on(btn, "click", () => { this.card._state.openNewLayoutEditor(); this.card._scheduleRender(); });
    });
    root.querySelectorAll("[data-action='open-rename-layout']").forEach((btn) => {
      this.card._on(btn, "click", () => { this.card._state.openRenameLayoutEditor(); this.card._scheduleRender(); });
    });
    root.querySelectorAll("[data-action='cancel-layout-editor']").forEach((btn) => {
      this.card._on(btn, "click", () => { this.card._state.closeLayoutEditor(); this.card._scheduleRender(); });
    });
    root.querySelectorAll("[data-layout-field='name']").forEach((inp) => {
      this.card._on(inp, "input", () => { this.card._state.setLayoutDraftName(inp.value); });
    });

    // Custom-layout create
    root.querySelectorAll("[data-action='create-layout-save']").forEach((btn) => {
      this.card._on(btn, "click", async () => {
        const mapId = _mapId();
        if (!mapId) return;
        const name = (this.card._state.layoutDraftName?.() ?? "").trim();
        try {
          await this.card._actions.createCustomLayout(mapId, name);
          this.card._state.closeLayoutEditor();
          await this.card._actions.getMapSegments(mapId);
          this.card._scheduleRender();
        } catch (err) {
          console.error("[eufy-vacuum-command-center] create layout failed:", err);
        }
      });
    });

    // Custom-layout rename
    root.querySelectorAll("[data-action='rename-layout-save']").forEach((btn) => {
      this.card._on(btn, "click", async () => {
        const mapId = _mapId();
        const layoutId = this.card._state.activeCustomLayoutId?.();
        const name = (this.card._state.layoutDraftName?.() ?? "").trim();
        if (!mapId || !layoutId || !name) return;
        try {
          await this.card._actions.renameCustomLayout(mapId, layoutId, name);
          this.card._state.closeLayoutEditor();
          await this.card._actions.getMapSegments(mapId);
          this.card._scheduleRender();
        } catch (err) {
          console.error("[eufy-vacuum-command-center] rename layout failed:", err);
        }
      });
    });

    // Custom-layout delete
    root.querySelectorAll("[data-action='delete-layout']").forEach((btn) => {
      this.card._on(btn, "click", async () => {
        const mapId = _mapId();
        const layoutId = this.card._state.activeCustomLayoutId?.();
        if (!mapId || !layoutId) return;
        try {
          await this.card._actions.deleteCustomLayout(mapId, layoutId);
          await this.card._actions.getMapSegments(mapId);
          this.card._scheduleRender();
        } catch (err) {
          console.error("[eufy-vacuum-command-center] delete layout failed:", err);
        }
      });
    });

    // Composer: add a shape
    root.querySelectorAll("[data-action='compose-add']").forEach((btn) => {
      this.card._on(btn, "click", () => {
        this.card._state.addComposeShape(btn.dataset.shapeType || "rect");
        this.card._scheduleRender();
      });
    });

    // Composer: select a shape — or, mid-merge, fold it into the merge target.
    root.querySelectorAll("[data-action='compose-select']").forEach((el) => {
      this.card._on(el, "click", () => {
        const tapped = el.dataset.shapeId;
        const mergeFrom = this.card._state.composeMergeFrom?.();
        if (mergeFrom && mergeFrom !== tapped) {
          this.card._state.mergeComposeShapes(mergeFrom, tapped);
          this.card._state.cancelComposeMerge();
          this.card._state.selectComposeShape(mergeFrom);  // keep the target selected
        } else {
          this.card._state.selectComposeShape(tapped);
        }
        this.card._scheduleRender();
      });
    });

    // Composer: deselect (stop editing the current shape)
    root.querySelectorAll("[data-action='compose-deselect']").forEach((btn) => {
      this.card._on(btn, "click", () => {
        this.card._state.selectComposeShape(null);
        this.card._scheduleRender();
      });
    });

    // Composer: link the selected shape to a room
    root.querySelectorAll("[data-action='compose-assign-room']").forEach((btn) => {
      this.card._on(btn, "click", () => {
        this.card._state.assignComposeRoom(btn.dataset.shapeId, btn.dataset.roomId);
        this.card._scheduleRender();
      });
    });

    // Composer: save the draft as custom segments (replace-all)
    root.querySelectorAll("[data-action='compose-save']").forEach((btn) => {
      this.card._on(btn, "click", async () => {
        const mapId = this.card._state.mapSegmentsData()?.map_id
          ?? this.card._state.activeMapId?.() ?? null;
        if (!mapId) return;
        const segments = this.card._state.composeToSegments();
        if (!segments.length) return;
        this.card._state.setMapActionStatus?.({ type: "compose-save", status: "busy" });
        this.card._scheduleRender();
        try {
          // Backend payload is id + primitives only; room_id rides separately.
          const backendSegments = segments.map((seg) => ({ id: seg.id, primitives: seg.primitives }));
          // Live-image-backed layout (no uploaded backdrop): hand the saver the
          // rendered live image's NATURAL pixel size so it can rasterise the pct
          // shapes (the live URL carries no dimensions). Harmless when an uploaded
          // backdrop exists — the backend prefers the stored variant's dims.
          const liveImg = root.querySelector(".evcc-map-image");
          const backdropDims = (liveImg && liveImg.naturalWidth > 0)
            ? { width: liveImg.naturalWidth, height: liveImg.naturalHeight }
            : null;
          const res = await this.card._actions.setCustomSegments(mapId, backendSegments, backdropDims);
          // The segmenter rasterises onto THIS layout's backdrop; with none uploaded
          // AND no live image loaded it bails (saved:false). Surface that instead of
          // silently saving room links onto segments that never persisted.
          if (!res?.saved) {
            const reason = res?.reason === "no_custom_backdrop"
              ? this.t("bind_map.map_image_still_loading")
              : (res?.reason ? this.t("bind_map.save_failed_reason", { reason: res.reason }) : this.t("bind_map.save_failed"));
            this.card._state.setMapActionStatus?.({
              type: "compose-save", status: "error", message: reason,
            });
            this.card._scheduleRender();
            return;
          }
          // Reconcile room links per SEGMENT (= group), not per shape — a merged
          // room is one segment whose id is the group id.
          for (const seg of segments) {
            await this.card._actions.setSegmentRoomLink(mapId, seg.id, seg.room_id ?? null);
          }
          await this.card._actions.getMapSegments(mapId);
          this.card._state.clearMapActionStatus?.();
          this.card._scheduleRender();
        } catch (err) {
          console.error("[eufy-vacuum-command-center] save custom segments failed:", err);
          this.card._state.setMapActionStatus?.({
            type: "compose-save", status: "error",
            message: err?.message ?? this.t("bind_map.save_failed"),
          });
          this.card._scheduleRender();
        }
      });
    });

    // Composer: delete the selected shape
    root.querySelectorAll("[data-action='compose-delete']").forEach((btn) => {
      this.card._on(btn, "click", () => {
        const id = this.card._state.composeSelectedId();
        if (!id) return;
        this.card._state.deleteComposeShape(id);
        this.card._scheduleRender();
      });
    });

    // Composer: clear the whole draft
    root.querySelectorAll("[data-action='compose-clear']").forEach((btn) => {
      this.card._on(btn, "click", () => {
        this.card._state.clearComposeDraft();
        this.card._scheduleRender();
      });
    });

    // Composer: nudge step size (Fine/Med/Coarse)
    root.querySelectorAll("[data-action='compose-step']").forEach((btn) => {
      this.card._on(btn, "click", () => {
        this.card._state.setComposeStep(Number(btn.dataset.step ?? 3));
        this.card._scheduleRender();
      });
    });

    // Composer: move scope (whole room vs single piece) for merged shapes
    root.querySelectorAll("[data-action='compose-move-scope']").forEach((btn) => {
      this.card._on(btn, "click", () => {
        this.card._state.setComposeMoveScope(btn.dataset.scope);
        this.card._scheduleRender();
      });
    });

    // Composer: move the selected shape by the current step
    root.querySelectorAll("[data-action='compose-move']").forEach((btn) => {
      this.card._on(btn, "click", () => {
        const id = this.card._state.composeSelectedId();
        if (!id) return;
        const step = this.card._state.composeStep?.() ?? 3;
        this.card._state.moveComposeScoped(
          id, Number(btn.dataset.dx ?? 0) * step, Number(btn.dataset.dy ?? 0) * step,
        );
        this.card._scheduleRender();
      });
    });

    // Composer: scale the selected shape (uniform, about its centre)
    root.querySelectorAll("[data-action='compose-scale']").forEach((btn) => {
      this.card._on(btn, "click", () => {
        const id = this.card._state.composeSelectedId();
        if (!id) return;
        this.card._state.scaleComposeShape(id, Number(btn.dataset.factor ?? 1));
        this.card._scheduleRender();
      });
    });

    // Composer: resize the selected rectangle (per side) by the current step
    root.querySelectorAll("[data-action='compose-resize']").forEach((btn) => {
      this.card._on(btn, "click", () => {
        const id = this.card._state.composeSelectedId();
        if (!id) return;
        const step = this.card._state.composeStep?.() ?? 3;
        this.card._state.resizeComposeShape(id, btn.dataset.dim, Number(btn.dataset.delta ?? 0) * step);
        this.card._scheduleRender();
      });
    });

    // Composer: rotate the selected shape
    root.querySelectorAll("[data-action='compose-rotate']").forEach((btn) => {
      this.card._on(btn, "click", () => {
        const id = this.card._state.composeSelectedId();
        if (!id) return;
        this.card._state.rotateComposeShape(id, Number(btn.dataset.deg ?? 0));
        this.card._scheduleRender();
      });
    });

    // Composer: start a merge (then the next shape-tap folds into this one)
    root.querySelectorAll("[data-action='compose-merge-start']").forEach((btn) => {
      this.card._on(btn, "click", () => {
        const id = this.card._state.composeSelectedId();
        if (!id) return;
        this.card._state.startComposeMerge(id);
        this.card._scheduleRender();
      });
    });

    // Composer: cancel a pending merge
    root.querySelectorAll("[data-action='compose-merge-cancel']").forEach((btn) => {
      this.card._on(btn, "click", () => {
        this.card._state.cancelComposeMerge();
        this.card._scheduleRender();
      });
    });

    // Composer: split the selected shape back out of its merged room
    root.querySelectorAll("[data-action='compose-split']").forEach((btn) => {
      this.card._on(btn, "click", () => {
        const id = this.card._state.composeSelectedId();
        if (!id) return;
        this.card._state.splitComposeShape(id);
        this.card._scheduleRender();
      });
    });

    // Composer: toggle the selected shape between fill and cutout
    root.querySelectorAll("[data-action='compose-toggle-op']").forEach((btn) => {
      this.card._on(btn, "click", () => {
        const id = this.card._state.composeSelectedId();
        if (!id) return;
        this.card._state.toggleComposeOp(id);
        this.card._scheduleRender();
      });
    });

    // Composer: tap the map to drop the selected shape there (coarse placement).
    // Hooks the config canvas's click; bails on shape-taps (those select) and on
    // taps that were really a pan-drag (_mapDragOccurred).
    const composeLayers = root.querySelector(".evcc-map-container--config .evcc-map-layers");
    if (composeLayers) {
      this.card._on(composeLayers, "click", (e) => {
        if ((this.card._state.segmentationMode?.() ?? "cv") !== "custom") return;
        // An empty-canvas tap while merging cancels the merge (rather than placing).
        if (this.card._state.composeMergeFrom?.()) {
          this.card._state.cancelComposeMerge();
          this.card._scheduleRender();
          return;
        }
        const id = this.card._state.composeSelectedId?.();
        if (!id) return;
        if (e.target?.closest?.("[data-action='compose-select']")) return;
        // A press that landed on the furnished-art drag layer is an art move, not a
        // shape placement — let its own handler own it.
        if (e.target?.closest?.("[data-action='furnished-art-drag']")) return;
        if (this.card._mapDragOccurred) { this.card._mapDragOccurred = false; return; }
        const r = composeLayers.getBoundingClientRect();
        if (!r.width || !r.height) return;
        // Config content is now wrapped in .evcc-map-content-rotator (D5), so convert the
        // pointer% -> CONTENT% via unrotatePct (matches the room-view tap + the art drag);
        // identity at rotation 0 (the prior un-rotated behaviour).
        const rot = this.card._state.effectiveMapRotation?.()
          ? (this.card._state.isLiveBackdropActive?.() ? this.card._state.effectiveMapRotation() : 0)
          : 0;
        const [pcx, pcy] = this.card._state.unrotatePct(
          ((e.clientX - r.left) / r.width) * 100,
          ((e.clientY - r.top) / r.height) * 100,
          rot,
        );
        this.card._state.placeComposeScoped(id, pcx, pcy);
        this.card._scheduleRender();
      });
    }

    // Nudge buttons
    root.querySelectorAll("[data-action='nudge-segment']").forEach((btn) => {
      this.card._on(btn, "click", async () => {
        const segId = btn.dataset.segmentId;
        const dx    = Number(btn.dataset.dx ?? 0);
        const dy    = Number(btn.dataset.dy ?? 0);
        const rooms = this.card._state.getRoomsForActiveMap?.() ?? [];
        const mapId = rooms[0]?.mapId ?? this.card._state.activeMapId?.() ?? null;
        if (!segId || !mapId) return;

        try {
          await this.card._actions.adjustMapSegment(mapId, segId, { delta_x: dx, delta_y: dy });
          await this.card._actions.getMapSegments(mapId);
          if (this.card._state.mapSegmentsData()) this.card._scheduleRender();
        } catch (err) {
          console.error("[eufy-vacuum-command-center] Nudge failed:", err);
        }
      });
    });

    // Reset adjustment
    root.querySelectorAll("[data-action='reset-segment-adjustment']").forEach((btn) => {
      this.card._on(btn, "click", async () => {
        const segId = btn.dataset.segmentId;
        const rooms = this.card._state.getRoomsForActiveMap?.() ?? [];
        const mapId = rooms[0]?.mapId ?? this.card._state.activeMapId?.() ?? null;
        if (!segId || !mapId) return;

        const seg = this.card._state.mapSegments().find(
          (s) => String(s.segment_id) === String(segId)
        );
        if (!seg) return;

        const raw = seg.translation_offset;
        const ox  = Array.isArray(raw) ? (raw[0] ?? 0) : (raw?.x ?? 0);
        const oy  = Array.isArray(raw) ? (raw[1] ?? 0) : (raw?.y ?? 0);
        if (ox === 0 && oy === 0) return;

        try {
          await this.card._actions.adjustMapSegment(mapId, segId, {
            delta_x: -ox,
            delta_y: -oy,
          });
          await this.card._actions.getMapSegments(mapId);
          if (this.card._state.mapSegmentsData()) this.card._scheduleRender();
        } catch (err) {
          console.error("[eufy-vacuum-command-center] Reset failed:", err);
        }
      });
    });

    // Edge adjust buttons
    root.querySelectorAll("[data-action='adjust-edge']").forEach((btn) => {
      this.card._on(btn, "click", async () => {
        const segId  = btn.dataset.segmentId;
        const edge   = btn.dataset.edge;
        const delta  = Number(btn.dataset.delta ?? 0);
        const rooms  = this.card._state.getRoomsForActiveMap?.() ?? [];
        const mapId  = rooms[0]?.mapId ?? this.card._state.activeMapId?.() ?? null;
        if (!segId || !mapId || !edge) return;
        const param  = { [`edge_${edge}`]: delta };
        try {
          await this.card._actions.adjustMapSegment(mapId, segId, param);
          await this.card._actions.getMapSegments(mapId);
          const result = this.card._state.mapSegmentsData();
          if (result) this.card._scheduleRender();
        } catch (err) {
          console.error("[eufy-vacuum-command-center] Edge adjust failed:", err);
        }
      });
    });

    // Vertex select
    root.querySelectorAll("[data-action='select-vertex']").forEach((btn) => {
      this.card._on(btn, "click", (e) => {
        e.stopPropagation();
        const idx = Number(btn.dataset.vertexIndex);
        const cur = this.card._state.configSelectedVertexIndex?.();
        this.card._state.setConfigSelectedVertexIndex(cur === idx ? null : idx);
        this.card._scheduleRender();
      });
    });

    // Vertex nudge
    root.querySelectorAll("[data-action='nudge-vertex']").forEach((btn) => {
      this.card._on(btn, "click", async () => {
        const segId  = btn.dataset.segmentId;
        const idx    = Number(btn.dataset.vertexIndex);
        const dx     = Number(btn.dataset.dx ?? 0);
        const dy     = Number(btn.dataset.dy ?? 0);
        const rooms  = this.card._state.getRoomsForActiveMap?.() ?? [];
        const mapId  = rooms[0]?.mapId ?? this.card._state.activeMapId?.() ?? null;
        if (!segId || !mapId) return;
        try {
          await this.card._actions.adjustMapSegment(mapId, segId, {
            vertex_moves: [{ index: idx, delta_x: dx, delta_y: dy }],
          });
          await this.card._actions.getMapSegments(mapId);
          const result = this.card._state.mapSegmentsData();
          if (result) this.card._scheduleRender();
        } catch (err) {
          console.error("[eufy-vacuum-command-center] Vertex nudge failed:", err);
        }
      });
    });

    // Vertex reset
    root.querySelectorAll("[data-action='reset-vertex']").forEach((btn) => {
      this.card._on(btn, "click", async () => {
        const segId  = btn.dataset.segmentId;
        const idx    = Number(btn.dataset.vertexIndex);
        const rooms  = this.card._state.getRoomsForActiveMap?.() ?? [];
        const mapId  = rooms[0]?.mapId ?? this.card._state.activeMapId?.() ?? null;
        if (!segId || !mapId) return;
        const seg = this.card._state.mapSegments().find(
          (s) => String(s.segment_id) === String(segId)
        );
        const cur = (seg?.vertex_adjustment ?? []).find((v) => v.index === idx);
        if (!cur || (!cur.delta_x && !cur.delta_y)) return;
        try {
          await this.card._actions.adjustMapSegment(mapId, segId, {
            vertex_moves: [{ index: idx, delta_x: -(cur.delta_x ?? 0), delta_y: -(cur.delta_y ?? 0) }],
          });
          await this.card._actions.getMapSegments(mapId);
          const result = this.card._state.mapSegmentsData();
          if (result) this.card._scheduleRender();
        } catch (err) {
          console.error("[eufy-vacuum-command-center] Vertex reset failed:", err);
        }
      });
    });

    // Room assignment chips. Optimistic local update + backend save
    // via the new set_segment_room_link service. State and action
    // live on different objects (state.assignSegmentRoom is
    // local-only; card._actions.setSegmentRoomLink persists), so the
    // binding orchestrates both.
    root.querySelectorAll("[data-action='assign-segment-room']").forEach((btn) => {
      this.card._on(btn, "click", () => {
        const segId  = btn.dataset.segmentId;
        const roomId = btn.dataset.roomId;
        if (!segId || !roomId) return;

        const state = this.card._state;
        const current = state.roomIdForSegment(segId);
        const mapId   = state.mapSegmentsData()?.map_id;

        if (current != null && String(current) === String(roomId)) {
          state.unassignSegmentRoom(segId);
          if (mapId) this.card._actions?.setSegmentRoomLink?.(mapId, segId, null);
        } else {
          state.assignSegmentRoom(segId, roomId);
          if (mapId) this.card._actions?.setSegmentRoomLink?.(mapId, segId, roomId);
        }
        this.card._scheduleRender();
      });
    });
  };

  /* =========================================================
     SEGMENT FETCH HELPER
     ========================================================= */

  proto._ensureMapSegments = async function () {
    if (this.card._state.mapSegmentsData()) return;
    if (this._mapSegmentsFetching) return;

    const rooms = this.card._state.getRoomsForActiveMap?.() ?? [];
    const mapId = rooms[0]?.mapId ?? this.card._state.activeMapId?.() ?? null;
    if (!mapId) return;

    this._mapSegmentsFetching = true;
    try {
      await this.card._actions.getMapSegments(mapId);
      if (this.card._state.mapSegmentsData()) {
        this._syncSegmentsFromRooms();
        this.card._scheduleRender();
      }
    } catch (err) {
      console.error("[eufy-vacuum-command-center] Failed to load map segments:", err);
    } finally {
      this._mapSegmentsFetching = false;
    }
  };

/* =========================================================
   ANIMAL COMPANION
   =========================================================
   Drag the animal icon to reposition it on the map.
   Uses pointer capture so the drag tracks reliably even when
   the pointer moves outside the element.

   Animal selector (<select>) → persist choice + re-render.
   ========================================================= */

  proto._bindMapAnimalSelect = function (root) {
    root.querySelectorAll("[data-action='map-animal-select']").forEach((sel) => {
      this.card._on(sel, "change", () => {
        this.card._state.setMapAnimalSelection?.(sel.value);
        this.card._scheduleRender();
      });
    });
    // Mascot on/off
    root.querySelectorAll("[data-action='map-animal-toggle']").forEach((btn) => {
      this.card._on(btn, "click", () => {
        this.card._state.toggleMapAnimalEnabled?.();
        this.card._scheduleRender();
      });
    });
    // Mascot follows the live robot position (replaces the dot) vs. room/dock homing.
    root.querySelectorAll("[data-action='map-animal-follow-toggle']").forEach((btn) => {
      this.card._on(btn, "click", () => {
        this.card._state.toggleMapAnimalFollowsRobot?.();
        this.card._scheduleRender();
      });
    });
    // Floor textures on/off — map polygons and room cards toggle independently.
    root.querySelectorAll("[data-action='map-texture-toggle']").forEach((btn) => {
      this.card._on(btn, "click", () => {
        this.card._state.toggleMapFloorTextureEnabled?.();
        this.card._scheduleRender();
      });
    });
    root.querySelectorAll("[data-action='room-texture-toggle']").forEach((btn) => {
      this.card._on(btn, "click", () => {
        this.card._state.toggleRoomFloorTextureEnabled?.();
        this.card._scheduleRender();
      });
    });
    // Room labels on/off — VA's own map labels. Hide them to avoid stacking on a
    // live backdrop (e.g. the eufy-clean camera) that already bakes in its labels.
    root.querySelectorAll("[data-action='map-labels-toggle']").forEach((btn) => {
      this.card._on(btn, "click", () => {
        this.card._state.toggleMapRoomLabelsEnabled?.();
        this.card._scheduleRender();
      });
    });
    root.querySelectorAll("[data-action='map-animal-scale']").forEach((slider) => {
      // input fires continuously while dragging — update state live.
      // change fires when the thumb is released — schedule a render then.
      this.card._on(slider, "input", () => {
        this.card._state.setMapAnimalScale?.(slider.value);
        // Live-update the animal element dimensions without a full re-render
        // so the icon resizes smoothly as the slider moves.
        const animal = root.querySelector(".evcc-map-animal");
        const svg    = animal?.querySelector("animal-svg");
        if (animal && svg) {
          const scale = parseFloat(slider.value) || 1;
          const W = Math.round(64 * scale) + "px";
          const H = Math.round(44 * scale) + "px";
          animal.style.width  = W;
          animal.style.height = H;
          svg.setAttribute("width",  W);
          svg.setAttribute("height", H);
        }
      });
      this.card._on(slider, "change", () => {
        this.card._scheduleRender();
      });
    });
  };

  proto._bindMapAnimal = function (root) {
    root.querySelectorAll("[data-action='map-dot-click']").forEach((el) => {
      const layers = root.querySelector(".evcc-map-layers");
      if (!layers) return;

      this.card._on(el, "pointerdown", (e) => {
        if (e.button !== 0) return;
        // In zone-draw mode the rubber-band owns the press — don't let the mascot
        // swallow a drag that happens to start over the floating animal.
        if (this.card._state.zoneDrawMode?.()) return;
        e.stopPropagation();   // prevent the pan handler from starting a drag
        e.preventDefault();    // prevent text selection, browser scroll takeover

        const anchorKey = el.dataset.anchorKey;
        if (!anchorKey) return;

        // Capture all subsequent pointer events on this element so the drag
        // stays smooth even if the pointer leaves the element bounds.
        el.setPointerCapture(e.pointerId);
        el.classList.add("evcc-map-animal--dragging");

        // Snapshot the layers bounding rect in visual (post-transform) space.
        // getBoundingClientRect() accounts for zoom/pan transform, and dividing
        // by the visual dimension gives the correct pct in natural space.
        const layerRect = layers.getBoundingClientRect();

        // The mascot lives INSIDE .evcc-map-content-rotator (rotated by the live-map
        // rotation), but the pointer is in the unrotated .evcc-map-layers frame. Convert
        // pointer% -> CONTENT% via unrotatePct before placing/storing the anchor —
        // otherwise a 90/270 drag tracks (and persists) at the wrong spot. Identity at 0.
        const rot = this.card._state.effectiveMapRotation?.() ?? 0;
        const ptrContentPct = (clientX, clientY) =>
          this.card._state.unrotatePct(
            (clientX - layerRect.left) / layerRect.width  * 100,
            (clientY - layerRect.top)  / layerRect.height * 100,
            rot,
          );

        // Grab offset in CONTENT% so the icon doesn't snap its centre to the grab point.
        const curPctX = parseFloat(el.style.left) || 0;
        const curPctY = parseFloat(el.style.top)  || 0;
        const [grabX, grabY] = ptrContentPct(e.clientX, e.clientY);
        const grabOffX = grabX - curPctX;
        const grabOffY = grabY - curPctY;

        // Track live position so pointercancel can save the last known good spot.
        let livePctX = curPctX;
        let livePctY = curPctY;

        const onMove = (ev) => {
          const [cx, cy] = ptrContentPct(ev.clientX, ev.clientY);
          livePctX = Math.max(0, Math.min(100, cx - grabOffX));
          livePctY = Math.max(0, Math.min(100, cy - grabOffY));
          el.style.left = `${livePctX}%`;
          el.style.top  = `${livePctY}%`;
        };

        const finish = () => {
          el.removeEventListener("pointermove",   onMove);
          el.removeEventListener("pointerup",     finish);
          el.removeEventListener("pointercancel", finish);
          el.classList.remove("evcc-map-animal--dragging");
          // Optimistic local update + backend save (same orchestration
          // pattern as assign-segment-room — state has no card ref,
          // and actions live on card._actions).
          this.card._state.setRoomDotAnchor?.(anchorKey, livePctX, livePctY);
          const mapId = this.card._state.mapSegmentsData()?.map_id;
          if (mapId && anchorKey != null) {
            this.card._actions?.setCompanionAnchor?.(
              mapId, anchorKey, livePctX, livePctY,
            );
          }
          this.card._scheduleRender();
        };

        el.addEventListener("pointermove",   onMove);
        el.addEventListener("pointerup",     finish);
        el.addEventListener("pointercancel", finish);
      });
    });
  };

  /**
   * Drag a room's area (m²) chip off its name label. Mirrors the mascot-anchor drag exactly:
   * rotation-aware pointer→content% conversion, grab offset so it doesn't snap, optimistic
   * local update + backend persist on drop. The chip is positioned in map-content-box % (the
   * same frame the renderer uses), keyed by room number, stored map-level.
   */
  proto._bindAreaLabelDrag = function (root) {
    root.querySelectorAll("[data-action='area-label-drag']").forEach((el) => {
      const layers = root.querySelector(".evcc-map-layers");
      if (!layers) return;

      this.card._on(el, "pointerdown", (e) => {
        if (e.button !== 0) return;
        // Don't swallow a rubber-band (zone/hide draw) that starts over a chip.
        if (this.card._state.zoneDrawMode?.() || this.card._state.hideDrawMode?.()) return;
        e.stopPropagation();   // keep the pan handler from starting a drag
        e.preventDefault();

        const roomKey = el.dataset.room;
        if (roomKey == null || roomKey === "") return;

        el.setPointerCapture(e.pointerId);
        el.classList.add("evcc-map-ov-area--dragging");

        const layerRect = layers.getBoundingClientRect();
        const rot = this.card._state.effectiveMapRotation?.() ?? 0;
        const ptrContentPct = (clientX, clientY) =>
          this.card._state.unrotatePct(
            (clientX - layerRect.left) / layerRect.width  * 100,
            (clientY - layerRect.top)  / layerRect.height * 100,
            rot,
          );

        const curPctX = parseFloat(el.style.left) || 0;
        const curPctY = parseFloat(el.style.top)  || 0;
        const [grabX, grabY] = ptrContentPct(e.clientX, e.clientY);
        const grabOffX = grabX - curPctX;
        const grabOffY = grabY - curPctY;
        let livePctX = curPctX;
        let livePctY = curPctY;
        let moved = false;

        const onMove = (ev) => {
          const [cx, cy] = ptrContentPct(ev.clientX, ev.clientY);
          livePctX = Math.max(0, Math.min(100, cx - grabOffX));
          livePctY = Math.max(0, Math.min(100, cy - grabOffY));
          moved = true;
          el.style.left = `${livePctX}%`;
          el.style.top  = `${livePctY}%`;
        };

        const finish = () => {
          el.removeEventListener("pointermove",   onMove);
          el.removeEventListener("pointerup",     finish);
          el.removeEventListener("pointercancel", finish);
          el.classList.remove("evcc-map-ov-area--dragging");
          if (!moved) return;   // a tap (no drag) shouldn't pin the chip at its default spot
          this.card._state.setAreaLabelAnchorLocal?.(roomKey, livePctX, livePctY);
          this.card._actions?.setAreaLabelAnchor?.(roomKey, livePctX, livePctY);
          this.card._scheduleRender();
        };

        el.addEventListener("pointermove",   onMove);
        el.addEventListener("pointerup",     finish);
        el.addEventListener("pointercancel", finish);
      });
    });
  };

  /* =========================================================
     ROOM-NAME LABEL DRAG — move a room's name off its centroid.
     Mirrors _bindAreaLabelDrag: a drag repositions the label (saved per-device in
     localStorage, % of the content box); a TAP (no drag) keeps today's behavior and
     selects the room. Reset = drag it back toward the centre. (No backend; user choice.)
     ========================================================= */
  proto._bindRoomNameDrag = function (root) {
    root.querySelectorAll("[data-action='room-name-drag']").forEach((el) => {
      const layers = root.querySelector(".evcc-map-layers");
      if (!layers) return;

      this.card._on(el, "pointerdown", (e) => {
        if (e.button !== 0) return;
        // Don't swallow a rubber-band (zone/hide draw) that starts over a label.
        if (this.card._state.zoneDrawMode?.() || this.card._state.hideDrawMode?.()) return;
        e.stopPropagation();   // keep the pan handler from starting a drag
        e.preventDefault();

        const roomKey = el.dataset.room;
        if (roomKey == null || roomKey === "") return;

        el.setPointerCapture(e.pointerId);

        const layerRect = layers.getBoundingClientRect();
        const rot = this.card._state.effectiveMapRotation?.() ?? 0;
        const ptrContentPct = (clientX, clientY) =>
          this.card._state.unrotatePct(
            (clientX - layerRect.left) / layerRect.width  * 100,
            (clientY - layerRect.top)  / layerRect.height * 100,
            rot,
          );

        const curPctX = parseFloat(el.style.left) || 0;
        const curPctY = parseFloat(el.style.top)  || 0;
        const [grabX, grabY] = ptrContentPct(e.clientX, e.clientY);
        const grabOffX = grabX - curPctX;
        const grabOffY = grabY - curPctY;
        const startClientX = e.clientX;
        const startClientY = e.clientY;
        // The auto-placement (room centroid) the renderer used — dropping the name back
        // near here clears the anchor (the reset gesture; restores automatic positioning).
        const homeX = parseFloat(el.dataset.cx);
        const homeY = parseFloat(el.dataset.cy);
        let livePctX = curPctX;
        let livePctY = curPctY;
        let moved = false;

        const onMove = (ev) => {
          // Pixel-based dead-zone (container-size independent, matching the pan handler's 3px)
          // so a jittery tap on the small embedded card map isn't promoted to a drag.
          if (!moved && Math.abs(ev.clientX - startClientX) < 3 && Math.abs(ev.clientY - startClientY) < 3) return;
          const [mx, my] = ptrContentPct(ev.clientX, ev.clientY);
          livePctX = Math.max(0, Math.min(100, mx - grabOffX));
          livePctY = Math.max(0, Math.min(100, my - grabOffY));
          moved = true;
          el.classList.add("evcc-map-label--dragging");
          el.style.left = `${livePctX}%`;
          el.style.top  = `${livePctY}%`;
        };

        const cleanup = () => {
          el.removeEventListener("pointermove",   onMove);
          el.removeEventListener("pointerup",     onUp);
          el.removeEventListener("pointercancel", onCancel);
          el.classList.remove("evcc-map-label--dragging");
        };
        const onUp = () => {
          cleanup();
          if (moved) {
            const nearHome = Number.isFinite(homeX) && Number.isFinite(homeY)
              && Math.abs(livePctX - homeX) < 3 && Math.abs(livePctY - homeY) < 3;
            if (nearHome) this.card._state.clearRoomNameAnchor?.(roomKey);   // snap back to auto
            else          this.card._state.setRoomNameAnchorLocal?.(roomKey, livePctX, livePctY);
            this.card._scheduleRender();
          } else if (el.dataset.segment != null && el.dataset.segment !== "") {
            // A tap, not a drag — preserve prior behavior: select the room. Polygon
            // (Eufy) labels carry data-segment.
            this._selectSegmentFromLabelTap(el.dataset.segment);
          } else {
            // Device (raster) labels have no segment — select by the room NUMBER
            // (== managed room id), mirroring the canvas hit-test tap. Needed because
            // the draggable label now captures the pointer, so the tap no longer falls
            // through to the canvas room-select.
            this._selectDeviceRoomFromLabelTap(roomKey);
          }
        };
        const onCancel = () => {
          // An ABORTED gesture (scroll/gesture takeover, focus loss) is NOT a tap — never
          // select; just drop the in-progress move and let the next render revert the label.
          cleanup();
          if (moved) this.card._scheduleRender();
        };

        el.addEventListener("pointermove",   onMove);
        el.addEventListener("pointerup",     onUp);
        el.addEventListener("pointercancel", onCancel);
      });
    });
  };

  // Single-tap select forwarded from a name-label tap — mirrors the polygon single-click
  // path (toggle the segment + sync the room enable), minus the dbl-click editor timer.
  proto._selectSegmentFromLabelTap = function (segmentId) {
    if (segmentId == null || segmentId === "") return;
    const st = this.card._state;
    const wasSelected = st.isSegmentSelected?.(segmentId);
    st.toggleSegmentSelected?.(segmentId);
    const rooms  = st.getRoomsForActiveMap?.() ?? [];
    const roomId = st.roomIdForSegment?.(segmentId);
    const room   = roomId != null ? rooms.find((r) => String(r.id) === String(roomId)) : null;
    if (room && this.card._actions?.toggleRoomEnabled) {
      this.card._actions
        .toggleRoomEnabled(room.mapId, room.id, wasSelected)
        .then(() => this.card._scheduleRender())
        .catch((err) => console.error("[eufy-vacuum-command-center] Room sync failed:", err));
    } else {
      this.card._scheduleRender();
    }
  };

  // Device (raster) room-name label tap — no polygon segment to toggle; select by the
  // device room NUMBER (== managed room id), mirroring the canvas hit-test tap
  // (toggleRoomEnabled with the room's current enabled state). Keeps tap-to-select working
  // now that the draggable label captures the pointer instead of letting it reach the canvas.
  proto._selectDeviceRoomFromLabelTap = function (roomNumber) {
    if (roomNumber == null || roomNumber === "") return;
    const st = this.card._state;
    const mapId = st.activeMapId?.();
    const room = (st.getRoomsForActiveMap?.() ?? []).find(
      (rm) => Number(rm.id) === Number(roomNumber),
    );
    this.card._actions?.toggleRoomEnabled?.(mapId, Number(roomNumber), room?.enabled ?? false);
    this.card._scheduleRender?.();
  };

  /* =========================================================
     FURNISHED ART (Wave 1 — config view; "Live map" layout only)
     =========================================================
     Upload / render-mode toggle / align (nudge/scale/rotate + pointer-drag) the
     whole-home art. The alignment uses an art-only DRAFT transform {tx,ty,scale,rotation}
     (separate from the segment composer — no group/op/room_id, no polygon bake); Save
     persists it via set_furnished_art_placement (scope home). The drag converts
     pointer→content% through unrotatePct (the mascot/area-label pattern) so it stays
     correct on a rotated live map. */
  proto._bindFurnishedArt = function (root) {
    const _mapId = () =>
      this.card._state.mapSegmentsData()?.map_id ?? this.card._state.activeMapId?.() ?? null;

    // --- Render-mode toggle (live / blend / art) ---
    root.querySelectorAll("[data-action='furnished-render-mode']").forEach((btn) => {
      this.card._on(btn, "click", async () => {
        const mapId = _mapId();
        const mode = btn.dataset.mode;
        if (!mapId || !mode) return;
        // Optimistic flip is set inside the action; refetch to settle the saved value.
        this.card._scheduleRender();
        try {
          await this.card._actions.setFurnishedRenderMode(mapId, mode);
        } catch (err) {
          // The mode-set itself failed → revert the optimistic overlay to the saved value.
          console.error("[eufy-vacuum-command-center] set furnished render mode failed:", err);
          this.card._state.clearFurnishedRenderModeOptimistic?.();
          this.card._scheduleRender();
          return;
        }
        // Mode is saved server-side; refresh segments to settle it. If the REFRESH fails the
        // optimistic overlay STAYS (it reflects what the server saved) and self-corrects on
        // the next successful fetch — don't clear it here or the toggle snaps back to stale.
        try {
          await this.card._actions.getMapSegments(mapId);
        } catch (err) {
          console.error("[eufy-vacuum-command-center] segments refresh after render-mode set failed (mode was saved):", err);
        }
        this.card._scheduleRender();
      });
    });

    // --- Upload furnished art (websocket-safe; whole-home scope) ---
    root.querySelectorAll("[data-action='upload-furnished-art']").forEach((btn) => {
      this.card._on(btn, "click", () => {
        const input = document.createElement("input");
        input.type = "file";
        input.accept = "image/png,image/jpeg,image/webp,image/bmp";
        const handleChange = async () => {
          input.removeEventListener("change", handleChange);
          const file = input.files?.[0];
          if (!file) return;
          const mapId = _mapId();
          const layoutId = this.card._state.activeCustomLayoutId?.();
          if (!mapId || !layoutId) {
            this.card._state.setMapActionStatus({
              type: "upload", variant: "furnished-art", status: "error",
              message: this.t("bind_map.no_active_live_map_layout"),
            });
            this.card._scheduleRender();
            return;
          }
          this.card._state.setMapActionStatus({ type: "upload", variant: "furnished-art", status: "busy" });
          this.card._scheduleRender();
          try {
            // Display-only art: downscale + recompress (alpha-safe) to fit HA's WS frame.
            const fitted = await _imageFileToFittedBase64(file, { maxDim: 2048, allowDownscale: true });
            if (!fitted) throw new Error(this.t("bind_map.could_not_prepare_image"));
            await this.card._actions.uploadMapImage(mapId, fitted.base64, {
              variant: "custom",        // ignored when art_scope is set (server derives the key)
              layout_id: layoutId,
              art_scope: "home",
            });
            // Surface the freshly-uploaded art for alignment: if the layout is still in
            // "live" mode (art hidden — the default), flip to "blend" so the user sees the
            // art over a faded live map immediately, not an apparently-no-op upload.
            if ((this.card._state.furnishedRenderMode?.() ?? "live") === "live") {
              try { await this.card._actions.setFurnishedRenderMode(mapId, "blend"); }
              catch (_e) { /* non-fatal: art uploaded; user can pick a mode manually */ }
            }
            await this.card._actions.getMapSegments(mapId);
            this.card._state.clearMapActionStatus();
            this.card._scheduleRender();
          } catch (err) {
            console.error("[eufy-vacuum-command-center] furnished art upload failed:", err);
            this.card._state.setMapActionStatus({
              type: "upload", variant: "furnished-art", status: "error",
              message: _uploadErrorMessage(err, this.tRaw.bind(this)),
            });
            this.card._scheduleRender();
          }
        };
        input.addEventListener("change", handleChange);
        input.click();
      });
    });

    // --- Export the current map image (download it to trace furniture over) ---
    // Fetches the exact live-map frame the card is showing (the same bytes a right-click →
    // Save image would grab) and downloads it. The user draws their furniture over THAT in an
    // external editor, then uploads it as the art — already registered to the map pixels, so
    // in-card placement is near-identity. Pure client-side: no service call. Reads the src off
    // the displayed <img> (most reliable — it's exactly what loaded), with a VA-render <canvas>
    // fallback for the (non-live) self-render case.
    root.querySelectorAll("[data-action='furnished-export-map']").forEach((btn) => {
      this.card._on(btn, "click", async () => {
        this.card._state.clearMapActionStatus?.();   // fresh action → drop any prior status (incl. a stale export error)
        try {
          const objId = (this.card._state.vacuumEntityId?.() ?? "vacuum").replace(/^.*\./, "");
          const nameBase = `${objId}_${_mapId() ?? "map"}_map`;
          // The button only renders when the furnished (live-backdrop) layout is active, which
          // requires a present live image — so the base <img> is always mounted. Guard anyway.
          const url = root
            .querySelector(".evcc-map-container--config img.evcc-map-image")
            ?.getAttribute("src") || null;
          if (!url) throw new Error("no map image to export");
          const resp = await fetch(url, { credentials: "same-origin" });
          if (!resp.ok) throw new Error(`fetch ${resp.status}`);
          const blob = await resp.blob();
          if (!blob || !blob.size) throw new Error("empty image");
          // Prefer the served Content-Type; fall back to the extension on the URL path (strip
          // the cache-bust query) so a generic/empty type doesn't mislabel a JPEG/WebP as .png.
          const byType = { "image/jpeg": "jpg", "image/jpg": "jpg", "image/webp": "webp",
                           "image/png": "png", "image/bmp": "bmp" }[blob.type];
          const byPath = (url.split("?")[0].match(/\.(png|jpe?g|webp|bmp)$/i)?.[1] || "")
            .toLowerCase().replace("jpeg", "jpg");
          const ext = byType || byPath || "png";
          const href = URL.createObjectURL(blob);
          const a = document.createElement("a");
          a.href = href;
          a.download = `${nameBase}.${ext}`;
          document.body.appendChild(a);
          a.click();
          a.remove();
          setTimeout(() => URL.revokeObjectURL(href), 1000);
          this.card._scheduleRender();   // reflect the cleared status (drop any prior error span)
        } catch (err) {
          console.error("[eufy-vacuum-command-center] export map image failed:", err);
          this.card._state.setMapActionStatus?.({
            type: "export", variant: "furnished-map", status: "error",
            message: this.t("bind_map.could_not_save_map_image"),
          });
          this.card._scheduleRender();
        }
      });
    });

    // --- Align: nudge / scale / rotate the draft (local; persisted on Save) ---
    root.querySelectorAll("[data-action='furnished-art-nudge']").forEach((btn) => {
      this.card._on(btn, "click", () => {
        this.card._state.nudgeFurnishedArt?.(Number(btn.dataset.dx ?? 0), Number(btn.dataset.dy ?? 0));
        this.card._scheduleRender();
      });
    });
    root.querySelectorAll("[data-action='furnished-art-scale']").forEach((btn) => {
      this.card._on(btn, "click", () => {
        this.card._state.scaleFurnishedArt?.(Number(btn.dataset.factor ?? 1));
        this.card._scheduleRender();
      });
    });
    root.querySelectorAll("[data-action='furnished-art-rotate']").forEach((btn) => {
      this.card._on(btn, "click", () => {
        this.card._state.rotateFurnishedArt?.(Number(btn.dataset.deg ?? 0));
        this.card._scheduleRender();
      });
    });

    // --- Fine rotation-trim slider (±15° around the current angle, commit on release) ---
    // Previews a RELATIVE trim inline (no re-render mid-drag, like the pointer-drag), then
    // commits the resulting ABSOLUTE angle on 'change'. `base` is the draft rotation captured
    // at the start of the gesture; the slider snaps back to 0 after commit. Works for both
    // pointer-drag and keyboard (base is lazily captured on the first 'input').
    root.querySelectorAll("[data-action='furnished-art-rotate-slider']").forEach((slider) => {
      let base = null;   // draft rotation captured at gesture start; the trim is RELATIVE to it
      const artEl   = () => root.querySelector(".evcc-map-art--editable");
      const readout = () => root.querySelector(".evcc-map-furnished-rotate-readout");
      const applyInline = (rot) => {
        const el = artEl();
        if (el) {
          const t = this.card._state.furnishedArtTransform?.() ?? { tx: 0, ty: 0, scale: 1 };
          const tx = Number(t.tx) || 0, ty = Number(t.ty) || 0, sc = Number(t.scale) || 1;
          el.style.transform = `translate(${tx.toFixed(3)}%, ${ty.toFixed(3)}%) rotate(${rot}deg) scale(${sc})`;
        }
        const r = readout();
        if (r) r.textContent = `${((((rot % 360) + 360) % 360)).toFixed(1)}°`;
      };
      // Pointer-drag is a multi-second gesture → suppress re-renders for its duration so the
      // slider/art aren't rebuilt mid-drag (which would lose the gesture). Each input applies
      // the trim ABSOLUTELY (base + value) to the draft, so re-applying never compounds and
      // there's no fragile separate-commit step. Release just recenters the slider + re-enables
      // rendering. Keyboard arrows fire input+change instantly per press (base re-captured each
      // time), so they don't depend on the pointer bracket.
      this.card._on(slider, "pointerdown", () => {
        this.card._furnishedGestureActive = true;
        base = Number(this.card._state.furnishedArtTransform?.()?.rotation ?? 0);
      });
      this.card._on(slider, "input", () => {
        if (base == null) base = Number(this.card._state.furnishedArtTransform?.()?.rotation ?? 0);
        const target = base + (Number(slider.value) || 0);
        this.card._state.setFurnishedArtRotationAbsolute?.(target);  // mutate draft (absolute → no compounding)
        applyInline(target);                                         // live visual (renders are suppressed)
      });
      const release = () => {
        base = null;
        slider.value = 0;                            // the trim recenters after each gesture
        this.card._furnishedGestureActive = false;
        this.card._scheduleRender();                 // settles the committed draft + resets the slider DOM
      };
      this.card._on(slider, "change", release);
      this.card._on(slider, "pointerup", release);
      this.card._on(slider, "pointercancel", release);
    });

    // --- Save the draft alignment ---
    root.querySelectorAll("[data-action='furnished-art-save']").forEach((btn) => {
      this.card._on(btn, "click", async () => {
        const mapId = _mapId();
        if (!mapId) return;
        const t = this.card._state.furnishedArtTransform?.();
        try {
          await this.card._actions.setFurnishedArtPlacement(mapId, t);
          await this.card._actions.getMapSegments(mapId);  // refresh FIRST so the layout holds the new transform
          this.card._state.clearFurnishedArtDraft?.();     // THEN drop the draft — no fall-back-to-old-transform flicker window
          this.card._scheduleRender();
        } catch (err) {
          console.error("[eufy-vacuum-command-center] save furnished art placement failed:", err);
        }
      });
    });

    // --- Reset placement (clear the saved transform; keeps the uploaded image) ---
    root.querySelectorAll("[data-action='furnished-art-clear']").forEach((btn) => {
      this.card._on(btn, "click", async () => {
        const mapId = _mapId();
        if (!mapId) return;
        try {
          await this.card._actions.setFurnishedArtPlacement(mapId, null);
          this.card._state.clearFurnishedArtDraft?.();
          await this.card._actions.getMapSegments(mapId);
          this.card._scheduleRender();
        } catch (err) {
          console.error("[eufy-vacuum-command-center] clear furnished art placement failed:", err);
        }
      });
    });

    // --- Pointer-drag the art over the map (mascot/area-label pattern) ---
    root.querySelectorAll("[data-action='furnished-art-drag']").forEach((el) => {
      const layers = el.closest(".evcc-map-layers")
        ?? root.querySelector(".evcc-map-container--config .evcc-map-layers");
      if (!layers) return;
      this.card._on(el, "pointerdown", (e) => {
        if (e.button !== 0) return;
        e.stopPropagation();   // don't let the pan handler start a drag
        e.preventDefault();
        el.setPointerCapture(e.pointerId);
        el.classList.add("evcc-map-art--dragging");
        this.card._furnishedGestureActive = true;   // suppress re-renders so this element survives the drag

        const layerRect = layers.getBoundingClientRect();
        // The art lives INSIDE .evcc-map-content-rotator; the pointer is in the unrotated
        // .evcc-map-layers frame. Convert pointer% -> CONTENT% via unrotatePct so a 90/270
        // drag tracks (and stores) at the right spot. Identity at 0.
        const rot = this.card._state.effectiveMapRotation?.() ?? 0;
        const ptrContentPct = (clientX, clientY) =>
          this.card._state.unrotatePct(
            (clientX - layerRect.left) / layerRect.width  * 100,
            (clientY - layerRect.top)  / layerRect.height * 100,
            rot,
          );

        // Drag by the CONTENT-frame delta added to the current draft offset, so the art
        // doesn't snap its centre to the grab point (it's translate(tx%,ty%) about centre).
        const t0 = this.card._state.furnishedArtTransform?.() ?? { tx: 0, ty: 0, scale: 1, rotation: 0 };
        const baseTx = Number(t0.tx) || 0, baseTy = Number(t0.ty) || 0;
        const [grabX, grabY] = ptrContentPct(e.clientX, e.clientY);
        let liveTx = baseTx, liveTy = baseTy, moved = false;

        const applyInline = () => {
          const sc = Number(this.card._state.furnishedArtTransform?.()?.scale ?? t0.scale ?? 1) || 1;
          const r  = Number(this.card._state.furnishedArtTransform?.()?.rotation ?? t0.rotation ?? 0);
          el.style.transform = `translate(${liveTx.toFixed(3)}%, ${liveTy.toFixed(3)}%) rotate(${r}deg) scale(${sc})`;
        };
        const onMove = (ev) => {
          const [cx, cy] = ptrContentPct(ev.clientX, ev.clientY);
          liveTx = baseTx + (cx - grabX);
          liveTy = baseTy + (cy - grabY);
          moved = true;
          applyInline();   // optimistic, no re-render mid-drag
        };
        const finish = () => {
          el.removeEventListener("pointermove",   onMove);
          el.removeEventListener("pointerup",     finish);
          el.removeEventListener("pointercancel", finish);
          el.classList.remove("evcc-map-art--dragging");
          this.card._furnishedGestureActive = false;   // re-enable renders
          if (moved) this.card._state.setFurnishedArtOffset?.(liveTx, liveTy);
          this.card._scheduleRender();   // settle: commit the move (if any) + restore normal rendering
        };
        el.addEventListener("pointermove",   onMove);
        el.addEventListener("pointerup",     finish);
        el.addEventListener("pointercancel", finish);
      });
    });
  };

  /**
   * Auto-derived click target: a clean tap on a room region toggles it into the clean selection.
   * Pixel-exact — convert the tap (screen) through pan/zoom -> un-rotate -> the room raster to a
   * DEVICE ROOM ID (== the managed room id), then toggle that room's enabled switch. No-op while
   * drawing/anchoring. When there's no render raster (a bare Roborock/Eufy live map) it falls back
   * to an approximate bbox hit-test against the map_state_source rooms (deviceRoomIdAtContentPct).
   */
  proto._handleRoomTap = function (container, clientX, clientY) {
    const state = this.card._state;
    if (state.zoneDrawMode?.() || state.hideDrawMode?.() || state.isMapAnchorMode?.()) return;
    // Only hit-test over a backdrop the device-frame raster is registered to (VA render or live
    // image). On an uploaded/CV --fill backdrop the raster doesn't co-register, so a tap would
    // toggle the wrong room. Mirrors the deviceOverlays / scrim gate.
    if (!(state.overlaysAligned?.() ?? false)) return;
    const layers = container.querySelector(".evcc-map-layers");
    if (!layers) return;
    const r = layers.getBoundingClientRect();
    if (!r.width || !r.height) return;
    const fx = (clientX - r.left) / r.width  * 100;
    const fy = (clientY - r.top)  / r.height * 100;
    const rot = state.effectiveMapRotation?.() ?? 0;
    const [cx, cy] = state.unrotatePct(fx, fy, rot);
    // Pixel-exact raster hit-test (Eufy CV / VA self-render); fall back to the device rooms'
    // approximate bboxes when there's no raster (a bare Roborock/Eufy live map).
    const rd = state.mapRenderData?.();
    const rid = (rd && rd.present)
      ? state.roomIdAtContentPct(cx, cy, rd)
      : state.deviceRoomIdAtContentPct?.(cx, cy);
    if (rid == null) return;
    const mapId = state.activeMapId?.();
    const room = (state.getRoomsForActiveMap?.() ?? []).find((rm) => Number(rm.id) === Number(rid));
    this.card._actions?.toggleRoomEnabled?.(mapId, rid, room?.enabled ?? false);
    this.card._scheduleRender?.();
  };

/* =========================================================
   ZOOM / PAN
   =========================================================
   Applies transform directly to .evcc-map-layers during
   interaction to avoid render-cycle DOM teardown mid-drag.
   State is kept in sync so the next scheduled render picks
   up the correct transform from state.
   ========================================================= */

  proto._bindMapZoomPan = function (root) {
    const container = root.querySelector(".evcc-map-container");
    if (!container) return;

    const applyTransform = () => {
      const layers = container.querySelector(".evcc-map-layers");
      if (!layers) return;
      // Re-clamp the pinned translate to the LIVE container before applying, so a
      // view restored from storage (or panned to the edge) can't strand the map
      // off-screen after a container resize. clientWidth/Height are the
      // untransformed box (CSS transforms don't affect them) and the container has
      // no border/padding, so they equal the .evcc-map-layers box. Persist any
      // correction (debounced) so the next reload starts from an on-screen view.
      if (this.card._state.clampMapTransform?.(container.clientWidth, container.clientHeight)) {
        this.card._state._persistMapTransform?.();
      }
      const z  = this.card._state.mapZoom?.()        ?? 1;
      const tx = this.card._state.mapTranslateX?.()  ?? 0;
      const ty = this.card._state.mapTranslateY?.()  ?? 0;
      layers.style.transform = `translate(${tx}px,${ty}px) scale(${z})`;
    };

    // ----------------------------------------------------------
    // Zoom toolbar buttons — explicit +/-/fit controls. The map state
    // already supports zoom in the range [0.5, 8]; these just provide
    // discoverable UI for desktop users who have no pinch gesture.
    // ----------------------------------------------------------
    const _stepZoom = (factor) => {
      const cur = this.card._state.mapZoom?.() ?? 1;
      const rect = container.getBoundingClientRect();
      // Zoom toward container center when triggered via button.
      const cx = rect.width / 2;
      const cy = rect.height / 2;
      this.card._state.applyMapZoom?.(cur * factor, cx, cy);
      applyTransform();
      this.card._scheduleRender?.();      // refresh the % readout
    };

    root.querySelectorAll("[data-action='map-zoom-in']").forEach((btn) => {
      this.card._on(btn, "click", (e) => { e.stopPropagation(); _stepZoom(1.25); });
    });
    root.querySelectorAll("[data-action='map-zoom-out']").forEach((btn) => {
      this.card._on(btn, "click", (e) => { e.stopPropagation(); _stepZoom(0.8); });
    });
    root.querySelectorAll("[data-action='map-zoom-fit']").forEach((btn) => {
      this.card._on(btn, "click", (e) => {
        e.stopPropagation();
        this.card._state.resetMapTransform?.();
        applyTransform();
        this.card._scheduleRender?.();
      });
    });
    // Rotate the live map 90° CW (display only; backend-stored per map). The
    // action sets an optimistic overlay synchronously, so re-rendering now shows
    // the turn instantly while the service persists it.
    root.querySelectorAll("[data-action='map-rotate']").forEach((btn) => {
      this.card._on(btn, "click", (e) => {
        e.stopPropagation();
        // Rotation invalidates the draw gates (zone + hide-area are rot-0 only) — tear down any
        // in-progress draw so a rotated box can never be confirmed.
        this.card._state.setZoneDrawMode?.(false);
        this.card._state.setHideDrawMode?.(false);
        const mapId = this.card._state.mapSegmentsData?.()?.map_id
          ?? this.card._state.activeMapId?.() ?? null;
        this.card._actions.rotateLiveMap?.(mapId);
        this.card._scheduleRender?.();
      });
    });

    // Ad-hoc zone clean: toggle draw mode / dispatch the drawn box / cancel.
    root.querySelectorAll("[data-action='toggle-zone-draw']").forEach((btn) => {
      this.card._on(btn, "click", (e) => {
        e.stopPropagation();
        this.card._state.setZoneDrawMode?.(!this.card._state.zoneDrawMode?.());
        this.card._scheduleRender?.();
      });
    });
    root.querySelectorAll("[data-action='zone-clean-cancel']").forEach((btn) => {
      this.card._on(btn, "click", (e) => {
        e.stopPropagation();
        this.card._state.setZoneDrawMode?.(false);
        this.card._scheduleRender?.();
      });
    });
    root.querySelectorAll("[data-action='zone-clear']").forEach((btn) => {
      this.card._on(btn, "click", (e) => {
        e.stopPropagation();
        this.card._state.clearZoneDrafts?.();
        this.card._scheduleRender?.();
      });
    });
    // Live setting selects in the zone panel — set the real provider entity. The
    // HA state push re-renders with the confirmed value; no local render needed.
    root.querySelectorAll("[data-action='zone-setting']").forEach((sel) => {
      this.card._on(sel, "change", (e) => {
        e.stopPropagation();
        this.card._actions.setVacuumSetting?.(sel.dataset.entityId, sel.value);
      });
    });
    // Fallback suction row (brands with no fan-speed `select` entity, e.g. Roborock):
    // set the device's fan power via the standard vacuum.set_fan_speed. Card-wide (covers
    // the zone panel AND the saved-zones panel), like the sz-setting binding, so both
    // surfaces' fallback rows are wired from one place.
    this.card._onAll?.("[data-action='zone-fanspeed']", "change", (e) => {
      e.stopPropagation();
      this.card._actions.setVacuumFanSpeed?.(e.target.value);
    });
    // Per-zone remove in the zone panel.
    root.querySelectorAll("[data-action='zone-remove']").forEach((btn) => {
      this.card._on(btn, "click", (e) => {
        e.stopPropagation();
        const i = Number(btn.dataset.zoneIndex);
        if (!Number.isNaN(i)) this.card._state.removeZoneDraft?.(i);
        this.card._scheduleRender?.();
      });
    });
    root.querySelectorAll("[data-action='zone-clean-confirm']").forEach((btn) => {
      this.card._on(btn, "click", async (e) => {
        e.stopPropagation();
        // Refuse to dispatch if the gate no longer holds (e.g. rotated mid-draw).
        if (!this.card._state.canDrawZone?.()) {
          this.card._state.setZoneDrawMode?.(false);
          this.card._scheduleRender?.();
          return;
        }
        // The live backdrop's natural pixel size lets us letterbox-correct the pct draft into
        // the image's normalized frame (object-fit:contain on a square container letterboxes a
        // non-square map). Backdrop may be an <img> OR a <canvas> (VA render) — _liveMapDims
        // handles both.
        const dims = this._liveMapDims(root);
        const rects = this.card._state.zoneDraftsToNormalizedRects?.(dims) ?? [];
        if (!rects.length) {
          console.warn(
            "[eufy-vacuum-command-center] zone clean: nothing drawn or live image not ready",
          );
          return;
        }
        try {
          await this.card._actions.cleanZone?.(rects, 1);
        } catch (err) {
          console.error("[eufy-vacuum-command-center] zone clean failed:", err);
        }
        this.card._state.setZoneDrawMode?.(false); // exit + clear the drafts
        this.card._scheduleRender?.();
      });
    });

    // ----------------------------------------------------------
    // Ctrl + wheel zoom — desktop equivalent of pinch. Plain wheel
    // is left to the page (so scrolling the parent dashboard still
    // works); only Ctrl-modified wheel intercepts.
    // ----------------------------------------------------------
    this.card._on(container, "wheel", (e) => {
      if (!e.ctrlKey) return;
      e.preventDefault();
      const rect = container.getBoundingClientRect();
      const cx = e.clientX - rect.left;
      const cy = e.clientY - rect.top;
      const factor = e.deltaY < 0 ? 1.1 : (1 / 1.1);   // up = in, down = out
      const cur = this.card._state.mapZoom?.() ?? 1;
      this.card._state.applyMapZoom?.(cur * factor, cx, cy);
      applyTransform();
      this.card._scheduleRender?.();
    }, { passive: false });

    // ----------------------------------------------------------
    // Pointer drag pan — document-level listeners so pointer
    // capture is never set (capture redirects click events away
    // from child SVG polygons, breaking tap-to-select).
    // ----------------------------------------------------------
    let _dragging = false;
    let _lastX = 0, _lastY = 0;
    let _moved  = false;

    this.card._on(container, "pointerdown", (e) => {
      if (e.button !== 0) return;
      // Zone-draw mode owns the press: paint a rubber-band rectangle instead of
      // panning. This MUST live inside this one handler — _on() is idempotent per
      // element+event (core.js), so a second pointerdown bind on the container is
      // silently dropped. (That dropped-bind was the "drag does nothing" bug.)
      if (this.card._state.zoneDrawMode?.() && this.card._state.canDrawZone?.()) {
        const layers = container.querySelector(".evcc-map-layers");
        if (!layers) return;
        const zr = layers.getBoundingClientRect();
        if (!zr.width || !zr.height) return;
        e.preventDefault();
        const zclamp = (v) => Math.min(Math.max(v, 0), 100);
        const zsx = zclamp(((e.clientX - zr.left) / zr.width)  * 100);
        const zsy = zclamp(((e.clientY - zr.top)  / zr.height) * 100);
        let zcur = { x: zsx, y: zsy, w: 0, h: 0 };
        const zpaint = () => {
          // Re-query each paint so a mid-drag re-render doesn't strand a detached node.
          const box = container.querySelector(".evcc-zone-draft");
          if (!box) return;
          box.style.left    = Math.min(zcur.x, zcur.x + zcur.w) + "%";
          box.style.top     = Math.min(zcur.y, zcur.y + zcur.h) + "%";
          box.style.width   = Math.abs(zcur.w) + "%";
          box.style.height  = Math.abs(zcur.h) + "%";
          box.style.display = "block";
        };
        zpaint();
        const zMove = (ev) => {
          zcur = {
            x: zsx, y: zsy,
            w: zclamp(((ev.clientX - zr.left) / zr.width)  * 100) - zsx,
            h: zclamp(((ev.clientY - zr.top)  / zr.height) * 100) - zsy,
          };
          zpaint();
        };
        const zUp = () => {
          document.removeEventListener("pointermove", zMove);
          document.removeEventListener("pointerup",     zUp);
          document.removeEventListener("pointercancel", zUp);
          if (Math.abs(zcur.w) < 1 || Math.abs(zcur.h) < 1) return; // ignore a stray click
          // Commit this box to the list (no-op at the 10-zone cap); re-render shows
          // it as a persistent overlay and the in-progress box resets to hidden.
          this.card._state.addZoneDraft?.(zcur);
          this.card._scheduleRender?.();
        };
        document.addEventListener("pointermove", zMove);
        document.addEventListener("pointerup",     zUp);
        document.addEventListener("pointercancel", zUp);
        return;
      }
      // Hide-area draw owns the press the same way (mirrors the zone rubber-band): drag a box,
      // convert it to a normalized image rect (letterbox-corrected), and append it to the
      // persisted hidden regions. Like zones, this MUST live in this one pointerdown handler.
      if (this.card._state.hideDrawMode?.() && this.card._state.canDrawHideArea?.()) {
        // Don't start a rubber-band when the press is on the × delete button (its own click
        // handler owns it) — else a tiny move while deleting would paint a stray draft.
        if (e.target.closest("[data-action='delete-hidden-region']")) return;
        const layers = container.querySelector(".evcc-map-layers");
        if (!layers) return;
        const hr = layers.getBoundingClientRect();
        if (!hr.width || !hr.height) return;
        e.preventDefault();
        const hclamp = (v) => Math.min(Math.max(v, 0), 100);
        const hsx = hclamp(((e.clientX - hr.left) / hr.width)  * 100);
        const hsy = hclamp(((e.clientY - hr.top)  / hr.height) * 100);
        let hcur = { x: hsx, y: hsy, w: 0, h: 0 };
        const hpaint = () => {
          const box = container.querySelector(".evcc-hide-draft");
          if (!box) return;
          box.style.left    = Math.min(hcur.x, hcur.x + hcur.w) + "%";
          box.style.top     = Math.min(hcur.y, hcur.y + hcur.h) + "%";
          box.style.width   = Math.abs(hcur.w) + "%";
          box.style.height  = Math.abs(hcur.h) + "%";
          box.style.display = "block";
        };
        hpaint();
        const hMove = (ev) => {
          hcur = {
            x: hsx, y: hsy,
            w: hclamp(((ev.clientX - hr.left) / hr.width)  * 100) - hsx,
            h: hclamp(((ev.clientY - hr.top)  / hr.height) * 100) - hsy,
          };
          hpaint();
        };
        const hUp = () => {
          document.removeEventListener("pointermove", hMove);
          document.removeEventListener("pointerup",     hUp);
          document.removeEventListener("pointercancel", hUp);
          if (Math.abs(hcur.w) < 1 || Math.abs(hcur.h) < 1) return; // ignore a stray click
          const size = this.card._state.mapImageSize?.();
          const dims = (Array.isArray(size) && size.length === 2)
            ? { width: size[0], height: size[1] } : null;
          const norm = this.card._state._rectToNormalized?.(hcur, dims);
          if (!norm) return;
          const next = [...(this.card._state.hiddenRegions?.() ?? []), norm];
          this.card._actions?.setHiddenRegions?.(next);   // optimistic + persist
          this.card._scheduleRender?.();
        };
        document.addEventListener("pointermove", hMove);
        document.addEventListener("pointerup",     hUp);
        document.addEventListener("pointercancel", hUp);
        return;
      }
      // Always reset drag flag so the next click starts clean.
      this.card._mapDragOccurred = false;
      // Don't start a pan drag when the press originates on a draggable element (the animal
      // icon or a room-area chip) — let its own drag handler deal with it.
      if (e.target.closest("[data-action='map-dot-click']")) return;
      if (e.target.closest("[data-action='area-label-drag']")) return;
      _dragging = true;
      _moved    = false;
      _lastX    = e.clientX;
      _lastY    = e.clientY;
      const downX = e.clientX, downY = e.clientY;

      const onMove = (ev) => {
        if (!_dragging) return;
        const dx = ev.clientX - _lastX;
        const dy = ev.clientY - _lastY;
        _lastX = ev.clientX;
        _lastY = ev.clientY;
        if (!_moved && Math.abs(dx) < 3 && Math.abs(dy) < 3) return;
        _moved = true;
        this.card._mapDragOccurred = true;
        this.card._state.applyMapPan?.(dx, dy);
        applyTransform();
      };

      const onUp = () => {
        _dragging = false;
        document.removeEventListener("pointermove", onMove);
        document.removeEventListener("pointerup",     onUp);
        document.removeEventListener("pointercancel", onUp);
        // A clean tap (no drag) on a room region -> toggle it into the clean selection.
        if (!_moved) this._handleRoomTap(container, downX, downY);
      };

      document.addEventListener("pointermove", onMove);
      document.addEventListener("pointerup",     onUp);
      document.addEventListener("pointercancel", onUp);
    });

    // ----------------------------------------------------------
    // Double-click on map background → reset transform
    // ----------------------------------------------------------
    this.card._on(container, "dblclick", (e) => {
      if (e.target.closest("[data-action='toggle-segment']")) return;
      this.card._state.resetMapTransform?.();
      applyTransform();
    });

    // ----------------------------------------------------------
    // Touch pinch zoom
    // ----------------------------------------------------------
    const _activeTouches = {};
    let _lastPinchDist = null;

    this.card._on(container, "touchstart", (e) => {
      Array.from(e.changedTouches).forEach((t) => {
        _activeTouches[t.identifier] = { x: t.clientX, y: t.clientY };
      });
      if (Object.keys(_activeTouches).length === 2) {
        e.preventDefault();
        _lastPinchDist = _pinchDist(_activeTouches);
      }
    }, { passive: false });

    this.card._on(container, "touchmove", (e) => {
      Array.from(e.changedTouches).forEach((t) => {
        _activeTouches[t.identifier] = { x: t.clientX, y: t.clientY };
      });
      const pts = Object.values(_activeTouches);
      if (pts.length !== 2 || _lastPinchDist === null) return;
      e.preventDefault();
      const dist   = _pinchDist(_activeTouches);
      const rect   = container.getBoundingClientRect();
      const cx     = (pts[0].x + pts[1].x) / 2 - rect.left;
      const cy     = (pts[0].y + pts[1].y) / 2 - rect.top;
      this.card._state.applyMapZoom?.(
        (this.card._state.mapZoom?.() ?? 1) * (dist / _lastPinchDist),
        cx, cy,
      );
      applyTransform();
      _lastPinchDist = dist;
    }, { passive: false });

    this.card._on(container, "touchend", (e) => {
      Array.from(e.changedTouches).forEach((t) => {
        delete _activeTouches[t.identifier];
      });
      if (Object.keys(_activeTouches).length < 2) _lastPinchDist = null;
    });

    // Clamp + apply NOW: the freshly-mounted container is measurable, so a restored
    // view that no longer fits this container is corrected synchronously (before
    // paint) — no blank-map flash. The renderer baked the stored (possibly
    // off-screen) transform into the inline style; this overwrites it.
    applyTransform();
    // ...and keep it on-screen through a LIVE resize (window resize / rotation while
    // mounted, no reload): observe the container so its size changes re-clamp.
    this._observeMapResize(container, applyTransform);
  };

  // One container ResizeObserver per bindings instance. The container is recreated
  // on each render that swaps the map HTML, so re-point the observer at the fresh
  // node (keeping it when the node is unchanged avoids churn on no-op renders). RO
  // fires once on observe() and on every later size change, re-running applyTransform
  // (which clamps) — covers a live resize that doesn't trigger a re-render.
  proto._observeMapResize = function (container, applyTransform) {
    this._mapResizeApply = applyTransform;
    if (typeof ResizeObserver === "undefined") return;
    if (this._mapResizeObserver && this._mapResizeTarget === container) return;
    if (this._mapResizeObserver) this._mapResizeObserver.disconnect();
    this._mapResizeTarget = container;
    this._mapResizeObserver = new ResizeObserver(() => this._mapResizeApply?.());
    this._mapResizeObserver.observe(container);
  };

  // Host teardown: drop the observer so it can't fire (or pin a detached container)
  // after the card is removed. Mirrors flushMapTransform's disconnectedCallback care.
  proto._teardownMapResize = function () {
    if (this._mapResizeObserver) { this._mapResizeObserver.disconnect(); this._mapResizeObserver = null; }
    this._mapResizeTarget = null;
    this._mapResizeApply = null;
  };
}

function _pinchDist(touches) {
  const [a, b] = Object.values(touches);
  return Math.sqrt((a.x - b.x) ** 2 + (a.y - b.y) ** 2);
}

/* =========================================================
   FILE → FITTED BASE64  (websocket-safe image upload)
   =========================================================
   HA's websocket caps a single inbound frame at 4 MiB (aiohttp's
   default max_msg_size; HA exposes no knob to raise it). A raw
   high-res PNG base64-encodes ~33% larger, so anything past ~3 MB of
   raw image overruns the frame: HA closes the socket and callService
   rejects with the bare number 3 (ERR_CONNECTION_LOST). So we shrink
   the payload BEFORE upload, with two profiles:

   - CV variants (dark/light/default) are consumed by the segmenter.
     Their absolute pixels matter (fixed area floors) and the dark/light
     pair must stay within ~6% scale of each other for alignment, so we
     MUST NOT silently rescale them: pass through if the original fits,
     otherwise hard-fail and ask for a smaller screenshot.
   - Custom backdrops are display/tracing images only (never segmented),
     so we downscale + recompress them freely to fit. Transparency must
     survive (the backdrop composites over a themeable surface), so we
     encode WebP only when a round-trip probe proves THIS engine keeps
     alpha, else PNG (always alpha-safe).
   ========================================================= */

// ~3.24 MiB of base64 — ~19% under HA's 4 MiB frame, leaving ~800 KB of
// headroom for the JSON envelope. Images whose base64 fits this upload at full
// quality (no recompression); larger custom backdrops downscale to meet it.
const _WS_SAFE_BASE64_BYTES = 3_400_000;

// Decoded byte count of a base64 string (no data: prefix): 4 chars -> 3 bytes,
// minus '=' padding. This — not the string length — is the size to budget.
function _b64Bytes(b64) {
  const n = b64.length;
  if (!n) return 0;
  let pad = 0;
  if (b64.charCodeAt(n - 1) === 61) pad++;
  if (n > 1 && b64.charCodeAt(n - 2) === 61) pad++;
  return Math.floor((n * 3) / 4) - pad;
}

function _blobToBase64(blob) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(reader.error || new Error("FileReader failed"));
    reader.onload = () => {
      const result = String(reader.result || "");
      const comma = result.indexOf(",");
      resolve(comma >= 0 ? result.slice(comma + 1) : result);
    };
    reader.readAsDataURL(blob);
  });
}

// Decode a File to something drawable, honoring EXIF orientation. Prefer
// createImageBitmap({imageOrientation:'from-image'}); fall back to <img> (which
// applies orientation by default) when it is unavailable or rejects the options.
async function _decodeImageFile(file) {
  if (typeof createImageBitmap === "function") {
    try {
      const bmp = await createImageBitmap(file, { imageOrientation: "from-image" });
      return { source: bmp, width: bmp.width, height: bmp.height, close: () => bmp.close?.() };
    } catch (_) {
      /* options bag rejected (older Safari) — fall through to the <img> path */
    }
  }
  const url = URL.createObjectURL(file);
  try {
    const img = await new Promise((resolve, reject) => {
      const im = new Image();
      im.onload = () => resolve(im);
      im.onerror = () => reject(new Error("Could not decode image file"));
      im.src = url;
    });
    return {
      source: img,
      width: img.naturalWidth,
      height: img.naturalHeight,
      close: () => URL.revokeObjectURL(url),
    };
  } catch (e) {
    URL.revokeObjectURL(url);
    throw e;
  }
}

// Does this engine's canvas WebP encoder PRESERVE alpha? Some emit a valid
// image/webp blob with the alpha channel flattened to opaque — a MIME-type
// check can't see that. Round-trip a transparent pixel and read it back.
let _webpAlphaOk = null;
async function _canEncodeWebpAlpha() {
  if (_webpAlphaOk != null) return _webpAlphaOk;
  try {
    const c = document.createElement("canvas");
    c.width = c.height = 2;
    const ctx = c.getContext("2d", { alpha: true });
    ctx.clearRect(0, 0, 2, 2); // (0,0) stays fully transparent
    ctx.fillStyle = "rgba(255,0,0,1)";
    ctx.fillRect(1, 1, 1, 1); // (1,1) opaque
    const blob = await new Promise((res) => c.toBlob(res, "image/webp", 0.8));
    if (!blob || blob.type !== "image/webp" || typeof createImageBitmap !== "function") {
      _webpAlphaOk = false;
      return false;
    }
    const bmp = await createImageBitmap(blob);
    const c2 = document.createElement("canvas");
    c2.width = c2.height = 2;
    const ctx2 = c2.getContext("2d", { alpha: true });
    ctx2.clearRect(0, 0, 2, 2);
    ctx2.drawImage(bmp, 0, 0);
    bmp.close?.();
    _webpAlphaOk = ctx2.getImageData(0, 0, 1, 1).data[3] === 0; // transparent pixel survived?
  } catch (_) {
    _webpAlphaOk = false;
  }
  return _webpAlphaOk;
}

function _encodeCanvas(source, w, h, mime, quality) {
  const canvas = document.createElement("canvas");
  canvas.width = w;
  canvas.height = h;
  const ctx = canvas.getContext("2d", { alpha: true });
  if (!ctx) return Promise.reject(new Error("Could not get a 2D canvas context"));
  ctx.imageSmoothingEnabled = true;
  ctx.imageSmoothingQuality = "high";
  ctx.drawImage(source, 0, 0, w, h); // onto a cleared (transparent) canvas — alpha kept
  return new Promise((resolve, reject) =>
    canvas.toBlob(
      (b) => (b ? resolve(b) : reject(new Error("canvas.toBlob returned null (encode failed)"))),
      mime,
      quality,
    ),
  );
}

// Returns { base64, width, height, mime, bytes }.
//   allowDownscale=false (CV variants) → passthrough if it fits, else throw.
//   allowDownscale=true  (backdrop)    → downscale + recompress to fit the ceiling.
async function _imageFileToFittedBase64(
  file,
  { maxDim = 2048, ceilingBytes = _WS_SAFE_BASE64_BYTES, allowDownscale = true } = {},
) {
  // 1) Byte-passthrough: if the original already fits, upload it verbatim —
  //    lossless, alpha-perfect, and (for CV) no rescale that could desync the
  //    dark/light pair or trip the segmentor's pixel-area floors. Cheap-estimate
  //    from file.size first so we don't base64 a huge file just to discard it.
  if (Math.ceil(file.size / 3) * 4 <= ceilingBytes) {
    const original = await _blobToBase64(file);
    const bytes = _b64Bytes(original);
    if (bytes <= ceilingBytes) {
      return { base64: original, width: null, height: null, mime: file.type || null, bytes };
    }
  }

  // 2) Too big. CV variants must never be silently downscaled.
  if (!allowDownscale) {
    throw new Error(
      "Image too large for upload. Crop or shrink this map screenshot to a smaller file, then try again.",
    );
  }

  // 3) Custom backdrop: decode + recompress, shrinking until it fits the frame.
  const dec = await _decodeImageFile(file);
  try {
    const { source, width: srcW, height: srcH } = dec;
    if (!srcW || !srcH) throw new Error("Decoded image has zero size (corrupt or unsupported file)");
    const mime = (await _canEncodeWebpAlpha()) ? "image/webp" : "image/png";

    let curMax = Math.max(1, Math.floor(maxDim));
    let quality = 0.85;
    let best = null;
    let warned = false;
    for (let i = 0; i < 7; i++) {
      const ratio = Math.min(1, curMax / Math.max(srcW, srcH)); // never upscale
      const outW = Math.max(1, Math.round(srcW * ratio));
      const outH = Math.max(1, Math.round(srcH * ratio));
      const blob = await _encodeCanvas(source, outW, outH, mime, mime === "image/webp" ? quality : undefined);
      const base64 = await _blobToBase64(blob);
      const bytes = _b64Bytes(base64);
      const result = { base64, width: outW, height: outH, mime, bytes };
      if (!best || bytes < best.bytes) best = result;
      if (ratio < 1 && !warned) {
        console.warn(
          `[eufy-vacuum-command-center] backdrop downscaled to ${outW}×${outH} to fit the upload limit`,
        );
        warned = true;
      }
      if (bytes <= ceilingBytes) return result;
      const nextMax = Math.max(256, Math.floor(curMax * 0.8));
      if (mime === "image/webp" && quality > 0.5) quality = +(quality - 0.1).toFixed(2);
      if (nextMax === curMax && (mime !== "image/webp" || quality <= 0.5)) break; // floors hit
      curMax = nextMax;
    }
    return best; // smallest we could make it; err===3 mapper covers a true overrun
  } finally {
    dec.close?.();
  }
}

// Map a callService rejection to a user-facing message. A bare numeric 3
// (ERR_CONNECTION_LOST) or a "Connection lost" Error means the WS frame was
// dropped — almost always the payload still overran HA's 4 MiB limit.
// `tRaw` is the RAW translator (the action-status message sink escapeHtml()s it —
// model A; passing t() would double-escape). The backend `err.message` passes
// through raw (the sink escapes it).
function _uploadErrorMessage(err, tRaw) {
  if (err === 3 || (err && typeof err.message === "string" && /connection lost/i.test(err.message))) {
    return tRaw("bind_map.image_too_large");
  }
  return err && err.message ? err.message : tRaw("bind_map.upload_failed_generic");
}
