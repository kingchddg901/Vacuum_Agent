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
  SERVICE_ADJUST_MAP_SEGMENT,
  SERVICE_SET_SEGMENT_ROOM_LINK,
  SERVICE_SET_COMPANION_ANCHOR,
} from "../constants.js";

export function applyMapActions(proto) {

  /**
   * Fetch map segments and store the result in state.
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
    if (data != null) this.state.setMapSegmentsData(data);
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
    );
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
