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
} from "../constants.js";

export function applyMapActions(proto) {

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
}
