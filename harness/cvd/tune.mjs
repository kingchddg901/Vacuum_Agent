/**
 * Scratchpad: try candidate CVD-safe palettes against the separation
 * matrix. The winner becomes harness/bundles/cvd-safe.mjs.
 *   node harness/cvd/tune.mjs            # print all candidates
 *   node harness/cvd/tune.mjs v2         # one candidate
 *
 * Steer (per JI#3): fix the palette, not the floor. success→teal,
 * warning→amber-yellow, error→magenta-red; separate success/info by
 * LUMINANCE (tritan confuses blue-green by hue, so lean on lightness).
 */
import { printReport } from "./report.mjs";

const hex = (h) => [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16));
const pal = (success, warning, error, info, muted) => ({
  success: hex(success), warning: hex(warning), error: hex(error), info: hex(info), muted: hex(muted),
});

const CANDIDATES = {
  // v7 lineage. Only success-muted failed → push success to a saturated,
  // slightly darker cyan-teal (clear of neutral grey on both L and b).
  v9:  pal("#0a8a90", "#e9a100", "#d6403a", "#0f4c86", "#9aa0a6"),
  v10: pal("#0b8088", "#e9a100", "#d6403a", "#114e86", "#9aa0a6"),
  // also lighten muted a touch (more L-gap below it) while keeping it legible.
  v11: pal("#0c8f86", "#e9a100", "#d6403a", "#0f4c86", "#aeb4ba"),
  // FINAL: v11 with muted lifted further — closes protan success-muted; the
  // muted pairs all had headroom, success-info untouched.
  v12: pal("#0c8f86", "#e9a100", "#d6403a", "#0f4c86", "#bcc2c7"),
};

const which = process.argv[2];
for (const [name, groups] of Object.entries(CANDIDATES)) {
  if (which && name !== which) continue;
  printReport(name, groups);
}
