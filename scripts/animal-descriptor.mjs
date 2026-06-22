/**
 * ============================================================
 * ANIMAL DESCRIPTOR CORE  (community animal intake)
 * ============================================================
 *
 * Pure, dependency-free, unit-testable. Shared by BOTH intake paths:
 *   - the issue-form processor  (scripts/process-animal-submission.mjs)
 *   - the fork-PR check          (.github/workflows/animal-submission.yml)
 *
 * WHY THIS EXISTS — the security model:
 *   A theme is DATA (colour tokens). An animal, as the framework loads it
 *   (animal-svg.js → AnimalSVG.register, parts injected via innerHTML in
 *   `_render`), is EXECUTABLE JS with raw SVG markup. We never accept JS.
 *   A community animal is a declarative descriptor; the executable
 *   animals/<id>.js is GENERATED here, by us, from validated + sanitised
 *   data. The submitter authors data; we author the code.
 *
 * Three load-bearing controls:
 *   1. validateDescriptor() — the CONTRACT GATE. Declarative-only: rejects
 *      type:'custom', any render/function field, raw JS. Enforces type,
 *      required parts, id/name/licence shape, the baked⟹memorial rule, and
 *      strict HSL colour values (a stray ';'/'}' would break out of the
 *      framework's <style> block, so the HSL regex is also CSS-injection
 *      defence).
 *   2. quickRejectSvg() — a fail-CLOSED denylist pre-scan on each parts.*
 *      string. This is the BELT. The authoritative ALLOWLIST sanitiser is
 *      DOMPurify in a real browser (scripts/sanitize-animal-svg.mjs), run at
 *      intake — the SUSPENDERS. Defence in depth; never rely on one alone.
 *   3. codegenAnimalModule() — embeds the validated def via JSON.stringify
 *      with <,>,U+2028,U+2029 escaped, so no SVG/string content can break
 *      out of the generated source into executable code.
 *
 * Provenance: every accepted animal is stamped source:"community" here, never
 * trusted from input. `memorial` is honoured from input (it gates the Rainbow
 * Bridge group AND is required for baked animals) but a maintainer still merges
 * the PR — the human gate against tribute-section abuse.
 * ============================================================
 */

import { isAcceptableAuthorUrl } from "./process-submission.mjs";

// --- Contract constants ------------------------------------------------------

/** Declarative body plans only. 'custom' (the render(svg,pose) JS path) is
 *  reserved for maintainer commits and is hard-rejected here. */
export const ANIMAL_TYPES = new Set(["quadruped", "parrot"]);

/** Required anatomical slots per body plan (parrot has no hind legs). */
export const REQUIRED_PARTS = {
  quadruped: ["body", "frontLeftLeg", "frontRightLeg", "backLeftLeg", "backRightLeg", "tail", "head", "eyes", "face"],
  parrot: ["body", "frontLeftLeg", "frontRightLeg", "tail", "head", "eyes", "face"],
};
export const OPTIONAL_PARTS = ["warning", "extra"];

/** Def keys a community submission may NEVER carry: the JS-callback path and
 *  the maintainer-only parrot wing fields. */
const FORBIDDEN_DEF_KEYS = new Set(["render", "wingLeft", "wingRight"]);

/** Bundled animals — an intake must never overwrite these (register() silently
 *  replaces on duplicate name). */
export const RESERVED_IDS = new Set(["cat", "dog", "raccoon", "parrot", "snake", "mittens"]);

const ID_RE = /^[a-z][a-z0-9-]{1,30}$/;
const NAME_MAX = 60;
const META_MAX = 200;
const DESC_MAX = 280;
const TAG_MAX = 32;
const MAX_TAGS = 12;
const MAX_PART_BYTES = 32 * 1024;
const MAX_TOTAL_BYTES = 256 * 1024;
const MAX_NESTING = 32;

/** SPDX licence allowlist — an SVG drawing is copyrightable art, so a clear
 *  licence is required (themes don't need one; a token map isn't). */
export const LICENSES = new Set(["CC0-1.0", "CC-BY-4.0", "MIT", "Apache-2.0"]);

/** A bare HSL triple: "H S% L%" (e.g. "142 71% 45%"). Format-strict on
 *  purpose — the value is interpolated into a CSS custom property, so a stray
 *  ';' or '}' would escape the <style> block. No such char can match here. */
