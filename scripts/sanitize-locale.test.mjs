/**
 * ============================================================
 * LOCALE INTAKE GATE — adversarial tests (real-browser)
 * ============================================================
 *
 * The sibling to check-i18n.mjs's Trust-Model-B contract: that proves the
 * translate()-time ESCAPE; THIS proves the intake GATE (sanitize-or-quarantine)
 * that runs before registerLocale on the untrusted drop-in path.
 *
 * WHY A REAL BROWSER (Playwright Chromium), not jsdom — same reason as the animal
 * SVG sanitiser: the gate defends against the SAME parser the innerHTML sink will
 * later run; jsdom's parser differs, and that gap is where mutation-XSS hides. So
 * we bundle the real src/i18n/index.js, run loadLocale() (gate included) IN the
 * page against page-side fixtures, and assert the end-to-end outcome.
 *
 *   docker run --rm -v "$PWD":/work -w /work \
 *     mcr.microsoft.com/playwright:v1.60.0-noble \
 *     node --test scripts/sanitize-locale.test.mjs
 * ============================================================
 */
import { test, before, after } from "node:test";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";
import { build } from "esbuild";

const HERE = dirname(fileURLToPath(import.meta.url));
let browser, page;

before(async () => {
  // Bundle the REAL i18n module (gate + DOMPurify) into one IIFE for the page.
  const result = await build({
    entryPoints: [resolve(HERE, "../src/i18n/index.js")],
    bundle: true,
    format: "iife",
    globalName: "I18N",
    write: false,
    logLevel: "silent",
  });
  const code = result.outputFiles[0].text;

  const { chromium } = await import("playwright");
  browser = await chromium.launch();
  page = await browser.newPage();
  await page.setContent("<!doctype html><title>locale gate</title>");
  await page.addScriptTag({ content: code });
});

after(async () => { if (browser) await browser.close(); });

/**
 * Load a flat locale object as an UNTRUSTED ("custom") drop-in, in the page.
 * Returns { report, quarantine, value } where `value` is the registered raw
 * (tRaw) string for the probe key, or the key itself if nothing registered.
 */
async function loadCustom(catalog, { probe = "common.save", code = "zz" } = {}) {
  return page.evaluate(
    async ({ catalog, probe, code }) => {
      const text = JSON.stringify(catalog);
      const fetchImpl = async () => ({
        ok: true,
        status: 200,
        async text() { return text; },
        async json() { return JSON.parse(text); },
      });
      const report = await window.I18N.loadLocale("drop.json", code, { fetchImpl, status: "custom" });
      const quarantine = window.I18N.getLocaleQuarantineReport();
      const value = window.I18N.translate(code, probe, null, { raw: true });
      return { report, quarantine, value };
    },
    { catalog, probe, code },
  );
}

// §7.1 — active tags / event handlers → QUARANTINE_HOSTILE, named key + predicate.
test("[GATE-1] <script>/<iframe>/onerror/onclick quarantine the whole file", async () => {
  for (const [payload, pred] of [
    ["<script>alert(1)</script>", "dangerous_tag"],
    ["<iframe src=https://x></iframe>", "dangerous_tag"],
    ['<img src=x onerror="alert(1)">', "event_handler"],
    ['<b onclick="x()">hi</b>', "event_handler"],
  ]) {
    const { report, quarantine, value } = await loadCustom({ "common.save": payload });
    assert.equal(report.ok, false, `loaded a hostile file: ${payload}`);
    assert.ok(report.errors.join(" ").includes("QUARANTINE_HOSTILE"), report.errors.join(" "));
    assert.ok(quarantine.some((q) => q.predicate === pred && q.firstOffendingKey === "common.save"), JSON.stringify(quarantine));
    // Quarantined → the custom value never registered; translate falls back to the
    // English base ("Save"), so no hostile markup reached the catalog.
    assert.ok(!value.includes("<"), `hostile markup reached the catalog: ${value}`);
  }
});

// §7.2 — javascript: URL, incl whitespace/entity padding → quarantine (parse, not regex).
test("[GATE-2] javascript: href (padded) quarantines", async () => {
  for (const href of ["javascript:alert(1)", "java\tscript:alert(1)", "java&#9;script:alert(1)", "  JAVASCRIPT:alert(1)", "//evil.example/x"]) {
    const { report, quarantine } = await loadCustom({ "common.save": `<a href="${href}">x</a>` });
    assert.equal(report.ok, false, `loaded a hostile href: ${href}`);
    assert.ok(quarantine.some((q) => q.predicate === "dangerous_url_scheme"), `${href}: ${JSON.stringify(quarantine)}`);
  }
});

// §7.3 — active content INSIDE a plural form → quarantine (recursive walk).
test("[GATE-3] active content in a plural form quarantines", async () => {
  const { report, quarantine } = await loadCustom({
    "common.save": { one: "clean", other: '<img src=x onerror="alert(1)">' },
  });
  assert.equal(report.ok, false);
  assert.ok(quarantine.some((q) => q.predicate === "event_handler" && q.firstOffendingKey === "common.save.other"), JSON.stringify(quarantine));
});

// §7.4 — inert junk scrubs: file LOADS, <span> escaped-visible, allowlist survives.
test("[GATE-4] inert disallowed tags scrub to visible text; allowlist survives", async () => {
  const { report, value } = await loadCustom({
    "common.save": '<span>x</span> <strong>bold</strong> <code>c</code> <a href="https://github.com/a/b">link</a>',
  });
  assert.equal(report.ok, true, report.errors.join(" "));
  assert.ok(value.includes("&lt;span&gt;x&lt;/span&gt;"), `span not escaped-visible: ${value}`);
  assert.ok(value.includes("<strong>bold</strong>"), `strong stripped: ${value}`);
  assert.ok(value.includes("<code>c</code>"), `code stripped: ${value}`);
  assert.ok(value.includes('<a href="https://github.com/a/b">link</a>'), `allowed href dropped: ${value}`);
});

