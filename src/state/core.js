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

  /* === SETUP SUB-TAB (live:ENT-11) === */

  /** @returns {"steps"|"system"} */
  proto.setupSubtab = function () {
    return this._setupSubtab === "system" ? "system" : "steps";
  };

  proto.setSetupSubtab = function (value) {
    this._setupSubtab = value === "system" ? "system" : "steps";
  };

  /**
   * One row per role: what we read, and how it was chosen.
   * Assembled server-side (manager._entity_bindings) so the card stays a
   * display layer, per the Setup tab's existing "adapter owns the truth"
   * contract.
   * @returns {Array<object>}
   */
  proto.entityBindings = function () {
    const rows = this.dashboardSnapshot?.()?.entity_bindings;
    return Array.isArray(rows) ? rows : [];
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

  /**
   * The entity the BACKEND resolved for a role, or null.
   *
   * live:ENT-10. The card used to derive its own ids from the vacuum's object_id
   * — `sensor.${objectId}_battery` and friends — which is the same naming
   * assumption the Python side repaired in ENT-1/ENT-5, in a language none of
   * those fixes reach. On issue #49 the battery sensor resolves fine server-side
   * and reads 100, while the card derives an id that does not exist and draws
   * nothing. The resolver already knows the answer; asking it beats guessing.
   *
   * @param {string} role
   * @returns {string|null}
   */
  proto.resolvedEntity = function (role) {
    const id = this.dashboardSnapshot?.()?.resolved_entities?.[role];
    return typeof id === "string" && id ? id : null;
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
    // The vacuum entity's `battery_level` attribute FIRST, so any install where
    // it still exists resolves exactly as before and this can only rescue, never
    // change, a working case.
    const raw = this.vacuumAttrs()?.battery_level;
    const n   = Number(raw);
    if (Number.isFinite(n)) return n;

    // Home Assistant DEPRECATED AND REMOVED battery_level from vacuum entities;
    // battery now lives on its own `sensor.<vacuum>_battery` (device_class
    // battery). Verified on HA 2026.7.4: vacuum.alfred exposes no battery_level
    // at all, while sensor.alfred_battery reads 100.
    //
    // Nothing failed loudly when that happened — this returned null, every
    // consumer treated it as "unknown", and the header battery simply stopped
    // rendering. Chris noticed it as a MISSING FEATURE ("such a normal thing
    // I've never noticed it's missing"), which is what a silent upstream
    // removal looks like from the outside.
    //
    // isCharging() below already reads binary_sensor.<vacuum>_charging, so the
    // separate-entity pattern was known here; battery just never got the same
    // treatment. The shorter copy at the neighbouring seam.
    // The RESOLVED id first (live:ENT-10) — the backend already rescued this on
    // installs whose companions are not named after the vacuum. Falling back to
    // derivation keeps every working install byte-identical.
    const objectId = this.vacuumObjectId();
    const batteryId = this.resolvedEntity("battery")
      || (objectId ? `sensor.${objectId}_battery` : null);
    if (!batteryId) return null;
    const raw2 = this.stateOf(batteryId);
    // The non-value check MUST precede Number(): Number("") is 0, and 0 is
    // finite, so an empty or missing state would read as a FLAT battery rather
    // than an unknown one — "good" becomes "emergency" with no data behind it.
    // Third occurrence of this exact trap in one session (REV-6, CENSUS-6);
    // caught here by [BAT-6] rather than in the field.
    if (raw2 == null || raw2 === "" || raw2 === "unavailable" || raw2 === "unknown") {
      return null;
    }
    const sensor = Number(raw2);
    return Number.isFinite(sensor) ? sensor : null;
  };

  /**
   * Whether the vacuum is currently charging. Reads the integration's
   * binary_sensor.<vacuum>_charging entity. Returns false (not null) when
   * the sensor is unavailable so renderers can treat it as a clean boolean.
   * @returns {boolean}
   */
  proto.isCharging = function () {
    // Same rescue as batteryLevel (live:ENT-10). This is the neighbouring seam
    // the battery comment already pointed at — the two are always broken
    // together, because they carry the identical naming assumption.
    const objectId = this.vacuumObjectId();
    const chargingId = this.resolvedEntity("charging")
      || (objectId ? `binary_sensor.${objectId}_charging` : null);
    if (!chargingId) return false;
    return this.stateOf(chargingId) === "on";
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
