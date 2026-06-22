/**
 * ============================================================
 * FULL SVG -> DESCRIPTOR  ("hand over a drawing, get the safe descriptor")
 * ============================================================
 *
 * Lets an author draw the whole animal as ONE SVG and get back a safe,
 * submittable descriptor — instead of hand-writing JSON-with-embedded-SVG.
 *
 * The author marks each anatomical part with `data-slot` and (per the authoring
 * guide) places the leg-animation classes + transform-origins themselves and
 * uses `hsl(var(--animal-X))` for any colour they want themeable. This tool then:
 *   1. parses the SVG in a REAL browser (robust nesting) and splits it by
 *      data-slot — the wrapper is dropped, each group's innerHTML becomes a slot;
 *   2. SANITISES every slot with DOMPurify (the "safe version" handed back —
 *      same allowlist as the intake);
 *   3. scaffolds a `colors` block from the `var(--animal-*)` tokens it finds
 *      (defaults are placeholders unless you pass real ones) and assembles the
 *      descriptor with your metadata.
 *
 * It can't infer anatomy from an untagged blob — no data-slot groups ⟹ refusal
 * with guidance. Colours can't be inferred from a token ref (the SVG carries the
 * name, not the default), so fill the scaffolded defaults (or pass `colors`)
 * before validating with build-animal.mjs.
 *
 * Usage:
 *   node scripts/svg-to-descriptor.mjs <drawing.svg> --id <id> --name "<name>" \
 *        [--type quadruped|parrot] [--license CC0-1.0] [--meta meta.json] [-o out.json]
 * ============================================================
 */
import { readFileSync, writeFileSync } from "node:fs";
import { pathToFileURL } from "node:url";
import { sanitizePartsWithPage } from "./sanitize-animal-svg.mjs";
import { REQUIRED_PARTS, OPTIONAL_PARTS } from "./animal-descriptor.mjs";

const TOKEN_RE = /var\(\s*(--animal-[a-z0-9-]+)/gi;

/**
 * @param {string} svg   the full SVG source (with data-slot markers).
 * @param {object} [meta] id, name, type, license, colors?, author?, ...
 * @returns {Promise<{ok:true, envelope, removed, missing, scaffoldedColors}|{ok:false, error}>}
 */
export async function svgToDescriptor(svg, meta = {}) {
  const type = meta.type || "quadruped";
  const allowedSlots = new Set([
    ...(REQUIRED_PARTS[type] || REQUIRED_PARTS.quadruped),
    ...OPTIONAL_PARTS,
    ...(type === "parrot" ? ["wingLeft", "wingRight"] : []),
  ]);

  const { chromium } = await import("playwright");
  const browser = await chromium.launch();
  try {
    const page = await browser.newPage();
    await page.setContent("<!doctype html><body></body>");

    // Parse in the real DOM + split by data-slot (handles arbitrary nesting).
    const raw = await page.evaluate((s) => {
      const wrap = document.createElement("div");
      wrap.innerHTML = s;
      const out = [];
      wrap.querySelectorAll("[data-slot]").forEach((el) => out.push([el.getAttribute("data-slot"), el.innerHTML]));
      return out;
    }, String(svg || ""));

    if (!raw.length) {
      return {
        ok: false,
        error: 'No <g data-slot="..."> groups found. Tag each anatomical part with data-slot (body, head, frontLeftLeg, …) — see the authoring guide.',
      };
    }

    const rawParts = {};
    const unknown = [];
    for (const [slot, html] of raw) {
      if (!slot) continue;
      if (!allowedSlots.has(slot)) {
        if (!unknown.includes(slot)) unknown.push(slot);
        continue;
      }
      if (!(slot in rawParts)) rawParts[slot] = html; // first wins
    }
    if (unknown.length) {
      return { ok: false, error: `Unknown data-slot value(s) for a ${type}: ${unknown.join(", ")}. Allowed: ${[...allowedSlots].join(", ")}.` };
    }

    // Sanitise every slot — this is the safe version handed back.
    const { parts, removed } = await sanitizePartsWithPage(page, rawParts);

    // Colours: use what's given, else scaffold the keys the SVG references.
    let colors = meta.colors;
    let scaffoldedColors = false;
    if (!colors || typeof colors !== "object" || Array.isArray(colors)) {
      const found = new Set(["--animal-eye"]);
      for (const v of Object.values(parts)) {
        let m;
        const re = new RegExp(TOKEN_RE);
        while ((m = re.exec(v))) found.add(m[1]);
      }
      colors = {};
      for (const k of found) colors[k] = k === "--animal-eye" ? "142 71% 45%" : "0 0% 50%";
      scaffoldedColors = true;
    }

    const animal = {
      id: meta.id || "my-animal",
      name: meta.name || meta.id || "My Animal",
      type,
      license: meta.license || "CC-BY-4.0",
      ...(meta.memorial ? { memorial: true } : {}),
      colors,
      parts,
    };
    for (const k of ["author", "author_url", "submitted_by", "description", "tags"]) {
      if (meta[k] != null) animal[k] = meta[k];
    }

    const required = REQUIRED_PARTS[type] || REQUIRED_PARTS.quadruped;
    const missing = required.filter((s) => !(s in parts));
    return { ok: true, envelope: { version: 1, kind: "animal", animal }, removed, missing, scaffoldedColors };
  } finally {
    await browser.close();
  }
}

// --- CLI ---------------------------------------------------------------------
if (process.argv[1] && pathToFileURL(process.argv[1]).href === import.meta.url) {
  const args = process.argv.slice(2);
  const flag = (n) => {
    const i = args.indexOf(n);
    return i >= 0 ? args[i + 1] : undefined;
  };
  const file = args.find((a) => !a.startsWith("-") && a.endsWith(".svg"));
  if (!file) {
    console.error('usage: node scripts/svg-to-descriptor.mjs <drawing.svg> --id <id> --name "<name>" [--type quadruped|parrot] [--license CC0-1.0] [--meta meta.json] [-o out.json]');
    process.exit(2);
  }
  const meta = flag("--meta") ? JSON.parse(readFileSync(flag("--meta"), "utf8")) : {};
  for (const [k, f] of [["id", "--id"], ["name", "--name"], ["type", "--type"], ["license", "--license"]]) {
    if (flag(f) != null) meta[k] = flag(f);
  }
  const r = await svgToDescriptor(readFileSync(file, "utf8"), meta);
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
  if (r.missing.length) console.error(`⚠ Missing required slots for a ${r.envelope.animal.type}: ${r.missing.join(", ")}.`);
  if (r.scaffoldedColors) console.error("⚠ Colours were scaffolded with placeholder defaults — replace them with your real HSL values before submitting.");
  if (Object.keys(r.removed).length) console.error("The sanitiser cleaned some markup (safe version returned). Slots touched: " + Object.keys(r.removed).join(", "));
}