// §7.5 — <a href> to an off-allowlist host → scrub (href stripped, text kept), NOT quarantine.
test("[GATE-5] off-allowlist host scrubs the href, keeps the text", async () => {
  const before = await page.evaluate(() => window.I18N.getLocaleQuarantineReport().length);
  const { report, quarantine, value } = await loadCustom({
    "common.save": '<a href="https://evil.example/x">click</a>',
  });
  assert.equal(report.ok, true, report.errors.join(" "));
  assert.equal(quarantine.length, before, "off-host was quarantined (should scrub, not quarantine)");
  assert.ok(value.includes("<a>click</a>"), `href not stripped / text lost: ${value}`);
  assert.ok(!value.includes("evil.example"), `off-host href survived: ${value}`);
});

// §7.6 — same hostile bytes → silent skip; changed bytes → re-evaluated.
test("[GATE-6] hash-keyed quarantine: same bytes silent, changed bytes re-eval", async () => {
  const before = await page.evaluate(() => window.I18N.getLocaleQuarantineReport().length);
  const payload = { "common.save": "<script>boom</script>" };
  await loadCustom(payload);
  const afterFirst = await page.evaluate(() => window.I18N.getLocaleQuarantineReport().length);
  assert.equal(afterFirst, before + 1, "first hostile load did not record one quarantine");
  await loadCustom(payload); // identical bytes
  const afterSecond = await page.evaluate(() => window.I18N.getLocaleQuarantineReport().length);
  assert.equal(afterSecond, afterFirst, "identical bytes re-alarmed (should be silent)");
  // A CHANGED file (new hash) is re-evaluated — a clean replacement loads.
  const { report } = await loadCustom({ "common.save": "<strong>fixed</strong>" });
  assert.equal(report.ok, true, "fixed replacement did not clear quarantine");
});

// [GATE-8] mutation-XSS classics + namespace confusion → the scrubbed value, when
// RENDERED the way a tRaw sink does, must produce only inert DOM (real property).
test("[GATE-8] mXSS / namespace payloads render inert", async () => {
  const payloads = [
    "<math><mtext><table><mglyph><style><img src=x onerror=alert(1)></style></mglyph></table></mtext></math>",
    "<svg><foreignObject><iframe src=javascript:alert(1)></iframe></foreignObject></svg>",
    "<noscript><p title=\"</noscript><img src=x onerror=alert(1)>\">",
    "<svg><a><set attributeName=href to=javascript:alert(1)></set></a></svg>",
    "<template><script>alert(1)</script></template>",
  ];
  for (const p of payloads) {
    const { report, value } = await loadCustom({ "common.save": p });
    if (!report.ok) continue; // quarantined → fine
    const bad = await page.evaluate((html) => {
      const d = document.createElement("div");
      d.innerHTML = html; // exactly what a tRaw sink does
      const tags = d.querySelectorAll("script,img,iframe,svg,math,style,set,object,embed,form,link,meta,base").length;
      let handlers = 0;
      d.querySelectorAll("*").forEach((el) => { for (const a of el.attributes) if (/^on/i.test(a.name)) handlers++; });
      return { tags, handlers };
    }, value);
    assert.equal(bad.tags, 0, `live dangerous element rendered from: ${p} → ${value}`);
    assert.equal(bad.handlers, 0, `live event handler rendered from: ${p} → ${value}`);
  }
});

// [GATE-9] a surviving <a href> must RESOLVE only to an allowlisted host (the
// property that matters — backslash/@/userinfo tricks are judged by resolution).
test("[GATE-9] surviving hrefs resolve only to allowlisted hosts", async () => {
  const ALLOW = new Set(["github.com", "kingchddg901.github.io"]);
  for (const href of [
    "https://github.com.evil.com/x",
    "https://github.com@evil.com/x",
    "https://evil.com/github.com",
    "https://GitHub.com.evil.com",
    "https://github.com\\@evil.com",
  ]) {
    const { report, value } = await loadCustom({ "common.save": `<a href="${href}">x</a>` });
    if (!report.ok) continue;
    const host = await page.evaluate((html) => {
      const d = document.createElement("div");
      d.innerHTML = html;
      const a = d.querySelector("a[href]");
      return a ? a.hostname.toLowerCase() : null;
    }, value);
    if (host !== null) assert.ok(ALLOW.has(host), `surviving href resolves off-host: ${href} → ${host}`);
  }
});

// §7.7 — malformed JSON → REJECT_MALFORMED, NOT hash-locked (no quarantine entry).
test("[GATE-7] malformed JSON soft-skips, never hash-locks", async () => {
  const out = await page.evaluate(async () => {
    const fetchImpl = async () => ({ ok: true, status: 200, async text() { return "{ not json"; }, async json() { throw new Error("bad"); } });
    const before = window.I18N.getLocaleQuarantineReport().length;
    const report = await window.I18N.loadLocale("bad.json", "qq", { fetchImpl, status: "custom" });
    const after = window.I18N.getLocaleQuarantineReport().length;
    return { report, before, after };
  });
  assert.equal(out.report.ok, false);
  assert.ok(out.report.errors.join(" ").includes("REJECT_MALFORMED"), out.report.errors.join(" "));
  assert.equal(out.after, out.before, "malformed JSON was hash-locked (should not be)");
});
