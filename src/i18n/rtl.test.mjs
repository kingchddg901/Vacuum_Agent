import { test } from "node:test";
import assert from "node:assert/strict";

import { isRTL, applyDir, translate } from "./index.js";

const FSI = String.fromCodePoint(0x2068); // First Strong Isolate  (opens a bidi-isolated run)
const PDI = String.fromCodePoint(0x2069); // Pop Directional Isolate (closes it)

test("[RTL-1] Arabic / Hebrew / Persian / Urdu are RTL", () => {
  for (const code of ["ar", "he", "fa", "ur", "iw", "ps"]) {
    assert.equal(isRTL(code), true, `${code} should be RTL`);
  }
});

test("[RTL-2] LTR languages are not RTL", () => {
  for (const code of ["en", "de", "es", "fr", "it", "nl", "pt", "ru"]) {
    assert.equal(isRTL(code), false, `${code} should be LTR`);
  }
});

test("[RTL-3] region + casing are normalized off the base subtag", () => {
  assert.equal(isRTL("he-IL"), true);
  assert.equal(isRTL("ar_EG"), true);
  assert.equal(isRTL("AR"), true);
  assert.equal(isRTL("en-US"), false);
});

test("[RTL-4] empty / nullish is LTR (never throws)", () => {
  assert.equal(isRTL(""), false);
  assert.equal(isRTL(undefined), false);
  assert.equal(isRTL(null), false);
});

test("[RTL-5] applyDir stamps rtl/ltr on the host from the resolved lang", () => {
  const attrs = {};
  const host = { setAttribute: (k, v) => { attrs[k] = v; } };
  applyDir(host, "ar");
  assert.equal(attrs.dir, "rtl");
  applyDir(host, "en");
  assert.equal(attrs.dir, "ltr", "must flip back — never leaves a stale rtl");
});

test("[RTL-6] applyDir is safe on a missing host", () => {
  assert.doesNotThrow(() => applyDir(null, "ar"));
  assert.doesNotThrow(() => applyDir({}, "ar"));
});

test("[RTL-7] RTL locale isolates each substituted var in FSI…PDI", () => {
  // "ar" falls back to the English string (draft catalog may be absent) but the
  // resolved code is still RTL, so the embedded run is isolated regardless.
  const out = translate("ar", "bind_run_profiles.confirm_delete", { name: "Kitchen" });
  assert.ok(out.includes(`${FSI}Kitchen${PDI}`), out);
});

test("[RTL-8] LTR locale leaves substituted vars byte-identical (no isolates)", () => {
  const out = translate("en", "bind_run_profiles.confirm_delete", { name: "Kitchen" });
  assert.ok(!out.includes(FSI) && !out.includes(PDI), "no bidi controls in LTR output");
  assert.ok(out.includes("Kitchen"), out);
});

test("[RTL-9] plural {count} is isolated too (embedded LTR number)", () => {
  const out = translate("he", "base_station.recorded_count", { count: 5 });
  assert.ok(out.includes(`${FSI}5${PDI}`), out);
});

test("[RTL-10] a missing placeholder is left as the literal token, un-isolated", () => {
  // vars present but without the referenced key → the {name} token stays verbatim,
  // never wrapped (nothing was substituted).
  const out = translate("ar", "bind_run_profiles.confirm_delete", { other: "x" });
  assert.ok(out.includes("{name}"), out);
  assert.ok(!out.includes(`${FSI}{name}${PDI}`), "un-substituted token must not be isolated");
});
