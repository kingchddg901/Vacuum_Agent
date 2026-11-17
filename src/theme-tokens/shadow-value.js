/**
 * ============================================================
 * BOX-SHADOW VALUE: PARSE AND FORMAT
 * ============================================================
 *
 * The editor's 16 `shadow`-type tokens are one free-text box holding a whole CSS
 * box-shadow. This module is the half that lets a real control exist: it takes a stored
 * value apart into editable parts and puts it back together again, and it is deliberately
 * the only place that knows the grammar.
 *
 * IT IS A LAYER LIST, NOT FIVE FIELDS, and that is the data's doing rather than a design
 * preference. Measured against the saved themes on a real install: of the 8 shadow values
 * any theme actually stores, 3 are single-layer, 4 are two-layer and 1 is three-layer --
 * so a five-field single-shadow control would have covered 37% and punted the rest to a
 * text box. The stacks are not incidental either: `0 0 0 1px rgba(...)` layered under a
 * blur is the standard ring-plus-shadow idiom, and five fields cannot express it at all.
 * The SHIPPED DEFAULTS are all single-layer, which is why reading them first gave the
 * wrong answer.
 *
 * WHAT COUNTS AS DECOMPOSABLE. A value is only taken apart when every layer is a plain
 * `[inset] <len> <len> [<len> [<len>]] [<color>]`, the lengths are literals and the colour
 * is one the swatch can actually edit. Anything else -- a `var()` or `calc()` in a length
 * slot, a whole value that is itself a `var()` reference, a colour the control cannot
 * round-trip -- returns `ok: false` and the caller keeps the text box. FAILING OPEN IS THE
 * POINT: a control that silently rewrites `var(--evcc-shadow-hover, ...)` into something
 * else would destroy a deliberate reference, and the user could not see why.
 *
 * `none` AND EMPTY ARE DIFFERENT, and conflating them would be a real bug. An empty token
 * is UNSET and inherits; `none` is an explicit instruction to have no shadow, which
 * overrides an inherited one. So `none` parses to zero layers with `explicitNone: true`,
 * and `formatShadow([])` emits `none` rather than an empty string -- removing the last
 * layer means "no shadow", while clearing the token entirely is what Reset is for.
 *
 * Lives in theme-tokens/ rather than beside the renderer because it is pure and needs
 * tests: see [SHV-*], whose acceptance corpus is the 8 real stored values.
 * ============================================================
 */

/** Length-ish: a number with an optional CSS unit. `0` alone is legal in a shadow. */
const LENGTH_RE = /^[+-]?(?:\d*\.\d+|\d+)(?:px|rem|em|%|vh|vw|vmin|vmax|ch|ex)?$/i;

/** A colour the swatch can round-trip. Deliberately NOT var()/currentColor: see header. */
const COLOR_RE = /^(?:#[0-9a-f]{3,8}|rgba?\([^)]*\)|hsla?\([^)]*\))$/i;

/**
 * Split on TOP-LEVEL commas only. `rgba(0, 0, 0, .5)` carries three commas of its own,
 * so a naive split(",") shreds every real value in the corpus.
 */
export function splitShadowLayers(value) {
  const raw = String(value ?? "").trim();
  if (!raw) return [];
  const out = [];
  let depth = 0;
  let cur = "";
  for (const ch of raw) {
    if (ch === "(") depth += 1;
    else if (ch === ")") depth -= 1;
    if (ch === "," && depth === 0) {
      out.push(cur.trim());
      cur = "";
    } else {
      cur += ch;
    }
  }
  if (cur.trim()) out.push(cur.trim());
  return out.filter((s) => s.length > 0);
}

/** Whitespace-split one layer, keeping bracketed groups whole. */
function tokenise(layer) {
  const out = [];
  let depth = 0;
  let cur = "";
  for (const ch of layer) {
    if (ch === "(") depth += 1;
    else if (ch === ")") depth -= 1;
    if (/\s/.test(ch) && depth === 0) {
      if (cur) { out.push(cur); cur = ""; }
    } else {
      cur += ch;
    }
  }
  if (cur) out.push(cur);
  return out;
}

/**
 * One layer -> { inset, x, y, blur, spread, color } or null when it cannot be edited.
 * CSS lets `inset` and the colour sit anywhere in the layer, so they are picked out by
 * what they ARE rather than by position; the lengths keep their order.
 */
export function parseShadowLayer(layer) {
  const parts = tokenise(String(layer ?? "").trim());
  if (!parts.length) return null;

  let inset = false;
  let color = "";
  const lengths = [];

  for (const p of parts) {
    if (/^inset$/i.test(p)) {
      if (inset) return null;            // twice is not valid CSS
      inset = true;
    } else if (LENGTH_RE.test(p)) {
      lengths.push(p);
    } else if (COLOR_RE.test(p)) {
      if (color) return null;            // two colours is not valid CSS
      color = p;
    } else {
      return null;                        // var(), calc(), currentColor, a keyword...
    }
  }

  // CSS requires offset-x and offset-y; blur and spread are optional, in that order.
  if (lengths.length < 2 || lengths.length > 4) return null;

  return {
    inset,
    x: lengths[0],
    y: lengths[1],
    blur: lengths[2] ?? "",
    spread: lengths[3] ?? "",
    color,
  };
}

/** One layer object -> a CSS layer string. Omits what was never there. */
export function formatShadowLayer(layer) {
  if (!layer) return "";
  const bits = [];
  if (layer.inset) bits.push("inset");
  bits.push(String(layer.x ?? "0").trim() || "0");
  bits.push(String(layer.y ?? "0").trim() || "0");
  // Spread without blur is not expressible, so a spread forces a blur of 0.
  const blur = String(layer.blur ?? "").trim();
  const spread = String(layer.spread ?? "").trim();
  if (blur || spread) bits.push(blur || "0");
  if (spread) bits.push(spread);
  const color = String(layer.color ?? "").trim();
  if (color) bits.push(color);
  return bits.join(" ");
}

/**
 * A whole token value -> editable layers, or a refusal the caller can act on.
 *
 * @returns {{ok: true, layers: object[], explicitNone: boolean}
 *          | {ok: false, reason: string, layers: null}}
 */
export function parseShadow(value) {
  const raw = String(value ?? "").trim();
  if (!raw) return { ok: true, layers: [], explicitNone: false };
  if (/^none$/i.test(raw)) return { ok: true, layers: [], explicitNone: true };

  const chunks = splitShadowLayers(raw);
  if (!chunks.length) return { ok: true, layers: [], explicitNone: false };

  const layers = [];
  for (const chunk of chunks) {
    const parsed = parseShadowLayer(chunk);
    if (!parsed) {
      return {
        ok: false,
        layers: null,
        reason: `layer ${JSON.stringify(chunk)} is not a plain [inset] x y [blur [spread]] [color]`,
      };
    }
    layers.push(parsed);
  }
  return { ok: true, layers, explicitNone: false };
}

/**
 * Layers -> a CSS value. ZERO LAYERS EMITS `none`, not "": removing the last layer is an
 * instruction to have no shadow, and an empty token would instead inherit one. Clearing
 * the token is what the row's Reset does.
 */
export function formatShadow(layers) {
  const list = (Array.isArray(layers) ? layers : []).map(formatShadowLayer).filter(Boolean);
  return list.length ? list.join(", ") : "none";
}
