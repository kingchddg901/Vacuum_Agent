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

/**
 * Mix map binding methods onto the given prototype.
 *
 * @param {object} proto - VacuumCardBindings prototype to extend.
 */
export function applyMapBindings(proto) {

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
    this._bindMapAnimalSelect(root);

    const view = this.card._view;
    if (view === VIEWS.MAP_CONFIG || this.card._state.isMapViewActive?.()) {
      this._ensureMapSegments();
    }
  };

  /* =========================================================
     VIEW TOGGLE
     ========================================================= */

  proto._bindMapViewToggle = function (root) {
    root.querySelectorAll("[data-action='set-map-view']").forEach((btn) => {
      btn.addEventListener("click", () => {
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

      el.addEventListener("click", (e) => {
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
      tooltip.innerHTML =
        `<span class="evcc-map-tooltip-label">${label}</span>` +
        (hint ? `<span class="evcc-map-tooltip-hint">${hint}</span>` : "");
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
      el.addEventListener("pointerenter", (e) => show(el, e));
      el.addEventListener("pointermove",  (e) => move(e));
      el.addEventListener("pointerleave", hide);
      el.addEventListener("click",        hide);
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

      chip.addEventListener("click", (e) => {
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
      btn.addEventListener("click", () => {
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
      btn.addEventListener("click", () => {
        this.card.setView(VIEWS.ROOMS);
      });
    });

    // Segment selection (config mode)
    root.querySelectorAll("[data-action='config-select-segment']").forEach((el) => {
      el.addEventListener("click", (e) => {
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

    // Upload buttons — bind change handler fresh at click time so a
    // re-render while the file picker is open doesn't orphan the listener.
    root.querySelectorAll("[data-action='upload-map-variant']").forEach((btn) => {
      btn.addEventListener("click", () => {
        const variant = btn.dataset.variant;
        const input   = root.querySelector(`[data-variant-input="${variant}"]`);
        if (!input) return;

        const handleChange = async () => {
          input.removeEventListener("change", handleChange);

          const file = input.files?.[0];
          if (!file) return;
          input.value = "";

          const rooms = this.card._state.getRoomsForActiveMap?.() ?? [];
          const mapId = rooms[0]?.mapId ?? null;
          if (!mapId) {
            this.card._state.setMapActionStatus({
              type: "upload", variant, status: "error",
              message: "No active map found",
            });
            this.card._scheduleRender();
            return;
          }

          this.card._state.setMapActionStatus({ type: "upload", variant, status: "busy" });
          this.card._scheduleRender();

          try {
            const base64 = await _fileToBase64(file);
            await this.card._actions.uploadMapImage(mapId, base64, { variant });
            this.card._state.setMapActionStatus({ type: "analyze", status: "busy" });
            this.card._scheduleRender();
            await this.card._actions.analyzeMapImage(mapId, { force_reanalyze: true });
            await this.card._actions.getMapSegments(mapId);
            this.card._state.clearMapActionStatus();
            this.card._scheduleRender();
          } catch (err) {
            console.error("[eufy-vacuum-command-center] Map upload failed:", err);
            this.card._state.setMapActionStatus({
              type: "upload", variant, status: "error",
              message: err?.message ?? "Upload failed",
            });
            this.card._scheduleRender();
          }
        };

        input.addEventListener("change", handleChange);
        input.click();
      });
    });

    // Analyse button
    root.querySelectorAll("[data-action='analyze-map']").forEach((btn) => {
      btn.addEventListener("click", async () => {
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
            message: err?.message ?? "Analysis failed",
          });
          this.card._scheduleRender();
        }
      });
    });

    // Nudge buttons
    root.querySelectorAll("[data-action='nudge-segment']").forEach((btn) => {
      btn.addEventListener("click", async () => {
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
      btn.addEventListener("click", async () => {
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
      btn.addEventListener("click", async () => {
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
      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        const idx = Number(btn.dataset.vertexIndex);
        const cur = this.card._state.configSelectedVertexIndex?.();
        this.card._state.setConfigSelectedVertexIndex(cur === idx ? null : idx);
        this.card._scheduleRender();
      });
    });

    // Vertex nudge
    root.querySelectorAll("[data-action='nudge-vertex']").forEach((btn) => {
      btn.addEventListener("click", async () => {
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
      btn.addEventListener("click", async () => {
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
      btn.addEventListener("click", () => {
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
      sel.addEventListener("change", () => {
        this.card._state.setMapAnimalSelection?.(sel.value);
        this.card._scheduleRender();
      });
    });
    root.querySelectorAll("[data-action='map-animal-scale']").forEach((slider) => {
      // input fires continuously while dragging — update state live.
      // change fires when the thumb is released — schedule a render then.
      slider.addEventListener("input", () => {
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
      slider.addEventListener("change", () => {
        this.card._scheduleRender();
      });
    });
  };

  proto._bindMapAnimal = function (root) {
    root.querySelectorAll("[data-action='map-dot-click']").forEach((el) => {
      const layers = root.querySelector(".evcc-map-layers");
      if (!layers) return;

      el.addEventListener("pointerdown", (e) => {
        if (e.button !== 0) return;
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

        // Compute offset from pointer to the animal's current centre so the
        // icon doesn't snap its centre to the grab point.
        const curPctX = parseFloat(el.style.left) || 0;
        const curPctY = parseFloat(el.style.top)  || 0;
        const offsetX = (e.clientX - layerRect.left) - (curPctX / 100 * layerRect.width);
        const offsetY = (e.clientY - layerRect.top)  - (curPctY / 100 * layerRect.height);

        // Track live position so pointercancel can save the last known good spot.
        let livePctX = curPctX;
        let livePctY = curPctY;

        const onMove = (ev) => {
          livePctX = Math.max(0, Math.min(100,
            (ev.clientX - layerRect.left - offsetX) / layerRect.width  * 100));
          livePctY = Math.max(0, Math.min(100,
            (ev.clientY - layerRect.top  - offsetY) / layerRect.height * 100));
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
      btn.addEventListener("click", (e) => { e.stopPropagation(); _stepZoom(1.25); });
    });
    root.querySelectorAll("[data-action='map-zoom-out']").forEach((btn) => {
      btn.addEventListener("click", (e) => { e.stopPropagation(); _stepZoom(0.8); });
    });
    root.querySelectorAll("[data-action='map-zoom-fit']").forEach((btn) => {
      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        this.card._state.resetMapTransform?.();
        applyTransform();
        this.card._scheduleRender?.();
      });
    });

    // ----------------------------------------------------------
    // Ctrl + wheel zoom — desktop equivalent of pinch. Plain wheel
    // is left to the page (so scrolling the parent dashboard still
    // works); only Ctrl-modified wheel intercepts.
    // ----------------------------------------------------------
    container.addEventListener("wheel", (e) => {
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

    container.addEventListener("pointerdown", (e) => {
      if (e.button !== 0) return;
      // Always reset drag flag so the next click starts clean.
      this.card._mapDragOccurred = false;
      // Don't start a pan drag when the press originates on the
      // animal icon — let its own click handler deal with it.
      if (e.target.closest("[data-action='map-dot-click']")) return;
      _dragging = true;
      _moved    = false;
      _lastX    = e.clientX;
      _lastY    = e.clientY;

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
      };

      document.addEventListener("pointermove", onMove);
      document.addEventListener("pointerup",     onUp);
      document.addEventListener("pointercancel", onUp);
    });

    // ----------------------------------------------------------
    // Double-click on map background → reset transform
    // ----------------------------------------------------------
    container.addEventListener("dblclick", (e) => {
      if (e.target.closest("[data-action='toggle-segment']")) return;
      this.card._state.resetMapTransform?.();
      applyTransform();
    });

    // ----------------------------------------------------------
    // Touch pinch zoom
    // ----------------------------------------------------------
    const _activeTouches = {};
    let _lastPinchDist = null;

    container.addEventListener("touchstart", (e) => {
      Array.from(e.changedTouches).forEach((t) => {
        _activeTouches[t.identifier] = { x: t.clientX, y: t.clientY };
      });
      if (Object.keys(_activeTouches).length === 2) {
        e.preventDefault();
        _lastPinchDist = _pinchDist(_activeTouches);
      }
    }, { passive: false });

    container.addEventListener("touchmove", (e) => {
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

    container.addEventListener("touchend", (e) => {
      Array.from(e.changedTouches).forEach((t) => {
        delete _activeTouches[t.identifier];
      });
      if (Object.keys(_activeTouches).length < 2) _lastPinchDist = null;
    });
  };
}

function _pinchDist(touches) {
  const [a, b] = Object.values(touches);
  return Math.sqrt((a.x - b.x) ** 2 + (a.y - b.y) ** 2);
}

/* =========================================================
   FILE → BASE64
   ========================================================= */

function _fileToBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload  = () => {
      const result = reader.result;
      // strip "data:image/...;base64," prefix
      const comma = result.indexOf(",");
      resolve(comma >= 0 ? result.slice(comma + 1) : result);
    };
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}
