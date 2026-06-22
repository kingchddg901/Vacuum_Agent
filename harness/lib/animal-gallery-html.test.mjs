/**
 * Tests for the animal gallery HTML generator. Pure (no Playwright) — the
 * emphasis is the security surface: an untrusted author_url must never become a
 * live javascript: link on the public Pages site, and markup must be escaped.
 *
 *   node --test harness/lib/animal-gallery-html.test.mjs
 */
import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, mkdirSync, readFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { safeHttpUrl, attributionHtml, filterTokensFor, writeAnimalPage, writeAnimalIndex } from "./animal-gallery-html.mjs";

test("[AG-1] safeHttpUrl keeps http(s), drops dangerous schemes", () => {
  assert.equal(safeHttpUrl("https://example.com/x"), "https://example.com/x");
  assert.equal(safeHttpUrl("http://example.com"), "http://example.com");
  assert.equal(safeHttpUrl("javascript:alert(1)"), "");
  assert.equal(safeHttpUrl("data:text/html,x"), "");
  assert.equal(safeHttpUrl(""), "");
});

test("[AG-2] attributionHtml links only safe urls + escapes markup", () => {
  const ok = attributionHtml({ author: "Pat", author_url: "https://example.com/pat" });
  assert.match(ok, /href="https:\/\/example\.com\/pat"/);
  const bad = attributionHtml({ author: "<b>x</b>", author_url: "javascript:alert(1)" });
  assert.ok(!/javascript:/i.test(bad), bad);
  assert.ok(!/<b>/.test(bad), bad);
  assert.match(bad, /&lt;b&gt;/);
});

test("[AG-3] filterTokensFor: type / companion|memorial / license / source", () => {
  const t = filterTokensFor({ type: "quadruped", license: "CC0-1.0", source: "community" });
  assert.ok(t.includes("quadruped") && t.includes("companion") && t.includes("cc0-1.0") && t.includes("community"));
  const m = filterTokensFor({ type: "quadruped", license: "MIT", source: "community", memorial: true });
  assert.ok(m.includes("memorial") && !m.includes("companion"));
});

test("[AG-4] writeAnimalPage + writeAnimalIndex emit valid-looking HTML", () => {
  const root = mkdtempSync(join(tmpdir(), "animgal-"));
  const animal = {
    id: "fox", name: "Fox", type: "quadruped", license: "CC0-1.0", source: "community",
    colors: { "--animal-eye": "1 2% 3%", "--animal-fur": "4 5% 6%" }, tags: ["red"],
    description: "A red fox.", author: "Vacuum Agent",
  };
  const sub = join(root, "fox");
  mkdirSync(sub, { recursive: true });
  writeAnimalPage(sub, animal, [{ pose: "standing", file: "pose-standing.png" }], { download: "fox.json" });
  const page = readFileSync(join(sub, "index.html"), "utf8");
  assert.match(page, /Fox/);
  assert.match(page, /all animals/);
  assert.match(page, /pose-standing\.png/);
  assert.ok(!/<script>/.test(page), "no stray script");

  writeAnimalIndex(
    [{ id: "fox", animal, filterTokens: filterTokensFor(animal), download: "fox.json" }],
    root,
  );
  const index = readFileSync(join(root, "index.html"), "utf8");
  assert.match(index, /animal gallery/);
  assert.match(index, /animal-submission\.yml/); // submit link
  assert.match(index, /data-tags="[^"]*quadruped/); // filter dataset
});
