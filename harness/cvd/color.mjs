/**
 * Color math for the CVD gate: sRGB↔linear, CIE Lab, CIEDE2000, and
 * alpha compositing. Pure functions, no deps.
 *
 * sRGB gamma matches the libDaltonLens reference exactly.
 */

/** sRGB channel (0–255) → linear (0–1). */
export function srgbToLinear(v) {
  const f = v / 255;
  return f <= 0.04045 ? f / 12.92 : ((f + 0.055) / 1.055) ** 2.4;
}

/** Linear channel (0–1) → sRGB (0–255, clamped + rounded). */
export function linearToSrgb(v) {
  const c = v <= 0.0031308 ? v * 12.92 : 1.055 * v ** (1 / 2.4) - 0.055;
  return Math.max(0, Math.min(255, Math.round(c * 255)));
}

/* sRGB (D65) → XYZ via linear RGB, then XYZ → CIE Lab (D65 white). */
const Xn = 0.95047, Yn = 1.0, Zn = 1.08883;

function labf(t) {
  return t > 0.008856 ? Math.cbrt(t) : (903.3 * t + 16) / 116;
}

/** [r,g,b] (0–255 sRGB) → CIE Lab [L,a,b]. */
export function rgbToLab([r, g, b]) {
  const R = srgbToLinear(r), G = srgbToLinear(g), B = srgbToLinear(b);
  const X = 0.4124564 * R + 0.3575761 * G + 0.1804375 * B;
  const Y = 0.2126729 * R + 0.7151522 * G + 0.0721750 * B;
  const Z = 0.0193339 * R + 0.1191920 * G + 0.9503041 * B;
  const fx = labf(X / Xn), fy = labf(Y / Yn), fz = labf(Z / Zn);
  return [116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz)];
}

const deg = (r) => (r * 180) / Math.PI;
const rad = (d) => (d * Math.PI) / 180;

/** CIEDE2000 color difference between two CIE Lab colors. */
export function ciede2000([L1, a1, b1], [L2, a2, b2]) {
  const C1 = Math.hypot(a1, b1), C2 = Math.hypot(a2, b2);
  const Cbar = (C1 + C2) / 2;
  const G = 0.5 * (1 - Math.sqrt(Cbar ** 7 / (Cbar ** 7 + 25 ** 7)));
  const a1p = (1 + G) * a1, a2p = (1 + G) * a2;
  const C1p = Math.hypot(a1p, b1), C2p = Math.hypot(a2p, b2);
  let h1p = deg(Math.atan2(b1, a1p)); if (h1p < 0) h1p += 360;
  let h2p = deg(Math.atan2(b2, a2p)); if (h2p < 0) h2p += 360;

  const dLp = L2 - L1;
  const dCp = C2p - C1p;
  let dhp = 0;
  if (C1p * C2p !== 0) {
    dhp = h2p - h1p;
    if (dhp > 180) dhp -= 360;
    else if (dhp < -180) dhp += 360;
  }
  const dHp = 2 * Math.sqrt(C1p * C2p) * Math.sin(rad(dhp) / 2);

  const Lbar = (L1 + L2) / 2;
  const Cbarp = (C1p + C2p) / 2;
  let hbar;
  if (C1p * C2p === 0) {
    hbar = h1p + h2p;
  } else if (Math.abs(h1p - h2p) > 180) {
    hbar = (h1p + h2p + 360) / 2;
  } else {
    hbar = (h1p + h2p) / 2;
  }
  const T =
    1 -
    0.17 * Math.cos(rad(hbar - 30)) +
    0.24 * Math.cos(rad(2 * hbar)) +
    0.32 * Math.cos(rad(3 * hbar + 6)) -
    0.20 * Math.cos(rad(4 * hbar - 63));
  const dtheta = 30 * Math.exp(-(((hbar - 275) / 25) ** 2));
  const Rc = 2 * Math.sqrt(Cbarp ** 7 / (Cbarp ** 7 + 25 ** 7));
  const Sl = 1 + (0.015 * (Lbar - 50) ** 2) / Math.sqrt(20 + (Lbar - 50) ** 2);
  const Sc = 1 + 0.045 * Cbarp;
  const Sh = 1 + 0.015 * Cbarp * T;
  const Rt = -Math.sin(rad(2 * dtheta)) * Rc;

  return Math.sqrt(
    (dLp / Sl) ** 2 +
    (dCp / Sc) ** 2 +
    (dHp / Sh) ** 2 +
    Rt * (dCp / Sc) * (dHp / Sh),
  );
}

/** Parse a CSS "rgb(...)"/"rgba(...)" string → [r,g,b,a] (a defaults 1). */
export function parseColor(s) {
  const n = String(s).match(/[\d.]+/g)?.map(Number) ?? [];
  return n.length >= 4 ? [n[0], n[1], n[2], n[3]] : [n[0] ?? 0, n[1] ?? 0, n[2] ?? 0, 1];
}

/** Composite [r,g,b,a] foreground over an opaque [r,g,b] background. */
export function composite([r, g, b, a = 1], bg) {
  return [
    Math.round(r * a + bg[0] * (1 - a)),
    Math.round(g * a + bg[1] * (1 - a)),
    Math.round(b * a + bg[2] * (1 - a)),
  ];
}
