/**
 * ============================================================
 * ANIMAL .js -> DESCRIPTOR JSON  (converter)
 * ============================================================
 *
 * Convert an existing hand-written animal-svg module (the old format — const
 * colour aliases + backtick `parts` with ${FUR} interpolation, like
 * animals/raccoon.js) into a gallery DESCRIPTOR JSON you can submit.
 *
 * It does NOT hand-translate the SVG. It RUNS the module with a stub
 * AnimalSVG.register that captures the def — so every ${FUR} interpolation is
 * already resolved to its literal `hsl(var(--animal-fur))` by the JS runtime —
 * then tidies whitespace, switches attribute quotes to single (so the JSON is
 * clean), and writes { id, name, type, colors, parts } in the descriptor shape.
 *
 * You add `license` (required) + any author/description after; then validate
 * with build-animal.mjs (which is also what the intake runs).
 *
 * Usage:
 *   node scripts/animal-js-to-descriptor.mjs <module.js> [--id <id>] [--license CC0-1.0] [-o out.json]
 *
 * Declarative animals only — a `type: "custom"` (procedural JS) module can't
 * become data, and is rejected.
 * ============================================================
 */
import { readFileSync, writeFileSync } from "node:fs";
import { pathToFileURL } from "node:url";

/**
 * Convert a module's source into a descriptor envelope.
 * @param {string} src  the module source (an IIFE that calls AnimalSVG.register).
 * @param {object} [opts] { id?, license? }
 * @returns {{ok:true, envelope:object} | {ok:false, error:string}}
 */
export function convertModule(src, opts = {}) {
  let captured = null;
  const AnimalSVG = { register: (rid, def) => { captured = { id: rid, def }; } };
  try {
    // The module references `AnimalSVG` as a free name; new Function makes it a
    // parameter we inject. Template-literal parts evaluate here, so the captured
    // def has its colour interpolations already resolved to literal strings.
    // eslint-disable-next-line no-new-func
    new Function("AnimalSVG", src)(AnimalSVG);
  } catch (e) {
    return { ok: false, error: `couldn't run the module: ${e.message}` };
  }
  if (!captured) return { ok: false, error: "the module didn't call AnimalSVG.register — is it an animal module?" };

  const { id: srcId, def } = captured;
  if (def.type === "custom") {
    return { ok: false, error: "this is a procedural (type:'custom') animal — it's JavaScript, not data, so it can't be converted" };
  }

  // Tidy: collapse template-literal whitespace to single spaces (SVG path data
  // tolerates single spaces), then switch attribute quotes to single so the JSON
  // needs no escaping. Safe because animal SVG never has a quote inside a value.
  const tidy = (s) => String(s).replace(/\s+/g, " ").trim().replace(/"/g, "'");
  const parts = {};
  for (const [slot, svg] of Object.entries(def.parts || {})) parts[slot] = tidy(svg);

  const id = opts.id || srcId;
  const animal = {
    id,
    name: def.label || id,
    type: def.type || "quadruped",
    license: opts.license || "CC-BY-4.0",
    ...(def.memorial ? { memorial: true } : {}),
    colors: def.colors || {},
    parts,
  };
  return { ok: true, envelope: { version: 1, kind: "animal", animal } };
}

// --- CLI ---------------------------------------------------------------------
if (process.argv[1] && pathToFileURL(process.argv[1]).href === import.meta.url) {
  const args = process.argv.slice(2);
  const flag = (name) => {
    const i = args.indexOf(name);
    return i >= 0 ? args[i + 1] : undefined;
  };
  const file = args.find((a) => !a.startsWith("-") && a.endsWith(".js"));
  if (!file) {
    console.error("usage: node scripts/animal-js-to-descriptor.mjs <module.js> [--id <id>] [--license CC0-1.0] [-o out.json]");
    process.exit(2);
  }
  const r = convertModule(readFileSync(file, "utf8"), { id: flag("--id"), license: flag("--license") });
  if (!r.ok) {
    console.error(r.error);
    process.exit(1);
  }
  const json = JSON.stringify(r.envelope, null, 2);
  const out = flag("-o") || flag("--out");
  if (out) {
    writeFileSync(out, json + "\n");
    console.error(`Wrote ${out}.`);
  } else {
    console.log(json);
  }
  console.error(
    `Converted "${r.envelope.animal.id}" (${r.envelope.animal.name}). Set a real licence + add author/description if you like, then validate:\n` +
      `  node scripts/build-animal.mjs ${out || "<file>.json"}`,
  );
}
