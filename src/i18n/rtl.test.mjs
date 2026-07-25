import { test } from "node:test";
import assert from "node:assert/strict";

import { isRTL, applyDir } from "./index.js";

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
