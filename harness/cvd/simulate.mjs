/**
 * Dichromat CVD simulation, applied to LINEAR RGB (per DaltonLens).
 *
 *  - protan / deutan : Machado et al. 2009 matrices at severity 1.0
 *    (perceptually validated, per-type). Full dichromat severity — a
 *    pass here covers milder anomalous trichromats.
 *  - tritan          : Brettel 1997 — two half-plane projection matrices
 *    chosen by the sign of dot(linRGB, separationNormal). Viénot/Machado
 *    are known to be inaccurate for tritan; Brettel is the valid choice.
 *
 * Constants verified against libDaltonLens and Machado's UFRGS page.
 * Sources:
 *   https://daltonlens.org/understanding-cvd-simulation/
 *   https://github.com/DaltonLens/libDaltonLens (libDaltonLens.c)
 *   https://www.inf.ufrgs.br/~oliveira/pubs_files/CVD_Simulation/CVD_Simulation.html
 */
import { srgbToLinear, linearToSrgb } from "./color.mjs";

const MACHADO = {
  protan: [
    [0.152286, 1.052583, -0.204868],
    [0.114503, 0.786281, 0.099216],
    [-0.003882, -0.048116, 1.051998],
  ],
  deutan: [
    [0.367322, 0.860646, -0.227968],
    [0.280085, 0.672501, 0.047413],
    [-0.011820, 0.042940, 0.968881],
  ],
};

const BRETTEL_TRITAN = {
  m1: [
    [1.01277, 0.13548, -0.14826],
    [-0.01243, 0.86812, 0.14431],
    [0.07589, 0.80500, 0.11911],
  ],
  m2: [
    [0.93678, 0.18979, -0.12657],
    [0.06154, 0.81526, 0.12320],
    [-0.37562, 1.12767, 0.24796],
  ],
  normal: [0.03901, -0.02788, -0.01113],
};

const applyMatrix = (m, v) => [
  m[0][0] * v[0] + m[0][1] * v[1] + m[0][2] * v[2],
  m[1][0] * v[0] + m[1][1] * v[1] + m[1][2] * v[2],
  m[2][0] * v[0] + m[2][1] * v[1] + m[2][2] * v[2],
];

/** Simulate a CVD type ("protan"|"deutan"|"tritan") on an [r,g,b] (0–255). */
export function simulate(type, [r, g, b]) {
  const lin = [srgbToLinear(r), srgbToLinear(g), srgbToLinear(b)];
  let out;
  if (type === "tritan") {
    const n = BRETTEL_TRITAN.normal;
    const dot = lin[0] * n[0] + lin[1] * n[1] + lin[2] * n[2];
    out = applyMatrix(dot >= 0 ? BRETTEL_TRITAN.m1 : BRETTEL_TRITAN.m2, lin);
  } else {
    out = applyMatrix(MACHADO[type], lin);
  }
  return out.map(linearToSrgb);
}

export const SIMS = ["protan", "deutan", "tritan"];