const HSL_RE = /^\d{1,3}(?:\.\d+)?\s+\d{1,3}(?:\.\d+)?%\s+\d{1,3}(?:\.\d+)?%$/;

const COLOR_KEY_RE = /^--animal-[a-z0-9-]+$/;

/** The eye must stay themeable so the battery-state recolour works. */
const EYE_KEY = "--animal-eye";

/**
 * The single source of truth for what sanitised SVG may contain. The browser
 * sanitiser (scripts/sanitize-animal-svg.mjs) imports this to configure
 * DOMPurify; the quick-reject below enforces the obvious negatives. Geometry +
 * presentation only — no scripting, no external refs, no embedded HTML.
 */
export const SVG_ALLOWLIST = {
  tags: [
    "g", "path", "circle", "ellipse", "rect", "line", "polyline", "polygon",
    "defs", "linearGradient", "radialGradient", "stop", "clipPath", "use",
    "title", "desc",
  ],
  attrs: [
    "d", "cx", "cy", "r", "rx", "ry", "x", "y", "x1", "y1", "x2", "y2",
    "width", "height", "points", "transform", "transform-origin",
    "fill", "fill-opacity", "fill-rule", "stroke", "stroke-width",
    "stroke-linecap", "stroke-linejoin", "stroke-dasharray", "stroke-opacity",
    "opacity", "class", "style", "offset", "stop-color", "stop-opacity",
    "gradientUnits", "gradientTransform", "clip-path", "href", "id",
  ],
  // `style` is allowed but only these CSS properties survive (the framework's
  // own pose machinery sets transform/transition; submitters mostly need
  // transform-origin for the leg pivots).
  styleProps: [
    "transform", "transform-origin", "transition", "opacity", "fill",
    "stroke", "stroke-width",
  ],
  // Lower-leg knee classes the framework animates are hardcoded to cat-/dog-/
  // rac- prefixes, so a community quadruped reuses one of those (the Mittens
  // pattern). `animal-eyes` opts the eye into the charging pulse. Any other
  // class is dropped by the sanitiser (harmless — shadow DOM encapsulates it —
  // but kept tidy + predictable).
  classAllow: new Set([
    "animal-eyes",
    "f-wing-l", // parrot wing-flap (flight pose) — authored in the wing parts
    "f-wing-r",
    ...["cat", "dog", "rac"].flatMap((p) => ["fl", "fr", "bl", "br"].map((leg) => `${p}-${leg}-lower`)),
  ]),
};

// --- SVG fail-closed pre-scan (the BELT) -------------------------------------

/**
 * Return a human reason if `svg` contains an obviously dangerous construct,
 * else null. This REJECTS (fail-closed) rather than strips — clearer feedback
 * and no silent mutation. The authoritative allowlist sanitiser runs after.
 */
