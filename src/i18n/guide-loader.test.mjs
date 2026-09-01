// Unit tests for the guide loader (the bundle-en / serve-the-rest debundle of the
// upkeep-guide catalogs). Each asserts the INPUT that turns it red.
// Run: node --test src/i18n/guide-loader.test.mjs
import { test } from "node:test";
import assert from "node:assert/strict";
import {
  guideCatalog,
  registerGuideCatalog,
  loadGuideCatalog,
  ensureGuideLanguage,
} from "./guide-loader.js";

// A served catalog under a throwaway language that no other test/file uses, so
// registering it can never perturb a real language a sibling test relies on.
const ZZ = { standard: { main_brush: { steps: ["zz step"], notes: [], clean_frequency: "weekly", replace_frequency: null } } };
const okResp = (obj) => ({ ok: true, json: async () => obj });

// [GL-1] English is BUNDLED — available synchronously with no fetch. RED if the
// guide-translations.js import breaks or en is not seeded into the registry.
test("[GL-1] en is available synchronously from the bundle", () => {
  const en = guideCatalog("en");
  assert.ok(en && typeof en === "object", "en catalog must be present from the bundle");
  assert.ok(Object.keys(en).length > 0, "bundled en catalog must be non-empty");
});

// [GL-2] A served catalog registers and is then readable. RED if fetch→register
// wiring drops the payload.
test("[GL-2] loadGuideCatalog registers a served catalog", async () => {
  const ok = await loadGuideCatalog("served:zz", "zz", { fetchImpl: async () => okResp(ZZ) });
  assert.equal(ok, true);
  assert.deepEqual(guideCatalog("zz"), ZZ);
});

// [GL-3] English is NOT overridable (it is the universal fallback). RED if a
// served/registered en could replace the bundled base.
test("[GL-3] en is refused by register and load (bundled base is not overridable)", async () => {
  const before = guideCatalog("en");
  assert.equal(registerGuideCatalog("en", { standard: {} }), false);
  assert.equal(await loadGuideCatalog("served:en", "en", { fetchImpl: async () => okResp({ standard: {} }) }), false);
  assert.strictEqual(guideCatalog("en"), before, "en must be untouched");
});

// [GL-4] A failed fetch fails soft (false, no throw, registry intact). RED if a
// 404 throws or corrupts a language.
test("[GL-4] a failed fetch fails soft and leaves the registry intact", async () => {
  const ok = await loadGuideCatalog("served:de", "de", { fetchImpl: async () => ({ ok: false, status: 404 }) });
  assert.equal(ok, false);
  assert.equal(guideCatalog("de"), undefined);
});

// [GL-5] registerGuideCatalog rejects a non-object payload. RED if a hostile/
// malformed served file (array, null, string) could register.
test("[GL-5] a non-object catalog is rejected", () => {
  assert.equal(registerGuideCatalog("zz2", ["not", "an", "object"]), false);
  assert.equal(registerGuideCatalog("zz2", null), false);
  assert.equal(registerGuideCatalog("zz2", "nope"), false);
  assert.equal(guideCatalog("zz2"), undefined);
});

// [GL-6] ensureGuideLanguage fetches ONLY the active language — not all 17. RED if
// it reverted to a load-all sweep (the whole point of on-demand).
test("[GL-6] ensureGuideLanguage fetches only the active language", async () => {
  const urls = [];
  const fetchImpl = async (url) => { urls.push(String(url)); return okResp(ZZ); };
  const loaded = await ensureGuideLanguage("zzx", null, { fetchImpl, baseUrl: "/g", ver: "t" });
  assert.deepEqual(loaded, ["zzx"]);
  assert.deepEqual(urls, ["/g/zzx.json?v=t"], "must fetch exactly the one language file");
  assert.deepEqual(guideCatalog("zzx"), ZZ);
});

// [GL-7] A regional tag also pulls its base (pt-BR -> pt); en and already-loaded
// codes fetch nothing. RED if pt-BR misses pt, or if en/dup triggered a fetch.
test("[GL-7] ensureGuideLanguage adds the base for a regional tag, skips en/loaded", async () => {
  const urls = [];
  const fetchImpl = async (url) => { urls.push(String(url).split("?")[0]); return okResp(ZZ); };
  await ensureGuideLanguage("zy-REG", null, { fetchImpl, baseUrl: "/g" });
  assert.deepEqual(urls.sort(), ["/g/zy-REG.json", "/g/zy.json"]);
  // en never fetches; a re-request for already-loaded codes fetches nothing.
  const urls2 = [];
  const f2 = async (url) => { urls2.push(String(url)); return okResp(ZZ); };
  await ensureGuideLanguage("en", null, { fetchImpl: f2, baseUrl: "/g" });
  await ensureGuideLanguage("zy-REG", null, { fetchImpl: f2, baseUrl: "/g" });
  assert.deepEqual(urls2, [], "en + already-loaded must not re-fetch");
});
