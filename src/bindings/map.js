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
              message: "No active map found",
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
            if (!fitted) throw new Error("Could not prepare the image for upload");
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
              message: _uploadErrorMessage(err),
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
            ok ? `${variant.charAt(0).toUpperCase()}${variant.slice(1)} image deleted`
               : `Could not delete ${variant} image`,
            { kind: ok ? "success" : "error" }
          );
        } catch (err) {
          console.error("[eufy-vacuum-command-center] deleteMapImage failed:", err);
          this.card._state.setMapActionStatus?.({
            type: "delete", variant, status: "error",
            message: err?.message ?? "Delete failed",
          });
          this.card.showToast?.(`Could not delete ${variant} image`, { kind: "error" });
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
            message: err?.message ?? "Analysis failed",
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
              ? "Map image still loading — wait for the live map to appear, then save again (or upload a backdrop)."
              : (res?.reason ? `Save failed: ${res.reason}` : "Save failed");
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
            message: err?.message ?? "Save failed",
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
        if (this.card._mapDragOccurred) { this.card._mapDragOccurred = false; return; }
        const r = composeLayers.getBoundingClientRect();
        if (!r.width || !r.height) return;
        this.card._state.placeComposeScoped(
          id,
          ((e.clientX - r.left) / r.width) * 100,
          ((e.clientY - r.top) / r.height) * 100,
        );
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
        const rot = this.card._state.mapRotation?.() ?? 0;
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
        const mapId = this.card._state.mapSegmentsData?.()?.map_id
          ?? this.card._state.activeMapId?.() ?? null;
        this.card._actions.rotateLiveMap?.(mapId);
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
function _uploadErrorMessage(err) {
  if (err === 3 || (err && typeof err.message === "string" && /connection lost/i.test(err.message))) {
    return "Image too large even after resizing — please pick a smaller image.";
  }
  return err && err.message ? err.message : "Upload failed";
}
