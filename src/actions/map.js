// Service wrappers for map segment reads, image analysis/upload, segment
// adjustment, and the two backend-persisted UI overlays (segment→room
// links + companion anchors). The overlay services replaced
// browser-localStorage storage so the same configuration follows the
// user across browsers and devices.
import {
  DOMAIN,
  SERVICE_GET_MAP_SEGMENTS,
  SERVICE_ANALYZE_MAP_IMAGE,
  SERVICE_UPLOAD_MAP_IMAGE,
  SERVICE_DELETE_MAP_IMAGE,
  SERVICE_ADJUST_MAP_SEGMENT,
  SERVICE_SET_SEGMENT_ROOM_LINK,
  SERVICE_SET_COMPANION_ANCHOR,
  SERVICE_SET_LIVE_MAP_ROTATION,
  SERVICE_SET_MAP_OVERLAY_VISIBILITY,
  SERVICE_SET_SEGMENTATION_MODE,
  SERVICE_SET_CUSTOM_SEGMENTS,
  SERVICE_CREATE_CUSTOM_LAYOUT,
  SERVICE_RENAME_CUSTOM_LAYOUT,
  SERVICE_DELETE_CUSTOM_LAYOUT,
  SERVICE_SET_ACTIVE_CUSTOM_LAYOUT,
  SERVICE_START_ZONE_CLEAN,
} from "../constants.js";

