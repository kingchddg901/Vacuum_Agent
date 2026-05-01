// Service wrappers for map segment reads, image analysis/upload, and segment adjustment.
import {
  DOMAIN,
  SERVICE_GET_MAP_SEGMENTS,
  SERVICE_ANALYZE_MAP_IMAGE,
  SERVICE_UPLOAD_MAP_IMAGE,
  SERVICE_ADJUST_MAP_SEGMENT,
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
}
