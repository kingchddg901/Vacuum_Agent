/**
 * ============================================================
 * TEXTURES: FLOOR TEXTURE RESOLVER
 * ============================================================
 *
 * PURPOSE
 * -------
 * Maps raw floor_type / carpet_type fields from room data to
 * the canonical keys used by FLOOR_TEXTURE_REGISTRY.
 *
 * ARCHITECTURAL ROLE
 * ------------------
 * Single normalisation point. Accepts:
 *   • Spec format: { floor_type: "carpet", carpet_type: "low_pile" }
 *   • Legacy combined: carpet_low_pile, carpet_high_pile, carpet_low,
 *     carpet_high
 *   • Direct registry keys: tile, wood, marble, concrete, granite_light
 *   • Aliases: hardwood, laminate → wood; granite → granite_light
 * Falls back to "default" for anything unrecognised.
 *
 * ============================================================
 */

/**
 * Resolves a room's floor type to a canonical FLOOR_TEXTURE_REGISTRY key.
 * Handles the current spec format, legacy combined values, direct registry keys,
 * and common aliases. Falls back to "default" for unrecognised values.
 *
 * @param {{ floor_type?: string, carpet_type?: string }} room - Raw room data object.
 * @returns {string} Canonical floor type key (e.g. "tile", "wood", "carpet_low").
 */
export function resolveFloorType(room) {
  const raw     = String(room?.floor_type  ?? "").toLowerCase().trim();
  const carpetRaw = String(room?.carpet_type ?? "").toLowerCase().trim();

  // Spec format: {floor_type:"carpet", carpet_type:"low_pile"|"high_pile"}
  if (raw === "carpet") {
    if (carpetRaw === "high_pile" || carpetRaw === "high") return "carpet_high";
    return "carpet_low";
  }

  // Legacy combined forms
  if (raw === "carpet_low_pile"  || raw === "carpet_low")  return "carpet_low";
  if (raw === "carpet_high_pile" || raw === "carpet_high") return "carpet_high";

  if (raw === "hardwood" || raw === "laminate" || raw === "wood") return "wood";
  if (raw === "tile")                                       return "tile";
  if (raw === "marble")                                     return "marble";
  if (raw === "concrete")                                   return "concrete";
  if (raw === "granite" || raw === "granite_light")         return "granite_light";

  return "default";
}

/**
 * Normalise a map-texture rotation (degrees) to a stable value: coerce non-finite to 0,
 * quantise to 0.1° so tiny getComputedStyle noise can't churn the render cache, and wrap
 * into [-180, 180). 0 = as-authored. Folded into the mask pattern matrix at decode time.
 *
 * @param {number} deg - Raw rotation in degrees (may be NaN / out of range).
 * @returns {number} Quantised, wrapped degrees in [-180, 180).
 */
export function normalizeFloorRotationDeg(deg) {
  let d = Number.isFinite(deg) ? deg : 0;
  d = ((d % 360) + 540) % 360 - 180;   // wrap to [-180, 180)
  d = Math.round(d * 10) / 10;         // quantise to 0.1° AFTER the wrap so no FP tail lingers
  return d >= 180 ? d - 360 : d;       // rounding can nudge 179.96 -> 180; keep it in range
}
