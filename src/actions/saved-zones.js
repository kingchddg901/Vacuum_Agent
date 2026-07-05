// Service wrappers for saved-zone CRUD + filing + clean (Wave 3b).

import {
  DOMAIN,
  SERVICE_GET_MAP_SEGMENTS,
  SERVICE_CREATE_SAVED_ZONE,
  SERVICE_RENAME_SAVED_ZONE,
  SERVICE_DELETE_SAVED_ZONE,
  SERVICE_SET_SAVED_ZONE_ROOM,
  SERVICE_CLEAN_SAVED_ZONE,
  SERVICE_CLEAN_SAVED_ZONES,
} from "../constants.js";

export function applySavedZonesActions(proto) {
  /**
   * Fetch just the saved-zones list (off get_map_segments) for the panel, WITHOUT
   * touching map state — the response's saved_zones ride into an isolated state slot
   * so a background refresh can never clobber the map's optimistic overlays (mirrors
   * how run-profiles fetches into its own library, not _mapSegmentsData).
   * @returns {Promise<object[]|null>}
   */
  proto.getSavedZones = async function ({ vacuum_entity_id, map_id } = {}) {
    if (!vacuum_entity_id || !map_id) return null;
    const result = await this.callService(
      DOMAIN,
      SERVICE_GET_MAP_SEGMENTS,
      { vacuum_entity_id, map_id },
      true
    );
    const data = result?.response ?? result;
    return data?.saved_zones ?? [];
  };

  /**
   * Create a named saved zone from a normalized 0-1 polygon.
   * @returns {Promise<object|null>} {saved, zone_id, zone}
   */
  proto.createSavedZone = async function ({
    vacuum_entity_id,
    map_id,
    name,
    geometry,
    kind,
  } = {}) {
    const data = { vacuum_entity_id, map_id, name, geometry };
    if (kind != null) data.kind = kind;
    const result = await this.callService(DOMAIN, SERVICE_CREATE_SAVED_ZONE, data, true);
    return result?.response ?? result;
  };

  proto.renameSavedZone = async function ({ vacuum_entity_id, map_id, zone_id, name } = {}) {
    const result = await this.callService(
      DOMAIN,
      SERVICE_RENAME_SAVED_ZONE,
      { vacuum_entity_id, map_id, zone_id, name },
      true
    );
    return result?.response ?? result;
  };

  proto.deleteSavedZone = async function ({ vacuum_entity_id, map_id, zone_id } = {}) {
    const result = await this.callService(
      DOMAIN,
      SERVICE_DELETE_SAVED_ZONE,
      { vacuum_entity_id, map_id, zone_id },
      true
    );
    return result?.response ?? result;
  };

  /** File the zone under a room (or null = Unassigned). Filing only. */
  proto.setSavedZoneRoom = async function ({
    vacuum_entity_id,
    map_id,
    zone_id,
    room_number,
  } = {}) {
    const result = await this.callService(
      DOMAIN,
      SERVICE_SET_SAVED_ZONE_ROOM,
      { vacuum_entity_id, map_id, zone_id, room_number: room_number ?? null },
      true
    );
    return result?.response ?? result;
  };

  /**
   * Fire a saved zone's geometry as an ad-hoc clean.
   * @returns {Promise<object|null>} {cleaned, reason?} — reason ∈
   *   map_not_active | zone_not_found | bad_geometry.
   */
  proto.cleanSavedZone = async function ({
    vacuum_entity_id,
    map_id,
    zone_id,
    clean_times,
  } = {}) {
    const data = { vacuum_entity_id, map_id, zone_id };
    if (clean_times != null) data.clean_times = clean_times;
    this.state.resetLiveTrail?.();   // fresh trace for this saved-zone clean
    const result = await this.callService(DOMAIN, SERVICE_CLEAN_SAVED_ZONE, data, true);
    return result?.response ?? result;
  };

  /**
   * Fire SEVERAL saved zones as one clean (panel multi-select). The device cleans the
   * whole set in a single run; the per-brand count + size caps are enforced service-side.
   * @returns {Promise<object|null>} {cleaned, reason?, zone_count?} — reason ∈
   *   map_not_active | zone_not_found | bad_geometry | no_zones.
   */
  proto.cleanSavedZones = async function ({
    vacuum_entity_id,
    map_id,
    zone_ids,
    clean_times,
  } = {}) {
    const data = { vacuum_entity_id, map_id, zone_ids: zone_ids ?? [] };
    if (clean_times != null) data.clean_times = clean_times;
    this.state.resetLiveTrail?.();   // fresh trace for this multi-zone clean
    const result = await this.callService(DOMAIN, SERVICE_CLEAN_SAVED_ZONES, data, true);
    return result?.response ?? result;
  };
}
