/**
 * Compute and print the pairwise CIEDE2000 separation matrix for a
 * 5-group semantic palette under each CVD sim. Margins, not just
 * pass/fail — so we can see whether the worst pair clears the floor by
 * 1 or by 20.
 *
 *   node harness/cvd/report.mjs            # default palette
 *   node harness/cvd/report.mjs cvd-safe   # a bundle under harness/bundles
 *
 * The gate is the 10 pairs among {success, warning, error, info, muted}.
 * warn/likely deliberately share warning (orange) and are NOT a color
 * pair — their separation is the shape cue's job.
 */
import { pathToFileURL } from "node:url";
import { simulate, SIMS } from "./simulate.mjs";
import { rgbToLab, ciede2000 } from "./color.mjs";

export const FLOOR = 15; // ΔE2000; defensible at dot size given the area effect.

export const GROUP_KEYS = ["success", "warning", "error", "info", "muted"];

export function pairs(keys = GROUP_KEYS) {
  const out = [];
  for (let i = 0; i < keys.length; i++)
    for (let j = i + 1; j < keys.length; j++) out.push([keys[i], keys[j]]);
  return out;
}

/**
 * @param {Record<string,[number,number,number]>} groups - opaque rgb per group.
 * @returns {{ matrix: object, worst: object, pass: boolean }}
 */
export function separationMatrix(groups) {
  const matrix = {}; // sim -> { "a-b": deltaE }
  const worst = {};
  let pass = true;
  for (const sim of SIMS) {
    const simmed = Object.fromEntries(
      GROUP_KEYS.map((k) => [k, rgbToLab(simulate(sim, groups[k]))]),
    );
    matrix[sim] = {};
    let w = { pair: null, dE: Infinity };
    for (const [a, b] of pairs()) {
      const dE = ciede2000(simmed[a], simmed[b]);
      matrix[sim][`${a}-${b}`] = dE;
      if (dE < w.dE) w = { pair: `${a}-${b}`, dE };
    }
    worst[sim] = w;
    if (w.dE < FLOOR) pass = false;
  }
  return { matrix, worst, pass };
}

export function printReport(label, groups) {
  const { matrix, worst, pass } = separationMatrix(groups);
  console.log(`\nPALETTE: ${label}    (floor ΔE2000 ≥ ${FLOOR})`);
  const ps = pairs().map(([a, b]) => `${a}-${b}`);
  const head = "pair".padEnd(18) + SIMS.map((s) => s.padStart(9)).join("");
  console.log(head);
  console.log("-".repeat(head.length));
  for (const p of ps) {
    const row = p.padEnd(18) +
      SIMS.map((s) => {
        const v = matrix[s][p];
        const cell = v.toFixed(1) + (v < FLOOR ? "*" : " ");
        return cell.padStart(9);
      }).join("");
    console.log(row);
  }
  console.log("-".repeat(head.length));
  console.log(
    "worst".padEnd(18) +
    SIMS.map((s) => `${worst[s].dE.toFixed(1)}`.padStart(9)).join(""),
  );
  for (const s of SIMS) console.log(`  ${s}: worst pair ${worst[s].pair} = ΔE ${worst[s].dE.toFixed(1)}`);
  console.log(`RESULT: ${pass ? "PASS — all 30 ≥ " + FLOOR : "FAIL (* marks pairs below floor)"}`);
  return pass;
}

// Default semantic palette (opaque; muted = text-muted composited over the
// panel surface). These mirror the foundation.js defaults.
const DEFAULT_GROUPS = {
  success: [76, 175, 110],  // #4caf6e
  warning: [245, 166, 35],  // #f5a623
  error:   [224, 82, 82],   // #e05252
  info:    [74, 159, 224],  // #4a9fe0
  muted:   [147, 150, 154], // rgba(240,242,245,0.48) over ~rgb(62,66,71)
};

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  const arg = process.argv[2];
  if (arg) {
    // Load a bundle (harness/bundles/<arg>.mjs) and map its semantic tokens
    // to the 5 groups (opaque hex; muted may be hex here).
    const mod = await import(new URL(`../bundles/${arg}.mjs`, import.meta.url).href);
    const b = mod.default ?? {};
    const hx = (h) => [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16));
    printReport(arg, {
      success: hx(b["--evcc-sem-success"]),
      warning: hx(b["--evcc-sem-warning"]),
      error: hx(b["--evcc-sem-error"]),
      info: hx(b["--evcc-sem-info"]),
      muted: hx(b["--evcc-text-muted"]),
    });
  } else {
    printReport("default", DEFAULT_GROUPS);
  }
}