export function quickRejectSvg(svg) {
  const s = String(svg || "");
  const checks = [
    [/<\s*script/i, "contains a <script> element"],
    [/<\s*foreignObject/i, "contains a <foreignObject> (can embed arbitrary HTML)"],
    [/<\s*image\b/i, "contains an <image> element (can load external resources)"],
    [/<\s*iframe/i, "contains an <iframe>"],
    [/<\s*(annotation|set|animate)/i, "contains a scripting/animation element that isn't allowed"],
    [/\son[a-z]+\s*=/i, "contains an inline event handler (on… attribute)"],
    [/javascript\s*:/i, "contains a javascript: URI"],
    [/data\s*:/i, "contains a data: URI"],
    [/vbscript\s*:/i, "contains a vbscript: URI"],
    // href / xlink:href must be an internal #fragment (e.g. a gradient/clip),
    // never an external/absolute reference.
    [/(?:xlink:)?href\s*=\s*(["'])\s*(?!#)/i, "has an href that isn't an internal #fragment reference"],
    // url(...) must point at an internal #fragment (fill="url(#grad)"), not http/data/etc.
    [/url\s*\(\s*(?!["']?#)/i, "has a url(...) that isn't an internal #fragment reference"],
    [/@import/i, "contains an @import"],
    [/expression\s*\(/i, "contains a CSS expression()"],
    [/<!\s*(DOCTYPE|ENTITY)/i, "contains a DOCTYPE/ENTITY declaration"],
    [/<!\[CDATA\[/i, "contains a CDATA section"],
  ];
  for (const [re, reason] of checks) {
    if (re.test(s)) return reason;
  }
  if (svgNestingDepth(s) > MAX_NESTING) return `is nested deeper than ${MAX_NESTING} elements`;
  return null;
}

/** Rough max element-nesting depth (open tags minus closes), ignoring
 *  self-closing tags. A cheap guard against deeply-nested element bombs. */
export function svgNestingDepth(svg) {
  let depth = 0;
  let max = 0;
  const tagRe = /<\s*(\/?)\s*([a-z][a-z0-9]*)([^>]*?)(\/?)\s*>/gi;
  let m;
  while ((m = tagRe.exec(String(svg || "")))) {
    const isClose = m[1] === "/";
    const selfClose = m[4] === "/";
    if (isClose) depth = Math.max(0, depth - 1);
    else if (!selfClose) {
      depth += 1;
      if (depth > max) max = depth;
    }
  }
  return max;
}

// --- Slug --------------------------------------------------------------------

/** Slug = sanitised-name + issue/PR number, mirroring the theme slugger but
 *  defaulting to "animal". The number keeps slugs unique across submissions. */
export function slugifyAnimal(name, suffix) {
  const base =
    String(name || "animal")
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "")
      .slice(0, 40) || "animal";
  return suffix == null ? base : `${base}-${suffix}`;
}

// --- Contract gate -----------------------------------------------------------

/**
 * Validate + normalise a community animal descriptor.
 *
 * @param {object} input     the submitted `animal` object.
 * @param {object} [opts]
 * @param {string[]} [opts.existingIds] ids already in gallery/animals (collision check).
 * @returns {{ok:boolean, errors:string[], animal?:object}}
 *   On ok:true, `animal` is the cleaned, source-stamped def ready to wrap +
 *   codegen. On ok:false, `errors` lists every problem (so a submitter can fix
 *   them all at once).
 */
export function validateDescriptor(input, opts = {}) {
  const errors = [];
  const existing = new Set((opts.existingIds || []).map((s) => String(s).toLowerCase()));

  if (!input || typeof input !== "object" || Array.isArray(input)) {
    return { ok: false, errors: ["The submission isn't an animal object."] };
  }

  // 1. No JS / forbidden keys / function-valued fields.
  for (const k of Object.keys(input)) {
    if (FORBIDDEN_DEF_KEYS.has(k)) {
      if (k === "wingLeft" || k === "wingRight") {
        errors.push(`Put "${k}" inside \`parts\` (e.g. parts.${k}), not at the top level — it's a parrot slot.`);
      } else {
        errors.push(`Field "${k}" isn't allowed — community animals are declarative-only (no procedural \`${k}\`).`);
      }
    }
    if (typeof input[k] === "function") {
      errors.push(`Field "${k}" is a function; only data is accepted.`);
    }
  }

  // 2. Body plan.
  const type = input.type;
  if (!ANIMAL_TYPES.has(type)) {
    errors.push(`type must be one of: ${[...ANIMAL_TYPES].join(", ")} (got ${JSON.stringify(type)}). The "custom" (procedural JS) path is maintainer-only.`);
  }

  // 3. Identity.
  const id = String(input.id || "");
  if (!ID_RE.test(id)) {
    errors.push('id must match ^[a-z][a-z0-9-]{1,30}$ (lowercase letters, digits, hyphens; start with a letter).');
  } else if (RESERVED_IDS.has(id) && !opts.allowReservedIds) {
    errors.push(`id "${id}" is a built-in animal — choose a different id.`);
  } else if (existing.has(id)) {
    errors.push(`id "${id}" already exists in the gallery — choose a different id.`);
  }

  const name = String(input.name || "").trim();
  if (!name || name.length > NAME_MAX) {
    errors.push(`name is required and must be ≤ ${NAME_MAX} characters.`);
  }

  // 4. Licence (required — SVG art is copyrightable).
  const license = String(input.license || "");
  if (!LICENSES.has(license)) {
    errors.push(`license is required and must be one of: ${[...LICENSES].join(", ")}.`);
  }

  // 5. Colours — strict HSL triples; eye must be present + themeable.
  const colors = input.colors;
  let themeableCount = 0;
  let hasEye = false;
  if (!colors || typeof colors !== "object" || Array.isArray(colors)) {
    errors.push("colors must be an object of --animal-* HSL defaults (at minimum --animal-eye).");
  } else {
    for (const [k, v] of Object.entries(colors)) {
      if (!COLOR_KEY_RE.test(k)) {
        errors.push(`colors key "${k}" must look like --animal-<name>.`);
        continue;
      }
      if (typeof v !== "string" || !HSL_RE.test(v.trim())) {
        errors.push(`colors["${k}"] must be a bare HSL triple like "142 71% 45%" (got ${JSON.stringify(v)}).`);
        continue;
      }
      if (k === EYE_KEY) hasEye = true;
      else themeableCount += 1;
    }
    if (!hasEye) {
      errors.push(`colors must declare ${EYE_KEY} so the battery-state recolour works.`);
    }
  }

  // 6. The baked ⟹ memorial rule. "Baked" = no themeable token beyond the eye
  //    (the Mittens pattern: markings are literal hsl() in the parts). A baked
  //    animal is a tribute and MUST be tagged memorial (Rainbow Bridge).
  const memorial = input.memorial === true;
  if (input.memorial != null && typeof input.memorial !== "boolean") {
    errors.push("memorial must be true or false.");
  }
  const isBaked = themeableCount === 0;
  if (isBaked && !memorial) {
    errors.push(
      "This animal bakes its colours in (only the eye is themeable), so it must be a tribute: set memorial: true " +
        "and it joins the Rainbow Bridge — or expose a themeable --animal-* colours block to make it a regular companion.",
    );
  }

  // 7. Parts — required slots present, allowed keys only, non-empty, sized,
  //    and each passes the fail-closed SVG pre-scan.
  const parts = input.parts;
  if (!parts || typeof parts !== "object" || Array.isArray(parts)) {
    errors.push("parts must be an object of SVG markup strings, one per anatomical slot.");
  } else {
    const required = REQUIRED_PARTS[type] || REQUIRED_PARTS.quadruped;
    // Parrots may carry optional wingLeft/wingRight slots (shown in flight).
    const allowed = new Set([...required, ...OPTIONAL_PARTS, ...(type === "parrot" ? ["wingLeft", "wingRight"] : [])]);
    for (const slot of required) {
      const v = parts[slot];
      if (typeof v !== "string" || v.trim() === "") {
        errors.push(`parts.${slot} is required and must be a non-empty SVG string.`);
      }
    }
    let total = 0;
    for (const [slot, v] of Object.entries(parts)) {
      if (!allowed.has(slot)) {
        errors.push(`parts.${slot} isn't a recognised slot for a ${type} (allowed: ${[...allowed].join(", ")}).`);
        continue;
      }
      if (typeof v !== "string") {
        errors.push(`parts.${slot} must be an SVG string.`);
        continue;
      }
      const bytes = Buffer.byteLength(v, "utf8");
      total += bytes;
      if (bytes > MAX_PART_BYTES) {
        errors.push(`parts.${slot} is ${bytes} bytes — over the ${MAX_PART_BYTES}-byte per-slot limit.`);
      }
      const bad = quickRejectSvg(v);
      if (bad) errors.push(`parts.${slot} ${bad}.`);
    }
    if (total > MAX_TOTAL_BYTES) {
      errors.push(`The SVG parts total ${total} bytes — over the ${MAX_TOTAL_BYTES}-byte limit.`);
    }
  }

  // 8. Optional metadata — cleaned, never trusted. author_url reuses the theme
  //    URL policy verbatim (direct http(s), no shorteners; also XSS defence).
  const author = String(input.author || "").slice(0, META_MAX).trim();
  const rawUrl = String(input.author_url || "").slice(0, META_MAX).trim();
  const authorUrl = isAcceptableAuthorUrl(rawUrl) ? rawUrl : "";
  const authorUrlRejected = rawUrl !== "" && authorUrl === "";
  const submittedBy = String(input.submitted_by || "").slice(0, META_MAX).trim();
  const description = String(input.description || "").slice(0, DESC_MAX).trim();

  let tags = [];
  if (input.tags != null) {
    if (!Array.isArray(input.tags)) {
      errors.push("tags must be an array of strings.");
    } else {
      const seen = new Set();
      for (const raw of input.tags) {
        const tag = String(raw || "").trim().toLowerCase();
        if (!tag || tag.length > TAG_MAX || seen.has(tag)) continue;
        seen.add(tag);
        tags.push(tag);
        if (tags.length >= MAX_TAGS) break;
      }
    }
  }

  if (errors.length) return { ok: false, errors };

  // Build the cleaned def. source is stamped here, never read from input.
  const animal = {
    id,
    name,
    type,
    source: opts.source || "community",
    license,
    colors: { ...colors },
    parts: { ...parts },
  };
  if (memorial) animal.memorial = true;
  if (description) animal.description = description;
  if (author) animal.author = author;
  if (authorUrl) animal.author_url = authorUrl;
  if (submittedBy) animal.submitted_by = submittedBy;
  if (tags.length) animal.tags = tags;

  return { ok: true, errors: [], animal, meta: { authorUrlRejected } };
}

// --- Envelope + codegen ------------------------------------------------------

/** Wrap a validated animal in the gallery envelope written to
 *  gallery/animals/<slug>.json. `kind` discriminates it from theme envelopes. */
export function buildEnvelope(animal) {
  return { version: 1, kind: "animal", animal };
}

/** Escape a JSON string for safe embedding inside a generated .js source:
 *  JSON.stringify leaves <, > and U+2028/U+2029 raw, which are unsafe in a JS
 *  string literal / when inlined in HTML. Escaping them keeps the generated
 *  module robust no matter how it's later served. */
function jsSafeJson(value) {
  // JSON.stringify leaves <, >, U+2028 and U+2029 raw: <,> are unsafe if the
  // module is ever inlined in HTML, and the line/paragraph separators are
  // illegal inside a JS string literal. Escape all four, char by char — built
  // this way to avoid embedding a raw separator (or a regex literal matching
  // one) in this very file.
  let out = "";
  for (const ch of JSON.stringify(value, null, 2)) {
    const c = ch.charCodeAt(0);
    if (ch === "<") out += "\\u003c";
    else if (ch === ">") out += "\\u003e";
    else if (c === 0x2028) out += "\\u2028";
    else if (c === 0x2029) out += "\\u2029";
    else out += ch;
  }
  return out;
}

/**
 * Generate the animals/<id>.js module from a validated (and, in the real
 * pipeline, SVG-sanitised) animal. The def is embedded via JSON.stringify so
 * no SVG/string content can break out into executable code. Submitters never
 * write this file — the intake regenerates it from the .json source of truth.
 */
export function codegenAnimalModule(animal) {
  // Parrot wings ride in `parts` in the descriptor (so they're sanitised like
  // any slot), but the framework reads them at def-level — lift them back out.
  const { wingLeft, wingRight, ...parts } = animal.parts;
  const def = {
    label: animal.name,
    type: animal.type,
    ...(animal.memorial ? { memorial: true } : {}),
    colors: animal.colors,
    parts,
    ...(wingLeft ? { wingLeft } : {}),
    ...(wingRight ? { wingRight } : {}),
  };
  // First-party/bundled animals are authored as descriptors under animal-svg/src/;
  // community submissions live in gallery/animals/. Name the real source either way.
  const isCore = animal.source === "core";
  const kind = isCore ? "Bundled" : "Community";
  const sourcePath = isCore
    ? `custom_components/eufy_vacuum/frontend/animal-svg/src/${animal.id}.json`
    : `gallery/animals/${animal.id}.json`;
  return (
    `/* GENERATED — do not edit by hand.\n` +
    ` * ${kind} animal "${animal.id}" — ${animal.name}.\n` +
    ` * Source of truth: ${sourcePath}.\n` +
    ` * Regenerate via the animal intake (scripts/animal-descriptor.mjs); never hand-edit.\n` +
    ` */\n` +
    `(function () {\n` +
    `  AnimalSVG.register(${JSON.stringify(animal.id)}, ${jsSafeJson(def)});\n` +
    `})();\n`
  );
}
