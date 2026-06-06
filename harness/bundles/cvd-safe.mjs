/**
 * CVD-safe semantic palette — validated to ΔE2000 ≥ 15 on all 10 pairs
 * among {success, warning, error, info, muted}, under Machado 2009
 * protanopia + deuteranopia (severity 1.0) and Brettel 1997 tritanopia.
 * Worst margins: protan 18.1, deutan 18.4, tritan 19.3 (see
 * `node harness/cvd/report.mjs cvd-safe`).
 *
 * Design (per JI#3): success & error sit at similar lightness but
 * OPPOSITE blue-yellow (teal vs warm-red) — the one axis protan/deutan
 * keep; warm-red not magenta (magenta's blue collided with info-blue
 * under protan); the five hues are luminance-spread so none desaturates
 * into neutral grey.
 *
 * Only five overrides are needed: the rest of the semantic palette
 * (conf-*, color-cleaning/returning/error, confidence-*,
 * learning-confidence-*) cascades from --evcc-sem-* via var() chains.
 * Colour is necessary-but-not-sufficient — warn/likely share warning by
 * design, so a redundant per-state SHAPE cue carries the rest.
 */
export default {
  "--evcc-sem-success": "#0c8f86", // dark cyan-teal
  "--evcc-sem-warning": "#e9a100", // amber
  "--evcc-sem-error":   "#d6403a", // warm red
  "--evcc-sem-info":    "#0f4c86", // deep blue (reference / baseline)
  "--evcc-text-muted":  "#bcc2c7", // light neutral grey
};
