// Foundational HA entity/state access helpers shared by every other state module.

import { ENTITY, INVALID_STATES, vacuumObjectId } from "../constants.js";

export function applyCoreState(proto) {

  /* === HASS / ENTITY ACCESS === */

  /**
   * Single access point for hass.states — guards against missing hass.
   * @param {string} entityId
   * @returns {object|null}
   */
  proto.entity = function (entityId) {
    if (!entityId) return null;
    return this.hass?.states?.[entityId] ?? null;
  };

  /** @returns {string|null} entity .state string, or null if unavailable */
  proto.stateOf = function (entityId) {
    return this.entity(entityId)?.state ?? null;
  };

  /** @returns {object} entity attributes, or {} when missing */
  proto.attrsOf = function (entityId) {
    return this.entity(entityId)?.attributes ?? {};
  };

  /** Returns false for HA sentinel values: "unknown", "unavailable", "". */
  proto.isValidState = function (value) {
    if (value == null) return false;
    return !INVALID_STATES.has(String(value));
  };

  /** Returns true when the entity exists and has a valid (non-sentinel) state. */
  proto.hasEntity = function (entityId) {
    const s = this.stateOf(entityId);
    return s !== null && this.isValidState(s);
  };

  /* === VACUUM RESOLUTION === */

  /** @returns {string|null} full vacuum entity ID from card config */
  proto.vacuumEntityId = function () {
    return this.config?.vacuum_entity_id ?? null;
  };

  /** "vacuum.alfred" → "alfred". Used to construct integration entity IDs. */
  proto.vacuumObjectId = function () {
    return vacuumObjectId(this.vacuumEntityId());
  };

  /** @returns {string|null} vacuum HA state ("docked", "cleaning", "returning", "paused", "error", …) */
  proto.vacuumState = function () {
    const entityId = this.vacuumEntityId();
    if (!entityId) return null;
    return this.stateOf(entityId);
  };

  /**
   * Pre-formatted, display-ready vacuum state label sourced from the
   * dashboard snapshot's lifecycle slice (server-side `_display_label`).
   * Returns null when the snapshot hasn't landed yet — the header
   * renderers fall back to title-casing the raw vacuumState() value.
   *
   * Mirrors the dock_status / dock_status_label pair so card-side
   * vocabulary normalization is no longer needed for status display.
   * Future multi-brand adapters can override vocabulary server-side
   * without the card having to know.
   *
   * @returns {string|null}
   */
  proto.vacuumStateLabel = function () {
    return this.dashboardLifecycle?.()?.vacuum_state_label ?? null;
  };

  /** @returns {object} vacuum entity attributes (battery_level, fan_speed, etc.) */
  proto.vacuumAttrs = function () {
    const entityId = this.vacuumEntityId();
    if (!entityId) return {};
    return this.attrsOf(entityId);
  };

  /** @returns {number|null} current battery level (0–100), or null */
  proto.batteryLevel = function () {
    const raw = this.vacuumAttrs()?.battery_level;
    const n   = Number(raw);
    return Number.isFinite(n) ? n : null;
  };

  /**
   * Whether the vacuum is currently charging. Reads the integration's
   * binary_sensor.<vacuum>_charging entity. Returns false (not null) when
   * the sensor is unavailable so renderers can treat it as a clean boolean.
   * @returns {boolean}
   */
  proto.isCharging = function () {
    const objectId = this.vacuumObjectId();
    if (!objectId) return false;
    return this.stateOf(`binary_sensor.${objectId}_charging`) === "on";
  };

  /**
   * Resolves the vacuum's current battery state into one of five buckets
   * for visual presentation. Used by the map view's animal companion (the
   * `battery-state` attribute on <animal-svg>) and any other consumer that
   * wants the same banding.
   *
   * Bands (battery_level percent):
   *   charging      — isCharging() is true (overrides level-based bands)
   *   good          — battery > 50
   *   mid           — 25 < battery ≤ 50
   *   warn          — 15 < battery ≤ 25
   *   low           — battery ≤ 15
   *
   * Battery unavailable → "good" (least-alarming default).
   *
   * @returns {'good'|'mid'|'warn'|'low'|'charging'}
   */
  proto.batteryState = function () {
    if (this.isCharging()) return "charging";
    const level = this.batteryLevel();
    if (level == null) return "good";
    if (level <= 15) return "low";
    if (level <= 25) return "warn";
    if (level <= 50) return "mid";
    return "good";
  };

  /**
   * User-friendly vacuum name. Priority: friendly_name attribute → formatted object_id.
   * @returns {string}
   */
  proto.vacuumDisplayName = function () {
    const attrs = this.vacuumAttrs();
    if (attrs?.friendly_name) return String(attrs.friendly_name).trim();

    const objectId = this.vacuumObjectId();
    if (!objectId) return "Vacuum";

    return objectId
      .replace(/_/g, " ")
      .replace(/\b\w/g, (c) => c.toUpperCase());
  };

  /**
   * Current robot position from live raw coordinate sensors.
   * @returns {{ x: number, y: number }|null}
   */
  proto.rawRobotPosition = function () {
    const vacuumEntityId = this.vacuumEntityId();
    if (!vacuumEntityId) return null;

    const rawX = Number(this.stateOf(ENTITY.robotPositionXRaw(vacuumEntityId)));
    const rawY = Number(this.stateOf(ENTITY.robotPositionYRaw(vacuumEntityId)));
    if (!Number.isFinite(rawX) || !Number.isFinite(rawY)) return null;

    return {
      x: Math.round(rawX),
      y: Math.round(rawY),
    };
  };

  /* === SHARED UTILITY HELPERS === */

  /**
   * Read one attribute from an entity, returning fallback when missing.
   * @param {string} entityId
   * @param {string} key
   * @param {*} [fallback=null]
   */
  proto.attrOf = function (entityId, key, fallback = null) {
    const attrs = this.attrsOf(entityId);
    const value = attrs?.[key];
    return value !== undefined ? value : fallback;
  };
}
