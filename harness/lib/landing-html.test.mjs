/**
 * Tests for the landing page + the shared site nav. Pure (no browser).
 *   node --test harness/lib/landing-html.test.mjs
 */
import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, readFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { writeLanding } from "./landing-html.mjs";
import { siteNav } from "./site-nav.mjs";

test("[NAV-1] siteNav links to all sections, depth-prefixed, active marked", () => {
  const root = siteNav(0, "home");
  assert.match(root, /href="themes\/"/);
  assert.match(root, /href="animals\/"/);
  assert.match(root, /href="docs\/"/);
  assert.match(root, /class="active"/); // home active

  const detail = siteNav(2, "animals");
  assert.match(detail, /href="\.\.\/\.\.\/themes\/"/); // depth-2 prefix
  assert.match(detail, /href="\.\.\/\.\.\/docs\/"/);
});

test("[LND-1] landing hub links to themes/animals/docs + repo, with counts + nav", () => {
  const dir = mkdtempSync(join(tmpdir(), "landing-"));
  writeLanding(dir, { themeCount: 3, animalCount: 6, repoUrl: "https://github.com/x/y" });
  const html = readFileSync(join(dir, "index.html"), "utf8");
  assert.match(html, /Vacuum Agent/);
  assert.match(html, /href="themes\/"/);
  assert.match(html, /href="animals\/"/);
  assert.match(html, /href="docs\/"/);
  assert.match(html, /github\.com\/x\/y/);
  assert.match(html, /class="site-nav"/);
  assert.match(html, />3</); // theme count
  assert.match(html, />6</); // animal count
  assert.ok(!/<script/.test(html), "landing has no scripts");
});
