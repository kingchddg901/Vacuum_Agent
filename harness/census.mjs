#!/usr/bin/env node
/**
 * Census: render every tab with the Wave-1 stub and record which state
 * accessors (and any direct `_hass` reaches) each tab touches.
 *
 *   node harness/census.mjs   ->   harness/out/census.json
 *
 * Two uses:
 *  - seeds Wave 2 fixtures (the real per-tab accessor surface), and
 *  - surfaces renderer contract breaches: any `_hass.*` path means a
 *    renderer reached into hass directly instead of through `state`.
 */
import { chromium } from "@playwright/test";
import { mkdirSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { mountHarness, renderTab, VIEW_ORDER } from "./lib/mount-page.mjs";

const here = dirname(fileURLToPath(import.meta.url));

const browser = await chromium.launch();
const page = await browser.newPage();
await mountHarness(page);

const perTab = {};
const hassReaches = {};
const distinct = new Set();

for (const view of VIEW_ORDER) {
  const res = await renderTab(page, view);
  perTab[view] = res.misses.state;
  res.misses.state.forEach((m) => distinct.add(m.split(".")[0]));
  if (res.misses.hass.length) hassReaches[view] = res.misses.hass;
}

await browser.close();

mkdirSync(join(here, "out"), { recursive: true });
writeFileSync(
  join(here, "out", "census.json"),
  JSON.stringify(
    { distinctStateAccessors: [...distinct].sort(), perTab, hassReaches },
    null,
    2,
  ),
);

console.log(`distinct state accessors touched: ${distinct.size}`);
const breached = Object.keys(hassReaches);
console.log(
  breached.length
    ? `WARN direct _hass reaches (contract breaches) in: ${breached.join(", ")}`
    : "no direct _hass reaches — renderers stay within the state/ctx contract",
);
console.log("wrote harness/out/census.json");