export function applyMapActions(proto) {

  /**
   * Dispatch an ad-hoc free-form zone clean (draw a box on the live map → clean
   * it). `zones` is a list of normalized rectangles [x0,y0,x1,y1] (fractions 0-1
   * of the live-map image, top-left origin). Fire-and-forget: the backend bypasses
   * the room-id job pipeline. Returns the service response (a status dict) or null.
   *
   * @param {number[][]} zones
   * @param {number} [cleanTimes=1]
   */
  proto.cleanZone = async function (zones, cleanTimes = 1) {
    const vacuum = this.state.vacuumEntityId();
    if (!vacuum || !Array.isArray(zones) || zones.length === 0) return null;
    const data = { vacuum_entity_id: vacuum, zones, clean_times: cleanTimes };
    const mapId = this.state.activeMapId?.();
    if (mapId) data.map_id = mapId;
    return await this.callService(DOMAIN, SERVICE_START_ZONE_CLEAN, data, true);
  };

  /**
   * Set one of the vacuum's provider setting selects (suction/mode/intensity/water)
   * to `option`. These are the device's current settings a zone clean runs off, so
   * the zone panel edits the real entity directly via the HA `select` service.
   *
   * @param {string} entityId  a select.* entity id from settingEntities()
   * @param {string} option    one of the entity's options
   */
  proto.setVacuumSetting = async function (entityId, option) {
    if (!entityId || option == null) return null;
    return await this.callService("select", "select_option", {
      entity_id: entityId,
      option,
    });
  };

  /**
   * Fetch map segments and store the result in state. Also drives the
   * one-time legacy-localStorage migration for the two map UI overlays
   * (segment_room_links, companion_anchors). The migration runs here
   * (not in state) because state has no back-reference to call services.
   *
   * @param {string} mapId
   */
  proto.getMapSegments = async function (mapId) {
    const vacuum = this.state.vacuumEntityId();
    if (!vacuum || !mapId) return;

    const result = await this.callService(
      DOMAIN,
      SERVICE_GET_MAP_SEGMENTS,
      { vacuum_entity_id: vacuum, map_id: mapId },
      true, // returnResponse
    );

    const data = result?.response ?? result ?? null;
    if (data == null) return;
    this.state.setMapSegmentsData(data);
    // Custom mode: rebuild the composer draft from the saved segments (once per
    // map) so previously-authored rooms are editable again.
    this.state.maybeLoadComposeDraft?.(data);

    // Legacy migration. Runs every fetch but bails fast if there's
    // nothing in localStorage. Push only entries the backend doesn't
    // already know about, then clear the legacy key.
    try {
      await this._migrateLegacyMapOverlays(mapId, data);
    } catch (err) {
      console.warn("[evcc] map overlay migration failed", err);
    }
  };

  /**
   * One-time push of any legacy localStorage map overlays into backend
   * storage. Called from getMapSegments after the segments payload
   * lands so we can compare against backend-known links and skip
   * already-migrated entries.
   */
  proto._migrateLegacyMapOverlays = async function (mapId, segmentsPayload) {
    const state = this.state;

    // -- Segment-room links --
    const legacyLinks = state.getLegacySegmentRoomLinks?.();
    if (legacyLinks && Object.keys(legacyLinks).length > 0) {
      const backendLinks = new Set();
      for (const seg of segmentsPayload?.segments || []) {
        if (seg && seg.room_id != null) {
          backendLinks.add(String(seg.segment_id));
        }
      }
      let pushed = 0;
      for (const [segId, roomId] of Object.entries(legacyLinks)) {
        if (backendLinks.has(String(segId))) continue;
        await this.setSegmentRoomLink(mapId, segId, roomId);
        pushed += 1;
      }
      state.clearLegacySegmentRoomLinks?.();
      if (pushed > 0 && console?.info) {
        console.info(
          `[evcc] Migrated ${pushed} segment-room link(s) from localStorage to backend.`
        );
      }
    }

    // -- Companion anchors --
    const legacyAnchors = state.getLegacyDotAnchors?.();
    if (legacyAnchors && Object.keys(legacyAnchors).length > 0) {
      const backendAnchors = segmentsPayload?.companion_anchors || {};
      let pushed = 0;
      for (const [roomId, val] of Object.entries(legacyAnchors)) {
        if (backendAnchors[roomId]) continue;
        const pct_x = val?.pct_x;
        const pct_y = val?.pct_y;
        if (pct_x == null || pct_y == null) continue;
        await this.setCompanionAnchor(mapId, roomId, pct_x, pct_y);
        pushed += 1;
      }
      state.clearLegacyDotAnchors?.();
      if (pushed > 0 && console?.info) {
        console.info(
          `[evcc] Migrated ${pushed} companion anchor(s) from localStorage to backend.`
        );
      }
    }
  };

  /**
   * Trigger server-side map image analysis.
   * WHY direct hass.callService: errors must propagate to the binding's try/catch for status feedback.
   */
  proto.analyzeMapImage = async function (mapId, options = {}) {
    const vacuum = this.state.vacuumEntityId();
    if (!vacuum || !mapId) return;

    await this.hass.callService(
      DOMAIN,
      SERVICE_ANALYZE_MAP_IMAGE,
      { vacuum_entity_id: vacuum, map_id: mapId, ...options },
      undefined, // target
      true,      // notifyOnError — let HA surface the toast too
      true,      // returnResponse — service is registered supports_response=True;
                 // modern HA silently rejects the call if the caller doesn't opt in.
    );
  };

  /** Upload a base64-encoded map image. Direct hass.callService for the same reason as analyzeMapImage. */
  proto.uploadMapImage = async function (mapId, imageBase64, options = {}) {
    const vacuum = this.state.vacuumEntityId();
    if (!vacuum || !mapId) return;

    await this.hass.callService(
      DOMAIN,
      SERVICE_UPLOAD_MAP_IMAGE,
      { vacuum_entity_id: vacuum, map_id: mapId, image_base64: imageBase64, ...options },
      undefined,
      true,
      true,      // returnResponse — service is registered supports_response=True;
                 // without this the call silently no-ops, file never gets written.
    );
  };

  /**
   * Delete a single uploaded map image variant. Mirrors uploadMapImage's
   * direct hass.callService pattern — supports_response=True on the
   * backend means we must opt into returnResponse or the call silently
   * no-ops. Returns the response payload or null on failure.
   */
  proto.deleteMapImage = async function (mapId, variant = "default") {
    const vacuum = this.state.vacuumEntityId();
    if (!vacuum || !mapId) return null;

    try {
      const result = await this.hass.callService(
        DOMAIN,
        SERVICE_DELETE_MAP_IMAGE,
        { vacuum_entity_id: vacuum, map_id: mapId, variant },
        undefined,
        true,
        true,
      );
      return result?.response ?? result ?? null;
    } catch (err) {
      console.error("[eufy-vacuum-command-center] deleteMapImage failed", err);
      return null;
    }
  };

  /** Nudge or resize a map segment. Direct hass.callService for the same reason as analyzeMapImage. */
  proto.adjustMapSegment = async function (mapId, segmentId, adjustment = {}) {
    const vacuum = this.state.vacuumEntityId();
    if (!vacuum || !mapId) return;

    await this.hass.callService(
      DOMAIN,
      SERVICE_ADJUST_MAP_SEGMENT,
      { vacuum_entity_id: vacuum, map_id: mapId, segment_id: segmentId, ...adjustment },
      undefined,
      true,
      true,      // returnResponse — same as upload/analyze above
    );
  };

  /**
   * Persist (or clear) the segment→room link on the backend. Pass null
   * for roomId to clear the existing link. Returns the full updated
   * mapping so callers can sync local state without a refetch.
   */
  proto.setSegmentRoomLink = async function (mapId, segmentId, roomId) {
    const vacuum = this.state.vacuumEntityId();
    if (!vacuum || !mapId || !segmentId) return null;

    const result = await this.callService(
      DOMAIN,
      SERVICE_SET_SEGMENT_ROOM_LINK,
      {
        vacuum_entity_id: vacuum,
        map_id: mapId,
        segment_id: segmentId,
        room_id: roomId == null ? null : String(roomId),
      },
      true,
    );
    return result?.response ?? result ?? null;
  };

  /**
   * Persist (or clear) the per-room companion sprite anchor. Pass null
   * for both pct_x and pct_y to clear. pct values are 0-100. Returns
   * the full updated anchors map.
   */
  proto.setCompanionAnchor = async function (mapId, roomId, pctX, pctY) {
    const vacuum = this.state.vacuumEntityId();
    if (!vacuum || !mapId || roomId == null) return null;

    const payload = {
      vacuum_entity_id: vacuum,
      map_id: mapId,
      room_id: String(roomId),
    };
    if (pctX != null) payload.pct_x = Number(pctX);
    if (pctY != null) payload.pct_y = Number(pctY);

    const result = await this.callService(
      DOMAIN,
      SERVICE_SET_COMPANION_ANCHOR,
      payload,
      true,
    );
    return result?.response ?? result ?? null;
  };

  /**
   * Rotate the live map 90° CW (display only; backend-stored per map). Sets an
   * optimistic overlay synchronously so the turn is instant, then persists via the
   * service; the dashboard snapshot reconciles the overlay on its next push.
   */
  proto.rotateLiveMap = async function (mapId) {
    const vacuum = this.state.vacuumEntityId();
    if (!vacuum || !mapId) return null;
    const next = (Number(this.state.mapRotation?.() ?? 0) + 90) % 360;
    this.state.setMapRotationOptimistic?.(next);
    const result = await this.callService(
      DOMAIN,
      SERVICE_SET_LIVE_MAP_ROTATION,
      { vacuum_entity_id: vacuum, map_id: mapId, rotation: next },
      true,
    );
    return result?.response ?? result ?? null;
  };

  /**
   * Toggle one map_state_source overlay layer's visibility (Wave 3c). Sends only the
   * one layer as a partial `visibility` delta (the backend merges over the defaults);
   * map_id auto-resolves server-side when omitted. Optimistic flip first so the
   * checkbox + overlay update instantly; the snapshot reconciles on its next push.
   */
  proto.setMapOverlayVisibility = async function (layer, visible) {
    const vacuum = this.state.vacuumEntityId();
    if (!vacuum || !layer) return null;
    this.state.setOverlayVisibilityOptimistic?.(layer, visible);
    const data = { vacuum_entity_id: vacuum, visibility: { [layer]: Boolean(visible) } };
    const mapId = this.state.activeMapId?.();
    if (mapId) data.map_id = mapId;
    const result = await this.callService(
      DOMAIN, SERVICE_SET_MAP_OVERLAY_VISIBILITY, data, true,
    );
    return result?.response ?? result ?? null;
  };

  /**
   * Flip a map between CV (auto-detected) and Custom (manually authored)
   * segmentation. The backend only swaps the active segment store — it never
   * re-runs the segmenter — so this is cheap and lossless in both directions.
   * Returns the service response { mode, segment_count } or null.
   */
  proto.setSegmentationMode = async function (mapId, mode) {
    const vacuum = this.state.vacuumEntityId();
    if (!vacuum || !mapId) return null;
    const result = await this.callService(
      DOMAIN,
      SERVICE_SET_SEGMENTATION_MODE,
      { vacuum_entity_id: vacuum, map_id: mapId, mode },
      true,
    );
    return result?.response ?? result ?? null;
  };

  /**
   * Replace-all write of manually-authored custom segments. `segments` is a list
   * of { id?, primitives:[...] }; the backend rasterises each into a CV-shaped
   * segment (set_custom_segments). Returns the service response or null.
   */
  proto.setCustomSegments = async function (mapId, segments, backdropDims) {
    const vacuum = this.state.vacuumEntityId();
    if (!vacuum || !mapId) return null;
    const payload = { vacuum_entity_id: vacuum, map_id: mapId, segments };
    // For a live-image-backed layout (no uploaded backdrop) the caller passes the
    // rendered live image's natural pixel size so the saver can rasterise.
    if (backdropDims?.width && backdropDims?.height) {
      payload.backdrop_width = Math.round(backdropDims.width);
      payload.backdrop_height = Math.round(backdropDims.height);
    }
    const result = await this.callService(
      DOMAIN,
      SERVICE_SET_CUSTOM_SEGMENTS,
      payload,
      true,
    );
    return result?.response ?? result ?? null;
  };

  /* =========================================================
     CUSTOM LAYOUTS (named no-CV segmentations per map)
     ========================================================= */

  /** Activate a custom layout (+ flip to custom mode). Null layoutId auto-creates. */
  proto.setActiveCustomLayout = async function (mapId, layoutId) {
    const vacuum = this.state.vacuumEntityId();
    if (!vacuum || !mapId) return null;
    const result = await this.callService(
      DOMAIN, SERVICE_SET_ACTIVE_CUSTOM_LAYOUT,
      { vacuum_entity_id: vacuum, map_id: mapId, layout_id: layoutId ?? null },
      true,
    );
    return result?.response ?? result ?? null;
  };

  /** Create + activate a new named custom layout. opts.backdropSource="live" pins it
   *  to the brand's live-map image (the "Live map" source). */
  proto.createCustomLayout = async function (mapId, name, opts = {}) {
    const vacuum = this.state.vacuumEntityId();
    if (!vacuum || !mapId) return null;
    const data = { vacuum_entity_id: vacuum, map_id: mapId, name: name ?? "" };
    if (opts.backdropSource) data.backdrop_source = String(opts.backdropSource);
    const result = await this.callService(
      DOMAIN, SERVICE_CREATE_CUSTOM_LAYOUT, data, true,
    );
    return result?.response ?? result ?? null;
  };

  /** Rename a custom layout. */
  proto.renameCustomLayout = async function (mapId, layoutId, name) {
    const vacuum = this.state.vacuumEntityId();
    if (!vacuum || !mapId || !layoutId) return null;
    const result = await this.callService(
      DOMAIN, SERVICE_RENAME_CUSTOM_LAYOUT,
      { vacuum_entity_id: vacuum, map_id: mapId, layout_id: layoutId, name: name ?? "" },
      true,
    );
    return result?.response ?? result ?? null;
  };

  /** Delete a custom layout (+ its backdrop). */
  proto.deleteCustomLayout = async function (mapId, layoutId) {
    const vacuum = this.state.vacuumEntityId();
    if (!vacuum || !mapId || !layoutId) return null;
    const result = await this.callService(
      DOMAIN, SERVICE_DELETE_CUSTOM_LAYOUT,
      { vacuum_entity_id: vacuum, map_id: mapId, layout_id: layoutId },
      true,
    );
    return result?.response ?? result ?? null;
  };
}
