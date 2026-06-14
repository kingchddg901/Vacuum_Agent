/**
 * ============================================================
 * THEME TAGS — colour-vision verification (the `colorblind-safe` gate)
 * ============================================================
 *
 * `colorblind-safe` is a VERIFIED tag, never just asserted: an author may request
 * it, but verifyColorblindSafe() runs a real check and the tag is stripped (with a
 * reason) if the theme fails. The claim has to be trustworthy.
 *
 * Method (standard, deterministic):
 *   1. take the four status semantics (success / warning / error / info),
 *   2. simulate each under deuteranopia, protanopia and tritanopia using the
 *      Machado (2009) dichromacy matrices in LINEAR-RGB,
 *   3. convert to CIELab and measure pairwise ΔE (CIE76),
 *   4. fail if ANY pair collapses below the ΔE floor under ANY of the three —
 *      i.e. two status colours a CVD viewer couldn't tell apart.
 *
 * Returns { pass, reasons[] } where each reason names the pair, the CVD type, and
 * the ΔE, so the submission UI / card can say exactly WHY it failed.
 * ============================================================
 */
import { parseColor } from "./derive.mjs";

const SEM_DEFAULTS = {
  success: "#4caf6e", warning: "#f5a623", error: "#e05252", info: "#5a90d6",
};

// Minimum CIELab ΔE between any two semantics, after the worst-case CVD simulation,
// for the set to count as distinguishable. ~19 ≈ "clearly different at a glance".
export const CVD_DELTA_E = 19;

// Layman buckets people recognise: red-green (deuteranopia + protanopia — ~8% of
// men) vs blue-yellow (tritanopia — rare). The filter/tag use the bucket; the
// breakdown keeps the precise medical term. A red-green viewer can't perceive
// which subtype they are, so the bucket margin is the conservative min of the two.
const CVD_BUCKET = {
  deuteranopia: "red-green",
  protanopia: "red-green",
  tritanopia: "blue-yellow",
};

/* ---- Machado (2009) dichromacy matrices, severity 1.0, for LINEAR RGB ---- */
const MACHADO = {
  deuteranopia: [[0.367322, 0.860646, -0.227968], [0.280085, 0.672501, 0.047413], [-0.011820, 0.042940, 0.968881]],
  protanopia:   [[0.152286, 1.052583, -0.204868], [0.114503, 0.786281, 0.099216], [-0.003882, -0.048116, 1.051998]],
  tritanopia:   [[1.255528, -0.076749, -0.178779], [-0.078411, 0.930809, 0.147602], [0.004733, 0.691367, 0.303900]],
};

const _toLin = (c) => { c /= 255; return c <= 0.04045 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4); };
const _clamp01 = (x) => (x < 0 ? 0 : x > 1 ? 1 : x);

function simulateLinear({ r, g, b }, kind) {
  const lr = _toLin(r), lg = _toLin(g), lb = _toLin(b);
  const M = MACHADO[kind];
  return {
    r: _clamp01(M[0][0] * lr + M[0][1] * lg + M[0][2] * lb),
    g: _clamp01(M[1][0] * lr + M[1][1] * lg + M[1][2] * lb),
    b: _clamp01(M[2][0] * lr + M[2][1] * lg + M[2][2] * lb),
  };
}

function linearRgbToLab({ r, g, b }) {
  // linear sRGB -> XYZ (D65)
  const X = 0.4124 * r + 0.3576 * g + 0.1805 * b;
  const Y = 0.2126 * r + 0.7152 * g + 0.0722 * b;
  const Z = 0.0193 * r + 0.1192 * g + 0.9505 * b;
  // XYZ -> Lab (D65 white)
  const f = (t) => (t > 0.008856 ? Math.cbrt(t) : 7.787 * t + 16 / 116);
  const fx = f(X / 0.95047), fy = f(Y / 1.0), fz = f(Z / 1.08883);
  return { L: 116 * fy - 16, a: 500 * (fx - fy), b: 200 * (fy - fz) };
}
const deltaE76 = (p, q) => Math.hypot(p.L - q.L, p.a - q.a, p.b - q.b);

/**
 * Verify a theme's four status semantics survive colour-vision deficiency.
 * @param {object} tokens  resolved `--evcc-*` map (reads the four --evcc-sem-* colours).
 * @param {object} [opts]  { threshold } override for CVD_DELTA_E.
 * @returns {{
 *   pass: boolean,
 *   minDeltaE: number,                                    // the global tightest separation
 *   weakest: { cvd:string, bucket:string, pair:[string,string], deltaE:number },  // bottleneck
 *   buckets: { [bucket:string]: { min:number, pair:[string,string], cvd:string } },  // red-green / blue-yellow
 *   bestBucket: string,                                   // the layman bucket it handles best
 *   perCvd:  { [cvd:string]: { min:number, pair:[string,string] } },
 *   reasons: Array<{ pair:[string,string], cvd:string, deltaE:number }>,  // only failing pairs
 * }}
 */
export function verifyColorblindSafe(tokens, opts = {}) {
  const threshold = opts.threshold ?? CVD_DELTA_E;
  const names = ["success", "warning", "error", "info"];
  const rgb = {};
  for (const n of names) rgb[n] = parseColor(tokens?.[`--evcc-sem-${n}`]) || parseColor(SEM_DEFAULTS[n]);

  const reasons = [];
  const perCvd = {}; // cvd -> { min, pair } : the closest pair under that simulation
  for (const cvd of Object.keys(MACHADO)) {
    const lab = {};
    for (const n of names) lab[n] = linearRgbToLab(simulateLinear(rgb[n], cvd));
    let cvdMin = Infinity;
    let cvdPair = null;
    for (let i = 0; i < names.length; i++) {
      for (let j = i + 1; j < names.length; j++) {
        const de = deltaE76(lab[names[i]], lab[names[j]]);
        if (de < cvdMin) { cvdMin = de; cvdPair = [names[i], names[j]]; }
        if (de < threshold) reasons.push({ pair: [names[i], names[j]], cvd, deltaE: +de.toFixed(1) });
      }
    }
    perCvd[cvd] = { min: +cvdMin.toFixed(1), pair: cvdPair };
  }

  // Weakest = the tightest pair anywhere (the bottleneck == the global min).
  let weakest = null;
  for (const cvd of Object.keys(perCvd)) {
    const entry = { cvd, bucket: CVD_BUCKET[cvd], pair: perCvd[cvd].pair, deltaE: perCvd[cvd].min };
    if (!weakest || entry.deltaE < weakest.deltaE) weakest = entry;
  }

  // Collapse to layman buckets: each bucket's margin is the MIN over its sims (the
  // conservative figure), and bestBucket is the bucket the theme handles best.
  const buckets = {};
  for (const cvd of Object.keys(perCvd)) {
    const bucket = CVD_BUCKET[cvd];
    if (!buckets[bucket] || perCvd[cvd].min < buckets[bucket].min) {
      buckets[bucket] = { min: perCvd[cvd].min, pair: perCvd[cvd].pair, cvd };
    }
  }
  let bestBucket = null;
  for (const b of Object.keys(buckets)) {
    if (bestBucket === null || buckets[b].min > buckets[bestBucket].min) bestBucket = b;
  }

  return {
    pass: reasons.length === 0,
    minDeltaE: weakest ? weakest.deltaE : Infinity,
    weakest,
    buckets,
    bestBucket,
    perCvd,
    reasons,
  };
}
