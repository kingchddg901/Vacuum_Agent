// Run: node --test src/renderers/i18n-escaping-contract.test.mjs
//
// live:I18N-1 — renderers/shared.js documented tRaw as "STILL escapes
// interpolated values". It never has. Both t() and tRaw() insert vars RAW; the
// only difference is whether the CATALOG STRING is escaped.
//
// That was a documentation defect rather than a live hole — every tRaw call site
// lands in a sink that escapes — but a future caller who trusted the sentence
// and skipped escaping at a NEW sink would open one, with the docstring reading
// as justification in review. So the contract is pinned by EXECUTION here, not
// described in prose that can drift again.
//
// Coverage (IEC = I18n Escaping Contract):
//   [IEC-1] t() escapes the CATALOG string
//   [IEC-2] tRaw() does NOT escape the catalog string (that is its whole job)
//   [IEC-3] NEITHER escapes interpolated values — the documented-wrong part
//   [IEC-4] the docstring no longer claims otherwise

import { test } from "node:test";
import assert from "node:assert/strict";

import { translate } from "../i18n/index.js";

// A key whose English carries no markup, so any escaping we see is ours.
const KEY = "bind_setup.failed_add_vacuum";
const PAYLOAD = '<img src=x onerror=alert(1)>';

test("[IEC-1] t() escapes the catalog string", () => {
  // en.js's setup.delete_type_confirm carries authored <strong>, so t() must
  // neutralise it while tRaw() must not — that difference IS the pairing.
  const escaped = translate("en", "setup.delete_type_confirm", { name: "x" });
  assert.ok(!escaped.includes("<strong>"), "t() let authored markup through");
  assert.match(escaped, /&lt;strong&gt;/);
});

test("[IEC-2] tRaw() does not escape the catalog string", () => {
  const raw = translate("en", "setup.delete_type_confirm", { name: "x" }, { raw: true });
  assert.ok(raw.includes("<strong>"), "tRaw() escaped authored markup — its one job");
});

test("[IEC-3] NEITHER escapes interpolated values", () => {
  // The claim the docstring got wrong. Vars are the CALLER's to escape, in both.
  const viaT = translate("en", KEY, { error: PAYLOAD });
  const viaTRaw = translate("en", KEY, { error: PAYLOAD }, { raw: true });

  assert.ok(viaT.includes(PAYLOAD), "t() escaped a var — the sink contract changed");
  assert.ok(viaTRaw.includes(PAYLOAD), "tRaw() escaped a var — the docstring would be right and the code changed");
  assert.equal(viaT.includes("&lt;img"), false);
  assert.equal(viaTRaw.includes("&lt;img"), false);
});

test("[IEC-4] the docstring no longer claims tRaw escapes vars", async () => {
  const fs = await import("node:fs");
  const src = fs.readFileSync(new URL("./shared.js", import.meta.url), "utf-8");
  // Matches the ORIGINAL sentence ("…survives, but STILL escapes interpolated
  // values"), not the corrected docstring's QUOTATION of it — the quote is
  // deliberate documentation and must not trip its own guard.
  assert.doesNotMatch(
    src,
    /but STILL escapes interpolated/,
    "the incorrect claim is back in the docstring",
  );
  // The positive marker is the load-bearing half: revert the correction and this
  // disappears, whatever the wording around it.
  assert.match(src, /INTERPOLATED VALUES ARE INSERTED RAW/);
});
