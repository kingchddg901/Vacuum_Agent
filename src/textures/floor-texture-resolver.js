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
