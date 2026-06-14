#!/usr/bin/env node
/**
 * FAST dry-run of the gallery index — no Chromium render. It runs every committed
 * theme through the SAME shared generator (lib/gallery-html.mjs) that preview.mjs
 * uses, but draws a cheap palette-swatch thumbnail instead of rendering the card.
 * Purpose: eyeball the faceted filter bar / tag chips / author credit / search over
 * the real corpus in seconds.
 *
 *   node harness/preview-index-dryrun.mjs
 *   -> harness/out/preview-dryrun/index.html
 *
 * By default it reflects the REAL committed metadata. Pass --demo to overlay a few
 * in-memory author/community examples (to exercise the author credit + community
 * source rendering before real submissions exist); --demo never touches the files.
 */
import { readFileSync, readdirSync, writeFileSync, mkdirSync, copyFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { deflateSync } from "node:zlib";
import { effectiveThemeTags, themeAttribution, parseColor } from "../src/theme-tags/index.mjs";
import { writeThemePage, writeIndex } from "./lib/gallery-html.mjs";

const here = dirname(fileURLToPath(import.meta.url));
const repo = join(here, "..");
const THEMES = join(repo, "gallery", "themes");
const OUT = join(repo, "harness", "out", "preview-dryrun");

const USE_DEMO = process.argv.includes("--demo");

/* DEMO ONLY (--demo) — in-memory attribution to preview author/community rendering.
   Keyed by theme id. Real files are untouched. */
const DEMO = {
  theme_jewel_spiral: { source: "core" },
  theme_nightfall_coast: { source: "core" },
  theme_aurora_duet: { source: "community", author: "Ada L.", author_url: "https://github.com/example" },
  theme_orange_aurora: { source: "community", author: "K. Rivera", submitted_by: "kingchddg901" },
  theme_green_airglow: { source: "generated", tags: ["colorblind-safe", "aurora"] }, // claims CB but fails -> tag silently stripped; "aurora" vibe tag stays
};

/* ---- minimal solid-rect RGBA PNG encoder (palette swatch thumbnails) ---- */
const CRC = (() => {
  const t = new Uint32Array(256);
  for (let n = 0; n < 256; n++) {
    let c = n;
    for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
    t[n] = c >>> 0;
  }
  return t;
})();
function crc32(buf) {
  let c = 0xffffffff;
  for (let i = 0; i < buf.length; i++) c = CRC[(c ^ buf[i]) & 0xff] ^ (c >>> 8);
  return (c ^ 0xffffffff) >>> 0;
}
function chunk(type, data) {
  const len = Buffer.alloc(4);
  len.writeUInt32BE(data.length, 0);
  const td = Buffer.concat([Buffer.from(type, "latin1"), data]);
  const crc = Buffer.alloc(4);
  crc.writeUInt32BE(crc32(td), 0);
  return Buffer.concat([len, td, crc]);
}
function png(w, h, rgbaAt) {
  const raw = Buffer.alloc((w * 4 + 1) * h);
  let p = 0;
  for (let y = 0; y < h; y++) {
    raw[p++] = 0; // filter: none
    for (let x = 0; x < w; x++) {
      const [r, g, b, a] = rgbaAt(x, y);
      raw[p++] = r; raw[p++] = g; raw[p++] = b; raw[p++] = a;
    }
  }
  const ihdr = Buffer.alloc(13);
  ihdr.writeUInt32BE(w, 0); ihdr.writeUInt32BE(h, 4);
  ihdr[8] = 8; ihdr[9] = 6; // 8-bit, RGBA
  return Buffer.concat([
    Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
    chunk("IHDR", ihdr),
    chunk("IDAT", deflateSync(raw)),
    chunk("IEND", Buffer.alloc(0)),
  ]);
}
const rgb = (hex, fb) => parseColor(hex) || parseColor(fb) || { r: 30, g: 34, b: 40 };

/** Card-like palette swatch: base field, accent header bar, four semantic dots. */
function swatch(colors) {
  const W = 260, H = 150;
  const base = rgb(colors["--evcc-surface-base"], "#14181d");
  const panel = rgb(colors["--evcc-surface-panel"], "#1b212a");
  const accent = rgb(colors["--evcc-accent"], "#5aa9ff");
  const text = rgb(colors["--evcc-text-primary"], "#e6e9ee");
  const sems = ["success", "warning", "error", "info"].map((n) => rgb(colors[`--evcc-sem-${n}`]));
  return png(W, H, (x, y) => {
    if (y < 34) return [accent.r, accent.g, accent.b, 255]; // header
    // a "card" panel inset
    const inCard = x > 16 && x < W - 16 && y > 48 && y < H - 16;
    let c = inCard ? panel : base;
    // text bar
    if (inCard && y > 60 && y < 70 && x > 28 && x < 150) c = text;
    // four semantic dots
    if (inCard && y > 96 && y < 116) {
      for (let i = 0; i < 4; i++) {
        const cx = 40 + i * 36;
        if ((x - cx) ** 2 + (y - 106) ** 2 < 90) c = sems[i];
      }
    }
    return [c.r, c.g, c.b, 255];
  });
}

const files = readdirSync(THEMES).filter((f) => f.endsWith(".json")).sort();
mkdirSync(OUT, { recursive: true });
const processed = [];

for (const f of files) {
  const env = JSON.parse(readFileSync(join(THEMES, f), "utf8"));
  const th = { ...(env.theme || {}) };
  const name = f.replace(/\.json$/, "");
  if (USE_DEMO && DEMO[th.id]) Object.assign(th, DEMO[th.id]); // optional demo overlay (in-memory)

  const { tags, colorblind } = effectiveThemeTags(th);
  const attr = themeAttribution(th);
  const filterTokens = [...new Set([...tags, ...(attr.source ? [attr.source] : [])])];

  const dir = join(OUT, name);
  mkdirSync(dir, { recursive: true });
  writeFileSync(join(dir, "thumb.png"), swatch(th.colors || {}));
  // Copy the real export (not the demo overlay) so the download link works.
  const downloadFile = `${name}.json`;
  copyFileSync(join(THEMES, f), join(dir, downloadFile));

  const report = { keyCount: Object.keys(th.colors || {}).length, clamped: 0, skippedKeys: [], ok: true };
  writeThemePage(dir, th.name || name, [], report, [], { tags, attr, colorblind, download: downloadFile });
  processed.push({ name, themeName: th.name || name, scope: [], report, tags, attr, filterTokens, download: downloadFile });
}

writeIndex(processed, OUT);
console.log(`dry-run index -> ${join(OUT, "index.html")} (${processed.length} themes)`);
