// Run: node --test src/renderers/maintenance-census6.test.mjs
//
// CENSUS-6 — server-baked English reached the user in all 18 locales, two ways:
//   1. `attention_summary`, an English sentence composed in Python
//      (f"{n} upkeep item(s) need attention.") and rendered verbatim;
//   2. `*_status_label`, preferred OVER the card's own translated rendering —
//      `status_label ?? _formatMaintenanceStatus(code)` put the English first
//      while the machine code sat right there. Same precedence inversion
//      A5-AG-2 found in startBlockedReason.
//
// Coverage (C6 = Census 6):
//   [C6-1] a known status resolves to the TRANSLATION, not the server label
//   [C6-2] an UNKNOWN status still falls back to the server label (forward-compat)
//   [C6-3] no code and no label degrades to the formatted kind, never blank
//   [C6-4] the renderer no longer prefers status_label over the code
//   [C6-5] the attention summary is composed from the COUNT, with real plurals
//   [C6-6] an ABSENT count falls back to the server sentence, never "none"

import { test } from "node:test";
import assert from "node:assert/strict";

/** _maintenanceStatusText, transcribed from renderers/maintenance.js. */
function statusText(status, label, { known = ["good", "replace_now"] } = {}) {
  const host = {
    tRaw: (key) => {
      const code = key.replace("maintenance.status_", "");
      return known.includes(code) ? `T:${code}` : key;   // miss returns the key
    },
    _formatMaintenanceStatus: (s) => `KIND:${String(s ?? "unknown")}`,
  };
  const normalized = String(status ?? "").trim().toLowerCase();
  if (normalized) {
    const key = `maintenance.status_${normalized}`;
    const translated = host.tRaw(key);
    if (translated && translated !== key) return translated;
  }
  if (label) return String(label);
  return host._formatMaintenanceStatus(normalized || "unknown");
}

test("[C6-1] a known status resolves to the translation, not the server label", () => {
  assert.equal(statusText("replace_now", "Replace Now"), "T:replace_now");
  assert.equal(statusText("good", "Good"), "T:good");
});

test("[C6-2] an unknown status falls back to the server label", () => {
  // Forward-compat: a backend that adds a status this release has not keyed must
  // still render something real rather than a bare key or a blank.
  assert.equal(statusText("needs_descaling", "Needs Descaling"), "Needs Descaling");
});

test("[C6-3] no code and no label degrades to the formatted kind, never blank", () => {
  assert.equal(statusText(null, null), "KIND:unknown");
  assert.equal(statusText("", ""), "KIND:unknown");
});

test("[C6-4] the renderer no longer prefers status_label over the code", async () => {
  const fs = await import("node:fs");
  const src = fs.readFileSync(new URL("./maintenance.js", import.meta.url), "utf-8");

  assert.doesNotMatch(
    src,
    /item\?\.status_label \?\? this\._formatMaintenanceStatus/,
    "the label-first precedence is back"
  );
  assert.match(src, /_maintenanceStatusText\(item\?\.status/);
});

test("[C6-5] the attention summary is composed from the count", () => {
  const t = (key, vars = {}) => `${key}${vars.count != null ? `(${vars.count})` : ""}`;
  const compose = (upkeep) => {
    const raw = upkeep.attention_count != null ? Number(upkeep.attention_count) : NaN;
    return Number.isFinite(raw)
      ? (raw > 0 ? t("maintenance.attention_summary", { count: raw })
                 : t("maintenance.attention_summary_none"))
      : (upkeep.attention_summary ?? null);
  };

  assert.equal(compose({ attention_count: 3 }), "maintenance.attention_summary(3)");
  assert.equal(compose({ attention_count: 1 }), "maintenance.attention_summary(1)");
  assert.equal(compose({ attention_count: 0 }), "maintenance.attention_summary_none");
});

test("[C6-6] an ABSENT count falls back to the sentence, never 'none'", () => {
  // absent-is-not-zero, same call as REV-6: `?? 0` here would confidently claim
  // "no upkeep items need attention" on a payload that never said so.
  const compose = (upkeep) => {
    const raw = upkeep.attention_count != null ? Number(upkeep.attention_count) : NaN;
    return Number.isFinite(raw)
      ? (raw > 0 ? "COMPOSED" : "NONE")
      : (upkeep.attention_summary ?? null);
  };

  assert.equal(compose({ attention_summary: "3 upkeep item(s) need attention." }),
    "3 upkeep item(s) need attention.");
  assert.equal(compose({ attention_count: null, attention_summary: "server text" }), "server text");
  assert.equal(compose({}), null);
});

// [C6-7] SOURCE PIN for C6-5/C6-6 — added 2026-08-07 by the W0 v2 census.
//
// C6-5 and C6-6 above assert a `compose` TRANSCRIBED into this file. A
// transcription proves the intended semantics and nothing about the shipped
// renderer: the real composition is inline at renderers/maintenance.js and is
// referenced by no assertion in the suite. C6-4 already pins its half against
// source; this is the missing sibling.
//
// The forbidden shape is not hypothetical — `Number(upkeep.attention_count ?? 0)`
// EXISTS twelve lines below the real code (the `attentionCount` used for a stat
// tile, where zero-for-absent is harmless). One copy-paste up and an absent count
// renders a confident "No upkeep items need attention." on a payload that never
// said so, which is precisely C6-6's stated failure and the REV-6 bug class.
test("[C6-7] the SHIPPED attention summary still distinguishes absent from zero", async () => {
  const fs = await import("node:fs");
  const src = fs.readFileSync(new URL("./maintenance.js", import.meta.url), "utf-8");

  // The guard must be `!= null` FIRST, then finite — Number(null) is 0 and 0 IS
  // finite, so testing finiteness alone re-introduces the bug.
  assert.match(
    src,
    /attention_count\s*!=\s*null\s*\?\s*Number\(\s*upkeep\.attention_count\s*\)\s*:\s*NaN/,
    "the absent-vs-zero guard on attention_count is gone — an absent count will render "
    + "'No upkeep items need attention.' on a payload that never said so (C6-6)",
  );
  assert.match(
    src,
    /Number\.isFinite\(\s*_attentionCountRaw\s*\)/,
    "the finite check that routes an absent count to the server sentence is gone (C6-6)",
  );
  // And the summary must still be COMPOSED from the count rather than echoing a
  // server-baked English sentence when the count is present (C6-5, CENSUS-6).
  assert.match(
    src,
    /this\.t\(\s*["']maintenance\.attention_summary["']\s*,\s*\{\s*count:/,
    "the attention summary no longer interpolates the count through i18n — "
    + "server-baked English would reach every locale again (C6-5)",
  );
});
