#!/usr/bin/env node
/**
 * Report the EFFECTIVE tags (derived ∪ verified ∪ vibe) for every gallery theme.
 * Handy to eyeball the taxonomy as the gallery grows.
 *   node scripts/theme-tags-report.mjs            # tags only
 *   node scripts/theme-tags-report.mjs --cvd      # + why a colorblind-safe request was withheld
 *   node scripts/theme-tags-report.mjs --metrics  # + the raw numbers
 */
import { readFileSync, readdirSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { effectiveThemeTags, themeMetrics } from "../src/theme-tags/index.mjs";

const repo = join(dirname(fileURLToPath(import.meta.url)), "..");
const dir = join(repo, "gallery", "themes");
const files = readdirSync(dir).filter((f) => f.endsWith(".json")).sort();
const wantCvd = process.argv.includes("--cvd");
const wantMetrics = process.argv.includes("--metrics");

for (const f of files) {
  const env = JSON.parse(readFileSync(join(dir, f), "utf8"));
  const th = env.theme || env;
  const { tags, colorblind } = effectiveThemeTags(th);
  console.log((th.name || f).slice(0, 22).padEnd(23) + tags.join(" "));
  if (wantCvd && !colorblind.verified) {
    const why = colorblind.reasons.slice(0, 2).map((r) => `${r.pair.join("/")}@${r.cvd.slice(0, 4)}=${r.deltaE}`).join("  ");
    console.log("      cvd fail (minΔE " + colorblind.minDeltaE + ")  " + why);
  }
  if (wantMetrics) {
    const m = themeMetrics({ ...(th.tokens || {}), ...(th.colors || {}) });
    console.log(`      [L${m.baseLum.toFixed(3)} acc h${m.accentHue.toFixed(0)}/s${m.accentSat.toFixed(2)} txt${m.textContrast.toFixed(1)} bsat${m.baseSat.toFixed(2)}]`);
  }
}
