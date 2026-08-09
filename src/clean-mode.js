// The card-side canonical clean_mode fold. ONE owner, deliberately dependency-free
// so every consumer can reach it — the panel state, the standalone cards, and the
// pure steps-manifest builder, which is import-free by design apart from this.
//
// ISSUE #48. The room editor persists a DISPLAY LABEL ("Vacuum and mop") while the
// adapter's option values, the profile catalog and the framework all use the TOKEN
// "vacuum_mop". Every place that compared the two invented its own fold, and the
// ones that used a plain lowercase compare silently failed on exactly one value —
// the combined mode. "Vacuum" and "Mop" survive lowercasing, which is why a defect
// that made mode chips render unselected and mode hints disappear went unnoticed.
//
// This mirrors the BACKEND owner, `canonical_clean_mode` in
// profiles/room_profiles.py, alias for alias. The two are separate languages and
// cannot share code, so they are pinned to each other by test instead: if you add
// an alias to one, add it to the other.

/**
 * Display spellings the card and older records use for the combined mode.
 * Keys are lowercased; look-ups fold case first.
 */
export const CLEAN_MODE_DISPLAY_ALIASES = {
  "vacuum and mop": "vacuum_mop",
  "vacuum & mop":   "vacuum_mop",
  "vacuum+mop":     "vacuum_mop",
  "vac & mop":      "vacuum_mop",
  "vacmop":         "vacuum_mop",
};

/**
 * Fold a clean_mode to its canonical token: `vacuum` | `mop` | `vacuum_mop`.
 * Unknown values pass through lowercased, so a brand-specific mode survives
 * rather than being coerced into somebody else's vocabulary.
 */
export function canonicalCleanMode(value) {
  const text = String(value ?? "").trim().toLowerCase();
  if (!text) return text;
  if (CLEAN_MODE_DISPLAY_ALIASES[text]) return CLEAN_MODE_DISPLAY_ALIASES[text];
  // Any phrasing carrying both verbs is a combined vacuum+mop run.
  if (text.includes("vacuum") && text.includes("mop")) return "vacuum_mop";
  return text;
}

/** True when this clean_mode wets the floor. THE question, asked once. */
export function isMopCleanMode(value) {
  const canonical = canonicalCleanMode(value);
  return canonical === "mop" || canonical === "vacuum_mop";
}
